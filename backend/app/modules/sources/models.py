import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String,
    Text,
    BigInteger,
    Integer,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class SourceDocument(Base):
    """Authoritative metadata record for an uploaded source file (bytes in storage)."""
    __tablename__ = "source_documents"
    __table_args__ = (
        UniqueConstraint("institution_id", "content_dedupe_key", name="uq_source_document_dedupe_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    uploaded_by_membership_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institution_memberships.id", ondelete="CASCADE"), nullable=False, index=True
    )
    original_filename: Mapped[str] = mapped_column(Text, nullable=False)
    display_filename: Mapped[str] = mapped_column(Text, nullable=False)
    storage_backend: Mapped[str] = mapped_column(String(20), default="local", nullable=False)  # local | r2
    storage_key: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_extension: Mapped[str] = mapped_column(String(20), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256_checksum: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Nullable for legacy duplicate rows retained to preserve their provenance.
    # New uploads use a tenant-scoped key derived from checksum and material classification.
    content_dedupe_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    source_type: Mapped[str] = mapped_column(
        String(30), default="syllabus", nullable=False
    )  # syllabus | question_paper | lecture_notes | slides | reference_material | other
    status: Mapped[str] = mapped_column(
        String(20), default="uploaded", nullable=False
    )  # uploaded | processing | processed | failed | archived
    publication_status: Mapped[str] = mapped_column(
        String(20), default="pending_review", nullable=False
    )  # pending_review | published | rejected
    review_status: Mapped[str] = mapped_column(
        String(20), default="pending_review", nullable=False
    )  # pending_review | approved | rejected; independent from student publication
    visibility: Mapped[str] = mapped_column(
        String(20), default="course", nullable=False
    )  # private | course | institution

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    extractions: Mapped[List["SourceExtraction"]] = relationship(
        "SourceExtraction", back_populates="document", cascade="all, delete-orphan"
    )
    offering_links: Mapped[List["SourceDocumentCourseOffering"]] = relationship(
        "SourceDocumentCourseOffering", back_populates="document", cascade="all, delete-orphan"
    )
    curriculum_links: Mapped[List["SourceDocumentCurriculumVersion"]] = relationship(
        "SourceDocumentCurriculumVersion", back_populates="document", cascade="all, delete-orphan"
    )


class SourceDocumentCourseOffering(Base):
    """Explicit join table linking an uploaded source document to a Course Offering."""
    __tablename__ = "source_document_course_offerings"
    __table_args__ = (
        UniqueConstraint("source_document_id", "course_offering_id", name="uq_src_doc_course_offering"),
    )

    source_document_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("source_documents.id", ondelete="CASCADE"), primary_key=True
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_offering_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("course_offerings.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped["SourceDocument"] = relationship("SourceDocument", back_populates="offering_links")
    offering: Mapped["app.modules.academics.models.CourseOffering"] = relationship("app.modules.academics.models.CourseOffering")


class SourceDocumentCurriculumVersion(Base):
    """Explicit join table linking an uploaded source document to a Curriculum Version."""
    __tablename__ = "source_document_curriculum_versions"
    __table_args__ = (
        UniqueConstraint("source_document_id", "curriculum_version_id", name="uq_src_doc_curriculum_ver"),
    )

    source_document_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("source_documents.id", ondelete="CASCADE"), primary_key=True
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    curriculum_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("curriculum_versions.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    document: Mapped["SourceDocument"] = relationship("SourceDocument", back_populates="curriculum_links")
    curriculum_version: Mapped["app.modules.academics.models.CurriculumVersion"] = relationship("app.modules.academics.models.CurriculumVersion")


class SourceExtraction(Base):
    """Extraction run/version for an ingested source document."""
    __tablename__ = "source_extractions"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    extractor_name: Mapped[str] = mapped_column(String(50), nullable=False)
    extractor_version: Mapped[str] = mapped_column(String(30), nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="queued", nullable=False
    )  # queued | running | succeeded | partial | failed
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    warnings_json: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    error_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    safe_error_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_text_checksum: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    document: Mapped["SourceDocument"] = relationship("SourceDocument", back_populates="extractions")
    chunks: Mapped[List["SourceChunk"]] = relationship(
        "SourceChunk",
        back_populates="extraction",
        cascade="all, delete-orphan",
        order_by="SourceChunk.chunk_index",
    )
    assets: Mapped[List["SourceAsset"]] = relationship(
        "SourceAsset", back_populates="extraction", cascade="all, delete-orphan"
    )


class SourceChunk(Base):
    """Atomic text segment extracted from document pages/slides with full provenance."""
    __tablename__ = "source_chunks"
    __table_args__ = (
        UniqueConstraint("source_extraction_id", "chunk_index", name="uq_src_chunk_idx"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_extraction_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("source_extractions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    slide_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    section_path: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    chunk_type: Mapped[str] = mapped_column(
        String(30), default="paragraph", nullable=False
    )  # paragraph | table | heading | caption | other
    content_text: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    embedding_json: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    extraction: Mapped["SourceExtraction"] = relationship("SourceExtraction", back_populates="chunks")
    document: Mapped["SourceDocument"] = relationship("SourceDocument")


class SourceAsset(Base):
    """Extracted binary asset (diagram, figure, formula screenshot) with source coordinates."""
    __tablename__ = "source_assets"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_document_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_extraction_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("source_extractions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    storage_backend: Mapped[str] = mapped_column(String(20), default="local", nullable=False)
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    asset_type: Mapped[str] = mapped_column(
        String(30), default="image", nullable=False
    )  # image | diagram | embedded_table
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    slide_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    surrounding_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sha256_checksum: Mapped[str] = mapped_column(String(64), nullable=False)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    extraction: Mapped["SourceExtraction"] = relationship("SourceExtraction", back_populates="assets")
