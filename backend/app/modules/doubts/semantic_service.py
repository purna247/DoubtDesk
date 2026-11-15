from __future__ import annotations
import uuid
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.doubts.models import Doubt
from app.modules.knowledge.models import (
    SyllabusNode,
    Concept,
    CourseContentVersion,
    CourseContentConcept,
)

STOP_WORDS = {
    "a", "an", "the", "and", "or", "but", "if", "because", "as", "what",
    "which", "this", "that", "these", "those", "then", "just", "so", "than",
    "such", "both", "through", "about", "for", "is", "of", "while", "during",
    "to", "from", "in", "out", "on", "off", "again", "further", "then", "once",
    "why", "how", "all", "any", "can", "someone", "explain", "i", "my", "we",
    "you", "do", "does", "did", "doing", "would", "should", "could", "please",
}


def _tokenize(text: str) -> List[str]:
    """Tokenize text into lowercase alphanumeric keywords excluding stop words."""
    words = re.findall(r"[a-zA-Z0-9_\-\+]+", text.lower())
    return [w for w in words if len(w) > 1 and w not in STOP_WORDS]


@dataclass
class SemanticVerdict:
    extracted_confusion: str
    matched_node_id: Optional[uuid.UUID] = None
    matched_node_title: Optional[str] = None
    matched_concept_id: Optional[uuid.UUID] = None
    matched_concept_name: Optional[str] = None
    candidate_misconceptions: List[str] = field(default_factory=list)
    confidence_score: float = 0.0


class DeterministicSemanticAdapter:
    """
    Fast, deterministic semantic classifier utilizing token overlap,
    keyword matching, and heuristic misconception extraction.
    Zero external network dependencies, suitable for tests and production fallback.
    """

    @staticmethod
    def analyze(
        title: str,
        body: str,
        syllabus_nodes: List[SyllabusNode],
        concepts: List[Concept],
    ) -> SemanticVerdict:
        full_text = f"{title} {body}"
        query_tokens = set(_tokenize(full_text))

        # 1. Match against Syllabus Nodes
        best_node: Optional[SyllabusNode] = None
        best_node_score = 0.0

        for node in syllabus_nodes:
            node_text = f"{node.title} {node.description or ''}"
            node_tokens = set(_tokenize(node_text))
            if not node_tokens:
                continue

            intersection = query_tokens.intersection(node_tokens)
            # Jaccard overlap + bonus for exact substring containment of key phrases
            overlap = len(intersection) / len(node_tokens.union(query_tokens)) if query_tokens else 0.0
            if node.title.lower() in full_text.lower():
                overlap += 0.5
            elif any(token in node.title.lower() for token in query_tokens):
                overlap += 0.2

            if overlap > best_node_score:
                best_node_score = overlap
                best_node = node

        # 2. Match against Canonical Concepts
        best_concept: Optional[Concept] = None
        best_concept_score = 0.0

        for concept in concepts:
            concept_text = f"{concept.canonical_name} {concept.concept_code or ''}"
            concept_tokens = set(_tokenize(concept_text))
            if not concept_tokens:
                continue

            intersection = query_tokens.intersection(concept_tokens)
            overlap = len(intersection) / len(concept_tokens.union(query_tokens)) if query_tokens else 0.0
            if concept.canonical_name.lower() in full_text.lower():
                overlap += 0.6
            elif any(token in concept.canonical_name.lower() for token in query_tokens):
                overlap += 0.25

            if overlap > best_concept_score:
                best_concept_score = overlap
                best_concept = concept

        # 3. Detect candidate misconception patterns
        candidate_misconceptions: List[str] = []
        lower_text = full_text.lower()
        if "ecg" in lower_text and ("cortex" in lower_text or "invasive" in lower_text or "microelectrode" in lower_text):
            candidate_misconceptions.append("ecg_confused_with_invasive_ecog")
        if "binary search" in lower_text and ("o(n)" in lower_text or "linear" in lower_text):
            candidate_misconceptions.append("binary_search_assumed_linear_runtime")
        if "recolor" in lower_text and "rotate" in lower_text:
            candidate_misconceptions.append("red_black_tree_uncle_recoloring_vs_rotation")

        # 4. Formulate confusion summary
        extracted_confusion = title.strip()
        if not extracted_confusion.endswith("?"):
            extracted_confusion += "?"

        confidence = round(min(1.0, max(best_node_score, best_concept_score, 0.45 if query_tokens else 0.1)), 2)

        return SemanticVerdict(
            extracted_confusion=extracted_confusion,
            matched_node_id=best_node.id if best_node and best_node_score >= 0.15 else None,
            matched_node_title=best_node.title if best_node and best_node_score >= 0.15 else None,
            matched_concept_id=best_concept.id if best_concept and best_concept_score >= 0.15 else None,
            matched_concept_name=best_concept.canonical_name if best_concept and best_concept_score >= 0.15 else None,
            candidate_misconceptions=candidate_misconceptions,
            confidence_score=confidence,
        )


