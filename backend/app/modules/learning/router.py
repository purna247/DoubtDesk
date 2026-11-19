import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.common.exceptions import AppException
from app.modules.rbac.dependencies import (
    require_teacher,
    require_student,
    get_current_user,
)
from app.modules.auth.schemas import UserProfile
from app.modules.learning.models import LearningNode, Activity, ActivityVersion
from app.modules.learning.schemas import (
    LearningNodeCreate,
    LearningNodeUpdate,
    LearningNodeOut,
    LearningNodePrerequisiteCreate,
    LearningNodePrerequisiteOut,
    ActivityCreate,
    ActivityOut,
    ActivityVersionOut,
    ActivityEvaluateRequest,
    CourseLearningMapResponse,
    PracticeSessionStartOut,
    PracticeHintOut,
    PracticeAnswerRequest,
    PracticeAnswerResultOut,
    StudentProgressSummaryResponse,
)
from app.modules.learning.scoring import ActivityEvaluationResult
from app.modules.learning.service import LearningService
from app.modules.learning.practice_service import AdaptivePracticeService, _ensure_node_practice_bank
from app.modules.knowledge.service import KnowledgeService

router = APIRouter(tags=["Learning Nodes & Structured Activities"])


def _get_tenant_id(user: UserProfile) -> uuid.UUID:
    if not user.institution_id:
        raise AppException(code="NO_TENANT_CONTEXT", message="Institution context required.", status_code=400)
    return uuid.UUID(user.institution_id)


# ------------------------------------------------------------------------------
# Teacher Learning Node & Prerequisite Authoring
# ------------------------------------------------------------------------------

