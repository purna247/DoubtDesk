from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.common.exceptions import AppException
from app.config import get_settings
from app.modules.academics.models import CourseOffering, CurriculumSubjectEntry
from app.modules.assessments.models import StudentLearningNodeProgress
from app.modules.auth.models import InstitutionMembership
from app.modules.knowledge.models import Concept, ConceptVersion
from app.modules.knowledge.service import KnowledgeService
from app.modules.learning.models import (
    Activity,
    ActivityVersion,
    LearningNode,
    LearningNodeConcept,
    LearningNodePrerequisite,
    LearningNodeQuestion,
    StudentPracticeEvent,
    StudentPracticeSession,
)
from app.modules.learning.schemas import (
    PracticeAnswerRequest,
    PracticeAnswerResultOut,
    PracticeHintOut,
    PracticeQuestionOut,
    PracticeSessionStartOut,
    PracticeSessionStateOut,
)
from app.modules.learning.scoring import SCORING_DISPATCHER, evaluate_activity_response
from app.modules.learning.service import LearningService
from app.modules.questions.models import QuestionVersion
from app.modules.sources.embeddings import find_top_k_chunks

logger = logging.getLogger(__name__)

_DIFFICULTY_ORDER = ("easy", "medium", "hard")


def _next_harder(diff: str) -> str:
    if diff == "easy":
        return "medium"
    return "hard"


def _next_easier(diff: str) -> str:
    if diff == "hard":
        return "medium"
    return "easy"


def _build_session_state_out(session: StudentPracticeSession) -> PracticeSessionStateOut:
    return PracticeSessionStateOut(
        id=session.id,
        learning_node_id=session.learning_node_id,
        status=session.status,
        current_difficulty=session.current_difficulty,
        in_remediation=session.in_remediation,
        target_correct_count=session.target_correct_count,
        questions_answered=session.questions_answered,
        correct_count=session.correct_count,
        mistake_count=session.mistake_count,
        consecutive_mistakes=session.consecutive_mistakes,
        easier_followups_triggered=session.easier_followups_triggered,
        hints_used=session.hints_used,
        recovered_after_mistake_count=session.recovered_after_mistake_count,
        repeated_mistakes=session.consecutive_mistakes >= 2 or session.mistake_count >= 2,
        needs_easier_questions=session.easier_followups_triggered > 0,
        improving=session.recovered_after_mistake_count > 0,
    )


def _to_practice_question_out(act_v: ActivityVersion) -> PracticeQuestionOut:
    payload = act_v.student_payload_json or {}
    cfg = act_v.scoring_config_json or {}
    ans_key = act_v.answer_key_json or {}
    raw_opts = payload.get("options") if isinstance(payload.get("options"), list) else []
    options = [
        {"option_id": str(o.get("option_id", "")), "text": str(o.get("text", ""))}
        for o in raw_opts
        if isinstance(o, dict)
    ]
    q_text = str(payload.get("question") or payload.get("template") or payload.get("prompt") or act_v.title)
    return PracticeQuestionOut(
        activity_version_id=act_v.id,
        title=act_v.title,
        question=q_text,
        activity_type=act_v.activity_type,
        options=options,
        payload=payload,
        difficulty=str(cfg.get("difficulty") or "easy"),
        is_remediation=bool(cfg.get("is_remediation", False)),
        has_hint=bool(cfg.get("hint")),
        citation=ans_key.get("citation") or cfg.get("citation"),
    )


