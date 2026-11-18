import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status, Request, Response
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
from app.modules.auth.models import InstitutionMembership
from app.modules.auth.models import User
from app.modules.assessments.models import (
    Assessment,
    AssessmentVersion,
    AssessmentItem,
    AssessmentAttempt,
    AssessmentStudentOverride,
)
from app.modules.interventions.models import Intervention
from app.modules.assessments.schemas import (
    AssessmentCreate,
    AssessmentOut,
    StartAttemptResponse,
    SaveResponseRequest,
    SubmitAttemptRequest,
    AttemptSummaryOut,
    CourseAssessmentActivityOut,
    QuizCreateRequest,
    QuizAiGenerateRequest,
    QuizAiGenerateResponse,
    FormalQuizCreateRequest,
    StudentOverrideCreate,
    StudentOverrideOut,
    FormalQuizRosterSummaryOut,
    MarkOverrideRequest,
)
from app.modules.assessments.service import AssessmentService
from app.modules.knowledge.service import KnowledgeService

router = APIRouter(tags=["Assessments, CBT Attempts & Scoring"])


def _get_tenant_id(user: UserProfile) -> uuid.UUID:
    if not user.institution_id:
        raise AppException(code="NO_TENANT_CONTEXT", message="Institution context required.", status_code=400)
    return uuid.UUID(user.institution_id)


async def _get_membership_id(db: AsyncSession, user: UserProfile) -> uuid.UUID:
    stmt = select(InstitutionMembership.id).where(
        InstitutionMembership.user_id == uuid.UUID(user.id),
        InstitutionMembership.institution_id == uuid.UUID(user.institution_id),
    )
    res = await db.execute(stmt)
    mem_id = res.scalar()
    if not mem_id:
        raise AppException(status_code=403, code="NO_MEMBERSHIP", message="User has no membership in this institution.")
    return mem_id


# ------------------------------------------------------------------------------
# Teacher Assessment Authoring & Publication
# ------------------------------------------------------------------------------