@router.post("/courses/{offering_id}/learning-nodes", response_model=LearningNodeOut, status_code=status.HTTP_201_CREATED)
async def create_learning_node(
    offering_id: uuid.UUID,
    req: LearningNodeCreate,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> LearningNodeOut:
    """Create a new dynamic learning node along the course learning map."""
    tenant_id = _get_tenant_id(user)
    is_admin = user.role in ["ADMIN", "SUPER_ADMIN"]
    await KnowledgeService.verify_teacher_access(
        db=db, offering_id=offering_id, tenant_id=tenant_id, user_id=uuid.UUID(user.id), is_admin=is_admin
    )
    node = await LearningService.create_learning_node(
        db=db,
        offering_id=offering_id,
        tenant_id=tenant_id,
        user_id=uuid.UUID(user.id),
        data=req,
    )
    return LearningNodeOut(
        id=node.id,
        institution_id=node.institution_id,
        course_offering_id=node.course_offering_id,
        course_content_version_id=node.course_content_version_id,
        node_code=node.node_code,
        module_title=node.module_title,
        difficulty_rank=node.difficulty_rank,
        title=node.title,
        description=node.description,
        sequence_no=node.sequence_no,
        status=node.status,
        completion_rule_json=node.completion_rule_json,
        created_by_user_id=node.created_by_user_id,
        published_at=node.published_at,
        created_at=node.created_at,
        updated_at=node.updated_at,
        concept_ids=req.concept_ids,
        prerequisite_node_ids=req.prerequisite_node_ids,
    )


@router.get("/courses/{offering_id}/learning-nodes", response_model=List[LearningNodeOut])
async def list_course_learning_nodes_teacher(
    offering_id: uuid.UUID,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> List[LearningNodeOut]:
    """List persisted learning nodes, including draft nodes, for the assigned course studio."""
    tenant_id = _get_tenant_id(user)
    await KnowledgeService.verify_teacher_access(
        db=db, offering_id=offering_id, tenant_id=tenant_id,
        user_id=uuid.UUID(user.id), is_admin=user.role in ["ADMIN", "SUPER_ADMIN"],
    )
    stmt = (
        select(LearningNode)
        .options(selectinload(LearningNode.concept_links), selectinload(LearningNode.prerequisites))
        .where(LearningNode.course_offering_id == offering_id, LearningNode.institution_id == tenant_id)
        .order_by(LearningNode.sequence_no, LearningNode.created_at)
    )
    raw_nodes = (await db.execute(stmt)).scalars().unique().all()
    nodes = [
        node for node in raw_nodes
        if node.title != "Course Quizzes & Assessments"
        and (node.node_code or "") not in ["QUIZZES", "QUIZ_CONTAINER"]
    ]
    return [LearningNodeOut(
        id=node.id, institution_id=node.institution_id, course_offering_id=node.course_offering_id,
        course_content_version_id=node.course_content_version_id, node_code=node.node_code,
        module_title=node.module_title,
        difficulty_rank=node.difficulty_rank,
        title=node.title, description=node.description, sequence_no=node.sequence_no, status=node.status,
        completion_rule_json=node.completion_rule_json, created_by_user_id=node.created_by_user_id,
        published_at=node.published_at, created_at=node.created_at, updated_at=node.updated_at,
        concept_ids=[link.concept_id for link in node.concept_links],
        prerequisite_node_ids=[link.prerequisite_node_id for link in node.prerequisites],
    ) for node in nodes]


@router.patch("/learning-nodes/{node_id}", response_model=LearningNodeOut)
async def update_learning_node(
    node_id: uuid.UUID,
    req: LearningNodeUpdate,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> LearningNodeOut:
    tenant_id = _get_tenant_id(user)
    current = await db.get(LearningNode, node_id)
    if not current or current.institution_id != tenant_id:
        raise AppException(status_code=404, code="NODE_NOT_FOUND", message="Learning node not found.")
    await KnowledgeService.verify_teacher_access(
        db=db, offering_id=current.course_offering_id, tenant_id=tenant_id,
        user_id=uuid.UUID(user.id), is_admin=user.role in ["ADMIN", "SUPER_ADMIN"],
    )
    node = await LearningService.update_learning_node(db, node_id, tenant_id, req)
    stmt = select(LearningNode).options(
        selectinload(LearningNode.concept_links), selectinload(LearningNode.prerequisites)
    ).where(LearningNode.id == node.id)
    node = (await db.execute(stmt)).scalars().first()
    return LearningNodeOut(
        id=node.id, institution_id=node.institution_id, course_offering_id=node.course_offering_id,
        course_content_version_id=node.course_content_version_id, node_code=node.node_code,
        module_title=node.module_title,
        difficulty_rank=node.difficulty_rank,
        title=node.title, description=node.description, sequence_no=node.sequence_no,
        revision=node.revision, status=node.status, completion_rule_json=node.completion_rule_json,
        created_by_user_id=node.created_by_user_id, published_at=node.published_at,
        created_at=node.created_at, updated_at=node.updated_at,
        concept_ids=[link.concept_id for link in node.concept_links],
        prerequisite_node_ids=[link.prerequisite_node_id for link in node.prerequisites],
    )


@router.delete("/learning-nodes/{node_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_learning_node(
    node_id: uuid.UUID,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Delete a learning node and cascade associated relationships."""
    tenant_id = _get_tenant_id(user)
    current = await db.get(LearningNode, node_id)
    if not current or current.institution_id != tenant_id:
        raise AppException(status_code=404, code="NODE_NOT_FOUND", message="Learning node not found.")
    await KnowledgeService.verify_teacher_access(
        db=db, offering_id=current.course_offering_id, tenant_id=tenant_id,
        user_id=uuid.UUID(user.id), is_admin=user.role in ["ADMIN", "SUPER_ADMIN"],
    )
    await db.delete(current)
    await db.commit()
    return None


@router.post("/learning-nodes/{node_id}/prerequisites", response_model=LearningNodePrerequisiteOut, status_code=status.HTTP_201_CREATED)
async def add_prerequisite(
    node_id: uuid.UUID,
    req: LearningNodePrerequisiteCreate,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> LearningNodePrerequisiteOut:
    """Add a prerequisite dependency with automatic circular-cycle detection."""
    tenant_id = _get_tenant_id(user)
    link = await LearningService.add_prerequisite(
        db=db,
        node_id=node_id,
        tenant_id=tenant_id,
        data=req,
    )
    return LearningNodePrerequisiteOut.model_validate(link)


@router.post("/learning-nodes/{node_id}/publish", response_model=LearningNodeOut)
async def publish_learning_node(
    node_id: uuid.UUID,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> LearningNodeOut:
    """Publish a learning node, making it visible to enrolled students on their learning map."""
    tenant_id = _get_tenant_id(user)
    node = await LearningService.publish_learning_node(
        db=db,
        node_id=node_id,
        tenant_id=tenant_id,
    )
    return LearningNodeOut.model_validate(node)


# ------------------------------------------------------------------------------
# Activity Authoring
# ------------------------------------------------------------------------------

@router.post("/learning-nodes/{node_id}/activities", response_model=ActivityOut, status_code=status.HTTP_201_CREATED)
async def create_activity(
    node_id: uuid.UUID,
    req: ActivityCreate,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> ActivityOut:
    """
    Author an interactive activity (mcq, fill_blank, matching_pairs, ordering, classification, key_points_check).
    Automatically sanitizes student-safe payload and server-authoritative answer key.
    """
    tenant_id = _get_tenant_id(user)
    activity = await LearningService.create_activity(
        db=db,
        node_id=node_id,
        tenant_id=tenant_id,
        user_id=uuid.UUID(user.id),
        data=req,
    )
    # Fetch latest version
    v_stmt = (
        select(ActivityVersion)
        .where(ActivityVersion.activity_id == activity.id)
        .order_by(ActivityVersion.version_number.desc())
        .limit(1)
    )
    latest_v = (await db.execute(v_stmt)).scalars().first()

    return ActivityOut(
        id=activity.id,
        institution_id=activity.institution_id,
        learning_node_id=activity.learning_node_id,
        question_id=activity.question_id,
        status=activity.status,
        created_at=activity.created_at,
        latest_version=ActivityVersionOut.model_validate(latest_v) if latest_v else None,
    )


@router.get("/learning-nodes/{node_id}/activities", response_model=List[ActivityOut])
async def list_node_activities_teacher(
    node_id: uuid.UUID,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> List[ActivityOut]:
    """Teacher view of all active activities under a node including answer keys."""
    tenant_id = _get_tenant_id(user)
    stmt = (
        select(Activity)
        .options(selectinload(Activity.versions))
        .where(
            Activity.learning_node_id == node_id,
            Activity.institution_id == tenant_id,
            Activity.status != "archived",
        )
        .order_by(Activity.created_at.asc())
    )
    activities = (await db.execute(stmt)).scalars().all()
    results: List[ActivityOut] = []
    for a in activities:
        v = a.versions[0] if a.versions else None
        results.append(
            ActivityOut(
                id=a.id,
                institution_id=a.institution_id,
                learning_node_id=a.learning_node_id,
                question_id=a.question_id,
                status=a.status,
                created_at=a.created_at,
                latest_version=ActivityVersionOut.model_validate(v) if v else None,
            )
        )
    return results


@router.post("/learning-nodes/{node_id}/generate-practice-questions", response_model=List[ActivityOut])
async def generate_node_practice_questions(
    node_id: uuid.UUID,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> List[ActivityOut]:
    """Generate grounded practice questions for this node using question paper items and lecture slides."""
    tenant_id = _get_tenant_id(user)
    node = await db.get(LearningNode, node_id)
    if not node or node.institution_id != tenant_id:
        raise AppException(status_code=404, code="NODE_NOT_FOUND", message="Learning node not found.")

    await _ensure_node_practice_bank(db, node, tenant_id, uuid.UUID(user.id), force=True)
    await db.commit()

    stmt = (
        select(Activity)
        .options(selectinload(Activity.versions))
        .where(Activity.learning_node_id == node_id, Activity.status == "active")
        .order_by(Activity.created_at.asc())
    )
    acts = (await db.execute(stmt)).scalars().all()
    results = []
    for a in acts:
        v = a.versions[-1] if a.versions else None
        results.append(
            ActivityOut(
                id=a.id,
                institution_id=a.institution_id,
                learning_node_id=a.learning_node_id,
                question_id=a.question_id,
                status=a.status,
                created_at=a.created_at,
                latest_version=ActivityVersionOut.model_validate(v) if v else None,
            )
        )
    return results


@router.post("/courses/{offering_id}/generate-all-practice-questions")
async def generate_all_course_practice_questions(
    offering_id: uuid.UUID,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate grounded practice questions for every node in this course offering."""
    tenant_id = _get_tenant_id(user)
    stmt = (
        select(LearningNode)
        .where(LearningNode.course_offering_id == offering_id, LearningNode.institution_id == tenant_id)
        .order_by(LearningNode.sequence_no.asc())
    )
    nodes = (await db.execute(stmt)).scalars().all()
    total_generated = 0
    for node in nodes:
        bank = await _ensure_node_practice_bank(db, node, tenant_id, uuid.UUID(user.id))
        total_generated += len(bank)
    await db.commit()
    return {"status": "ok", "nodes_count": len(nodes), "total_questions": total_generated}


@router.patch("/activities/{activity_id}", response_model=ActivityOut)
async def update_activity(
    activity_id: uuid.UUID,
    req: ActivityCreate,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> ActivityOut:
    """Update an existing activity's question text, options, answer key, and explanation."""
    tenant_id = _get_tenant_id(user)
    activity = await LearningService.update_activity(
        db=db,
        activity_id=activity_id,
        tenant_id=tenant_id,
        user_id=uuid.UUID(user.id),
        data=req,
    )
    v_stmt = (
        select(ActivityVersion)
        .where(ActivityVersion.activity_id == activity.id)
        .order_by(ActivityVersion.version_number.desc())
        .limit(1)
    )
    latest_v = (await db.execute(v_stmt)).scalars().first()
    return ActivityOut(
        id=activity.id,
        institution_id=activity.institution_id,
        learning_node_id=activity.learning_node_id,
        question_id=activity.question_id,
        status=activity.status,
        created_at=activity.created_at,
        latest_version=ActivityVersionOut.model_validate(latest_v) if latest_v else None,
    )


@router.delete("/activities/{activity_id}", response_model=ActivityOut)
async def archive_activity(
    activity_id: uuid.UUID,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> ActivityOut:
    """Archive / delete a practice activity so it is immediately removed from student practice."""
    tenant_id = _get_tenant_id(user)
    activity = await LearningService.archive_activity(
        db=db,
        activity_id=activity_id,
        tenant_id=tenant_id,
    )
    return ActivityOut(
        id=activity.id,
        institution_id=activity.institution_id,
        learning_node_id=activity.learning_node_id,
        question_id=activity.question_id,
        status=activity.status,
        created_at=activity.created_at,
        latest_version=None,
    )


# ------------------------------------------------------------------------------
# Student Course Learning Map & Activity Practice
# ------------------------------------------------------------------------------

@router.get("/courses/{offering_id}/student/map", response_model=CourseLearningMapResponse)
async def get_student_learning_map(
    offering_id: uuid.UUID,
    user: UserProfile = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> CourseLearningMapResponse:
    """
    Student learning map progression view.
    Resolves only published nodes with calculated prerequisite unlock statuses.
    """
    tenant_id = _get_tenant_id(user)
    return await LearningService.resolve_student_learning_map(
        db=db,
        offering_id=offering_id,
        tenant_id=tenant_id,
        student_id=uuid.UUID(user.id),
    )


@router.get("/learning-nodes/{node_id}/student/activities", response_model=List[ActivityOut])
async def list_node_activities_student(
    node_id: uuid.UUID,
    user: UserProfile = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> List[ActivityOut]:
    """
    Student activity practice view.
    Guarantees answer_key_json is NEVER sent to the client.
    """
    tenant_id = _get_tenant_id(user)
    node = await db.get(LearningNode, node_id)
    if not node or node.institution_id != tenant_id:
        raise AppException(status_code=404, code="NODE_NOT_FOUND", message="Learning node not found.")

    await KnowledgeService.verify_student_access(
        db=db, offering_id=node.course_offering_id, tenant_id=tenant_id, user_id=uuid.UUID(user.id)
    )

    stmt = (
        select(Activity)
        .options(selectinload(Activity.versions))
        .where(Activity.learning_node_id == node_id, Activity.institution_id == tenant_id, Activity.status == "active")
    )
    activities = (await db.execute(stmt)).scalars().all()
    results: List[ActivityOut] = []
    for a in activities:
        v = a.versions[0] if a.versions else None
        v_out = None
        if v:
            v_out = ActivityVersionOut(
                id=v.id,
                institution_id=v.institution_id,
                activity_id=v.activity_id,
                version_number=v.version_number,
                activity_type=v.activity_type,
                schema_version=v.schema_version,
                title=v.title,
                instructions=v.instructions,
                student_payload_json=v.student_payload_json,
                answer_key_json=None,  # STRICT: never sent to student
                scoring_config_json=v.scoring_config_json,
                approval_status=v.approval_status,
                created_at=v.created_at,
            )
        results.append(
            ActivityOut(
                id=a.id,
                institution_id=a.institution_id,
                learning_node_id=a.learning_node_id,
                question_id=a.question_id,
                status=a.status,
                created_at=a.created_at,
                latest_version=v_out,
            )
        )
    return results


@router.post("/activities/{activity_version_id}/evaluate", response_model=ActivityEvaluationResult)
async def evaluate_activity(
    activity_version_id: uuid.UUID,
    req: ActivityEvaluateRequest,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ActivityEvaluationResult:
    """
    Server-authoritative deterministic practice scoring.
    No LLM is called during answer evaluation.
    """
    tenant_id = _get_tenant_id(user)
    return await LearningService.evaluate_activity(
        db=db,
        activity_version_id=activity_version_id,
        tenant_id=tenant_id,
        response_data=req.response_data,
    )


# ------------------------------------------------------------------------------
# Student Adaptive Practice Loop (Learn Tab)
# ------------------------------------------------------------------------------

@router.post("/learning-nodes/{node_id}/practice/start", response_model=PracticeSessionStartOut)
async def start_adaptive_practice(
    node_id: uuid.UUID,
    user: UserProfile = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> PracticeSessionStartOut:
    """Start or resume an adaptive practice session for a roadmap topic."""
    tenant_id = _get_tenant_id(user)
    return await AdaptivePracticeService.start_or_resume_practice(
        db=db,
        node_id=node_id,
        tenant_id=tenant_id,
        user_id=uuid.UUID(user.id),
    )


@router.post("/practice-sessions/{session_id}/hint", response_model=PracticeHintOut)
async def get_adaptive_practice_hint(
    session_id: uuid.UUID,
    user: UserProfile = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> PracticeHintOut:
    """Reveal a hint for the current practice question and track hint usage."""
    tenant_id = _get_tenant_id(user)
    return await AdaptivePracticeService.request_hint(
        db=db,
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=uuid.UUID(user.id),
    )


@router.post("/practice-sessions/{session_id}/answer", response_model=PracticeAnswerResultOut)
async def submit_adaptive_practice_answer(
    session_id: uuid.UUID,
    req: PracticeAnswerRequest,
    user: UserProfile = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> PracticeAnswerResultOut:
    """Evaluate a practice answer, deliver immediate explanation/remediation, and adapt difficulty."""
    tenant_id = _get_tenant_id(user)
    return await AdaptivePracticeService.submit_answer(
        db=db,
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=uuid.UUID(user.id),
        data=req,
    )


# ------------------------------------------------------------------------------
# Student Learning Progress Summary (/student/progress-summary)
# ------------------------------------------------------------------------------

@router.get("/student/progress-summary", response_model=StudentProgressSummaryResponse)
async def get_student_progress_summary(
    curriculum_subject_entry_id: Optional[uuid.UUID] = Query(None),
    user: UserProfile = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> StudentProgressSummaryResponse:
    """Authoritative student learning progress summary across topics, practice questions, and interventions."""
    tenant_id = _get_tenant_id(user)
    return await LearningService.get_student_progress_summary(
        db=db,
        tenant_id=tenant_id,
        user=user,
        curriculum_subject_entry_id=curriculum_subject_entry_id,
    )