async def _get_student_membership(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> InstitutionMembership:
    stmt = select(InstitutionMembership).where(
        InstitutionMembership.institution_id == tenant_id,
        InstitutionMembership.user_id == user_id,
    )
    mem = (await db.execute(stmt)).scalars().first()
    if not mem:
        raise AppException(status_code=403, code="MEMBERSHIP_NOT_FOUND", message="Student membership not found.")
    return mem


async def _ensure_node_unlocked(
    db: AsyncSession,
    node: LearningNode,
    student_membership_id: uuid.UUID,
) -> None:
    prereq_rows = (
        await db.execute(
            select(LearningNodePrerequisite).where(
                LearningNodePrerequisite.learning_node_id == node.id,
                LearningNodePrerequisite.prerequisite_type == "required",
            )
        )
    ).scalars().all()
    if not prereq_rows:
        return
    req_ids = [p.prerequisite_node_id for p in prereq_rows]
    done_rows = (
        await db.execute(
            select(StudentLearningNodeProgress.learning_node_id).where(
                StudentLearningNodeProgress.student_membership_id == student_membership_id,
                StudentLearningNodeProgress.learning_node_id.in_(req_ids),
                StudentLearningNodeProgress.progress_status == "completed",
            )
        )
    ).scalars().all()
    if not set(req_ids).issubset(set(done_rows)):
        raise AppException(
            status_code=403,
            code="NODE_LOCKED",
            message="Complete the prerequisite topic(s) in the roadmap before starting this topic.",
        )


def _persist_practice_activity(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    node_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    title: str,
    activity_type: str,
    raw_payload: Dict[str, Any],
    difficulty: str,
    hint: str,
    explanation: str,
    is_remediation: bool = False,
    easier_followup: Optional[Dict[str, Any]] = None,
    citation: Optional[str] = None,
) -> tuple[Activity, ActivityVersion]:
    now = datetime.now(timezone.utc)
    if activity_type not in SCORING_DISPATCHER:
        activity_type = "mcq"

    authoring_payload = dict(raw_payload)
    authoring_payload["explanation"] = explanation.strip()

    if activity_type == "mcq":
        raw_options = authoring_payload.get("options") or []
        if raw_options and isinstance(raw_options[0], str):
            opt_items = [{"option_id": f"opt_{i+1}", "text": s.strip()} for i, s in enumerate(raw_options) if s.strip()]
        elif raw_options and isinstance(raw_options[0], dict):
            opt_items = [
                {"option_id": str(o.get("option_id", f"opt_{i+1}")), "text": str(o.get("text", "")).strip()}
                for i, o in enumerate(raw_options)
                if str(o.get("text", "")).strip()
            ]
        else:
            opt_items = []
        if len(opt_items) < 2:
            opt_items = [{"option_id": "opt_1", "text": "True"}, {"option_id": "opt_2", "text": "False"}]
        c_idx = authoring_payload.get("correct_index", 0)
        c_opt = authoring_payload.get("correct_option_id")
        if not c_opt:
            safe_idx = c_idx if 0 <= c_idx < len(opt_items) else 0
            c_opt = opt_items[safe_idx]["option_id"]
        authoring_payload["question"] = str(authoring_payload.get("question") or title).strip()
        authoring_payload["options"] = opt_items
        authoring_payload["correct_option_id"] = c_opt

    elif activity_type == "true_false":
        c_val = authoring_payload.get("correct_value")
        if c_val is not None:
            c_opt = "true" if c_val is True else "false"
        else:
            c_opt = str(authoring_payload.get("correct_option_id") or "true").lower()
        authoring_payload["question"] = str(authoring_payload.get("question") or title).strip()
        authoring_payload["options"] = [{"option_id": "true", "text": "True"}, {"option_id": "false", "text": "False"}]
        authoring_payload["correct_option_id"] = c_opt

    elif activity_type == "fill_blank":
        tmpl = authoring_payload.get("template") or authoring_payload.get("question") or f"{title} involves [blank_1]."
        if "[blank_1]" not in tmpl and "_" in tmpl:
            tmpl = tmpl.replace("___", "[blank_1]").replace("__", "[blank_1]")
        if "[blank_1]" not in tmpl:
            tmpl = f"{tmpl} [blank_1]"
        authoring_payload["template"] = tmpl
        if "blanks" not in authoring_payload:
            acc = authoring_payload.get("accepted_answers") or [authoring_payload.get("correct_answer") or "answer"]
            if isinstance(acc, str):
                acc = [s.strip() for s in acc.split(",") if s.strip()]
            authoring_payload["blanks"] = [{"blank_id": "blank_1", "accepted_answers": acc, "explanation": explanation}]

    elif activity_type == "one_word":
        acc = authoring_payload.get("accepted_answers") or []
        if isinstance(acc, str):
            acc = [s.strip() for s in acc.split(",") if s.strip()]
        if not acc and authoring_payload.get("correct_answer"):
            acc = [str(authoring_payload["correct_answer"]).strip()]
        if not acc:
            acc = [title.strip()]
        authoring_payload["question"] = str(authoring_payload.get("question") or title).strip()
        authoring_payload["accepted_answers"] = acc

    elif activity_type == "matching_pairs":
        raw_pairs = authoring_payload.get("pairs") or [
            {"pair_id": "p1", "left_text": f"{title} Concept", "right_text": "Definition"},
            {"pair_id": "p2", "left_text": "Methodology", "right_text": "Implementation"},
        ]
        authoring_payload["pairs"] = raw_pairs

    elif activity_type == "ordering":
        items = authoring_payload.get("items") or [
            {"item_id": "i1", "label": "Step 1"},
            {"item_id": "i2", "label": "Step 2"},
        ]
        authoring_payload["items"] = items
        if "correct_order" not in authoring_payload:
            authoring_payload["correct_order"] = [i["item_id"] for i in items]

    student_payload, answer_key = LearningService.sanitize_authoring_payload(
        activity_type,
        authoring_payload,
    )
    if easier_followup:
        answer_key["easier_followup"] = easier_followup
    if citation:
        answer_key["citation"] = citation

    activity = Activity(
        institution_id=tenant_id,
        learning_node_id=node_id,
        created_by_user_id=user_id,
        status="active",
    )
    db.add(activity)
    version = ActivityVersion(
        institution_id=tenant_id,
        activity=activity,
        version_number=1,
        activity_type=activity_type,
        schema_version=1,
        title=title[:240],
        student_payload_json=student_payload,
        answer_key_json=answer_key,
        scoring_config_json={
            "max_marks": 1.0,
            "difficulty": difficulty if difficulty in _DIFFICULTY_ORDER else "easy",
            "hint": hint.strip(),
            "is_remediation": is_remediation,
            "citation": citation,
            "source": "adaptive_practice",
        },
        approval_status="approved",
        created_by_user_id=user_id,
        approved_by_user_id=user_id,
        approved_at=now,
    )
    db.add(version)
    return activity, version


def _persist_mcq_activity(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    node_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    title: str,
    question_text: str,
    options: List[str],
    correct_index: int,
    explanation: str,
    hint: str,
    difficulty: str,
    is_remediation: bool = False,
    easier_followup: Optional[Dict[str, Any]] = None,
    citation: Optional[str] = None,
) -> tuple[Activity, ActivityVersion]:
    return _persist_practice_activity(
        db=db,
        tenant_id=tenant_id,
        node_id=node_id,
        user_id=user_id,
        title=title,
        activity_type="mcq",
        raw_payload={
            "question": question_text,
            "options": options,
            "correct_index": correct_index,
        },
        difficulty=difficulty,
        hint=hint,
        explanation=explanation,
        is_remediation=is_remediation,
        easier_followup=easier_followup,
        citation=citation,
    )


def _fallback_practice_questions(
    node: LearningNode,
    concepts: List[tuple[Concept, Optional[ConceptVersion]]],
    source_prompts: List[str],
) -> List[Dict[str, Any]]:
    """Deterministic fallback questions covering all pedagogical styles when Gemini is unavailable."""
    topic = node.title
    c_name = concepts[0][0].canonical_name if concepts else topic
    c_def = (
        (concepts[0][1].definition if concepts and concepts[0][1] else None)
        or node.description
        or f"Core principles and applications of {topic}."
    )
    sample_prompt = source_prompts[0] if source_prompts else f"What is the primary focus of {topic}?"

    return [
        {
            "activity_type": "mcq",
            "difficulty": "easy",
            "question": f"Which statement best describes the primary objective of {c_name}?",
            "options": [
                c_def[:180],
                f"A storage-only format unrelated to {topic}",
                "An uncalibrated noise source without signal interpretation",
                "A purely administrative metric for course logging",
            ],
            "correct_index": 0,
            "hint": f"Focus on the core function of {c_name} in {topic}.",
            "explanation": f"{c_name}: {c_def[:220]}",
            "citation": f"Course Syllabus & Lecture Slides · {topic}",
            "easier_followup": {
                "activity_type": "true_false",
                "question": f"True or False: {c_name} is directly studied under {topic}.",
                "options": ["True", "False"],
                "correct_option_id": "true",
                "hint": f"Check the module topic: {topic}.",
                "explanation": f"Yes, {c_name} is directly part of {topic}.",
            },
        },
        {
            "activity_type": "true_false",
            "difficulty": "easy",
            "question": f"In {topic}, {c_name} operates deterministically according to established engineering standards.",
            "correct_value": True,
            "options": [{"option_id": "true", "text": "True"}, {"option_id": "false", "text": "False"}],
            "hint": f"Consider whether {c_name} follows systematic principles.",
            "explanation": f"True: {c_name} provides standardized methodologies in {topic}.",
            "citation": f"Course Materials · {topic}",
        },
        {
            "activity_type": "fill_blank",
            "difficulty": "medium",
            "question": f"The core concept responsible for analyzing {topic} is [blank_1].",
            "template": f"The core concept responsible for analyzing {topic} is [blank_1].",
            "blanks": [
                {
                    "blank_id": "blank_1",
                    "accepted_answers": [c_name, c_name.lower(), topic, topic.lower()],
                    "explanation": f"{c_name} is the primary focus of this unit.",
                }
            ],
            "hint": f"Name the key subject: {c_name[:15]}...",
            "explanation": f"{c_name} is the primary analytical framework in {topic}.",
            "citation": f"Lecture Slides · {topic}",
        },
        {
            "activity_type": "one_word",
            "difficulty": "medium",
            "question": f"Identify the foundational domain or technology analyzed in: \"{sample_prompt[:140]}\"?",
            "accepted_answers": [c_name.lower(), topic.lower(), "bci", "brain computer interface"],
            "hint": f"Refers to {topic}.",
            "explanation": f"This question addresses {topic} ({c_name}).",
            "citation": f"Question Paper & Notes · {topic}",
        },
        {
            "activity_type": "matching_pairs",
            "difficulty": "hard",
            "question": f"Match each aspect of {topic} with its functional purpose:",
            "pairs": [
                {"pair_id": "p1", "left_text": f"{c_name} Theory", "right_text": "Conceptual definitions & models"},
                {"pair_id": "p2", "left_text": f"{topic} Implementation", "right_text": "Real-time processing & evaluation"},
                {"pair_id": "p3", "left_text": "System Validation", "right_text": "Verification against specifications"},
            ],
            "hint": "Match the theoretical and practical dimensions.",
            "explanation": f"Engineering systems in {topic} integrate theory, implementation, and rigorous validation.",
            "citation": f"Reference Notes · {topic}",
        },
        {
            "activity_type": "ordering",
            "difficulty": "hard",
            "question": f"Arrange the typical engineering workflow for {topic} in chronological order:",
            "items": [
                {"item_id": "s1", "label": "Requirements Formulation & Sensor Setup"},
                {"item_id": "s2", "label": "Signal Acquisition & Conditioning"},
                {"item_id": "s3", "label": "Feature Processing & Analytical Modeling"},
                {"item_id": "s4", "label": "Output Actuation & Performance Review"},
            ],
            "correct_order": ["s1", "s2", "s3", "s4"],
            "hint": "Begin with requirements setup and conclude with performance review.",
            "explanation": f"The workflow progresses sequentially from requirements to actuation and verification.",
            "citation": f"Architecture Overview · {topic}",
        },
    ]


async def _generate_practice_questions_ai(
    db: AsyncSession,
    node: LearningNode,
    concepts: List[tuple[Concept, Optional[ConceptVersion]]],
    source_prompts: List[str],
    rag_chunks: Optional[List[tuple[Any, float, str]]] = None,
) -> Optional[List[Dict[str, Any]]]:
    settings = get_settings()
    if not settings.GEMINI_API_KEY:
        return None

    offering = (
        await db.execute(
            select(CourseOffering)
            .options(selectinload(CourseOffering.curriculum_subject_entry).selectinload(CurriculumSubjectEntry.canonical_subject))
            .where(CourseOffering.id == node.course_offering_id)
        )
    ).scalars().first()
    subject_name = "this course"
    if offering and offering.curriculum_subject_entry:
        e = offering.curriculum_subject_entry
        subject_name = e.display_name_override or (e.canonical_subject.name if e.canonical_subject else e.official_subject_code)

    concept_text = "\n".join(
        f"- {c.canonical_name}: {(cv.definition if cv else '')[:220]}"
        for c, cv in concepts
    ) or f"- {node.title}: {node.description or ''}"
    q_text = "\n".join(f"- {p[:220]}" for p in source_prompts[:8]) or "(No prior exam prompts)"

    rag_text = ""
    if rag_chunks:
        rag_text = "\n\nVerified Lecture Slides and Course Documents:\n" + "\n".join(
            f"[{citation}]: {chunk.content_text[:800]}" for chunk, _, citation in rag_chunks
        )

    prompt = (
        f"You are creating an interactive practice question bank for {subject_name}.\n"
        f"Module: {node.module_title or 'Core Module'}\n"
        f"Topic: {node.title}\n"
        f"Description: {node.description or ''}\n\n"
        f"Concepts covered:\n{concept_text}\n\n"
        f"Reference questions from exam paper for this topic:\n{q_text}"
        f"{rag_text}\n\n"
        "Generate 6 diverse, objectively verifiable interactive practice questions strictly grounded in the verified lecture slides and reference questions above.\n"
        "CRITICAL RULES:\n"
        "1. Include a mix of question styles:\n"
        "   - 'mcq' (4 options, exactly 1 correct)\n"
        "   - 'true_false' (statement testing a key principle, options True and False)\n"
        "   - 'fill_blank' (sentence with '[blank_1]' and accepted_answers list)\n"
        "   - 'one_word' (short recall question where answer is a single technical term with accepted_answers list)\n"
        "   - 'matching_pairs' (3-4 pairs of concepts to definitions/components)\n"
        "   - 'ordering' (3-5 process steps in chronological sequence)\n"
        "2. Arrange difficulties: 2 'easy', 2 'medium', 2 'hard'.\n"
        "3. Every question MUST include:\n"
        "   - 'hint': A short nudge without revealing the answer.\n"
        "   - 'explanation': 1-2 sentence pedagogical explanation citing the slide or topic.\n"
        "   - 'citation': The exact slide deck or document cited (e.g. from the reference text).\n"
        "   - 'easier_followup': For medium/hard questions, a simpler scaffold question.\n"
        "4. DO NOT generate long or short subjective answers. All evaluations must be 100% deterministic.\n\n"
        "Return valid JSON ONLY matching this schema:\n"
        "{\n"
        '  "questions": [\n'
        "    {\n"
        '      "activity_type": "mcq",\n'
        '      "difficulty": "easy",\n'
        '      "question": "Which component in BCI acquires neural signals?",\n'
        '      "options": ["Signal Acquisition", "Feature Extraction", "Classifier", "Effector"],\n'
        '      "correct_index": 0,\n'
        '      "hint": "Think about the sensor/electrode stage.",\n'
        '      "explanation": "Signal acquisition uses electrodes to capture brain activity directly.",\n'
        '      "citation": "BCI_System_Structure_MODULE 1.pptx · Slide 4"\n'
        "    },\n"
        "    {\n"
        '      "activity_type": "true_false",\n'
        '      "difficulty": "easy",\n'
        '      "question": "Non-invasive BCIs require surgical implantation inside the skull.",\n'
        '      "correct_value": false,\n'
        '      "hint": "Consider scalp surface EEG.",\n'
        '      "explanation": "Non-invasive BCIs use scalp sensors with no surgery required.",\n'
        '      "citation": "Invasive_Partially_Invasive_Non_Invasive_BCI_Comparison.pptx · Slide 3"\n'
        "    },\n"
        "    {\n"
        '      "activity_type": "fill_blank",\n'
        '      "difficulty": "medium",\n'
        '      "question": "The physiological monitoring method recording electrical brain activity from the scalp is called [blank_1].",\n'
        '      "template": "The physiological monitoring method recording electrical brain activity from the scalp is called [blank_1].",\n'
        '      "blanks": [{"blank_id": "blank_1", "accepted_answers": ["EEG", "electroencephalography", "electroencephalogram"]}],\n'
        '      "hint": "A 3-letter acronym beginning with E.",\n'
        '      "explanation": "EEG measures voltage fluctuations from ionic current within the brain neurons.",\n'
        '      "citation": "BCI_System_Structure_MODULE 1.pptx · Slide 6"\n'
        "    },\n"
        "    {\n"
        '      "activity_type": "one_word",\n'
        '      "difficulty": "medium",\n'
        '      "question": "What type of BCI places electrodes directly on the exposed surface of the brain (ECoG)?",\n'
        '      "accepted_answers": ["partially invasive", "partially-invasive", "semi-invasive", "ECoG"],\n'
        '      "hint": "It is between fully invasive and non-invasive.",\n'
        '      "explanation": "Partially invasive BCIs use electrocorticography on the cortex surface.",\n'
        '      "citation": "Invasive_Partially_Invasive_Non_Invasive_BCI_Comparison.pptx · Slide 5"\n'
        "    },\n"
        "    {\n"
        '      "activity_type": "matching_pairs",\n'
        '      "difficulty": "hard",\n'
        '      "question": "Match each BCI type with its characteristic recording location:",\n'
        '      "pairs": [\n'
        '        {"pair_id": "p1", "left_text": "Non-Invasive", "right_text": "Scalp Surface (EEG)"},\n'
        '        {"pair_id": "p2", "left_text": "Partially Invasive", "right_text": "Cortical Surface (ECoG)"},\n'
        '        {"pair_id": "p3", "left_text": "Invasive", "right_text": "Inside Grey Matter (Microelectrodes)"}\n'
        '      ],\n'
        '      "hint": "Associate the invasiveness depth with tissue penetration.",\n'
        '      "explanation": "Non-invasive is on scalp, partially invasive is subdural, and invasive penetrates cortical tissue.",\n'
        '      "citation": "Invasive_Partially_Invasive_Non_Invasive_BCI_Comparison.pptx · Slide 8"\n'
        "    },\n"
        "    {\n"
        '      "activity_type": "ordering",\n'
        '      "difficulty": "hard",\n'
        '      "question": "Arrange the standard BCI pipeline stages in sequential order:",\n'
        '      "items": [\n'
        '        {"item_id": "s1", "label": "Signal Acquisition"},\n'
        '        {"item_id": "s2", "label": "Signal Preprocessing & Artifact Removal"},\n'
        '        {"item_id": "s3", "label": "Feature Extraction"},\n'
        '        {"item_id": "s4", "label": "Classification & Decoding"},\n'
        '        {"item_id": "s5", "label": "Device Control / Feedback"}\n'
        '      ],\n'
        '      "correct_order": ["s1", "s2", "s3", "s4", "s5"],\n'
        '      "hint": "Start with signal input and end with device actuation.",\n'
        '      "explanation": "The BCI pipeline flows from acquisition through preprocessing, feature extraction, classification, and device actuation.",\n'
        '      "citation": "BCI_System_Structure_MODULE 1.pptx · Slide 2"\n'
        "    }\n"
        "  ]\n"
        "}\n"
    )

    models = list(
        dict.fromkeys(
            [
                settings.GEMINI_MODEL,
                *[m.strip() for m in getattr(settings, "GEMINI_FALLBACK_MODELS", "").split(",") if m.strip()],
                getattr(settings, "GEMINI_REPAIR_MODEL", settings.GEMINI_MODEL),
            ]
        )
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.35},
    }
    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            for model in models:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
                resp = await client.post(url, headers={"x-goog-api-key": settings.GEMINI_API_KEY}, json=payload)
                if resp.status_code != 200:
                    continue
                parts = (resp.json().get("candidates") or [{}])[0].get("content", {}).get("parts") or [{}]
                raw = (parts[0].get("text") or "").strip()
                if raw.startswith("```"):
                    raw = raw.strip("`").removeprefix("json").strip()
                parsed = json.loads(raw)
                items = parsed.get("questions") if isinstance(parsed, dict) else parsed
                if isinstance(items, list) and len(items) >= 3:
                    return [q for q in items if isinstance(q, dict) and (q.get("question") or q.get("template"))]
    except Exception as exc:
        logger.warning("Adaptive practice AI generation failed node=%s error=%s", node.id, exc)
    return None


