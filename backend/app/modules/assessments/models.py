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


class Assessment(Base):
    """
    Stable identity for a course assessment (Practice, Boss Arena, or Intervention Phase).
    """
    __tablename__ = "assessments"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_offering_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    learning_node_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learning_nodes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    assessment_type: Mapped[str] = mapped_column(
        String(40), default="node_practice", nullable=False
    )  # node_practice | boss | intervention_baseline | intervention_practice | intervention_post
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False
    )  # draft | published | archived
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    offering: Mapped["app.modules.academics.models.CourseOffering"] = relationship("app.modules.academics.models.CourseOffering")
    is_formal_quiz: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    scheduled_start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_end_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    shuffle_questions: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    shuffle_options: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_finalized: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    finalized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finalized_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    versions: Mapped[List["AssessmentVersion"]] = relationship(
        "AssessmentVersion", back_populates="assessment", cascade="all, delete-orphan", order_by="AssessmentVersion.version_number.desc()"
    )


class AssessmentVersion(Base):
    """
    Immutable version of assessment rules, time limit, and items.
    """
    __tablename__ = "assessment_versions"
    __table_args__ = (
        UniqueConstraint("assessment_id", "version_number", name="uq_assessment_version_num"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False
    )  # draft | approved | published | superseded | archived
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g. 1800 for 30m, None for untimed
    max_attempts: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # None = unlimited
    retake_policy_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    unlock_policy_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    pass_criteria_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    assessment: Mapped["Assessment"] = relationship("Assessment", back_populates="versions")
    items: Mapped[List["AssessmentItem"]] = relationship(
        "AssessmentItem", back_populates="assessment_version", cascade="all, delete-orphan", order_by="AssessmentItem.sequence_no"
    )
    attempts: Mapped[List["AssessmentAttempt"]] = relationship(
        "AssessmentAttempt", back_populates="assessment_version", cascade="all, delete-orphan"
    )


class AssessmentItem(Base):
    """
    An assessable question or activity item within one immutable assessment version.
    """
    __tablename__ = "assessment_items"
    __table_args__ = (
        UniqueConstraint("assessment_version_id", "sequence_no", name="uq_assessment_item_seq"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assessment_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("question_versions.id", ondelete="SET NULL"), nullable=True
    )
    activity_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("activity_versions.id", ondelete="SET NULL"), nullable=True
    )
    sequence_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    marks_available: Mapped[float] = mapped_column(Numeric(8, 2), default=1.0, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    assessment_version: Mapped["AssessmentVersion"] = relationship("AssessmentVersion", back_populates="items")
    activity_version: Mapped[Optional["app.modules.learning.models.ActivityVersion"]] = relationship("app.modules.learning.models.ActivityVersion")
    question_version: Mapped[Optional["app.modules.questions.models.QuestionVersion"]] = relationship("app.modules.questions.models.QuestionVersion")
    concept_allocations: Mapped[List["AssessmentItemConceptAllocation"]] = relationship(
        "AssessmentItemConceptAllocation", back_populates="assessment_item", cascade="all, delete-orphan"
    )


class AssessmentItemConceptAllocation(Base):
    """
    Snapshot of concept mark allocation for this assessment item.
    Prevents later question-bank modifications from altering historical assessment data.
    """
    __tablename__ = "assessment_item_concept_allocations"
    __table_args__ = (
        UniqueConstraint("assessment_item_id", "concept_id", name="uq_assessment_item_concept"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_item_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assessment_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    marks_available: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    allocation_source: Mapped[str] = mapped_column(
        String(30), default="question_part_mapping", nullable=False
    )  # question_part_mapping | teacher_override

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    assessment_item: Mapped["AssessmentItem"] = relationship("AssessmentItem", back_populates="concept_allocations")
    concept: Mapped["app.modules.knowledge.models.Concept"] = relationship("app.modules.knowledge.models.Concept")


class AssessmentAttempt(Base):
    """
    Student assessment attempt. Server is authoritative for identity, timing, and score.
    """
    __tablename__ = "assessment_attempts"
    __table_args__ = (
        UniqueConstraint("assessment_version_id", "student_membership_id", "attempt_number", name="uq_attempt_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assessment_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_membership_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institution_memberships.id", ondelete="CASCADE"), nullable=False, index=True
    )
    attempt_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="in_progress", nullable=False
    )  # in_progress | submitted | expired | abandoned | invalidated
    scoring_status: Mapped[str] = mapped_column(
        String(20), default="not_scored", nullable=False
    )  # not_scored | scored | partially_scored | grading_pending | scoring_failed
    is_valid: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finalized_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_synced_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    marks_awarded: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    marks_available: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    score_fraction: Mapped[Optional[float]] = mapped_column(Numeric(7, 5), nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    scoring_policy_snapshot: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    invalid_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    faculty_override_marks: Mapped[Optional[float]] = mapped_column(Numeric(10, 2), nullable=True)
    override_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    override_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    assessment_version: Mapped["AssessmentVersion"] = relationship("AssessmentVersion", back_populates="attempts")
    student_membership: Mapped["app.modules.auth.models.InstitutionMembership"] = relationship("app.modules.auth.models.InstitutionMembership")
    responses: Mapped[List["AssessmentResponse"]] = relationship(
        "AssessmentResponse", back_populates="attempt", cascade="all, delete-orphan"
    )
    item_scores: Mapped[List["AssessmentItemScore"]] = relationship(
        "AssessmentItemScore", back_populates="attempt", cascade="all, delete-orphan"
    )
    concept_scores: Mapped[List["AssessmentConceptScore"]] = relationship(
        "AssessmentConceptScore", back_populates="attempt", cascade="all, delete-orphan"
    )


class AssessmentResponse(Base):
    """
    Current server-persisted response projection for one item in an attempt.
    """
    __tablename__ = "assessment_responses"
    __table_args__ = (
        UniqueConstraint("assessment_attempt_id", "assessment_item_id", name="uq_attempt_item_response"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_attempt_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assessment_attempts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_item_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assessment_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    response_payload_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    response_state: Mapped[str] = mapped_column(
        String(25), default="empty", nullable=False
    )  # empty | draft | answered | marked_for_review
    visited_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    first_saved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_saved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    response_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    attempt: Mapped["AssessmentAttempt"] = relationship("AssessmentAttempt", back_populates="responses")
    item: Mapped["AssessmentItem"] = relationship("AssessmentItem")


class AssessmentResponseEvent(Base):
    """
    Append-only log of response events during an assessment attempt.
    """
    __tablename__ = "assessment_response_events"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_attempt_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assessment_attempts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_item_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assessment_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # visited | draft_saved | answer_changed | marked_for_review | unmarked_for_review | submitted
    response_payload_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    client_event_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    server_received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class AssessmentItemScore(Base):
    """
    Server-authoritative item-level scoring result for an attempt.
    """
    __tablename__ = "assessment_item_scores"
    __table_args__ = (
        UniqueConstraint("assessment_attempt_id", "assessment_item_id", name="uq_attempt_item_score"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_attempt_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assessment_attempts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_item_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assessment_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    marks_awarded: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    marks_available: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    result_status: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # correct | incorrect | partially_correct | not_assessed
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    scoring_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    attempt: Mapped["AssessmentAttempt"] = relationship("AssessmentAttempt", back_populates="item_scores")
    item: Mapped["AssessmentItem"] = relationship("AssessmentItem")


class AssessmentConceptScore(Base):
    """
    Canonical concept mark attribution for diagnostic and progress analytics.
    Enforces that multi-concept questions distribute marks without duplication.
    """
    __tablename__ = "assessment_concept_scores"
    __table_args__ = (
        UniqueConstraint("assessment_attempt_id", "assessment_item_id", "concept_id", name="uq_attempt_concept_score"),
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
    assessment_attempt_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assessment_attempts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_item_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assessment_items.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("questions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    marks_awarded: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    marks_available: Mapped[float] = mapped_column(Numeric(8, 2), nullable=False)
    scored_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    attempt: Mapped["AssessmentAttempt"] = relationship("AssessmentAttempt", back_populates="concept_scores")
    concept: Mapped["app.modules.knowledge.models.Concept"] = relationship("app.modules.knowledge.models.Concept")


class StudentLearningNodeProgress(Base):
    """
    Per student and node workflow progress state.
    """
    __tablename__ = "student_learning_node_progress"
    __table_args__ = (
        UniqueConstraint("student_membership_id", "learning_node_id", name="uq_student_node_progress"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_membership_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institution_memberships.id", ondelete="CASCADE"), nullable=False, index=True
    )
    learning_node_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learning_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    progress_status: Mapped[str] = mapped_column(
        String(20), default="available", nullable=False
    )  # locked | available | in_progress | completed | needs_review
    first_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    latest_attempt_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assessment_attempts.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class AssessmentStudentOverride(Base):
    """
    Individual student access schedule overrides, makeup exam authorizations,
    and confirmed absence records for formal assessments.
    """
    __tablename__ = "assessment_student_overrides"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_membership_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institution_memberships.id", ondelete="CASCADE"), nullable=False, index=True
    )
    override_type: Mapped[str] = mapped_column(
        String(30), default="makeup_window", nullable=False
    )  # makeup_window | confirmed_absence
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )  # active | used | superseded | revoked | confirmed
    start_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    granted_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resulting_attempt_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assessment_attempts.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    assessment: Mapped["Assessment"] = relationship("Assessment")
    student_membership: Mapped["app.modules.auth.models.InstitutionMembership"] = relationship("app.modules.auth.models.InstitutionMembership")
    resulting_attempt: Mapped[Optional["AssessmentAttempt"]] = relationship("AssessmentAttempt")

