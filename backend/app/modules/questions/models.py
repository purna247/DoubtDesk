import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String,
    Text,
    Integer,
    Numeric,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Question(Base):
    """
    Stable academic identity for an assessment question.
    Original exam questions are never merged or deleted when duplicates or variants exist.
    """
    __tablename__ = "questions"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    origin_type: Mapped[str] = mapped_column(
        String(30), default="teacher_authored", nullable=False
    )  # original_exam | teacher_authored | imported | ai_supplementary
    lifecycle_status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False
    )  # draft | pending_review | approved | rejected | archived
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    versions: Mapped[List["QuestionVersion"]] = relationship(
        "QuestionVersion", back_populates="question", cascade="all, delete-orphan", order_by="QuestionVersion.version_number.desc()"
    )
    coverage_events: Mapped[List["QuestionCoverageEvent"]] = relationship(
        "QuestionCoverageEvent", back_populates="question", cascade="all, delete-orphan"
    )


class QuestionVersion(Base):
    """
    Immutable version of question text, prompt, marks, and pedagogical classification.
    Once referenced by an active assessment, it cannot be modified in place.
    """
    __tablename__ = "question_versions"
    __table_args__ = (
        UniqueConstraint("question_id", "version_number", name="uq_question_version_num"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    prompt_text: Mapped[str] = mapped_column(Text, nullable=False)
    question_type: Mapped[str] = mapped_column(
        String(30), default="mcq", nullable=False
    )  # mcq | fill_blank | matching_pairs | ordering | classification | key_points_check | descriptive
    command_verb: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # analyze, evaluate, calculate, explain
    expected_answer_depth: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)  # brief | detailed | derivation | proof
    marks_total: Mapped[float] = mapped_column(Numeric(8, 2), default=1.0, nullable=False)
    difficulty_level: Mapped[str] = mapped_column(
        String(20), default="medium", nullable=False
    )  # very_easy | easy | medium | hard | very_hard | unrated
    cognitive_level: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True
    )  # remember | understand | apply | analyze | evaluate | create
    approval_status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False
    )  # draft | pending_review | approved | rejected | superseded
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    marking_guidance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    question: Mapped["Question"] = relationship("Question", back_populates="versions")
    parts: Mapped[List["QuestionPart"]] = relationship(
        "QuestionPart", back_populates="question_version", cascade="all, delete-orphan", order_by="QuestionPart.sequence_no"
    )
    learning_objective_links: Mapped[List["QuestionVersionLearningObjective"]] = relationship(
        "QuestionVersionLearningObjective", back_populates="question_version", cascade="all, delete-orphan"
    )
    source_links: Mapped[List["QuestionVersionSource"]] = relationship(
        "QuestionVersionSource", back_populates="question_version", cascade="all, delete-orphan"
    )


