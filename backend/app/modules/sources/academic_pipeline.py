"""Course-level Gemini extraction with provenance, quota pacing, and partial validation."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import time
import unicodedata
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from rapidfuzz import fuzz
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.modules.jobs.models import BackgroundJob, BackgroundJobEvent
from app.modules.knowledge.models import Concept, ConceptVersion, CourseContentConcept, CourseContentVersion, LearningObjective, SyllabusNode
from app.modules.learning.models import LearningNode, LearningNodeConcept, LearningNodePrerequisite, LearningNodeQuestion
from app.modules.questions.models import Question, QuestionVersion, QuestionPart, QuestionPartConceptAllocation, QuestionVersionSource, QuestionCoverageEvent
from app.modules.sources.academic_models import AcademicExtractionRun, AcademicExtractionBatch, GeminiQuotaWindow
from app.modules.sources.models import SourceChunk, SourceDocument, SourceDocumentCourseOffering, SourceExtraction
from app.common.gemini_client import gemini_gateway, Priority

logger=logging.getLogger(__name__)
PROMPT_VERSION="course-graph-v3"
CONFIDENCE_THRESHOLD=0.80
MAX_INPUT_TOKENS=210_000
QUESTION_BATCH_SIZE=45
_MODEL_COOLDOWN_UNTIL:dict[str,float]={}
RPM_LIMITS={"gemini-3.5-flash-lite":15,"gemini-3.1-flash-lite":15,"gemini-flash-lite-latest":15,"gemini-3.8-flash":5,"gemini-3.6-flash":5,"gemini-2.5-flash":5}
RPD_LIMITS={"gemini-3.5-flash-lite":500,"gemini-3.1-flash-lite":500,"gemini-flash-lite-latest":500,"gemini-3.8-flash":20,"gemini-3.6-flash":20,"gemini-2.5-flash":20}
TOKENS_PER_MINUTE=250_000
LABEL_STOPLIST={"subject code","course code","credits","course outcomes","course outcome","references","textbooks","course objectives","course objective","assessment scheme","contents"}


class Evidence(BaseModel):
    model_config=ConfigDict(extra="ignore")
    chunk_id:str
    quote:str

class ConceptOut(BaseModel):
    model_config=ConfigDict(extra="ignore")
    concept_key:str=Field(min_length=2,max_length=100)
    name:str=Field(min_length=2,max_length=180)
    definition:str=Field(min_length=4,max_length=1200)
    confidence:float=Field(ge=0,le=1)
    evidence:list[Evidence]=Field(min_length=1)

class TopicOut(BaseModel):
    model_config=ConfigDict(extra="ignore")
    title:str=Field(min_length=2,max_length=240)
    confidence:float=Field(ge=0,le=1)
    evidence:list[Evidence]=Field(min_length=1)
    concepts:list[ConceptOut]

class ModuleOut(BaseModel):
    model_config=ConfigDict(extra="ignore")
    title:str=Field(min_length=2,max_length=240)
    confidence:float=Field(ge=0,le=1)
    evidence:list[Evidence]=Field(min_length=1)
    topics:list[TopicOut]

class QuestionOut(BaseModel):
    model_config=ConfigDict(extra="ignore")
    source_question_id:str
    original_number:str=Field(min_length=1,max_length=50)
    text:str=Field(min_length=5,max_length=5000)
    marks:float=Field(default=2.0,ge=0,le=1000)
    module:str=Field(default="",max_length=240)
    concept_keys:list[str]
    confidence:float=Field(ge=0,le=1)
    evidence:list[Evidence]=Field(min_length=1)

class AnalysisOut(BaseModel):
    model_config=ConfigDict(extra="ignore")
    modules:list[ModuleOut]
    questions:list[QuestionOut]

class NodeOut(BaseModel):
    model_config=ConfigDict(extra="ignore")
    node_key:str=Field(min_length=1,max_length=80)
    title:str=Field(min_length=2,max_length=255)
    objective:str=Field(min_length=8,max_length=1500)
    concept_ids:list[str]=Field(min_length=1)
    question_ids:list[str]
    prerequisite_node_keys:list[str]
    difficulty_rank:int=Field(default=1,ge=1,le=1000)
    confidence:float=Field(ge=0,le=1)

class NodePlan(BaseModel):
    model_config=ConfigDict(extra="ignore")
    nodes:list[NodeOut]


class QuotaExhausted(RuntimeError):
    pass


class CheckpointMismatch(ValueError):
    pass


class GeminiProviderError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None, *, attempts: list[dict] | None = None, retryable: bool | None = None):
        super().__init__(message)
        self.status_code = status_code
        self.attempts = attempts or []
        self.retryable = retryable if retryable is not None else status_code is None or status_code in {408, 429, 500, 502, 503, 504}


def normalize_text(value:str)->str:
    value=unicodedata.normalize("NFKD",value).casefold().replace("–","-").replace("—","-")
    return " ".join(re.findall(r"[a-z0-9]+",value))


def evidence_matches(quote:str, source:str)->bool:
    """Normalize formatting, then use a length-guarded fuzzy check for PDF/DOCX wraps."""
    q=normalize_text(quote); s=normalize_text(source)
    if q and q in s:return True
    if len(q)<30 or len(q.split())<5:return False
    if fuzz.partial_ratio(q,s)<90:return False
    distinctive={w for w in q.split() if len(w)>=4}
    return len(distinctive)>=4 and len(distinctive & set(s.split()))/len(distinctive)>=0.8


def _is_metadata(label:str)->bool:
    n=normalize_text(label)
    return n in {normalize_text(x) for x in LABEL_STOPLIST} or any(n.startswith(normalize_text(x)+" ") for x in LABEL_STOPLIST)


def _json_schema(stage:str)->dict[str,Any]:
    evidence={"type":"OBJECT","properties":{"chunk_id":{"type":"STRING"},"quote":{"type":"STRING"}},"required":["chunk_id","quote"]}
    concept={"type":"OBJECT","properties":{"concept_key":{"type":"STRING"},"name":{"type":"STRING"},"definition":{"type":"STRING"},"confidence":{"type":"NUMBER"},"evidence":{"type":"ARRAY","items":evidence}},"required":["concept_key","name","definition","confidence","evidence"]}
    topic={"type":"OBJECT","properties":{"title":{"type":"STRING"},"confidence":{"type":"NUMBER"},"evidence":{"type":"ARRAY","items":evidence},"concepts":{"type":"ARRAY","items":concept}},"required":["title","confidence","evidence","concepts"]}
    module={"type":"OBJECT","properties":{"title":{"type":"STRING"},"confidence":{"type":"NUMBER"},"evidence":{"type":"ARRAY","items":evidence},"topics":{"type":"ARRAY","items":topic}},"required":["title","confidence","evidence","topics"]}
    question={"type":"OBJECT","properties":{"source_question_id":{"type":"STRING"},"original_number":{"type":"STRING"},"text":{"type":"STRING"},"marks":{"type":"NUMBER"},"module":{"type":"STRING"},"concept_keys":{"type":"ARRAY","items":{"type":"STRING"}},"confidence":{"type":"NUMBER"},"evidence":{"type":"ARRAY","items":evidence}},"required":["source_question_id","original_number","text","marks","module","concept_keys","confidence","evidence"]}
    node={"type":"OBJECT","properties":{"node_key":{"type":"STRING"},"title":{"type":"STRING"},"objective":{"type":"STRING"},"concept_ids":{"type":"ARRAY","items":{"type":"STRING"}},"question_ids":{"type":"ARRAY","items":{"type":"STRING"}},"prerequisite_node_keys":{"type":"ARRAY","items":{"type":"STRING"}},"difficulty_rank":{"type":"INTEGER"},"confidence":{"type":"NUMBER"}},"required":["node_key","title","objective","concept_ids","question_ids","prerequisite_node_keys","difficulty_rank","confidence"]}
    analysis_schema={"type":"OBJECT","properties":{"modules":{"type":"ARRAY","items":module},"questions":{"type":"ARRAY","items":question}},"required":["modules","questions"]}
    syllabus_schema={"type":"OBJECT","properties":{"modules":{"type":"ARRAY","items":module}},"required":["modules"]}
    questions_schema={"type":"OBJECT","properties":{"questions":{"type":"ARRAY","items":question}},"required":["questions"]}
    return {"analysis":analysis_schema,"syllabus":syllabus_schema,"questions":questions_schema,"grouping":{"type":"OBJECT","properties":{"nodes":{"type":"ARRAY","items":node}},"required":["nodes"]},"repair":analysis_schema}[stage]


async def _reserve_model(db:AsyncSession, model:str, input_tokens:int, output_budget:int)->float:
    now=datetime.now(timezone.utc); day=now.date()
    stmt=insert(GeminiQuotaWindow).values(id=uuid.uuid4(),model_name=model,quota_date=day,requests_used=0,tokens_in_window=0).on_conflict_do_nothing(index_elements=["model_name","quota_date"])
    await db.execute(stmt); await db.flush()
    quota=(await db.execute(select(GeminiQuotaWindow).where(GeminiQuotaWindow.model_name==model,GeminiQuotaWindow.quota_date==day).with_for_update())).scalars().first()
    if quota.requests_used>=RPD_LIMITS.get(model,20):
        raise QuotaExhausted(f"Daily request quota reached for {model}.")
    cooldown=15 if RPM_LIMITS.get(model,5)<=5 else 4.1
    wait=max(0.0,(quota.last_request_at+timedelta(seconds=cooldown)-now).total_seconds()) if quota.last_request_at else 0.0
    window_start=quota.window_started_at
    if not window_start or (now-window_start).total_seconds()>=60:
        quota.window_started_at=now;quota.tokens_in_window=0;window_start=now
    if quota.tokens_in_window+input_tokens+output_budget>TOKENS_PER_MINUTE:
        wait=max(wait,60-max(0.0,(now-window_start).total_seconds()))
        if wait>=60:
            raise ValueError("One academic request exceeds the configured token-per-minute budget.")
    scheduled=now+timedelta(seconds=wait)
    quota.requests_used+=1
    quota.last_request_at=scheduled
    quota.tokens_in_window+=input_tokens+output_budget
    await db.commit()
    if wait: await asyncio.sleep(wait)
    return wait


async def _gemini_json(db:AsyncSession,prompt:str,stage:str,repair:bool=False)->tuple[dict[str,Any],int,int,str]:
    settings=get_settings()
    if not settings.GEMINI_API_KEY:raise GeminiProviderError("Gemini API key is not configured.", retryable=False)
    estimate=max(1,len(prompt)//4)
    if estimate>MAX_INPUT_TOKENS:raise ValueError("Course extraction exceeds safe single-request size; teacher review is required.")
    configured_models=[settings.GEMINI_MODEL,*[m.strip() for m in settings.GEMINI_FALLBACK_MODELS.split(",") if m.strip()],settings.GEMINI_REPAIR_MODEL]
    models=[settings.GEMINI_REPAIR_MODEL] if repair else list(dict.fromkeys(configured_models))
    now_mono=time.monotonic()
    if not repair:
        healthy=[m for m in models if _MODEL_COOLDOWN_UNTIL.get(m,0)<=now_mono]
        if healthy:models=healthy
    exhausted=[]; last_error=None; attempts=[]
    for model in models:
        stage_budget={"analysis":24000,"syllabus":16000,"questions":24000,"grouping":12000,"repair":16000}.get(stage,12000)
        output_budget=min(settings.GEMINI_MAX_OUTPUT_TOKENS,stage_budget)
        try:
            await _reserve_model(db,model,estimate,output_budget)
        except QuotaExhausted:
            exhausted.append(model);continue
        url=f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        payload={"contents":[{"role":"user","parts":[{"text":prompt}]}],"generationConfig":{"temperature":0.1,"maxOutputTokens":output_budget,"responseMimeType":"application/json","responseSchema":_json_schema(stage)}}
        started=time.monotonic()
        try:
            response = await gemini_gateway._execute_with_backoff(
                limiter=gemini_gateway.flash_limiter,
                url=url,
                payload=payload,
                estimated_tokens=estimate + output_budget,
                priority=Priority.LOW,
                timeout=180.0,
                max_retries=2,
            )
            data=response.json()
            parts=data["candidates"][0]["content"]["parts"]
            text_part=next((p["text"] for p in reversed(parts) if isinstance(p,dict) and not p.get("thought") and "text" in p),parts[0]["text"])
            cleaned_text = text_part.strip()
            if cleaned_text.startswith("```"):
                cleaned_text = cleaned_text.strip("`").removeprefix("json").strip()
            try:
                body = json.loads(cleaned_text)
            except json.JSONDecodeError:
                s_idx = cleaned_text.find("{")
                e_idx = cleaned_text.rfind("}")
                if s_idx != -1 and e_idx != -1:
                    body = json.loads(cleaned_text[s_idx : e_idx + 1])
                else:
                    raise
            _MODEL_COOLDOWN_UNTIL.pop(model,None)
            usage=data.get("usageMetadata",{})
            return body,int(usage.get("promptTokenCount",estimate)),int(usage.get("candidatesTokenCount",0)),model
        except (httpx.HTTPError,KeyError,IndexError,ValueError,json.JSONDecodeError,RuntimeError) as exc:
            last_error=exc
            detail={**getattr(db,"info",{}).get("academic_context",{}),"model":model,"stage":stage,"error_type":type(exc).__name__,"elapsed_seconds":round(time.monotonic()-started,2)}
            if isinstance(exc,httpx.HTTPStatusError):
                status=exc.response.status_code
                detail["http_status"]=status
                try:
                    provider_status=exc.response.json().get("error",{}).get("status","")
                    if re.fullmatch(r"[A-Z_]{1,80}",provider_status):detail["provider_status"]=provider_status
                except (ValueError,AttributeError,TypeError):pass
                request_id=exc.response.headers.get("x-request-id","")
                if re.fullmatch(r"[a-zA-Z0-9_-]{1,128}",request_id):detail["request_id"]=request_id
                logger.warning("Gemini request failed model=%s status=%s stage=%s",model,status,stage)
                if status==404:_MODEL_COOLDOWN_UNTIL[model]=time.monotonic()+1800
                elif status==503:_MODEL_COOLDOWN_UNTIL[model]=time.monotonic()+300
            else:
                logger.warning("Gemini request failed model=%s error=%s stage=%s",model,type(exc).__name__,stage)
                if isinstance(exc,httpx.TimeoutException):_MODEL_COOLDOWN_UNTIL[model]=time.monotonic()+300
            attempts.append(detail)
            logger.warning("Academic provider attempt: %s",json.dumps(detail,sort_keys=True))
            if repair:break
    if len(exhausted)==len(models):raise QuotaExhausted("All configured Gemini daily request quotas are exhausted.")
    if any(isinstance(last_error,t) for t in (httpx.HTTPError,RuntimeError)):
        statuses=[a.get("http_status") for a in attempts]
        retryable=any(s in {408,429,500,502,503,504} or s is None for s in statuses)
        outcomes=", ".join(f"{a['model']}: HTTP {a['http_status']}" if a.get('http_status') else f"{a['model']}: {a['error_type']}" for a in attempts)
        raise GeminiProviderError(f"Gemini {stage} request failed ({outcomes}). Saved extraction checkpoints are retained.",getattr(getattr(last_error,"response",None),"status_code",None),attempts=attempts,retryable=retryable)
    if isinstance(last_error, (json.JSONDecodeError, KeyError, IndexError)):
        raise last_error
    raise RuntimeError(f"Gemini structured request failed ({type(last_error).__name__ if last_error else 'unknown'}).")


def _validate_evidence(evidence:list[Evidence], chunks:dict[str,SourceChunk])->bool:
    return bool(evidence) and all(ev.chunk_id in chunks and evidence_matches(ev.quote,chunks[ev.chunk_id].content_text) for ev in evidence)


def _clean_module_item(raw:dict[str,Any],chunks:dict[str,SourceChunk])->tuple[dict[str,Any],list[dict[str,Any]]]:
    """Keep every valid nested item and return only invalid nested fragments for Lite repair."""
    module=ModuleOut.model_validate({**raw,"topics":[]})
    if _is_metadata(module.title) or not _validate_evidence(module.evidence,chunks):raise ValueError("module_source_invalid")
    clean_topics=[];invalid_fragments=[]
    for raw_topic in raw.get("topics",[]):
        try:
            topic=TopicOut.model_validate({**raw_topic,"concepts":[]})
            if _is_metadata(topic.title) or not _validate_evidence(topic.evidence,chunks):raise ValueError("topic_source_invalid")
        except Exception:
            invalid_fragments.append({**module.model_dump(mode="json"),"topics":[raw_topic]});continue
        valid_concepts=[];bad_concepts=[]
        for raw_concept in raw_topic.get("concepts",[]):
            try:
                concept=ConceptOut.model_validate(raw_concept)
                if _is_metadata(concept.name) or not _validate_evidence(concept.evidence,chunks):raise ValueError("concept_source_invalid")
                valid_concepts.append(concept.model_dump(mode="json"))
            except Exception:bad_concepts.append(raw_concept)
        clean_topic=topic.model_dump(mode="json");clean_topic["concepts"]=valid_concepts;clean_topics.append(clean_topic)
        if bad_concepts:invalid_fragments.append({**module.model_dump(mode="json"),"topics":[{**topic.model_dump(mode="json"),"concepts":bad_concepts}]})
    clean=module.model_dump(mode="json");clean["topics"]=clean_topics
    return clean,invalid_fragments


async def _latest_document_chunks(db:AsyncSession,source_id:uuid.UUID)->list[SourceChunk]:
    """Return non-empty chunks from the latest succeeded extraction, falling back to index/hash dedupe."""
    latest_ext_id=await db.scalar(select(SourceExtraction.id).where(SourceExtraction.source_document_id==source_id,SourceExtraction.status=="succeeded").order_by(SourceExtraction.created_at.desc()).limit(1))
    query=select(SourceChunk).where(SourceChunk.source_document_id==source_id)
    if latest_ext_id is not None:
        query=query.where(SourceChunk.source_extraction_id==latest_ext_id)
    chunks=(await db.execute(query.order_by(SourceChunk.chunk_index.asc(),SourceChunk.created_at.asc()))).scalars().all()
    if latest_ext_id is not None:
        return [c for c in chunks if c.content_text.strip()]
    seen:set[tuple[int,str]]=set(); unique:list[SourceChunk]=[]
    for chunk in chunks:
        if not chunk.content_text.strip():continue
        key=(chunk.chunk_index,chunk.content_hash)
        if key not in seen:seen.add(key);unique.append(chunk)
    return unique


def _analysis_syllabus_prompt(syllabus:list[tuple[SourceDocument,SourceChunk]])->str:
    syllabus_text="\n\n".join(f"[CHUNK_ID:{c.id}] [SOURCE:{d.display_filename}] [PAGE:{c.page_number or ''}]\n{c.content_text}" for d,c in syllabus)
    return ("Analyze this course's syllabus chunks and build a grounded hierarchy of modules -> topics -> stable concepts. "
            "Cover every syllabus module and its key technical topics and concepts. Never create concepts from administrative metadata: subject/course codes, credits, course outcomes/objectives, references, textbooks, assessment scheme, or section-title-only text. "
            "Every module, topic, and concept must cite chunk IDs and verbatim quotes copied from those chunks. IMPORTANT: every `quote` MUST contain at least 35 characters and at least 6 words from the cited chunk (for a short heading like 'Module-I' or a topic header, include the following line or words from that chunk in the quote so it has >= 35 characters and >= 6 words). Use concept_key as a short stable lowercase identifier (e.g. 'eeg_signal_acquisition'). Keep definitions concise (1-2 sentences), not echoed source paragraphs.\n\nSYLLABUS CHUNKS:\n"+syllabus_text)


def _preceding_section_headers(question_rows:list[tuple[SourceDocument,SourceChunk]],start_idx:int)->list[str]:
    """Collect the most recent structural/marks header chunks before `start_idx` as read-only context."""
    headers:list[str]=[]
    for _,chunk in question_rows[:start_idx]:
        text=" ".join(chunk.content_text.split())
        if len(text)<=120 and any(tok in text.casefold() for tok in ("module","unit","part","section","marks","question")):
            headers.append(f"[{chunk.id}] {text}")
    return headers[-4:]


def _analysis_questions_prompt(valid_modules:list[dict[str,Any]],question_slice:list[tuple[SourceDocument,SourceChunk]],header_context:list[str])->str:
    catalog=[{"module":m["title"],"concepts":[{"concept_key":c["concept_key"],"name":c["name"]} for t in m.get("topics",[]) for c in t.get("concepts",[])]} for m in valid_modules]
    question_text="\n\n".join(f"[QUESTION_SOURCE_ID_BASE:q:{c.id}] [CHUNK_ID:{c.id}] [SOURCE:{d.display_filename}] [PAGE:{c.page_number or ''}]\n{c.content_text}" for d,c in question_slice)
    context_block="\n".join(header_context) if header_context else "(none)"
    return ("Extract every actual exam/practice question from QUESTION PAPER CHUNKS below and map each to one or more concept_keys from AVAILABLE MODULES & CONCEPTS. "
            "Set `module` to one of the exact `module` titles in AVAILABLE MODULES & CONCEPTS (or '' if cross-module). Use only supplied concept_keys. "
            "Preserve each question's text, numbering, and marks accurately using READ_ONLY_SECTION_CONTEXT only to infer active module/marks; do not extract questions from READ_ONLY_SECTION_CONTEXT or heading-only chunks. "
            "For each question, set `source_question_id` to exact QUESTION_SOURCE_ID_BASE plus '#' plus `original_number` (example `q:<chunk UUID>#2(b)`; if unnumbered, assign a sequential `original_number` like `1`, `2` and use that exact suffix after '#'). Cite its chunk_id and include the question text as the evidence quote.\n\n"
            f"AVAILABLE MODULES & CONCEPTS:\n{json.dumps(catalog,ensure_ascii=False,separators=(',',':'))}\n\nREAD_ONLY_SECTION_CONTEXT:\n{context_block}\n\nQUESTION PAPER CHUNKS:\n{question_text}")


def _analysis_prompt(syllabus:list[tuple[SourceDocument,SourceChunk]],questions:list[tuple[SourceDocument,SourceChunk]])->str:
    syllabus_text="\n\n".join(f"[CHUNK_ID:{c.id}] [SOURCE:{d.display_filename}] [PAGE:{c.page_number or ''}]\n{c.content_text}" for d,c in syllabus)
    question_text=[f"[QUESTION_SOURCE_ID_BASE:q:{c.id}] [CHUNK_ID:{c.id}] [SOURCE:{d.display_filename}] [PAGE:{c.page_number or ''}]\n{c.content_text}" for d,c in questions]
    return ("Analyze this course's complete syllabus and PYQ corpus in one pass. Build a grounded hierarchy of modules -> topics -> stable concepts, then extract original questions and map each to concept_keys created in that hierarchy. "
            "Never create concepts from administrative metadata: subject/course codes, credits, course outcomes/objectives, references, textbooks, assessment scheme, or section-title-only text. Do not treat every heading/paragraph as a concept. "
            "Preserve every original question's numbering and marks exactly; do not invent question text, marks, modules, or concepts. For each question set source_question_id to the exact QUESTION_SOURCE_ID_BASE plus '#' plus original_number (example q:<chunk UUID>#2(b)); include a short source quote from that chunk. Every module/topic/concept must cite chunk IDs and source quotes. Use concept_key as a stable opaque reference and reuse it for the same concept. Confidence is a calibrated estimate, not permission to fabricate. Return concise names/definitions and references, not echoed source paragraphs.\n\nSYLLABUS CHUNKS:\n"+
            syllabus_text+"\n\nQUESTION PAPER CHUNKS:\n"+"\n\n".join(question_text))


def _group_prompt(module:str,concepts:list[dict],questions:list[dict])->str:
    return ("Group this module's approved concepts, learning objectives, and original questions into a variable number of coherent learning nodes. Consider concept clusters, prerequisites, marks/cognitive demand, and content density. Order nodes from foundational/easier to advanced/harder within this module and assign difficulty_rank from 1 (easiest) upward with no gaps. Around 3-6 related concepts/questions per node is only a soft planning hint. Do not create a node per topic mechanically or an oversized catch-all node. Always assign specific, syllabus-supported names (e.g., 'BCI System Structure and Monitoring Hardware', 'Spatial Filtering and Artifact Reduction (PCA & ICA)'). Never use vague, generic titles such as 'Integrated BCI Systems'. Ensure each node has a coherent learning objective and does not combine unrelated concepts. Include each supplied question exactly once; if no original questions are supplied, create concept-based nodes with empty question_ids. Use only supplied UUID IDs. Provide a concise learning objective and prerequisite node keys from this module.\nMODULE: "+module+"\nCONCEPTS: "+json.dumps(concepts,separators=(",",":"))+"\nQUESTIONS: "+json.dumps(questions,separators=(",",":")))


def _validate_question_item(item:dict[str,Any],question_source_ids:set[str],allowed_concept_keys:set[str],chunks_by_id:dict[str,SourceChunk])->dict[str,Any]:
    """Validate and ground one extracted question item against source chunks and concept keys."""
    raw_item = dict(item)
    if raw_item.get("marks") is None or float(raw_item.get("marks", 0)) <= 0:
        raw_item["marks"] = 2.0
    q=QuestionOut.model_validate(raw_item)
    source_key,separator,number=q.source_question_id.partition("#")
    source_chunk_id=source_key.removeprefix("q:")
    if not separator or normalize_text(number)!=normalize_text(q.original_number) or source_chunk_id not in question_source_ids or source_chunk_id not in {ev.chunk_id for ev in q.evidence}:
        raise ValueError("unknown_question_source")
    if not _validate_evidence(q.evidence,chunks_by_id):
        raise ValueError("question_source_invalid")
    if not set(q.concept_keys)<=allowed_concept_keys or not q.concept_keys:
        raise ValueError("question_concept_reference_invalid")
    combined_quote = " ".join(ev.quote for ev in q.evidence)
    norm_text = normalize_text(q.text)
    norm_combined = normalize_text(combined_quote)
    if fuzz.ratio(norm_text, norm_combined) < 75 and fuzz.partial_ratio(norm_combined, norm_text) < 75:
        raise ValueError("question_text_not_grounded")
    return q.model_dump(mode="json")


def _extract_invalid_chunk_ids(invalid_modules:list[dict[str,Any]],invalid_questions:list[dict[str,Any]],chunks_by_id:dict[str,SourceChunk])->set[str]:
    bad_ids:set[str]=set()
    for it in invalid_modules+invalid_questions:
        if not isinstance(it,dict):continue
        for ev in it.get("evidence") or []:
            if isinstance(ev,dict) and ev.get("chunk_id") in chunks_by_id:
                bad_ids.add(ev["chunk_id"])
    for it in invalid_questions:
        if not isinstance(it,dict):continue
        sid=str(it.get("source_question_id") or "")
        if sid.startswith("q:"):
            cid=sid.partition("#")[0].removeprefix("q:")
            if cid in chunks_by_id:bad_ids.add(cid)
    return bad_ids


async def _repair_invalid_items(db:AsyncSession,run:AcademicExtractionRun,chunks_by_id:dict[str,SourceChunk],invalid_modules:list[dict[str,Any]],invalid_questions:list[dict[str,Any]],allowed_concept_keys:set[str],question_source_ids:set[str],valid_modules:list[dict[str,Any]],valid_questions:list[dict[str,Any]])->tuple[list[dict[str,Any]],list[dict[str,Any]]]:
    """Run one surgical Lite repair call for invalid items and return unresolved module/question items."""
    bad_ids=_extract_invalid_chunk_ids(invalid_modules,invalid_questions,chunks_by_id)
    source_subset=[{"chunk_id":i,"text":chunks_by_id[i].content_text} for i in sorted(bad_ids)]
    repair_prompt=("Repair only the invalid academic items. Do not add items. Use the exact provided source IDs and one of the supplied concept keys. Every evidence quote MUST be copied verbatim from Source chunks with at least 35 characters and at least 6 words (for short headings, include adjacent words/lines from the chunk). Return only repaired modules/questions in the required schema. Invalid outputs: "+json.dumps({"modules":invalid_modules,"questions":invalid_questions},ensure_ascii=False)+"\nSource chunks: "+json.dumps(source_subset,ensure_ascii=False)+"\nAvailable concept keys: "+json.dumps(sorted(allowed_concept_keys)))
    try:
        repaired,ri,ro,repair_model=await _gemini_json(db,repair_prompt,"repair",repair=True)
        run.model_name=f"{run.model_name}+{repair_model}";run.input_tokens+=ri;run.output_tokens+=ro
        for item in repaired.get("modules",[]):
            try:
                normalized,remaining=_clean_module_item(item,chunks_by_id);valid_modules.append(normalized);invalid_modules.extend(remaining)
            except Exception:pass
        for item in repaired.get("questions",[]):
            try:
                valid_questions.append(_validate_question_item(item,question_source_ids,allowed_concept_keys,chunks_by_id))
            except Exception:pass
    except Exception as exc:
        logger.warning("Surgical academic repair failed run=%s error=%s",run.id,type(exc).__name__)
    unresolved_modules=_unresolved_module_fragments(invalid_modules,valid_modules)
    valid_question_keys={q.get("source_question_id") for q in valid_questions}
    unresolved_questions=[q for q in invalid_questions if isinstance(q,dict) and q.get("source_question_id") not in valid_question_keys]
    return unresolved_modules,unresolved_questions


async def _academic_offerings(db,trigger_doc,job_id):
    offerings=(await db.execute(select(SourceDocumentCourseOffering.course_offering_id).where(SourceDocumentCourseOffering.source_document_id==trigger_doc.id))).scalars().all()
    job=await db.get(BackgroundJob,job_id)
    if job and (job.input_reference_json or {}).get("academic_only"):
        return [job.scope_course_offering_id] if job.scope_course_offering_id in offerings else []
    return offerings


async def _academic_progress(db,job_id,run,stage,batch_index,total):
    from app.modules.jobs.service import JobService
    context={"job_id":str(job_id),"run_id":str(run.id),"batch_index":batch_index,"total_batches":total}
    db.info["academic_context"]=context
    job=await db.get(BackgroundJob,job_id)
    if job:
        checkpoint=dict(job.checkpoint_json or {})
        checkpoint["academic_progress"]={**context,"stage":stage}
        job.checkpoint_json=checkpoint
        progress=92 if stage=="academic_syllabus" else 93+3*batch_index/max(1,total) if stage=="academic_questions" else 96+3*batch_index/max(1,total)
        await JobService.update_progress(db,job_id,stage,progress,f"Preparing {stage.removeprefix('academic_')} batch {batch_index+1} of {total}; validated checkpoints are retained.",context)


async def _cached_run_complete(db,run,all_rows):
    """Legacy 'succeeded' flags alone do not prove a complete course build."""
    batches=(await db.execute(select(AcademicExtractionBatch).where(AcademicExtractionBatch.run_id==run.id,AcademicExtractionBatch.status=="validated"))).scalars().all()
    by_stage={(b.stage,b.batch_index):b for b in batches}
    syllabus=by_stage.get(("analysis_syllabus",0))
    syllabus_ids=[str(c.id) for d,c in all_rows if d.source_type=="syllabus"]
    if not syllabus or syllabus.source_chunk_ids!=syllabus_ids:return False
    modules=(syllabus.response_json or {}).get("modules",[])
    if not modules:return False
    question_ids=[str(c.id) for d,c in all_rows if d.source_type=="question_paper"]
    for index,start in enumerate(range(0,len(question_ids),QUESTION_BATCH_SIZE)):
        batch=by_stage.get(("analysis_questions",index))
        if not batch or batch.source_chunk_ids!=question_ids[start:start+QUESTION_BATCH_SIZE]:return False
    expected=set()
    try:
        for index,module in enumerate(modules):
            if not any(c.get("confidence",0)>=CONFIDENCE_THRESHOLD for t in module.get("topics",[]) for c in t.get("concepts",[])):continue
            batch=by_stage.get(("grouping",index))
            if not batch:return False
            plan=NodePlan.model_validate(batch.response_json)
            if not plan.nodes:return False
            expected.update(f"AI-{run.id.hex[:8]}-{index+1}-{n}" for n in range(1,len(plan.nodes)+1))
    except (ValueError,TypeError):return False
    actual=set((await db.execute(select(LearningNode.node_code).where(LearningNode.course_offering_id==run.course_offering_id,LearningNode.node_code.like(f"AI-{run.id.hex[:8]}-%")))).scalars().all())
    return bool(expected) and expected<=actual


async def process_academic_document(db:AsyncSession,trigger_doc:SourceDocument,job_id:uuid.UUID)->dict[str,Any]:
    from app.modules.jobs.execution import course_execution_locks
    if trigger_doc.source_type not in {"syllabus","question_paper"}:
        return {"skipped":True,"complete":True}
    offerings=await _academic_offerings(db,trigger_doc,job_id)
    async with course_execution_locks(db,offerings) as acquired:
        if not acquired:
            from app.modules.jobs.service import JobService
            await JobService.defer_job(db,job_id,"waiting_for_course_build",30,"Another worker is preparing this course; saved progress will be reused.")
            return {"deferred":True,"complete":False}
        return await _process_academic_document(db,trigger_doc,job_id)


async def _process_academic_document(db:AsyncSession,trigger_doc:SourceDocument,job_id:uuid.UUID)->dict[str,Any]:
    """Run syllabus structure extraction, batched question extraction, then one dynamic grouping call per module."""
    settings=get_settings()
    offering_ids=await _academic_offerings(db,trigger_doc,job_id)
    out={"runs":[],"warnings_count":0,"has_warnings":False,"usable_batches":0,"validated_batches":0,"complete":True,"skipped":False,"deferred":False}
    if trigger_doc.source_type not in {"syllabus","question_paper"} or not offering_ids:
        out["skipped"]=True;return out
    for offering_id in offering_ids:
        docs=(await db.execute(select(SourceDocument).join(SourceDocumentCourseOffering).where(SourceDocumentCourseOffering.course_offering_id==offering_id,SourceDocument.institution_id==trigger_doc.institution_id,SourceDocument.status=="processed",SourceDocument.source_type.in_(["syllabus","question_paper"])).order_by(SourceDocument.source_type,SourceDocument.created_at))).scalars().all()
        syllabus_docs=[d for d in docs if d.source_type=="syllabus"]; question_docs=[d for d in docs if d.source_type=="question_paper"]
        if not syllabus_docs or not question_docs:
            out["skipped"]=True
            out["waiting_for"]="syllabus" if not syllabus_docs else "question_paper"
            out["complete"]=False
            out["safe_error_summary"]=f"Material is available. Academic preparation is waiting for a processed {out['waiting_for'].replace('_',' ')}."
            continue
        all_rows=[];checksum_material=[]
        for source in docs:
            chunks=await _latest_document_chunks(db,source.id)
            checksum_material.append(f"{source.id}:{source.sha256_checksum}")
            all_rows.extend((source,c) for c in chunks)
        aggregate=hashlib.sha256("|".join(sorted(checksum_material)).encode()).hexdigest()
        pipeline_key=hashlib.sha256(f"{aggregate}:{settings.GEMINI_MODEL}:{settings.GEMINI_FALLBACK_MODELS}:{settings.GEMINI_REPAIR_MODEL}:{PROMPT_VERSION}".encode()).hexdigest()
        run=(await db.execute(select(AcademicExtractionRun).where(AcademicExtractionRun.course_offering_id==offering_id,AcademicExtractionRun.pipeline_key==pipeline_key))).scalars().first()
        job=await db.get(BackgroundJob,job_id)
        previous_run_id=(job.input_reference_json or {}).get("previous_run_id") if job else None
        if not run and previous_run_id:
            # Deliberate configuration repair may select another provider without
            # invalidating grounded outputs produced by the same prompt and inputs.
            # Keep original run/key/batch IDs; cached generation metadata is retained.
            previous=await db.get(AcademicExtractionRun,uuid.UUID(previous_run_id))
            if previous and previous.institution_id==trigger_doc.institution_id and previous.course_offering_id==offering_id and previous.content_checksum==aggregate and previous.prompt_version==PROMPT_VERSION:
                run=previous
        unresolved_groupings=await db.scalar(select(func.count()).select_from(AcademicExtractionBatch).where(AcademicExtractionBatch.run_id==run.id,AcademicExtractionBatch.stage=="grouping",AcademicExtractionBatch.status=="flagged_for_review")) if run else 0
        persisted_nodes=await db.scalar(select(func.count()).select_from(LearningNode).where(LearningNode.course_offering_id==offering_id,LearningNode.node_code.like(f"AI-{run.id.hex[:8]}-%"))) if run else 0
        if run and run.status=="succeeded" and not unresolved_groupings and persisted_nodes and await _cached_run_complete(db,run,all_rows):
            cached_count=await db.scalar(select(func.count()).select_from(AcademicExtractionBatch).where(AcademicExtractionBatch.run_id==run.id,AcademicExtractionBatch.status=="validated")) or 0
            out["validated_batches"]+=cached_count;out["usable_batches"]+=cached_count
            out["runs"].append({"run_id":str(run.id),"status":"succeeded","cached":True,"warnings_count":run.warnings_count,"has_warnings":run.has_warnings});out["warnings_count"]+=run.warnings_count;out["has_warnings"]|=run.has_warnings;continue
        if not run:
            run=AcademicExtractionRun(institution_id=trigger_doc.institution_id,source_document_id=trigger_doc.id,course_offering_id=offering_id,content_checksum=aggregate,pipeline_key=pipeline_key,model_name=settings.GEMINI_MODEL,prompt_version=PROMPT_VERSION,status="running");db.add(run);await db.flush()
        elif run.status!="running":
            if run.status=="failed":
                run.safe_error_summary=None;run.warnings_count=0;run.has_warnings=False
            run.status="running"
        job=await db.get(BackgroundJob,job_id);teacher_id=job.requested_by_user_id if job else None
        version=(await db.execute(select(CourseContentVersion).where(CourseContentVersion.course_offering_id==offering_id,CourseContentVersion.status.in_(["draft","in_review"])).order_by(CourseContentVersion.version_number.desc()))).scalars().first()
        if not version:
            maximum=(await db.execute(select(func.max(CourseContentVersion.version_number)).where(CourseContentVersion.course_offering_id==offering_id))).scalar() or 0
            version=CourseContentVersion(institution_id=trigger_doc.institution_id,course_offering_id=offering_id,version_number=maximum+1,status="draft",created_by_user_id=teacher_id);db.add(version);await db.flush()
        if not settings.GEMINI_API_KEY:
            run.status="failed";run.has_warnings=True;run.warnings_count=1;run.safe_error_summary="Gemini API key is not configured; academic proposals were not generated."
            out["complete"]=False;out["retryable"]=False;out["safe_error_summary"]=run.safe_error_summary
            out["runs"].append({"run_id":str(run.id),"status":"failed","safe_error_summary":run.safe_error_summary})
            await db.commit();continue
        chunks_by_id={str(c.id):c for _,c in all_rows}
        syllabus_rows=[(d,c) for d,c in all_rows if d.source_type=="syllabus"]
        question_rows=[(d,c) for d,c in all_rows if d.source_type=="question_paper"]
        stale_failed=(await db.execute(select(AcademicExtractionBatch).where(AcademicExtractionBatch.run_id==run.id,AcademicExtractionBatch.stage.in_(["analysis","analysis_syllabus","analysis_questions"]),AcademicExtractionBatch.warning_code.in_(["ANALYSIS_FAILED","ANALYSIS_RESPONSE_INVALID","GEMINI_PROVIDER_UNAVAILABLE","GEMINI_PROVIDER_REQUEST_FAILED","CHECKPOINT_SOURCE_MISMATCH","AI_NOT_CONFIGURED"])))).scalars().all()
        for batch in stale_failed:
            if batch.status=="validated":continue
            await db.delete(batch)
        if stale_failed:await db.flush()
        # Cached successful analysis will not reproduce unresolved-item warnings.
        # Retain their original checkpoints and rebuild the warning count from them.
        retained_reviews=(await db.execute(select(AcademicExtractionBatch).where(AcademicExtractionBatch.run_id==run.id,AcademicExtractionBatch.status=="flagged_for_review"))).scalars().all()
        run.warnings_count=sum(len((b.response_json or {}).get("items",[])) if b.stage=="confidence_review" else 1 for b in retained_reviews)
        run.has_warnings=run.warnings_count>0

        validated_modules:list[dict[str,Any]]=[];validated_questions:list[dict[str,Any]]=[]
        legacy_analysis=(await db.execute(select(AcademicExtractionBatch).where(AcademicExtractionBatch.run_id==run.id,AcademicExtractionBatch.stage=="analysis",AcademicExtractionBatch.batch_index==0))).scalars().first()
        if legacy_analysis and legacy_analysis.status=="validated" and legacy_analysis.response_json:
            validated_modules=legacy_analysis.response_json.get("modules",[]);validated_questions=legacy_analysis.response_json.get("questions",[])
        else:
            try:
                syllabus_batch=(await db.execute(select(AcademicExtractionBatch).where(AcademicExtractionBatch.run_id==run.id,AcademicExtractionBatch.stage=="analysis_syllabus",AcademicExtractionBatch.batch_index==0,AcademicExtractionBatch.status=="validated"))).scalars().first()
                if syllabus_batch and syllabus_batch.source_chunk_ids!=[str(c.id) for _,c in syllabus_rows]:
                    raise CheckpointMismatch("Saved syllabus checkpoint does not match the current source chunk IDs. Existing validated output was retained; investigate input provenance before retrying.")
                if syllabus_batch and syllabus_batch.source_chunk_ids==[str(c.id) for _,c in syllabus_rows] and syllabus_batch.response_json:
                    validated_modules=syllabus_batch.response_json.get("modules",[])
                else:
                    await _academic_progress(db,job_id,run,"academic_syllabus",0,1)
                    raw_syl,in_tokens,out_tokens,actual_model=await _gemini_json(db,_analysis_syllabus_prompt(syllabus_rows),"syllabus")
                    run.model_name=actual_model;run.input_tokens+=in_tokens;run.output_tokens+=out_tokens
                    valid_modules=[];invalid_modules=[]
                    for item in (raw_syl.get("modules",[]) if isinstance(raw_syl,dict) else []):
                        try:
                            cleaned,fragments=_clean_module_item(item,chunks_by_id);valid_modules.append(cleaned);invalid_modules.extend(fragments)
                        except Exception:invalid_modules.append(item)
                    if invalid_modules:
                        cand_keys={str(c.get("concept_key")) for m in (raw_syl.get("modules",[]) if isinstance(raw_syl,dict) else []) if isinstance(m,dict) for t in (m.get("topics") or []) if isinstance(t,dict) for c in (t.get("concepts") or []) if isinstance(c,dict) and c.get("concept_key")}
                        unresolved_modules,_=await _repair_invalid_items(db,run,chunks_by_id,invalid_modules,[],cand_keys,set(),valid_modules,[])
                        if unresolved_modules:
                            existing_review=await db.scalar(select(AcademicExtractionBatch.id).where(AcademicExtractionBatch.run_id==run.id,AcademicExtractionBatch.stage=="repair",AcademicExtractionBatch.batch_index==0).limit(1))
                            if not existing_review:
                                run.warnings_count+=1;run.has_warnings=True
                                db.add(AcademicExtractionBatch(run_id=run.id,stage="repair",batch_index=0,status="flagged_for_review",source_chunk_ids=sorted(_extract_invalid_chunk_ids(unresolved_modules,[],chunks_by_id)),response_json={"modules":unresolved_modules,"questions":[]},warning_code="ITEMS_NEED_REVIEW",warning_message="Some syllabus items remained invalid after repair and need teacher review.",attempts=1))
                    validated_modules=_dedupe_modules(valid_modules)
                    if not validated_modules:
                        raise ValueError("no_valid_syllabus_modules")
                    db.add(AcademicExtractionBatch(run_id=run.id,stage="analysis_syllabus",batch_index=0,status="validated",source_chunk_ids=[str(c.id) for _,c in syllabus_rows],response_json={"modules":validated_modules,"generation_model":actual_model},attempts=1,input_tokens=in_tokens,output_tokens=out_tokens))
                    await db.commit()

                question_source_ids={str(c.id) for _,c in question_rows}
                valid_concept_keys={c["concept_key"] for m in validated_modules for t in m.get("topics",[]) for c in t.get("concepts",[])}
                existing_q_batches={b.batch_index:b for b in (await db.execute(select(AcademicExtractionBatch).where(AcademicExtractionBatch.run_id==run.id,AcademicExtractionBatch.stage=="analysis_questions",AcademicExtractionBatch.status=="validated"))).scalars().all()}
                unresolved_q_all:list[dict[str,Any]]=[]
                for b_idx,start in enumerate(range(0,len(question_rows),QUESTION_BATCH_SIZE)):
                    q_slice=question_rows[start:start+QUESTION_BATCH_SIZE]
                    await _academic_progress(db,job_id,run,"academic_questions",b_idx,(len(question_rows)+QUESTION_BATCH_SIZE-1)//QUESTION_BATCH_SIZE)
                    cached_batch=existing_q_batches.get(b_idx)
                    if cached_batch and cached_batch.source_chunk_ids!=[str(c.id) for _,c in q_slice]:
                        raise CheckpointMismatch("Saved question checkpoint does not match the current source chunk IDs. Existing validated output was retained; investigate input provenance before retrying.")
                    if cached_batch and cached_batch.source_chunk_ids==[str(c.id) for _,c in q_slice] and cached_batch.response_json is not None:
                        validated_questions.extend(cached_batch.response_json.get("questions",[]))
                        continue
                    headers=_preceding_section_headers(question_rows,start)
                    q_prompt=_analysis_questions_prompt(validated_modules,q_slice,headers)
                    raw_q,qin,qout,qmodel=await _gemini_json(db,q_prompt,"questions")
                    run.model_name=qmodel;run.input_tokens+=qin;run.output_tokens+=qout
                    slice_valid:list[dict[str,Any]]=[];slice_invalid:list[dict[str,Any]]=[]
                    for item in (raw_q.get("questions",[]) if isinstance(raw_q,dict) else []):
                        try:
                            slice_valid.append(_validate_question_item(item,question_source_ids,valid_concept_keys,chunks_by_id))
                        except Exception:
                            slice_invalid.append(item)
                    if slice_invalid:
                        _,unresolved_q=await _repair_invalid_items(db,run,chunks_by_id,[],slice_invalid,valid_concept_keys,question_source_ids,validated_modules,slice_valid)
                        unresolved_q_all.extend(unresolved_q)
                    db.add(AcademicExtractionBatch(run_id=run.id,stage="analysis_questions",batch_index=b_idx,status="validated",source_chunk_ids=[str(c.id) for _,c in q_slice],response_json={"questions":slice_valid,"generation_model":qmodel},attempts=1,input_tokens=qin,output_tokens=qout))
                    validated_questions.extend(slice_valid)
                    await db.commit()
                if unresolved_q_all:
                    existing_q_repair=await db.scalar(select(AcademicExtractionBatch.id).where(AcademicExtractionBatch.run_id==run.id,AcademicExtractionBatch.stage=="repair",AcademicExtractionBatch.batch_index==1).limit(1))
                    if not existing_q_repair:
                        run.warnings_count+=1;run.has_warnings=True
                        db.add(AcademicExtractionBatch(run_id=run.id,stage="repair",batch_index=1,status="flagged_for_review",source_chunk_ids=sorted(_extract_invalid_chunk_ids([],unresolved_q_all,chunks_by_id)),response_json={"modules":[],"questions":unresolved_q_all},warning_code="ITEMS_NEED_REVIEW",warning_message="Some extracted questions remained invalid after the single Lite repair and need teacher review.",attempts=1))
            except QuotaExhausted:
                await _defer_job_until_quota(db,job_id)
                out["deferred"]=True;await db.commit();return out
            except Exception as exc:
                run.status="failed";run.has_warnings=True;run.warnings_count+=1
                if isinstance(exc,GeminiProviderError):
                    run.safe_error_summary=str(exc)
                    warning_code="GEMINI_PROVIDER_UNAVAILABLE" if exc.status_code==503 or exc.status_code is None else "GEMINI_PROVIDER_REQUEST_FAILED"
                elif isinstance(exc,CheckpointMismatch):
                    run.safe_error_summary=str(exc)
                    warning_code="CHECKPOINT_SOURCE_MISMATCH"
                elif isinstance(exc,(ValidationError,json.JSONDecodeError,KeyError,IndexError)):
                    run.safe_error_summary="Gemini returned a response that did not match the required academic schema. No unvalidated content was stored."
                    warning_code="ANALYSIS_RESPONSE_INVALID"
                else:
                    run.safe_error_summary="Course analysis could not be completed. Check the worker log for the failure category, then retry."
                    warning_code="ANALYSIS_FAILED"
                db.add(AcademicExtractionBatch(run_id=run.id,stage="analysis",batch_index=0,status="flagged_for_review",source_chunk_ids=[str(c.id) for _,c in all_rows],response_json={"error_category":warning_code,"provider_attempts":getattr(exc,"attempts",[])},warning_code=warning_code,warning_message=run.safe_error_summary,attempts=1))
                await db.flush()
                retained=await db.scalar(select(func.count()).select_from(AcademicExtractionBatch).where(AcademicExtractionBatch.run_id==run.id,AcademicExtractionBatch.status=="validated")) or 0
                out["validated_batches"]+=retained;out["complete"]=False
                out["safe_error_summary"]=f"{run.safe_error_summary} {retained} validated batches retained."
                out["runs"].append({"run_id":str(run.id),"status":"failed","validated_batches":retained,"safe_error_summary":run.safe_error_summary,"provider_attempts":getattr(exc,"attempts",[])})
                out["warnings_count"]+=1;out["has_warnings"]=True;out["retryable"]=out.get("retryable",True) and bool(getattr(exc,"retryable",False));logger.warning("Course analysis failed run=%s error=%s",run.id,type(exc).__name__);await db.commit();continue
        validated_modules=_dedupe_modules(validated_modules);validated_questions=_dedupe_questions(validated_questions)
        low_confidence_details=[]
        for m in validated_modules:
            if float(m.get("confidence",0))<CONFIDENCE_THRESHOLD:low_confidence_details.append({"kind":"module","label":m.get("title"),"confidence":m.get("confidence"),"source_chunk_ids":[e.get("chunk_id") for e in m.get("evidence",[])]})
            for t in m.get("topics",[]):
                if float(t.get("confidence",0))<CONFIDENCE_THRESHOLD:low_confidence_details.append({"kind":"topic","label":t.get("title"),"confidence":t.get("confidence"),"source_chunk_ids":[e.get("chunk_id") for e in t.get("evidence",[])]})
                for c in t.get("concepts",[]):
                    if float(c.get("confidence",0))<CONFIDENCE_THRESHOLD:low_confidence_details.append({"kind":"concept","label":c.get("name"),"confidence":c.get("confidence"),"source_chunk_ids":[e.get("chunk_id") for e in c.get("evidence",[])]})
        low_confidence_details.extend({"kind":"question","label":q.get("original_number"),"confidence":q.get("confidence"),"source_question_id":q.get("source_question_id")} for q in validated_questions if float(q.get("confidence",0))<CONFIDENCE_THRESHOLD)
        low_confidence_items=len(low_confidence_details)
        if low_confidence_items and not await db.scalar(select(func.count()).select_from(AcademicExtractionBatch).where(AcademicExtractionBatch.run_id==run.id,AcademicExtractionBatch.stage=="confidence_review")):
            run.warnings_count+=low_confidence_items;run.has_warnings=True
            db.add(AcademicExtractionBatch(run_id=run.id,stage="confidence_review",batch_index=0,status="flagged_for_review",source_chunk_ids=[],response_json={"items":low_confidence_details},warning_code="LOW_CONFIDENCE_ITEMS",warning_message="Low-confidence syllabus/question items require teacher review.",attempts=1))
        # `trigger_doc` is the uploaded source that initiated this course-level run.
        # There is no local `doc` in this function; passing that stale name caused a
        # NameError after Gemini returned successfully, leaving the job to retry
        # forever without persisting syllabus, questions, or roadmap nodes.
        concepts_by_key=await _persist_syllabus(db,trigger_doc,version,teacher_id,validated_modules)
        question_ids=await _persist_questions(db,trigger_doc,run,offering_id,teacher_id,validated_questions,concepts_by_key,chunks_by_id)
        await db.flush()
        try:
            db.info["academic_job_id"]=job_id
            grouping_count=await _make_dynamic_nodes(db,trigger_doc,run,version,teacher_id,validated_modules,concepts_by_key,question_ids)
            out["usable_batches"]+=1 if validated_modules or validated_questions else 0
            if grouping_count:out["usable_batches"]+=grouping_count
        except QuotaExhausted:
            run.status="running";await db.commit();await _defer_job_until_quota(db,job_id);out["deferred"]=True;return out
        except (GeminiProviderError,ValidationError,ValueError,KeyError,IndexError) as exc:
            run.safe_error_summary=str(exc) if isinstance(exc,GeminiProviderError) else "Module grouping returned an invalid academic schema. Validated earlier stages are retained."
            out["retryable"]=bool(getattr(exc,"retryable",False))
            out["provider_attempts"]=getattr(exc,"attempts",[])
        generated_node_count=await db.scalar(select(func.count()).select_from(LearningNode).where(LearningNode.course_content_version_id==version.id,LearningNode.node_code.like(f"AI-{run.id.hex[:8]}-%"))) or 0
        required_groupings=sum(any(c.get("confidence",0)>=CONFIDENCE_THRESHOLD for t in m.get("topics",[]) for c in t.get("concepts",[])) for m in validated_modules)
        completed_groupings=await db.scalar(select(func.count()).select_from(AcademicExtractionBatch).where(AcademicExtractionBatch.run_id==run.id,AcademicExtractionBatch.stage=="grouping",AcademicExtractionBatch.status=="validated")) or 0
        run.status="succeeded" if generated_node_count>0 and required_groupings>0 and completed_groupings==required_groupings and not run.safe_error_summary else "failed"
        if run.status!="succeeded":
            out["complete"]=False
            if not run.safe_error_summary:run.safe_error_summary="Academic content is retained, but required module roadmap preparation is incomplete."
            out["safe_error_summary"]=run.safe_error_summary
        if generated_node_count==0 and not run.safe_error_summary:
            run.safe_error_summary="The course content was extracted, but no validated learning roadmap nodes could be generated. Review flagged items and retry after correcting the source content."
        run.has_warnings=run.warnings_count>0
        out["warnings_count"]+=run.warnings_count
        await db.flush()
        out["validated_batches"]+=await db.scalar(select(func.count()).select_from(AcademicExtractionBatch).where(AcademicExtractionBatch.run_id==run.id,AcademicExtractionBatch.status=="validated")) or 0
        out["has_warnings"]|=run.has_warnings
        out["usable_batches"]+=1 if validated_modules or validated_questions else 0
        out["runs"].append({"run_id":str(run.id),"status":run.status,"cached":False,"warnings_count":run.warnings_count,"has_warnings":run.has_warnings,"completed_groupings":completed_groupings,"required_groupings":required_groupings})
        await db.commit()
    return out


def _dedupe_modules(modules:list[dict])->list[dict]:
    merged={}
    for mod in modules:
        key=normalize_text(mod.get("title",""))
        if not key:continue
        if key not in merged:merged[key]=mod
        else:
            existing=merged[key]
            for topic in mod.get("topics",[]):
                tkey=normalize_text(topic.get("title",""))
                prev=next((t for t in existing["topics"] if normalize_text(t.get("title",""))==tkey),None)
                if prev is None:existing["topics"].append(topic)
                else:
                    known={normalize_text(c.get("name","")) for c in prev["concepts"]}
                    prev["concepts"].extend(c for c in topic["concepts"] if normalize_text(c.get("name","")) not in known)
    return list(merged.values())


def _dedupe_questions(questions:list[dict])->list[dict]:
    output={}
    for q in questions:
        key=(q.get("source_question_id"),normalize_text(q.get("original_number","")))
        output.setdefault(key,q)
    return list(output.values())


def _unresolved_module_fragments(fragments:list[dict],valid_modules:list[dict])->list[dict]:
    unresolved=[]
    for fragment in fragments:
        parent=next((m for m in valid_modules if normalize_text(m.get("title",""))==normalize_text(fragment.get("title",""))),None)
        if parent is None:
            unresolved.append(fragment);continue
        for topic in fragment.get("topics",[]):
            matched=next((t for t in parent.get("topics",[]) if normalize_text(t.get("title",""))==normalize_text(topic.get("title",""))),None)
            if matched is None:
                unresolved.append({**fragment,"topics":[topic]});continue
            for concept in topic.get("concepts",[]):
                if not any(normalize_text(c.get("name",""))==normalize_text(concept.get("name","")) for c in matched.get("concepts",[])):
                    unresolved.append({**fragment,"topics":[{**topic,"concepts":[concept]}]})
    return unresolved


async def _persist_syllabus(db,doc,version,teacher_id,modules)->dict[str,Concept]:
    concepts_by_key={};seen_modules={}
    for mindex,module in enumerate(modules,1):
        mkey=normalize_text(module["title"])
        if _is_metadata(module["title"]):continue
        module_node=seen_modules.get(mkey)
        if not module_node:
            module_node=await db.scalar(select(SyllabusNode).where(SyllabusNode.course_content_version_id==version.id,SyllabusNode.node_type=="module",func.lower(SyllabusNode.title)==module["title"].lower()))
            if not module_node:
                module_node=SyllabusNode(institution_id=doc.institution_id,course_content_version_id=version.id,node_type="module",title=module["title"],sequence_no=mindex,source_chunk_id=uuid.UUID(module["evidence"][0]["chunk_id"]),review_status="approved" if module["confidence"]>=CONFIDENCE_THRESHOLD else "needs_review");db.add(module_node);await db.flush()
            seen_modules[mkey]=module_node
        for tindex,topic in enumerate(module.get("topics",[]),1):
            if _is_metadata(topic["title"]):continue
            topic_node=await db.scalar(select(SyllabusNode).where(SyllabusNode.course_content_version_id==version.id,SyllabusNode.parent_node_id==module_node.id,SyllabusNode.node_type=="topic",func.lower(SyllabusNode.title)==topic["title"].lower()))
            if not topic_node:
                topic_node=SyllabusNode(institution_id=doc.institution_id,course_content_version_id=version.id,parent_node_id=module_node.id,node_type="topic",title=topic["title"],sequence_no=tindex,source_chunk_id=uuid.UUID(topic["evidence"][0]["chunk_id"]),review_status="approved" if topic["confidence"]>=CONFIDENCE_THRESHOLD else "needs_review");db.add(topic_node);await db.flush()
            for concept in topic.get("concepts",[]):
                if _is_metadata(concept["name"]):continue
                ckey=concept["concept_key"]
                concept_uuid=uuid.uuid5(uuid.NAMESPACE_URL,f"doubtdesk:{doc.institution_id}:{normalize_text(concept['name'])}")
                existing=await db.get(Concept,concept_uuid)
                if not existing:
                    existing=await db.scalar(select(Concept).where(Concept.institution_id==doc.institution_id,func.lower(Concept.canonical_name)==concept["name"].strip().lower()))
                if existing:entity=existing
                else:
                    entity=Concept(id=concept_uuid,institution_id=doc.institution_id,canonical_name=concept["name"].strip());db.add(entity);await db.flush()
                    db.add(ConceptVersion(institution_id=doc.institution_id,concept_id=entity.id,version_number=1,definition=concept["definition"],review_status="teacher_approved" if concept["confidence"]>=CONFIDENCE_THRESHOLD else "provisional",created_by_user_id=teacher_id,approved_by_user_id=teacher_id if concept["confidence"]>=CONFIDENCE_THRESHOLD else None))
                concepts_by_key[ckey]=entity
                binding=await db.scalar(select(CourseContentConcept).where(CourseContentConcept.course_content_version_id==version.id,CourseContentConcept.concept_id==entity.id))
                if not binding:db.add(CourseContentConcept(course_content_version_id=version.id,concept_id=entity.id,institution_id=doc.institution_id,primary_syllabus_node_id=topic_node.id))
                if concept["confidence"]>=CONFIDENCE_THRESHOLD:
                    latest=(await db.execute(select(ConceptVersion).where(ConceptVersion.concept_id==entity.id).order_by(ConceptVersion.version_number.desc()).limit(1))).scalars().first()
                    if latest and latest.review_status=="provisional":latest.review_status="teacher_approved";latest.approved_by_user_id=teacher_id
    await db.flush();return concepts_by_key


async def _persist_questions(db,doc,run,offering_id,teacher_id,questions,concepts_by_key,chunks_by_id)->dict[str,dict]:
    output={}
    for q in questions:
        mapped=[concepts_by_key[key] for key in q["concept_keys"] if key in concepts_by_key]
        if not mapped:continue
        high=q["confidence"]>=CONFIDENCE_THRESHOLD
        source_chunk_id=uuid.UUID(q["source_question_id"].partition("#")[0].removeprefix("q:"))
        source=chunks_by_id.get(str(source_chunk_id))
        if not source:continue
        # Identity belongs to the original question source, not whichever material
        # happens to trigger a course-level retry.
        stable_question_id=uuid.uuid5(source.source_document_id,q["source_question_id"])
        existing_question=await db.get(Question,stable_question_id)
        existing_version=(await db.execute(select(QuestionVersion).where(QuestionVersion.question_id==stable_question_id).order_by(QuestionVersion.version_number.desc()).limit(1))).scalars().first() if existing_question else None
        if not existing_version:
            existing_version=await db.scalar(select(QuestionVersion).join(QuestionCoverageEvent,QuestionCoverageEvent.question_version_id==QuestionVersion.id).where(
                QuestionVersion.institution_id==doc.institution_id,
                QuestionCoverageEvent.course_offering_id==offering_id,
                QuestionVersion.metadata_json["source_question_id"].as_string()==q["source_question_id"],
            ).order_by(QuestionVersion.version_number.desc()).limit(1))
        if existing_version:
            existing_question=await db.get(Question,existing_version.question_id)
            coverage_exists=await db.scalar(select(QuestionCoverageEvent.id).where(QuestionCoverageEvent.course_offering_id==offering_id,QuestionCoverageEvent.question_version_id==existing_version.id,QuestionCoverageEvent.event_type=="extracted").limit(1))
            if not coverage_exists:
                db.add(QuestionCoverageEvent(institution_id=doc.institution_id,course_offering_id=offering_id,question_id=existing_question.id,question_version_id=existing_version.id,event_type="extracted",actor_user_id=teacher_id))
            output[str(existing_version.id)]={"question_id":str(existing_question.id),"question_version_id":str(existing_version.id),"module":q["module"],"concept_ids":[str(c.id) for c in mapped],"confidence":q["confidence"]}
            continue
        question=Question(id=stable_question_id,institution_id=doc.institution_id,created_by_user_id=teacher_id,origin_type="original_exam",lifecycle_status="approved" if high else "pending_review",is_ai_generated=False);db.add(question);await db.flush()
        version=QuestionVersion(institution_id=doc.institution_id,question_id=question.id,version_number=1,prompt_text=q["text"],question_type="descriptive",marks_total=q["marks"],difficulty_level="unrated",approval_status="approved" if high else "pending_review",created_by_user_id=teacher_id,reviewed_by_user_id=teacher_id if high else None,metadata_json={"original_number":q["original_number"],"module":q["module"],"confidence":q["confidence"],"academic_extraction_run_id":str(run.id),"source_question_id":q["source_question_id"]})
        db.add(version);await db.flush()
        part=QuestionPart(institution_id=doc.institution_id,question_version_id=version.id,part_key="A",part_prompt=q["text"],sequence_no=1,marks_available=q["marks"],answer_type="descriptive");db.add(part);await db.flush()
        remaining=q["marks"]
        for index,concept in enumerate(mapped):
            allocated=remaining if index==len(mapped)-1 else round(q["marks"]/len(mapped),2);remaining-=allocated
            db.add(QuestionPartConceptAllocation(institution_id=doc.institution_id,question_part_id=part.id,concept_id=concept.id,allocated_marks=allocated))
        for evidence in q["evidence"]:
            cited=chunks_by_id[evidence["chunk_id"]]
            db.add(QuestionVersionSource(institution_id=doc.institution_id,question_version_id=version.id,source_chunk_id=cited.id,reference_role="origin",excerpt=evidence["quote"],page_number=cited.page_number))
        db.add(QuestionCoverageEvent(institution_id=doc.institution_id,course_offering_id=offering_id,question_id=question.id,question_version_id=version.id,event_type="extracted",actor_user_id=teacher_id))
        output[str(version.id)]={"question_id":str(question.id),"question_version_id":str(version.id),"module":q["module"],"concept_ids":[str(c.id) for c in mapped],"confidence":q["confidence"]}
    await db.flush();return output


def _module_variants(label:str)->set[str]:
    """Generate normalized module key variants covering Roman and Arabic unit numbers."""
    norm=normalize_text(label)
    if not norm:return set()
    roman_to_arabic={"i":"1","ii":"2","iii":"3","iv":"4","v":"5","vi":"6","vii":"7","viii":"8","ix":"9","x":"10"}
    arabic_to_roman={v:k for k,v in roman_to_arabic.items()}
    variants={norm}
    tokens=norm.split()
    variants.add(" ".join(roman_to_arabic.get(tok,tok) for tok in tokens))
    variants.add(" ".join(arabic_to_roman.get(tok,tok) for tok in tokens))
    return variants


def _reconcile_grouping_plan(plan:NodePlan,module_questions:list[dict],concepts:list[dict])->bool:
    """Validate IDs belong to this module and deterministically deduplicate/assign minor LLM omissions."""
    question_ids_valid={q["id"] for q in module_questions}
    alias_to_qid={q["question_id"]:q["id"] for q in module_questions if q.get("question_id")}
    concept_ids_valid={c["id"] for c in concepts}
    if not plan.nodes:
        return False
    for node in plan.nodes:
        node.question_ids=[alias_to_qid.get(qid,qid) for qid in node.question_ids]
    flattened_q=[qid for node in plan.nodes for qid in node.question_ids]
    flattened_c=[cid for node in plan.nodes for cid in node.concept_ids]
    if any(qid not in question_ids_valid for qid in flattened_q) or any(cid not in concept_ids_valid for cid in flattened_c):
        return False
    seen_q:set[str]=set()
    for node in plan.nodes:
        unique_q:list[str]=[]
        for qid in node.question_ids:
            if qid not in seen_q:seen_q.add(qid);unique_q.append(qid)
        node.question_ids=unique_q
        node.concept_ids=list(dict.fromkeys(node.concept_ids))
    missing_c=[c["id"] for c in concepts if c["id"] not in set(flattened_c)]
    if missing_c:
        plan.nodes[0].concept_ids.extend(missing_c)
    for node in plan.nodes:
        if not node.concept_ids:
            node.concept_ids=[concepts[0]["id"]]
    q_concepts={q["id"]:set(q.get("concept_ids",[])) for q in module_questions}
    for qid in [q["id"] for q in module_questions if q["id"] not in seen_q]:
        target=max(plan.nodes,key=lambda n:len(set(n.concept_ids)&q_concepts.get(qid,set())))
        target.question_ids.append(qid)
    return True


async def _make_dynamic_nodes(db,doc,run,version,teacher_id,modules,concepts_by_key,question_ids)->int:
    count=0
    for module_index,module in enumerate(modules):
        job_id=db.info.get("academic_job_id")
        if job_id:
            await _academic_progress(db,job_id,run,"academic_grouping",module_index,len(modules))
        mod_variants=_module_variants(module["title"])
        concepts=[]
        for topic in module.get("topics",[]):
            for c in topic.get("concepts",[]):
                entity=concepts_by_key.get(c["concept_key"])
                if entity and c["confidence"]>=CONFIDENCE_THRESHOLD:concepts.append({"id":str(entity.id),"name":entity.canonical_name,"topic":topic["title"]})
        concepts=list({c["id"]:c for c in concepts}.values())
        if not concepts:continue
        module_questions=[]
        for qid,q in question_ids.items():
            mapped=set(q["concept_ids"])
            q_variants=_module_variants(q["module"])
            if q_variants and not any((qv in mv or mv in qv) for qv in q_variants for mv in mod_variants):continue
            if mapped.intersection(c["id"] for c in concepts):
                qver=await db.get(QuestionVersion,uuid.UUID(qid))
                module_questions.append({"id":qid,"question_id":q["question_id"],"text":qver.prompt_text[:280] if qver else "","marks":float(qver.marks_total) if qver else 0,"concept_ids":q["concept_ids"]})
        batch=(await db.execute(select(AcademicExtractionBatch).where(AcademicExtractionBatch.run_id==run.id,AcademicExtractionBatch.stage=="grouping",AcademicExtractionBatch.batch_index==module_index))).scalars().first()
        if batch and batch.status=="validated" and batch.response_json:
            plan=NodePlan.model_validate(batch.response_json)
        else:
            if batch:
                if batch.status=="flagged_for_review" and run.warnings_count>0:
                    run.warnings_count-=1
                await db.delete(batch);await db.flush()
            prompt_questions=[{"id":q["id"],"text":q["text"],"marks":q["marks"],"concept_ids":q["concept_ids"]} for q in module_questions]
            prompt=_group_prompt(module["title"],concepts,prompt_questions)
            raw,tok_in,tok_out,actual_model=await _gemini_json(db,prompt,"grouping")
            plan=NodePlan.model_validate(raw)
            if not _reconcile_grouping_plan(plan,module_questions,concepts):
                db.add(AcademicExtractionBatch(run_id=run.id,stage="grouping",batch_index=module_index,status="flagged_for_review",source_chunk_ids=[],response_json=raw,warning_code="GROUPING_VALIDATION_FAILED",warning_message=f"Learning-node grouping for {module['title']} did not preserve all concepts/questions.",attempts=1));run.warnings_count+=1;run.has_warnings=True
                continue
            run.input_tokens+=tok_in;run.output_tokens+=tok_out
            batch=AcademicExtractionBatch(run_id=run.id,stage="grouping",batch_index=module_index,status="validated",source_chunk_ids=[],response_json=plan.model_dump(mode="json"),attempts=1,input_tokens=tok_in,output_tokens=tok_out);db.add(batch);await db.flush()
        created_by_key={}
        for node_index,node_data in enumerate(sorted(plan.nodes,key=lambda node:node.difficulty_rank),1):
            node_code=f"AI-{run.id.hex[:8]}-{module_index+1}-{node_index}"
            existing=await db.scalar(select(LearningNode).where(LearningNode.course_offering_id==version.course_offering_id,LearningNode.node_code==node_code))
            if existing:
                if existing.module_title is None:existing.module_title=module["title"]
                if existing.difficulty_rank is None:existing.difficulty_rank=node_data.difficulty_rank
                node=existing
            else:
                node=LearningNode(institution_id=doc.institution_id,course_offering_id=version.course_offering_id,course_content_version_id=version.id,node_code=node_code,module_title=module["title"],difficulty_rank=node_data.difficulty_rank,title=node_data.title,description=node_data.objective,sequence_no=module_index*1000+node_index,status="draft",created_by_user_id=teacher_id);db.add(node);await db.flush();count+=1
            created_by_key[node_data.node_key]=node
            for concept_id in node_data.concept_ids:
                if not await db.scalar(select(LearningNodeConcept.id).where(LearningNodeConcept.learning_node_id==node.id,LearningNodeConcept.concept_id==uuid.UUID(concept_id)).limit(1)):
                    db.add(LearningNodeConcept(institution_id=doc.institution_id,learning_node_id=node.id,concept_id=uuid.UUID(concept_id),relationship_role="primary",mapping_status="teacher_approved"))
            for question_version_id in node_data.question_ids:
                q=question_ids[question_version_id]
                if not await db.scalar(select(LearningNodeQuestion.id).where(LearningNodeQuestion.learning_node_id==node.id,LearningNodeQuestion.question_version_id==uuid.UUID(question_version_id)).limit(1)):
                    db.add(LearningNodeQuestion(institution_id=doc.institution_id,learning_node_id=node.id,question_id=uuid.UUID(q["question_id"]),question_version_id=uuid.UUID(question_version_id),relationship_role="practice"))
            if not await db.scalar(select(LearningObjective.id).where(LearningObjective.course_content_version_id==version.id,LearningObjective.objective_code==f"LO-{node.id.hex[:16]}").limit(1)):
                db.add(LearningObjective(institution_id=doc.institution_id,course_content_version_id=version.id,concept_id=uuid.UUID(node_data.concept_ids[0]),objective_code=f"LO-{node.id.hex[:16]}",description=node_data.objective,bloom_level="understand",sequence_no=node.sequence_no))
        seen_prereqs:set[tuple[uuid.UUID,uuid.UUID]]=set()
        for node_data in plan.nodes:
            current=created_by_key.get(node_data.node_key)
            if not current:continue
            for prereq_key in node_data.prerequisite_node_keys:
                prerequisite=created_by_key.get(prereq_key)
                if not prerequisite or prerequisite.id==current.id:continue
                pair=(current.id,prerequisite.id)
                if pair in seen_prereqs:continue
                seen_prereqs.add(pair)
                if not await db.scalar(select(LearningNodePrerequisite.id).where(LearningNodePrerequisite.learning_node_id==current.id,LearningNodePrerequisite.prerequisite_node_id==prerequisite.id).limit(1)):
                    db.add(LearningNodePrerequisite(institution_id=doc.institution_id,learning_node_id=current.id,prerequisite_node_id=prerequisite.id,prerequisite_type="required"))
        # Commit each module's completed nodes before asking Gemini to build the next one.
        await db.commit()
    await db.flush();return count


async def _defer_job_until_quota(db:AsyncSession,job_id:uuid.UUID)->None:
    job=await db.get(BackgroundJob,job_id)
    if not job:return
    now=datetime.now(timezone.utc);reset=(now+timedelta(days=1)).replace(hour=0,minute=0,second=5,microsecond=0)
    job.status="retrying";job.current_stage="waiting_for_provider_quota";job.next_retry_at=reset;job.lease_owner=None;job.lease_expires_at=None;job.safe_error_summary="Gemini daily request quota is exhausted; processing is scheduled to resume after quota reset.";job.updated_at=now;job.attempt_count=max(0,job.attempt_count-1)
    checkpoint=dict(job.checkpoint_json or {});checkpoint["provider_quota"]={"reason":"daily_rpd_exhausted","resume_after":reset.isoformat()};job.checkpoint_json=checkpoint
    db.add(BackgroundJobEvent(job_id=job.id,event_type="progress_updated",stage_name=job.current_stage,progress_percent=job.progress_percent,message_safe=job.safe_error_summary,details_json=checkpoint["provider_quota"]))
    await db.commit()
