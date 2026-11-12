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
    UniqueConstraint,
    CheckConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class CourseContentVersion(Base):
    """
    Immutable publication boundary for a course offering's academic learning content.
    Student views must resolve the published version only.
    """
    __tablename__ = "course_content_versions"
    __table_args__ = (
        UniqueConstraint("course_offering_id", "version_number", name="uq_course_content_version_num"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_offering_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False
    )  # draft | in_review | approved | published | superseded | archived
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    change_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    offering: Mapped["app.modules.academics.models.CourseOffering"] = relationship("app.modules.academics.models.CourseOffering")
    syllabus_nodes: Mapped[List["SyllabusNode"]] = relationship(
        "SyllabusNode", back_populates="content_version", cascade="all, delete-orphan", order_by="SyllabusNode.sequence_no"
    )
    concept_bindings: Mapped[List["CourseContentConcept"]] = relationship(
        "CourseContentConcept", back_populates="content_version", cascade="all, delete-orphan"
    )
    learning_objectives: Mapped[List["LearningObjective"]] = relationship(
        "LearningObjective", back_populates="content_version", cascade="all, delete-orphan"
    )


class SyllabusNode(Base):
    """
    Flexible hierarchical tree for module/topic/subtopic syllabus structure.
    Preserves links to source chunks for provenance while supporting teacher review.
    """
    __tablename__ = "syllabus_nodes"
    __table_args__ = (
        CheckConstraint("parent_node_id IS NULL OR parent_node_id <> id", name="chk_node_not_self_parent"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_content_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("course_content_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_node_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("syllabus_nodes.id", ondelete="CASCADE"), nullable=True, index=True
    )
    node_type: Mapped[str] = mapped_column(
        String(20), default="module", nullable=False
    )  # module | topic | subtopic
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sequence_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    source_chunk_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("source_chunks.id", ondelete="SET NULL"), nullable=True
    )
    review_status: Mapped[str] = mapped_column(
        String(20), default="extracted", nullable=False
    )  # extracted | needs_review | approved | rejected

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    content_version: Mapped["CourseContentVersion"] = relationship("CourseContentVersion", back_populates="syllabus_nodes")
    parent_node: Mapped[Optional["SyllabusNode"]] = relationship("SyllabusNode", remote_side=[id], back_populates="child_nodes")
    child_nodes: Mapped[List["SyllabusNode"]] = relationship("SyllabusNode", back_populates="parent_node", cascade="all, delete-orphan", order_by="SyllabusNode.sequence_no")
    source_chunk: Mapped[Optional["app.modules.sources.models.SourceChunk"]] = relationship("app.modules.sources.models.SourceChunk")
    learning_objectives: Mapped[List["LearningObjective"]] = relationship("LearningObjective", back_populates="syllabus_node")


class Concept(Base):
    """
    Stable concept registry identity within an institution.
    Concept IDs remain permanent across wording and definition changes.
    """
    __tablename__ = "concepts"
    __table_args__ = (
        UniqueConstraint("institution_id", "concept_code", name="uq_institution_concept_code"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    concept_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )  # active | retired

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    versions: Mapped[List["ConceptVersion"]] = relationship(
        "ConceptVersion", back_populates="concept", cascade="all, delete-orphan", order_by="ConceptVersion.version_number.desc()"
    )
    content_bindings: Mapped[List["CourseContentConcept"]] = relationship(
        "CourseContentConcept", back_populates="concept", cascade="all, delete-orphan"
    )


class ConceptVersion(Base):
    """Editable and versioned definitions and pedagogical explanations for a concept."""
    __tablename__ = "concept_versions"
    __table_args__ = (
        UniqueConstraint("concept_id", "version_number", name="uq_concept_version_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    definition: Mapped[str] = mapped_column(Text, nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    review_status: Mapped[str] = mapped_column(
        String(20), default="provisional", nullable=False
    )  # provisional | teacher_approved | rejected
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    concept: Mapped["Concept"] = relationship("Concept", back_populates="versions")


class CourseContentConcept(Base):
    """Binding of a Concept to a Course Content Version and primary Syllabus Node."""
    __tablename__ = "course_content_concepts"
    __table_args__ = (
        UniqueConstraint("course_content_version_id", "concept_id", name="uq_content_version_concept"),
    )

    course_content_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("course_content_versions.id", ondelete="CASCADE"), primary_key=True
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    primary_syllabus_node_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("syllabus_nodes.id", ondelete="SET NULL"), nullable=True
    )
    importance_weight: Mapped[float] = mapped_column(Numeric(4, 2), default=1.0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    content_version: Mapped["CourseContentVersion"] = relationship("CourseContentVersion", back_populates="concept_bindings")
    concept: Mapped["Concept"] = relationship("Concept", back_populates="content_bindings")
    syllabus_node: Mapped[Optional["SyllabusNode"]] = relationship("SyllabusNode")


class LearningObjective(Base):
    """Course outcome / learning objective mapped to Bloom's taxonomy and concepts."""
    __tablename__ = "learning_objectives"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_content_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("course_content_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    syllabus_node_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("syllabus_nodes.id", ondelete="SET NULL"), nullable=True
    )
    concept_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True
    )
    objective_code: Mapped[str] = mapped_column(String(50), nullable=False)  # e.g. CO1, CO2
    description: Mapped[str] = mapped_column(Text, nullable=False)
    bloom_level: Mapped[str] = mapped_column(
        String(30), default="understand", nullable=False
    )  # remember | understand | apply | analyze | evaluate | create
    sequence_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    content_version: Mapped["CourseContentVersion"] = relationship("CourseContentVersion", back_populates="learning_objectives")
    syllabus_node: Mapped[Optional["SyllabusNode"]] = relationship("SyllabusNode", back_populates="learning_objectives")
    concept: Mapped[Optional["Concept"]] = relationship("Concept")

