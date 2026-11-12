from __future__ import annotations
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.common.exceptions import AppException
from app.modules.rbac.dependencies import get_current_user
from app.modules.auth.schemas import UserProfile
from app.modules.analytics.service import AnalyticsService
from app.modules.analytics.schemas import (
    CourseAnalyticsPolicyUpdate,
    CourseAnalyticsPolicyOut,
    CohortConceptAnalyticsOut,
    ConceptAnalyticsDetailOut,
    MisconceptionReportOut,
    ConceptMasteryPolicyCreate,
    ConceptMasteryPolicyOut,
)

router = APIRouter(prefix="/courses/{course_offering_id}/analytics", tags=["Concept Analytics & Teacher Dashboard"])


def _get_tenant_id(user: UserProfile) -> uuid.UUID:
    if not user.institution_id:
        raise AppException(code="NO_TENANT_CONTEXT", message="Institution context required.", status_code=400)
    return uuid.UUID(user.institution_id)


@router.get("/policies", response_model=CourseAnalyticsPolicyOut)
async def get_analytics_policy(
    course_offering_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """Retrieve active analytics policy (thresholds and attempt selection rules) for this course offering."""
    tenant_id = _get_tenant_id(current_user)
    await AnalyticsService.verify_teacher_course_access(
        db, tenant_id, course_offering_id, current_user
    )
    policy = await AnalyticsService.get_or_resolve_policy(
        db, tenant_id, course_offering_id
    )
    return CourseAnalyticsPolicyOut(
        id=policy.id,
        institution_id=policy.institution_id,
        course_offering_id=policy.course_offering_id,
        min_distinct_questions=policy.min_distinct_questions,
        weakness_accuracy_threshold=float(policy.weakness_accuracy_threshold),
        diagnostic_attempt_policy=policy.diagnostic_attempt_policy,
        is_active=policy.is_active,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


@router.put("/policies", response_model=CourseAnalyticsPolicyOut)
async def update_analytics_policy(
    course_offering_id: uuid.UUID,
    req: CourseAnalyticsPolicyUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """Configure course-specific analytics thresholds (min distinct questions, weakness ceiling)."""
    tenant_id = _get_tenant_id(current_user)
    await AnalyticsService.verify_teacher_course_access(
        db, tenant_id, course_offering_id, current_user
    )
    policy = await AnalyticsService.update_or_create_course_policy(
        db, tenant_id, course_offering_id, req, uuid.UUID(current_user.id)
    )
    return CourseAnalyticsPolicyOut(
        id=policy.id,
        institution_id=policy.institution_id,
        course_offering_id=policy.course_offering_id,
        min_distinct_questions=policy.min_distinct_questions,
        weakness_accuracy_threshold=float(policy.weakness_accuracy_threshold),
        diagnostic_attempt_policy=policy.diagnostic_attempt_policy,
        is_active=policy.is_active,
        created_at=policy.created_at,
        updated_at=policy.updated_at,
    )


@router.post("/runs", status_code=status.HTTP_201_CREATED)
async def trigger_analytics_run(
    course_offering_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """Manually trigger a full diagnostic analytics execution and snapshot regeneration."""
    tenant_id = _get_tenant_id(current_user)
    await AnalyticsService.verify_teacher_course_access(
        db, tenant_id, course_offering_id, current_user
    )
    run = await AnalyticsService.compute_and_persist_analytics_run(
        db, tenant_id, course_offering_id, user_id=uuid.UUID(current_user.id)
    )
    return {"message": "Analytics run completed successfully.", "run_id": str(run.id), "status": run.status}


@router.get("/concepts", response_model=List[CohortConceptAnalyticsOut])
async def get_cohort_concept_analytics(
    course_offering_id: uuid.UUID,
    refresh: bool = Query(False, description="Force recompute analytics snapshot"),
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """
    Get cohort concept performance summary for all concepts in this course.
    Returns Cohort Mean Accuracy, Cohort Pooled Accuracy, and confirmed weakness counts.
    """
    tenant_id = _get_tenant_id(current_user)
    await AnalyticsService.verify_teacher_course_access(
        db, tenant_id, course_offering_id, current_user
    )
    return await AnalyticsService.get_cohort_concept_analytics(
        db, tenant_id, course_offering_id, refresh=refresh
    )


@router.get("/concepts/{concept_id}", response_model=ConceptAnalyticsDetailOut)
async def get_concept_analytics_detail(
    course_offering_id: uuid.UUID,
    concept_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """
    Deep drilldown into a specific concept: inspect all enrolled students, their diagnostic status,
    distinct question counts, and supporting question attempts.
    """
    tenant_id = _get_tenant_id(current_user)
    await AnalyticsService.verify_teacher_course_access(
        db, tenant_id, course_offering_id, current_user
    )
    return await AnalyticsService.get_concept_analytics_detail(
        db, tenant_id, course_offering_id, concept_id
    )


@router.get("/misconceptions", response_model=MisconceptionReportOut)
async def get_misconception_report(
    course_offering_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """Misconception tag frequency report across student responses in this course offering."""
    tenant_id = _get_tenant_id(current_user)
    await AnalyticsService.verify_teacher_course_access(
        db, tenant_id, course_offering_id, current_user
    )
    return await AnalyticsService.get_misconception_report(
        db, tenant_id, course_offering_id
    )


@router.get("/mastery/policies", response_model=List[ConceptMasteryPolicyOut])
async def list_mastery_policies(
    course_offering_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """List teacher-configured concept mastery policies."""
    tenant_id = _get_tenant_id(current_user)
    await AnalyticsService.verify_teacher_course_access(
        db, tenant_id, course_offering_id, current_user
    )
    return await AnalyticsService.list_mastery_policies(
        db, tenant_id, course_offering_id
    )


@router.post("/mastery/policies", response_model=ConceptMasteryPolicyOut, status_code=status.HTTP_201_CREATED)
async def create_mastery_policy(
    course_offering_id: uuid.UUID,
    req: ConceptMasteryPolicyCreate,
    db: AsyncSession = Depends(get_db),
    current_user: UserProfile = Depends(get_current_user),
):
    """Create a new concept mastery policy."""
    tenant_id = _get_tenant_id(current_user)
    await AnalyticsService.verify_teacher_course_access(
        db, tenant_id, course_offering_id, current_user
    )
    return await AnalyticsService.create_mastery_policy(
        db, tenant_id, course_offering_id, req, uuid.UUID(current_user.id)
    )