class QuestionPart(Base):
    """
    Subquestion or part inside a QuestionVersion. Single-part questions have one default part.
    Enforces discrete mark availability for granular concept attribution.
    """
    __tablename__ = "question_parts"
    __table_args__ = (
        UniqueConstraint("question_version_id", "part_key", name="uq_question_part_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("question_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    part_key: Mapped[str] = mapped_column(String(20), default="A", nullable=False)
    part_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    marks_available: Mapped[float] = mapped_column(Numeric(8, 2), default=1.0, nullable=False)
    answer_type: Mapped[str] = mapped_column(
        String(30), default="mcq", nullable=False
    )  # mcq | fill_blank | matching_pairs | ordering | classification | key_points_check | descriptive
    expected_answer_depth: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    question_version: Mapped["QuestionVersion"] = relationship("QuestionVersion", back_populates="parts")
    options: Mapped[List["QuestionPartOption"]] = relationship(
        "QuestionPartOption", back_populates="part", cascade="all, delete-orphan", order_by="QuestionPartOption.sequence_no"
    )
    concept_allocations: Mapped[List["QuestionPartConceptAllocation"]] = relationship(
        "QuestionPartConceptAllocation", back_populates="part", cascade="all, delete-orphan"
    )


class Misconception(Base):
    """
    Institution-scoped misconception catalogue mapped to concepts.
    Used for diagnosing specific student error patterns when wrong options are chosen.
    """
    __tablename__ = "misconceptions"
    __table_args__ = (
        UniqueConstraint("institution_id", "code", name="uq_institution_misconception_code"),
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
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    review_status: Mapped[str] = mapped_column(
        String(20), default="teacher_approved", nullable=False
    )  # provisional | teacher_approved | retired

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    concept: Mapped["app.modules.knowledge.models.Concept"] = relationship("app.modules.knowledge.models.Concept")


class QuestionPartOption(Base):
    """
    Structured objective options for MCQ and selection activities.
    Option correctness is server-authoritative and never serialized to students before submission.
    """
    __tablename__ = "question_part_options"
    __table_args__ = (
        UniqueConstraint("question_part_id", "option_key", name="uq_part_option_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_part_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("question_parts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    option_key: Mapped[str] = mapped_column(String(10), nullable=False)  # A, B, C, D
    display_text: Mapped[str] = mapped_column(Text, nullable=False)
    sequence_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_correct: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    misconception_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("misconceptions.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    part: Mapped["QuestionPart"] = relationship("QuestionPart", back_populates="options")
    misconception: Mapped[Optional["Misconception"]] = relationship("Misconception")


class QuestionPartConceptAllocation(Base):
    """
    Explicit mark budget allocated to assessed concepts for a question part.
    Enforces that sum(allocated_marks) == question_parts.marks_available.
    Never duplicates full question marks independently across mapped concepts.
    """
    __tablename__ = "question_part_concept_allocations"
    __table_args__ = (
        UniqueConstraint("question_part_id", "concept_id", name="uq_part_concept_alloc"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_part_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("question_parts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    allocated_marks: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    allocation_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    part: Mapped["QuestionPart"] = relationship("QuestionPart", back_populates="concept_allocations")
    concept: Mapped["app.modules.knowledge.models.Concept"] = relationship("app.modules.knowledge.models.Concept")


class QuestionVersionLearningObjective(Base):
    """Many-to-many relationship linking a question version to learning objectives."""
    __tablename__ = "question_version_learning_objectives"
    __table_args__ = (
        UniqueConstraint("question_version_id", "learning_objective_id", name="uq_qversion_lo"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("question_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    learning_objective_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learning_objectives.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relationship_role: Mapped[str] = mapped_column(
        String(20), default="primary", nullable=False
    )  # primary | supporting

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    question_version: Mapped["QuestionVersion"] = relationship("QuestionVersion", back_populates="learning_objective_links")
    learning_objective: Mapped["app.modules.knowledge.models.LearningObjective"] = relationship("app.modules.knowledge.models.LearningObjective")


class QuestionVersionSource(Base):
    """Provenance link grounding a question version in an extracted source chunk or document."""
    __tablename__ = "question_version_sources"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("question_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_chunk_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("source_chunks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reference_role: Mapped[str] = mapped_column(
        String(30), default="origin", nullable=False
    )  # origin | supporting | answer_key | marking_scheme
    excerpt: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    question_version: Mapped["QuestionVersion"] = relationship("QuestionVersion", back_populates="source_links")
    source_chunk: Mapped[Optional["app.modules.sources.models.SourceChunk"]] = relationship("app.modules.sources.models.SourceChunk")


class QuestionRelationship(Base):
    """Directed or symmetric relationship between stable question IDs."""
    __tablename__ = "question_relationships"
    __table_args__ = (
        CheckConstraint("source_question_id <> target_question_id", name="chk_question_not_self_rel"),
        UniqueConstraint("source_question_id", "target_question_id", "relationship_type", name="uq_question_rel"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    source_question_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_question_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relationship_type: Mapped[str] = mapped_column(
        String(40), nullable=False
    )  # related | possible_near_duplicate | variant_of | broader_requirement | narrower_requirement | prerequisite_for | same_learning_objective
    confidence: Mapped[Optional[float]] = mapped_column(Numeric(4, 3), nullable=True)
    review_status: Mapped[str] = mapped_column(
        String(20), default="provisional", nullable=False
    )  # provisional | teacher_approved | rejected
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class QuestionCoverageEvent(Base):
    """
    Append-only coverage progress event tracking question integration into offering syllabus.
    Prevents false reporting of coverage based on mere foreign key existence.
    """
    __tablename__ = "question_coverage_events"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_offering_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("question_versions.id", ondelete="SET NULL"), nullable=True
    )
    event_type: Mapped[str] = mapped_column(
        String(40), nullable=False
    )  # extracted | classified | concept_mapped | assigned_to_node | represented_by_activity | included_in_assessment | attempted_by_student | teacher_approved | mapping_rejected
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    details_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    question: Mapped["Question"] = relationship("Question", back_populates="coverage_events")

