import uuid
from datetime import datetime, date
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AcademicExtractionRun(Base):
    """Versioned, checksum-keyed academic AI run for one course offering."""
    __tablename__ = "academic_extraction_runs"
    __table_args__ = (UniqueConstraint("course_offering_id", "pipeline_key", name="uq_academic_run_cache_key"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    source_document_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False, index=True)
    course_offering_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False, index=True)
    content_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    pipeline_key: Mapped[str] = mapped_column(String(128), nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")  # running | succeeded | failed
    has_warnings: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    warnings_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    safe_error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class AcademicExtractionBatch(Base):
    """Persisted stage/batch checkpoint; invalid batches remain teacher-reviewable."""
    __tablename__ = "academic_extraction_batches"
    __table_args__ = (UniqueConstraint("run_id", "stage", "batch_index", name="uq_academic_batch"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("academic_extraction_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    stage: Mapped[str] = mapped_column(String(30), nullable=False)  # syllabus | questions | grouping
    batch_index: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)  # validated | flagged_for_review | failed
    source_chunk_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    response_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    warning_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    warning_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    input_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class GeminiQuotaWindow(Base):
    """Atomic per-model daily request counter and conservative rolling-minute token window."""
    __tablename__ = "gemini_quota_windows"
    __table_args__ = (UniqueConstraint("model_name", "quota_date", name="uq_gemini_quota_day"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    quota_date: Mapped[date] = mapped_column(Date, nullable=False)
    requests_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_in_window: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    window_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_request_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