async def _load_node_mcq_versions(db: AsyncSession, node_id: uuid.UUID) -> List[ActivityVersion]:
    stmt = (
        select(ActivityVersion)
        .join(Activity, ActivityVersion.activity_id == Activity.id)
        .where(
            Activity.learning_node_id == node_id,
            Activity.status == "active",
            ActivityVersion.approval_status == "approved",
        )
        .order_by(ActivityVersion.created_at.asc())
    )
    return list((await db.execute(stmt)).scalars().all())


async def _ensure_node_practice_bank(
    db: AsyncSession,
    node: LearningNode,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    force: bool = False,
) -> List[ActivityVersion]:
    existing = await _load_node_mcq_versions(db, node.id)
    main_items = [v for v in existing if not (v.scoring_config_json or {}).get("is_remediation")]
    if not force and len(main_items) >= 3:
        return existing

    # Gather node concepts and source prompts
    concept_links = (
        await db.execute(
            select(Concept)
            .join(LearningNodeConcept, LearningNodeConcept.concept_id == Concept.id)
            .where(LearningNodeConcept.learning_node_id == node.id)
        )
    ).scalars().all()
    concepts_with_ver: List[tuple[Concept, Optional[ConceptVersion]]] = []
    for c in concept_links:
        cv = (
            await db.execute(
                select(ConceptVersion)
                .where(ConceptVersion.concept_id == c.id)
                .order_by(ConceptVersion.version_number.desc())
                .limit(1)
            )
        ).scalars().first()
        concepts_with_ver.append((c, cv))

    source_prompts = list(
        (
            await db.execute(
                select(QuestionVersion.prompt_text)
                .join(LearningNodeQuestion, LearningNodeQuestion.question_version_id == QuestionVersion.id)
                .where(LearningNodeQuestion.learning_node_id == node.id)
                .limit(10)
            )
        ).scalars().all()
    )

    # Retrieve relevant RAG chunks from slides, notes, and syllabus for this node
    rag_chunks = await find_top_k_chunks(
        db,
        node.course_offering_id,
        f"{node.title} {node.module_title or ''}",
        top_k=3,
    )
    primary_citation = rag_chunks[0][2] if rag_chunks else None

    generated = await _generate_practice_questions_ai(db, node, concepts_with_ver, source_prompts, rag_chunks=rag_chunks)
    if not generated:
        generated = _fallback_practice_questions(node, concepts_with_ver, source_prompts)

    for idx, q in enumerate(generated, start=len(existing) + 1):
        act_type = str(q.get("activity_type") or "mcq").lower()
        diff = str(q.get("difficulty") or "easy").lower()
        if diff not in _DIFFICULTY_ORDER:
            diff = "easy"
        cit = q.get("citation") or primary_citation
        _persist_practice_activity(
            db=db,
            tenant_id=tenant_id,
            node_id=node.id,
            user_id=user_id,
            title=f"{node.title} · Q{idx}",
            activity_type=act_type,
            raw_payload=q,
            difficulty=diff,
            hint=str(q.get("hint") or f"Think about the core rule of {node.title}."),
            explanation=str(q.get("explanation") or f"Review the key idea of {node.title}."),
            is_remediation=False,
            easier_followup=q.get("easier_followup") if isinstance(q.get("easier_followup"), dict) else None,
            citation=cit,
        )
    await db.flush()
    return await _load_node_mcq_versions(db, node.id)


