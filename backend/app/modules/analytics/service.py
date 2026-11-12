from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy import select, and_, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.exceptions import AppException
from app.modules.academics.models import CourseOffering, CourseOfferingEnrolment, CourseOfferingFaculty
from app.modules.auth.models import User, InstitutionMembership
from app.modules.knowledge.models import Concept, CourseContentConcept, CourseContentVersion
from app.modules.assessments.models import (
    Assessment,
    AssessmentVersion,
    AssessmentItem,
    AssessmentItemConceptAllocation,
    AssessmentAttempt,
    AssessmentConceptScore,
    AssessmentResponse,
)
from app.modules.questions.models import Misconception, QuestionPartOption
from app.modules.analytics.models import (
    CourseAnalyticsPolicy,
    MisconceptionEvent,
    AnalyticsRun,
    StudentConceptEvidenceSnapshot,
    CohortConceptAnalytics,
    ConceptMasteryPolicy,
    StudentConceptMasteryEvaluation,
)
from app.modules.analytics.schemas import (
    CourseAnalyticsPolicyCreate,
    CourseAnalyticsPolicyUpdate,
    CourseAnalyticsPolicyOut,
    CohortConceptAnalyticsOut,
    StudentConceptEvidenceOut,
    StudentConceptDetailOut,
    SupportingQuestionEvidenceOut,
    ConceptAnalyticsDetailOut,
    MisconceptionFrequencyItemOut,
    MisconceptionReportOut,
    ConceptMasteryPolicyCreate,
    ConceptMasteryPolicyOut,
    StudentConceptMasteryEvaluationOut,
)


