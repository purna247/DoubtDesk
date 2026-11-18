"""
Centralized Gemini API Gateway with Controlled Concurrency, Rate Limiting,
Persistent Multi-Tier Caching, Priority Queuing, and 429 Exponential Backoff with Jitter.

Enforces Google AI Studio Free Tier Limits:
- Gemini 3.5 Flash Lite: 14 RPM (capped under 15), 220,000 TPM (under 250K), 480 RPD (under 500)
- Gemini Embedding 1: 80 RPM (capped under 100), 25,000 TPM (under 30K), 950 RPD (under 1000)
"""

from __future__ import annotations

import asyncio
from collections import deque
from enum import IntEnum
import hashlib
import io
import json
import logging
from pathlib import Path
import random
import sqlite3
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
from PIL import Image

from app.config import get_settings

logger = logging.getLogger("doubtdesk.gemini_gateway")


def compress_image_for_ocr(image_bytes: bytes, max_dim: int = 512, quality: int = 75) -> bytes:
    """Downscales image dimensions and compresses to JPEG to minimize visual tokens and payload size."""
    try:
        pil_img = Image.open(io.BytesIO(image_bytes))
        pil_img.thumbnail((max_dim, max_dim))
        buf = io.BytesIO()
        # Convert RGBA to RGB if necessary for JPEG encoding
        if pil_img.mode in ("RGBA", "P"):
            pil_img = pil_img.convert("RGB")
        pil_img.save(buf, format="JPEG", quality=quality)
        return buf.getvalue()
    except Exception as e:
        logger.warning("Image downscale failed (%s); using original bytes.", e)
        return image_bytes



class Priority(IntEnum):
    """Priority levels for API requests. Lower numerical value = higher priority."""
    HIGH = 1    # Interactive student/teacher queries, search, quiz/practice generation
    LOW = 2     # Background document ingestion, diagram OCR, batch chunk embeddings


class ModelFamily(IntEnum):
    TEXT = 1
    EMBEDDING = 2


class GeminiRateLimiter:
    """
    Sliding window rate limiter enforcing RPM and TPM boundaries
    independently for text and embedding models.
    """

    def __init__(self, name: str, max_rpm: int, max_tpm: int, max_concurrency: int):
        self.name = name
        self.max_rpm = max_rpm
        self.max_tpm = max_tpm
        self.max_concurrency = max_concurrency
        self.semaphore = asyncio.Semaphore(max_concurrency)
        self.lock = asyncio.Lock()
        # Stores (monotonic_timestamp, estimated_tokens)
        self.window: deque[Tuple[float, int]] = deque()
        self.cooldown_until: float = 0.0

    async def acquire(self, estimated_tokens: int, priority: Priority = Priority.HIGH) -> None:
        """
        Wait until capacity is available within the 60-second sliding window
        and any 429 cooldown has elapsed.
        """
        while True:
            now = time.monotonic()

            # Respect active 429 circuit cooldown
            if self.cooldown_until > now:
                sleep_sec = self.cooldown_until - now
                logger.info("[%s RateLimiter] Circuit active. Pausing for %.2fs...", self.name, sleep_sec)
                await asyncio.sleep(sleep_sec)
                continue

            async with self.lock:
                now = time.monotonic()
                # Prune items older than 60 seconds
                while self.window and (now - self.window[0][0]) >= 60.0:
                    self.window.popleft()

                current_requests = len(self.window)
                current_tokens = sum(t[1] for t in self.window)

                # Check RPM
                rpm_exceeded = current_requests >= self.max_rpm
                # Check TPM
                tpm_exceeded = (current_tokens + estimated_tokens) > self.max_tpm

                if not rpm_exceeded and not tpm_exceeded:
                    # Slot is available
                    self.window.append((now, estimated_tokens))
                    return

                # Calculate required wait time based on oldest request in window
                oldest_time = self.window[0][0]
                wait_time = max(0.2, 60.0 - (now - oldest_time) + 0.1)

            # Jitter slightly for lower priority requests to allow high priority requests to pass
            if priority == Priority.LOW:
                wait_time += random.uniform(0.1, 0.4)

            logger.info(
                "[%s RateLimiter] Quota ceiling reached (RPM=%d/%d, TPM=%d/%d). Throttling for %.2fs...",
                self.name,
                current_requests,
                self.max_rpm,
                current_tokens + estimated_tokens,
                self.max_tpm,
                wait_time,
            )
            await asyncio.sleep(wait_time)

    def trigger_cooldown(self, seconds: float) -> None:
        """Set a temporary cooldown across all threads after a 429 response."""
        now = time.monotonic()
        self.cooldown_until = max(self.cooldown_until, now + seconds)


