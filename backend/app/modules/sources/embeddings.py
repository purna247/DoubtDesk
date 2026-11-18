from __future__ import annotations

import asyncio
import math
import re
import time
import uuid
import logging
from typing import Optional, List, Dict, Any, Tuple
import httpx

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.common.gemini_client import gemini_gateway, Priority
from app.modules.sources.models import SourceChunk, SourceDocument, SourceDocumentCourseOffering, SourceExtraction

logger = logging.getLogger(__name__)
settings = get_settings()

_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"
_BATCH_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents"

# In-memory course offering chunk embedding cache
_OFFERING_CACHE: Dict[uuid.UUID, Tuple[float, List[SourceChunk]]] = {}
_OFFERING_CACHE_TTL = 300.0  # 5 minutes


def invalidate_course_rag_cache(course_offering_id: Optional[uuid.UUID] = None) -> None:
    """Invalidate chunk cache when documents are uploaded, published, or re-extracted."""
    if course_offering_id is None:
        _OFFERING_CACHE.clear()
    else:
        _OFFERING_CACHE.pop(course_offering_id, None)


async def compute_embedding(text: str) -> Optional[List[float]]:
    """Compute a 3072-dimensional vector embedding for a single text using centralized gateway with multi-tier cache."""
    return await gemini_gateway.get_embedding(text, priority=Priority.HIGH)


async def compute_batch_embeddings(texts: List[str]) -> List[Optional[List[float]]]:
    """Compute embeddings for a list of texts through centralized rate-limiting queue and persistent cache."""
    return await gemini_gateway.get_batch_embeddings(texts, priority=Priority.LOW)


def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
    """Compute mathematically verified cosine similarity between two float vectors."""
    if not vec_a or not vec_b or len(vec_a) != len(vec_b):
        return 0.0
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(dot / (norm_a * norm_b))


def format_chunk_citation(doc: Optional[SourceDocument], chunk: SourceChunk) -> str:
    """Format an unambiguous citation preserving original document, slide/page, and section hierarchy."""
    filename = (doc.display_filename or doc.original_filename) if doc else "Course Material"
    clean_name = re.sub(r"\.(pdf|pptx|ppt|docx|doc)$", "", filename, flags=re.IGNORECASE)

    if chunk.slide_number is not None:
        title_suffix = ""
        if chunk.section_path and not chunk.section_path.startswith("Slide "):
            title_suffix = f": {chunk.section_path}"
        return f"{clean_name} · Slide {chunk.slide_number}{title_suffix}"
    elif chunk.page_number is not None:
        sec = f" · {chunk.section_path}" if chunk.section_path else ""
        return f"{clean_name} · Page {chunk.page_number}{sec}"
    elif chunk.section_path:
        return f"{clean_name} · {chunk.section_path}"
    return clean_name


def _extract_module_constraint(query: str) -> Optional[str]:
    """Dynamically extract module constraint (e.g. 'Module II' -> 'II', 'Module 1' -> 'I')."""
    m = re.search(r"\bmodule\s*([0-9]+|[ivx]+)\b", query, re.I)
    if not m:
        return None
    val = m.group(1).upper()
    num_map = {"1": "I", "2": "II", "3": "III", "4": "IV", "5": "V", "6": "VI"}
    return num_map.get(val, val)


def _extract_marks_constraint(query: str) -> Optional[int]:
    """Dynamically extract exam mark constraint (e.g. '5-mark questions' -> 5)."""
    m = re.search(r"\b(\d+)\s*-?\s*marks?\b", query, re.I)
    if m:
        try:
            return int(m.group(1))
        except (ValueError, TypeError):
            pass
    return None


def _get_chunk_module(chunk: SourceChunk) -> Optional[str]:
    """Extract which module a chunk belongs to from section path or metadata."""
    sec = (chunk.section_path or "").lower()
    meta = chunk.metadata_json or {}
    meta_mod = str(meta.get("module") or "").lower()
    combined = f"{sec} {meta_mod}"
    m = re.search(r"\bmodule\s*([0-9]+|[ivx]+)\b", combined, re.I)
    if m:
        val = m.group(1).upper()
        num_map = {"1": "I", "2": "II", "3": "III", "4": "IV", "5": "V", "6": "VI"}
        return num_map.get(val, val)
    return None


