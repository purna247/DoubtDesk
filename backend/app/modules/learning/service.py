from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Set
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.exceptions import AppException
from app.modules.auth.schemas import UserProfile
from app.modules.auth.models import InstitutionMembership
from app.modules.learning.models import (
    LearningNode,
    LearningNodeConcept,
    LearningNodePrerequisite,
    LearningNodeQuestion,
    Activity,
    ActivityVersion,
    StudentPracticeSession,
    StudentPracticeEvent,
)
from app.modules.assessments.models import (
    StudentLearningNodeProgress,
    AssessmentAttempt,
    AssessmentItemScore,
    AssessmentItem,
)
from app.modules.questions.models import Question, QuestionVersion
from app.modules.interventions.models import (
    Intervention,
    InterventionAssignment,
)
from app.modules.interventions.service import InterventionService
from app.modules.learning.schemas import (
    LearningNodeCreate,
    LearningNodeUpdate,
    LearningNodeOut,
    LearningNodePrerequisiteCreate,
    ActivityCreate,
    ActivityOut,
    ActivityVersionOut,
    CourseLearningMapResponse,
    MetricSummary,
    RemainingSupportSummary,
    ContinueLearningSummary,
    CourseProgressSummary,
    StudentProgressSummaryResponse,
)
from app.modules.learning.scoring import evaluate_activity_response, ActivityEvaluationResult
from app.modules.academics.models import (
    CourseOffering,
    CourseOfferingEnrolment,
    CurriculumSubjectEntry,
    CanonicalSubject,
)
from app.modules.knowledge.models import CourseContentVersion, Concept
from app.modules.knowledge.service import KnowledgeService


