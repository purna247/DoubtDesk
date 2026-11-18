import uuid
import hashlib
from datetime import datetime, timezone
from collections import Counter
from typing import Optional, List
from urllib.parse import quote
from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, status
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.common.exceptions import AppException
from app.modules.rbac.dependencies import get_current_user, require_teacher, require_student
from app.modules.auth.schemas import UserProfile
from app.modules.auth.models import InstitutionMembership
from app.modules.academics.models import (
    CanonicalSubject,
    CourseOffering,
    CourseOfferingEnrolment,
    CourseOfferingFaculty,
    CurriculumSubjectEntry,
)
from app.modules.sources.models import SourceDocument, SourceDocumentCourseOffering
from app.modules.sources.schemas import (
    SourceDocumentOut,
    SourceExtractionOut,
    SourceChunkOut,
    DocumentUploadResponse,
    JobStatusResponse,
    JobEventOut,
    StudentStudyMaterialOut,
    SourceDocumentReviewRequest,
    TeacherSourceMaterialOut,
    RagSearchResultOut,
    AcademicRetryResponse,
)
from app.modules.sources.service import SourceService
from app.modules.jobs.service import JobService
from app.modules.jobs.models import BackgroundJob
from app.modules.sources.academic_models import AcademicExtractionRun, AcademicExtractionBatch
from sqlalchemy import and_, select

router = APIRouter(tags=["Source Documents & Processing Jobs"])
settings = get_settings()


def _get_tenant_id(user: UserProfile) -> uuid.UUID:
    if not user.institution_id:
        raise AppException(code="NO_TENANT_CONTEXT", message="Institution context required.", status_code=400)
    return uuid.UUID(user.institution_id)


# ------------------------------------------------------------------------------
# Source Documents Upload & Inspection
# ------------------------------------------------------------------------------

