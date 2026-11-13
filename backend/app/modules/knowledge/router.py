import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from app.database import get_db
from app.common.exceptions import AppException
from app.modules.rbac.dependencies import (
    get_current_user,
    require_teacher,
    require_student,
)
from app.modules.auth.schemas import UserProfile
from app.modules.knowledge.models import Concept, ConceptVersion, CourseContentConcept, CourseContentVersion, SyllabusNode
from app.modules.learning.models import LearningNode
from app.modules.questions.models import QuestionCoverageEvent, QuestionVersion
from app.modules.sources.academic_models import AcademicExtractionRun, AcademicExtractionBatch
from app.modules.sources.models import SourceDocument, SourceDocumentCourseOffering
from app.modules.jobs.models import BackgroundJob
from app.modules.jobs.service import JobService
from app.modules.knowledge.schemas import (
    CourseContentVersionOut,
    CourseContentVersionCreate,
    PublishContentVersionRequest,
    SyllabusNodeCreate,
    SyllabusNodeUpdate,
    SyllabusNodeOut,
    ConceptCreate,
    ConceptVersionCreate,
    ConceptOut,
    ConceptVersionOut,
    CourseContentConceptBindRequest,
    CourseContentConceptOut,
    LearningObjectiveCreate,
    LearningObjectiveOut,
    SyllabusTreeResponse,
)
from app.modules.knowledge.service import KnowledgeService

router = APIRouter(tags=["Knowledge & Syllabus"])


