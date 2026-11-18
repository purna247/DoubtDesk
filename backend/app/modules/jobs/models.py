import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String,
    Text,
    Integer,
    Numeric,
    DateTime,
    ForeignKey,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class WorkerHeartbeat(Base):
    __tablename__ = "worker_heartbeats"

    worker_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class BackgroundJob(Base):
    """
    Durable PostgreSQL-backed queue record.
    Supports transactional claiming (FOR UPDATE SKIP LOCKED) and lease recovery.
    """
    __tablename__ = "background_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=True, index=True
    )
    requested_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    job_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # extract_source_document | generate_course_syllabus | etc.
    target_entity_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_entity_id: Mapped[Optional[uuid.UUID]] = mapped_column(PG_UUID(as_uuid=True), nullable=True)
    scope_course_offering_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("course_offerings.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="queued", nullable=False, index=True
    )  # queued | running | retrying | succeeded | failed | cancelled
    current_stage: Mapped[str] = mapped_column(String(50), default="queued", nullable=False)
    progress_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0.0, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)

    lease_owner: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    lease_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    next_retry_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    input_reference_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    checkpoint_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    result_reference_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    safe_error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    events: Mapped[List["BackgroundJobEvent"]] = relationship(
        "BackgroundJobEvent", back_populates="job", cascade="all, delete-orphan", order_by="BackgroundJobEvent.created_at"
    )


class BackgroundJobEvent(Base):
    """Append-only audit and progress event history for background jobs."""
    __tablename__ = "background_job_events"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("background_jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # job_enqueued | lease_acquired | progress_updated | stage_completed | error | completed
    stage_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    progress_percent: Mapped[Optional[float]] = mapped_column(Numeric(5, 2), nullable=True)
    message_safe: Mapped[str] = mapped_column(Text, nullable=False)
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    job: Mapped["BackgroundJob"] = relationship("BackgroundJob", back_populates="events")