@router.get("/sources/student/materials", response_model=List[StudentStudyMaterialOut])
async def list_student_study_materials(
    user: UserProfile = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> List[StudentStudyMaterialOut]:
    """List processed course files shared with this student's active offerings."""
    tenant_id = _get_tenant_id(user)
    stmt = (
        select(
            SourceDocument,
            CourseOffering.id.label("course_offering_id"),
            CurriculumSubjectEntry.official_subject_code.label("subject_code"),
            CanonicalSubject.name.label("subject_name"),
            CourseOffering.section_code.label("section_code"),
        )
        .join(
            SourceDocumentCourseOffering,
            SourceDocumentCourseOffering.source_document_id == SourceDocument.id,
        )
        .join(CourseOffering, CourseOffering.id == SourceDocumentCourseOffering.course_offering_id)
        .join(CourseOfferingEnrolment, CourseOfferingEnrolment.course_offering_id == CourseOffering.id)
        .join(InstitutionMembership, InstitutionMembership.id == CourseOfferingEnrolment.institution_membership_id)
        .join(CurriculumSubjectEntry, CurriculumSubjectEntry.id == CourseOffering.curriculum_subject_entry_id)
        .join(CanonicalSubject, CanonicalSubject.id == CurriculumSubjectEntry.canonical_subject_id)
        .where(
            and_(
                SourceDocument.institution_id == tenant_id,
                SourceDocument.visibility == "course",
                SourceDocument.status == "processed",
                SourceDocument.publication_status != "rejected",
                SourceDocumentCourseOffering.institution_id == tenant_id,
                CourseOffering.status == "active",
                CourseOfferingEnrolment.enrolment_status == "active",
                InstitutionMembership.institution_id == tenant_id,
                InstitutionMembership.user_id == uuid.UUID(user.id),
                InstitutionMembership.membership_status == "active",
            )
        )
        .order_by(SourceDocument.created_at.desc(), SourceDocument.original_filename.asc())
    )
    rows = (await db.execute(stmt)).all()
    materials = []
    seen_content_per_offering: set[tuple[uuid.UUID, str]] = set()
    for document, course_offering_id, subject_code, subject_name, section_code in rows:
        # Also suppress historical duplicate records created before checksum
        # deduplication was enforced, so students see one card per file/course.
        dedupe_identity = (course_offering_id, document.sha256_checksum)
        if dedupe_identity in seen_content_per_offering:
            continue
        seen_content_per_offering.add(dedupe_identity)
        materials.append(StudentStudyMaterialOut(
            id=str(document.id),
            course_offering_id=str(course_offering_id),
            original_filename=document.original_filename,
            source_type=document.source_type,
            mime_type=document.mime_type,
            size_bytes=document.size_bytes,
            created_at=document.created_at,
            subject_code=subject_code,
            subject_name=subject_name,
            section_code=section_code,
        ))
    return materials


@router.get("/sources/teacher/materials", response_model=List[TeacherSourceMaterialOut])
async def list_teacher_course_materials(
    course_offering_id: uuid.UUID,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> List[TeacherSourceMaterialOut]:
    """Return the persistent material library and latest processing status for one assigned course."""
    tenant_id = _get_tenant_id(user)
    offering = await db.get(CourseOffering, course_offering_id)
    if not offering or offering.institution_id != tenant_id:
        raise AppException(code="OFFERING_NOT_FOUND", message="Course offering not found.", status_code=404)
    membership_stmt = select(InstitutionMembership).where(
        InstitutionMembership.institution_id == tenant_id,
        InstitutionMembership.user_id == uuid.UUID(user.id),
        InstitutionMembership.membership_status == "active",
    )
    membership = (await db.execute(membership_stmt)).scalars().first()
    if not membership:
        raise AppException(code="MEMBERSHIP_REQUIRED", message="Active institutional membership required.", status_code=403)
    if user.role == "TEACHER":
        assignment_stmt = select(CourseOfferingFaculty.id).where(
            CourseOfferingFaculty.course_offering_id == course_offering_id,
            CourseOfferingFaculty.institution_membership_id == membership.id,
            CourseOfferingFaculty.status == "active",
        )
        if not (await db.execute(assignment_stmt)).scalars().first():
            raise AppException(code="COURSE_ASSIGNMENT_REQUIRED", message="Teacher is not assigned to this course.", status_code=403)

    documents_stmt = (
        select(SourceDocument)
        .join(SourceDocumentCourseOffering, SourceDocumentCourseOffering.source_document_id == SourceDocument.id)
        .where(
            SourceDocument.institution_id == tenant_id,
            SourceDocumentCourseOffering.institution_id == tenant_id,
            SourceDocumentCourseOffering.course_offering_id == course_offering_id,
        )
        .order_by(SourceDocument.created_at.desc())
    )
    documents = (await db.execute(documents_stmt)).scalars().unique().all()
    if not documents:
        return []

    jobs_stmt = select(BackgroundJob).where(
        BackgroundJob.job_type == "extract_source_document",
        BackgroundJob.target_entity_type == "source_document",
        BackgroundJob.target_entity_id.in_([document.id for document in documents]),
    ).order_by(BackgroundJob.created_at.desc())
    jobs = (await db.execute(jobs_stmt)).scalars().all()
    latest_jobs = {}
    for processing_job in jobs:
        latest_jobs.setdefault(processing_job.target_entity_id, processing_job)

    health = await JobService.worker_health(db)
    current_sources=[d for d in documents if d.status=="processed" and d.source_type in {"syllabus","question_paper"}]
    checksum=hashlib.sha256("|".join(sorted(f"{d.id}:{d.sha256_checksum}" for d in current_sources)).encode()).hexdigest()
    course_run = await db.scalar(select(AcademicExtractionRun).where(
        AcademicExtractionRun.course_offering_id==course_offering_id,
        AcademicExtractionRun.institution_id==tenant_id,
        AcademicExtractionRun.content_checksum==checksum,
    ).order_by(AcademicExtractionRun.updated_at.desc()).limit(1))
    batches = (await db.execute(select(AcademicExtractionBatch).where(
        AcademicExtractionBatch.run_id==course_run.id,
    ))).scalars().all() if course_run else []
    academic_ids={d.id for d in documents if d.source_type in {"syllabus","question_paper"}}
    active_course_job=next((j for j in jobs if j.target_entity_id in academic_ids and j.status in {"queued","running","retrying"}),None)
    # A course build is shared by its syllabus and question papers. Reconcile both
    # cards without mutating historical failed jobs belonging to either document.
    shared_job=active_course_job or next((j for j in jobs if any(
        r.get("run_id")==str(course_run.id) for r in (
            (j.result_reference_json or {}).get("academic_extraction",{}).get("runs",[]) or
            (j.checkpoint_json or {}).get("academic_extraction",{}).get("runs",[])
        )
    )),None) if course_run else active_course_job
    if shared_job:
        for document in current_sources:
            latest_jobs[document.id]=shared_job
    def academic_fields(document):
        required=document.source_type in {"syllabus","question_paper"}
        status="not_required"
        if required:
            status=active_course_job.status if active_course_job else course_run.status if course_run else "waiting_for_materials"
        return {
            "academic_status":status,
            "academic_summary":{
                "run_id":str(course_run.id),"validated_batches":sum(b.status=="validated" for b in batches),
                "completed_question_batches":sum(b.stage=="analysis_questions" and b.status=="validated" for b in batches),
                "safe_error_summary":course_run.safe_error_summary,"warnings_count":course_run.warnings_count,
            } if required and course_run else None,
            "can_retry_academic":required and document.status=="processed" and not active_course_job and bool(course_run and course_run.status=="failed"),
            "worker_available":health["available"],"worker_last_seen_at":health["last_seen_at"],
        }

    return [TeacherSourceMaterialOut(
        id=str(document.id), institution_id=str(document.institution_id),
        original_filename=document.original_filename, display_filename=document.display_filename,
        mime_type=document.mime_type, file_extension=document.file_extension,
        size_bytes=document.size_bytes, sha256_checksum=document.sha256_checksum,
        source_type=document.source_type, status=document.status,
        publication_status=document.publication_status, visibility=document.visibility,
        review_status=document.review_status, created_at=document.created_at, course_offering_id=str(course_offering_id),
        job_id=str(latest_jobs[document.id].id) if document.id in latest_jobs else None,
        job_status=latest_jobs[document.id].status if document.id in latest_jobs else None,
        job_stage=latest_jobs[document.id].current_stage if document.id in latest_jobs else None,
        job_progress_percent=float(latest_jobs[document.id].progress_percent) if document.id in latest_jobs else None,
        job_error_summary=latest_jobs[document.id].safe_error_summary if document.id in latest_jobs else None,
        **academic_fields(document),
    ) for document in documents]


@router.post("/sources/{document_id}/retry-academic", response_model=AcademicRetryResponse)
async def retry_academic_preparation(
    document_id: uuid.UUID,
    course_offering_id: uuid.UUID,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> AcademicRetryResponse:
    # Reuse the material-library authorization, including active faculty assignment.
    materials=await list_teacher_course_materials(course_offering_id,user,db)
    material=next((m for m in materials if m.id==str(document_id)),None)
    if not material:
        raise AppException(code="DOCUMENT_NOT_FOUND",message="Course material not found.",status_code=404)
    if material.status!="processed" or material.source_type not in {"syllabus","question_paper"}:
        raise AppException(code="ACADEMIC_RETRY_UNAVAILABLE",message="Only extracted syllabus and question papers can resume academic preparation.",status_code=409)
    # Serialize retry submissions. enqueue_job commits while this row is locked.
    await db.execute(select(CourseOffering.id).where(CourseOffering.id==course_offering_id).with_for_update())
    doc_ids=select(SourceDocumentCourseOffering.source_document_id).where(
        SourceDocumentCourseOffering.course_offering_id==course_offering_id,
        SourceDocumentCourseOffering.institution_id==_get_tenant_id(user),
    )
    active=await db.scalar(select(BackgroundJob).where(
        BackgroundJob.job_type=="extract_source_document",
        BackgroundJob.target_entity_id.in_(doc_ids),
        BackgroundJob.status.in_(["queued","running","retrying"]),
    ).order_by(BackgroundJob.created_at.desc()).limit(1))
    if not active:
        if not material.can_retry_academic:
            raise AppException(code="ACADEMIC_RETRY_UNAVAILABLE",message="There is no failed preparation for the current course sources.",status_code=409)
        # Re-read under the lock: another retry may have completed while waiting.
        run=await db.scalar(select(AcademicExtractionRun).where(AcademicExtractionRun.course_offering_id==course_offering_id).order_by(AcademicExtractionRun.updated_at.desc()).limit(1))
        if not run or run.status!="failed":
            raise AppException(code="ACADEMIC_RETRY_UNAVAILABLE",message="There is no failed academic preparation to retry.",status_code=409)
        previous=await db.scalar(select(BackgroundJob).where(BackgroundJob.target_entity_id==document_id,BackgroundJob.job_type=="extract_source_document").order_by(BackgroundJob.created_at.desc()).limit(1))
        active=await JobService.enqueue_job(db,"extract_source_document","source_document",document_id,
            institution_id=_get_tenant_id(user),requested_by_user_id=uuid.UUID(user.id),scope_course_offering_id=course_offering_id,
            input_reference_json={"academic_only":True,"previous_job_id":str(previous.id) if previous else None,"previous_run_id":str(run.id)})
        already_active=False
    else:
        already_active=True
    health=await JobService.worker_health(db)
    return AcademicRetryResponse(job_id=str(active.id),status=active.status,already_active=already_active,
        worker_available=health["available"],message="Academic preparation is queued or active. Existing source chunks and compatible validated batches will be reused." if health["available"] else "Academic preparation is queued or active, but no recent worker heartbeat is available. Start the ingestion worker to process queued work.")


@router.get("/courses/{course_offering_id}/sources/processing-health")
async def course_processing_health(
    course_offering_id: uuid.UUID,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    materials=await list_teacher_course_materials(course_offering_id,user,db)
    ids=[uuid.UUID(m.id) for m in materials]
    jobs=(await db.execute(select(BackgroundJob).where(
        BackgroundJob.institution_id==_get_tenant_id(user),
        BackgroundJob.job_type=="extract_source_document",
        BackgroundJob.target_entity_id.in_(ids),
    ))).scalars().all() if ids else []
    pending=[j for j in jobs if j.status in {"queued","retrying"}]
    def utc(value):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    oldest=min((utc(j.created_at) for j in pending),default=None)
    last_success=max((utc(j.completed_at) for j in jobs if j.status=="succeeded" and j.completed_at),default=None)
    return {"worker":await JobService.worker_health(db),"jobs_by_status":dict(Counter(j.status for j in jobs)),
        "oldest_pending_age_seconds":max(0,(datetime.now(timezone.utc)-oldest).total_seconds()) if oldest else None,
        "last_success_at":last_success,
        "additional_attempts":sum(max(0,j.attempt_count-1) for j in jobs),
        "failed_jobs_by_error":dict(Counter(j.error_code or "UNKNOWN" for j in jobs if j.status=="failed")),
        "failed_jobs_by_stage":dict(Counter(j.current_stage for j in jobs if j.status=="failed"))}

@router.post("/sources/upload", response_model=DocumentUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    source_type: str = Form(default="syllabus"),
    visibility: str = Form(default="course"),
    course_offering_id: Optional[str] = Form(None),
    curriculum_version_id: Optional[str] = Form(None),
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> DocumentUploadResponse:
    """
    Upload source syllabus, lecture notes, slides, or question paper.
    Enforces that teachers are assigned to the target course offering.
    Saves file bytes with an opaque key and enqueues a background processing job.
    """
    # Read at most one byte beyond the configured limit to avoid unbounded memory use.
    file_bytes = await file.read(settings.MAX_UPLOAD_SIZE_BYTES + 1)
    await file.close()
    offering_uuid = uuid.UUID(course_offering_id) if course_offering_id else None
    curriculum_uuid = uuid.UUID(curriculum_version_id) if curriculum_version_id else None

    doc, job_id, already_uploaded = await SourceService.upload_source_document(
        db=db,
        institution_id=_get_tenant_id(user),
        user_id=uuid.UUID(user.id),
        user_role=user.role,
        file_bytes=file_bytes,
        original_filename=file.filename or "uploaded_document",
        source_type=source_type,
        visibility=visibility,
        course_offering_id=offering_uuid,
        curriculum_version_id=curriculum_uuid,
    )

    return DocumentUploadResponse(
        document=SourceDocumentOut(
            id=str(doc.id),
            institution_id=str(doc.institution_id),
            original_filename=doc.original_filename,
            display_filename=doc.display_filename,
            mime_type=doc.mime_type,
            file_extension=doc.file_extension,
            size_bytes=doc.size_bytes,
            sha256_checksum=doc.sha256_checksum,
            source_type=doc.source_type,
            status=doc.status,
            publication_status=doc.publication_status,
            review_status=doc.review_status,
            visibility=doc.visibility,
            created_at=doc.created_at,
        ),
        job_id=str(job_id) if job_id else None,
        already_uploaded=already_uploaded,
        message=(
            f"This file was already uploaded as {doc.source_type}; the stored copy was reused."
            if already_uploaded
            else "Document uploaded successfully. Processing job queued."
        ),
    )


@router.get("/sources/{document_id}", response_model=SourceDocumentOut)
async def get_document(
    document_id: str,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SourceDocumentOut:
    doc = await SourceService.get_document(
        db=db,
        document_id=uuid.UUID(document_id),
        user_id=uuid.UUID(user.id),
        user_role=user.role,
        institution_id=user.institution_id,
    )
    return SourceDocumentOut(
        id=str(doc.id),
        institution_id=str(doc.institution_id),
        original_filename=doc.original_filename,
        display_filename=doc.display_filename,
        mime_type=doc.mime_type,
        file_extension=doc.file_extension,
        size_bytes=doc.size_bytes,
        sha256_checksum=doc.sha256_checksum,
        source_type=doc.source_type,
        status=doc.status,
        publication_status=doc.publication_status,
        review_status=doc.review_status,
        visibility=doc.visibility,
        created_at=doc.created_at,
    )


@router.post("/sources/{document_id}/review", response_model=SourceDocumentOut)
async def review_source_document(
    document_id: str,
    req: SourceDocumentReviewRequest,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> SourceDocumentOut:
    """Approve material for student publication or reject it after extraction review."""
    doc = await SourceService.set_publication_status(
        db=db,
        document_id=uuid.UUID(document_id),
        user_id=uuid.UUID(user.id),
        institution_id=str(_get_tenant_id(user)),
        publication_status=req.publication_status,
        review_status=req.review_status,
    )
    return SourceDocumentOut(
        id=str(doc.id),
        institution_id=str(doc.institution_id),
        original_filename=doc.original_filename,
        display_filename=doc.display_filename,
        mime_type=doc.mime_type,
        file_extension=doc.file_extension,
        size_bytes=doc.size_bytes,
        sha256_checksum=doc.sha256_checksum,
        source_type=doc.source_type,
        status=doc.status,
        publication_status=doc.publication_status,
        review_status=doc.review_status,
        visibility=doc.visibility,
        created_at=doc.created_at,
    )


@router.get("/sources/{document_id}/extractions", response_model=List[SourceExtractionOut])
async def get_document_extractions(
    document_id: str,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[SourceExtractionOut]:
    # Check access to document first
    await SourceService.get_document(
        db=db,
        document_id=uuid.UUID(document_id),
        user_id=uuid.UUID(user.id),
        user_role=user.role,
        institution_id=user.institution_id,
    )
    extractions = await SourceService.get_extractions(db, uuid.UUID(document_id))
    return [
        SourceExtractionOut(
            id=str(e.id),
            source_document_id=str(e.source_document_id),
            extractor_name=e.extractor_name,
            extractor_version=e.extractor_version,
            status=e.status,
            warnings_json=e.warnings_json,
            error_code=e.error_code,
            safe_error_summary=e.safe_error_summary,
            raw_text_checksum=e.raw_text_checksum,
            created_at=e.created_at,
            chunks=[
                SourceChunkOut(
                    id=str(c.id),
                    chunk_index=c.chunk_index,
                    page_number=c.page_number,
                    slide_number=c.slide_number,
                    section_path=c.section_path,
                    chunk_type=c.chunk_type,
                    content_text=c.content_text,
                    content_hash=c.content_hash,
                    metadata_json=c.metadata_json,
                )
                for c in e.chunks
            ],
        )
        for e in extractions
    ]


@router.get("/sources/{document_id}/download")
async def download_document(
    document_id: str,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    file_bytes, mime_type, filename = await SourceService.download_file(
        db=db,
        document_id=uuid.UUID(document_id),
        user_id=uuid.UUID(user.id),
        user_role=user.role,
        institution_id=user.institution_id,
    )
    fallback_filename = "".join(
        character if 32 <= ord(character) < 127 and character not in {'"', "\\"} else "_"
        for character in filename
    )
    return Response(
        content=file_bytes,
        media_type=mime_type,
        headers={
            "Content-Disposition": (
                f'attachment; filename="{fallback_filename}"; '
                f"filename*=UTF-8''{quote(filename, safe='')}"
            )
        },
    )


# ------------------------------------------------------------------------------
# Background Processing Jobs Inspection
# ------------------------------------------------------------------------------

@router.get("/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    job_id: str,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobStatusResponse:
    job = await JobService.get_job_status(db, uuid.UUID(job_id))
    if not job:
        raise AppException(code="JOB_NOT_FOUND", message="Background job record not found.", status_code=404)

    # Multi-tenant isolation check
    if user.role != "SUPER_ADMIN":
        if job.institution_id and user.institution_id and str(job.institution_id) != user.institution_id:
            raise AppException(code="FORBIDDEN_JOB", message="Access forbidden: Job belongs to another institution.", status_code=403)
        if job.job_type == "extract_source_document" and job.target_entity_id:
            await SourceService.get_document(
                db=db,
                document_id=job.target_entity_id,
                user_id=uuid.UUID(user.id),
                user_role=user.role,
                institution_id=user.institution_id,
            )

    return JobStatusResponse(
        id=str(job.id),
        job_type=job.job_type,
        target_entity_type=job.target_entity_type,
        target_entity_id=str(job.target_entity_id) if job.target_entity_id else None,
        status=job.status,
        current_stage=job.current_stage,
        progress_percent=float(job.progress_percent),
        attempt_count=job.attempt_count,
        max_attempts=job.max_attempts,
        error_code=job.error_code,
        safe_error_summary=job.safe_error_summary,
        result_reference_json=job.result_reference_json,
        created_at=job.created_at,
        completed_at=job.completed_at,
        events=[
            JobEventOut(
                id=str(ev.id),
                event_type=ev.event_type,
                stage_name=ev.stage_name,
                progress_percent=float(ev.progress_percent) if ev.progress_percent is not None else None,
                message_safe=ev.message_safe,
                details_json=ev.details_json,
                created_at=ev.created_at,
            )
            for ev in job.events
        ] if job.events else [],
    )


@router.get("/courses/{offering_id}/sources/rag-search", response_model=List[RagSearchResultOut])
async def search_course_materials_rag(
    offering_id: uuid.UUID,
    query: str = Query(..., min_length=2, description="Search query or doubt question"),
    limit: int = Query(3, ge=1, le=10),
    min_score: float = Query(0.65, ge=0.0, le=1.0, description="Minimum similarity score threshold"),
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[RagSearchResultOut]:
    """Semantic RAG search over course lecture slides, notes, and syllabus chunks."""
    from app.modules.sources.embeddings import find_top_k_chunks
    top_chunks = await find_top_k_chunks(db=db, course_offering_id=offering_id, query=query, top_k=limit, min_score=min_score)
    results: List[RagSearchResultOut] = []
    for chunk, score, citation in top_chunks:
        doc = chunk.document
        results.append(
            RagSearchResultOut(
                chunk_id=str(chunk.id),
                document_id=str(chunk.source_document_id),
                document_title=doc.display_filename if doc else "Course Document",
                source_type=doc.source_type if doc else "notes",
                page_number=chunk.page_number,
                slide_number=chunk.slide_number,
                section_path=chunk.section_path,
                content_text=chunk.content_text,
                citation=citation,
                score=round(score, 4),
            )
        )
    return results

