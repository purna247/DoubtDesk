from __future__ import annotations
import io
import json
import logging
import re
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
import httpx
import xlsxwriter
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.common.exceptions import AppException
from app.modules.assessments.models import (
    Assessment,
    AssessmentVersion,
    AssessmentItem,
    AssessmentItemConceptAllocation,
    AssessmentAttempt,
    AssessmentResponse,
    AssessmentResponseEvent,
    AssessmentItemScore,
    AssessmentConceptScore,
    StudentLearningNodeProgress,
    AssessmentStudentOverride,
)
from app.modules.assessments.schemas import (
    AssessmentCreate,
    AssessmentOut,
    AssessmentVersionOut,
    AssessmentItemOut,
    StartAttemptResponse,
    SaveResponseRequest,
    SubmitAttemptRequest,
    AttemptSummaryOut,
    ItemScoreOut,
    ConceptScoreOut,
    ConceptAllocationOut,
    StudentQuestionPartOut,
    StudentQuestionOptionOut,
    QuizCreateRequest,
    QuizAiGenerateRequest,
    QuizAiGenerateResponse,
    QuizAiQuestionOut,
    FormalQuizCreateRequest,
    StudentOverrideCreate,
    StudentOverrideOut,
    FormalQuizRosterSummaryOut,
    RosterStudentResultOut,
    MarkOverrideRequest,
)
from app.modules.learning.models import LearningNode, Activity, ActivityVersion
from app.modules.learning.scoring import evaluate_activity_response
from app.modules.learning.service import LearningService
from app.modules.academics.models import CourseOffering, CurriculumSubjectEntry, CourseOfferingEnrolment, StudentProgrammeEnrolment
from app.modules.auth.models import InstitutionMembership, User
from app.modules.audit.models import AuditEvent
from app.modules.knowledge.models import Concept, CourseContentConcept, CourseContentVersion
from app.modules.interventions.models import Intervention, InterventionAssignment
from app.modules.questions.models import QuestionVersion, QuestionPart
from app.modules.knowledge.service import KnowledgeService
from app.modules.sources.models import SourceChunk, SourceDocument, SourceDocumentCourseOffering

logger = logging.getLogger(__name__)

_ARABIC_TO_ROMAN = {
    "1": "i", "2": "ii", "3": "iii", "4": "iv", "5": "v",
    "6": "vi", "7": "vii", "8": "viii", "9": "ix", "10": "x",
}
_ROMAN_TO_ARABIC = {v: k for k, v in _ARABIC_TO_ROMAN.items()}


def _build_topic_phrases_and_terms(topic: str) -> tuple[list[str], set[str]]:
    """Build normalized phrase variants (including arabic/roman numeral equivalents) and search terms."""
    cleaned = re.sub(r"\s+", " ", topic.strip().lower())
    phrases = [cleaned] if cleaned else []
    words = [w for w in re.split(r"[^a-z0-9]+", cleaned) if w]
    terms = {w for w in words if len(w) > 2} or set(words)

    for idx, word in enumerate(words):
        alt = _ARABIC_TO_ROMAN.get(word) or _ROMAN_TO_ARABIC.get(word)
        if not alt or idx == 0:
            continue
        prev = words[idx - 1]
        if prev in {"module", "unit", "chapter", "part", "section", "lec", "lecture"}:
            phrases.extend([f"{prev} {word}", f"{prev}-{word}", f"{prev} {alt}", f"{prev}-{alt}"])
            phrases.extend([f"unit {word}", f"unit-{word}", f"unit {alt}", f"unit-{alt}"])
    return list(dict.fromkeys(p for p in phrases if p)), terms


_CONCEPT_STOPWORDS = {
    "the", "and", "for", "with", "from", "into", "that", "this", "which", "what",
    "how", "why", "when", "where", "are", "was", "were", "will", "can", "not",
    "system", "systems", "module", "unit", "chapter", "topic", "quiz", "question",
    "based", "using", "used", "covered", "under", "within", "between", "according",
}

_METADATA_CONCEPT_PREFIXES = (
    "sub_code:", "course outcomes:", "detailed syllabus", "text books:",
    "references books:", "co-po mapping:", "co/po |", "prerequisites |",
    "(1:low", "module-", "co1 |", "co2 |", "co3 |", "co4 |", "co5 |", "co6 |",
)


def _is_metadata_concept_name(name: str) -> bool:
    low = (name or "").strip().lower()
    if not low:
        return True
    if any(low.startswith(prefix) for prefix in _METADATA_CONCEPT_PREFIXES):
        return True
    if any(pub in low for pub in ("first edition", "oxford university press", "cambridge university press", "springer,", "intechopen", "(editors)")):
        return True
    if re.search(r",\s*(?:19|20)\d{2}\.?\s*$", low):
        return True
    return False


