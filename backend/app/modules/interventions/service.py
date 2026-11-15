from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Set
from sqlalchemy import select, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.exceptions import AppException
from app.modules.academics.models import CourseOfferingFaculty, CourseOfferingEnrolment
from app.modules.auth.models import User, InstitutionMembership
from app.modules.knowledge.models import Concept
from app.modules.assessments.models import (
    Assessment,
    AssessmentVersion,
    AssessmentItem,
    AssessmentAttempt,
    AssessmentResponse,
)
from app.modules.interventions.models import (
    Intervention,
    InterventionConcept,
    InterventionAssignment,
)
from app.modules.interventions.schemas import (
    InterventionCreate,
    InterventionOut,
    InterventionConceptOut,
    InterventionAssignmentOut,
    StudentInterventionViewOut,
    InterventionReportOut,
    PrimerDraftRequest,
    PrimerDraftResponse,
)
from app.modules.analytics.models import AnalyticsRun, StudentConceptEvidenceSnapshot
from app.modules.analytics.service import AnalyticsService


class InterventionService:

    @staticmethod
    async def verify_teacher_course_access(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        course_offering_id: uuid.UUID,
        user: Any,
    ) -> None:
        """Verify user is Super Admin, Institution Admin, or assigned Faculty for this course offering."""
        role = getattr(user, "role", "").upper()
        if role == "SUPER_ADMIN" or getattr(user, "is_super_admin", False):
            return
        if role == "ADMIN":
            return
        if role == "TEACHER":
            user_uuid = uuid.UUID(str(user.id))
            stmt = (
                select(CourseOfferingFaculty)
                .join(InstitutionMembership, CourseOfferingFaculty.institution_membership_id == InstitutionMembership.id)
                .where(
                    CourseOfferingFaculty.course_offering_id == course_offering_id,
                    CourseOfferingFaculty.institution_id == tenant_id,
                    InstitutionMembership.user_id == user_uuid,
                    CourseOfferingFaculty.status == "active",
                )
            )
            res = await db.execute(stmt)
            if res.scalars().first():
                return

        raise AppException(
            status_code=403,
            code="UNAUTHORIZED_COURSE_ACCESS",
            message="You do not have permission to manage interventions for this course offering.",
        )

    @staticmethod
    async def _get_assessment_question_identities(
        db: AsyncSession,
        assessment_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> Set[uuid.UUID]:
        """Collect all question_version_id and activity_version_id used across items in the assessment."""
        stmt = (
            select(AssessmentItem)
            .join(AssessmentVersion, AssessmentItem.assessment_version_id == AssessmentVersion.id)
            .where(
                AssessmentVersion.assessment_id == assessment_id,
                AssessmentItem.institution_id == tenant_id,
            )
        )
        items = (await db.execute(stmt)).scalars().all()
        ids: Set[uuid.UUID] = set()
        for item in items:
            if item.question_version_id:
                ids.add(item.question_version_id)
            if item.activity_version_id:
                ids.add(item.activity_version_id)
        return ids

    @staticmethod
    async def _get_assessment_profile(
        db: AsyncSession,
        assessment_id: uuid.UUID,
        tenant_id: uuid.UUID,
        course_offering_id: uuid.UUID,
        expected_type: str,
    ) -> Dict[str, Any]:
        stmt = (
            select(Assessment)
            .options(
                selectinload(Assessment.versions)
                .selectinload(AssessmentVersion.items)
                .selectinload(AssessmentItem.concept_allocations),
                selectinload(Assessment.versions)
                .selectinload(AssessmentVersion.items)
                .selectinload(AssessmentItem.question_version),
                selectinload(Assessment.versions)
                .selectinload(AssessmentVersion.items)
                .selectinload(AssessmentItem.activity_version),
            )
            .where(
                Assessment.id == assessment_id,
                Assessment.institution_id == tenant_id,
                Assessment.course_offering_id == course_offering_id,
                Assessment.status == "published",
                Assessment.assessment_type == expected_type,
            )
        )
        assessment = (await db.execute(stmt)).scalars().first()
        if not assessment:
            raise AppException(
                status_code=400,
                code="INVALID_INTERVENTION_ASSESSMENT",
                message=f"A published {expected_type.replace('_', ' ')} assessment for this course is required.",
            )
        version = next((candidate for candidate in assessment.versions if candidate.status == "published"), None)
        if not version or not version.items:
            raise AppException(status_code=400, code="EMPTY_INTERVENTION_ASSESSMENT", message="Intervention assessments must contain published questions.")
        concept_marks: Dict[uuid.UUID, float] = {}
        difficulty_counts: Dict[str, int] = {}
        cognitive_counts: Dict[str, int] = {}
        item_types: Dict[str, int] = {}
        total_marks = 0.0
        for item in version.items:
            total_marks += float(item.marks_available)
            for allocation in item.concept_allocations:
                concept_marks[allocation.concept_id] = concept_marks.get(allocation.concept_id, 0.0) + float(allocation.marks_available)
            question = item.question_version
            if question:
                difficulty_counts[question.difficulty_level] = difficulty_counts.get(question.difficulty_level, 0) + 1
                level = question.cognitive_level or "unclassified"
                cognitive_counts[level] = cognitive_counts.get(level, 0) + 1
                item_types[question.question_type] = item_types.get(question.question_type, 0) + 1
            elif item.activity_version:
                kind = item.activity_version.activity_type
                item_types[kind] = item_types.get(kind, 0) + 1
        return {
            "concept_marks": concept_marks,
            "difficulty_counts": difficulty_counts,
            "cognitive_counts": cognitive_counts,
            "item_types": item_types,
            "total_marks": round(total_marks, 2),
        }

    @staticmethod
    async def create_intervention(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        course_offering_id: uuid.UUID,
        req: InterventionCreate,
        user_id: uuid.UUID,
    ) -> Intervention:
        """
        Create a targeted intervention from concept analytics evidence.
        Enforces published phase types, target concept coverage, comparable mark/classification profiles,
        and disjoint Phase A and Phase C question sets.
        """
        if len(set(req.student_membership_ids)) != len(req.student_membership_ids):
            raise AppException(status_code=422, code="DUPLICATE_INTERVENTION_STUDENT", message="A student can only be assigned once per intervention.")
        concept_stmt = select(Concept.id).where(Concept.institution_id == tenant_id, Concept.id.in_(req.concept_ids))
        valid_concepts = set((await db.execute(concept_stmt)).scalars().all())
        if valid_concepts != set(req.concept_ids):
            raise AppException(status_code=400, code="INVALID_INTERVENTION_CONCEPT", message="Every targeted concept must belong to this institution.")

        # 1. Enforce that Phase A and Phase C are different assessments
        if req.phase_a_assessment_id == req.phase_c_assessment_id:
            raise AppException(
                status_code=400,
                code="IDENTICAL_PHASE_ASSESSMENTS",
                message="Phase A (baseline) and Phase C (post-test) must be distinct assessments.",
            )

        # 2. Enforce disjoint question sets between Phase A and Phase C
        phase_a_q_ids = await InterventionService._get_assessment_question_identities(
            db, req.phase_a_assessment_id, tenant_id
        )
        phase_c_q_ids = await InterventionService._get_assessment_question_identities(
            db, req.phase_c_assessment_id, tenant_id
        )
        overlap = phase_a_q_ids.intersection(phase_c_q_ids)
        if overlap:
            raise AppException(
                status_code=400,
                code="OVERLAPPING_INTERVENTION_QUESTIONS",
                message="Phase A and Phase C question sets must be strictly disjoint to ensure valid pre/post comparison.",
            )

        phase_a_profile = await InterventionService._get_assessment_profile(
            db, req.phase_a_assessment_id, tenant_id, course_offering_id, "intervention_baseline"
        )
        phase_b_profile = await InterventionService._get_assessment_profile(
            db, req.phase_b_practice_assessment_id, tenant_id, course_offering_id, "intervention_practice"
        )
        phase_c_profile = await InterventionService._get_assessment_profile(
            db, req.phase_c_assessment_id, tenant_id, course_offering_id, "intervention_post"
        )
        expected_concepts = set(req.concept_ids)
        for phase_name, profile in (("Phase A", phase_a_profile), ("Phase B", phase_b_profile), ("Phase C", phase_c_profile)):
            if set(profile["concept_marks"]) != expected_concepts:
                raise AppException(
                    status_code=400,
                    code="INTERVENTION_CONCEPT_COVERAGE_MISMATCH",
                    message=f"{phase_name} must map assessment marks to exactly the targeted intervention concepts.",
                )
        if phase_a_profile["concept_marks"] != phase_c_profile["concept_marks"]:
            raise AppException(status_code=400, code="INCOMPARABLE_INTERVENTION_MARKS", message="Phase A and Phase C marks must be equal for each targeted concept.")
        if phase_a_profile["total_marks"] != phase_c_profile["total_marks"]:
            raise AppException(status_code=400, code="INCOMPARABLE_INTERVENTION_TOTALS", message="Phase A and Phase C must have the same total marks.")
        if phase_a_profile["difficulty_counts"] != phase_c_profile["difficulty_counts"]:
            raise AppException(status_code=400, code="INCOMPARABLE_INTERVENTION_DIFFICULTY", message="Phase A and Phase C question difficulty classifications must match.")
        if phase_a_profile["cognitive_counts"] != phase_c_profile["cognitive_counts"]:
            raise AppException(status_code=400, code="INCOMPARABLE_INTERVENTION_COGNITIVE_DEMAND", message="Phase A and Phase C cognitive-demand classifications must match.")
        if phase_a_profile["item_types"] != phase_c_profile["item_types"]:
            raise AppException(status_code=400, code="INCOMPARABLE_INTERVENTION_QUESTION_TYPES", message="Phase A and Phase C question classifications must match.")

        enrolment_stmt = select(CourseOfferingEnrolment.institution_membership_id).where(
            CourseOfferingEnrolment.institution_id == tenant_id,
            CourseOfferingEnrolment.course_offering_id == course_offering_id,
            CourseOfferingEnrolment.enrolment_status == "active",
            CourseOfferingEnrolment.institution_membership_id.in_(req.student_membership_ids),
        )
        enrolled_ids = set((await db.execute(enrolment_stmt)).scalars().all())
        if enrolled_ids != set(req.student_membership_ids):
            raise AppException(status_code=400, code="INVALID_INTERVENTION_STUDENTS", message="Every selected student must be actively enrolled in this course offering.")

        latest_run = await AnalyticsService.compute_and_persist_analytics_run(
            db, tenant_id, course_offering_id, user_id=user_id
        )
        evidence_stmt = select(StudentConceptEvidenceSnapshot.student_membership_id).where(
            StudentConceptEvidenceSnapshot.analytics_run_id == latest_run.id,
            StudentConceptEvidenceSnapshot.course_offering_id == course_offering_id,
            StudentConceptEvidenceSnapshot.concept_id.in_(req.concept_ids),
            StudentConceptEvidenceSnapshot.student_membership_id.in_(req.student_membership_ids),
            StudentConceptEvidenceSnapshot.diagnostic_status == "confirmed_weakness",
        ).distinct()
        confirmed_ids = set((await db.execute(evidence_stmt)).scalars().all())
        if confirmed_ids != set(req.student_membership_ids):
            raise AppException(status_code=400, code="STUDENT_NOT_CONFIRMED_WEAK", message="Each selected student must have confirmed weakness evidence for at least one targeted concept in the latest analytics run.")

        # 3. Validate completion rule parameters
        if req.phase_b_completion_rule == "minimum_count" and not req.phase_b_required_count:
            raise AppException(
                status_code=422,
                code="MISSING_PHASE_B_REQUIRED_COUNT",
                message="phase_b_required_count is required when completion rule is 'minimum_count'.",
            )

        now = datetime.now(timezone.utc)
        intervention = Intervention(
            institution_id=tenant_id,
            course_offering_id=course_offering_id,
            title=req.title,
            description=req.description,
            status="draft",
            created_by_user_id=user_id,
            phase_a_assessment_id=req.phase_a_assessment_id,
            phase_b_primer_content=req.phase_b_primer_content,
            phase_b_practice_assessment_id=req.phase_b_practice_assessment_id,
            phase_b_completion_rule=req.phase_b_completion_rule,
            phase_b_required_count=req.phase_b_required_count,
            phase_c_assessment_id=req.phase_c_assessment_id,
            assignment_starts_at=req.assignment_starts_at or now,
            assignment_ends_at=req.assignment_ends_at,
        )
        db.add(intervention)
        await db.flush()

        # 4. Attach targeted concepts
        for c_id in req.concept_ids:
            db.add(
                InterventionConcept(
                    institution_id=tenant_id,
                    intervention_id=intervention.id,
                    concept_id=c_id,
                )
            )

        # 5. Assign targeted students
        for s_id in req.student_membership_ids:
            db.add(
                InterventionAssignment(
                    institution_id=tenant_id,
                    intervention_id=intervention.id,
                    student_membership_id=s_id,
                    target_evidence_status="confirmed_weakness",
                    assignment_status="assigned",
                    assigned_at=now,
                )
            )

        await db.commit()
        await db.refresh(intervention)
        return intervention

    @staticmethod
    async def approve_and_publish_intervention(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        course_offering_id: uuid.UUID,
        intervention_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Intervention:
        """Teacher approves and activates an intervention. AI cannot autonomously publish."""
        stmt = (
            select(Intervention)
            .options(
                selectinload(Intervention.concepts).selectinload(InterventionConcept.concept),
                selectinload(Intervention.assignments),
            )
            .where(
                Intervention.id == intervention_id,
                Intervention.course_offering_id == course_offering_id,
                Intervention.institution_id == tenant_id,
            )
        )
        res = await db.execute(stmt)
        intervention = res.scalars().first()
        if not intervention:
            raise AppException(status_code=404, code="INTERVENTION_NOT_FOUND", message="Intervention not found.")

        now = datetime.now(timezone.utc)
        intervention.status = "active"
        intervention.approved_by_user_id = user_id
        intervention.approved_at = now
        intervention.published_at = now
        intervention.updated_at = now

        await db.commit()
        await db.refresh(intervention)
        return intervention

    @staticmethod
    async def sync_student_progress(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        intervention_id: uuid.UUID,
        student_membership_id: uuid.UUID,
    ) -> InterventionAssignment:
        """
        Evaluate student attempt records for Phase A, B, and C assessments,
        and update the InterventionAssignment status and gating.
        """
        stmt = (
            select(InterventionAssignment)
            .where(
                InterventionAssignment.intervention_id == intervention_id,
                InterventionAssignment.student_membership_id == student_membership_id,
                InterventionAssignment.institution_id == tenant_id,
            )
        )
        assignment = (await db.execute(stmt)).scalars().first()
        if not assignment:
            raise AppException(
                status_code=404,
                code="INTERVENTION_ASSIGNMENT_NOT_FOUND",
                message="Student is not assigned to this intervention.",
            )

        intv_stmt = select(Intervention).where(Intervention.id == intervention_id)
        intervention = (await db.execute(intv_stmt)).scalars().first()
        if not intervention:
            raise AppException(status_code=404, code="INTERVENTION_NOT_FOUND", message="Intervention not found.")

        # 1. Check Phase A Attempt (Must be submitted & scored)
        if intervention.phase_a_assessment_id:
            a_stmt = (
                select(AssessmentAttempt)
                .join(AssessmentVersion, AssessmentAttempt.assessment_version_id == AssessmentVersion.id)
                .where(
                    AssessmentVersion.assessment_id == intervention.phase_a_assessment_id,
                    AssessmentAttempt.student_membership_id == student_membership_id,
                    AssessmentAttempt.status == "submitted",
                    AssessmentAttempt.is_valid == True,
                )
                .order_by(AssessmentAttempt.submitted_at.asc())
            )
            a_att = (await db.execute(a_stmt)).scalars().first()
            if a_att:
                assignment.phase_a_attempt_id = a_att.id
                assignment.phase_a_completed_at = a_att.submitted_at
                assignment.phase_a_score = float(a_att.marks_awarded or 0.0)
                if assignment.assignment_status == "assigned":
                    assignment.assignment_status = "phase_a_completed"

        # 2. Check Phase B Practice (Only if Phase A is completed!)
        if assignment.phase_a_completed_at and intervention.phase_b_practice_assessment_id:
            b_stmt = (
                select(AssessmentAttempt)
                .join(AssessmentVersion, AssessmentAttempt.assessment_version_id == AssessmentVersion.id)
                .options(selectinload(AssessmentAttempt.responses))
                .where(
                    AssessmentVersion.assessment_id == intervention.phase_b_practice_assessment_id,
                    AssessmentAttempt.student_membership_id == student_membership_id,
                    AssessmentAttempt.status == "submitted",
                    AssessmentAttempt.is_valid == True,
                )
                .order_by(AssessmentAttempt.submitted_at.asc())
            )
            b_att = (await db.execute(b_stmt)).scalars().first()
            if b_att:
                # Count distinct answered items
                answered_items = {
                    r.assessment_item_id
                    for r in b_att.responses
                    if r.response_state in ("answered", "marked_for_review")
                }
                assignment.phase_b_items_completed_count = len(answered_items)

                # Check completion rule
                rule = intervention.phase_b_completion_rule
                is_completed = False

                # Fetch Phase B items and enforce the configured mandatory-item rule.
                items_stmt = (
                    select(AssessmentItem)
                    .join(AssessmentVersion, AssessmentItem.assessment_version_id == AssessmentVersion.id)
                    .where(AssessmentVersion.assessment_id == intervention.phase_b_practice_assessment_id)
                )
                b_items = (await db.execute(items_stmt)).scalars().all()
                required_items = [i for i in b_items if i.is_required]

                if rule == "all_required_items":
                    required_ids = {i.id for i in required_items}
                    is_completed = required_ids.issubset(answered_items)
                elif rule == "designated_core_items":
                    core_ids = {i.id for i in required_items}
                    is_completed = core_ids.issubset(answered_items)
                elif rule == "minimum_count":
                    k = intervention.phase_b_required_count or 1
                    is_completed = len(answered_items) >= k

                if is_completed:
                    assignment.phase_b_completed_at = b_att.submitted_at
                    if assignment.assignment_status in ("phase_a_completed", "phase_b_in_progress"):
                        assignment.assignment_status = "phase_b_completed"

        # 3. Check Phase C Post Assessment (Only if Phase B is completed!)
        if assignment.phase_b_completed_at and intervention.phase_c_assessment_id:
            c_stmt = (
                select(AssessmentAttempt)
                .join(AssessmentVersion, AssessmentAttempt.assessment_version_id == AssessmentVersion.id)
                .where(
                    AssessmentVersion.assessment_id == intervention.phase_c_assessment_id,
                    AssessmentAttempt.student_membership_id == student_membership_id,
                    AssessmentAttempt.status == "submitted",
                    AssessmentAttempt.is_valid == True,
                )
                .order_by(AssessmentAttempt.submitted_at.asc())
            )
            c_att = (await db.execute(c_stmt)).scalars().first()
            if c_att:
                assignment.phase_c_attempt_id = c_att.id
                assignment.phase_c_completed_at = c_att.submitted_at
                assignment.phase_c_score = float(c_att.marks_awarded or 0.0)
                assignment.assignment_status = "completed"

                # Calculate observed change (Phase C score - Phase A score)
                if assignment.phase_a_score is not None and assignment.phase_c_score is not None:
                    diff = round(assignment.phase_c_score - assignment.phase_a_score, 2)
                    assignment.observed_score_change = diff
                    if diff > 0.0:
                        assignment.outcome_status = "improved"
                    elif diff == 0.0:
                        assignment.outcome_status = "unchanged"
                    else:
                        assignment.outcome_status = "declined"

        assignment.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(assignment)
        return assignment

    @staticmethod
    async def get_student_intervention_view(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        course_offering_id: uuid.UUID,
        intervention_id: uuid.UUID,
        student_membership_id: uuid.UUID,
    ) -> StudentInterventionViewOut:
        """
        Get student view of intervention with strictly enforced phase gating.
        Phase B is inaccessible until Phase A is submitted.
        Phase C is inaccessible until Phase B completion rule is satisfied.
        """
        # Sync latest progress
        assignment = await InterventionService.sync_student_progress(
            db, tenant_id, intervention_id, student_membership_id
        )

        intv_stmt = select(Intervention).where(Intervention.id == intervention_id)
        intervention = (await db.execute(intv_stmt)).scalars().first()

        # Gate Phase B
        phase_a_done = assignment.phase_a_completed_at is not None
        phase_b_unlocked = phase_a_done

        # Gate Phase C
        phase_b_done = assignment.phase_b_completed_at is not None
        phase_c_unlocked = phase_b_done

        # Determine current phase
        if not phase_a_done:
            current_phase = "phase_a"
        elif not phase_b_done:
            current_phase = "phase_b"
        elif assignment.phase_c_completed_at is None:
            current_phase = "phase_c"
        else:
            current_phase = "completed"

        rule_desc = {
            "all_required_items": "Submit all practice items attached to Phase B.",
            "designated_core_items": "Submit all designated core practice items.",
            "minimum_count": f"Submit at least {intervention.phase_b_required_count or 1} distinct practice items.",
        }.get(intervention.phase_b_completion_rule, "Submit required practice items.")

        return StudentInterventionViewOut(
            intervention_id=intervention.id,
            title=intervention.title,
            description=intervention.description,
            current_phase=current_phase,
            phase_a_unlocked=True,
            phase_a_completed=phase_a_done,
            phase_a_assessment_id=intervention.phase_a_assessment_id,
            phase_a_score=assignment.phase_a_score,
            phase_b_unlocked=phase_b_unlocked,
            phase_b_completed=phase_b_done,
            phase_b_primer_content=intervention.phase_b_primer_content if phase_b_unlocked else None,
            phase_b_practice_assessment_id=intervention.phase_b_practice_assessment_id if phase_b_unlocked else None,
            phase_b_items_completed=assignment.phase_b_items_completed_count,
            phase_b_rule_description=rule_desc,
            phase_c_unlocked=phase_c_unlocked,
            phase_c_completed=assignment.phase_c_completed_at is not None,
            phase_c_assessment_id=intervention.phase_c_assessment_id if phase_c_unlocked else None,
            phase_c_score=assignment.phase_c_score,
            observed_score_change=assignment.observed_score_change,
            outcome_status=assignment.outcome_status,
        )

    @staticmethod
    async def get_intervention_report(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        course_offering_id: uuid.UUID,
        intervention_id: uuid.UUID,
    ) -> InterventionReportOut:
        """
        Generate matched pre/post outcome report.
        Only counts students who have completed both Phase A and Phase C toward matched comparisons.
        """
        stmt = (
            select(Intervention)
            .options(
                selectinload(Intervention.assignments).selectinload(InterventionAssignment.student_membership),
            )
            .where(
                Intervention.id == intervention_id,
                Intervention.course_offering_id == course_offering_id,
                Intervention.institution_id == tenant_id,
            )
        )
        intervention = (await db.execute(stmt)).scalars().first()
        if not intervention:
            raise AppException(status_code=404, code="INTERVENTION_NOT_FOUND", message="Intervention not found.")

        # Sync all student assignments
        assignments_out: List[InterventionAssignmentOut] = []
        for ass in intervention.assignments:
            updated = await InterventionService.sync_student_progress(
                db, tenant_id, intervention_id, ass.student_membership_id
            )
            assignments_out.append(
                InterventionAssignmentOut(
                    id=updated.id,
                    intervention_id=updated.intervention_id,
                    student_membership_id=updated.student_membership_id,
                    target_evidence_status=updated.target_evidence_status,
                    assignment_status=updated.assignment_status,
                    phase_a_completed_at=updated.phase_a_completed_at,
                    phase_a_score=updated.phase_a_score,
                    phase_b_completed_at=updated.phase_b_completed_at,
                    phase_b_items_completed_count=updated.phase_b_items_completed_count,
                    phase_c_completed_at=updated.phase_c_completed_at,
                    phase_c_score=updated.phase_c_score,
                    observed_score_change=updated.observed_score_change,
                    outcome_status=updated.outcome_status,
                    assigned_at=updated.assigned_at,
                )
            )

        total_assigned = len(assignments_out)
        phase_a_completed = sum(1 for a in assignments_out if a.phase_a_completed_at is not None)
        phase_b_completed = sum(1 for a in assignments_out if a.phase_b_completed_at is not None)
        phase_c_completed = sum(1 for a in assignments_out if a.phase_c_completed_at is not None)

        # Matched comparison requires BOTH Phase A and Phase C
        matched_students = [
            a for a in assignments_out
            if a.phase_a_completed_at is not None and a.phase_c_completed_at is not None
        ]
        matched_count = len(matched_students)
        improved_count = sum(1 for a in matched_students if a.outcome_status == "improved")
        unchanged_count = sum(1 for a in matched_students if a.outcome_status == "unchanged")
        declined_count = sum(1 for a in matched_students if a.outcome_status == "declined")
        incomplete_count = total_assigned - matched_count

        avg_a = (
            round(sum(a.phase_a_score for a in matched_students) / matched_count, 2)
            if matched_count > 0
            else None
        )
        avg_c = (
            round(sum(a.phase_c_score for a in matched_students) / matched_count, 2)
            if matched_count > 0
            else None
        )
        avg_change = (
            round(sum(a.observed_score_change for a in matched_students) / matched_count, 2)
            if matched_count > 0
            else None
        )

        return InterventionReportOut(
            intervention_id=intervention.id,
            title=intervention.title,
            status=intervention.status,
            total_assigned_count=total_assigned,
            phase_a_completed_count=phase_a_completed,
            phase_b_completed_count=phase_b_completed,
            phase_c_completed_count=phase_c_completed,
            matched_completed_count=matched_count,
            improved_count=improved_count,
            unchanged_count=unchanged_count,
            declined_count=declined_count,
            incomplete_count=incomplete_count,
            average_phase_a_score=avg_a,
            average_phase_c_score=avg_c,
            average_observed_change=avg_change,
            assignments=assignments_out,
        )

    @staticmethod
    async def list_course_interventions(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        course_offering_id: uuid.UUID,
    ) -> List[InterventionOut]:
        """List all interventions created for this course offering."""
        stmt = (
            select(Intervention)
            .options(
                selectinload(Intervention.concepts).selectinload(InterventionConcept.concept),
                selectinload(Intervention.assignments),
            )
            .where(
                Intervention.course_offering_id == course_offering_id,
                Intervention.institution_id == tenant_id,
            )
            .order_by(Intervention.created_at.desc())
        )
        items = (await db.execute(stmt)).scalars().all()
        return [
            InterventionOut(
                id=item.id,
                institution_id=item.institution_id,
                course_offering_id=item.course_offering_id,
                title=item.title,
                description=item.description,
                status=item.status,
                phase_a_assessment_id=item.phase_a_assessment_id,
                phase_b_primer_content=item.phase_b_primer_content,
                phase_b_practice_assessment_id=item.phase_b_practice_assessment_id,
                phase_b_completion_rule=item.phase_b_completion_rule,
                phase_b_required_count=item.phase_b_required_count,
                phase_c_assessment_id=item.phase_c_assessment_id,
                approved_at=item.approved_at,
                published_at=item.published_at,
                created_at=item.created_at,
                updated_at=item.updated_at,
                target_concepts=[
                    InterventionConceptOut(
                        concept_id=ic.concept_id,
                        canonical_name=ic.concept.canonical_name if ic.concept else None,
                        concept_code=ic.concept.concept_code if ic.concept else None,
                        target_notes=ic.target_notes,
                    )
                    for ic in item.concepts
                ],
                assigned_students_count=len(item.assignments),
            )
            for item in items
        ]

    @staticmethod
    async def generate_intervention_primer_draft(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        course_offering_id: uuid.UUID,
        req: PrimerDraftRequest,
    ) -> PrimerDraftResponse:
        """
        Synthesizes a targeted pedagogical intervention primer (Phase B explanation)
        fusing teacher curriculum definitions, recorded student doubt inquiries, and
        observed assessment misconceptions.
        """
        concept_stmt = (
            select(Concept)
            .options(selectinload(Concept.versions))
            .where(
                Concept.id == req.concept_id,
                Concept.institution_id == tenant_id,
            )
        )
        concept = (await db.execute(concept_stmt)).scalars().first()
        if not concept:
            raise AppException(status_code=404, code="CONCEPT_NOT_FOUND", message="Concept not found.")

        # Gather recent doubts on this concept
        from app.modules.doubts.models import Doubt
        doubt_stmt = select(Doubt).where(
            Doubt.course_offering_id == course_offering_id,
            Doubt.concept_id == req.concept_id,
            Doubt.status != "removed",
        ).order_by(Doubt.created_at.desc()).limit(10)
        doubts = (await db.execute(doubt_stmt)).scalars().all()

        doubt_titles = [d.title for d in doubts if d.title]

        # Gather observed misconceptions from assessment telemetry
        from app.modules.analytics.models import MisconceptionEvent
        from app.modules.questions.models import Misconception
        misc_stmt = (
            select(Misconception.code, Misconception.description, func.count(MisconceptionEvent.id).label("cnt"))
            .join(MisconceptionEvent, Misconception.id == MisconceptionEvent.misconception_id)
            .where(
                MisconceptionEvent.course_offering_id == course_offering_id,
                MisconceptionEvent.institution_id == tenant_id,
                Misconception.concept_id == req.concept_id,
            )
            .group_by(Misconception.code, Misconception.description)
            .order_by(func.count(MisconceptionEvent.id).desc())
            .limit(5)
        )
        misc_rows = (await db.execute(misc_stmt)).all()
        misconception_descs = [f"{r[0]}: {r[1]}" for r in misc_rows]

        name = concept.canonical_name or "Target Concept"
        latest_ver = concept.versions[0] if concept.versions else None
        definition = (
            latest_ver.definition
            if latest_ver and latest_ver.definition
            else "Fundamental principle in the course syllabus."
        )

        primer_lines = [
            f"# Remediation Primer: {name}",
            "",
            "## 1. Core Principle & Intuition",
            f"{definition}",
            "",
            "When approaching problems in this topic, remember the fundamental invariant:",
            f"- Verify state transitions and edge boundary conditions for `{name}`.",
            "- Avoid premature optimization before verifying core correctness.",
            "",
        ]

        if misconception_descs:
            primer_lines.append("## 2. Common Pitfalls & Misconceptions Detected in Quizzes")
            for m in misconception_descs:
                primer_lines.append(f"- ⚠️ **{m}**")
            primer_lines.append("")

        if doubt_titles:
            primer_lines.append("## 3. Addressing Student Inquiries & Confusion Spikes")
            primer_lines.append("Students in this cohort recently inquired about:")
            for dt in doubt_titles[:4]:
                primer_lines.append(f"- *\"{dt}\"*")
            primer_lines.append("")
            primer_lines.append("**Key Takeaway**: Maintain clear distinction between high-level conceptual guarantees and implementation edge cases. Work through the base transitions systematically.")
            primer_lines.append("")

        primer_lines.extend([
            "## 4. Guided Checklist Before Moving to Practice Items",
            "1. Read the problem statement and identify the governing constraints.",
            "2. State the base cases and preconditions explicitly.",
            "3. Verify that your solution terminates on all valid sub-problem instances.",
            "4. Complete the targeted practice exercises below to demonstrate mastery.",
        ])

        primer_text = "\n".join(primer_lines)

        return PrimerDraftResponse(
            concept_id=concept.id,
            concept_name=name,
            primer_draft=primer_text,
            detected_misconceptions=misconception_descs,
            key_doubt_themes=doubt_titles[:5],
            recommended_reading=f"Course syllabus node: {name}",
        )