class LearningService:

    @staticmethod
    async def update_learning_node(
        db: AsyncSession,
        node_id: uuid.UUID,
        tenant_id: uuid.UUID,
        data: LearningNodeUpdate,
    ) -> LearningNode:
        node = await db.get(LearningNode, node_id)
        if not node or node.institution_id != tenant_id:
            raise AppException(status_code=404, code="NODE_NOT_FOUND", message="Learning node not found.")
        if data.expected_revision is not None and data.expected_revision != node.revision:
            raise AppException(status_code=409, code="LEARNING_NODE_REVISION_CONFLICT", message="This node changed since you opened it. Reload before saving edits.")
        if node.status != "draft":
            raise AppException(status_code=409, code="PUBLISHED_NODE_IMMUTABLE", message="Published learning nodes are immutable. Create a draft revision before changing student-facing content.")

        changes = data.model_dump(exclude_unset=True, exclude={"expected_revision"})
        if changes:
            for field_name, value in changes.items():
                setattr(node, field_name, value)
            node.revision += 1
            await db.commit()
            await db.refresh(node)
        return node

    @staticmethod
    def sanitize_authoring_payload(
        activity_type: str,
        authoring_payload: Dict[str, Any],
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        """
        Splits a teacher authoring payload into:
        1. A student-safe renderer payload (WITHOUT correct answers, feedback, or misconception tags).
        2. A server-authoritative answer key.
        """
        if activity_type == "mcq":
            student_payload = {
                "question": authoring_payload["question"],
                "options": [
                    {"option_id": o["option_id"], "text": o["text"]}
                    for o in authoring_payload["options"]
                ],
            }
            answer_key = {
                "correct_option_id": authoring_payload["correct_option_id"],
                "explanation": authoring_payload.get("explanation"),
                "misconceptions": {
                    o["option_id"]: o.get("misconception_tag")
                    for o in authoring_payload["options"]
                    if o.get("misconception_tag")
                },
            }

        elif activity_type == "fill_blank":
            student_payload = {
                "template": authoring_payload["template"],
                "blank_ids": [b["blank_id"] for b in authoring_payload["blanks"]],
                "word_bank": authoring_payload.get("word_bank", []),
            }
            answer_key = {
                "blanks": {
                    b["blank_id"]: {
                        "accepted_answers": b["accepted_answers"],
                        "explanation": b.get("explanation"),
                    }
                    for b in authoring_payload["blanks"]
                }
            }

        elif activity_type == "matching_pairs":
            student_payload = {
                "left_items": [
                    {"pair_id": p["pair_id"], "text": p["left_text"]}
                    for p in authoring_payload["pairs"]
                ],
                "right_items": [
                    {"pair_id": p["pair_id"], "text": p["right_text"]}
                    for p in reversed(authoring_payload["pairs"])  # Shuffled for presentation
                ],
            }
            answer_key = {
                "pairs": {p["pair_id"]: p["pair_id"] for p in authoring_payload["pairs"]},
                "explanations": {p["pair_id"]: p.get("explanation") for p in authoring_payload["pairs"]},
            }

        elif activity_type == "ordering":
            student_payload = {
                "items": [
                    {"item_id": i["item_id"], "label": i["label"], "detail": i.get("detail")}
                    for i in authoring_payload["items"]
                ]
            }
            answer_key = {
                "correct_order": authoring_payload["correct_order"],
                "explanation": authoring_payload.get("explanation"),
            }

        elif activity_type == "classification":
            student_payload = {
                "categories": [
                    {"category_id": c["category_id"], "label": c["label"], "description": c.get("description")}
                    for c in authoring_payload["categories"]
                ],
                "items": [
                    {"item_id": i["item_id"], "text": i["text"]}
                    for i in authoring_payload["items"]
                ],
            }
            answer_key = {
                "items": {i["item_id"]: i["correct_category_id"] for i in authoring_payload["items"]}
            }

        elif activity_type == "key_points_check":
            student_payload = {
                "question": authoring_payload["question"],
                "options": [
                    {"point_id": p["point_id"], "text": p["text"]}
                    for p in authoring_payload["options"]
                ],
                "min_required": authoring_payload.get("min_required", 1),
            }
            answer_key = {
                "essential_point_ids": [
                    p["point_id"] for p in authoring_payload["options"] if p.get("is_essential")
                ],
                "non_essential_point_ids": [
                    p["point_id"] for p in authoring_payload["options"] if not p.get("is_essential")
                ],
                "explanation": authoring_payload.get("explanation"),
            }

        elif activity_type == "true_false":
            opts = authoring_payload.get("options") or [
                {"option_id": "true", "text": "True"},
                {"option_id": "false", "text": "False"},
            ]
            student_payload = {
                "question": authoring_payload.get("question") or authoring_payload.get("prompt"),
                "options": [{"option_id": str(o.get("option_id")), "text": str(o.get("text"))} for o in opts],
            }
            raw_correct = authoring_payload.get("correct_option_id")
            if raw_correct is None and "correct_value" in authoring_payload:
                raw_correct = "true" if authoring_payload["correct_value"] is True else "false"
            answer_key = {
                "correct_option_id": str(raw_correct or "true").lower(),
                "explanation": authoring_payload.get("explanation"),
            }

        elif activity_type == "one_word":
            acc = authoring_payload.get("accepted_answers") or []
            if isinstance(acc, str):
                acc = [s.strip() for s in acc.split(",") if s.strip()]
            if not acc and authoring_payload.get("correct_answer"):
                acc = [str(authoring_payload["correct_answer"]).strip()]
            student_payload = {
                "question": authoring_payload.get("question") or authoring_payload.get("prompt"),
                "placeholder": authoring_payload.get("placeholder", "Type one-word answer..."),
            }
            answer_key = {
                "accepted_answers": acc,
                "explanation": authoring_payload.get("explanation"),
            }
        else:
            raise AppException(
                status_code=400,
                code="UNSUPPORTED_ACTIVITY_TYPE",
                message=f"Activity type '{activity_type}' is not supported.",
            )

        return student_payload, answer_key

    @staticmethod
    async def create_learning_node(
        db: AsyncSession,
        offering_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        data: LearningNodeCreate,
    ) -> LearningNode:
        offering = await db.get(CourseOffering, offering_id)
        if not offering or offering.institution_id != tenant_id:
            raise AppException(status_code=404, code="OFFERING_NOT_FOUND", message="Course offering not found.")

        # Find latest content version
        v_stmt = (
            select(CourseContentVersion)
            .where(
                CourseContentVersion.course_offering_id == offering_id,
                CourseContentVersion.institution_id == tenant_id,
            )
            .order_by(CourseContentVersion.version_number.desc())
        )
        content_v = (await db.execute(v_stmt)).scalars().first()
        if not content_v:
            # Create initial content version
            content_v = await KnowledgeService.get_or_create_draft_version(
                db=db, offering_id=offering_id, tenant_id=tenant_id, user_id=user_id
            )

        node = LearningNode(
            institution_id=tenant_id,
            course_offering_id=offering_id,
            course_content_version_id=content_v.id,
            node_code=data.node_code,
            module_title=data.module_title,
            difficulty_rank=data.difficulty_rank,
            title=data.title,
            description=data.description,
            sequence_no=data.sequence_no,
            status="draft",
            completion_rule_json=data.completion_rule_json,
            created_by_user_id=user_id,
        )
        db.add(node)
        await db.flush()

        # Add concepts
        for c_id in data.concept_ids:
            c = await db.get(Concept, c_id)
            if c and c.institution_id == tenant_id:
                db.add(
                    LearningNodeConcept(
                        institution_id=tenant_id,
                        learning_node_id=node.id,
                        concept_id=c_id,
                        relationship_role="primary",
                        mapping_status="teacher_approved",
                    )
                )

        # Add prerequisites
        for p_id in data.prerequisite_node_ids:
            if p_id == node.id:
                raise AppException(status_code=400, code="SELF_PREREQUISITE", message="Node cannot be prerequisite of itself.")
            db.add(
                LearningNodePrerequisite(
                    institution_id=tenant_id,
                    learning_node_id=node.id,
                    prerequisite_node_id=p_id,
                    prerequisite_type="required",
                )
            )

        await db.commit()
        await db.refresh(node)
        return node

    @staticmethod
    async def add_prerequisite(
        db: AsyncSession,
        node_id: uuid.UUID,
        tenant_id: uuid.UUID,
        data: LearningNodePrerequisiteCreate,
    ) -> LearningNodePrerequisite:
        if node_id == data.prerequisite_node_id:
            raise AppException(status_code=400, code="SELF_PREREQUISITE", message="A node cannot depend on itself.")

        node = await db.get(LearningNode, node_id)
        prereq = await db.get(LearningNode, data.prerequisite_node_id)
        if not node or node.institution_id != tenant_id or not prereq or prereq.institution_id != tenant_id:
            raise AppException(status_code=404, code="NODE_NOT_FOUND", message="Learning node not found.")

        # Cycle detection: Check if node_id is reachable from data.prerequisite_node_id
        is_cyclic = await LearningService._is_reachable(db, start_id=data.prerequisite_node_id, target_id=node_id)
        if is_cyclic:
            raise AppException(
                status_code=400,
                code="CYCLE_DETECTED",
                message="Cannot add prerequisite: circular dependency cycle detected.",
            )

        prereq_link = LearningNodePrerequisite(
            institution_id=tenant_id,
            learning_node_id=node_id,
            prerequisite_node_id=data.prerequisite_node_id,
            prerequisite_type=data.prerequisite_type,
        )
        db.add(prereq_link)
        await db.commit()
        await db.refresh(prereq_link)
        return prereq_link

    @staticmethod
    async def _is_reachable(db: AsyncSession, start_id: uuid.UUID, target_id: uuid.UUID) -> bool:
        """DFS traversal checking if target_id is reachable from start_id."""
        visited: Set[uuid.UUID] = set()
        queue: List[uuid.UUID] = [start_id]

        while queue:
            curr = queue.pop(0)
            if curr == target_id:
                return True
            if curr in visited:
                continue
            visited.add(curr)

            # Find all prerequisites of curr
            stmt = select(LearningNodePrerequisite.prerequisite_node_id).where(
                LearningNodePrerequisite.learning_node_id == curr
            )
            res = await db.execute(stmt)
            neighbors = res.scalars().all()
            for n in neighbors:
                if n not in visited:
                    queue.append(n)

        return False

    @staticmethod
    async def publish_learning_node(
        db: AsyncSession,
        node_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> LearningNode:
        node = await db.get(LearningNode, node_id)
        if not node or node.institution_id != tenant_id:
            raise AppException(status_code=404, code="NODE_NOT_FOUND", message="Learning node not found.")

        node.status = "published"
        node.published_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(node)
        return node

    @staticmethod
    async def create_activity(
        db: AsyncSession,
        node_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        data: ActivityCreate,
    ) -> Activity:
        node = await db.get(LearningNode, node_id)
        if not node or node.institution_id != tenant_id:
            raise AppException(status_code=404, code="NODE_NOT_FOUND", message="Learning node not found.")

        student_payload, answer_key = LearningService.sanitize_authoring_payload(
            activity_type=data.activity_type,
            authoring_payload=data.authoring_payload,
        )

        scoring_config = data.scoring_config or {"max_marks": 1.0, "partial_credit": True}

        activity = Activity(
            institution_id=tenant_id,
            learning_node_id=node_id,
            question_id=data.question_id,
            created_by_user_id=user_id,
            status="active",
        )
        db.add(activity)
        await db.flush()

        now = datetime.now(timezone.utc)
        version = ActivityVersion(
            institution_id=tenant_id,
            activity_id=activity.id,
            version_number=1,
            activity_type=data.activity_type,
            schema_version=1,
            title=data.title,
            instructions=data.instructions,
            student_payload_json=student_payload,
            answer_key_json=answer_key,
            scoring_config_json=scoring_config,
            approval_status="approved",
            created_by_user_id=user_id,
            approved_by_user_id=user_id,
            approved_at=now,
        )
        db.add(version)
        await db.commit()
        await db.refresh(activity)
        return activity

    @staticmethod
    async def update_activity(
        db: AsyncSession,
        activity_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        data: ActivityCreate,
    ) -> Activity:
        activity = await db.get(Activity, activity_id)
        if not activity or activity.institution_id != tenant_id:
            raise AppException(status_code=404, code="ACTIVITY_NOT_FOUND", message="Activity not found.")

        student_payload, answer_key = LearningService.sanitize_authoring_payload(
            activity_type=data.activity_type,
            authoring_payload=data.authoring_payload,
        )
        scoring_config = data.scoring_config or {"max_marks": 1.0, "partial_credit": True}

        v_stmt = (
            select(ActivityVersion)
            .where(ActivityVersion.activity_id == activity.id)
            .order_by(ActivityVersion.version_number.desc())
            .limit(1)
        )
        latest_v = (await db.execute(v_stmt)).scalars().first()

        now = datetime.now(timezone.utc)
        if latest_v:
            latest_v.title = data.title
            latest_v.instructions = data.instructions
            latest_v.student_payload_json = student_payload
            if scoring_config.get("citation"):
                answer_key["citation"] = scoring_config["citation"]
            scoring_config["edited_by_teacher"] = True
            latest_v.answer_key_json = answer_key
            latest_v.scoring_config_json = scoring_config
            latest_v.approved_by_user_id = user_id
            latest_v.approved_at = now
        else:
            latest_v = ActivityVersion(
                institution_id=tenant_id,
                activity_id=activity.id,
                version_number=1,
                activity_type=data.activity_type,
                schema_version=1,
                title=data.title,
                instructions=data.instructions,
                student_payload_json=student_payload,
                answer_key_json=answer_key,
                scoring_config_json=scoring_config,
                approval_status="approved",
                created_by_user_id=user_id,
                approved_by_user_id=user_id,
                approved_at=now,
            )
            db.add(latest_v)

        activity.status = "active"
        await db.commit()
        await db.refresh(activity)
        return activity

    @staticmethod
    async def archive_activity(
        db: AsyncSession,
        activity_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> Activity:
        activity = await db.get(Activity, activity_id)
        if not activity or activity.institution_id != tenant_id:
            raise AppException(status_code=404, code="ACTIVITY_NOT_FOUND", message="Activity not found.")
        activity.status = "archived"
        await db.commit()
        await db.refresh(activity)
        return activity

    @staticmethod
    async def resolve_student_learning_map(
        db: AsyncSession,
        offering_id: uuid.UUID,
        tenant_id: uuid.UUID,
        student_id: uuid.UUID,
    ) -> CourseLearningMapResponse:
        await KnowledgeService.verify_student_access(
            db=db, offering_id=offering_id, tenant_id=tenant_id, user_id=student_id
        )

        # Get all published learning nodes for this offering
        stmt = (
            select(LearningNode)
            .options(
                selectinload(LearningNode.concept_links),
                selectinload(LearningNode.prerequisites),
                selectinload(LearningNode.activities),
            )
            .where(
                LearningNode.course_offering_id == offering_id,
                LearningNode.institution_id == tenant_id,
                LearningNode.status == "published",
            )
            .order_by(LearningNode.sequence_no, LearningNode.difficulty_rank)
        )
        res = await db.execute(stmt)
        all_nodes = res.scalars().all()
        nodes = [
            n for n in all_nodes
            if n.title != "Course Quizzes & Assessments"
            and (n.node_code or "") != "QUIZ_CONTAINER"
        ]

        # Lookup student membership to inspect prerequisite completions & practice telemetry
        from app.modules.auth.models import InstitutionMembership
        mem = (
            await db.execute(
                select(InstitutionMembership).where(
                    InstitutionMembership.institution_id == tenant_id,
                    InstitutionMembership.user_id == student_id,
                )
            )
        ).scalars().first()

        completed_node_ids: Set[uuid.UUID] = set()
        progress_by_node: Dict[uuid.UUID, str] = {}
        session_by_node: Dict[uuid.UUID, StudentPracticeSession] = {}
        node_ids = [n.id for n in nodes]

        if mem and node_ids:
            prog_rows = (
                await db.execute(
                    select(StudentLearningNodeProgress).where(
                        StudentLearningNodeProgress.student_membership_id == mem.id,
                        StudentLearningNodeProgress.learning_node_id.in_(node_ids),
                    )
                )
            ).scalars().all()
            for p in prog_rows:
                progress_by_node[p.learning_node_id] = p.progress_status
                if p.progress_status == "completed":
                    completed_node_ids.add(p.learning_node_id)

            sess_rows = (
                await db.execute(
                    select(StudentPracticeSession)
                    .where(
                        StudentPracticeSession.student_membership_id == mem.id,
                        StudentPracticeSession.learning_node_id.in_(node_ids),
                    )
                    .order_by(StudentPracticeSession.updated_at.desc())
                )
            ).scalars().all()
            for s in sess_rows:
                session_by_node.setdefault(s.learning_node_id, s)

        # Count source LearningNodeQuestions per node
        lnq_counts: Dict[uuid.UUID, int] = {}
        if node_ids:
            cnt_rows = (
                await db.execute(
                    select(LearningNodeQuestion.learning_node_id, func.count(LearningNodeQuestion.id))
                    .where(LearningNodeQuestion.learning_node_id.in_(node_ids))
                    .group_by(LearningNodeQuestion.learning_node_id)
                )
            ).all()
            lnq_counts = {nid: int(cnt) for nid, cnt in cnt_rows}

        out_nodes: List[LearningNodeOut] = []
        for n in nodes:
            prereq_ids = [p.prerequisite_node_id for p in n.prerequisites if p.prerequisite_type == "required"]
            concept_ids = [c.concept_id for c in n.concept_links]
            is_unlocked = len(prereq_ids) == 0 or all(pid in completed_node_ids for pid in prereq_ids)
            sess = session_by_node.get(n.id)
            prog_status = progress_by_node.get(n.id) or ("available" if is_unlocked else "locked")
            act_count = len([a for a in (n.activities or []) if a.status == "active"])
            q_count = max(act_count, lnq_counts.get(n.id, 0))
            practice_summary = None
            if sess:
                practice_summary = {
                    "session_id": str(sess.id),
                    "status": sess.status,
                    "current_difficulty": sess.current_difficulty,
                    "questions_answered": sess.questions_answered,
                    "correct_count": sess.correct_count,
                    "target_correct_count": sess.target_correct_count,
                    "mistake_count": sess.mistake_count,
                    "easier_followups_triggered": sess.easier_followups_triggered,
                    "hints_used": sess.hints_used,
                    "recovered_after_mistake_count": sess.recovered_after_mistake_count,
                    "repeated_mistakes": sess.consecutive_mistakes >= 2 or sess.mistake_count >= 2,
                    "needs_easier_questions": sess.easier_followups_triggered > 0,
                    "improving": sess.recovered_after_mistake_count > 0,
                }

            out_nodes.append(
                LearningNodeOut(
                    id=n.id,
                    institution_id=n.institution_id,
                    course_offering_id=n.course_offering_id,
                    course_content_version_id=n.course_content_version_id,
                    node_code=n.node_code,
                    module_title=n.module_title,
                    difficulty_rank=n.difficulty_rank,
                    title=n.title,
                    description=n.description,
                    sequence_no=n.sequence_no,
                    status=n.status,
                    completion_rule_json=n.completion_rule_json,
                    created_by_user_id=n.created_by_user_id,
                    published_at=n.published_at,
                    created_at=n.created_at,
                    updated_at=n.updated_at,
                    concept_ids=concept_ids,
                    prerequisite_node_ids=prereq_ids,
                    is_unlocked=is_unlocked,
                    progress_status=prog_status,
                    question_count=q_count,
                    practice_summary=practice_summary,
                )
            )

        content_v_id = nodes[0].course_content_version_id if nodes else uuid.uuid4()
        return CourseLearningMapResponse(
            course_offering_id=offering_id,
            course_content_version_id=content_v_id,
            nodes=out_nodes,
        )

    @staticmethod
    async def evaluate_activity(
        db: AsyncSession,
        activity_version_id: uuid.UUID,
        tenant_id: uuid.UUID,
        response_data: Dict[str, Any],
    ) -> ActivityEvaluationResult:
        v = await db.get(ActivityVersion, activity_version_id)
        if not v or v.institution_id != tenant_id:
            raise AppException(status_code=404, code="ACTIVITY_NOT_FOUND", message="Activity version not found.")

        if (v.scoring_config_json or {}).get("assessment_type", "").startswith("intervention_"):
            raise AppException(status_code=403, code="ASSESSMENT_ACTIVITY_RESTRICTED", message="Complete intervention questions through the assigned assessment.")

        return evaluate_activity_response(
            activity_type=v.activity_type,
            response_data=response_data,
            answer_key=v.answer_key_json,
            scoring_config=v.scoring_config_json,
        )

    @staticmethod
    async def get_student_progress_summary(
        db: AsyncSession,
        tenant_id: uuid.UUID,
        user: UserProfile,
        curriculum_subject_entry_id: Optional[uuid.UUID] = None,
    ) -> StudentProgressSummaryResponse:
        user_uuid = uuid.UUID(user.id)
        # Find active institution membership
        mem = (
            await db.execute(
                select(InstitutionMembership).where(
                    InstitutionMembership.user_id == user_uuid,
                    InstitutionMembership.institution_id == tenant_id,
                    InstitutionMembership.membership_status == "active",
                )
            )
        ).scalars().first()
        if not mem:
            raise AppException(status_code=403, code="NOT_A_MEMBER", message="Active membership required.")

        # Find active enrolled offerings for this student
        enrol_stmt = (
            select(CourseOffering, CurriculumSubjectEntry, CanonicalSubject)
            .join(CourseOfferingEnrolment, CourseOfferingEnrolment.course_offering_id == CourseOffering.id)
            .join(CurriculumSubjectEntry, CurriculumSubjectEntry.id == CourseOffering.curriculum_subject_entry_id)
            .join(CanonicalSubject, CanonicalSubject.id == CurriculumSubjectEntry.canonical_subject_id)
            .where(
                CourseOffering.institution_id == tenant_id,
                CourseOfferingEnrolment.institution_membership_id == mem.id,
                CourseOfferingEnrolment.enrolment_status == "active",
            )
        )
        enrol_rows = (await db.execute(enrol_stmt)).all()

        if curriculum_subject_entry_id is not None:
            filtered_rows = [
                row for row in enrol_rows if row[1].id == curriculum_subject_entry_id
            ]
            if not filtered_rows:
                # Return non-disclosing 404 as required by the specification
                raise AppException(
                    status_code=404,
                    code="SUBJECT_NOT_FOUND",
                    message="Subject not found or student not enrolled in this subject.",
                )
            enrol_rows = filtered_rows

        per_offering: List[CourseProgressSummary] = []
        all_active_interventions: List[tuple[Intervention, InterventionAssignment, CourseOffering, CanonicalSubject]] = []
        all_unlocked_nodes: List[tuple[LearningNode, CourseOffering, CanonicalSubject]] = []

        total_topics_completed = 0
        total_topics_eligible = 0
        topics_has_available = False
        topics_has_unsupported = False

        total_practice_attempted = 0
        total_practice_eligible = 0
        total_practice_correct = 0
        practice_has_available = False
        practice_has_unsupported = False

        total_active_support = 0
        total_completed_support = 0

        now = datetime.now(timezone.utc)

        for offering, entry, canon in enrol_rows:
            # 1. Topic Progress
            nodes_stmt = (
                select(LearningNode)
                .where(
                    LearningNode.course_offering_id == offering.id,
                    LearningNode.institution_id == tenant_id,
                    LearningNode.status == "published",
                )
                .order_by(LearningNode.sequence_no.asc())
            )
            published_nodes = (await db.execute(nodes_stmt)).scalars().all()
            published_node_ids = [n.id for n in published_nodes]

            completed_node_ids: Set[uuid.UUID] = set()
            if published_node_ids:
                prog_stmt = select(StudentLearningNodeProgress.learning_node_id).where(
                    StudentLearningNodeProgress.student_membership_id == mem.id,
                    StudentLearningNodeProgress.learning_node_id.in_(published_node_ids),
                    StudentLearningNodeProgress.progress_status == "completed",
                )
                completed_node_ids = set((await db.execute(prog_stmt)).scalars().all())

            # Find first unlocked unfinished node for continue learning fallback
            for node in published_nodes:
                if node.id not in completed_node_ids:
                    all_unlocked_nodes.append((node, offering, canon))

            topic_metric: MetricSummary
            if not published_nodes:
                topic_metric = MetricSummary(
                    status="no_content",
                    reason="No published learning topics in this course.",
                )
                topics_has_unsupported = True
            else:
                comp_c = len(completed_node_ids)
                elig_c = len(published_nodes)
                topic_metric = MetricSummary(
                    status="available",
                    completed_count=comp_c,
                    eligible_count=elig_c,
                    percentage=round((comp_c / elig_c) * 100, 1) if elig_c > 0 else 0.0,
                )
                total_topics_completed += comp_c
                total_topics_eligible += elig_c
                topics_has_available = True

            # 2. Teacher Material Practice Questions
            eligible_item_ids: Set[uuid.UUID] = set()
            if published_node_ids:
                # Mapped question IDs
                q_stmt = select(LearningNodeQuestion.question_id).where(
                    LearningNodeQuestion.learning_node_id.in_(published_node_ids)
                )
                ln_q_ids = (await db.execute(q_stmt)).scalars().all()
                for qid in ln_q_ids:
                    eligible_item_ids.add(qid)

                # Approved practice activities
                act_stmt = select(Activity.id).where(
                    Activity.learning_node_id.in_(published_node_ids),
                    Activity.status == "active",
                )
                act_ids = (await db.execute(act_stmt)).scalars().all()
                for aid in act_ids:
                    eligible_item_ids.add(aid)

            attempted_item_ids: Set[uuid.UUID] = set()
            correct_item_ids: Set[uuid.UUID] = set()

            if eligible_item_ids:
                # Responses from assessment attempts
                score_stmt = (
                    select(
                        QuestionVersion.question_id,
                        AssessmentItemScore.result_status,
                    )
                    .join(AssessmentAttempt, AssessmentAttempt.id == AssessmentItemScore.assessment_attempt_id)
                    .join(AssessmentItem, AssessmentItem.id == AssessmentItemScore.assessment_item_id)
                    .join(QuestionVersion, QuestionVersion.id == AssessmentItem.question_version_id)
                    .where(
                        AssessmentAttempt.student_membership_id == mem.id,
                        AssessmentAttempt.institution_id == tenant_id,
                        AssessmentAttempt.status == "submitted",
                        AssessmentAttempt.is_valid == True,
                    )
                )
                q_scores = (await db.execute(score_stmt)).all()
                for q_id, res_status in q_scores:
                    if q_id in eligible_item_ids:
                        attempted_item_ids.add(q_id)
                        if res_status == "correct":
                            correct_item_ids.add(q_id)

                # Responses from practice events
                if published_node_ids:
                    ev_stmt = select(StudentPracticeEvent).where(
                        StudentPracticeEvent.student_membership_id == mem.id,
                        StudentPracticeEvent.learning_node_id.in_(published_node_ids),
                        StudentPracticeEvent.event_type == "answer",
                    )
                    events = (await db.execute(ev_stmt)).scalars().all()
                    for ev in events:
                        if ev.activity_id and ev.activity_id in eligible_item_ids:
                            attempted_item_ids.add(ev.activity_id)
                            if ev.is_correct:
                                correct_item_ids.add(ev.activity_id)

            practice_metric: MetricSummary
            if not eligible_item_ids:
                practice_metric = MetricSummary(
                    status="unsupported",
                    reason="Not tracked / No published question bank",
                )
                practice_has_unsupported = True
            else:
                att_c = len(attempted_item_ids)
                elig_c = len(eligible_item_ids)
                corr_c = len(correct_item_ids)
                practice_metric = MetricSummary(
                    status="available",
                    attempted_count=att_c,
                    eligible_count=elig_c,
                    correct_count=corr_c,
                    percentage=round((att_c / elig_c) * 100, 1) if elig_c > 0 else 0.0,
                )
                total_practice_attempted += att_c
                total_practice_eligible += elig_c
                total_practice_correct += corr_c
                practice_has_available = True

            # 3. Interventions / Support
            intv_stmt = (
                select(Intervention, InterventionAssignment)
                .join(InterventionAssignment, InterventionAssignment.intervention_id == Intervention.id)
                .where(
                    Intervention.course_offering_id == offering.id,
                    Intervention.institution_id == tenant_id,
                    Intervention.status.in_(["active", "published"]),
                    InterventionAssignment.student_membership_id == mem.id,
                )
            )
            intv_rows = (await db.execute(intv_stmt)).all()
            c_active = 0
            c_completed = 0
            for intv, ass in intv_rows:
                if ass.phase_c_completed_at is not None:
                    c_completed += 1
                else:
                    c_active += 1
                    all_active_interventions.append((intv, ass, offering, canon))

            total_active_support += c_active
            total_completed_support += c_completed

            course_title = entry.display_name_override or canon.name
            per_offering.append(
                CourseProgressSummary(
                    course_offering_id=offering.id,
                    curriculum_subject_entry_id=entry.id,
                    subject_code=entry.official_subject_code,
                    subject_name=course_title,
                    learning_topics=topic_metric,
                    teacher_material_practice=practice_metric,
                    remaining_support=RemainingSupportSummary(
                        active_count=c_active,
                        completed_count=c_completed,
                    ),
                )
            )

        # 4. Resolve Deterministic Continue Learning
        continue_learning: Optional[ContinueLearningSummary] = None
        if all_active_interventions:
            best_intv = None
            best_view = None
            best_offering = None
            best_canon = None
            best_rank = 999

            for intv, ass, off, can in all_active_interventions:
                view = await InterventionService.get_student_intervention_view(
                    db=db,
                    tenant_id=tenant_id,
                    course_offering_id=off.id,
                    intervention_id=intv.id,
                    student_membership_id=mem.id,
                )
                action_kind = view.next_action.action_kind if view.next_action else "start_baseline"
                rank = 99
                if "resume" in action_kind:
                    rank = 1
                elif action_kind in ("open_guide", "acknowledge_guide", "start_practice", "start_reassessment"):
                    rank = 2
                elif action_kind == "start_baseline":
                    rank = 3

                if rank < best_rank:
                    best_rank = rank
                    best_intv = intv
                    best_view = view
                    best_offering = off
                    best_canon = can

            if best_intv and best_view and best_offering and best_canon:
                act = best_view.next_action
                step = "study" if act and act.action_kind in ("open_guide", "acknowledge_guide") else ("practice" if act and "practice" in act.action_kind else ("reassessment" if act and "reassessment" in act.action_kind else "baseline"))
                dest_url = f"/quiz?offering={best_offering.id}&intervention={best_intv.id}&step={step}"
                continue_learning = ContinueLearningSummary(
                    title=best_intv.title,
                    concept_name=best_canon.name,
                    course_name=best_canon.name,
                    action_kind=act.action_kind if act else "start_baseline",
                    action_label=act.label if act else "Start baseline",
                    destination_url=dest_url,
                )

        if not continue_learning and all_unlocked_nodes:
            first_node, first_off, first_canon = all_unlocked_nodes[0]
            continue_learning = ContinueLearningSummary(
                title=first_node.title,
                concept_name=first_node.module_title or first_canon.name,
                course_name=first_canon.name,
                action_kind="learn_topic",
                action_label="Start topic",
                destination_url=f"/courses?offering={first_off.id}&node={first_node.id}",
            )

        if not continue_learning:
            continue_learning = ContinueLearningSummary(
                title="All caught up!",
                concept_name=None,
                course_name=None,
                action_kind="all_caught_up",
                action_label="Review courses",
                destination_url="/courses",
            )

        # 5. Build Aggregates
        agg_topic_status = (
            "available" if topics_has_available and not topics_has_unsupported
            else ("partial" if topics_has_available and topics_has_unsupported
                  else "no_content")
        )
        agg_topics = MetricSummary(
            status=agg_topic_status,
            reason="Partial curriculum coverage across enrolled subjects" if agg_topic_status == "partial" else None,
            completed_count=total_topics_completed if topics_has_available else None,
            eligible_count=total_topics_eligible if topics_has_available else None,
            percentage=round((total_topics_completed / total_topics_eligible) * 100, 1) if total_topics_eligible > 0 else None,
        )

        agg_practice_status = (
            "available" if practice_has_available and not practice_has_unsupported
            else ("partial" if practice_has_available and practice_has_unsupported
                  else "unsupported")
        )
        agg_practice = MetricSummary(
            status=agg_practice_status,
            reason="Not tracked / No published question bank" if agg_practice_status == "unsupported" else ("Partial question bank coverage" if agg_practice_status == "partial" else None),
            attempted_count=total_practice_attempted if practice_has_available else None,
            eligible_count=total_practice_eligible if practice_has_available else None,
            correct_count=total_practice_correct if practice_has_available else None,
            percentage=round((total_practice_attempted / total_practice_eligible) * 100, 1) if total_practice_eligible > 0 else None,
        )

        return StudentProgressSummaryResponse(
            learning_topics=agg_topics,
            teacher_material_practice=agg_practice,
            remaining_support=RemainingSupportSummary(
                active_count=total_active_support,
                completed_count=total_completed_support,
            ),
            continue_learning=continue_learning,
            per_offering=per_offering,
            updated_at=now,
        )