class DoubtSemanticService:
    """
    Deep Module for Doubt Structuring, Topic Binding & Semantic Analysis.
    Decoupled from specific LLM providers via swappable adapter seam.
    """

    adapter = DeterministicSemanticAdapter()

    @classmethod
    async def classify_and_tag_doubt(
        cls,
        db: AsyncSession,
        doubt_id: uuid.UUID,
    ) -> Optional[Doubt]:
        """
        Executes the 3-stage semantic analysis on a doubt:
        1. Ingests doubt title, body, and course syllabus context.
        2. Dispatches to the classifier adapter for topic & misconception inference.
        3. Deterministically commits metadata and links missing topic/concept foreign keys.
        """
        stmt = (
            select(Doubt)
            .options(
                selectinload(Doubt.syllabus_node),
                selectinload(Doubt.concept),
            )
            .where(Doubt.id == doubt_id)
        )
        doubt = (await db.execute(stmt)).scalars().first()
        if not doubt or doubt.status == "removed":
            return None

        # Gather syllabus nodes for the course offering
        syllabus_nodes: List[SyllabusNode] = []
        if doubt.course_offering_id:
            # Query nodes belonging to any content version of this course offering
            node_stmt = (
                select(SyllabusNode)
                .join(CourseContentVersion, SyllabusNode.course_content_version_id == CourseContentVersion.id)
                .where(CourseContentVersion.course_offering_id == doubt.course_offering_id)
                .order_by(SyllabusNode.sequence_no.asc())
            )
            syllabus_nodes = list((await db.execute(node_stmt)).scalars().all())

        # Gather active concepts for the institution
        concept_stmt = (
            select(Concept)
            .where(
                Concept.institution_id == doubt.institution_id,
                Concept.status == "active",
            )
        )
        concepts = list((await db.execute(concept_stmt)).scalars().all())

        # Analyze using adapter
        verdict = cls.adapter.analyze(
            title=doubt.title,
            body=doubt.body_markdown,
            syllabus_nodes=syllabus_nodes,
            concepts=concepts,
        )

        # Stage 3: Deterministic Merger
        # If user did not manually pick a topic, and classifier found a match with good confidence:
        if not doubt.syllabus_node_id and verdict.matched_node_id:
            doubt.syllabus_node_id = verdict.matched_node_id

        if not doubt.concept_id and verdict.matched_concept_id:
            doubt.concept_id = verdict.matched_concept_id

        # Update semantic metadata
        doubt.semantic_metadata = {
            "extracted_confusion": verdict.extracted_confusion,
            "matched_topic_title": verdict.matched_node_title or (doubt.syllabus_node.title if doubt.syllabus_node else None),
            "matched_concept_name": verdict.matched_concept_name or (doubt.concept.canonical_name if doubt.concept else None),
            "candidate_misconceptions": verdict.candidate_misconceptions,
            "confidence_score": verdict.confidence_score,
            "analyzed_at": datetime.now(timezone.utc).isoformat(),
        }

        db.add(doubt)
        await db.commit()
        await db.refresh(doubt)
        return doubt