@router.post("/courses/{offering_id}/academic-review/process")
async def start_academic_extraction(offering_id: uuid.UUID, user: UserProfile = Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    """Queue academic analysis for already processed course documents without re-uploading them."""
    tenant_id=_get_tenant_id(user);user_id=uuid.UUID(user.id)
    await KnowledgeService.verify_teacher_access(db,offering_id,tenant_id,user_id,user.role in ["ADMIN","SUPER_ADMIN"])
    if db.bind and db.bind.dialect.name=="postgresql":
        await db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"),{"key":f"academic-extraction:{offering_id}"})
    docs=(await db.execute(select(SourceDocument).join(SourceDocumentCourseOffering,SourceDocumentCourseOffering.source_document_id==SourceDocument.id).where(SourceDocument.institution_id==tenant_id,SourceDocumentCourseOffering.institution_id==tenant_id,SourceDocumentCourseOffering.course_offering_id==offering_id,SourceDocument.status=="processed",SourceDocument.source_type.in_(["syllabus","question_paper"])).order_by(SourceDocument.created_at.desc()))).scalars().unique().all()
    by_type={}
    for doc in docs:by_type.setdefault(doc.source_type,doc)
    missing=[source_type for source_type in ("syllabus","question_paper") if source_type not in by_type]
    if missing:raise AppException(status_code=409,code="ACADEMIC_SOURCES_MISSING",message="Process both a syllabus and a question paper for this course before starting academic extraction.",details={"missing_source_types":missing})
    document_ids=[doc.id for doc in by_type.values()]
    active=(await db.execute(select(BackgroundJob).where(BackgroundJob.job_type=="extract_source_document",BackgroundJob.target_entity_type=="source_document",BackgroundJob.target_entity_id.in_(document_ids),BackgroundJob.scope_course_offering_id==offering_id,BackgroundJob.status.in_(["queued","running","retrying"])).order_by(BackgroundJob.created_at.desc()).limit(1))).scalars().first()
    if active:return {"job_id":str(active.id),"status":active.status,"already_queued":True}
    source=by_type["syllabus"]
    job=await JobService.enqueue_job(db=db,job_type="extract_source_document",target_entity_type="source_document",target_entity_id=source.id,input_reference_json={"source_document_id":str(source.id),"resume_academic_extraction":True},institution_id=tenant_id,requested_by_user_id=user_id,scope_course_offering_id=offering_id)
    return {"job_id":str(job.id),"status":job.status,"already_queued":False}


@router.get("/courses/{offering_id}/academic-review/summary")
async def academic_review_summary(offering_id: uuid.UUID, user: UserProfile = Depends(require_teacher), db: AsyncSession = Depends(get_db)):
    """Compact teacher summary; only flagged items are returned for inspection."""
    tenant_id=_get_tenant_id(user)
    await KnowledgeService.verify_teacher_access(db,offering_id,tenant_id,uuid.UUID(user.id),user.role in ["ADMIN","SUPER_ADMIN"])
    version=(await db.execute(select(CourseContentVersion).where(CourseContentVersion.course_offering_id==offering_id,CourseContentVersion.institution_id==tenant_id,CourseContentVersion.status.in_(["draft","in_review"])).order_by(CourseContentVersion.version_number.desc()).limit(1))).scalars().first()
    run=(await db.execute(select(AcademicExtractionRun).where(AcademicExtractionRun.course_offering_id==offering_id).order_by(AcademicExtractionRun.created_at.desc()).limit(1))).scalars().first()
    processed_source_types=set((await db.execute(select(SourceDocument.source_type).join(SourceDocumentCourseOffering,SourceDocumentCourseOffering.source_document_id==SourceDocument.id).where(SourceDocument.institution_id==tenant_id,SourceDocumentCourseOffering.course_offering_id==offering_id,SourceDocument.status=="processed",SourceDocument.source_type.in_(["syllabus","question_paper"])).distinct())).scalars().all())
    sources_ready={"syllabus","question_paper"}.issubset(processed_source_types)
    active_job=(await db.execute(select(BackgroundJob).where(BackgroundJob.scope_course_offering_id==offering_id,BackgroundJob.job_type=="extract_source_document",BackgroundJob.status.in_(["queued","running","retrying"])).order_by(BackgroundJob.created_at.desc()).limit(1))).scalars().first()
    batches=[]
    failed_groupings=0
    if run:
        batches=(await db.execute(select(AcademicExtractionBatch).where(AcademicExtractionBatch.run_id==run.id,AcademicExtractionBatch.status=="flagged_for_review").order_by(AcademicExtractionBatch.created_at))).scalars().all()
        failed_groupings=sum(batch.stage=="grouping" for batch in batches)
    flagged=[]
    for batch in batches:
        payload=batch.response_json or {};items=[]
        for item in payload.get("items",[]):
            items.append({"kind":item.get("kind","item"),"label":item.get("label",item.get("title",item.get("original_number","Needs review"))),"confidence":item.get("confidence"),"source_chunk_ids":item.get("source_chunk_ids",[])})
        for module in payload.get("modules",[]):
            items.append({"kind":"syllabus","label":module.get("title","Syllabus section"),"source_chunk_ids":[e.get("chunk_id") for e in module.get("evidence",[]) if e.get("chunk_id")]})
        for question in payload.get("questions",[]):
            items.append({"kind":"question","label":f"Question {question.get('original_number','')}: {str(question.get('text',''))[:180]}","source_question_id":question.get("source_question_id")})
        flagged.append({"id":str(batch.id),"stage":batch.stage,"warning_code":batch.warning_code,"message":batch.warning_message,"items":items,"item_count":len(items),"source_chunk_count":len(batch.source_chunk_ids)})
    version_id=version.id if version else None
    node_count=topic_count=concept_count=approved_concepts_count=approved_syllabus_count=question_count=draft_node_count=roadmap_nodes_count=0
    if version_id:
        node_count=(await db.execute(select(func.count()).select_from(SyllabusNode).where(SyllabusNode.course_content_version_id==version_id,SyllabusNode.node_type=="module"))).scalar() or 0
        topic_count=(await db.execute(select(func.count()).select_from(SyllabusNode).where(SyllabusNode.course_content_version_id==version_id,SyllabusNode.node_type.in_(["topic","subtopic"])))).scalar() or 0
        approved_syllabus_count=(await db.execute(select(func.count()).select_from(SyllabusNode).where(SyllabusNode.course_content_version_id==version_id,SyllabusNode.review_status=="approved"))).scalar() or 0
        roadmap_nodes_count=(await db.execute(select(func.count()).select_from(LearningNode).where(LearningNode.course_content_version_id==version_id))).scalar() or 0
        concept_count=(await db.execute(select(func.count()).select_from(CourseContentConcept).where(CourseContentConcept.course_content_version_id==version_id))).scalar() or 0
        approved_concepts_count=(await db.execute(select(func.count()).select_from(CourseContentConcept).join(ConceptVersion,ConceptVersion.concept_id==CourseContentConcept.concept_id).where(CourseContentConcept.course_content_version_id==version_id,ConceptVersion.review_status=="teacher_approved"))).scalar() or 0
        draft_node_count=(await db.execute(select(func.count()).select_from(LearningNode).where(LearningNode.course_content_version_id==version_id,LearningNode.status=="draft"))).scalar() or 0
        concept_rows=(await db.execute(select(Concept,ConceptVersion).join(CourseContentConcept,CourseContentConcept.concept_id==Concept.id).join(ConceptVersion,ConceptVersion.concept_id==Concept.id).where(CourseContentConcept.course_content_version_id==version_id,ConceptVersion.review_status=="teacher_approved"))).all()
    else:concept_rows=[]
    coverage=(await db.execute(select(QuestionCoverageEvent.question_version_id).where(QuestionCoverageEvent.course_offering_id==offering_id,QuestionCoverageEvent.event_type=="extracted",QuestionCoverageEvent.question_version_id.is_not(None)).distinct())).scalars().all()
    question_count=len(coverage)
    approved_concepts=[];seen=set()
    for concept,cv in concept_rows:
        if concept.id in seen:continue
        latest=(await db.execute(select(ConceptVersion).where(ConceptVersion.concept_id==concept.id).order_by(ConceptVersion.version_number.desc()).limit(1))).scalars().first()
        if latest and latest.review_status=="teacher_approved":approved_concepts.append({"id":str(concept.id),"canonical_name":concept.canonical_name});seen.add(concept.id)
    # Count the same latest-version-approved concepts shown in the dropdown;
    # joining every historical version otherwise inflates this number.
    approved_concepts_count=len(approved_concepts)
    no_roadmap_after_run=bool(run and run.status=="succeeded" and version_id and roadmap_nodes_count==0)
    generation_status=active_job.status if active_job else ("failed" if failed_groupings or no_roadmap_after_run else (run.status if run else ("ready" if sources_ready else "waiting_for_documents")))
    generation_stage=active_job.current_stage if active_job else ("building_learning_roadmap" if run and run.status=="running" else None)
    grouping_warning=next((batch.warning_message for batch in batches if batch.stage=="grouping"),None)
    generation_message=active_job.safe_error_summary if active_job else (grouping_warning if failed_groupings else ("The extraction completed without saving any roadmap nodes. Retry generation after reviewing the source content." if no_roadmap_after_run else (run.safe_error_summary if run and run.status=="failed" else None)))
    publish_ready=approved_syllabus_count>0 and generation_status not in {"queued","running","retrying","failed"}
    return {"course_content_version_id":str(version_id) if version_id else None,"run_status":run.status if run else "waiting_for_documents","generation_status":generation_status,"generation_stage":generation_stage,"generation_message":generation_message,"sources_ready":sources_ready,"publish_ready":publish_ready,"approved_syllabus_count":approved_syllabus_count,"has_warnings":bool(run.has_warnings) if run else False,"warnings_count":run.warnings_count if run else 0,"modules_count":node_count,"topics_count":topic_count,"concepts_count":concept_count,"approved_concepts_count":approved_concepts_count,"questions_count":question_count,"draft_nodes_count":draft_node_count,"flagged_items":flagged,"approved_concepts":approved_concepts}


@router.post("/courses/{offering_id}/academic-review/publish-all")
async def publish_academic_content(offering_id: uuid.UUID,user: UserProfile=Depends(require_teacher),db:AsyncSession=Depends(get_db)):
    """Publish all accepted course structures/nodes atomically; flagged items remain hidden."""
    tenant_id=_get_tenant_id(user);user_id=uuid.UUID(user.id)
    await KnowledgeService.verify_teacher_access(db,offering_id,tenant_id,user_id,user.role in ["ADMIN","SUPER_ADMIN"])
    
    # Self-healing: Mark any stale extraction runs (>15m old or older than latest succeeded run) as failed
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=15)
    stale_runs = (await db.execute(
        select(AcademicExtractionRun).where(
            AcademicExtractionRun.course_offering_id == offering_id,
            AcademicExtractionRun.status == "running",
            AcademicExtractionRun.created_at < cutoff
        )
    )).scalars().all()
    for sr in stale_runs:
        sr.status = "failed"
        sr.safe_error_summary = "Timed out or superseded by newer extraction"
    if stale_runs:
        await db.commit()

    active_job=await db.scalar(select(BackgroundJob.id).where(BackgroundJob.scope_course_offering_id==offering_id,BackgroundJob.job_type=="extract_source_document",BackgroundJob.status.in_(["queued","running","retrying"])).limit(1))
    active_run=await db.scalar(select(AcademicExtractionRun.id).where(AcademicExtractionRun.course_offering_id==offering_id,AcademicExtractionRun.status=="running").limit(1))
    if active_job or active_run:raise AppException(status_code=409,code="ROADMAP_GENERATION_IN_PROGRESS",message="Wait until roadmap generation finishes before publishing the course content.")
    latest_run=(await db.execute(select(AcademicExtractionRun).where(AcademicExtractionRun.course_offering_id==offering_id).order_by(AcademicExtractionRun.created_at.desc()).limit(1))).scalars().first()
    if latest_run and await db.scalar(select(AcademicExtractionBatch.id).where(AcademicExtractionBatch.run_id==latest_run.id,AcademicExtractionBatch.stage=="grouping",AcademicExtractionBatch.status=="flagged_for_review").limit(1)):
        raise AppException(status_code=409,code="ROADMAP_GENERATION_INCOMPLETE",message="Resolve or retry the flagged roadmap generation before publishing the course content.")
    version=(await db.execute(select(CourseContentVersion).where(CourseContentVersion.course_offering_id==offering_id,CourseContentVersion.institution_id==tenant_id,CourseContentVersion.status.in_(["draft","in_review"])).order_by(CourseContentVersion.version_number.desc()).limit(1))).scalars().first()
    if not version:
        # If no draft version, check if already published
        published_version=(await db.execute(select(CourseContentVersion).where(CourseContentVersion.course_offering_id==offering_id,CourseContentVersion.institution_id==tenant_id,CourseContentVersion.status=="published").order_by(CourseContentVersion.version_number.desc()).limit(1))).scalars().first()
        if published_version:
            # Also publish any lingering draft learning nodes
            nodes=(await db.execute(select(LearningNode).where(LearningNode.course_offering_id==offering_id,LearningNode.status=="draft").with_for_update())).scalars().all()
            now=datetime.now(timezone.utc)
            for node in nodes:
                node.status="published"
                node.published_at=now
            await db.commit()
            return {"course_content_version_id":str(published_version.id),"published_nodes":len(nodes),"status":"published"}
        raise AppException(status_code=409,code="NO_DRAFT_CONTENT",message="There is no draft course content to publish.")
    accepted=(await db.execute(select(func.count()).select_from(SyllabusNode).where(SyllabusNode.course_content_version_id==version.id,SyllabusNode.review_status=="approved"))).scalar() or 0
    if not accepted:raise AppException(status_code=409,code="NO_APPROVED_CONTENT",message="No validated syllabus content is ready to publish.")
    now=datetime.now(timezone.utc)
    previous=(await db.execute(select(CourseContentVersion).where(CourseContentVersion.course_offering_id==offering_id,CourseContentVersion.institution_id==tenant_id,CourseContentVersion.status=="published").with_for_update())).scalars().all()
    for old in previous:old.status="superseded";old.updated_at=now
    version.status="published";version.reviewed_by_user_id=user_id;version.approved_at=now;version.published_at=now;version.updated_at=now
    nodes=(await db.execute(select(LearningNode).where(LearningNode.course_content_version_id==version.id,LearningNode.status=="draft").with_for_update())).scalars().all()
    for node in nodes:node.status="published";node.published_at=now
    await db.commit()
    return {"course_content_version_id":str(version.id),"published_nodes":len(nodes),"status":"published"}