@router.post("/courses/{offering_id}/assessments", response_model=AssessmentOut, status_code=status.HTTP_201_CREATED)
async def create_assessment(
    offering_id: uuid.UUID,
    req: AssessmentCreate,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> AssessmentOut:
    """Create an assessment (Node Practice, Boss Arena, or Intervention Phase) with items."""
    tenant_id = _get_tenant_id(user)
    is_admin = user.role in ["ADMIN", "SUPER_ADMIN"]
    await KnowledgeService.verify_teacher_access(
        db=db, offering_id=offering_id, tenant_id=tenant_id, user_id=uuid.UUID(user.id), is_admin=is_admin
    )
    assessment = await AssessmentService.create_assessment(
        db=db,
        offering_id=offering_id,
        tenant_id=tenant_id,
        user_id=uuid.UUID(user.id),
        data=req,
    )
    return AssessmentOut.model_validate(assessment)


@router.post("/assessments/{assessment_id}/publish", response_model=AssessmentOut)
async def publish_assessment(
    assessment_id: uuid.UUID,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> AssessmentOut:
    """Publish an assessment version, locking items and making it available to students."""
    tenant_id = _get_tenant_id(user)
    is_admin = user.role in ["ADMIN", "SUPER_ADMIN"]
    existing = await AssessmentService.load_assessment_full(db, assessment_id, tenant_id)
    await KnowledgeService.verify_teacher_access(
        db=db, offering_id=existing.course_offering_id, tenant_id=tenant_id, user_id=uuid.UUID(user.id), is_admin=is_admin
    )
    await AssessmentService.publish_assessment(
        db=db,
        assessment_id=assessment_id,
        tenant_id=tenant_id,
    )
    refreshed = await AssessmentService.load_assessment_full(db, assessment_id, tenant_id)
    return AssessmentService.serialize_assessment(refreshed, include_answer_key=True)


@router.post("/assessments/{assessment_id}/unpublish", response_model=AssessmentOut)
async def unpublish_assessment(
    assessment_id: uuid.UUID,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> AssessmentOut:
    """Revert a published assessment back to draft status."""
    tenant_id = _get_tenant_id(user)
    is_admin = user.role in ["ADMIN", "SUPER_ADMIN"]
    existing = await AssessmentService.load_assessment_full(db, assessment_id, tenant_id)
    await KnowledgeService.verify_teacher_access(
        db=db, offering_id=existing.course_offering_id, tenant_id=tenant_id, user_id=uuid.UUID(user.id), is_admin=is_admin
    )
    updated = await AssessmentService.unpublish_assessment(db=db, assessment_id=assessment_id, tenant_id=tenant_id)
    return AssessmentService.serialize_assessment(updated, include_answer_key=True)


@router.delete("/assessments/{assessment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_assessment(
    assessment_id: uuid.UUID,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete (or archive if attempts exist) a course assessment."""
    tenant_id = _get_tenant_id(user)
    is_admin = user.role in ["ADMIN", "SUPER_ADMIN"]
    existing = await AssessmentService.load_assessment_full(db, assessment_id, tenant_id)
    await KnowledgeService.verify_teacher_access(
        db=db, offering_id=existing.course_offering_id, tenant_id=tenant_id, user_id=uuid.UUID(user.id), is_admin=is_admin
    )
    await AssessmentService.delete_or_archive_assessment(db=db, assessment_id=assessment_id, tenant_id=tenant_id)


@router.post("/courses/{offering_id}/quizzes", response_model=AssessmentOut, status_code=status.HTTP_201_CREATED)
async def create_quiz(
    offering_id: uuid.UUID,
    req: QuizCreateRequest,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> AssessmentOut:
    """Author a course quiz with MCQ items and optionally publish it immediately."""
    tenant_id = _get_tenant_id(user)
    is_admin = user.role in ["ADMIN", "SUPER_ADMIN"]
    await KnowledgeService.verify_teacher_access(
        db=db, offering_id=offering_id, tenant_id=tenant_id, user_id=uuid.UUID(user.id), is_admin=is_admin
    )
    assessment = await AssessmentService.create_quiz(
        db=db,
        offering_id=offering_id,
        tenant_id=tenant_id,
        user_id=uuid.UUID(user.id),
        data=req,
    )
    return AssessmentService.serialize_assessment(assessment, include_answer_key=True)


@router.post("/courses/{offering_id}/quizzes/ai-generate", response_model=QuizAiGenerateResponse)
async def generate_quiz_with_ai(
    offering_id: uuid.UUID,
    req: QuizAiGenerateRequest,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> QuizAiGenerateResponse:
    """Synthesize draft MCQ quiz questions for a course topic using AI."""
    tenant_id = _get_tenant_id(user)
    is_admin = user.role in ["ADMIN", "SUPER_ADMIN"]
    await KnowledgeService.verify_teacher_access(
        db=db, offering_id=offering_id, tenant_id=tenant_id, user_id=uuid.UUID(user.id), is_admin=is_admin
    )
    return await AssessmentService.generate_quiz_with_ai(
        db=db,
        offering_id=offering_id,
        tenant_id=tenant_id,
        data=req,
    )


@router.get("/courses/{offering_id}/assessments", response_model=List[AssessmentOut])
async def list_course_assessments_teacher(
    offering_id: uuid.UUID,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> List[AssessmentOut]:
    """Teacher view of all assessments configured for a course offering."""
    tenant_id = _get_tenant_id(user)
    is_admin = user.role in ["ADMIN", "SUPER_ADMIN"]
    await KnowledgeService.verify_teacher_access(
        db=db, offering_id=offering_id, tenant_id=tenant_id, user_id=uuid.UUID(user.id), is_admin=is_admin
    )
    stmt = (
        select(Assessment)
        .options(
            selectinload(Assessment.versions)
            .selectinload(AssessmentVersion.items)
            .selectinload(AssessmentItem.activity_version),
            selectinload(Assessment.versions)
            .selectinload(AssessmentVersion.items)
            .selectinload(AssessmentItem.question_version),
            selectinload(Assessment.versions)
            .selectinload(AssessmentVersion.items)
            .selectinload(AssessmentItem.concept_allocations),
        )
        .where(
            Assessment.course_offering_id == offering_id,
            Assessment.institution_id == tenant_id,
            Assessment.status != "archived",
        )
        .order_by(Assessment.created_at.desc())
    )
    assessments = (await db.execute(stmt)).scalars().all()
    return [AssessmentService.serialize_assessment(a, include_answer_key=True) for a in assessments]


@router.get("/courses/{offering_id}/assessment-activity", response_model=List[CourseAssessmentActivityOut])
async def get_course_assessment_activity(
    offering_id: uuid.UUID,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> List[CourseAssessmentActivityOut]:
    """Teacher-only recent attempt activity, scoped to an assigned offering."""
    tenant_id = _get_tenant_id(user)
    await KnowledgeService.verify_teacher_access(
        db=db, offering_id=offering_id, tenant_id=tenant_id,
        user_id=uuid.UUID(user.id), is_admin=user.role in ["ADMIN", "SUPER_ADMIN"],
    )
    stmt = (
        select(AssessmentAttempt, Assessment, User.display_name)
        .join(AssessmentVersion, AssessmentAttempt.assessment_version_id == AssessmentVersion.id)
        .join(Assessment, AssessmentVersion.assessment_id == Assessment.id)
        .join(InstitutionMembership, AssessmentAttempt.student_membership_id == InstitutionMembership.id)
        .join(User, InstitutionMembership.user_id == User.id)
        .where(
            AssessmentAttempt.institution_id == tenant_id,
            Assessment.course_offering_id == offering_id,
        )
        .order_by(AssessmentAttempt.started_at.desc())
        .limit(100)
    )
    rows = (await db.execute(stmt)).all()
    return [CourseAssessmentActivityOut(
        attempt_id=attempt.id,
        student_membership_id=attempt.student_membership_id,
        student_name=display_name,
        assessment_id=assessment.id,
        assessment_title=assessment.title,
        assessment_type=assessment.assessment_type,
        status=attempt.status,
        scoring_status=attempt.scoring_status,
        marks_awarded=float(attempt.marks_awarded) if attempt.marks_awarded is not None else None,
        marks_available=float(attempt.marks_available) if attempt.marks_available is not None else None,
        started_at=attempt.started_at,
        submitted_at=attempt.submitted_at,
    ) for attempt, assessment, display_name in rows]


# ------------------------------------------------------------------------------
# Student CBT Assessment Experience & Scoring
# ------------------------------------------------------------------------------

@router.get("/courses/{offering_id}/student/assessments", response_model=List[AssessmentOut])
async def list_course_assessments_student(
    offering_id: uuid.UUID,
    user: UserProfile = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> List[AssessmentOut]:
    """Student view of published assessments for their enrolled course offering."""
    tenant_id = _get_tenant_id(user)
    await KnowledgeService.verify_student_access(
        db=db, offering_id=offering_id, tenant_id=tenant_id, user_id=uuid.UUID(user.id)
    )
    # Find IDs of assessments that are strictly bound to active interventions
    bound_ids_stmt = select(
        Intervention.phase_a_assessment_id,
        Intervention.phase_b_practice_assessment_id,
        Intervention.phase_c_assessment_id,
    ).where(
        Intervention.institution_id == tenant_id,
        Intervention.course_offering_id == offering_id,
        Intervention.status.in_(["active", "published"]),
    )
    bound_rows = (await db.execute(bound_ids_stmt)).all()
    bound_intervention_assessment_ids = set()
    for row in bound_rows:
        for ass_id in row:
            if ass_id is not None:
                bound_intervention_assessment_ids.add(ass_id)

    stmt = (
        select(Assessment)
        .options(
            selectinload(Assessment.versions)
            .selectinload(AssessmentVersion.items)
            .selectinload(AssessmentItem.activity_version),
            selectinload(Assessment.versions)
            .selectinload(AssessmentVersion.items)
            .selectinload(AssessmentItem.question_version),
            selectinload(Assessment.versions)
            .selectinload(AssessmentVersion.items)
            .selectinload(AssessmentItem.concept_allocations),
        )
        .where(
            Assessment.course_offering_id == offering_id,
            Assessment.institution_id == tenant_id,
            Assessment.status == "published",
        )
        .order_by(Assessment.created_at.desc())
    )
    assessments = (await db.execute(stmt)).scalars().all()
    results: List[AssessmentOut] = []
    for a in assessments:
        if a.id in bound_intervention_assessment_ids or (a.assessment_type and a.assessment_type.startswith("intervention_")):
            continue
        serialized = AssessmentService.serialize_assessment(a, include_answer_key=False, published_only=True)
        if serialized.latest_version is not None:
            results.append(serialized)
    return results


@router.post("/assessments/{assessment_id}/start", response_model=StartAttemptResponse, status_code=status.HTTP_201_CREATED)
async def start_assessment_attempt(
    assessment_id: uuid.UUID,
    idempotency_key: Optional[str] = Query(None),
    user: UserProfile = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> StartAttemptResponse:
    """
    Start a CBT assessment attempt.
    Enforces time limits, creates server-side timer, and initializes response slots.
    """
    tenant_id = _get_tenant_id(user)
    student_mem_id = await _get_membership_id(db, user)
    return await AssessmentService.start_attempt(
        db=db,
        assessment_id=assessment_id,
        tenant_id=tenant_id,
        student_membership_id=student_mem_id,
        student_id=uuid.UUID(user.id),
        idempotency_key=idempotency_key,
    )


@router.post("/attempts/{attempt_id}/responses", status_code=status.HTTP_200_OK)
async def save_attempt_response(
    attempt_id: uuid.UUID,
    req: SaveResponseRequest,
    user: UserProfile = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Autosave response draft and track palette navigation states.
    Validates attempt is within the server-side time limit.
    """
    tenant_id = _get_tenant_id(user)
    student_mem_id = await _get_membership_id(db, user)
    await AssessmentService.save_response(
        db=db,
        attempt_id=attempt_id,
        tenant_id=tenant_id,
        student_membership_id=student_mem_id,
        data=req,
    )
    return {"status": "saved", "item_id": str(req.item_id), "response_state": req.response_state}


@router.post("/attempts/{attempt_id}/submit", response_model=AttemptSummaryOut)
async def submit_assessment_attempt(
    attempt_id: uuid.UUID,
    req: Optional[SubmitAttemptRequest] = None,
    user: UserProfile = Depends(require_student),
    db: AsyncSession = Depends(get_db),
) -> AttemptSummaryOut:
    """
    Finalize and deterministically score an assessment attempt.
    Attributes marks to concepts proportionally without mark inflation.
    """
    tenant_id = _get_tenant_id(user)
    student_mem_id = await _get_membership_id(db, user)
    return await AssessmentService.submit_attempt(
        db=db,
        attempt_id=attempt_id,
        tenant_id=tenant_id,
        student_membership_id=student_mem_id,
    )


@router.get("/attempts/{attempt_id}", response_model=AttemptSummaryOut)
async def get_attempt_summary(
    attempt_id: uuid.UUID,
    user: UserProfile = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AttemptSummaryOut:
    """Get summarized score and concept breakdown for an attempt."""
    tenant_id = _get_tenant_id(user)
    return await AssessmentService.get_attempt_summary(
        db=db,
        attempt_id=attempt_id,
        tenant_id=tenant_id,
    )


# ------------------------------------------------------------------------------
# Formal Academic Quizzes, Makeup Overrides & Grade Roster
# ------------------------------------------------------------------------------

@router.post("/courses/{offering_id}/formal-quizzes", response_model=AssessmentOut, status_code=status.HTTP_201_CREATED)
async def create_formal_quiz(
    offering_id: uuid.UUID,
    req: FormalQuizCreateRequest,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> AssessmentOut:
    """Create a scheduled credit-bearing formal academic quiz."""
    tenant_id = _get_tenant_id(user)
    is_admin = user.role in ["ADMIN", "SUPER_ADMIN"]
    await KnowledgeService.verify_teacher_access(
        db=db, offering_id=offering_id, tenant_id=tenant_id, user_id=uuid.UUID(user.id), is_admin=is_admin
    )
    assessment = await AssessmentService.create_formal_quiz(
        db=db,
        offering_id=offering_id,
        tenant_id=tenant_id,
        user_id=uuid.UUID(user.id),
        data=req,
    )
    return AssessmentService.serialize_assessment(assessment, include_answer_key=True)


@router.get("/courses/{offering_id}/formal-quizzes/{quiz_id}/roster", response_model=FormalQuizRosterSummaryOut)
async def get_formal_quiz_roster(
    offering_id: uuid.UUID,
    quiz_id: uuid.UUID,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> FormalQuizRosterSummaryOut:
    """Get full enrolled course roster with attendance, scores, and makeup statuses for a formal quiz."""
    tenant_id = _get_tenant_id(user)
    is_admin = user.role in ["ADMIN", "SUPER_ADMIN"]
    await KnowledgeService.verify_teacher_access(
        db=db, offering_id=offering_id, tenant_id=tenant_id, user_id=uuid.UUID(user.id), is_admin=is_admin
    )
    return await AssessmentService.get_formal_quiz_roster(
        db=db,
        assessment_id=quiz_id,
        tenant_id=tenant_id,
    )


@router.post("/formal-quizzes/{quiz_id}/overrides", response_model=StudentOverrideOut, status_code=status.HTTP_201_CREATED)
async def grant_formal_quiz_override(
    quiz_id: uuid.UUID,
    req: StudentOverrideCreate,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> StudentOverrideOut:
    """Grant a student an individual makeup window or record confirmed absence."""
    tenant_id = _get_tenant_id(user)
    is_admin = user.role in ["ADMIN", "SUPER_ADMIN"]
    asmt = await db.get(Assessment, quiz_id)
    if not asmt or asmt.institution_id != tenant_id:
        raise AppException(status_code=404, code="ASSESSMENT_NOT_FOUND", message="Assessment not found.")
    await KnowledgeService.verify_teacher_access(
        db=db, offering_id=asmt.course_offering_id, tenant_id=tenant_id, user_id=uuid.UUID(user.id), is_admin=is_admin
    )
    override = await AssessmentService.grant_student_override(
        db=db,
        assessment_id=quiz_id,
        tenant_id=tenant_id,
        user_id=uuid.UUID(user.id),
        data=req,
    )
    return StudentOverrideOut.model_validate(override)


@router.put("/formal-quizzes/attempts/{attempt_id}/override-marks")
async def override_attempt_marks(
    attempt_id: uuid.UUID,
    req: MarkOverrideRequest,
    request: Request,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Faculty override of an attempt's marks with reason and audit log."""
    tenant_id = _get_tenant_id(user)
    is_admin = user.role in ["ADMIN", "SUPER_ADMIN"]
    att = await db.get(AssessmentAttempt, attempt_id)
    if not att or att.institution_id != tenant_id:
        raise AppException(status_code=404, code="ATTEMPT_NOT_FOUND", message="Attempt not found.")
    v = await db.get(AssessmentVersion, att.assessment_version_id)
    asmt = await db.get(Assessment, v.assessment_id) if v else None
    if asmt:
        await KnowledgeService.verify_teacher_access(
            db=db, offering_id=asmt.course_offering_id, tenant_id=tenant_id, user_id=uuid.UUID(user.id), is_admin=is_admin
        )
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    attempt = await AssessmentService.override_attempt_marks(
        db=db,
        attempt_id=attempt_id,
        tenant_id=tenant_id,
        user_id=uuid.UUID(user.id),
        data=req,
        ip_address=client_ip,
        user_agent=user_agent,
    )
    return {
        "status": "success",
        "attempt_id": str(attempt.id),
        "faculty_override_marks": float(attempt.faculty_override_marks),
        "override_reason": attempt.override_reason,
    }


@router.post("/formal-quizzes/{quiz_id}/finalize", response_model=AssessmentOut)
async def finalize_formal_quiz(
    quiz_id: uuid.UUID,
    request: Request,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> AssessmentOut:
    """Lock formal quiz marks so that results become official and solutions are visible."""
    tenant_id = _get_tenant_id(user)
    is_admin = user.role in ["ADMIN", "SUPER_ADMIN"]
    asmt = await db.get(Assessment, quiz_id)
    if not asmt or asmt.institution_id != tenant_id:
        raise AppException(status_code=404, code="ASSESSMENT_NOT_FOUND", message="Assessment not found.")
    await KnowledgeService.verify_teacher_access(
        db=db, offering_id=asmt.course_offering_id, tenant_id=tenant_id, user_id=uuid.UUID(user.id), is_admin=is_admin
    )
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    assessment = await AssessmentService.finalize_quiz_marks(
        db=db,
        assessment_id=quiz_id,
        tenant_id=tenant_id,
        user_id=uuid.UUID(user.id),
        ip_address=client_ip,
        user_agent=user_agent,
    )
    return AssessmentService.serialize_assessment(assessment, include_answer_key=True)


@router.get("/courses/{offering_id}/formal-quizzes/{quiz_id}/export-excel")
async def export_formal_quiz_excel(
    offering_id: uuid.UUID,
    quiz_id: uuid.UUID,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
):
    """Download official grade spreadsheet (.xlsx) for formal quiz records."""
    tenant_id = _get_tenant_id(user)
    is_admin = user.role in ["ADMIN", "SUPER_ADMIN"]
    await KnowledgeService.verify_teacher_access(
        db=db, offering_id=offering_id, tenant_id=tenant_id, user_id=uuid.UUID(user.id), is_admin=is_admin
    )
    excel_bytes = await AssessmentService.export_formal_quiz_excel(
        db=db,
        assessment_id=quiz_id,
        tenant_id=tenant_id,
    )
    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="Quiz_Marks_{str(quiz_id)[:8]}.xlsx"',
        },
    )

