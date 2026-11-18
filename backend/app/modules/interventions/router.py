from __future__ import annotations
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.common.exceptions import AppException
from app.modules.rbac.dependencies import get_current_user, require_teacher, require_student
from app.modules.auth.schemas import UserProfile
from app.modules.auth.models import InstitutionMembership
from app.modules.interventions.models import Intervention, InterventionAssignment
from app.modules.knowledge.service import KnowledgeService
from app.modules.interventions.service import InterventionService
from app.modules.interventions.authoring import generate_draft, approve_draft
from app.modules.interventions.authoring_schemas import GenerateInterventionRequest, InterventionDraft, ApproveInterventionDraft
from app.modules.interventions.schemas import (
    InterventionCreate,
    InterventionOut,
    StudentInterventionViewOut,
    InterventionReportOut,
    StudentInterventionListOut,
    PrimerDraftRequest,
    PrimerDraftResponse,
)

router = APIRouter(prefix="/courses/{course_offering_id}/interventions", tags=["Targeted Interventions"])


def _get_tenant_id(user: UserProfile) -> uuid.UUID:
    if not user.institution_id:
        raise AppException(code="NO_TENANT_CONTEXT", message="Institution context required.", status_code=400)
    return uuid.UUID(user.institution_id)


@router.post("/generate-draft", response_model=InterventionDraft)
async def generate_intervention_draft(
    course_offering_id: uuid.UUID,
    req: GenerateInterventionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(require_teacher),
):
    tenant_id = _get_tenant_id(current_user)
    await InterventionService.verify_teacher_course_access(db, tenant_id, course_offering_id, current_user)
    return await generate_draft(db, tenant_id, course_offering_id, req)


@router.post("/approve-draft", response_model=InterventionOut, status_code=status.HTTP_201_CREATED)
async def approve_intervention_draft(
    course_offering_id: uuid.UUID,
    req: ApproveInterventionDraft,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(require_teacher),
):
    tenant_id = _get_tenant_id(current_user)
    await InterventionService.verify_teacher_course_access(db, tenant_id, course_offering_id, current_user)
    intervention = await approve_draft(db, tenant_id, course_offering_id, uuid.UUID(current_user.id), req)
    rows = await InterventionService.list_course_interventions(db, tenant_id, course_offering_id)
    return next(row for row in rows if row.id == intervention.id)


@router.post("/approve-existing", response_model=InterventionOut, status_code=status.HTTP_201_CREATED)
async def approve_existing_intervention(
    course_offering_id: uuid.UUID,
    req: InterventionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(require_teacher),
):
    tenant_id = _get_tenant_id(current_user)
    await InterventionService.verify_teacher_course_access(db, tenant_id, course_offering_id, current_user)
    req.require_primer_acknowledgment = True
    intervention = await InterventionService.create_intervention(
        db, tenant_id, course_offering_id, req, uuid.UUID(current_user.id), commit=False
    )
    await InterventionService.approve_and_publish_intervention(
        db, tenant_id, course_offering_id, intervention.id, uuid.UUID(current_user.id)
    )
    rows = await InterventionService.list_course_interventions(db, tenant_id, course_offering_id)
    return next(row for row in rows if row.id == intervention.id)


@router.post("/draft-primer", response_model=PrimerDraftResponse)
async def draft_intervention_primer(
    course_offering_id: uuid.UUID,
    req: PrimerDraftRequest,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(require_teacher),
) -> PrimerDraftResponse:
    """
    Draft an evidence outline from concept definitions, doubts and misconceptions.
    Use generate-draft for an AI-written guide and matched quizzes.
    """
    tenant_id = _get_tenant_id(current_user)
    await InterventionService.verify_teacher_course_access(
        db, tenant_id, course_offering_id, current_user
    )
    return await InterventionService.generate_intervention_primer_draft(
        db=db,
        tenant_id=tenant_id,
        course_offering_id=course_offering_id,
        req=req,
    )