def _pick_next_question(
    pool: List[ActivityVersion],
    target_difficulty: str,
    seen_ids: set[uuid.UUID],
    exclude_id: Optional[uuid.UUID] = None,
) -> Optional[ActivityVersion]:
    main_pool = [v for v in pool if not (v.scoring_config_json or {}).get("is_remediation")]
    candidates = main_pool or pool
    if not candidates:
        return None

    unseen = [v for v in candidates if v.id not in seen_ids and v.id != exclude_id]
    if unseen:
        exact = [v for v in unseen if (v.scoring_config_json or {}).get("difficulty", "easy") == target_difficulty]
        if exact:
            return exact[0]
        # Prefer closest difficulty
        target_idx = _DIFFICULTY_ORDER.index(target_difficulty) if target_difficulty in _DIFFICULTY_ORDER else 0
        unseen.sort(
            key=lambda v: abs(
                _DIFFICULTY_ORDER.index(
                    (v.scoring_config_json or {}).get("difficulty", "easy")
                    if (v.scoring_config_json or {}).get("difficulty", "easy") in _DIFFICULTY_ORDER
                    else "easy"
                )
                - target_idx
            )
        )
        return unseen[0]

    # If all unseen exhausted, pick any other than exclude_id matching target_difficulty
    others = [v for v in candidates if v.id != exclude_id] or candidates
    exact_other = [v for v in others if (v.scoring_config_json or {}).get("difficulty", "easy") == target_difficulty]
    return exact_other[0] if exact_other else others[0]


