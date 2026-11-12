import uuid
from typing import Optional, List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.common.exceptions import AppException
from app.modules.rbac.dependencies import (
    require_teacher,
    require_student,
    get_current_user,
)
from app.modules.auth.schemas import UserProfile
from app.modules.questions.schemas import (
    QuestionCreate,
    QuestionOut,
    QuestionVersionCreate,
    QuestionVersionOut,
    QuestionReviewRequest,
    QuestionRelationshipCreate,
    QuestionRelationshipOut,
    CourseQuestionCoverageReport,
    MisconceptionCreate,
    MisconceptionOut,
)
from app.modules.questions.service import QuestionService
from app.modules.knowledge.service import KnowledgeService

router = APIRouter(tags=["Question Bank & Assessment Items"])


def _get_tenant_id(user: UserProfile) -> uuid.UUID:
    if not user.institution_id:
        raise AppException(code="NO_TENANT_CONTEXT", message="Institution context required.", status_code=400)
    return uuid.UUID(user.institution_id)


@router.post("/questions", response_model=QuestionOut, status_code=status.HTTP_201_CREATED)
async def create_question(
    req: QuestionCreate,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> QuestionOut:
    """Create a new academic question with parts, options, and concept mark allocations."""
    tenant_id = _get_tenant_id(user)
    question = await QuestionService.create_question(
        db=db,
        tenant_id=tenant_id,
        user_id=uuid.UUID(user.id),
        data=req,
    )
    return await QuestionService.get_question(db, question.id, tenant_id)


@router.get("/questions/{question_id}", response_model=QuestionOut)
async def get_question(
    question_id: uuid.UUID,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> QuestionOut:
    """Get complete question details including latest version, parts, and concept allocations."""
    tenant_id = _get_tenant_id(user)
    return await QuestionService.get_question(db, question_id, tenant_id)


@router.post("/questions/{question_id}/versions", response_model=QuestionVersionOut, status_code=status.HTTP_201_CREATED)
async def create_question_version(
    question_id: uuid.UUID,
    req: QuestionVersionCreate,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> QuestionVersionOut:
    """Author a new version of an existing question with updated text, parts, or concept weights."""
    tenant_id = _get_tenant_id(user)
    v = await QuestionService.create_question_version(
        db=db,
        question_id=question_id,
        tenant_id=tenant_id,
        user_id=uuid.UUID(user.id),
        data=req,
    )
    # Re-fetch full question to serialize
    q_out = await QuestionService.get_question(db, question_id, tenant_id)
    return q_out.latest_version


@router.post("/question-versions/{version_id}/review", response_model=QuestionVersionOut)
async def review_question_version(
    version_id: uuid.UUID,
    req: QuestionReviewRequest,
    course_offering_id: Optional[uuid.UUID] = Query(None),
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> QuestionVersionOut:
    """
    Teacher review and approval/rejection of a question version.
    Validates mark budget consistency before approving.
    """
    tenant_id = _get_tenant_id(user)
    v = await QuestionService.review_question_version(
        db=db,
        version_id=version_id,
        tenant_id=tenant_id,
        user_id=uuid.UUID(user.id),
        data=req,
        course_offering_id=course_offering_id,
    )
    q_out = await QuestionService.get_question(db, v.question_id, tenant_id)
    return q_out.latest_version


@router.post("/questions/{question_id}/relationships", response_model=QuestionRelationshipOut, status_code=status.HTTP_201_CREATED)
async def create_question_relationship(
    question_id: uuid.UUID,
    req: QuestionRelationshipCreate,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> QuestionRelationshipOut:
    """Link two questions as variants, near-duplicates, or prerequisite dependencies."""
    tenant_id = _get_tenant_id(user)
    rel = await QuestionService.create_relationship(
        db=db,
        source_id=question_id,
        tenant_id=tenant_id,
        user_id=uuid.UUID(user.id),
        data=req,
    )
    return QuestionRelationshipOut.model_validate(rel)


@router.post("/misconceptions", response_model=MisconceptionOut, status_code=status.HTTP_201_CREATED)
async def create_misconception(
    req: MisconceptionCreate,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> MisconceptionOut:
    """Create an approved misconception item mapped to a concept."""
    tenant_id = _get_tenant_id(user)
    misc = await QuestionService.create_misconception(db, tenant_id, req)
    return MisconceptionOut.model_validate(misc)


@router.get("/courses/{offering_id}/questions/coverage", response_model=CourseQuestionCoverageReport)
async def get_course_question_coverage(
    offering_id: uuid.UUID,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> CourseQuestionCoverageReport:
    """Coverage progress report tracking original exam questions vs syllabus mapping and approval."""
    tenant_id = _get_tenant_id(user)
    return await QuestionService.get_course_coverage(db, offering_id, tenant_id)


@router.get("/courses/{offering_id}/questions", response_model=List[QuestionOut])
async def list_course_questions(
    offering_id: uuid.UUID,
    user: UserProfile = Depends(require_teacher),
    db: AsyncSession = Depends(get_db),
) -> List[QuestionOut]:
    """List source-linked and authored question records for assigned-course review."""
    tenant_id = _get_tenant_id(user)
    await KnowledgeService.verify_teacher_access(
        db=db,
        offering_id=offering_id,
        tenant_id=tenant_id,
        user_id=uuid.UUID(user.id),
        is_admin=user.role in ["ADMIN", "SUPER_ADMIN"],
    )
    return await QuestionService.list_course_questions(db, offering_id, tenant_id)