@router.get("", response_model=List[InterventionOut])
async def list_interventions(
    course_offering_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """List all interventions created for this course offering."""
    tenant_id = _get_tenant_id(current_user)
    await InterventionService.verify_teacher_course_access(
        db, tenant_id, course_offering_id, current_user
    )
    return await InterventionService.list_course_interventions(
        db, tenant_id, course_offering_id
    )


@router.post("", response_model=InterventionOut, status_code=status.HTTP_201_CREATED)
async def create_intervention(
    course_offering_id: uuid.UUID,
    req: InterventionCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """
    Teacher creates a new targeted intervention.
    Enforces that Phase A and Phase C question sets are strictly disjoint.
    """
    tenant_id = _get_tenant_id(current_user)
    await InterventionService.verify_teacher_course_access(
        db, tenant_id, course_offering_id, current_user
    )
    intervention = await InterventionService.create_intervention(
        db=db,
        tenant_id=tenant_id,
        course_offering_id=course_offering_id,
        req=req,
        user_id=uuid.UUID(current_user.id),
    )
    interventions = await InterventionService.list_course_interventions(
        db, tenant_id, course_offering_id
    )
    created = next(i for i in interventions if i.id == intervention.id)
    return created


@router.post("/{intervention_id}/publish", response_model=InterventionOut)
async def publish_intervention(
    course_offering_id: uuid.UUID,
    intervention_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """Teacher approves and activates an intervention. AI cannot autonomously publish."""
    tenant_id = _get_tenant_id(current_user)
    await InterventionService.verify_teacher_course_access(
        db, tenant_id, course_offering_id, current_user
    )
    intervention = await InterventionService.approve_and_publish_intervention(
        db=db,
        tenant_id=tenant_id,
        course_offering_id=course_offering_id,
        intervention_id=intervention_id,
        user_id=uuid.UUID(current_user.id),
    )
    interventions = await InterventionService.list_course_interventions(
        db, tenant_id, course_offering_id
    )
    return next(i for i in interventions if i.id == intervention.id)


@router.get("/{intervention_id}/report", response_model=InterventionReportOut)
async def get_intervention_report(
    course_offering_id: uuid.UUID,
    intervention_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """
    Matched pre/post outcome report.
    Only evaluates observed score change for students who completed both Phase A and Phase C.
    """
    tenant_id = _get_tenant_id(current_user)
    await InterventionService.verify_teacher_course_access(
        db, tenant_id, course_offering_id, current_user
    )
    return await InterventionService.get_intervention_report(
        db, tenant_id, course_offering_id, intervention_id
    )


@router.get("/{intervention_id}/student-view", response_model=StudentInterventionViewOut)
async def get_student_intervention_view(
    course_offering_id: uuid.UUID,
    intervention_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(require_student),
):
    """
    Student view of an assigned intervention.
    Enforces sequential phase gating:
    - Phase B locked until Phase A is submitted.
    - Phase C locked until Phase B practice completion rule is met.
    """
    tenant_id = _get_tenant_id(current_user)
    user_uuid = uuid.UUID(current_user.id)
    mem_stmt = select(InstitutionMembership).where(
        InstitutionMembership.user_id == user_uuid,
        InstitutionMembership.institution_id == tenant_id,
        InstitutionMembership.membership_status == "active",
    )
    mem = (await db.execute(mem_stmt)).scalars().first()
    if not mem:
        raise AppException(status_code=403, code="NOT_A_MEMBER", message="Active membership required.")

    return await InterventionService.get_student_intervention_view(
        db=db,
        tenant_id=tenant_id,
        course_offering_id=course_offering_id,
        intervention_id=intervention_id,
        student_membership_id=mem.id,
    )


@router.post("/{intervention_id}/acknowledge-study-guide", response_model=StudentInterventionViewOut)
async def acknowledge_study_guide(
    course_offering_id: uuid.UUID,
    intervention_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(require_student),
):
    """Record a student's acknowledgment; this does not assert comprehension."""
    from datetime import datetime, timezone

    tenant_id = _get_tenant_id(current_user)
    await KnowledgeService.verify_student_access(
        db=db, offering_id=course_offering_id, tenant_id=tenant_id, user_id=uuid.UUID(current_user.id)
    )
    membership = (await db.execute(select(InstitutionMembership).where(
        InstitutionMembership.user_id == uuid.UUID(current_user.id),
        InstitutionMembership.institution_id == tenant_id,
        InstitutionMembership.membership_status == "active",
    ))).scalars().first()
    if not membership:
        raise AppException(status_code=403, code="NOT_A_MEMBER", message="Active membership required.")
    view = await InterventionService.get_student_intervention_view(
        db, tenant_id, course_offering_id, intervention_id, membership.id
    )
    if not view.phase_b_unlocked:
        raise AppException(status_code=403, code="STUDY_GUIDE_LOCKED", message="Submit the baseline before reviewing the study guide.")
    if not view.phase_b_primer_content:
        raise AppException(status_code=400, code="STUDY_GUIDE_REQUIRED", message="No study guide is attached.")
    assignment = (await db.execute(select(InterventionAssignment).where(
        InterventionAssignment.intervention_id == intervention_id,
        InterventionAssignment.student_membership_id == membership.id,
        InterventionAssignment.institution_id == tenant_id,
    ))).scalars().one()
    if assignment.phase_b_primer_acknowledged_at is None:
        assignment.phase_b_primer_acknowledged_at = datetime.now(timezone.utc)
        await db.commit()
    return await InterventionService.get_student_intervention_view(
        db, tenant_id, course_offering_id, intervention_id, membership.id
    )


@router.get("/student", response_model=List[StudentInterventionListOut])
async def list_student_interventions(
    course_offering_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(require_student),
):
    """List only published interventions assigned to the authenticated enrolled student."""
    tenant_id = _get_tenant_id(current_user)
    student_id = uuid.UUID(current_user.id)
    await KnowledgeService.verify_student_access(
        db=db, offering_id=course_offering_id, tenant_id=tenant_id, user_id=student_id
    )
    membership_stmt = select(InstitutionMembership).where(
        InstitutionMembership.user_id == student_id,
        InstitutionMembership.institution_id == tenant_id,
        InstitutionMembership.membership_status == "active",
    )
    membership = (await db.execute(membership_stmt)).scalars().first()
    if not membership:
        raise AppException(status_code=403, code="NOT_A_MEMBER", message="Active membership required.")

    stmt = (
        select(InterventionAssignment.intervention_id)
        .join(Intervention, Intervention.id == InterventionAssignment.intervention_id)
        .where(
            Intervention.institution_id == tenant_id,
            Intervention.course_offering_id == course_offering_id,
            Intervention.status.in_(["active", "published"]),
            InterventionAssignment.student_membership_id == membership.id,
        )
    )
    intervention_ids = (await db.execute(stmt)).scalars().all()
    results = []
    for intervention_id in intervention_ids:
        view = await InterventionService.get_student_intervention_view(
            db=db, tenant_id=tenant_id, course_offering_id=course_offering_id,
            intervention_id=intervention_id, student_membership_id=membership.id,
        )
        results.append(StudentInterventionListOut(**view.model_dump(), course_offering_id=course_offering_id))
    return results