class AnalyticsService:

    @staticmethod
    async def _latest_submission_at(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        course_offering_id: uuid.UUID,
    ) -> Optional[datetime]:
        stmt = (
            select(func.max(AssessmentAttempt.submitted_at))
            .join(AssessmentVersion, AssessmentAttempt.assessment_version_id == AssessmentVersion.id)
            .join(Assessment, AssessmentVersion.assessment_id == Assessment.id)
            .where(
                Assessment.course_offering_id == course_offering_id,
                Assessment.institution_id == tenant_id,
                AssessmentAttempt.institution_id == tenant_id,
                AssessmentAttempt.submitted_at.isnot(None),
            )
        )
        return (await db.execute(stmt)).scalar_one_or_none()

    @staticmethod
    def _utc(value: Optional[datetime]) -> Optional[datetime]:
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)

    @staticmethod
    async def _ensure_current_analytics_run(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        course_offering_id: uuid.UUID,
        force_refresh: bool = False,
    ) -> AnalyticsRun:
        latest_stmt = (
            select(AnalyticsRun)
            .where(
                AnalyticsRun.course_offering_id == course_offering_id,
                AnalyticsRun.institution_id == tenant_id,
                AnalyticsRun.status == "completed",
            )
            .order_by(AnalyticsRun.started_at.desc())
        )
        latest_run = (await db.execute(latest_stmt)).scalars().first()
        latest_submission_at = await AnalyticsService._latest_submission_at(
            db, tenant_id, course_offering_id
        )
        watermark = AnalyticsService._utc(latest_run.source_watermark) if latest_run else None
        latest_submission_at = AnalyticsService._utc(latest_submission_at)
        has_new_submissions = bool(
            latest_submission_at and (watermark is None or latest_submission_at > watermark)
        )

        if force_refresh or latest_run is None or has_new_submissions:
            return await AnalyticsService.compute_and_persist_analytics_run(
                db=db,
                tenant_id=tenant_id,
                course_offering_id=course_offering_id,
                run_type="manual" if force_refresh else "event_triggered",
            )
        return latest_run

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
            message="You do not have permission to view or manage analytics for this course offering.",
        )

    @staticmethod
    async def get_or_resolve_policy(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        course_offering_id: uuid.UUID,
    ) -> CourseAnalyticsPolicy:
        """Resolve policy using precedence: Course Offering Override -> Institution Default -> System Defaults."""
        # 1. Course offering override
        stmt = select(CourseAnalyticsPolicy).where(
            CourseAnalyticsPolicy.institution_id == tenant_id,
            CourseAnalyticsPolicy.course_offering_id == course_offering_id,
            CourseAnalyticsPolicy.is_active == True,
        )
        res = await db.execute(stmt)
        policy = res.scalars().first()
        if policy:
            return policy

        # 2. Institution default
        stmt_inst = select(CourseAnalyticsPolicy).where(
            CourseAnalyticsPolicy.institution_id == tenant_id,
            CourseAnalyticsPolicy.course_offering_id.is_(None),
            CourseAnalyticsPolicy.is_active == True,
        )
        res_inst = await db.execute(stmt_inst)
        policy = res_inst.scalars().first()
        if policy:
            return policy

        # 3. Create persistent institution default
        policy = CourseAnalyticsPolicy(
            institution_id=tenant_id,
            course_offering_id=None,
            min_distinct_questions=3,
            weakness_accuracy_threshold=0.60,
            diagnostic_attempt_policy="first_valid_submitted_scored",
            is_active=True,
        )
        db.add(policy)
        await db.commit()
        await db.refresh(policy)
        return policy

    @staticmethod
    async def update_or_create_course_policy(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        course_offering_id: uuid.UUID,
        req: CourseAnalyticsPolicyUpdate,
        user_id: uuid.UUID,
    ) -> CourseAnalyticsPolicy:
        """Update or create a course-offering specific analytics policy override."""
        stmt = select(CourseAnalyticsPolicy).where(
            CourseAnalyticsPolicy.institution_id == tenant_id,
            CourseAnalyticsPolicy.course_offering_id == course_offering_id,
        )
        res = await db.execute(stmt)
        policy = res.scalars().first()

        now = datetime.now(timezone.utc)
        if not policy:
            policy = CourseAnalyticsPolicy(
                institution_id=tenant_id,
                course_offering_id=course_offering_id,
                min_distinct_questions=req.min_distinct_questions or 3,
                weakness_accuracy_threshold=req.weakness_accuracy_threshold or 0.60,
                diagnostic_attempt_policy="first_valid_submitted_scored",
                is_active=req.is_active if req.is_active is not None else True,
                created_by_user_id=user_id,
                effective_from=now,
            )
            db.add(policy)
        else:
            if req.min_distinct_questions is not None:
                policy.min_distinct_questions = req.min_distinct_questions
            if req.weakness_accuracy_threshold is not None:
                policy.weakness_accuracy_threshold = req.weakness_accuracy_threshold
            if req.is_active is not None:
                policy.is_active = req.is_active
            policy.updated_at = now

        await db.commit()
        await db.refresh(policy)
        return policy

    @staticmethod
    async def record_misconception_if_tagged(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        course_offering_id: uuid.UUID,
        attempt_id: uuid.UUID,
        student_membership_id: uuid.UUID,
        item_id: uuid.UUID,
        response_id: Optional[uuid.UUID],
        selected_option_id: uuid.UUID,
    ) -> Optional[MisconceptionEvent]:
        """Record an append-only misconception event if the chosen option carries an approved misconception tag."""
        stmt = select(QuestionPartOption).options(
            selectinload(QuestionPartOption.misconception)
        ).where(
            QuestionPartOption.id == selected_option_id,
            QuestionPartOption.institution_id == tenant_id,
        )
        res = await db.execute(stmt)
        opt = res.scalars().first()
        if (
            not opt
            or opt.is_correct
            or not opt.misconception_id
            or not opt.misconception
            or opt.misconception.review_status != "teacher_approved"
        ):
            return None

        # Check existing event for idempotency
        check_stmt = select(MisconceptionEvent).where(
            MisconceptionEvent.assessment_attempt_id == attempt_id,
            MisconceptionEvent.assessment_item_id == item_id,
            MisconceptionEvent.selected_option_id == selected_option_id,
            MisconceptionEvent.misconception_id == opt.misconception_id,
        )
        existing = (await db.execute(check_stmt)).scalars().first()
        if existing:
            return existing

        now = datetime.now(timezone.utc)
        event = MisconceptionEvent(
            institution_id=tenant_id,
            assessment_attempt_id=attempt_id,
            assessment_item_id=item_id,
            assessment_response_id=response_id,
            selected_option_id=selected_option_id,
            misconception_id=opt.misconception_id,
            student_membership_id=student_membership_id,
            course_offering_id=course_offering_id,
            occurred_at=now,
        )
        db.add(event)
        await db.flush()
        return event

    @staticmethod
    async def compute_and_persist_analytics_run(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        course_offering_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        run_type: str = "manual",
    ) -> AnalyticsRun:
        """
        Compute rebuildable concept accuracy and cohort analytics snapshots.
        Strictly applies the First Valid Submitted and Scored attempt policy.
        """
        now = datetime.now(timezone.utc)
        policy = await AnalyticsService.get_or_resolve_policy(db, tenant_id, course_offering_id)

        # 1. Fetch all active enrolled students for this course offering
        enrolment_stmt = (
            select(CourseOfferingEnrolment)
            .where(
                CourseOfferingEnrolment.course_offering_id == course_offering_id,
                CourseOfferingEnrolment.institution_id == tenant_id,
                CourseOfferingEnrolment.enrolment_status == "active",
            )
        )
        enrolments = (await db.execute(enrolment_stmt)).scalars().all()
        enrolled_student_ids = {e.institution_membership_id for e in enrolments}

        # 2. Fetch all published concepts associated with this course offering
        # Find published course content version
        ver_stmt = (
            select(CourseContentVersion)
            .where(
                CourseContentVersion.course_offering_id == course_offering_id,
                CourseContentVersion.institution_id == tenant_id,
                CourseContentVersion.status == "published",
            )
            .order_by(CourseContentVersion.version_number.desc(), CourseContentVersion.updated_at.desc())
        )
        content_version = (await db.execute(ver_stmt)).scalars().first()

        concepts: List[Concept] = []
        if content_version:
            c_stmt = (
                select(Concept)
                .join(CourseContentConcept, CourseContentConcept.concept_id == Concept.id)
                .where(
                    CourseContentConcept.course_content_version_id == content_version.id,
                    Concept.institution_id == tenant_id,
                )
            )
            concepts = list((await db.execute(c_stmt)).scalars().all())

        # If no published concepts, also gather concepts directly linked via assessment concept scores
        score_concept_stmt = (
            select(Concept)
            .join(AssessmentConceptScore, AssessmentConceptScore.concept_id == Concept.id)
            .where(
                AssessmentConceptScore.course_offering_id == course_offering_id,
                AssessmentConceptScore.institution_id == tenant_id,
            )
            .distinct()
        )
        extra_concepts = (await db.execute(score_concept_stmt)).scalars().all()
        concept_map: Dict[uuid.UUID, Concept] = {c.id: c for c in concepts}
        for ec in extra_concepts:
            concept_map[ec.id] = ec

        # Also include concepts allocated in assessments of this course offering
        ass_alloc_stmt = (
            select(Concept)
            .join(AssessmentItemConceptAllocation, AssessmentItemConceptAllocation.concept_id == Concept.id)
            .join(AssessmentItem, AssessmentItemConceptAllocation.assessment_item_id == AssessmentItem.id)
            .join(AssessmentVersion, AssessmentItem.assessment_version_id == AssessmentVersion.id)
            .join(Assessment, AssessmentVersion.assessment_id == Assessment.id)
            .where(
                Assessment.course_offering_id == course_offering_id,
                Assessment.institution_id == tenant_id,
            )
            .distinct()
        )
        ass_concepts = (await db.execute(ass_alloc_stmt)).scalars().all()
        for ac in ass_concepts:
            concept_map[ac.id] = ac

        all_concepts = list(concept_map.values())

        # 3. Retrieve all valid submitted and scored attempts for assessments in this offering
        att_stmt = (
            select(AssessmentAttempt)
            .join(AssessmentVersion, AssessmentAttempt.assessment_version_id == AssessmentVersion.id)
            .join(Assessment, AssessmentVersion.assessment_id == Assessment.id)
            .where(
                Assessment.course_offering_id == course_offering_id,
                AssessmentAttempt.institution_id == tenant_id,
                AssessmentAttempt.status.in_(["submitted", "expired"]),
                AssessmentAttempt.is_valid == True,
                AssessmentAttempt.scoring_status.in_(["scored", "partially_scored"]),
                AssessmentAttempt.submitted_at.isnot(None),
            )
            .order_by(AssessmentAttempt.submitted_at.asc(), AssessmentAttempt.attempt_number.asc())
        )
        valid_attempts = (await db.execute(att_stmt)).scalars().all()
        valid_attempt_ids = [a.id for a in valid_attempts]
        source_watermark = await AnalyticsService._latest_submission_at(
            db, tenant_id, course_offering_id
        )

        # 4. Fetch all concept scores belonging to these valid attempts
        concept_scores: List[AssessmentConceptScore] = []
        if valid_attempt_ids:
            scores_stmt = (
                select(AssessmentConceptScore)
                .where(
                    AssessmentConceptScore.assessment_attempt_id.in_(valid_attempt_ids),
                    AssessmentConceptScore.course_offering_id == course_offering_id,
                )
            )
            concept_scores = list((await db.execute(scores_stmt)).scalars().all())

        # Map attempt_id -> attempt metadata
        attempt_map: Dict[uuid.UUID, AssessmentAttempt] = {a.id: a for a in valid_attempts}

        # 5. Diagnostic Attempt Selection: First valid submitted attempt per (student, question_key)
        # Sort concept scores by attempt submitted_at
        concept_scores.sort(
            key=lambda cs: (
                attempt_map[cs.assessment_attempt_id].submitted_at or datetime.min.replace(tzinfo=timezone.utc),
                attempt_map[cs.assessment_attempt_id].attempt_number,
            )
        )

        # Track first attempt per (student_id, question_key)
        # question_key = question_id if available else assessment_item_id
        diagnostic_score_by_student_q: Dict[Tuple[uuid.UUID, uuid.UUID], uuid.UUID] = {}
        diagnostic_concept_scores: List[AssessmentConceptScore] = []

        for cs in concept_scores:
            stu_id = attempt_map[cs.assessment_attempt_id].student_membership_id
            q_key = cs.question_id if cs.question_id else cs.assessment_item_id

            first_attempt_id = diagnostic_score_by_student_q.get((stu_id, q_key))
            if first_attempt_id is None:
                diagnostic_score_by_student_q[(stu_id, q_key)] = cs.assessment_attempt_id
                diagnostic_concept_scores.append(cs)
            elif first_attempt_id == cs.assessment_attempt_id:
                # Same first attempt having multiple concept scores for this question
                diagnostic_concept_scores.append(cs)
            else:
                # Subsequent retry attempt on the same question -> Excluded from diagnostic course evidence
                pass

        # 6. Aggregate student concept metrics from diagnostic evidence
        # Key: (student_id, concept_id) -> {questions: set(), awarded: float, available: float}
        student_concept_data: Dict[Tuple[uuid.UUID, uuid.UUID], Dict[str, Any]] = {}
        for cs in diagnostic_concept_scores:
            stu_id = attempt_map[cs.assessment_attempt_id].student_membership_id
            q_key = cs.question_id if cs.question_id else cs.assessment_item_id
            pair = (stu_id, cs.concept_id)
            if pair not in student_concept_data:
                student_concept_data[pair] = {
                    "questions": set(),
                    "awarded": 0.0,
                    "available": 0.0,
                }
            student_concept_data[pair]["questions"].add(q_key)
            student_concept_data[pair]["awarded"] += float(cs.marks_awarded)
            student_concept_data[pair]["available"] += float(cs.marks_available)

        # 7. Create AnalyticsRun record
        run = AnalyticsRun(
            institution_id=tenant_id,
            course_offering_id=course_offering_id,
            policy_id=policy.id,
            run_type=run_type,
            status="completed",
            started_at=now,
            completed_at=now,
            source_watermark=source_watermark,
            created_by_user_id=user_id,
        )
        db.add(run)
        await db.flush()

        # 8. Compute Student Snapshots and Cohort Analytics
        min_q = policy.min_distinct_questions
        weak_threshold = float(policy.weakness_accuracy_threshold)

        student_snapshots: List[StudentConceptEvidenceSnapshot] = []
        cohort_analytics_list: List[CohortConceptAnalytics] = []

        # Count tagged misconception events per concept
        misc_counts: Dict[uuid.UUID, int] = {}
        misc_stmt = (
            select(Misconception.concept_id, func.count(MisconceptionEvent.id))
            .join(Misconception, MisconceptionEvent.misconception_id == Misconception.id)
            .where(
                MisconceptionEvent.course_offering_id == course_offering_id,
                MisconceptionEvent.institution_id == tenant_id,
            )
            .group_by(Misconception.concept_id)
        )
        for c_id, count_val in (await db.execute(misc_stmt)).all():
            misc_counts[c_id] = count_val

        for concept in all_concepts:
            c_id = concept.id
            enrolled_count = len(enrolled_student_ids)

            assessed_student_accuracies: List[float] = []
            cohort_awarded = 0.0
            cohort_available = 0.0

            confirmed_weak = 0
            candidate_weak = 0
            insufficient = 0

            # Iterate over all enrolled students
            for stu_id in enrolled_student_ids:
                sc = student_concept_data.get((stu_id, c_id))
                if sc and sc["available"] > 0.0 and len(sc["questions"]) > 0:
                    distinct_q = len(sc["questions"])
                    awarded = round(sc["awarded"], 2)
                    available = round(sc["available"], 2)
                    accuracy = round(awarded / available, 5)

                    cohort_awarded += awarded
                    cohort_available += available
                    assessed_student_accuracies.append(accuracy)

                    if accuracy < weak_threshold:
                        if distinct_q >= min_q:
                            status = "confirmed_weakness"
                            confirmed_weak += 1
                        else:
                            status = "candidate_weakness"
                            candidate_weak += 1
                    else:
                        if distinct_q >= min_q:
                            status = "not_currently_flagged_as_weak"
                        else:
                            # Below min distinct questions and accuracy >= threshold:
                            # Classified as insufficient_evidence as per Document 06 item 4
                            status = "insufficient_evidence"
                            insufficient += 1
                else:
                    distinct_q = 0
                    awarded = 0.0
                    available = 0.0
                    accuracy = None
                    status = "insufficient_evidence"
                    insufficient += 1

                snap = StudentConceptEvidenceSnapshot(
                    institution_id=tenant_id,
                    analytics_run_id=run.id,
                    course_offering_id=course_offering_id,
                    student_membership_id=stu_id,
                    concept_id=c_id,
                    distinct_question_count=distinct_q,
                    awarded_marks=awarded,
                    available_marks=available,
                    accuracy=accuracy,
                    diagnostic_status=status,
                    computed_at=now,
                )
                student_snapshots.append(snap)
                db.add(snap)

            # Cohort calculations
            assessed_count = len(assessed_student_accuracies)
            mean_acc = (
                round(sum(assessed_student_accuracies) / assessed_count, 5)
                if assessed_count > 0
                else None
            )
            pooled_acc = (
                round(cohort_awarded / cohort_available, 5)
                if cohort_available > 0.0
                else None
            )

            cohort_item = CohortConceptAnalytics(
                institution_id=tenant_id,
                analytics_run_id=run.id,
                course_offering_id=course_offering_id,
                concept_id=c_id,
                enrolled_count=enrolled_count,
                assessed_count=assessed_count,
                confirmed_weak_count=confirmed_weak,
                candidate_weak_count=candidate_weak,
                insufficient_evidence_count=insufficient,
                cohort_mean_accuracy=mean_acc,
                cohort_pooled_accuracy=pooled_acc,
                tagged_misconception_count=misc_counts.get(c_id, 0),
                computed_at=now,
            )
            cohort_analytics_list.append(cohort_item)
            db.add(cohort_item)

        await db.commit()
        await db.refresh(run)
        return run

    @staticmethod
    async def get_cohort_concept_analytics(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        course_offering_id: uuid.UUID,
        refresh: bool = False,
    ) -> List[CohortConceptAnalyticsOut]:
        """Fetch latest cohort analytics summary per concept. Rebuilds if absent or requested."""
        run = await AnalyticsService._ensure_current_analytics_run(
            db=db,
            tenant_id=tenant_id,
            course_offering_id=course_offering_id,
            force_refresh=refresh,
        )
        cohort_stmt = (
            select(CohortConceptAnalytics)
            .options(selectinload(CohortConceptAnalytics.concept))
            .where(
                CohortConceptAnalytics.analytics_run_id == run.id,
                CohortConceptAnalytics.course_offering_id == course_offering_id,
            )
        )
        items = (await db.execute(cohort_stmt)).scalars().all()
        results = [
            CohortConceptAnalyticsOut(
                concept_id=item.concept_id,
                concept_code=item.concept.concept_code if item.concept else None,
                concept_name=item.concept.canonical_name if item.concept else None,
                enrolled_count=item.enrolled_count,
                assessed_count=item.assessed_count,
                confirmed_weak_count=item.confirmed_weak_count,
                candidate_weak_count=item.candidate_weak_count,
                insufficient_evidence_count=item.insufficient_evidence_count,
                cohort_mean_accuracy=item.cohort_mean_accuracy,
                cohort_pooled_accuracy=item.cohort_pooled_accuracy,
                tagged_misconception_count=item.tagged_misconception_count,
                computed_at=item.computed_at,
            )
            for item in items
        ]
        results.sort(
            key=lambda row: (
                0 if row.assessed_count > 0 else 1,
                -row.confirmed_weak_count,
                -row.candidate_weak_count,
                (row.concept_name or "").lower(),
            )
        )
        return results

    @staticmethod
    async def get_concept_analytics_detail(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        course_offering_id: uuid.UUID,
        concept_id: uuid.UUID,
    ) -> ConceptAnalyticsDetailOut:
        """Fetch deep drilldown of student performance and supporting evidence on a specific concept."""
        # Ensure latest run exists
        policy = await AnalyticsService.get_or_resolve_policy(db, tenant_id, course_offering_id)

        latest_run = await AnalyticsService._ensure_current_analytics_run(
            db=db,
            tenant_id=tenant_id,
            course_offering_id=course_offering_id,
        )

        # Get Cohort record
        cohort_stmt = (
            select(CohortConceptAnalytics)
            .options(selectinload(CohortConceptAnalytics.concept))
            .where(
                CohortConceptAnalytics.analytics_run_id == latest_run.id,
                CohortConceptAnalytics.concept_id == concept_id,
            )
        )
        cohort_rec = (await db.execute(cohort_stmt)).scalars().first()
        if not cohort_rec:
            raise AppException(status_code=404, code="CONCEPT_NOT_FOUND", message="Concept not found in course analytics.")

        cohort_out = CohortConceptAnalyticsOut(
            concept_id=cohort_rec.concept_id,
            concept_code=cohort_rec.concept.concept_code if cohort_rec.concept else None,
            concept_name=cohort_rec.concept.canonical_name if cohort_rec.concept else None,
            enrolled_count=cohort_rec.enrolled_count,
            assessed_count=cohort_rec.assessed_count,
            confirmed_weak_count=cohort_rec.confirmed_weak_count,
            candidate_weak_count=cohort_rec.candidate_weak_count,
            insufficient_evidence_count=cohort_rec.insufficient_evidence_count,
            cohort_mean_accuracy=cohort_rec.cohort_mean_accuracy,
            cohort_pooled_accuracy=cohort_rec.cohort_pooled_accuracy,
            tagged_misconception_count=cohort_rec.tagged_misconception_count,
            computed_at=cohort_rec.computed_at,
        )

        # Get student snapshots
        snap_stmt = (
            select(StudentConceptEvidenceSnapshot)
            .options(selectinload(StudentConceptEvidenceSnapshot.concept))
            .where(
                StudentConceptEvidenceSnapshot.analytics_run_id == latest_run.id,
                StudentConceptEvidenceSnapshot.concept_id == concept_id,
            )
        )
        snapshots = (await db.execute(snap_stmt)).scalars().all()

        # Get student names from memberships
        mem_ids = [s.student_membership_id for s in snapshots]
        user_stmt = (
            select(InstitutionMembership, User)
            .join(User, InstitutionMembership.user_id == User.id)
            .where(InstitutionMembership.id.in_(mem_ids))
        )
        user_rows = (await db.execute(user_stmt)).all()
        user_map = {row[0].id: row[1].display_name for row in user_rows}

        # Gather supporting evidence for all submitted attempts
        score_stmt = (
            select(AssessmentConceptScore, AssessmentAttempt, AssessmentItem, Assessment)
            .join(AssessmentAttempt, AssessmentConceptScore.assessment_attempt_id == AssessmentAttempt.id)
            .join(AssessmentItem, AssessmentConceptScore.assessment_item_id == AssessmentItem.id)
            .join(AssessmentVersion, AssessmentItem.assessment_version_id == AssessmentVersion.id)
            .join(Assessment, AssessmentVersion.assessment_id == Assessment.id)
            .where(
                AssessmentConceptScore.concept_id == concept_id,
                AssessmentConceptScore.course_offering_id == course_offering_id,
                AssessmentAttempt.status.in_(["submitted", "expired"]),
                AssessmentAttempt.is_valid == True,
            )
            .order_by(AssessmentAttempt.submitted_at.asc(), AssessmentAttempt.attempt_number.asc())
        )
        evidence_rows = (await db.execute(score_stmt)).all()

        # Determine which attempt was diagnostic for each (student_id, question_key)
        first_attempt_map: Dict[Tuple[uuid.UUID, uuid.UUID], uuid.UUID] = {}
        for cs, att, item, ass in evidence_rows:
            q_key = cs.question_id if cs.question_id else cs.assessment_item_id
            pair = (att.student_membership_id, q_key)
            if pair not in first_attempt_map:
                first_attempt_map[pair] = att.id

        # Group evidence by student
        evidence_by_student: Dict[uuid.UUID, List[SupportingQuestionEvidenceOut]] = {}
        for cs, att, item, ass in evidence_rows:
            q_key = cs.question_id if cs.question_id else cs.assessment_item_id
            is_diag = (first_attempt_map.get((att.student_membership_id, q_key)) == att.id)
            ev_item = SupportingQuestionEvidenceOut(
                item_id=item.id,
                question_or_activity_id=q_key,
                assessment_id=ass.id,
                assessment_title=ass.title,
                attempt_id=att.id,
                attempt_number=att.attempt_number,
                submitted_at=att.submitted_at or att.started_at,
                marks_awarded=float(cs.marks_awarded),
                marks_available=float(cs.marks_available),
                is_diagnostic=is_diag,
            )
            evidence_by_student.setdefault(att.student_membership_id, []).append(ev_item)

        students_out: List[StudentConceptDetailOut] = []
        for snap in snapshots:
            students_out.append(
                StudentConceptDetailOut(
                    student_membership_id=snap.student_membership_id,
                    student_name=user_map.get(snap.student_membership_id, "Student"),
                    concept_id=snap.concept_id,
                    concept_name=snap.concept.canonical_name if snap.concept else None,
                    distinct_question_count=snap.distinct_question_count,
                    awarded_marks=float(snap.awarded_marks),
                    available_marks=float(snap.available_marks),
                    accuracy=snap.accuracy,
                    diagnostic_status=snap.diagnostic_status,
                    computed_at=snap.computed_at,
                    supporting_evidence=evidence_by_student.get(snap.student_membership_id, []),
                )
            )

        policy_out = CourseAnalyticsPolicyOut(
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

        return ConceptAnalyticsDetailOut(
            concept=cohort_out,
            policy=policy_out,
            students=students_out,
        )

    @staticmethod
    async def get_misconception_report(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        course_offering_id: uuid.UUID,
    ) -> MisconceptionReportOut:
        """Misconception tag frequency report across all assessments in this offering."""
        stmt = (
            select(
                Misconception.id,
                Misconception.code,
                Misconception.description,
                Misconception.concept_id,
                Concept.canonical_name.label("concept_title"),
                func.count(MisconceptionEvent.id).label("occurrences"),
            )
            .join(MisconceptionEvent, MisconceptionEvent.misconception_id == Misconception.id)
            .join(Concept, Misconception.concept_id == Concept.id)
            .where(
                MisconceptionEvent.course_offering_id == course_offering_id,
                MisconceptionEvent.institution_id == tenant_id,
            )
            .group_by(
                Misconception.id,
                Misconception.code,
                Misconception.description,
                Misconception.concept_id,
                Concept.canonical_name,
            )
            .order_by(func.count(MisconceptionEvent.id).desc())
        )
        rows = (await db.execute(stmt)).all()

        items = [
            MisconceptionFrequencyItemOut(
                misconception_id=row[0],
                code=row[1],
                description=row[2],
                concept_id=row[3],
                concept_title=row[4],
                occurrence_count=row[5],
            )
            for row in rows
        ]
        total_count = sum(item.occurrence_count for item in items)
        return MisconceptionReportOut(
            course_offering_id=course_offering_id,
            total_events=total_count,
            misconceptions=items,
        )

    @staticmethod
    async def create_mastery_policy(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        course_offering_id: uuid.UUID,
        req: ConceptMasteryPolicyCreate,
        user_id: uuid.UUID,
    ) -> ConceptMasteryPolicyOut:
        """Create a separate teacher-configured concept mastery policy."""
        now = datetime.now(timezone.utc)
        policy = ConceptMasteryPolicy(
            institution_id=tenant_id,
            course_offering_id=course_offering_id,
            policy_name=req.policy_name,
            criteria_json=req.criteria_json,
            status="active",
            created_by_user_id=user_id,
            approved_by_user_id=user_id,
        )
        db.add(policy)
        await db.commit()
        await db.refresh(policy)
        return ConceptMasteryPolicyOut(
            id=policy.id,
            institution_id=policy.institution_id,
            course_offering_id=policy.course_offering_id,
            policy_name=policy.policy_name,
            criteria_json=policy.criteria_json,
            status=policy.status,
            created_at=policy.created_at,
            updated_at=policy.updated_at,
        )

    @staticmethod
    async def list_mastery_policies(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        course_offering_id: uuid.UUID,
    ) -> List[ConceptMasteryPolicyOut]:
        """List active mastery policies for a course offering."""
        stmt = (
            select(ConceptMasteryPolicy)
            .where(
                ConceptMasteryPolicy.course_offering_id == course_offering_id,
                ConceptMasteryPolicy.institution_id == tenant_id,
            )
            .order_by(ConceptMasteryPolicy.created_at.desc())
        )
        policies = (await db.execute(stmt)).scalars().all()
        return [
            ConceptMasteryPolicyOut(
                id=p.id,
                institution_id=p.institution_id,
                course_offering_id=p.course_offering_id,
                policy_name=p.policy_name,
                criteria_json=p.criteria_json,
                status=p.status,
                created_at=p.created_at,
                updated_at=p.updated_at,
            )
            for p in policies
        ]
