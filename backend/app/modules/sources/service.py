import asyncio
import hashlib
import uuid
from typing import Optional, List, Tuple
from sqlalchemy import select, and_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.exceptions import AppException, AuthorizationError
from app.modules.sources.models import (
    SourceDocument,
    SourceDocumentCourseOffering,
    SourceDocumentCurriculumVersion,
    SourceExtraction,
    SourceChunk,
    SourceAsset,
)
from app.modules.sources.storage import StorageService
from app.modules.sources.extractors import DocumentExtractionEngine, ExtractionResult
from app.modules.sources.embeddings import compute_batch_embeddings, invalidate_course_rag_cache
from app.modules.jobs.service import JobService
from app.modules.jobs.models import BackgroundJob
from app.modules.sources.academic_pipeline import process_academic_document
from app.modules.academics.models import (
    CourseOffering,
    CourseOfferingEnrolment,
    CourseOfferingFaculty,
    CurriculumSubjectEntry,
    CurriculumVersion,
)
from app.modules.auth.models import InstitutionMembership


class SourceService:
    """Document upload, secure storage, provenance-preserving extraction, and access control."""

    @staticmethod
    async def upload_source_document(
        db: AsyncSession,
        institution_id: uuid.UUID,
        user_id: uuid.UUID,
        user_role: str,
        file_bytes: bytes,
        original_filename: str,
        source_type: str = "syllabus",
        visibility: str = "course",
        course_offering_id: Optional[uuid.UUID] = None,
        curriculum_version_id: Optional[uuid.UUID] = None,
    ) -> Tuple[SourceDocument, Optional[uuid.UUID], bool]:
        """
        Upload and register source document.
        Enforces course-assignment authorization for teachers.
        Returns (SourceDocument, background_job_id, already_uploaded).
        """
        # Resolve membership
        mem_stmt = select(InstitutionMembership).where(
            and_(
                InstitutionMembership.institution_id == institution_id,
                InstitutionMembership.user_id == user_id,
                InstitutionMembership.membership_status == "active",
            )
        )
        mem = (await db.execute(mem_stmt)).scalars().first()
        if not mem:
            raise AuthorizationError("Active institutional membership required to upload documents.")

        # Check authorization for course offering scope
        if course_offering_id:
            offering = await db.get(CourseOffering, course_offering_id)
            if not offering or offering.institution_id != institution_id:
                raise AppException(code="OFFERING_NOT_FOUND", message="Target course offering not found.", status_code=404)

            # If teacher, verify explicit assignment to offering
            if user_role == "TEACHER":
                fac_stmt = select(CourseOfferingFaculty).where(
                    and_(
                        CourseOfferingFaculty.course_offering_id == course_offering_id,
                        CourseOfferingFaculty.institution_membership_id == mem.id,
                        CourseOfferingFaculty.status == "active",
                    )
                )
                if not (await db.execute(fac_stmt)).scalars().first():
                    raise AuthorizationError("Access forbidden: You are not assigned to this course offering.")

        if curriculum_version_id:
            ver = await db.get(CurriculumVersion, curriculum_version_id)
            if not ver or ver.institution_id != institution_id:
                raise AppException(code="CURRICULUM_NOT_FOUND", message="Target curriculum version not found.", status_code=404)

        file_extension, _ = StorageService.validate_file(original_filename, len(file_bytes))
        checksum = hashlib.sha256(file_bytes).hexdigest()
        # File identity is its checksum; changing the upload label or target
        # must not create another source record, extraction, or job.
        dedupe_key = checksum

        # Serialize same-content uploads on PostgreSQL; the unique constraint below
        # remains the final guard if two requests reach the insert simultaneously.
        if db.bind and db.bind.dialect.name == "postgresql":
            await db.execute(
                text("SELECT pg_advisory_xact_lock(hashtext(:dedupe_key))"),
                {"dedupe_key": f"{institution_id}:{dedupe_key}"},
            )

        existing_stmt = select(SourceDocument).where(
            SourceDocument.institution_id == institution_id,
            SourceDocument.content_dedupe_key == dedupe_key,
        ).order_by(SourceDocument.created_at.asc())
        existing = (await db.execute(existing_stmt)).scalars().first()
        if existing:
            if course_offering_id:
                offering_link = await db.get(
                    SourceDocumentCourseOffering, (existing.id, course_offering_id)
                )
                if not offering_link:
                    db.add(SourceDocumentCourseOffering(
                        source_document_id=existing.id,
                        institution_id=institution_id,
                        course_offering_id=course_offering_id,
                    ))
            if curriculum_version_id:
                curriculum_link = await db.get(
                    SourceDocumentCurriculumVersion, (existing.id, curriculum_version_id)
                )
                if not curriculum_link:
                    db.add(SourceDocumentCurriculumVersion(
                        source_document_id=existing.id,
                        institution_id=institution_id,
                        curriculum_version_id=curriculum_version_id,
                    ))

            prior_job_stmt = select(BackgroundJob).where(
                BackgroundJob.job_type == "extract_source_document",
                BackgroundJob.target_entity_type == "source_document",
                BackgroundJob.target_entity_id == existing.id,
            ).order_by(BackgroundJob.created_at.desc())
            prior_job = (await db.execute(prior_job_stmt)).scalars().first()
            if prior_job:
                await db.commit()
                await db.refresh(existing)
                return existing, prior_job.id, True

            if existing.status == "processed":
                await db.commit()
                await db.refresh(existing)
                return existing, None, True

            # Recover an incomplete legacy record with no corresponding job.
            storage_key = existing.storage_key
            mime_type = existing.mime_type
            size_bytes = existing.size_bytes
            doc = existing
        else:
            # Bytes are stored only once for identical tenant-scoped content.
            storage_key, mime_type, size_bytes, checksum = await StorageService.store_file(
                content=file_bytes,
                original_filename=original_filename,
                institution_id=institution_id,
            )

            doc = SourceDocument(
                id=uuid.uuid4(),
                institution_id=institution_id,
                uploaded_by_membership_id=mem.id,
                original_filename=original_filename,
                display_filename=original_filename,
                storage_backend="local",
                storage_key=storage_key,
                mime_type=mime_type,
                file_extension=file_extension,
                size_bytes=size_bytes,
                sha256_checksum=checksum,
                content_dedupe_key=dedupe_key,
                source_type=source_type,
                status="uploaded",
                visibility=visibility,
            )
            db.add(doc)
            await db.flush()

            # Link to offering or curriculum version.
            if course_offering_id:
                db.add(SourceDocumentCourseOffering(
                    source_document_id=doc.id,
                    institution_id=institution_id,
                    course_offering_id=course_offering_id,
                ))
            if curriculum_version_id:
                db.add(SourceDocumentCurriculumVersion(
                    source_document_id=doc.id,
                    institution_id=institution_id,
                    curriculum_version_id=curriculum_version_id,
                ))

        # Enqueue background extraction job
        job = await JobService.enqueue_job(
            db=db,
            job_type="extract_source_document",
            target_entity_type="source_document",
            target_entity_id=doc.id,
            input_reference_json={
                "source_document_id": str(doc.id),
                "storage_key": storage_key,
                "file_extension": doc.file_extension,
                "original_filename": original_filename,
            },
            institution_id=institution_id,
            requested_by_user_id=user_id,
            scope_course_offering_id=course_offering_id,
        )

        await db.commit()
        invalidate_course_rag_cache()
        await db.refresh(doc)
        return doc, job.id, existing is not None

    @staticmethod
    async def process_extraction_job(db: AsyncSession, job_id: uuid.UUID) -> ExtractionResult:
        """
        Execute document extraction within the background worker lifecycle.
        Updates job checkpoints, persists chunks with provenance, and records warnings.
        """
        job = await JobService.get_job_status(db, job_id)
        if not job or not job.target_entity_id:
            raise AppException(code="INVALID_JOB", message="Invalid background job entity.", status_code=400)

        doc_id = job.target_entity_id
        doc = await db.get(SourceDocument, doc_id)
        if not doc:
            await JobService.fail_job(db, job_id, "DOC_NOT_FOUND", "Source document record not found.", retry=False)
            raise AppException(code="DOCUMENT_NOT_FOUND", message="Source document record not found.", status_code=404)

        if (job.input_reference_json or {}).get("academic_only") and doc.status != "processed":
            await JobService.fail_job(db,job_id,"SOURCE_NOT_EXTRACTED","Academic-only recovery requires saved processed source chunks; raw extraction was not restarted.",retry=False)
            return ExtractionResult("DoubtDesk-Resume","1.0","failed",[],[],[],doc.sha256_checksum)

        # A provider-quota deferral happens after deterministic extraction has committed.
        # Resume only the academic stage so source chunks/assets are never duplicated.
        if doc.status == "processed":
            await JobService.update_progress(db, job_id, "academic_analysis", 92.0, "Resuming academic analysis from persisted source chunks.")
            academic_summary = await process_academic_document(db, doc, job_id)
            if academic_summary.get("deferred"):
                return ExtractionResult("DoubtDesk-Resume", "1.0", "succeeded", [], [], [], doc.sha256_checksum)
            current_job = await db.get(BackgroundJob, job_id)
            if current_job:
                diagnostics = dict(current_job.checkpoint_json or {})
                diagnostics["academic_extraction"] = academic_summary
                current_job.checkpoint_json=diagnostics
                await db.commit()
            payload={"academic_extraction":academic_summary,"resumed_from_persisted_source_chunks":True}
            if academic_summary.get("complete") or (academic_summary.get("skipped") and academic_summary.get("waiting_for") in {None,"syllabus","question_paper"}):
                await JobService.complete_job(db,job_id,result_reference_json=payload)
            else:
                await JobService.fail_job(db,job_id,"ACADEMIC_EXTRACTION_FAILED",academic_summary.get("safe_error_summary") or "Academic preparation is incomplete. Saved source chunks and validated batches are retained.",retry=bool(academic_summary.get("retryable")))
            return ExtractionResult("DoubtDesk-Resume","1.0","succeeded",[],[],[],doc.sha256_checksum)

        # Update stage
        await JobService.update_progress(db, job_id, "reading_file", 15.0, f"Reading {doc.original_filename} from storage.")
        doc.status = "processing"
        await db.commit()

        # Read file bytes
        file_bytes = await StorageService.retrieve_file(doc.storage_key)

        await JobService.update_progress(db, job_id, "parsing_content", 35.0, f"Parsing {doc.file_extension.upper()} structure, text, and diagram architectures.")
        result = await asyncio.to_thread(
            DocumentExtractionEngine.extract,
            file_bytes=file_bytes,
            file_extension=doc.file_extension,
            filename=doc.original_filename,
        )

        # Persist extraction record
        await JobService.update_progress(
            db, job_id, "persisting_provenance", 65.0,
            f"Extracted {len(result.chunks)} text blocks and {len(result.assets)} visual assets. Saving provenance."
        )
        extraction = SourceExtraction(
            id=uuid.uuid4(),
            institution_id=doc.institution_id,
            source_document_id=doc.id,
            extractor_name=result.extractor_name,
            extractor_version=result.extractor_version,
            status=result.status,
            warnings_json=result.warnings,
            error_code=result.error_code,
            safe_error_summary=result.safe_error_summary,
            raw_text_checksum=result.raw_text_checksum,
        )
        db.add(extraction)
        await db.flush()

        # Persist source chunks verbatim with parser provenance; academic AI is a later stage.
        persisted_chunks = []
        for chunk in result.chunks:
            source_chunk = SourceChunk(
                    id=uuid.uuid4(),
                    institution_id=doc.institution_id,
                    source_document_id=doc.id,
                    source_extraction_id=extraction.id,
                    chunk_index=chunk.chunk_index,
                    page_number=chunk.page_number,
                    slide_number=chunk.slide_number,
                    section_path=chunk.section_path,
                    chunk_type=chunk.chunk_type,
                    content_text=chunk.content_text,
                    content_hash=chunk.content_hash,
                    metadata_json=chunk.metadata_json,
                )
            db.add(source_chunk)
            persisted_chunks.append(source_chunk)
        await db.flush()

        # Compute semantic embeddings for document chunks with database and cache deduplication
        if persisted_chunks:
            # 1. Check existing embeddings across database by content_hash to avoid redundant API calls
            hashes = [c.content_hash for c in persisted_chunks if c.content_hash]
            existing_embeddings: dict[str, list] = {}
            if hashes:
                existing_res = await db.execute(
                    select(SourceChunk.content_hash, SourceChunk.embedding_json)
                    .where(SourceChunk.content_hash.in_(hashes), SourceChunk.embedding_json.isnot(None))
                )
                for row in existing_res.all():
                    if row[0] and row[1]:
                        existing_embeddings[row[0]] = row[1]

            chunks_needing_embed = []
            for sc in persisted_chunks:
                if sc.content_hash in existing_embeddings:
                    sc.embedding_json = existing_embeddings[sc.content_hash]
                elif not sc.embedding_json:
                    chunks_needing_embed.append(sc)

            if chunks_needing_embed:
                reused_count = len(persisted_chunks) - len(chunks_needing_embed)
                await JobService.update_progress(
                    db, job_id, "generating_embeddings", 78.0,
                    f"Generating Gemini semantic vector embeddings for {len(chunks_needing_embed)} chunks ({reused_count} reused from DB/cache)."
                )
                try:
                    texts_to_embed = [c.content_text for c in chunks_needing_embed]
                    embeddings = await compute_batch_embeddings(texts_to_embed)
                    for sc, emb in zip(chunks_needing_embed, embeddings):
                        if emb:
                            sc.embedding_json = emb
                    await db.flush()
                except Exception as emb_exc:
                    logger.debug("Failed computing chunk embeddings: %s", emb_exc)
            else:
                logger.info("[SourceService] 100%% of chunk embeddings (%d) reused from database! 0 API calls.", len(persisted_chunks))

        # Persist assets
        await JobService.update_progress(
            db, job_id, "persisting_assets", 86.0,
            f"Archiving {len(result.assets)} visual educational assets."
        )
        for asset in result.assets:
            # Store asset bytes
            asset_key = f"{doc.institution_id}/assets/{asset.sha256_checksum}.bin"
            db.add(
                SourceAsset(
                    id=uuid.uuid4(),
                    institution_id=doc.institution_id,
                    source_document_id=doc.id,
                    source_extraction_id=extraction.id,
                    storage_backend="local",
                    storage_key=asset_key,
                    asset_type=asset.asset_type,
                    page_number=asset.page_number,
                    slide_number=asset.slide_number,
                    surrounding_text=asset.surrounding_text,
                    sha256_checksum=asset.sha256_checksum,
                    metadata_json=asset.metadata_json,
                )
            )

        # Update document status
        if result.status in ("succeeded", "partial"):
            doc.status = "processed"
            # A course upload is a teaching resource, not an approval workflow.
            # Once extraction succeeds, make it available to enrolled students.
            doc.review_status = "approved"
            doc.publication_status = "published"
            await db.commit()
            invalidate_course_rag_cache()
            await JobService.update_progress(db, job_id, "academic_analysis", 92.0, "Analyzing validated syllabus and examination content.")
            academic_summary = await process_academic_document(db, doc, job_id)
            if academic_summary.get("deferred"):
                return result
            current_job = await db.get(BackgroundJob, job_id)
            if current_job:
                diagnostics = dict(current_job.checkpoint_json or {})
                diagnostics["academic_extraction"] = academic_summary
                current_job.checkpoint_json = diagnostics
                await db.commit()
            result_payload = {
                    "extraction_id": str(extraction.id),
                    "chunks_extracted": len(result.chunks),
                    "assets_extracted": len(result.assets),
                    "warnings": result.warnings,
                    "status": result.status,
                    "academic_extraction": academic_summary,
                }
            if academic_summary.get("complete") or (academic_summary.get("skipped") and academic_summary.get("waiting_for") in {None,"syllabus","question_paper"}):
                await JobService.complete_job(db, job_id, result_reference_json=result_payload)
            else:
                await JobService.fail_job(
                    db, job_id, error_code="ACADEMIC_EXTRACTION_FAILED",
                    safe_error_summary=academic_summary.get("safe_error_summary") or "Academic preparation is incomplete. Saved source chunks and validated batches are retained.",
                    retry=bool(academic_summary.get("retryable")),
                )
        else:
            doc.status = "failed"
            await db.commit()
            await JobService.fail_job(
                db,
                job_id,
                error_code=result.error_code or "EXTRACTION_FAILED",
                safe_error_summary=result.safe_error_summary or "Document extraction yielded no usable content.",
                retry=False,
            )

        return result

    @staticmethod
    async def get_document(
        db: AsyncSession, document_id: uuid.UUID, user_id: uuid.UUID, user_role: str, institution_id: Optional[str]
    ) -> SourceDocument:
        """Retrieve document metadata with multi-tenant and role scope verification."""
        doc = await db.get(SourceDocument, document_id)
        if not doc:
            raise AppException(code="DOCUMENT_NOT_FOUND", message="Source document not found.", status_code=404)

        if user_role == "SUPER_ADMIN":
            return doc

        if not institution_id or str(doc.institution_id) != institution_id:
            raise AuthorizationError("Access forbidden: Document belongs to another institution.")

        if user_role == "ADMIN":
            return doc

        membership_stmt = select(InstitutionMembership).where(
            and_(
                InstitutionMembership.institution_id == doc.institution_id,
                InstitutionMembership.user_id == user_id,
                InstitutionMembership.membership_status == "active",
            )
        )
        membership = (await db.execute(membership_stmt)).scalars().first()
        if not membership:
            raise AuthorizationError("Access forbidden: Active institutional membership required.")

        if doc.uploaded_by_membership_id == membership.id:
            if user_role == "STUDENT" and (doc.status != "processed" or doc.publication_status == "rejected"):
                raise AppException(code="DOCUMENT_NOT_FOUND", message="Source document not found.", status_code=404)
            return doc

        if doc.visibility == "institution":
            if user_role == "STUDENT" and (doc.status != "processed" or doc.publication_status == "rejected"):
                raise AppException(code="DOCUMENT_NOT_FOUND", message="Source document not found.", status_code=404)
            return doc
        if doc.visibility != "course":
            raise AuthorizationError("Access forbidden: Document is private to its uploader.")

        offering_stmt = select(SourceDocumentCourseOffering.course_offering_id).where(
            SourceDocumentCourseOffering.source_document_id == doc.id
        )
        offering_ids = list((await db.execute(offering_stmt)).scalars().all())

        curriculum_stmt = select(SourceDocumentCurriculumVersion.curriculum_version_id).where(
            SourceDocumentCurriculumVersion.source_document_id == doc.id
        )
        curriculum_ids = list((await db.execute(curriculum_stmt)).scalars().all())
        if curriculum_ids:
            curriculum_offerings_stmt = (
                select(CourseOffering.id)
                .join(
                    CurriculumSubjectEntry,
                    CurriculumSubjectEntry.id == CourseOffering.curriculum_subject_entry_id,
                )
                .where(CurriculumSubjectEntry.curriculum_version_id.in_(curriculum_ids))
            )
            offering_ids.extend((await db.execute(curriculum_offerings_stmt)).scalars().all())

        offering_ids = list(set(offering_ids))
        if not offering_ids:
            raise AuthorizationError("Access forbidden: Document is not shared with one of your courses.")

        if user_role == "TEACHER":
            access_stmt = select(CourseOfferingFaculty.course_offering_id).where(
                and_(
                    CourseOfferingFaculty.course_offering_id.in_(offering_ids),
                    CourseOfferingFaculty.institution_membership_id == membership.id,
                    CourseOfferingFaculty.status == "active",
                )
            )
        elif user_role == "STUDENT":
            access_stmt = select(CourseOfferingEnrolment.course_offering_id).where(
                and_(
                    CourseOfferingEnrolment.course_offering_id.in_(offering_ids),
                    CourseOfferingEnrolment.institution_membership_id == membership.id,
                    CourseOfferingEnrolment.enrolment_status == "active",
                )
            )
        else:
            raise AuthorizationError("Access forbidden: Role cannot access source documents.")

        if not (await db.execute(access_stmt)).scalars().first():
            raise AuthorizationError("Access forbidden: Document is not shared with one of your courses.")

        if user_role == "STUDENT" and (
            doc.status != "processed"
            or doc.publication_status == "rejected"
        ):
            raise AppException(code="DOCUMENT_NOT_FOUND", message="Source document not found.", status_code=404)

        return doc

    @staticmethod
    async def set_publication_status(
        db: AsyncSession,
        document_id: uuid.UUID,
        user_id: uuid.UUID,
        institution_id: str,
        publication_status: Optional[str] = None,
        review_status: Optional[str] = None,
    ) -> SourceDocument:
        """Record academic review separately from student-facing publication."""
        if publication_status not in {None, "published", "rejected"} or review_status not in {None, "approved", "rejected"} or (publication_status is None and review_status is None):
            raise AppException(
                code="INVALID_MATERIAL_REVIEW",
                message="Choose a valid review or publication action.",
                status_code=422,
            )
        doc = await SourceService.get_document(
            db, document_id, user_id, "TEACHER", institution_id
        )
        if doc.status != "processed":
            raise AppException(
                code="DOCUMENT_NOT_READY_FOR_REVIEW",
                message="Wait for document extraction to finish before reviewing it.",
                status_code=409,
            )

        membership_stmt = select(InstitutionMembership).where(
            InstitutionMembership.institution_id == doc.institution_id,
            InstitutionMembership.user_id == user_id,
            InstitutionMembership.membership_status == "active",
        )
        membership = (await db.execute(membership_stmt)).scalars().first()
        linked_offerings_stmt = select(SourceDocumentCourseOffering.course_offering_id).where(
            SourceDocumentCourseOffering.source_document_id == doc.id
        )
        offering_ids = (await db.execute(linked_offerings_stmt)).scalars().all()
        if not offering_ids or not membership:
            raise AuthorizationError("Only faculty assigned to the linked course can review this material.")
        assignment_stmt = select(CourseOfferingFaculty.id).where(
            CourseOfferingFaculty.course_offering_id.in_(offering_ids),
            CourseOfferingFaculty.institution_membership_id == membership.id,
            CourseOfferingFaculty.status == "active",
        )
        if not (await db.execute(assignment_stmt)).scalars().first():
            raise AuthorizationError("Only faculty assigned to the linked course can review this material.")

        if review_status is not None:
            doc.review_status = review_status
            if review_status == "rejected":
                doc.publication_status = "rejected"
        if publication_status == "published" and doc.review_status != "approved":
            raise AppException(
                code="MATERIAL_REVIEW_REQUIRED",
                message="Approve this material before publishing it to students.",
                status_code=409,
            )
        if publication_status is not None:
            doc.publication_status = publication_status
        await db.commit()
        invalidate_course_rag_cache()
        await db.refresh(doc)
        return doc

    @staticmethod
    async def get_extractions(
        db: AsyncSession, document_id: uuid.UUID
    ) -> List[SourceExtraction]:
        stmt = (
            select(SourceExtraction)
            .where(SourceExtraction.source_document_id == document_id)
            .options(selectinload(SourceExtraction.chunks), selectinload(SourceExtraction.assets))
            .order_by(SourceExtraction.created_at.desc())
        )
        res = await db.execute(stmt)
        return list(res.scalars().all())

    @staticmethod
    async def download_file(
        db: AsyncSession, document_id: uuid.UUID, user_id: uuid.UUID, user_role: str, institution_id: Optional[str]
    ) -> Tuple[bytes, str, str]:
        """Verify access and return (bytes, mime_type, original_filename)."""
        doc = await SourceService.get_document(db, document_id, user_id, user_role, institution_id)
        file_bytes = await StorageService.retrieve_file(doc.storage_key)
        return file_bytes, doc.mime_type, doc.original_filename