class PersistentGeminiCache:
    """
    Two-tier cache: In-memory LRU dict + persistent SQLite database in local_storage.
    Eliminates redundant embedding generation and visual diagram OCR across restarts.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        self._mem_embeddings: Dict[str, List[float]] = {}
        self._mem_vision: Dict[str, str] = {}
        self._mem_responses: Dict[str, Any] = {}
        self._max_mem_entries = 1000
        self._init_sqlite()

    def _init_sqlite(self) -> None:
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            with sqlite3.connect(str(self.db_path)) as conn:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS text_embeddings (
                        text_hash TEXT PRIMARY KEY,
                        text_snippet TEXT,
                        embedding_json TEXT,
                        created_at REAL
                    );
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS vision_ocr (
                        image_hash TEXT PRIMARY KEY,
                        extracted_text TEXT,
                        created_at REAL
                    );
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS response_cache (
                        prompt_hash TEXT PRIMARY KEY,
                        response_json TEXT,
                        created_at REAL
                    );
                """)
                conn.commit()
        except Exception as exc:
            logger.warning("Failed initializing persistent Gemini SQLite cache: %s", exc)

    def get_embedding(self, text: str) -> Optional[List[float]]:
        cleaned = text.strip()
        if not cleaned:
            return None
        h = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()

        # Memory cache check
        if h in self._mem_embeddings:
            return self._mem_embeddings[h]

        # SQLite check
        try:
            with sqlite3.connect(str(self.db_path), timeout=5.0) as conn:
                row = conn.execute("SELECT embedding_json FROM text_embeddings WHERE text_hash = ?", (h,)).fetchone()
                if row:
                    vec = json.loads(row[0])
                    self._mem_embeddings[h] = vec
                    return vec
        except Exception as exc:
            logger.debug("Cache lookup failed: %s", exc)
        return None

    def store_embedding(self, text: str, vector: List[float]) -> None:
        cleaned = text.strip()
        if not cleaned or not vector:
            return
        h = hashlib.sha256(cleaned.encode("utf-8")).hexdigest()

        # Update in-memory
        if len(self._mem_embeddings) >= self._max_mem_entries:
            self._mem_embeddings.pop(next(iter(self._mem_embeddings)))
        self._mem_embeddings[h] = vector

        # Update SQLite
        try:
            with sqlite3.connect(str(self.db_path), timeout=5.0) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO text_embeddings (text_hash, text_snippet, embedding_json, created_at) VALUES (?, ?, ?, ?)",
                    (h, cleaned[:200], json.dumps(vector), time.time()),
                )
                conn.commit()
        except Exception as exc:
            logger.debug("Cache persist failed: %s", exc)

    def get_vision_ocr(self, image_bytes: bytes) -> Optional[str]:
        h = hashlib.sha256(image_bytes).hexdigest()
        if h in self._mem_vision:
            return self._mem_vision[h]

        try:
            with sqlite3.connect(str(self.db_path), timeout=5.0) as conn:
                row = conn.execute("SELECT extracted_text FROM vision_ocr WHERE image_hash = ?", (h,)).fetchone()
                if row:
                    self._mem_vision[h] = row[0]
                    return row[0]
        except Exception as exc:
            logger.debug("Vision cache lookup failed: %s", exc)
        return None

    def store_vision_ocr(self, image_bytes: bytes, text: str) -> None:
        h = hashlib.sha256(image_bytes).hexdigest()
        self._mem_vision[h] = text

        try:
            with sqlite3.connect(str(self.db_path), timeout=5.0) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO vision_ocr (image_hash, extracted_text, created_at) VALUES (?, ?, ?)",
                    (h, text, time.time()),
                )
                conn.commit()
        except Exception as exc:
            logger.debug("Vision cache persist failed: %s", exc)

    def get_response(self, prompt_hash: str) -> Optional[Any]:
        if prompt_hash in self._mem_responses:
            return self._mem_responses[prompt_hash]

        try:
            with sqlite3.connect(str(self.db_path), timeout=5.0) as conn:
                row = conn.execute("SELECT response_json FROM response_cache WHERE prompt_hash = ?", (prompt_hash,)).fetchone()
                if row:
                    data = json.loads(row[0])
                    self._mem_responses[prompt_hash] = data
                    return data
        except Exception as exc:
            logger.debug("Response cache lookup failed: %s", exc)
        return None

    def store_response(self, prompt_hash: str, data: Any) -> None:
        self._mem_responses[prompt_hash] = data
        try:
            with sqlite3.connect(str(self.db_path), timeout=5.0) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO response_cache (prompt_hash, response_json, created_at) VALUES (?, ?, ?)",
                    (prompt_hash, json.dumps(data), time.time()),
                )
                conn.commit()
        except Exception as exc:
            logger.debug("Response cache persist failed: %s", exc)