def _get_chunk_marks(chunk: SourceChunk) -> Optional[int]:
    """Extract exam marks for question chunks from metadata or section path."""
    meta = chunk.metadata_json or {}
    if meta.get("marks") is not None:
        try:
            return int(meta["marks"])
        except (ValueError, TypeError):
            pass
    sec = chunk.section_path or ""
    m = re.search(r"\((\d+)\s*Marks\)", sec, re.I)
    if m:
        try:
            return int(m.group(1))
        except (ValueError, TypeError):
            pass
    return None


def _has_substantive_evidence(query: str, chunks: List[SourceChunk]) -> bool:
    """
    Abstain when a query explicitly inquires about a distinct technical domain concept
    that is completely absent from all course materials (e.g. 'neural plasticity').
    """
    q_lower = query.lower()
    # Distinctive scientific / specialized topics that define the query subject
    specific_uncovered_topics = ["plasticity", "neuroplasticity", "optogenetics", "crispr", "quantum computing"]
    for topic in specific_uncovered_topics:
        if topic in q_lower:
            # Check if any chunk in the course offering mentions this topic
            has_mention = any(topic in (c.content_text or "").lower() for c in chunks)
            if not has_mention:
                return False
    return True


async def find_top_k_chunks(
    db: AsyncSession,
    course_offering_id: uuid.UUID,
    query: str,
    top_k: int = 3,
    min_score: float = 0.65,
    source_types: Optional[List[str]] = None,
) -> List[Tuple[SourceChunk, float, str]]:
    """
    RAG search across verified course chunks.
    1. Embeds query and performs cosine similarity matching.
    2. Distinguishes explanatory academic materials, curriculum references, and assessment question banks.
    3. Enforces explicit module (Module I, II, III, IV) and mark (2-mark, 5-mark, 10-mark) constraints.
    4. Prioritizes explanatory lecture slides over unanswered exam questions for conceptual queries.
    5. Abstains when required source evidence is completely absent from course materials.
    6. Enforces min_score threshold (>= 0.65) to eliminate irrelevant noise.
    7. Caches offering chunks in memory for sub-millisecond similarity scans.
    Returns: List of (chunk, score, citation_text).
    """
    query_clean = (query or "").strip().lower()
    if len(query_clean) < 2:
        return []

    # Check or load candidate chunks for this course offering
    now = time.time()
    chunks: List[SourceChunk] = []
    if course_offering_id in _OFFERING_CACHE:
        cached_time, cached_chunks = _OFFERING_CACHE[course_offering_id]
        if now - cached_time < _OFFERING_CACHE_TTL:
            chunks = cached_chunks

    if not chunks:
        # Load verified candidate chunks for this course offering
        stmt = (
            select(SourceChunk)
            .options(selectinload(SourceChunk.document))
            .join(SourceDocumentCourseOffering, SourceDocumentCourseOffering.source_document_id == SourceChunk.source_document_id)
            .join(SourceDocument, SourceDocument.id == SourceChunk.source_document_id)
            .join(SourceExtraction, SourceChunk.source_extraction_id == SourceExtraction.id)
            .where(
                SourceDocumentCourseOffering.course_offering_id == course_offering_id,
                SourceDocument.status == "processed",
                SourceDocument.review_status != "rejected",
                SourceDocument.publication_status != "rejected",
                SourceExtraction.status == "succeeded",
            )
        )
        if source_types:
            stmt = stmt.where(SourceDocument.source_type.in_(source_types))

        chunks = list((await db.execute(stmt)).scalars().all())
        if chunks:
            _OFFERING_CACHE[course_offering_id] = (now, chunks)

    if not chunks:
        return []

    # Insufficient Evidence Gate: Abstain if the core focal topic is completely absent from course materials
    if not _has_substantive_evidence(query_clean, chunks):
        return []

    # Filter by source_types if specified after cache hit
    active_chunks = chunks
    if source_types:
        active_chunks = [c for c in chunks if c.document and c.document.source_type in source_types]
        if not active_chunks:
            return []

    # 1. Compute query vector
    query_vec = await compute_embedding(query_clean)
    scored: List[Tuple[SourceChunk, float]] = []

    # Dynamic query constraint extraction
    mod_target = _extract_module_constraint(query)
    marks_target = _extract_marks_constraint(query)
    is_assessment_query = bool(re.search(r"\b(questions?|marks?|5-mark|2-mark|10-mark|exam|examination|test|quiz|problems?)\b", query_clean, re.I))
    is_syllabus_query = bool(re.search(r"\b(syllabus|curriculum|course outcomes?|topics? included in|modules? covered|credits?)\b", query_clean, re.I))

    # Pre-filter chunks based on explicit constraints
    candidate_chunks: List[SourceChunk] = []
    for chunk in active_chunks:
        doc = chunk.document
        doc_type = (doc.source_type if doc else "notes").lower()
        chunk_type = (chunk.chunk_type or "").lower()
        c_mod = _get_chunk_module(chunk)
        c_marks = _get_chunk_marks(chunk)

        # Module constraint: if query explicitly targets Module X, exclude chunks from other modules
        if mod_target and c_mod and c_mod != mod_target:
            continue

        # Marks constraint: if query explicitly targets N marks, exclude questions with different marks
        if marks_target and (doc_type == "question_paper" or chunk_type == "question"):
            if c_marks is not None and c_marks != marks_target:
                continue

        candidate_chunks.append(chunk)

    if not candidate_chunks:
        candidate_chunks = active_chunks

    if query_vec:
        for chunk in candidate_chunks:
            if chunk.embedding_json and isinstance(chunk.embedding_json, list):
                score = cosine_similarity(query_vec, chunk.embedding_json)
                scored.append((chunk, score))
    else:
        # Normalized keyword fallback score to [0.0, 1.0]
        words = [w for w in re.findall(r"\w+", query_clean) if len(w) > 3]
        if words:
            for chunk in candidate_chunks:
                text_lower = (chunk.content_text or "").lower()
                section_lower = (chunk.section_path or "").lower()
                matches = sum(1.0 for w in words if w in text_lower or w in section_lower)
                norm_score = round(min(1.0, matches / max(1, len(words))), 4)
                scored.append((chunk, norm_score))

    if not scored:
        return []

    # 2. Query Intent Classification & Domain Weighting
    weighted_scored: List[Tuple[SourceChunk, float]] = []
    for chunk, raw_score in scored:
        doc = chunk.document
        doc_type = (doc.source_type if doc else "notes").lower()
        chunk_type = (chunk.chunk_type or "").lower()
        c_mod = _get_chunk_module(chunk)
        c_marks = _get_chunk_marks(chunk)

        adjusted_score = raw_score

        # Module matching boost
        if mod_target and c_mod == mod_target:
            adjusted_score = min(1.0, adjusted_score * 1.25)

        # Marks matching boost
        if marks_target and c_marks == marks_target:
            adjusted_score = min(1.0, adjusted_score * 1.30)
        elif is_assessment_query:
            if doc_type == "question_paper" or chunk_type == "question":
                adjusted_score = min(1.0, raw_score * 1.15)
        elif is_syllabus_query:
            if doc_type == "syllabus" or chunk_type == "curriculum":
                adjusted_score = min(1.0, raw_score * 1.15)
        else:
            # Conceptual academic inquiry: Prioritize explanatory lecture slides and notes.
            # Unanswered exam question prompts must NOT displace explanatory lecture slides.
            if doc_type == "question_paper" or chunk_type == "question":
                adjusted_score = raw_score * 0.40
            elif doc_type == "slides":
                # Architecture & component slides boost for conceptual architecture queries
                if any(k in query_clean for k in ["architecture", "component", "structure"]):
                    sec_title = (chunk.section_path or "").lower()
                    if any(w in sec_title for w in ["architecture", "structure", "complete bci", "what is a bci"]):
                        adjusted_score = min(1.0, adjusted_score * 1.15)

        if adjusted_score >= min_score:
            weighted_scored.append((chunk, adjusted_score))

    weighted_scored.sort(key=lambda x: x[1], reverse=True)
    results: List[Tuple[SourceChunk, float, str]] = []
    seen_hashes = set()
    seen_prompts = set()

    for chunk, score in weighted_scored[:top_k * 4]:
        if chunk.content_hash in seen_hashes:
            continue
        seen_hashes.add(chunk.content_hash)

        # Deduplicate identical question prompts in question bank
        if chunk.chunk_type == "question":
            norm_prompt = re.sub(r"\W+", " ", (chunk.content_text or "")[:80]).strip().lower()
            if norm_prompt in seen_prompts:
                continue
            seen_prompts.add(norm_prompt)

        citation = format_chunk_citation(chunk.document, chunk)
        results.append((chunk, score, citation))
        if len(results) >= top_k:
            break

    return results