def _get_tenant_id(user: UserProfile) -> uuid.UUID:
    if not user.institution_id:
        raise AppException(code="NO_TENANT_CONTEXT", message="Institution context required.", status_code=400)
    return uuid.UUID(user.institution_id)


# ------------------------------------------------------------------------------
# Teacher Syllabus & Content Versions
# ------------------------------------------------------------------------------

@router.get("/courses/{offering_id}/syllabus", response_model=SyllabusTreeResponse)
async def get_teacher_syllabus(
    offering_id: uuid.UUID,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> SyllabusTreeResponse:
    """
    Teacher course syllabus endpoint.
    Returns draft or published content version with review statuses and provenance links.
    """
    tenant_id = _get_tenant_id(user)
    is_admin = user.role in ["ADMIN", "SUPER_ADMIN"]
    return await KnowledgeService.resolve_teacher_syllabus(
        db=db,
        offering_id=offering_id,
        tenant_id=tenant_id,
        user_id=uuid.UUID(user.id),
        is_admin=is_admin,
    )


@router.post("/courses/{offering_id}/versions/draft", response_model=CourseContentVersionOut, status_code=status.HTTP_201_CREATED)
async def get_or_create_draft_version(
    offering_id: uuid.UUID,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> CourseContentVersionOut:
    """
    Creates or retrieves the current working draft version for a course offering.
    Clones nodes and concept bindings from prior published version if available.
    """
    tenant_id = _get_tenant_id(user)
    is_admin = user.role in ["ADMIN", "SUPER_ADMIN"]
    await KnowledgeService.verify_teacher_access(
        db=db, offering_id=offering_id, tenant_id=tenant_id, user_id=uuid.UUID(user.id), is_admin=is_admin
    )
    version = await KnowledgeService.get_or_create_draft_version(
        db=db,
        offering_id=offering_id,
        tenant_id=tenant_id,
        user_id=uuid.UUID(user.id),
    )
    return CourseContentVersionOut.model_validate(version)


@router.post("/content-versions/{version_id}/publish", response_model=CourseContentVersionOut)
async def publish_content_version(
    version_id: uuid.UUID,
    req: PublishContentVersionRequest,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> CourseContentVersionOut:
    """
    Publishes a content version.
    Validates non-empty syllabus, supersedes any previously published version,
    and sets published_at timestamp.
    """
    tenant_id = _get_tenant_id(user)
    version = await KnowledgeService.publish_content_version(
        db=db,
        version_id=version_id,
        tenant_id=tenant_id,
        user_id=uuid.UUID(user.id),
        change_summary=req.change_summary,
    )
    return CourseContentVersionOut.model_validate(version)


# ------------------------------------------------------------------------------
# Syllabus Node Management
# ------------------------------------------------------------------------------

@router.post("/content-versions/{version_id}/nodes", response_model=SyllabusNodeOut, status_code=status.HTTP_201_CREATED)
async def create_syllabus_node(
    version_id: uuid.UUID,
    req: SyllabusNodeCreate,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> SyllabusNodeOut:
    """Create a new module, topic, or subtopic node within a draft content version."""
    tenant_id = _get_tenant_id(user)
    node = await KnowledgeService.create_syllabus_node(
        db=db,
        version_id=version_id,
        tenant_id=tenant_id,
        data=req,
    )
    return SyllabusNodeOut.model_validate(node)


@router.patch("/syllabus-nodes/{node_id}", response_model=SyllabusNodeOut)
async def update_syllabus_node(
    node_id: uuid.UUID,
    req: SyllabusNodeUpdate,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> SyllabusNodeOut:
    """Update title, description, sequence, or review status of a syllabus node."""
    tenant_id = _get_tenant_id(user)
    node = await KnowledgeService.update_syllabus_node(
        db=db,
        node_id=node_id,
        tenant_id=tenant_id,
        data=req,
    )
    return SyllabusNodeOut.model_validate(node)


@router.post("/syllabus-nodes/{node_id}/approve", response_model=SyllabusNodeOut)
async def approve_syllabus_node(
    node_id: uuid.UUID,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> SyllabusNodeOut:
    """Teacher approval of an AI-extracted or provisional syllabus node."""
    tenant_id = _get_tenant_id(user)
    node = await KnowledgeService.approve_syllabus_node(
        db=db,
        node_id=node_id,
        tenant_id=tenant_id,
        user_id=uuid.UUID(user.id),
    )
    return SyllabusNodeOut.model_validate(node)


@router.delete("/syllabus-nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_syllabus_node(
    node_id: uuid.UUID,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a syllabus node and its subtree from a draft content version."""
    tenant_id = _get_tenant_id(user)
    await KnowledgeService.delete_syllabus_node(
        db=db,
        node_id=node_id,
        tenant_id=tenant_id,
    )


# ------------------------------------------------------------------------------
# Concept Bindings & Learning Objectives
# ------------------------------------------------------------------------------

@router.post("/content-versions/{version_id}/concepts", response_model=CourseContentConceptOut, status_code=status.HTTP_201_CREATED)
async def bind_concept_to_content(
    version_id: uuid.UUID,
    req: CourseContentConceptBindRequest,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> CourseContentConceptOut:
    """Bind an institutional concept to a course content version with an optional primary syllabus node."""
    tenant_id = _get_tenant_id(user)
    binding = await KnowledgeService.bind_concept_to_content(
        db=db,
        version_id=version_id,
        tenant_id=tenant_id,
        data=req,
    )
    return CourseContentConceptOut.model_validate(binding)


@router.post("/content-versions/{version_id}/learning-objectives", response_model=LearningObjectiveOut, status_code=status.HTTP_201_CREATED)
async def create_learning_objective(
    version_id: uuid.UUID,
    req: LearningObjectiveCreate,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> LearningObjectiveOut:
    """Define a course outcome / learning objective mapped to Bloom's taxonomy."""
    tenant_id = _get_tenant_id(user)
    lo = await KnowledgeService.create_learning_objective(
        db=db,
        version_id=version_id,
        tenant_id=tenant_id,
        data=req,
    )
    return LearningObjectiveOut.model_validate(lo)


# ------------------------------------------------------------------------------
# Student Syllabus Resolution
# ------------------------------------------------------------------------------

@router.get("/courses/{offering_id}/student/syllabus", response_model=SyllabusTreeResponse)
async def get_student_syllabus(
    offering_id: uuid.UUID,
    user: UserProfile = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> SyllabusTreeResponse:
    """
    Student course syllabus endpoint.
    Resolves ONLY the currently published content version.
    Returns 404 SYLLABUS_NOT_PUBLISHED if the course offering has no published version.
    """
    tenant_id = _get_tenant_id(user)
    return await KnowledgeService.resolve_student_syllabus(
        db=db,
        offering_id=offering_id,
        tenant_id=tenant_id,
        user_id=uuid.UUID(user.id),
    )


# ------------------------------------------------------------------------------
# Concept Registry
# ------------------------------------------------------------------------------

@router.post("/concepts", response_model=ConceptOut, status_code=status.HTTP_201_CREATED)
async def create_concept(
    req: ConceptCreate,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> ConceptOut:
    """Create an institutional concept and initial versioned definition."""
    tenant_id = _get_tenant_id(user)
    concept = await KnowledgeService.create_concept(
        db=db,
        tenant_id=tenant_id,
        data=req,
        user_id=uuid.UUID(user.id),
    )
    # Fetch latest version
    v_stmt = (
        select(ConceptVersion)
        .where(ConceptVersion.concept_id == concept.id)
        .order_by(ConceptVersion.version_number.desc())
        .limit(1)
    )
    v_res = await db.execute(v_stmt)
    latest_v = v_res.scalars().first()

    return ConceptOut(
        id=concept.id,
        institution_id=concept.institution_id,
        concept_code=concept.concept_code,
        canonical_name=concept.canonical_name,
        status=concept.status,
        created_at=concept.created_at,
        updated_at=concept.updated_at,
        latest_version=ConceptVersionOut.model_validate(latest_v) if latest_v else None,
    )


@router.post("/concepts/{concept_id}/versions", response_model=ConceptVersionOut, status_code=status.HTTP_201_CREATED)
async def create_concept_version(
    concept_id: uuid.UUID,
    req: ConceptVersionCreate,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> ConceptVersionOut:
    """Add a new versioned definition and explanation to an existing concept."""
    tenant_id = _get_tenant_id(user)
    v = await KnowledgeService.create_concept_version(
        db=db,
        concept_id=concept_id,
        tenant_id=tenant_id,
        data=req,
        user_id=uuid.UUID(user.id),
    )
    return ConceptVersionOut.model_validate(v)


@router.get("/concepts", response_model=List[ConceptOut])
async def list_concepts(
    query: Optional[str] = Query(None),
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ConceptOut]:
    """List concepts in the institution."""
    tenant_id = _get_tenant_id(user)
    stmt = select(Concept).where(Concept.institution_id == tenant_id)
    if query:
        stmt = stmt.where(Concept.canonical_name.ilike(f"%{query}%"))
    stmt = stmt.order_by(Concept.canonical_name)

    concepts = (await db.execute(stmt)).scalars().all()
    results: List[ConceptOut] = []
    for c in concepts:
        v_stmt = (
            select(ConceptVersion)
            .where(ConceptVersion.concept_id == c.id)
            .order_by(ConceptVersion.version_number.desc())
            .limit(1)
        )
        latest_v = (await db.execute(v_stmt)).scalars().first()
        results.append(
            ConceptOut(
                id=c.id,
                institution_id=c.institution_id,
                concept_code=c.concept_code,
                canonical_name=c.canonical_name,
                status=c.status,
                created_at=c.created_at,
                updated_at=c.updated_at,
                latest_version=ConceptVersionOut.model_validate(latest_v) if latest_v else None,
            )
        )
    return results

