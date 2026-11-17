from __future__ import annotations
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Set
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.exceptions import AppException
from app.modules.learning.models import (
    LearningNode,
    LearningNodeConcept,
    LearningNodePrerequisite,
    LearningNodeQuestion,
    Activity,
    ActivityVersion,
    StudentPracticeSession,
)
from app.modules.assessments.models import StudentLearningNodeProgress
from app.modules.learning.schemas import (
    LearningNodeCreate,
    LearningNodeUpdate,
    LearningNodeOut,
    LearningNodePrerequisiteCreate,
    ActivityCreate,
    ActivityOut,
    ActivityVersionOut,
    CourseLearningMapResponse,
)
from app.modules.learning.scoring import evaluate_activity_response, ActivityEvaluationResult
from app.modules.academics.models import CourseOffering
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

