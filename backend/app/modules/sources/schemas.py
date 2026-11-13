from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel


class SourceChunkOut(BaseModel):
    id: str
    chunk_index: int
    page_number: Optional[int] = None
    slide_number: Optional[int] = None
    section_path: Optional[str] = None
    chunk_type: str
    content_text: str
    content_hash: str
    metadata_json: Optional[Dict[str, Any]] = None

    model_config = {"from_attributes": True}


class SourceExtractionOut(BaseModel):
    id: str
    source_document_id: str
    extractor_name: str
    extractor_version: str
    status: str
    warnings_json: Optional[List[str]] = None
    error_code: Optional[str] = None
    safe_error_summary: Optional[str] = None
    raw_text_checksum: Optional[str] = None
    created_at: datetime
    chunks: Optional[List[SourceChunkOut]] = None

    model_config = {"from_attributes": True}


class SourceDocumentOut(BaseModel):
    id: str
    institution_id: str
    original_filename: str
    display_filename: str
    mime_type: str
    file_extension: str
    size_bytes: int
    sha256_checksum: str
    source_type: str
    status: str
    publication_status: str
    review_status: str = "pending_review"
    visibility: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StudentStudyMaterialOut(BaseModel):
    id: str
    course_offering_id: str
    original_filename: str
    source_type: str
    mime_type: str
    size_bytes: int
    created_at: datetime
    subject_code: Optional[str] = None
    subject_name: Optional[str] = None
    section_code: Optional[str] = None


class TeacherSourceMaterialOut(SourceDocumentOut):
    course_offering_id: str
    job_id: Optional[str] = None
    job_status: Optional[str] = None
    job_stage: Optional[str] = None
    job_progress_percent: Optional[float] = None
    job_error_summary: Optional[str] = None


class DocumentUploadResponse(BaseModel):
    document: SourceDocumentOut
    job_id: Optional[str] = None
    already_uploaded: bool = False
    message: str


class SourceDocumentReviewRequest(BaseModel):
    publication_status: Optional[str] = None
    review_status: Optional[str] = None


class JobEventOut(BaseModel):
    id: str
    event_type: str
    stage_name: Optional[str] = None
    progress_percent: Optional[float] = None
    message_safe: str
    details_json: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class JobStatusResponse(BaseModel):
    id: str
    job_type: str
    target_entity_type: str
    target_entity_id: Optional[str] = None
    status: str
    current_stage: str
    progress_percent: float
    attempt_count: int
    max_attempts: int
    error_code: Optional[str] = None
    safe_error_summary: Optional[str] = None
    result_reference_json: Optional[Dict[str, Any]] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    events: Optional[List[JobEventOut]] = None

    model_config = {"from_attributes": True}


class RagSearchResultOut(BaseModel):
    chunk_id: str
    document_id: str
    document_title: str
    source_type: str
    page_number: Optional[int] = None
    slide_number: Optional[int] = None
    section_path: Optional[str] = None
    content_text: str
    citation: str
    score: float