async def _pick_or_create_remediation_question(
    db: AsyncSession,
    node: LearningNode,
    missed_v: ActivityVersion,
    pool: List[ActivityVersion],
    seen_ids: set[uuid.UUID],
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
) -> ActivityVersion:
    # 1. Check if missed_v has a pre-generated easier_followup in answer_key_json
    followup = (missed_v.answer_key_json or {}).get("easier_followup")
    if isinstance(followup, dict) and followup.get("question") and isinstance(followup.get("options"), list):
        f_title = f"Easier follow-up · {node.title}"
        existing_rem = next(
            (
                v
                for v in pool
                if (v.scoring_config_json or {}).get("is_remediation")
                and (v.student_payload_json or {}).get("question") == followup["question"]
                and v.id not in seen_ids
            ),
            None,
        )
        if existing_rem:
            return existing_rem
        _, rem_v = _persist_mcq_activity(
            db,
            tenant_id,
            node.id,
            user_id,
            title=f_title,
            question_text=str(followup["question"]),
            options=[str(o) for o in followup["options"]],
            correct_index=int(followup.get("correct_index", 0) or 0),
            explanation=str(followup.get("explanation") or (missed_v.answer_key_json or {}).get("explanation") or ""),
            hint=str(followup.get("hint") or "Recall the explanation shown above."),
            difficulty="easy",
            is_remediation=True,
        )
        await db.flush()
        return rem_v

    # 2. Otherwise pick an unseen easy/remediation item from the pool
    unseen_easy = [
        v
        for v in pool
        if v.id != missed_v.id
        and v.id not in seen_ids
        and (v.scoring_config_json or {}).get("difficulty", "easy") == "easy"
    ]
    if unseen_easy:
        return unseen_easy[0]

    # 3. Synthesize a foundational scaffold question directly from the explanation
    expl = str((missed_v.answer_key_json or {}).get("explanation") or f"This tests a core concept of {node.title}.")
    _, rem_v = _persist_mcq_activity(
        db,
        tenant_id,
        node.id,
        user_id,
        title=f"Easier follow-up · {node.title}",
        question_text=f"Based on the explanation (\"{expl[:160]}\"), which statement is true?",
        options=[
            expl[:160],
            f"It is unrelated to {node.title}",
            "None of the concepts in this module apply",
        ],
        correct_index=0,
        explanation=expl,
        hint="Look closely at the explanation you just read.",
        difficulty="easy",
        is_remediation=True,
    )
    await db.flush()
    return rem_v


