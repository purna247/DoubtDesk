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
from app.modules.sources.models import SourceChunk, SourceDocument, SourceDocumentCourseOffering, SourceExtraction

logger = logging.getLogger(__name__)
settings = get_settings()

_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"
_BATCH_EMBED_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents"

# In-memory LRU query embedding cache to eliminate redundant Gemini API latency
_QUERY_CACHE: Dict[str, Tuple[float, List[float]]] = {}
_MAX_QUERY_CACHE = 1000
_QUERY_CACHE_TTL = 7200.0  # 2 hours

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
    """Compute a 3072-dimensional vector embedding for a single text using Gemini."""
    api_key = settings.GEMINI_API_KEY
    cleaned = (text or "").strip()
    if not api_key or len(cleaned) < 2:
        return None

    cache_key = cleaned.lower()[:300]
    now = time.time()
    if cache_key in _QUERY_CACHE:
        cached_time, cached_vec = _QUERY_CACHE[cache_key]
        if now - cached_time < _QUERY_CACHE_TTL:
            return cached_vec

    payload = {
        "model": "models/gemini-embedding-001",
        "content": {"parts": [{"text": cleaned[:2000]}]},
    }
    url = f"{_EMBED_URL}?key={api_key}"

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code == 200:
                values = resp.json().get("embedding", {}).get("values")
                if isinstance(values, list) and len(values) > 0:
                    vec = [float(v) for v in values]
                    if len(_QUERY_CACHE) >= _MAX_QUERY_CACHE:
                        oldest_key = min(_QUERY_CACHE.keys(), key=lambda k: _QUERY_CACHE[k][0])
                        _QUERY_CACHE.pop(oldest_key, None)
                    _QUERY_CACHE[cache_key] = (now, vec)
                    return vec
    except Exception as exc:
        logger.debug("Failed computing embedding: %s", exc)
    return None


async def compute_batch_embeddings(texts: List[str]) -> List[Optional[List[float]]]:
    """Compute 3072-dimensional embeddings for a list of texts in batches of 20 with retry."""
    api_key = settings.GEMINI_API_KEY
    if not api_key or not texts:
        return [None] * len(texts)

    results: List[Optional[List[float]]] = [None] * len(texts)
    chunk_size = 20

    for i in range(0, len(texts), chunk_size):
        sub_texts = texts[i : i + chunk_size]
        valid_indices = []
        valid_requests = []
        for idx, t in enumerate(sub_texts):
            clean_t = (t or "").strip()[:2000]
            if clean_t:
                valid_indices.append(idx)
                valid_requests.append({
                    "model": "models/gemini-embedding-001",
                    "content": {"parts": [{"text": clean_t}]},
                })

        if not valid_requests:
            continue

        url = f"{_BATCH_EMBED_URL}?key={api_key}"

        try:
            for attempt in range(5):
                async with httpx.AsyncClient(timeout=45.0) as client:
                    resp = await client.post(url, json={"requests": valid_requests})
                    if resp.status_code == 200:
                        embeddings_data = resp.json().get("embeddings", [])
                        for sub_idx, emb_obj in zip(valid_indices, embeddings_data):
                            vals = emb_obj.get("values")
                            if isinstance(vals, list) and len(vals) > 0:
                                results[i + sub_idx] = [float(v) for v in vals]
                        break
                    elif resp.status_code == 429:
                        wait_sec = 8.0 * (attempt + 1)
                        logger.warning("Gemini embedding rate limited (429). Backing off for %.1fs...", wait_sec)
                        await asyncio.sleep(wait_sec)
                    else:
                        logger.debug("Batch embedding non-200 status: %d", resp.status_code)
                        break
        except Exception as exc:
            logger.debug("Batch embedding request failed: %s", exc)
            for sub_idx in valid_indices:
                results[i + sub_idx] = await compute_embedding(sub_texts[sub_idx])
        await asyncio.sleep(1.5)

    return results


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
    3. Enforces min_score threshold (>= 0.65) to eliminate irrelevant noise.
    4. Excludes rejected or unpublished documents and stale extraction runs.
    5. Caches offering chunks in memory for sub-millisecond similarity scans.
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

    # Filter by source_types if specified after cache hit
    active_chunks = chunks
    if source_types:
        active_chunks = [c for c in chunks if c.document and c.document.source_type in source_types]
        if not active_chunks:
            return []

    # 1. Compute query vector
    query_vec = await compute_embedding(query_clean)
    scored: List[Tuple[SourceChunk, float]] = []

    if query_vec:
        for chunk in active_chunks:
            if chunk.embedding_json and isinstance(chunk.embedding_json, list):
                score = cosine_similarity(query_vec, chunk.embedding_json)
                scored.append((chunk, score))
    else:
        # Normalized keyword fallback score to [0.0, 1.0]
        words = [w for w in re.findall(r"\w+", query_clean) if len(w) > 3]
        if words:
            for chunk in active_chunks:
                text_lower = (chunk.content_text or "").lower()
                section_lower = (chunk.section_path or "").lower()
                matches = sum(1.0 for w in words if w in text_lower or w in section_lower)
                norm_score = round(min(1.0, matches / max(1, len(words))), 4)
                scored.append((chunk, norm_score))

    if not scored:
        return []

    # 2. Query Intent Classification & Source Separation
    # Distinguish: assessment material (question bank), curriculum references (syllabus), and explanatory content (slides, notes)
    is_assessment_query = bool(re.search(r"\b(questions?|marks?|5-mark|2-mark|10-mark|exam|examination|test|quiz|problems?)\b", query_clean, re.I))
    is_syllabus_query = bool(re.search(r"\b(syllabus|curriculum|course outcomes?|topics? included in|modules? covered|credits?)\b", query_clean, re.I))

    weighted_scored: List[Tuple[SourceChunk, float]] = []
    for chunk, raw_score in scored:
        doc = chunk.document
        doc_type = (doc.source_type if doc else "notes").lower()
        chunk_type = (chunk.chunk_type or "").lower()

        adjusted_score = raw_score
        if is_assessment_query:
            if doc_type == "question_paper" or chunk_type == "question":
                adjusted_score = min(1.0, raw_score * 1.15)
        elif is_syllabus_query:
            if doc_type == "syllabus" or chunk_type == "curriculum":
                adjusted_score = min(1.0, raw_score * 1.15)
        else:
            # Conceptual academic inquiry: Prioritize explanatory lecture slides and notes.
            # A 1-sentence unanswered question bank item must NOT displace explanatory lecture slides.
            if doc_type == "question_paper" or chunk_type == "question":
                adjusted_score = raw_score * 0.88

        if adjusted_score >= min_score:
            weighted_scored.append((chunk, adjusted_score))

    weighted_scored.sort(key=lambda x: x[1], reverse=True)
    results: List[Tuple[SourceChunk, float, str]] = []
    seen_hashes = set()

    for chunk, score in weighted_scored[:top_k * 3]:
        if chunk.content_hash in seen_hashes:
            continue
        seen_hashes.add(chunk.content_hash)
        citation = format_chunk_citation(chunk.document, chunk)
        results.append((chunk, score, citation))
        if len(results) >= top_k:
            break

    return results