def _tokenize_concept_text(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", (text or "").lower())
    return {w for w in words if len(w) > 2 and w not in _CONCEPT_STOPWORDS}


def _match_concepts_for_text(concepts: list[Concept], text: str, max_concepts: int = 2) -> list[uuid.UUID]:
    if not concepts or not (text or "").strip():
        return []
    low_text = re.sub(r"\s+", " ", text.lower())
    text_tokens = _tokenize_concept_text(low_text)
    if not text_tokens:
        return []

    scored: list[tuple[float, int, uuid.UUID]] = []
    for c in concepts:
        cname = re.sub(r"\s+", " ", (c.canonical_name or "").strip().lower())
        if not cname:
            continue
        score = 0.0
        if len(cname) >= 4 and cname in low_text:
            score += 10.0
        c_tokens = _tokenize_concept_text(cname)
        if c_tokens:
            overlap = len(c_tokens & text_tokens)
            if overlap > 0:
                score += overlap * 2.0 + (overlap / len(c_tokens)) * 3.0
        if score > 0.0:
            scored.append((score, len(c_tokens), c.id))

    if not scored:
        return []
    scored.sort(key=lambda row: (-row[0], -row[1]))
    top_score = scored[0][0]
    selected = [scored[0][2]]
    for score, _, cid in scored[1:]:
        if len(selected) >= max_concepts:
            break
        if score >= max(4.0, top_score * 0.6):
            selected.append(cid)
    return selected


async def _load_course_concepts(
    db: AsyncSession,
    offering_id: uuid.UUID,
    tenant_id: uuid.UUID,
) -> list[Concept]:
    """Load candidate course concepts from the published (or latest) course content version."""
    ver_stmt = (
        select(CourseContentVersion)
        .where(
            CourseContentVersion.course_offering_id == offering_id,
            CourseContentVersion.institution_id == tenant_id,
        )
        .order_by(
            (CourseContentVersion.status == "published").desc(),
            CourseContentVersion.version_number.desc(),
            CourseContentVersion.updated_at.desc(),
        )
    )
    ccv = (await db.execute(ver_stmt)).scalars().first()
    if not ccv:
        return []
    c_stmt = (
        select(Concept)
        .join(CourseContentConcept, CourseContentConcept.concept_id == Concept.id)
        .where(
            CourseContentConcept.course_content_version_id == ccv.id,
            Concept.institution_id == tenant_id,
            Concept.status == "active",
        )
    )
    all_concepts = list((await db.execute(c_stmt)).scalars().all())
    topical = [c for c in all_concepts if not _is_metadata_concept_name(c.canonical_name)]
    return topical or all_concepts


def _allocate_item_concepts(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    item_id: uuid.UUID,
    marks_available: float,
    concept_ids: list[uuid.UUID],
) -> None:
    """Split an assessment item's marks evenly across its concepts without mark duplication."""
    unique_ids = list(dict.fromkeys(concept_ids))
    if not unique_ids:
        return
    n = len(unique_ids)
    per_concept = round(marks_available / n, 2)
    remaining = round(marks_available, 2)
    for idx, cid in enumerate(unique_ids):
        alloc_marks = remaining if idx == n - 1 else per_concept
        remaining = round(remaining - alloc_marks, 2)
        db.add(
            AssessmentItemConceptAllocation(
                institution_id=tenant_id,
                assessment_item_id=item_id,
                concept_id=cid,
                marks_available=alloc_marks,
            )
        )


class AssessmentService:

    @staticmethod
    async def create_assessment(
        db: AsyncSession,
        offering_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        data: AssessmentCreate,
    ) -> Assessment:
        offering = await db.get(CourseOffering, offering_id)
        if not offering or offering.institution_id != tenant_id:
            raise AppException(status_code=404, code="OFFERING_NOT_FOUND", message="Course offering not found.")

        v_data = data.version

        assessment = Assessment(
            institution_id=tenant_id,
            course_offering_id=offering_id,
            learning_node_id=data.learning_node_id,
            assessment_type=data.assessment_type,
            title=data.title,
            description=data.description,
            status="draft",
            created_by_user_id=user_id,
        )
        db.add(assessment)
        await db.flush()

        version = AssessmentVersion(
            institution_id=tenant_id,
            assessment_id=assessment.id,
            version_number=1,
            status="draft",
            duration_seconds=v_data.duration_seconds,
            max_attempts=v_data.max_attempts,
            created_by_user_id=user_id,
        )
        db.add(version)
        await db.flush()

        for item_in in v_data.items:
            item = AssessmentItem(
                institution_id=tenant_id,
                assessment_version_id=version.id,
                question_version_id=item_in.question_version_id,
                activity_version_id=item_in.activity_version_id,
                sequence_no=item_in.sequence_no,
                marks_available=item_in.marks_available,
                is_required=item_in.is_required,
            )
            db.add(item)
            await db.flush()

            for alloc_in in item_in.concept_allocations:
                alloc = AssessmentItemConceptAllocation(
                    institution_id=tenant_id,
                    assessment_item_id=item.id,
                    concept_id=alloc_in.concept_id,
                    marks_available=alloc_in.marks_available,
                    allocation_source="teacher_override",
                )
                db.add(alloc)

        await db.commit()
        await db.refresh(assessment)
        return assessment

    @staticmethod
    async def publish_assessment(
        db: AsyncSession,
        assessment_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> Assessment:
        assessment = await db.get(Assessment, assessment_id)
        if not assessment or assessment.institution_id != tenant_id:
            raise AppException(status_code=404, code="ASSESSMENT_NOT_FOUND", message="Assessment not found.")

        # Fetch latest version
        v_stmt = (
            select(AssessmentVersion)
            .options(selectinload(AssessmentVersion.items))
            .where(AssessmentVersion.assessment_id == assessment_id)
            .order_by(AssessmentVersion.version_number.desc())
            .limit(1)
        )
        res = await db.execute(v_stmt)
        version = res.scalars().first()
        if not version or not version.items:
            raise AppException(
                status_code=400,
                code="EMPTY_ASSESSMENT",
                message="Cannot publish an assessment with no assessment items.",
            )

        now = datetime.now(timezone.utc)
        assessment.status = "published"
        version.status = "published"
        version.published_at = now

        await db.commit()
        await db.refresh(assessment)
        return assessment

    @staticmethod
    async def start_attempt(
        db: AsyncSession,
        assessment_id: uuid.UUID,
        tenant_id: uuid.UUID,
        student_membership_id: uuid.UUID,
        student_id: uuid.UUID,
        idempotency_key: Optional[str] = None,
    ) -> StartAttemptResponse:
        stmt = (
            select(Assessment)
            .options(
                selectinload(Assessment.versions)
                .selectinload(AssessmentVersion.items)
                .selectinload(AssessmentItem.concept_allocations),
                selectinload(Assessment.versions)
                .selectinload(AssessmentVersion.items)
                .selectinload(AssessmentItem.activity_version),
                selectinload(Assessment.versions)
                .selectinload(AssessmentVersion.items)
                .selectinload(AssessmentItem.question_version),
                selectinload(Assessment.versions)
                .selectinload(AssessmentVersion.items)
                .selectinload(AssessmentItem.question_version)
                .selectinload(QuestionVersion.parts)
                .selectinload(QuestionPart.options),
            )
            .where(Assessment.id == assessment_id, Assessment.institution_id == tenant_id)
        )
        res = await db.execute(stmt)
        assessment = res.scalars().first()
        if not assessment:
            raise AppException(status_code=404, code="ASSESSMENT_NOT_FOUND", message="Assessment not found.")

        if assessment.status != "published":
            raise AppException(
                status_code=400,
                code="ASSESSMENT_NOT_PUBLISHED",
                message="Assessment is not published yet.",
            )

        await KnowledgeService.verify_student_access(
            db=db,
            offering_id=assessment.course_offering_id,
            tenant_id=tenant_id,
            user_id=student_id,
        )

        if assessment.assessment_type.startswith("intervention_"):
            phase_column = {
                "intervention_baseline": Intervention.phase_a_assessment_id,
                "intervention_practice": Intervention.phase_b_practice_assessment_id,
                "intervention_post": Intervention.phase_c_assessment_id,
            }[assessment.assessment_type]
            bound_stmt = select(Intervention.id).where(
                Intervention.institution_id == tenant_id,
                Intervention.course_offering_id == assessment.course_offering_id,
                Intervention.status.in_(["active", "published"]),
                phase_column == assessment.id,
            )
            is_bound = (await db.execute(bound_stmt)).scalars().first() is not None

            if is_bound:
                assignment_stmt = (
                    select(Intervention, InterventionAssignment)
                    .join(InterventionAssignment, InterventionAssignment.intervention_id == Intervention.id)
                    .where(
                        Intervention.institution_id == tenant_id,
                        Intervention.course_offering_id == assessment.course_offering_id,
                        Intervention.status.in_(["active", "published"]),
                        phase_column == assessment.id,
                        InterventionAssignment.student_membership_id == student_membership_id,
                    )
                )
                assignments = (await db.execute(assignment_stmt)).all()
                eligible = False
                for intervention, assignment in assignments:
                    if assessment.assessment_type == "intervention_baseline":
                        eligible = True
                    elif assessment.assessment_type == "intervention_practice":
                        eligible = assignment.phase_a_completed_at is not None
                    else:
                        eligible = assignment.phase_b_completed_at is not None
                    if eligible:
                        break
                if not eligible:
                    raise AppException(
                        status_code=403,
                        code="INTERVENTION_PHASE_LOCKED",
                        message="This assessment is not assigned to you or its intervention phase is still locked.",
                    )

        version = next((v for v in assessment.versions if v.status == "published"), None)
        if not version:
            raise AppException(status_code=404, code="NO_PUBLISHED_VERSION", message="No published version available.")

        now = datetime.now(timezone.utc)

        # Check formal quiz window and makeup overrides
        active_makeup: Optional[AssessmentStudentOverride] = None
        if assessment.is_formal_quiz:
            makeup_stmt = select(AssessmentStudentOverride).where(
                AssessmentStudentOverride.assessment_id == assessment.id,
                AssessmentStudentOverride.student_membership_id == student_membership_id,
                AssessmentStudentOverride.override_type == "makeup_window",
                AssessmentStudentOverride.status == "active",
            )
            active_makeup = (await db.execute(makeup_stmt)).scalars().first()

            if active_makeup:
                if active_makeup.start_at:
                    start_t = active_makeup.start_at if active_makeup.start_at.tzinfo else active_makeup.start_at.replace(tzinfo=timezone.utc)
                    if now < start_t:
                        raise AppException(
                            status_code=400,
                            code="QUIZ_NOT_STARTED",
                            message=f"Makeup quiz window opens at {start_t.isoformat()}.",
                        )
                if active_makeup.end_at:
                    end_t = active_makeup.end_at if active_makeup.end_at.tzinfo else active_makeup.end_at.replace(tzinfo=timezone.utc)
                    if now > end_t:
                        raise AppException(
                            status_code=400,
                            code="QUIZ_WINDOW_CLOSED",
                            message="Makeup quiz window has closed.",
                        )
            else:
                if assessment.scheduled_start_at:
                    start_t = assessment.scheduled_start_at if assessment.scheduled_start_at.tzinfo else assessment.scheduled_start_at.replace(tzinfo=timezone.utc)
                    if now < start_t:
                        raise AppException(
                            status_code=400,
                            code="QUIZ_NOT_STARTED",
                            message=f"Formal quiz window opens at {start_t.isoformat()}.",
                        )
                if assessment.scheduled_end_at:
                    end_t = assessment.scheduled_end_at if assessment.scheduled_end_at.tzinfo else assessment.scheduled_end_at.replace(tzinfo=timezone.utc)
                    if now > end_t:
                        raise AppException(
                            status_code=400,
                            code="QUIZ_WINDOW_CLOSED",
                            message="Formal quiz window has closed.",
                        )

        # Check existing attempts
        att_stmt = (
            select(AssessmentAttempt)
            .where(
                AssessmentAttempt.assessment_version_id == version.id,
                AssessmentAttempt.student_membership_id == student_membership_id,
            )
            .order_by(AssessmentAttempt.attempt_number.desc())
        )
        existing_attempts = (await db.execute(att_stmt)).scalars().all()

        # Check for active attempt
        active_attempt = next((a for a in existing_attempts if a.status == "in_progress"), None)
        if active_attempt:
            # Check timer expiry
            if active_attempt.expires_at:
                exp = active_attempt.expires_at
                if exp.tzinfo is None:
                    exp = exp.replace(tzinfo=timezone.utc)
                if now > exp:
                    active_attempt.status = "expired"
                    await db.commit()
                else:
                    return await AssessmentService._build_start_attempt_response(db, active_attempt, version)

        # Check max attempts: if active_makeup, allowed count is expanded by 1
        effective_max_attempts = version.max_attempts
        if active_makeup and effective_max_attempts is not None:
            effective_max_attempts += 1

        if effective_max_attempts and len(existing_attempts) >= effective_max_attempts:
            raise AppException(
                status_code=400,
                code="MAX_ATTEMPTS_REACHED",
                message=f"Maximum allowed attempts reached for this assessment. Contact faculty for makeup authorization.",
            )

        new_attempt_num = len(existing_attempts) + 1

        # Expiry clamping: latecomer gets only remaining time until scheduled window closes
        expires_at = None
        if version.duration_seconds:
            normal_expiry = now + timedelta(seconds=version.duration_seconds)
            effective_deadline = None
            if active_makeup and active_makeup.end_at:
                effective_deadline = active_makeup.end_at if active_makeup.end_at.tzinfo else active_makeup.end_at.replace(tzinfo=timezone.utc)
            elif assessment.is_formal_quiz and assessment.scheduled_end_at:
                effective_deadline = assessment.scheduled_end_at if assessment.scheduled_end_at.tzinfo else assessment.scheduled_end_at.replace(tzinfo=timezone.utc)

            if effective_deadline:
                expires_at = min(normal_expiry, effective_deadline)
            else:
                expires_at = normal_expiry
        elif assessment.is_formal_quiz and assessment.scheduled_end_at:
            if active_makeup and active_makeup.end_at:
                expires_at = active_makeup.end_at if active_makeup.end_at.tzinfo else active_makeup.end_at.replace(tzinfo=timezone.utc)
            else:
                expires_at = assessment.scheduled_end_at if assessment.scheduled_end_at.tzinfo else assessment.scheduled_end_at.replace(tzinfo=timezone.utc)

        attempt = AssessmentAttempt(
            institution_id=tenant_id,
            assessment_version_id=version.id,
            student_membership_id=student_membership_id,
            attempt_number=new_attempt_num,
            status="in_progress",
            scoring_status="not_scored",
            is_valid=False,
            started_at=now,
            expires_at=expires_at,
            idempotency_key=idempotency_key,
        )
        db.add(attempt)
        await db.flush()

        if active_makeup:
            active_makeup.status = "used"
            active_makeup.resulting_attempt_id = attempt.id

        # Pre-populate empty responses for each item
        for item in version.items:
            resp = AssessmentResponse(
                institution_id=tenant_id,
                assessment_attempt_id=attempt.id,
                assessment_item_id=item.id,
                response_payload_json={},
                response_state="empty",
            )
            db.add(resp)

        await db.commit()
        await db.refresh(attempt)
        return await AssessmentService._build_start_attempt_response(db, attempt, version)

    @staticmethod
    async def _build_start_attempt_response(
        db: AsyncSession,
        attempt: AssessmentAttempt,
        version: AssessmentVersion,
    ) -> StartAttemptResponse:
        # Load responses
        r_stmt = select(AssessmentResponse).where(AssessmentResponse.assessment_attempt_id == attempt.id)
        responses = (await db.execute(r_stmt)).scalars().all()
        saved_map = {
            str(r.assessment_item_id): {
                "payload": r.response_payload_json or {},
                "state": r.response_state,
            }
            for r in responses
        }

        # Build items without answer keys
        assessment = version.assessment
        if not assessment:
            assessment = await db.get(Assessment, version.assessment_id)

        items = list(version.items or [])
        if assessment and assessment.shuffle_questions:
            # Deterministic per-student attempt shuffle using SHA-256
            items.sort(key=lambda it: hashlib.sha256(f"{attempt.id}:item:{it.id}".encode("utf-8")).hexdigest())

        items_out: List[AssessmentItemOut] = []
        for idx, it in enumerate(items, start=1):
            act_v = it.activity_version
            allocs_out = [
                ConceptAllocationOut(concept_id=a.concept_id, marks_available=float(a.marks_available))
                for a in it.concept_allocations
            ]

            student_payload = act_v.student_payload_json if act_v else None
            if student_payload and isinstance(student_payload, dict) and assessment and assessment.shuffle_options:
                if "options" in student_payload and isinstance(student_payload["options"], list):
                    opts_copy = list(student_payload["options"])
                    opts_copy.sort(
                        key=lambda o: hashlib.sha256(
                            f"{attempt.id}:opt:{o.get('option_id', '')}".encode("utf-8")
                        ).hexdigest()
                    )
                    student_payload = {**student_payload, "options": opts_copy}

            q_parts = []
            for part in (it.question_version.parts if it.question_version else []):
                part_opts = [
                    StudentQuestionOptionOut(
                        id=option.id,
                        option_key=option.option_key,
                        display_text=option.display_text,
                    ) for option in part.options
                ]
                if assessment and assessment.shuffle_options:
                    part_opts.sort(
                        key=lambda o: hashlib.sha256(
                            f"{attempt.id}:opt:{o.id}".encode("utf-8")
                        ).hexdigest()
                    )
                q_parts.append(
                    StudentQuestionPartOut(
                        id=part.id,
                        part_key=part.part_key,
                        part_prompt=part.part_prompt,
                        sequence_no=part.sequence_no,
                        marks_available=float(part.marks_available),
                        answer_type=part.answer_type,
                        options=part_opts,
                    )
                )

            items_out.append(
                AssessmentItemOut(
                    id=it.id,
                    sequence_no=idx,
                    marks_available=float(it.marks_available),
                    is_required=it.is_required,
                    question_version_id=it.question_version_id,
                    activity_version_id=it.activity_version_id,
                    activity_type=act_v.activity_type if act_v else None,
                    title=act_v.title if act_v else None,
                    student_payload_json=student_payload,
                    question_prompt=(it.question_version.prompt_text if it.question_version else None),
                    question_parts=q_parts,
                    concept_allocations=allocs_out,
                )
            )

        return StartAttemptResponse(
            attempt_id=attempt.id,
            assessment_version_id=version.id,
            attempt_number=attempt.attempt_number,
            status=attempt.status,
            started_at=attempt.started_at,
            expires_at=attempt.expires_at,
            duration_seconds=version.duration_seconds,
            items=items_out,
            saved_responses=saved_map,
        )

    @staticmethod
    async def save_response(
        db: AsyncSession,
        attempt_id: uuid.UUID,
        tenant_id: uuid.UUID,
        student_membership_id: uuid.UUID,
        data: SaveResponseRequest,
    ) -> None:
        attempt = await db.get(AssessmentAttempt, attempt_id)
        if not attempt or attempt.institution_id != tenant_id:
            raise AppException(status_code=404, code="ATTEMPT_NOT_FOUND", message="Attempt not found.")

        if attempt.student_membership_id != student_membership_id:
            raise AppException(status_code=403, code="NOT_ATTEMPT_OWNER", message="Not your assessment attempt.")

        now = datetime.now(timezone.utc)
        if attempt.status != "in_progress":
            raise AppException(status_code=400, code="ATTEMPT_NOT_ACTIVE", message=f"Attempt in {attempt.status} status.")

        # Check timer expiry
        if attempt.expires_at:
            exp = attempt.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if now > exp:
                attempt.status = "expired"
                await db.commit()
                raise AppException(
                    status_code=400,
                    code="ATTEMPT_EXPIRED",
                    message="Assessment time limit has expired. Submission locked.",
                )

        # Update or create response projection
        r_stmt = select(AssessmentResponse).where(
            AssessmentResponse.assessment_attempt_id == attempt_id,
            AssessmentResponse.assessment_item_id == data.item_id,
        )
        res = await db.execute(r_stmt)
        resp = res.scalars().first()

        if resp:
            resp.response_payload_json = data.response_payload
            resp.response_state = data.response_state
            resp.last_saved_at = now
            if not resp.first_saved_at:
                resp.first_saved_at = now
            if not resp.visited_at:
                resp.visited_at = now
        else:
            resp = AssessmentResponse(
                institution_id=tenant_id,
                assessment_attempt_id=attempt_id,
                assessment_item_id=data.item_id,
                response_payload_json=data.response_payload,
                response_state=data.response_state,
                visited_at=now,
                first_saved_at=now,
                last_saved_at=now,
            )
            db.add(resp)

        # Append response event
        db.add(
            AssessmentResponseEvent(
                institution_id=tenant_id,
                assessment_attempt_id=attempt_id,
                assessment_item_id=data.item_id,
                event_type="answer_changed" if data.response_state == "answered" else "draft_saved",
                response_payload_json=data.response_payload,
                client_event_id=data.client_event_id,
                server_received_at=now,
            )
        )
        attempt.last_synced_at = now
        await db.commit()

    @staticmethod
    async def submit_attempt(
        db: AsyncSession,
        attempt_id: uuid.UUID,
        tenant_id: uuid.UUID,
        student_membership_id: uuid.UUID,
    ) -> AttemptSummaryOut:
        stmt = (
            select(AssessmentAttempt)
            .options(
                selectinload(AssessmentAttempt.assessment_version)
                .selectinload(AssessmentVersion.assessment),
                selectinload(AssessmentAttempt.assessment_version)
                .selectinload(AssessmentVersion.items)
                .selectinload(AssessmentItem.concept_allocations),
                selectinload(AssessmentAttempt.assessment_version)
                .selectinload(AssessmentVersion.items)
                .selectinload(AssessmentItem.activity_version),
                selectinload(AssessmentAttempt.assessment_version)
                .selectinload(AssessmentVersion.items)
                .selectinload(AssessmentItem.question_version)
                .selectinload(QuestionVersion.parts)
                .selectinload(QuestionPart.options),
                selectinload(AssessmentAttempt.responses),
            )
            .where(AssessmentAttempt.id == attempt_id, AssessmentAttempt.institution_id == tenant_id)
        )
        res = await db.execute(stmt)
        attempt = res.scalars().first()
        if not attempt:
            raise AppException(status_code=404, code="ATTEMPT_NOT_FOUND", message="Attempt not found.")

        if attempt.student_membership_id != student_membership_id:
            raise AppException(status_code=403, code="NOT_ATTEMPT_OWNER", message="Not your assessment attempt.")

        # Idempotent submit
        if attempt.status == "submitted":
            return await AssessmentService.get_attempt_summary(db, attempt_id, tenant_id)

        now = datetime.now(timezone.utc)
        is_expired = False
        if attempt.expires_at:
            exp = attempt.expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if now > exp:
                is_expired = True

        version = attempt.assessment_version
        items = version.items
        responses_by_item = {r.assessment_item_id: r for r in attempt.responses}

        total_awarded = 0.0
        total_available = 0.0
        has_manual_review = False

        for item in items:
            item_avail = float(item.marks_available)
            total_available += item_avail

            resp = responses_by_item.get(item.id)
            resp_data = resp.response_payload_json if resp and resp.response_payload_json else {}

            act_v = item.activity_version
            if act_v and resp_data:
                eval_res = evaluate_activity_response(
                    activity_type=act_v.activity_type,
                    response_data=resp_data,
                    answer_key=act_v.answer_key_json,
                    scoring_config=act_v.scoring_config_json,
                )
                item_award = min(item_avail, max(0.0, float(eval_res.marks_awarded)))
                status_label = "correct" if eval_res.is_correct else ("partially_correct" if item_award > 0 else "incorrect")
            elif item.question_version and resp_data:
                parts = item.question_version.parts
                answers = resp_data.get("answers") if isinstance(resp_data.get("answers"), dict) else {}
                if len(parts) == 1 and "selected_option_id" in resp_data and not answers:
                    answers = {str(parts[0].id): resp_data["selected_option_id"]}
                item_award = 0.0
                manual_item = False
                for part in parts:
                    if part.answer_type != "mcq" or not part.options:
                        manual_item = True
                        continue
                    selected = answers.get(str(part.id), answers.get(part.part_key))
                    correct_option = next((option for option in part.options if option.is_correct), None)
                    if selected is not None and correct_option and str(selected) in {str(correct_option.id), correct_option.option_key}:
                        item_award += float(part.marks_available)
                if manual_item:
                    has_manual_review = True
                    status_label = "manual_review_required"
                else:
                    status_label = "correct" if item_award >= item_avail else ("partially_correct" if item_award > 0 else "incorrect")
                item_award = min(item_avail, max(0.0, item_award))
            else:
                item_award = 0.0
                status_label = "not_assessed" if not resp_data else "incorrect"

            # Record explicit, teacher-approved misconception evidence for each selected
            # distractor. Question-part responses are normally saved in `answers`, keyed
            # by part ID; single-part clients may also send selected_option_id directly.
            if resp_data and item.question_version:
                answer_map = resp_data.get("answers")
                answer_map = answer_map if isinstance(answer_map, dict) else {}
                parts = item.question_version.parts
                from app.modules.analytics.service import AnalyticsService

                for part in parts:
                    selected = answer_map.get(str(part.id), answer_map.get(part.part_key))
                    if selected is None and len(parts) == 1:
                        selected = resp_data.get("selected_option_id")
                    if selected is None:
                        continue

                    selected_option = next(
                        (
                            option
                            for option in part.options
                            if str(option.id) == str(selected) or option.option_key == str(selected)
                        ),
                        None,
                    )
                    if selected_option and not selected_option.is_correct and selected_option.misconception_id:
                        await AnalyticsService.record_misconception_if_tagged(
                            db=db,
                            tenant_id=tenant_id,
                            course_offering_id=version.assessment.course_offering_id,
                            attempt_id=attempt.id,
                            student_membership_id=student_membership_id,
                            item_id=item.id,
                            response_id=resp.id if resp else None,
                            selected_option_id=selected_option.id,
                        )

            total_awarded += item_award

            db.add(
                AssessmentItemScore(
                    institution_id=tenant_id,
                    assessment_attempt_id=attempt.id,
                    assessment_item_id=item.id,
                    marks_awarded=item_award,
                    marks_available=item_avail,
                    result_status=status_label,
                    scored_at=now,
                    scoring_version=1,
                )
            )

            # Concept mark attribution (no mark duplication)
            ratio = (item_award / item_avail) if item_avail > 0 else 0.0
            for alloc in item.concept_allocations:
                c_avail = float(alloc.marks_available)
                c_award = round(c_avail * ratio, 2)
                db.add(
                    AssessmentConceptScore(
                        institution_id=tenant_id,
                        course_offering_id=version.assessment.course_offering_id,
                        assessment_attempt_id=attempt.id,
                        assessment_item_id=item.id,
                        question_id=item.question_version_id,
                        concept_id=alloc.concept_id,
                        marks_awarded=c_award,
                        marks_available=c_avail,
                        scored_at=now,
                    )
                )

        attempt.status = "expired" if is_expired else "submitted"
        attempt.scoring_status = "manual_review_required" if has_manual_review else "scored"
        attempt.is_valid = not has_manual_review
        attempt.submitted_at = now
        attempt.finalized_at = now
        attempt.marks_awarded = round(total_awarded, 2)
        attempt.marks_available = round(total_available, 2)
        attempt.score_fraction = round(total_awarded / total_available, 5) if total_available > 0 else 0.0

        # Update node progress if linked
        if version.assessment.learning_node_id:
            prog_stmt = select(StudentLearningNodeProgress).where(
                StudentLearningNodeProgress.student_membership_id == student_membership_id,
                StudentLearningNodeProgress.learning_node_id == version.assessment.learning_node_id,
            )
            prog = (await db.execute(prog_stmt)).scalars().first()
            if not prog:
                prog = StudentLearningNodeProgress(
                    institution_id=tenant_id,
                    student_membership_id=student_membership_id,
                    learning_node_id=version.assessment.learning_node_id,
                    progress_status="completed",
                    first_started_at=attempt.started_at,
                    completed_at=now,
                    latest_attempt_id=attempt.id,
                )
                db.add(prog)
            else:
                prog.progress_status = "completed"
                prog.completed_at = now
                prog.latest_attempt_id = attempt.id

        await db.commit()
        submitted_assessment = version.assessment
        if submitted_assessment and submitted_assessment.assessment_type.startswith("intervention_"):
            phase_column = {
                "intervention_baseline": Intervention.phase_a_assessment_id,
                "intervention_practice": Intervention.phase_b_practice_assessment_id,
                "intervention_post": Intervention.phase_c_assessment_id,
            }[submitted_assessment.assessment_type]
            intervention_ids = (await db.execute(
                select(Intervention.id).where(
                    Intervention.institution_id == tenant_id,
                    Intervention.course_offering_id == submitted_assessment.course_offering_id,
                    phase_column == submitted_assessment.id,
                )
            )).scalars().all()
            from app.modules.interventions.service import InterventionService
            for intervention_id in intervention_ids:
                await InterventionService.sync_student_progress(
                    db, tenant_id, intervention_id, student_membership_id
                )
        return await AssessmentService.get_attempt_summary(db, attempt.id, tenant_id)

    @staticmethod
    def serialize_assessment(
        assessment: Assessment,
        *,
        include_answer_key: bool = False,
        published_only: bool = False,
    ) -> AssessmentOut:
        """Serialize an Assessment with its latest (or published) version and items."""
        versions = assessment.versions or []
        version = (
            next((v for v in versions if v.status == "published"), None)
            if published_only
            else (versions[0] if versions else None)
        )
        version_out = None
        if version is not None:
            items_out: List[AssessmentItemOut] = []
            for it in (version.items or []):
                act_v = it.activity_version
                q_v = it.question_version
                allocs_out = [
                    ConceptAllocationOut(concept_id=a.concept_id, marks_available=float(a.marks_available))
                    for a in (it.concept_allocations or [])
                ]
                items_out.append(
                    AssessmentItemOut(
                        id=it.id,
                        sequence_no=it.sequence_no,
                        marks_available=float(it.marks_available),
                        is_required=it.is_required,
                        question_version_id=it.question_version_id,
                        activity_version_id=it.activity_version_id,
                        activity_type=act_v.activity_type if act_v else None,
                        title=act_v.title if act_v else None,
                        student_payload_json=act_v.student_payload_json if act_v else None,
                        answer_key_json=(act_v.answer_key_json if (include_answer_key and act_v) else None),
                        question_prompt=(q_v.prompt_text if q_v else None),
                        concept_allocations=allocs_out,
                    )
                )
            version_out = AssessmentVersionOut(
                id=version.id,
                assessment_id=version.assessment_id,
                version_number=version.version_number,
                status=version.status,
                duration_seconds=version.duration_seconds,
                max_attempts=version.max_attempts,
                published_at=version.published_at,
                created_at=version.created_at,
                items=items_out,
            )

        return AssessmentOut(
            id=assessment.id,
            institution_id=assessment.institution_id,
            course_offering_id=assessment.course_offering_id,
            learning_node_id=assessment.learning_node_id,
            assessment_type=assessment.assessment_type,
            title=assessment.title,
            description=assessment.description,
            status=assessment.status,
            is_formal_quiz=bool(assessment.is_formal_quiz),
            scheduled_start_at=assessment.scheduled_start_at,
            scheduled_end_at=assessment.scheduled_end_at,
            shuffle_questions=bool(assessment.shuffle_questions),
            shuffle_options=bool(assessment.shuffle_options),
            is_finalized=bool(assessment.is_finalized),
            finalized_at=assessment.finalized_at,
            finalized_by_user_id=assessment.finalized_by_user_id,
            created_at=assessment.created_at,
            latest_version=version_out,
        )

    @staticmethod
    async def load_assessment_full(
        db: AsyncSession,
        assessment_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> Assessment:
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
            .where(Assessment.id == assessment_id, Assessment.institution_id == tenant_id)
        )
        assessment = (await db.execute(stmt)).scalars().first()
        if not assessment:
            raise AppException(status_code=404, code="ASSESSMENT_NOT_FOUND", message="Assessment not found.")
        return assessment

    @staticmethod
    async def unpublish_assessment(
        db: AsyncSession,
        assessment_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> Assessment:
        assessment = await AssessmentService.load_assessment_full(db, assessment_id, tenant_id)
        assessment.status = "draft"
        if assessment.versions:
            assessment.versions[0].status = "draft"
        await db.commit()
        return await AssessmentService.load_assessment_full(db, assessment_id, tenant_id)

    @staticmethod
    async def delete_or_archive_assessment(
        db: AsyncSession,
        assessment_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> None:
        assessment = await AssessmentService.load_assessment_full(db, assessment_id, tenant_id)
        version_ids = [v.id for v in (assessment.versions or [])]
        attempt_count = 0
        if version_ids:
            attempt_count = (
                await db.execute(
                    select(func.count(AssessmentAttempt.id)).where(
                        AssessmentAttempt.assessment_version_id.in_(version_ids)
                    )
                )
            ).scalar() or 0

        if attempt_count > 0:
            assessment.status = "archived"
        else:
            await db.delete(assessment)
        await db.commit()

    @staticmethod
    async def create_quiz(
        db: AsyncSession,
        offering_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        data: QuizCreateRequest,
        commit: bool = True,
    ) -> Assessment:
        """Atomically author an MCQ quiz assessment backed by LearningNode/ActivityVersion."""
        offering = await db.get(CourseOffering, offering_id)
        if not offering or offering.institution_id != tenant_id:
            raise AppException(status_code=404, code="OFFERING_NOT_FOUND", message="Course offering not found.")

        # Reuse latest learning node or provision a default published node for course quizzes
        node_stmt = (
            select(LearningNode)
            .where(
                LearningNode.course_offering_id == offering_id,
                LearningNode.institution_id == tenant_id,
            )
            .order_by(LearningNode.sequence_no.asc())
            .limit(1)
        )
        node = (await db.execute(node_stmt)).scalars().first()
        if not node:
            cv_stmt = (
                select(CourseContentVersion)
                .where(
                    CourseContentVersion.course_offering_id == offering_id,
                    CourseContentVersion.institution_id == tenant_id,
                )
                .order_by(CourseContentVersion.version_number.desc())
                .limit(1)
            )
            content_v = (await db.execute(cv_stmt)).scalars().first()
            if not content_v:
                content_v = await KnowledgeService.get_or_create_draft_version(
                    db=db, offering_id=offering_id, tenant_id=tenant_id, user_id=user_id
                )
            node = LearningNode(
                institution_id=tenant_id,
                course_offering_id=offering_id,
                course_content_version_id=content_v.id,
                node_code="QUIZZES",
                title="Course Quizzes & Assessments",
                description="Faculty authored practice quizzes and diagnostic assessments.",
                sequence_no=1,
                status="published",
                published_at=datetime.now(timezone.utc),
                created_by_user_id=user_id,
            )
            db.add(node)
            await db.flush()

        now = datetime.now(timezone.utc)
        target_status = "published" if data.publish else "draft"

        requested_source_ids = {source_id for question in data.questions for source_id in question.source_chunk_ids}
        valid_source_ids: set[uuid.UUID] = set()
        if requested_source_ids:
            valid_source_ids = set((await db.execute(
                select(SourceChunk.id)
                .join(SourceDocument, SourceDocument.id == SourceChunk.source_document_id)
                .join(SourceDocumentCourseOffering, SourceDocumentCourseOffering.source_document_id == SourceDocument.id)
                .where(
                    SourceChunk.id.in_(requested_source_ids),
                    SourceChunk.institution_id == tenant_id,
                    SourceDocument.institution_id == tenant_id,
                    SourceDocument.status == "processed",
                    SourceDocument.publication_status != "rejected",
                    SourceDocumentCourseOffering.course_offering_id == offering_id,
                )
            )).scalars().all())
            if valid_source_ids != requested_source_ids:
                raise AppException(
                    status_code=400,
                    code="INVALID_QUIZ_SOURCE_REFERENCE",
                    message="A quiz source reference is not part of reviewed material for this course.",
                )

        assessment = Assessment(
            institution_id=tenant_id,
            course_offering_id=offering_id,
            learning_node_id=node.id,
            assessment_type=data.assessment_type,
            title=data.title.strip(),
            description=(data.description or "").strip() or None,
            status=target_status,
            created_by_user_id=user_id,
        )
        db.add(assessment)
        await db.flush()

        version = AssessmentVersion(
            institution_id=tenant_id,
            assessment_id=assessment.id,
            version_number=1,
            status=target_status,
            duration_seconds=(data.time_limit_minutes * 60) if data.time_limit_minutes else None,
            max_attempts=None,
            published_at=now if data.publish else None,
            created_by_user_id=user_id,
        )
        db.add(version)
        await db.flush()

        course_concepts = await _load_course_concepts(db, offering_id, tenant_id)
        explicit_requested_ids = {cid for q_in in data.questions for cid in q_in.concept_ids}
        valid_explicit_ids: set[uuid.UUID] = set()
        if explicit_requested_ids:
            found_rows = (
                await db.execute(
                    select(Concept.id).where(
                        Concept.id.in_(explicit_requested_ids),
                        Concept.institution_id == tenant_id,
                    )
                )
            ).scalars().all()
            valid_explicit_ids = set(found_rows)

        for seq, q_in in enumerate(data.questions, start=1):
            if q_in.correct_index >= len(q_in.options):
                raise AppException(
                    status_code=400,
                    code="INVALID_QUIZ_OPTION",
                    message=f"Question {seq} correct option index is out of range.",
                )

            opt_items = [
                {"option_id": f"opt_{idx + 1}", "text": opt_text.strip() or f"Option {idx + 1}"}
                for idx, opt_text in enumerate(q_in.options)
            ]
            authoring_payload = {
                "question": q_in.statement.strip(),
                "options": opt_items,
                "correct_option_id": opt_items[q_in.correct_index]["option_id"],
                "explanation": (q_in.explanation or "").strip() or None,
            }
            student_payload, answer_key = LearningService.sanitize_authoring_payload("mcq", authoring_payload)

            activity = Activity(
                institution_id=tenant_id,
                learning_node_id=node.id,
                created_by_user_id=user_id,
                status="active",
            )
            db.add(activity)
            await db.flush()

            act_v = ActivityVersion(
                institution_id=tenant_id,
                activity_id=activity.id,
                version_number=1,
                activity_type="mcq",
                schema_version=1,
                title=f"Q{seq}: {q_in.statement.strip()[:120]}",
                student_payload_json=student_payload,
                answer_key_json=answer_key,
                scoring_config_json={
                    "max_marks": float(q_in.marks),
                    "negative_marks": 0.0,
                    "origin_type": q_in.origin_type,
                    "difficulty_level": q_in.difficulty_level,
                    "cognitive_level": q_in.cognitive_level,
                    "source_chunk_ids": [str(source_id) for source_id in q_in.source_chunk_ids],
                },
                approval_status="approved",
                created_by_user_id=user_id,
                approved_by_user_id=user_id,
                approved_at=now,
            )
            db.add(act_v)
            await db.flush()

            item = AssessmentItem(
                institution_id=tenant_id,
                assessment_version_id=version.id,
                activity_version_id=act_v.id,
                sequence_no=seq,
                marks_available=float(q_in.marks),
                is_required=True,
            )
            db.add(item)
            await db.flush()

            resolved_concept_ids = [cid for cid in q_in.concept_ids if cid in valid_explicit_ids]
            if not resolved_concept_ids and course_concepts:
                resolved_concept_ids = _match_concepts_for_text(
                    course_concepts,
                    f"{q_in.statement} {q_in.explanation or ''}",
                )
                if not resolved_concept_ids:
                    resolved_concept_ids = _match_concepts_for_text(
                        course_concepts,
                        f"{data.title} {data.description or ''}",
                    )
            _allocate_item_concepts(db, tenant_id, item.id, float(q_in.marks), resolved_concept_ids)

        if commit:
            await db.commit()
        else:
            await db.flush()
        return await AssessmentService.load_assessment_full(db, assessment.id, tenant_id)

    @staticmethod
    async def generate_quiz_with_ai(
        db: AsyncSession,
        offering_id: uuid.UUID,
        tenant_id: uuid.UUID,
        data: QuizAiGenerateRequest,
    ) -> QuizAiGenerateResponse:
        """Generate structured MCQ questions for a course topic using configured Gemini AI."""
        stmt = (
            select(CourseOffering)
            .options(
                selectinload(CourseOffering.curriculum_subject_entry).selectinload(CurriculumSubjectEntry.canonical_subject)
            )
            .where(CourseOffering.id == offering_id, CourseOffering.institution_id == tenant_id)
        )
        offering = (await db.execute(stmt)).scalars().first()
        if not offering:
            raise AppException(status_code=404, code="OFFERING_NOT_FOUND", message="Course offering not found.")

        entry = offering.curriculum_subject_entry
        subject_name = (
            (entry.display_name_override if entry else None)
            or (entry.canonical_subject.name if entry and entry.canonical_subject else None)
            or (entry.official_subject_code if entry else "Course")
        )
        subject_code = entry.official_subject_code if entry else ""

        # Retrieve a small, source-linked context from teacher-reviewed material.
        # Raw files are never sent to the model, and unreviewed extraction is excluded.
        source_rows = (await db.execute(
            select(SourceChunk, SourceDocument)
            .join(SourceDocument, SourceDocument.id == SourceChunk.source_document_id)
            .join(SourceDocumentCourseOffering, SourceDocumentCourseOffering.source_document_id == SourceDocument.id)
            .where(
                SourceDocumentCourseOffering.course_offering_id == offering_id,
                SourceDocument.institution_id == tenant_id,
                SourceDocument.publication_status != "rejected",
                SourceDocument.status == "processed",
                SourceChunk.institution_id == tenant_id,
            )
            .order_by(SourceChunk.created_at.desc(), SourceChunk.chunk_index.asc())
            .limit(1000)
        )).all()
        topic_phrases, topic_terms = _build_topic_phrases_and_terms(data.topic)
        seen_contents: set[tuple[uuid.UUID, str]] = set()
        ranked_chunks = []
        for chunk, source_document in source_rows:
            content = (chunk.content_text or "").strip()
            if not content:
                continue
            dedupe_key = (source_document.id, chunk.content_hash or content)
            if dedupe_key in seen_contents:
                continue
            seen_contents.add(dedupe_key)
            haystack = f"{chunk.section_path or ''} {content}".lower()
            phrase_score = sum(haystack.count(phrase) * 5 for phrase in topic_phrases)
            term_score = sum(haystack.count(term) for term in topic_terms)
            score = phrase_score + term_score
            if score:
                ranked_chunks.append((score, chunk, source_document, content))
        ranked_chunks.sort(key=lambda row: (-row[0], row[1].chunk_index))
        selected_chunks = ranked_chunks[:8]
        if not selected_chunks:
            raise AppException(
                status_code=409,
                code="REVIEWED_COURSE_KNOWLEDGE_REQUIRED",
                message="No reviewed course material matches this topic. Process and publish relevant material before AI generation.",
            )

        context_parts = []
        for _, chunk, source_document, content in selected_chunks:
            ref = f"[{chunk.id}] {source_document.original_filename}"
            if chunk.page_number:
                ref += f", page {chunk.page_number}"
            if chunk.slide_number:
                ref += f", slide {chunk.slide_number}"
            context_parts.append(f"{ref}\n{content[:1800]}")
        retrieved_context = "\n\n---\n\n".join(context_parts)

        settings = get_settings()
        if not settings.GEMINI_API_KEY:
            raise AppException(
                status_code=503,
                code="AI_NOT_CONFIGURED",
                message="Gemini API key is not configured on the backend.",
            )

        course_concepts = await _load_course_concepts(db, offering_id, tenant_id)
        concepts_block = ""
        if course_concepts:
            concept_lines = "\n".join(f"- [{c.id}] {c.canonical_name}" for c in course_concepts[:40])
            concepts_block = (
                "For each question also include concept_ids listing the matching course concept UUIDs from the list below:\n"
                f"{concept_lines}\n\n"
            )

        prompt = (
            f"You are an engineering university professor teaching {subject_code} {subject_name}. "
            f"Generate {data.question_count} multiple-choice quiz questions on the topic \"{data.topic.strip()}\" "
            f"at \"{data.difficulty}\" university difficulty level.\n"
            "Ground every question and answer in the reviewed course excerpts below. Do not invent unsupported facts. "
            "For each question include source_chunk_ids containing the excerpt identifiers that support it. "
            "These identifiers must be copied from the supplied context.\n\n"
            f"{concepts_block}"
            f"Reviewed course excerpts:\n{retrieved_context}\n\n"
            "Return valid JSON ONLY (no markdown) matching this exact schema:\n"
            "{\n"
            '  "title": "Short clear quiz title",\n'
            '  "description": "1-sentence assessment summary",\n'
            '  "questions": [\n'
            "    {\n"
            '      "statement": "Clear unambiguous question text",\n'
            '      "options": ["Option A", "Option B", "Option C", "Option D"],\n'
            '      "correct_index": 0,\n'
            '      "explanation": "Concise step-by-step rationale",\n'
            '      "source_chunk_ids": ["source chunk UUID"],\n'
            '      "concept_ids": ["concept UUID"],\n'
            '      "marks": 2\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "Rules: Every question must have exactly 4 distinct options and correct_index in 0..3."
        )

        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.4},
        }

        configured_models = [
            settings.GEMINI_MODEL,
            *[model.strip() for model in getattr(settings, "GEMINI_FALLBACK_MODELS", "").split(",") if model.strip()],
            getattr(settings, "GEMINI_REPAIR_MODEL", settings.GEMINI_MODEL),
        ]
        models = list(dict.fromkeys(configured_models))
        resp = None
        last_status = None
        observed_statuses = []
        last_network_error = False
        async with httpx.AsyncClient(timeout=90.0) as client:
            for model in models:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                try:
                    candidate = await client.post(url, headers={"x-goog-api-key": settings.GEMINI_API_KEY}, json=payload)
                except httpx.HTTPError as exc:
                    last_network_error = True
                    logger.warning("Quiz Gemini request failed model=%s error=%s", model, type(exc).__name__)
                    continue
                if candidate.status_code == 200:
                    resp = candidate
                    break
                last_status = candidate.status_code
                observed_statuses.append(candidate.status_code)
                logger.warning("Quiz Gemini request failed model=%s status=%s", model, candidate.status_code)
                # These statuses may be model-specific or transient; allow the configured fallbacks.
                if candidate.status_code not in {404, 429, 500, 502, 503, 504}:
                    break

        if resp is None:
            if 503 in observed_statuses:
                last_status = 503
            elif 429 in observed_statuses:
                last_status = 429
            if last_status == 503:
                message = "Gemini is temporarily unavailable across the configured models. Please retry shortly."
            elif last_status == 429:
                message = "Gemini API rate or usage limit was reached for the configured models. Please retry later."
            elif last_status in {401, 403}:
                message = "Gemini rejected the API key or model access. Check the backend Gemini API configuration."
            elif last_status == 404:
                message = "None of the configured Gemini models is available to this API key. Check model access and names."
            elif last_network_error:
                message = "The backend could not reach Gemini using the configured models. Check network access and retry."
            else:
                message = "Gemini could not generate quiz questions from the configured models. Please retry."
            raise AppException(status_code=502, code="AI_GENERATION_FAILED", message=message)

        raw_body = resp.json()
        candidates = raw_body.get("candidates") or [{}]
        parts = candidates[0].get("content", {}).get("parts") or [{}]
        raw_text = (parts[0].get("text") or "").strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.strip("`").removeprefix("json").strip()

        try:
            parsed = json.loads(raw_text)
        except json.JSONDecodeError:
            raise AppException(
                status_code=502,
                code="AI_INVALID_JSON",
                message="AI returned malformed quiz data. Please try generating again.",
            )

        if isinstance(parsed, list):
            parsed = {"questions": parsed}
        if not isinstance(parsed, dict):
            raise AppException(
                status_code=502,
                code="AI_INVALID_JSON",
                message="AI returned malformed quiz data. Please try generating again.",
            )

        valid_course_concept_map = {str(c.id): c.id for c in course_concepts}
        questions_out: List[QuizAiQuestionOut] = []
        for item in (parsed.get("questions") or [])[: data.question_count]:
            if not isinstance(item, dict):
                continue
            opts = [str(o).strip() for o in (item.get("options") or []) if str(o).strip()]
            if len(opts) < 2 or not str(item.get("statement") or "").strip():
                continue
            try:
                correct_idx = int(item.get("correct_index", 0))
            except (TypeError, ValueError):
                correct_idx = 0
            if correct_idx < 0 or correct_idx >= len(opts):
                correct_idx = 0
            raw_chunk_ids = {str(value) for value in (item.get("source_chunk_ids") or [])}
            raw_concept_ids = [
                valid_course_concept_map[str(value)]
                for value in (item.get("concept_ids") or [])
                if str(value) in valid_course_concept_map
            ]
            statement_text = str(item["statement"]).strip()
            explanation_text = str(item.get("explanation") or "").strip()
            if not raw_concept_ids and course_concepts:
                raw_concept_ids = _match_concepts_for_text(
                    course_concepts,
                    f"{statement_text} {explanation_text} {data.topic}",
                )
            questions_out.append(
                QuizAiQuestionOut(
                    statement=statement_text,
                    options=opts,
                    correct_index=correct_idx,
                    explanation=explanation_text,
                    marks=float(item.get("marks") or 2.0),
                    source_chunk_ids=[
                        chunk.id for _, chunk, _, _ in selected_chunks
                        if str(chunk.id) in raw_chunk_ids
                    ],
                    concept_ids=list(dict.fromkeys(raw_concept_ids)),
                )
            )

        if not questions_out:
            raise AppException(
                status_code=502,
                code="AI_EMPTY_QUIZ",
                message="AI did not produce usable quiz questions. Try a more specific topic.",
            )

        return QuizAiGenerateResponse(
            title=str(parsed.get("title") or f"{subject_name}: {data.topic.strip()}").strip()[:255],
            description=str(parsed.get("description") or f"{data.difficulty} quiz on {data.topic.strip()}").strip(),
            questions=questions_out,
            sources=[
                {
                    "source_document_id": document.id,
                    "source_chunk_id": chunk.id,
                    "filename": document.original_filename,
                    "page_number": chunk.page_number,
                    "slide_number": chunk.slide_number,
                }
                for _, chunk, document, _ in selected_chunks
            ],
        )

    @staticmethod
    async def get_attempt_summary(
        db: AsyncSession,
        attempt_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> AttemptSummaryOut:
        stmt = (
            select(AssessmentAttempt)
            .options(
                selectinload(AssessmentAttempt.item_scores)
                .selectinload(AssessmentItemScore.item)
                .selectinload(AssessmentItem.activity_version),
                selectinload(AssessmentAttempt.concept_scores),
                selectinload(AssessmentAttempt.responses),
            )
            .where(AssessmentAttempt.id == attempt_id, AssessmentAttempt.institution_id == tenant_id)
        )
        res = await db.execute(stmt)
        attempt = res.scalars().first()
        if not attempt:
            raise AppException(status_code=404, code="ATTEMPT_NOT_FOUND", message="Attempt not found.")

        is_finalized = attempt.status in ("submitted", "expired")
        resp_by_item = {r.assessment_item_id: (r.response_payload_json or {}) for r in (attempt.responses or [])}

        # For unfinalized formal quizzes, suppress correct answers and explanations to prevent cheating
        asmt_stmt = (
            select(Assessment)
            .join(AssessmentVersion, AssessmentVersion.assessment_id == Assessment.id)
            .where(AssessmentVersion.id == attempt.assessment_version_id)
        )
        asmt = (await db.execute(asmt_stmt)).scalars().first()
        show_solutions = is_finalized
        if asmt and asmt.is_formal_quiz and not asmt.is_finalized:
            show_solutions = False

        item_scores_out: List[ItemScoreOut] = []
        for sc in attempt.item_scores:
            act_v = sc.item.activity_version if sc.item else None
            ans_key = (act_v.answer_key_json or {}) if (show_solutions and act_v) else {}
            chosen_payload = resp_by_item.get(sc.assessment_item_id, {})
            item_scores_out.append(
                ItemScoreOut(
                    item_id=sc.assessment_item_id,
                    sequence_no=sc.item.sequence_no if sc.item else 1,
                    marks_awarded=float(sc.marks_awarded),
                    marks_available=float(sc.marks_available),
                    result_status=sc.result_status,
                    selected_option_id=chosen_payload.get("selected_option_id") if is_finalized else None,
                    correct_option_id=ans_key.get("correct_option_id") if show_solutions else None,
                    explanation=ans_key.get("explanation") if show_solutions else None,
                )
            )

        concept_scores_out = [
            ConceptScoreOut(
                concept_id=cs.concept_id,
                marks_awarded=float(cs.marks_awarded),
                marks_available=float(cs.marks_available),
            )
            for cs in attempt.concept_scores
        ]

        return AttemptSummaryOut(
            attempt_id=attempt.id,
            assessment_version_id=attempt.assessment_version_id,
            attempt_number=attempt.attempt_number,
            status=attempt.status,
            scoring_status=attempt.scoring_status,
            is_valid=attempt.is_valid,
            started_at=attempt.started_at,
            expires_at=attempt.expires_at,
            submitted_at=attempt.submitted_at,
            finalized_at=attempt.finalized_at,
            marks_awarded=float(attempt.marks_awarded) if attempt.marks_awarded is not None else None,
            marks_available=float(attempt.marks_available) if attempt.marks_available is not None else None,
            score_fraction=float(attempt.score_fraction) if attempt.score_fraction is not None else None,
            item_scores=item_scores_out,
            concept_scores=concept_scores_out,
        )

    @staticmethod
    async def create_formal_quiz(
        db: AsyncSession,
        offering_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        data: FormalQuizCreateRequest,
    ) -> Assessment:
        """Create a scheduled credit-bearing formal academic quiz with MCQ items."""
        offering = await db.get(CourseOffering, offering_id)
        if not offering or offering.institution_id != tenant_id:
            raise AppException(status_code=404, code="OFFERING_NOT_FOUND", message="Course offering not found.")

        if data.scheduled_start_at and data.scheduled_end_at:
            start_t = data.scheduled_start_at if data.scheduled_start_at.tzinfo else data.scheduled_start_at.replace(tzinfo=timezone.utc)
            end_t = data.scheduled_end_at if data.scheduled_end_at.tzinfo else data.scheduled_end_at.replace(tzinfo=timezone.utc)
            if end_t <= start_t:
                raise AppException(
                    status_code=400,
                    code="INVALID_QUIZ_WINDOW",
                    message="Formal quiz scheduled_end_at must be strictly after scheduled_start_at.",
                )

        node_stmt = (
            select(LearningNode)
            .where(
                LearningNode.course_offering_id == offering_id,
                LearningNode.institution_id == tenant_id,
            )
            .order_by(LearningNode.sequence_no.asc())
            .limit(1)
        )
        node = (await db.execute(node_stmt)).scalars().first()
        if not node:
            cv_stmt = (
                select(CourseContentVersion)
                .where(
                    CourseContentVersion.course_offering_id == offering_id,
                    CourseContentVersion.institution_id == tenant_id,
                )
                .order_by(CourseContentVersion.version_number.desc())
                .limit(1)
            )
            content_v = (await db.execute(cv_stmt)).scalars().first()
            if not content_v:
                content_v = await KnowledgeService.get_or_create_draft_version(
                    db=db, offering_id=offering_id, tenant_id=tenant_id, user_id=user_id
                )
            node = LearningNode(
                institution_id=tenant_id,
                course_offering_id=offering_id,
                course_content_version_id=content_v.id,
                node_code="FORMAL_QUIZZES",
                title="Formal Quizzes & Academic Assessments",
                description="Credit-bearing departmental quizzes and evaluations.",
                sequence_no=1,
                status="published",
                published_at=datetime.now(timezone.utc),
                created_by_user_id=user_id,
            )
            db.add(node)
            await db.flush()

        now = datetime.now(timezone.utc)
        target_status = "published" if data.publish else "draft"

        assessment = Assessment(
            institution_id=tenant_id,
            course_offering_id=offering_id,
            learning_node_id=node.id,
            assessment_type="node_practice",
            title=data.title.strip(),
            description=(data.description or "").strip() or None,
            status=target_status,
            is_formal_quiz=True,
            scheduled_start_at=data.scheduled_start_at,
            scheduled_end_at=data.scheduled_end_at,
            shuffle_questions=data.shuffle_questions,
            shuffle_options=data.shuffle_options,
            is_finalized=False,
            created_by_user_id=user_id,
        )
        db.add(assessment)
        await db.flush()

        version = AssessmentVersion(
            institution_id=tenant_id,
            assessment_id=assessment.id,
            version_number=1,
            status=target_status,
            duration_seconds=(data.time_limit_minutes * 60) if data.time_limit_minutes else None,
            max_attempts=1,
            published_at=now if data.publish else None,
            created_by_user_id=user_id,
        )
        db.add(version)
        await db.flush()

        course_concepts = await _load_course_concepts(db, offering_id, tenant_id)
        explicit_requested_ids = {cid for q_in in data.questions for cid in q_in.concept_ids}
        valid_explicit_ids: set[uuid.UUID] = set()
        if explicit_requested_ids:
            found_rows = (
                await db.execute(
                    select(Concept.id).where(
                        Concept.id.in_(explicit_requested_ids),
                        Concept.institution_id == tenant_id,
                    )
                )
            ).scalars().all()
            valid_explicit_ids = set(found_rows)

        for seq, q_in in enumerate(data.questions, start=1):
            if q_in.correct_index >= len(q_in.options):
                raise AppException(
                    status_code=400,
                    code="INVALID_QUIZ_OPTION",
                    message=f"Question {seq} correct option index is out of range.",
                )

            opt_items = [
                {"option_id": f"opt_{idx + 1}", "text": opt_text.strip() or f"Option {idx + 1}"}
                for idx, opt_text in enumerate(q_in.options)
            ]
            authoring_payload = {
                "question": q_in.statement.strip(),
                "options": opt_items,
                "correct_option_id": opt_items[q_in.correct_index]["option_id"],
                "explanation": (q_in.explanation or "").strip() or None,
            }
            student_payload, answer_key = LearningService.sanitize_authoring_payload("mcq", authoring_payload)

            activity = Activity(
                institution_id=tenant_id,
                learning_node_id=node.id,
                created_by_user_id=user_id,
                status="active",
            )
            db.add(activity)
            await db.flush()

            act_v = ActivityVersion(
                institution_id=tenant_id,
                activity_id=activity.id,
                version_number=1,
                activity_type="mcq",
                schema_version=1,
                title=f"Q{seq}: {q_in.statement.strip()[:120]}",
                student_payload_json=student_payload,
                answer_key_json=answer_key,
                scoring_config_json={
                    "max_marks": float(q_in.marks),
                    "negative_marks": 0.0,
                    "origin_type": q_in.origin_type,
                    "source_chunk_ids": [str(source_id) for source_id in q_in.source_chunk_ids],
                },
                approval_status="approved",
                created_by_user_id=user_id,
                approved_by_user_id=user_id,
                approved_at=now,
            )
            db.add(act_v)
            await db.flush()

            item = AssessmentItem(
                institution_id=tenant_id,
                assessment_version_id=version.id,
                activity_version_id=act_v.id,
                sequence_no=seq,
                marks_available=float(q_in.marks),
                is_required=True,
            )
            db.add(item)
            await db.flush()

            resolved_concept_ids = [cid for cid in q_in.concept_ids if cid in valid_explicit_ids]
            if not resolved_concept_ids and course_concepts:
                resolved_concept_ids = _match_concepts_for_text(
                    course_concepts,
                    f"{q_in.statement} {q_in.explanation or ''}",
                )
                if not resolved_concept_ids:
                    resolved_concept_ids = _match_concepts_for_text(
                        course_concepts,
                        f"{data.title} {data.description or ''}",
                    )
            _allocate_item_concepts(db, tenant_id, item.id, float(q_in.marks), resolved_concept_ids)

        await db.commit()
        return await AssessmentService.load_assessment_full(db, assessment.id, tenant_id)

    @staticmethod
    async def grant_student_override(
        db: AsyncSession,
        assessment_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        data: StudentOverrideCreate,
    ) -> AssessmentStudentOverride:
        """Grant a student an individual makeup window or record confirmed absence."""
        assessment = await db.get(Assessment, assessment_id)
        if not assessment or assessment.institution_id != tenant_id:
            raise AppException(status_code=404, code="ASSESSMENT_NOT_FOUND", message="Assessment not found.")

        enrolment_stmt = select(CourseOfferingEnrolment).where(
            CourseOfferingEnrolment.course_offering_id == assessment.course_offering_id,
            CourseOfferingEnrolment.institution_membership_id == data.student_membership_id,
            CourseOfferingEnrolment.enrolment_status == "active",
        )
        enrolment = (await db.execute(enrolment_stmt)).scalars().first()
        if not enrolment:
            raise AppException(
                status_code=400,
                code="STUDENT_NOT_ENROLLED",
                message="Student is not actively enrolled in this course offering.",
            )

        if data.override_type == "makeup_window":
            if not data.start_at or not data.end_at:
                raise AppException(
                    status_code=400,
                    code="INVALID_MAKEUP_WINDOW",
                    message="Both start_at and end_at are required for a makeup window.",
                )
            start_t = data.start_at if data.start_at.tzinfo else data.start_at.replace(tzinfo=timezone.utc)
            end_t = data.end_at if data.end_at.tzinfo else data.end_at.replace(tzinfo=timezone.utc)
            if end_t <= start_t:
                raise AppException(
                    status_code=400,
                    code="INVALID_MAKEUP_WINDOW",
                    message="Makeup window end_at must be strictly after start_at.",
                )

            # Supersede any existing active makeup grant for this student
            existing_active_stmt = select(AssessmentStudentOverride).where(
                AssessmentStudentOverride.assessment_id == assessment_id,
                AssessmentStudentOverride.student_membership_id == data.student_membership_id,
                AssessmentStudentOverride.override_type == "makeup_window",
                AssessmentStudentOverride.status == "active",
            )
            existing_active = (await db.execute(existing_active_stmt)).scalars().all()
            for row in existing_active:
                row.status = "superseded"

        override = AssessmentStudentOverride(
            institution_id=tenant_id,
            assessment_id=assessment_id,
            student_membership_id=data.student_membership_id,
            override_type=data.override_type,
            status="active",
            start_at=data.start_at,
            end_at=data.end_at,
            reason=data.reason.strip(),
            granted_by_user_id=user_id,
        )
        db.add(override)
        await db.commit()
        await db.refresh(override)
        return override

    @staticmethod
    async def override_attempt_marks(
        db: AsyncSession,
        attempt_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        data: MarkOverrideRequest,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AssessmentAttempt:
        """Faculty override of an attempt's total marks with immutable audit log."""
        attempt = await db.get(AssessmentAttempt, attempt_id)
        if not attempt or attempt.institution_id != tenant_id:
            raise AppException(status_code=404, code="ATTEMPT_NOT_FOUND", message="Attempt not found.")

        old_effective = float(attempt.faculty_override_marks if attempt.faculty_override_marks is not None else (attempt.marks_awarded or 0.0))

        attempt.faculty_override_marks = data.marks
        attempt.override_reason = data.reason.strip()
        attempt.override_by_user_id = user_id

        audit = AuditEvent(
            institution_id=tenant_id,
            actor_user_id=user_id,
            event_code="ASSESSMENT_MARK_OVERRIDE",
            target_type="assessment_attempt",
            target_id=str(attempt.id),
            payload_json={
                "original_marks_awarded": float(attempt.marks_awarded or 0.0),
                "previous_effective_marks": old_effective,
                "new_override_marks": float(data.marks),
                "delta": round(float(data.marks) - old_effective, 2),
                "reason": data.reason.strip(),
                "student_membership_id": str(attempt.student_membership_id),
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(audit)
        await db.commit()
        await db.refresh(attempt)
        return attempt

    @staticmethod
    async def finalize_quiz_marks(
        db: AsyncSession,
        assessment_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Assessment:
        """Lock formal quiz marks so that results become official and solutions are visible."""
        assessment = await db.get(Assessment, assessment_id)
        if not assessment or assessment.institution_id != tenant_id:
            raise AppException(status_code=404, code="ASSESSMENT_NOT_FOUND", message="Assessment not found.")

        now = datetime.now(timezone.utc)
        assessment.is_finalized = True
        assessment.finalized_at = now
        assessment.finalized_by_user_id = user_id

        audit = AuditEvent(
            institution_id=tenant_id,
            actor_user_id=user_id,
            event_code="ASSESSMENT_FINALIZED",
            target_type="assessment",
            target_id=str(assessment.id),
            payload_json={
                "quiz_title": assessment.title,
                "finalized_at": now.isoformat(),
            },
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.add(audit)
        await db.commit()
        return await AssessmentService.load_assessment_full(db, assessment.id, tenant_id)

    @staticmethod
    async def get_formal_quiz_roster(
        db: AsyncSession,
        assessment_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> FormalQuizRosterSummaryOut:
        """Full course offering roster evaluation for formal quiz grading and attendance."""
        assessment = await db.get(Assessment, assessment_id)
        if not assessment or assessment.institution_id != tenant_id:
            raise AppException(status_code=404, code="ASSESSMENT_NOT_FOUND", message="Assessment not found.")

        v_stmt = (
            select(AssessmentVersion)
            .options(selectinload(AssessmentVersion.items))
            .where(
                AssessmentVersion.assessment_id == assessment_id,
                AssessmentVersion.institution_id == tenant_id,
            )
            .order_by(AssessmentVersion.version_number.desc())
        )
        version = (await db.execute(v_stmt)).scalars().first()
        max_marks = sum(float(it.marks_available) for it in (version.items or [])) if version else 0.0

        enrolments_stmt = (
            select(CourseOfferingEnrolment, InstitutionMembership, User, StudentProgrammeEnrolment)
            .join(InstitutionMembership, InstitutionMembership.id == CourseOfferingEnrolment.institution_membership_id)
            .join(User, User.id == InstitutionMembership.user_id)
            .options(selectinload(User.identifiers))
            .outerjoin(StudentProgrammeEnrolment, StudentProgrammeEnrolment.institution_membership_id == InstitutionMembership.id)
            .where(
                CourseOfferingEnrolment.course_offering_id == assessment.course_offering_id,
                CourseOfferingEnrolment.institution_id == tenant_id,
                CourseOfferingEnrolment.enrolment_status == "active",
            )
            .order_by(User.display_name.asc())
        )
        enrolled_rows = (await db.execute(enrolments_stmt)).all()

        attempts_stmt = (
            select(AssessmentAttempt)
            .where(
                AssessmentAttempt.assessment_version_id == version.id,
                AssessmentAttempt.institution_id == tenant_id,
            )
            .order_by(AssessmentAttempt.attempt_number.desc())
        ) if version else None
        all_attempts = (await db.execute(attempts_stmt)).scalars().all() if attempts_stmt is not None else []

        attempts_by_student: Dict[uuid.UUID, List[AssessmentAttempt]] = {}
        for att in all_attempts:
            attempts_by_student.setdefault(att.student_membership_id, []).append(att)

        overrides_stmt = (
            select(AssessmentStudentOverride)
            .where(
                AssessmentStudentOverride.assessment_id == assessment_id,
                AssessmentStudentOverride.institution_id == tenant_id,
            )
            .order_by(AssessmentStudentOverride.created_at.desc())
        )
        all_overrides = (await db.execute(overrides_stmt)).scalars().all()
        overrides_by_student: Dict[uuid.UUID, List[AssessmentStudentOverride]] = {}
        for ov in all_overrides:
            overrides_by_student.setdefault(ov.student_membership_id, []).append(ov)

        students_out: List[RosterStudentResultOut] = []
        count_submitted = 0
        count_absent = 0
        count_makeup = 0
        count_unattempted = 0

        for enrolment, membership, user, prog in enrolled_rows:
            mem_id = membership.id
            stu_attempts = attempts_by_student.get(mem_id, [])
            stu_overrides = overrides_by_student.get(mem_id, [])

            active_makeup_obj = next((ov for ov in stu_overrides if ov.override_type == "makeup_window" and ov.status == "active"), None)
            confirmed_absence = next((ov for ov in stu_overrides if ov.override_type == "confirmed_absence" and ov.status == "active"), None)

            submitted_attempt = next((a for a in stu_attempts if a.status in ("submitted", "expired")), None)

            if submitted_attempt:
                raw_awarded = float(submitted_attempt.marks_awarded) if submitted_attempt.marks_awarded is not None else 0.0
                override_awarded = float(submitted_attempt.faculty_override_marks) if submitted_attempt.faculty_override_marks is not None else None
                effective = override_awarded if override_awarded is not None else raw_awarded
                row_status = "submitted"
                count_submitted += 1
                attempt_id = submitted_attempt.id
                attempt_no = submitted_attempt.attempt_number
                started_at = submitted_attempt.started_at
                submitted_at = submitted_attempt.submitted_at
                override_reason = submitted_attempt.override_reason
            elif active_makeup_obj:
                raw_awarded = None
                override_awarded = None
                effective = None
                row_status = "makeup_pending"
                count_makeup += 1
                attempt_id = None
                attempt_no = None
                started_at = None
                submitted_at = None
                override_reason = active_makeup_obj.reason
            elif confirmed_absence:
                raw_awarded = None
                override_awarded = None
                effective = None
                row_status = "absent"
                count_absent += 1
                attempt_id = None
                attempt_no = None
                started_at = None
                submitted_at = None
                override_reason = confirmed_absence.reason
            else:
                raw_awarded = None
                override_awarded = None
                effective = None
                row_status = "not_attempted"
                count_unattempted += 1
                attempt_id = None
                attempt_no = None
                started_at = None
                submitted_at = None
                override_reason = None

            email = next((i.identifier_value for i in (user.identifiers or []) if i.identifier_type == "email"), None)
            students_out.append(
                RosterStudentResultOut(
                    student_membership_id=mem_id,
                    student_user_id=user.id,
                    full_name=user.display_name or user.legal_name or "Student",
                    registration_number=prog.registration_number if prog else None,
                    roll_number=getattr(prog, "roll_number", None),
                    email=email,
                    status=row_status,
                    attempt_id=attempt_id,
                    attempt_number=attempt_no,
                    started_at=started_at,
                    submitted_at=submitted_at,
                    raw_marks_awarded=raw_awarded,
                    faculty_override_marks=override_awarded,
                    effective_marks=effective,
                    marks_available=max_marks,
                    override_reason=override_reason,
                    active_makeup=StudentOverrideOut.model_validate(active_makeup_obj) if active_makeup_obj else None,
                )
            )

        return FormalQuizRosterSummaryOut(
            quiz_id=assessment.id,
            quiz_title=assessment.title,
            course_offering_id=assessment.course_offering_id,
            is_finalized=assessment.is_finalized,
            finalized_at=assessment.finalized_at,
            total_enrolled=len(enrolled_rows),
            total_submitted=count_submitted,
            total_absent=count_absent,
            total_makeup_pending=count_makeup,
            total_not_attempted=count_unattempted,
            students=students_out,
        )

    @staticmethod
    async def export_formal_quiz_excel(
        db: AsyncSession,
        assessment_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> bytes:
        """Generate departmental grade spreadsheet (.xlsx) for formal quiz records."""
        roster = await AssessmentService.get_formal_quiz_roster(db, assessment_id, tenant_id)

        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {"in_memory": True})
        worksheet = workbook.add_worksheet("Quiz Marks")

        title_fmt = workbook.add_format({"bold": True, "font_size": 13, "font_color": "#0F172A", "align": "left"})
        meta_fmt = workbook.add_format({"font_size": 10, "font_color": "#475569"})
        header_fmt = workbook.add_format({
            "bold": True,
            "font_size": 10,
            "bg_color": "#0F172A",
            "font_color": "#FFFFFF",
            "align": "center",
            "valign": "vcenter",
            "border": 1,
        })
        cell_center = workbook.add_format({"font_size": 10, "align": "center", "border": 1})
        cell_left = workbook.add_format({"font_size": 10, "align": "left", "border": 1})
        cell_num = workbook.add_format({"font_size": 10, "align": "right", "num_format": "0.00", "border": 1})
        status_submitted = workbook.add_format({"font_size": 10, "align": "center", "bg_color": "#DCFCE7", "font_color": "#15803D", "border": 1})
        status_absent = workbook.add_format({"font_size": 10, "align": "center", "bg_color": "#FEE2E2", "font_color": "#B91C1C", "border": 1})
        status_makeup = workbook.add_format({"font_size": 10, "align": "center", "bg_color": "#FEF3C7", "font_color": "#B45309", "border": 1})
        status_unattempted = workbook.add_format({"font_size": 10, "align": "center", "bg_color": "#F1F5F9", "font_color": "#64748B", "border": 1})

        worksheet.write(0, 0, f"DOUBTDESK ACADEMIC EVALUATION: {roster.quiz_title}", title_fmt)
        worksheet.write(1, 0, f"Course Offering: {roster.course_offering_id} | Finalized: {'Yes' if roster.is_finalized else 'No'} | Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", meta_fmt)
        worksheet.write(2, 0, f"Enrolled: {roster.total_enrolled} | Submitted: {roster.total_submitted} | Absent: {roster.total_absent} | Makeup Pending: {roster.total_makeup_pending} | Unattempted: {roster.total_not_attempted}", meta_fmt)

        headers = [
            "Sl No.",
            "Registration No.",
            "Roll No.",
            "Student Name",
            "Email",
            "Status",
            "Raw Marks",
            "Faculty Override",
            "Final Marks",
            "Max Marks",
            "Score %",
            "Override / Absence Reason",
        ]

        worksheet.set_row(4, 25)
        for col_idx, h in enumerate(headers):
            worksheet.write(4, col_idx, h, header_fmt)

        for row_idx, stu in enumerate(roster.students, start=5):
            st_fmt = cell_center
            if stu.status == "submitted":
                st_fmt = status_submitted
            elif stu.status == "absent":
                st_fmt = status_absent
            elif stu.status == "makeup_pending":
                st_fmt = status_makeup
            elif stu.status == "not_attempted":
                st_fmt = status_unattempted

            pct = f"{(stu.effective_marks / stu.marks_available * 100):.1f}%" if stu.effective_marks is not None and stu.marks_available > 0 else "-"

            worksheet.write(row_idx, 0, row_idx - 4, cell_center)
            worksheet.write(row_idx, 1, stu.registration_number or "-", cell_center)
            worksheet.write(row_idx, 2, stu.roll_number or "-", cell_center)
            worksheet.write(row_idx, 3, stu.full_name, cell_left)
            worksheet.write(row_idx, 4, stu.email or "-", cell_left)
            worksheet.write(row_idx, 5, stu.status.upper().replace("_", " "), st_fmt)

            if stu.raw_marks_awarded is not None:
                worksheet.write_number(row_idx, 6, stu.raw_marks_awarded, cell_num)
            else:
                worksheet.write(row_idx, 6, "-", cell_center)

            if stu.faculty_override_marks is not None:
                worksheet.write_number(row_idx, 7, stu.faculty_override_marks, cell_num)
            else:
                worksheet.write(row_idx, 7, "-", cell_center)

            if stu.effective_marks is not None:
                worksheet.write_number(row_idx, 8, stu.effective_marks, cell_num)
            else:
                worksheet.write(row_idx, 8, "-", cell_center)

            worksheet.write_number(row_idx, 9, stu.marks_available, cell_num)
            worksheet.write(row_idx, 10, pct, cell_center)
            worksheet.write(row_idx, 11, stu.override_reason or "-", cell_left)

        worksheet.set_column(0, 0, 8)
        worksheet.set_column(1, 2, 16)
        worksheet.set_column(3, 3, 24)
        worksheet.set_column(4, 4, 26)
        worksheet.set_column(5, 5, 16)
        worksheet.set_column(6, 9, 14)
        worksheet.set_column(10, 10, 12)
        worksheet.set_column(11, 11, 32)

        workbook.close()
        return output.getvalue()