class AdaptivePracticeService:

    @staticmethod
    async def start_or_resume_practice(
        db: AsyncSession,
        node_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PracticeSessionStartOut:
        node = await db.get(LearningNode, node_id)
        if not node or node.institution_id != tenant_id:
            raise AppException(status_code=404, code="NODE_NOT_FOUND", message="Learning node not found.")

        await KnowledgeService.verify_student_access(
            db=db, offering_id=node.course_offering_id, tenant_id=tenant_id, user_id=user_id
        )
        mem = await _get_student_membership(db, tenant_id, user_id)
        await _ensure_node_unlocked(db, node, mem.id)

        pool = await _ensure_node_practice_bank(db, node, tenant_id, user_id)
        main_count = len([v for v in pool if not (v.scoring_config_json or {}).get("is_remediation")]) or len(pool)

        # Find active in-progress session (or latest completed session if restarting)
        session = (
            await db.execute(
                select(StudentPracticeSession)
                .where(
                    StudentPracticeSession.student_membership_id == mem.id,
                    StudentPracticeSession.learning_node_id == node.id,
                    StudentPracticeSession.status == "in_progress",
                )
                .order_by(StudentPracticeSession.created_at.desc())
                .limit(1)
            )
        ).scalars().first()

        if not session:
            target_correct = min(5, max(2, main_count))
            session = StudentPracticeSession(
                institution_id=tenant_id,
                student_membership_id=mem.id,
                course_offering_id=node.course_offering_id,
                learning_node_id=node.id,
                status="in_progress",
                current_difficulty="easy",
                target_correct_count=target_correct,
            )
            db.add(session)
            await db.flush()

        # Upsert StudentLearningNodeProgress to in_progress if not completed
        prog = (
            await db.execute(
                select(StudentLearningNodeProgress).where(
                    StudentLearningNodeProgress.student_membership_id == mem.id,
                    StudentLearningNodeProgress.learning_node_id == node.id,
                )
            )
        ).scalars().first()
        now = datetime.now(timezone.utc)
        if not prog:
            db.add(
                StudentLearningNodeProgress(
                    institution_id=tenant_id,
                    student_membership_id=mem.id,
                    learning_node_id=node.id,
                    progress_status="in_progress",
                    first_started_at=now,
                )
            )
        elif prog.progress_status in ("available", "locked"):
            prog.progress_status = "in_progress"
            prog.first_started_at = prog.first_started_at or now

        seen_ids = set(
            (
                await db.execute(
                    select(StudentPracticeEvent.activity_version_id).where(
                        StudentPracticeEvent.session_id == session.id,
                        StudentPracticeEvent.event_type == "answer_submitted",
                    )
                )
            ).scalars().all()
        )

        current_v = (
            next((v for v in pool if v.id == session.current_activity_version_id), None)
            if session.current_activity_version_id
            else None
        )
        if not current_v:
            current_v = _pick_next_question(pool, session.current_difficulty, seen_ids)
            if current_v:
                session.current_activity_version_id = current_v.id

        await db.commit()
        await db.refresh(session)
        return PracticeSessionStartOut(
            node_id=node.id,
            node_title=node.title,
            module_title=node.module_title,
            session=_build_session_state_out(session),
            current_question=_to_practice_question_out(current_v) if current_v else None,
        )

    @staticmethod
    async def request_hint(
        db: AsyncSession,
        session_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> PracticeHintOut:
        mem = await _get_student_membership(db, tenant_id, user_id)
        session = await db.get(StudentPracticeSession, session_id)
        if not session or session.institution_id != tenant_id or session.student_membership_id != mem.id:
            raise AppException(status_code=404, code="SESSION_NOT_FOUND", message="Practice session not found.")
        if not session.current_activity_version_id:
            raise AppException(status_code=400, code="NO_ACTIVE_QUESTION", message="No active question in this session.")

        act_v = await db.get(ActivityVersion, session.current_activity_version_id)
        cfg = (act_v.scoring_config_json or {}) if act_v else {}
        hint_text = str(cfg.get("hint") or "Break the question down into its core definition and eliminate clearly wrong options.")

        # Idempotent per active question turn (count once per question answered so far)
        existing_hint = (
            await db.execute(
                select(StudentPracticeEvent).where(
                    StudentPracticeEvent.session_id == session.id,
                    StudentPracticeEvent.activity_version_id == session.current_activity_version_id,
                    StudentPracticeEvent.event_type == "hint_requested",
                )
            )
        ).scalars().first()
        if not existing_hint:
            session.hints_used += 1
            db.add(
                StudentPracticeEvent(
                    institution_id=tenant_id,
                    session_id=session.id,
                    student_membership_id=mem.id,
                    learning_node_id=session.learning_node_id,
                    activity_version_id=session.current_activity_version_id,
                    event_type="hint_requested",
                    difficulty_tier=session.current_difficulty,
                    is_remediation=session.in_remediation,
                    hint_used=True,
                )
            )
            await db.commit()
            await db.refresh(session)

        return PracticeHintOut(hint=hint_text, hints_used=session.hints_used)

    @staticmethod
    async def submit_answer(
        db: AsyncSession,
        session_id: uuid.UUID,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        data: PracticeAnswerRequest,
    ) -> PracticeAnswerResultOut:
        mem = await _get_student_membership(db, tenant_id, user_id)
        session = await db.get(StudentPracticeSession, session_id)
        if not session or session.institution_id != tenant_id or session.student_membership_id != mem.id:
            raise AppException(status_code=404, code="SESSION_NOT_FOUND", message="Practice session not found.")
        if session.status != "in_progress":
            raise AppException(status_code=400, code="SESSION_COMPLETED", message="This practice session is already completed.")

        act_v = await db.get(ActivityVersion, data.activity_version_id)
        if not act_v or act_v.institution_id != tenant_id:
            raise AppException(status_code=404, code="ACTIVITY_NOT_FOUND", message="Question not found.")

        node = await db.get(LearningNode, session.learning_node_id)
        pool = await _load_node_mcq_versions(db, session.learning_node_id)

        response_payload = {
            "selected_option_id": data.selected_option_id,
            "text_answer": data.text_answer,
            "answer": data.text_answer or data.selected_option_id,
            "answers": data.answers or {},
            "pairs": data.pairs or [],
            "order": data.order or [],
            "classifications": data.classifications or {},
        }
        eval_res = evaluate_activity_response(
            activity_type=act_v.activity_type,
            response_data=response_payload,
            answer_key=act_v.answer_key_json,
            scoring_config=act_v.scoring_config_json,
        )
        is_correct = bool(eval_res.is_correct)
        ans_key = act_v.answer_key_json or {}
        correct_option_id = ans_key.get("correct_option_id")

        # Robustly resolve explanation across all activity types without crashing on missing attributes
        explanation = ans_key.get("explanation")
        if not explanation and "blanks" in ans_key:
            for b_info in (ans_key.get("blanks") or {}).values():
                if isinstance(b_info, dict) and b_info.get("explanation"):
                    explanation = b_info["explanation"]
                    break
        if not explanation and isinstance(eval_res.details, dict):
            explanation = eval_res.details.get("feedback")
        if not explanation:
            explanation = (act_v.scoring_config_json or {}).get("explanation") or "Review this concept and try the next step."

        if not is_correct and not correct_option_id and "blanks" in ans_key:
            accepted_answers = []
            for b_info in (ans_key.get("blanks") or {}).values():
                if isinstance(b_info, dict) and b_info.get("accepted_answers"):
                    accepted_answers.extend([str(a) for a in b_info["accepted_answers"] if a])
            if accepted_answers and not any(a.lower() in str(explanation).lower() for a in accepted_answers):
                explanation = f"Accepted answer: {accepted_answers[0]}.\n\n{explanation}"

        explanation = str(explanation)
        citation = ans_key.get("citation") or (act_v.scoring_config_json or {}).get("citation")
        if citation and citation not in explanation:
            explanation = f"{explanation}\n\n📖 Reference: {citation}"

        hint_used_here = bool(
            await db.scalar(
                select(StudentPracticeEvent.id).where(
                    StudentPracticeEvent.session_id == session.id,
                    StudentPracticeEvent.activity_version_id == act_v.id,
                    StudentPracticeEvent.event_type == "hint_requested",
                ).limit(1)
            )
        )

        seen_ids = set(
            (
                await db.execute(
                    select(StudentPracticeEvent.activity_version_id).where(
                        StudentPracticeEvent.session_id == session.id,
                        StudentPracticeEvent.event_type == "answer_submitted",
                    )
                )
            ).scalars().all()
        )
        seen_ids.add(act_v.id)

        session.questions_answered += 1
        was_remediation = session.in_remediation
        node_completed = False
        next_v: Optional[ActivityVersion] = None

        if is_correct:
            session.correct_count += 1
            if session.consecutive_mistakes > 0 or was_remediation:
                session.recovered_after_mistake_count += 1
            session.consecutive_mistakes = 0

            if was_remediation:
                session.in_remediation = False
                session.remediation_for_activity_version_id = None
                feedback_summary = "Nice recovery! You understood the concept — returning to your normal progression."
            else:
                prev_diff = session.current_difficulty
                session.current_difficulty = _next_harder(prev_diff)
                if session.current_difficulty != prev_diff:
                    feedback_summary = f"Correct! Moving up to a {session.current_difficulty.capitalize()} question."
                else:
                    feedback_summary = "Correct! Keep going."

            if session.correct_count >= session.target_correct_count and not session.in_remediation:
                node_completed = True
                session.status = "completed"
                session.completed_at = datetime.now(timezone.utc)
                session.current_activity_version_id = None
                feedback_summary = "Topic mastered! Next roadmap topic unlocked."
                prog = (
                    await db.execute(
                        select(StudentLearningNodeProgress).where(
                            StudentLearningNodeProgress.student_membership_id == mem.id,
                            StudentLearningNodeProgress.learning_node_id == session.learning_node_id,
                        )
                    )
                ).scalars().first()
                now = datetime.now(timezone.utc)
                if prog:
                    prog.progress_status = "completed"
                    prog.completed_at = prog.completed_at or now
                else:
                    db.add(
                        StudentLearningNodeProgress(
                            institution_id=tenant_id,
                            student_membership_id=mem.id,
                            learning_node_id=session.learning_node_id,
                            progress_status="completed",
                            first_started_at=now,
                            completed_at=now,
                        )
                    )
            else:
                next_v = _pick_next_question(pool, session.current_difficulty, seen_ids, exclude_id=act_v.id)
                session.current_activity_version_id = next_v.id if next_v else None
        else:
            session.mistake_count += 1
            session.consecutive_mistakes += 1
            session.easier_followups_triggered += 1
            session.current_difficulty = _next_easier(session.current_difficulty)
            session.in_remediation = True
            session.remediation_for_activity_version_id = act_v.id
            feedback_summary = "Not quite — review the short explanation below, then try an easier follow-up question."

            next_v = await _pick_or_create_remediation_question(
                db=db,
                node=node,
                missed_v=act_v,
                pool=pool,
                seen_ids=seen_ids,
                tenant_id=tenant_id,
                user_id=user_id,
            )
            session.current_activity_version_id = next_v.id if next_v else None

        db.add(
            StudentPracticeEvent(
                institution_id=tenant_id,
                session_id=session.id,
                student_membership_id=mem.id,
                learning_node_id=session.learning_node_id,
                activity_version_id=act_v.id,
                event_type="answer_submitted",
                difficulty_tier=(act_v.scoring_config_json or {}).get("difficulty", session.current_difficulty),
                is_remediation=was_remediation,
                is_correct=is_correct,
                hint_used=hint_used_here,
                selected_option_id=data.selected_option_id or (data.text_answer[:80] if data.text_answer else None),
                metadata_json={"next_difficulty": session.current_difficulty, "node_completed": node_completed},
            )
        )
        await db.commit()
        await db.refresh(session)

        return PracticeAnswerResultOut(
            is_correct=is_correct,
            correct_option_id=str(correct_option_id) if correct_option_id else None,
            explanation=explanation,
            feedback_summary=feedback_summary,
            citation=citation,
            node_completed=node_completed,
            session=_build_session_state_out(session),
            next_question=_to_practice_question_out(next_v) if (next_v and not node_completed) else None,
        )

