from __future__ import annotations
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.common.exceptions import AppException
from app.modules.rbac.dependencies import (
    get_current_user,
    require_teacher,
    require_institution_admin,
)
from app.modules.auth.schemas import UserProfile
from app.modules.doubts.service import DoubtService
from app.modules.doubts.schemas import (
    DoubtCreate,
    DoubtOut,
    DoubtAnswerCreate,
    DoubtAnswerOut,
    DoubtCommentCreate,
    DoubtCommentOut,
    DoubtFlagCreate,
    DoubtFlagOut,
    DoubtUnmaskRequest,
    DoubtUnmaskOut,
    MyDoubtStatsOut,
)

router = APIRouter(tags=["Academic Doubts & Community Feed"])


def _get_tenant_id(user: UserProfile) -> uuid.UUID:
    if not user.institution_id:
        raise AppException(
            code="NO_TENANT_CONTEXT",
            message="Institution context required.",
            status_code=400,
        )
    return uuid.UUID(user.institution_id)


def _get_user_role(user: UserProfile) -> str:
    return user.role or "STUDENT"


# --- Doubt Feed & CRUD ---

@router.get("/doubts", response_model=List[DoubtOut])
async def list_doubts(
    course_offering_id: Optional[uuid.UUID] = Query(None),
    concept_id: Optional[uuid.UUID] = Query(None),
    syllabus_node_id: Optional[uuid.UUID] = Query(None),
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """
    List campus and course doubt threads respecting peer-anonymity safeguards.
    """
    tenant_id = _get_tenant_id(current_user)
    role = _get_user_role(current_user)
    return await DoubtService.list_doubts(
        db=db,
        tenant_id=tenant_id,
        caller_user_id=uuid.UUID(current_user.id),
        caller_role=role,
        course_offering_id=course_offering_id,
        concept_id=concept_id,
        syllabus_node_id=syllabus_node_id,
    )


@router.post("/doubts", response_model=DoubtOut, status_code=status.HTTP_201_CREATED)
async def create_doubt(
    req: DoubtCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """
    Post a new academic doubt.
    If is_anonymous_to_peers is True, the author's identity is concealed from peers,
    while remaining securely recorded in backend audit storage for moderation.
    """
    tenant_id = _get_tenant_id(current_user)
    role = _get_user_role(current_user)
    caller_id = uuid.UUID(current_user.id)

    doubt = await DoubtService.create_doubt(
        db=db,
        tenant_id=tenant_id,
        user_id=caller_id,
        req=req,
    )
    return await DoubtService.get_doubt_detail(
        db=db,
        tenant_id=tenant_id,
        doubt_id=doubt.id,
        caller_user_id=caller_id,
        caller_role=role,
    )


@router.post("/doubts/{doubt_id}/classify", response_model=DoubtOut)
async def classify_doubt(
    doubt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """
    Manually trigger or refresh semantic classification for a doubt thread.
    """
    tenant_id = _get_tenant_id(current_user)
    role = _get_user_role(current_user)
    from app.modules.doubts.semantic_service import DoubtSemanticService
    doubt = await DoubtSemanticService.classify_and_tag_doubt(db, doubt_id)
    if not doubt:
        raise AppException(status_code=404, code="DOUBT_NOT_FOUND", message="Doubt not found.")
    return await DoubtService.get_doubt_detail(
        db=db,
        tenant_id=tenant_id,
        doubt_id=doubt_id,
        caller_user_id=uuid.UUID(current_user.id),
        caller_role=role,
    )


# --- Moderation Queue & Flag Inspection (Admin Only) ---

@router.get("/doubts/moderation/flags", response_model=List[DoubtFlagOut])
async def list_moderation_flags(
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(require_institution_admin),
):
    """Admin moderation queue: list reported doubt content."""
    tenant_id = _get_tenant_id(current_user)
    return await DoubtService.list_flags(db, tenant_id, status_filter)


@router.post("/doubts/moderation/flags/{flag_id}/resolve", response_model=DoubtFlagOut)
async def resolve_moderation_flag(
    flag_id: uuid.UUID,
    new_status: str = Query(..., pattern="^(reviewed|actioned|dismissed)$"),
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(require_institution_admin),
):
    """Admin resolves a moderation report."""
    tenant_id = _get_tenant_id(current_user)
    return await DoubtService.resolve_flag(
        db=db,
        tenant_id=tenant_id,
        flag_id=flag_id,
        user_id=uuid.UUID(current_user.id),
        new_status=new_status,
    )


# --- Personal Activity & Influence Stats ---

@router.get("/doubts/me/stats", response_model=MyDoubtStatsOut)
async def get_my_doubt_stats(
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """Return real doubt/answer counts and influence metrics for the authenticated user."""
    tenant_id = _get_tenant_id(current_user)
    return await DoubtService.get_my_stats(
        db=db,
        tenant_id=tenant_id,
        user_id=uuid.UUID(current_user.id),
    )


# --- Doubt Detail, Responses, Comments, Votes, and Flags ---

@router.get("/doubts/{doubt_id}", response_model=DoubtOut)
async def get_doubt(
    doubt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """
    Retrieve single doubt thread with verified answers and discussion.
    Peer-anonymity masking is applied unless requester is the author.
    """
    tenant_id = _get_tenant_id(current_user)
    role = _get_user_role(current_user)
    return await DoubtService.get_doubt_detail(
        db=db,
        tenant_id=tenant_id,
        doubt_id=doubt_id,
        caller_user_id=uuid.UUID(current_user.id),
        caller_role=role,
    )


@router.post("/doubts/{doubt_id}/answers", response_model=DoubtAnswerOut, status_code=status.HTTP_201_CREATED)
async def add_doubt_answer(
    doubt_id: uuid.UUID,
    req: DoubtAnswerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """Submit a peer or teacher answer to a doubt."""
    tenant_id = _get_tenant_id(current_user)
    role = _get_user_role(current_user)
    return await DoubtService.add_answer(
        db=db,
        tenant_id=tenant_id,
        doubt_id=doubt_id,
        user_id=uuid.UUID(current_user.id),
        req=req,
        caller_role=role,
    )


@router.post("/doubts/{doubt_id}/comments", response_model=DoubtCommentOut, status_code=status.HTTP_201_CREATED)
async def add_doubt_comment(
    doubt_id: uuid.UUID,
    req: DoubtCommentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """Add a lightweight discussion comment on a doubt thread or answer."""
    tenant_id = _get_tenant_id(current_user)
    role = _get_user_role(current_user)
    return await DoubtService.add_comment(
        db=db,
        tenant_id=tenant_id,
        doubt_id=doubt_id,
        user_id=uuid.UUID(current_user.id),
        req=req,
        caller_role=role,
    )


@router.post("/doubts/{doubt_id}/vote")
async def vote_doubt(
    doubt_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """Upvote an academic doubt thread."""
    tenant_id = _get_tenant_id(current_user)
    upvote_count = await DoubtService.vote_doubt(
        db=db,
        tenant_id=tenant_id,
        doubt_id=doubt_id,
        user_id=uuid.UUID(current_user.id),
    )
    return {"status": "ok", "doubt_id": doubt_id, "upvote_count": upvote_count}


@router.post("/doubts/answers/{answer_id}/thank")
@router.post("/doubt-answers/{answer_id}/thank")
async def thank_doubt_answer(
    answer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """Thank an answer author at most once per user."""
    tenant_id = _get_tenant_id(current_user)
    res = await DoubtService.thank_answer(
        db=db,
        tenant_id=tenant_id,
        answer_id=answer_id,
        user_id=uuid.UUID(current_user.id),
    )
    return {"status": "ok", **res}


@router.post("/doubts/{doubt_id}/flag", response_model=DoubtFlagOut, status_code=status.HTTP_201_CREATED)
async def flag_doubt(
    doubt_id: uuid.UUID,
    req: DoubtFlagCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """Report a doubt for community guideline violation or academic policy issues."""
    tenant_id = _get_tenant_id(current_user)
    return await DoubtService.flag_doubt(
        db=db,
        tenant_id=tenant_id,
        doubt_id=doubt_id,
        user_id=uuid.UUID(current_user.id),
        req=req,
    )


# --- Teacher Endorsement / Answer Verification ---

@router.post("/doubts/answers/{answer_id}/verify", response_model=DoubtAnswerOut)
@router.post("/doubt-answers/{answer_id}/verify", response_model=DoubtAnswerOut)
async def verify_doubt_answer(
    answer_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(require_teacher),
):
    """
    Teacher verifies an answer as academically correct.
    Marks answer with verified endorsement and resolves parent doubt.
    """
    tenant_id = _get_tenant_id(current_user)
    return await DoubtService.verify_answer(
        db=db,
        tenant_id=tenant_id,
        answer_id=answer_id,
        user_id=uuid.UUID(current_user.id),
        caller_role="TEACHER",
    )


# --- Audited Anonymous Identity Disclosure (Unmasking) ---

@router.post("/doubts/{doubt_id}/unmask", response_model=DoubtUnmaskOut)
async def unmask_doubt_author(
    doubt_id: uuid.UUID,
    req: DoubtUnmaskRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(require_institution_admin),
):
    """
    Admin audited unmasking of an anonymous doubt author for investigation.
    Requires justification reason_code and reason_text.
    Records immutable AuditEvent and DoubtIdentityDisclosureEvent.
    """
    tenant_id = _get_tenant_id(current_user)
    role = _get_user_role(current_user)
    return await DoubtService.unmask_anonymous_author(
        db=db,
        tenant_id=tenant_id,
        doubt_id=doubt_id,
        actor_user_id=uuid.UUID(current_user.id),
        actor_role=role,
        req=req,
    )