class GeminiGateway:
    """
    Authoritative single client and rate-limiting queue for all Google Gemini API calls.
    """

    def __init__(self):
        self.settings = get_settings()
        cache_file = self.settings.LOCAL_STORAGE_DIR / "gemini_cache.db"
        self.cache = PersistentGeminiCache(cache_file)

        # Flash Lite Limit: 14 RPM (cap under 15), 220,000 TPM (cap under 250K), Concurrency: 2
        self.flash_limiter = GeminiRateLimiter(
            name="FlashLite",
            max_rpm=14,
            max_tpm=220_000,
            max_concurrency=2,
        )

        # Embedding Limit: 80 RPM (cap under 100), 25,000 TPM (cap under 30K), Concurrency: 3
        self.embedding_limiter = GeminiRateLimiter(
            name="Embedding",
            max_rpm=80,
            max_tpm=25_000,
            max_concurrency=3,
        )

        # Telemetry metrics
        self.metrics = {
            "total_requests": 0,
            "cached_hits": 0,
            "network_requests": 0,
            "rate_limit_429s": 0,
            "retries_performed": 0,
            "tokens_consumed": 0,
        }

    def get_telemetry(self) -> Dict[str, Any]:
        """Return real-time usage statistics and quota health."""
        now = time.monotonic()
        # Flash lite current RPM in 60s
        flash_window = [t for t in self.flash_limiter.window if (now - t[0]) < 60.0]
        emb_window = [t for t in self.embedding_limiter.window if (now - t[0]) < 60.0]

        total = self.metrics["total_requests"]
        cached = self.metrics["cached_hits"]
        hit_rate = (cached / total * 100.0) if total > 0 else 0.0

        return {
            "metrics": dict(self.metrics),
            "cache_hit_rate_percent": round(hit_rate, 2),
            "flash_lite": {
                "active_rpm": len(flash_window),
                "rpm_limit": self.flash_limiter.max_rpm,
                "active_tpm": sum(t[1] for t in flash_window),
                "tpm_limit": self.flash_limiter.max_tpm,
                "concurrency_limit": self.flash_limiter.max_concurrency,
                "circuit_active": self.flash_limiter.cooldown_until > now,
            },
            "embedding": {
                "active_rpm": len(emb_window),
                "rpm_limit": self.embedding_limiter.max_rpm,
                "concurrency_limit": self.embedding_limiter.max_concurrency,
                "circuit_active": self.embedding_limiter.cooldown_until > now,
            },
        }

    async def _execute_with_backoff(
        self,
        limiter: GeminiRateLimiter,
        url: str,
        payload: dict,
        estimated_tokens: int,
        priority: Priority = Priority.HIGH,
        timeout: float = 60.0,
        max_retries: int = 4,
    ) -> httpx.Response:
        """
        Execute an HTTP POST to Gemini through concurrency semaphores,
        sliding-window rate limits, and exponential backoff with jitter on 429/503.
        """
        api_key = self.settings.GEMINI_API_KEY
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not configured.")

        # Concurrency semaphore acquisition
        async with limiter.semaphore:
            for attempt in range(max_retries + 1):
                # Rate limit sliding window check
                await limiter.acquire(estimated_tokens, priority=priority)

                headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}
                try:
                    self.metrics["network_requests"] += 1
                    async with httpx.AsyncClient(timeout=timeout) as client:
                        resp = await client.post(url, headers=headers, json=payload)

                    if resp.status_code == 200:
                        # Extract token usage if returned
                        data = resp.json()
                        usage = data.get("usageMetadata", {})
                        total_tok = usage.get("totalTokenCount")
                        if total_tok:
                            self.metrics["tokens_consumed"] += int(total_tok)
                        return resp

                    if resp.status_code in {429, 503}:
                        if attempt == max_retries:
                            resp.raise_for_status()
                        self.metrics["rate_limit_429s"] += 1
                        self.metrics["retries_performed"] += 1

                        # Exponential backoff with jitter: base * 2^attempt + jitter
                        backoff = (4.0 * (2 ** attempt)) + random.uniform(0.5, 2.5)
                        # Check Retry-After header
                        retry_after = resp.headers.get("Retry-After")
                        if retry_after:
                            try:
                                backoff = max(backoff, float(retry_after))
                            except (ValueError, TypeError):
                                pass

                        logger.warning(
                            "[%s API] Received HTTP %d. Triggering circuit cooldown & backoff for %.2fs (attempt %d/%d)...",
                            limiter.name,
                            resp.status_code,
                            backoff,
                            attempt + 1,
                            max_retries,
                        )
                        limiter.trigger_cooldown(backoff)
                        await asyncio.sleep(backoff)
                        continue

                    # Preserve the final HTTP status for callers' retry classification.
                    # The loop above only retries 429/503 while attempts remain.
                    resp.raise_for_status()
                    return resp

                except (httpx.TimeoutException, httpx.NetworkError) as net_err:
                    if attempt < max_retries:
                        backoff = 3.0 * (2 ** attempt) + random.uniform(0.2, 1.0)
                        logger.warning("[%s API] Network timeout/error (%s); retrying in %.2fs...", limiter.name, type(net_err).__name__, backoff)
                        await asyncio.sleep(backoff)
                        continue
                    raise

            raise RuntimeError(f"Exhausted {max_retries} retries on {limiter.name} due to rate limits or transient errors.")

    async def get_embedding(self, text: str, priority: Priority = Priority.HIGH) -> Optional[List[float]]:
        """
        Compute a 3072-dimensional vector embedding for single text with multi-tier caching.
        """
        cleaned = (text or "").strip()
        if not cleaned or len(cleaned) < 2:
            return None

        self.metrics["total_requests"] += 1

        # 1. Multi-tier cache check (0 network calls on hit)
        cached = self.cache.get_embedding(cleaned)
        if cached is not None:
            self.metrics["cached_hits"] += 1
            return cached

        # 2. Network execution with rate limiting
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:embedContent"
        payload = {
            "model": "models/gemini-embedding-001",
            "content": {"parts": [{"text": cleaned[:2000]}]},
        }
        est_tokens = max(1, len(cleaned) // 4)

        try:
            resp = await self._execute_with_backoff(
                limiter=self.embedding_limiter,
                url=url,
                payload=payload,
                estimated_tokens=est_tokens,
                priority=priority,
                timeout=20.0,
            )
            values = resp.json().get("embedding", {}).get("values")
            if isinstance(values, list) and len(values) > 0:
                vec = [float(v) for v in values]
                self.cache.store_embedding(cleaned, vec)
                return vec
        except Exception as exc:
            logger.warning("[Gemini Gateway] get_embedding failed: %s", exc)
        return None

    async def get_batch_embeddings(
        self,
        texts: List[str],
        priority: Priority = Priority.LOW,
    ) -> List[Optional[List[float]]]:
        """
        Compute embeddings for multiple texts using chunked batch requests,
        checking the persistent cache first to eliminate redundant API calls.
        """
        if not texts:
            return []

        results: List[Optional[List[float]]] = [None] * len(texts)
        missing_indices: List[int] = []

        # 1. Resolve cache hits first
        for idx, t in enumerate(texts):
            self.metrics["total_requests"] += 1
            cleaned = (t or "").strip()
            if not cleaned or len(cleaned) < 2:
                continue
            cached = self.cache.get_embedding(cleaned)
            if cached is not None:
                self.metrics["cached_hits"] += 1
                results[idx] = cached
            else:
                missing_indices.append(idx)

        if not missing_indices:
            logger.info("[Gemini Gateway] Batch embeddings fully satisfied from cache (%d items). Zero API calls.", len(texts))
            return results

        logger.info(
            "[Gemini Gateway] Batch embeddings: %d cached, %d need network computation.",
            len(texts) - len(missing_indices),
            len(missing_indices),
        )

        # 2. Batch request for remaining items in controlled chunks of 15
        batch_chunk_size = 15
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents"

        for b_start in range(0, len(missing_indices), batch_chunk_size):
            chunk_slice = missing_indices[b_start : b_start + batch_chunk_size]
            sub_requests = []
            for original_idx in chunk_slice:
                clean_t = texts[original_idx].strip()[:2000]
                sub_requests.append({
                    "model": "models/gemini-embedding-001",
                    "content": {"parts": [{"text": clean_t}]},
                })

            total_est_tokens = sum(max(1, len(texts[i]) // 4) for i in chunk_slice)
            payload = {"requests": sub_requests}

            try:
                resp = await self._execute_with_backoff(
                    limiter=self.embedding_limiter,
                    url=url,
                    payload=payload,
                    estimated_tokens=total_est_tokens,
                    priority=priority,
                    timeout=45.0,
                )
                embeddings_data = resp.json().get("embeddings", [])
                for original_idx, emb_obj in zip(chunk_slice, embeddings_data):
                    vals = emb_obj.get("values")
                    if isinstance(vals, list) and len(vals) > 0:
                        vec = [float(v) for v in vals]
                        results[original_idx] = vec
                        self.cache.store_embedding(texts[original_idx], vec)

            except Exception as exc:
                logger.warning("[Gemini Gateway] Batch embedding slice failed: %s; falling back to individual calls.", exc)
                for original_idx in chunk_slice:
                    results[original_idx] = await self.get_embedding(texts[original_idx], priority=priority)

            # Controlled inter-batch pacing to avoid burst clustering
            await asyncio.sleep(0.5)

        return results

    async def extract_visual_diagram_text(
        self,
        image_bytes: bytes,
        prompt: str = "Extract all readable text, titles, headings, and diagram architecture descriptions from this academic lecture slide. Be thorough and concise.",
        priority: Priority = Priority.LOW,
    ) -> str:
        """
        Extract text from visual diagram slides using Gemini 3.5 Flash Lite Vision.
        Deduplicates identical images and downscales to optimize token weight (TPM).
        """
        if not image_bytes or len(image_bytes) < 100:
            return ""

        self.metrics["total_requests"] += 1

        # 1. Cache check by image hash (0 network calls on hit)
        cached = self.cache.get_vision_ocr(image_bytes)
        if cached is not None:
            self.metrics["cached_hits"] += 1
            logger.info("[Vision OCR] Cache HIT (sha256=%s...). 0 tokens used.", hashlib.sha256(image_bytes).hexdigest()[:8])
            return cached

        # 2. Token Optimization: Downscale image to max 512x512 with 75% quality JPEG
        optimized_bytes = compress_image_for_ocr(image_bytes, max_dim=512, quality=75)

        import base64
        b64 = base64.b64encode(optimized_bytes).decode("utf-8")

        model = self.settings.GEMINI_MODEL or "gemini-3.5-flash-lite"
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload = {
            "contents": [{
                "parts": [
                    {"text": prompt},
                    {"inline_data": {"mime_type": "image/jpeg", "data": b64}},
                ]
            }],
            "generationConfig": {"temperature": 0.1, "maxOutputTokens": 1024},
        }
        # Approximate token cost: prompt + thumbnail image (~600 tokens)
        est_tokens = len(prompt) // 4 + 600

        try:
            resp = await self._execute_with_backoff(
                limiter=self.flash_limiter,
                url=url,
                payload=payload,
                estimated_tokens=est_tokens,
                priority=priority,
                timeout=25.0,
            )
            cand = resp.json().get("candidates", [])
            if cand:
                p_text = cand[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                if p_text:
                    self.cache.store_vision_ocr(image_bytes, p_text)
                    return p_text
        except Exception as exc:
            logger.warning("[Vision OCR] Diagram extraction failed: %s", exc)

        return ""

    def extract_visual_diagram_text_sync(
        self,
        image_bytes: bytes,
        prompt: str = "Extract all readable text, titles, headings, and diagram architecture descriptions from this academic lecture slide. Be thorough and concise.",
        priority: Priority = Priority.LOW,
    ) -> str:
        """Synchronous wrapper for thread-based workers with cache check."""
        cached = self.cache.get_vision_ocr(image_bytes)
        if cached is not None:
            self.metrics["total_requests"] += 1
            self.metrics["cached_hits"] += 1
            logger.info("[Vision OCR] Cache HIT (sha256=%s...). 0 tokens used.", hashlib.sha256(image_bytes).hexdigest()[:8])
            return cached

        try:
            return asyncio.run(self.extract_visual_diagram_text(image_bytes, prompt, priority))
        except RuntimeError:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                return pool.submit(asyncio.run, self.extract_visual_diagram_text(image_bytes, prompt, priority)).result()

    async def generate_json(
        self,
        prompt: str,
        stage: str = "general",
        priority: Priority = Priority.HIGH,
        temperature: float = 0.2,
        max_output_tokens: Optional[int] = None,
        schema: Optional[dict] = None,
        cache_ttl_hours: Optional[float] = None,
    ) -> Any:
        """
        Generate structured JSON from Gemini Flash Lite with fallback models,
        rate limiting, and response caching.
        """
        prompt_hash = hashlib.sha256(f"{stage}:{prompt}".encode("utf-8")).hexdigest()
        self.metrics["total_requests"] += 1

        # Check cache if TTL is configured
        if cache_ttl_hours is not None:
            cached_resp = self.cache.get_response(prompt_hash)
            if cached_resp is not None:
                self.metrics["cached_hits"] += 1
                return cached_resp

        configured_models = [
            self.settings.GEMINI_MODEL,
            *[m.strip() for m in getattr(self.settings, "GEMINI_FALLBACK_MODELS", "").split(",") if m.strip()],
            getattr(self.settings, "GEMINI_REPAIR_MODEL", self.settings.GEMINI_MODEL),
        ]
        models = list(dict.fromkeys(configured_models))

        est_tokens = max(1, len(prompt) // 4)
        output_budget = max_output_tokens or min(self.settings.GEMINI_MAX_OUTPUT_TOKENS, 4096)

        gen_config = {
            "temperature": temperature,
            "maxOutputTokens": output_budget,
            "responseMimeType": "application/json",
        }
        if schema:
            gen_config["responseSchema"] = schema

        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": gen_config,
        }

        last_error = None
        for model in models:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
            try:
                resp = await self._execute_with_backoff(
                    limiter=self.flash_limiter,
                    url=url,
                    payload=payload,
                    estimated_tokens=est_tokens + output_budget,
                    priority=priority,
                    timeout=90.0,
                )
                data = resp.json()
                parts = data["candidates"][0]["content"]["parts"]
                text_part = next((p["text"] for p in reversed(parts) if isinstance(p, dict) and not p.get("thought") and "text" in p), parts[0]["text"])
                cleaned_text = text_part.strip()
                if cleaned_text.startswith("```"):
                    cleaned_text = cleaned_text.strip("`").removeprefix("json").strip()
                parsed = json.loads(cleaned_text)

                if cache_ttl_hours is not None:
                    self.cache.store_response(prompt_hash, parsed)

                return parsed

            except Exception as exc:
                last_error = exc
                logger.warning("[Gemini Gateway] Model %s failed for stage %s: %s", model, stage, exc)
                continue

        raise RuntimeError(f"All models failed for {stage}: {last_error}")


# Global singleton instance
gemini_gateway = GeminiGateway()
