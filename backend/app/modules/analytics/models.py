from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String,
    Text,
    Boolean,
    Integer,
    Numeric,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class CourseAnalyticsPolicy(Base):
    """
    Configurable diagnostic analytics thresholds and attempt policy.
    Supports institution-wide defaults and optional course-offering overrides.
    """
    __tablename__ = "course_analytics_policies"
    __table_args__ = (
        UniqueConstraint("institution_id", "course_offering_id", name="uq_institution_offering_analytics_policy"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_offering_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=True, index=True
    )
    min_distinct_questions: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    weakness_accuracy_threshold: Mapped[float] = mapped_column(Numeric(5, 4), default=0.6000, nullable=False)
    diagnostic_attempt_policy: Mapped[str] = mapped_column(
        String(50), default="first_valid_submitted_scored", nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    effective_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class MisconceptionEvent(Base):
    """
    Append-only event created when a student selects an option with an approved misconception tag.
    """
    __tablename__ = "misconception_events"
    __table_args__ = (
        UniqueConstraint("assessment_response_id", "selected_option_id", "misconception_id", name="uq_resp_opt_misconception"),
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
    assessment_response_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assessment_responses.id", ondelete="CASCADE"), nullable=True, index=True
    )
    selected_option_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("question_part_options.id", ondelete="CASCADE"), nullable=False, index=True
    )
    misconception_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("misconceptions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_membership_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institution_memberships.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_offering_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    misconception: Mapped["app.modules.questions.models.Misconception"] = relationship("app.modules.questions.models.Misconception")


class AnalyticsRun(Base):
    """
    Execution run metadata for rebuildable concept and cohort analytics snapshots.
    """
    __tablename__ = "analytics_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_offering_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    policy_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("course_analytics_policies.id", ondelete="SET NULL"), nullable=True
    )
    run_type: Mapped[str] = mapped_column(
        String(30), default="manual", nullable=False
    )  # manual | scheduled | event_triggered
    status: Mapped[str] = mapped_column(
        String(20), default="completed", nullable=False
    )  # pending | running | completed | failed
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    source_watermark: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    student_snapshots: Mapped[List["StudentConceptEvidenceSnapshot"]] = relationship(
        "StudentConceptEvidenceSnapshot", back_populates="analytics_run", cascade="all, delete-orphan"
    )
    cohort_snapshots: Mapped[List["CohortConceptAnalytics"]] = relationship(
        "CohortConceptAnalytics", back_populates="analytics_run", cascade="all, delete-orphan"
    )


class StudentConceptEvidenceSnapshot(Base):
    """
    Derived snapshot of a student's concept accuracy and diagnostic status.
    Authoritative evidence remains in assessment attempts and score tables.
    """
    __tablename__ = "student_concept_evidence_snapshots"
    __table_args__ = (
        UniqueConstraint("analytics_run_id", "student_membership_id", "concept_id", name="uq_run_student_concept_snapshot"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analytics_run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("analytics_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_offering_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_membership_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institution_memberships.id", ondelete="CASCADE"), nullable=False, index=True
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    distinct_question_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    awarded_marks: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    available_marks: Mapped[float] = mapped_column(Numeric(10, 2), default=0.0, nullable=False)
    accuracy: Mapped[Optional[float]] = mapped_column(Numeric(7, 5), nullable=True)
    diagnostic_status: Mapped[str] = mapped_column(
        String(40), default="insufficient_evidence", nullable=False
    )  # insufficient_evidence | candidate_weakness | confirmed_weakness | not_currently_flagged_as_weak
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    analytics_run: Mapped["AnalyticsRun"] = relationship("AnalyticsRun", back_populates="student_snapshots")
    concept: Mapped["app.modules.knowledge.models.Concept"] = relationship("app.modules.knowledge.models.Concept")


class CohortConceptAnalytics(Base):
    """
    Derived cohort-level summary of concept mastery, gaps, and accuracies.
    Preserves both Cohort Mean Accuracy and Cohort Pooled Accuracy.
    """
    __tablename__ = "cohort_concept_analytics"
    __table_args__ = (
        UniqueConstraint("analytics_run_id", "concept_id", name="uq_run_concept_cohort_analytics"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    analytics_run_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("analytics_runs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_offering_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    enrolled_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    assessed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    confirmed_weak_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    candidate_weak_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    insufficient_evidence_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    cohort_mean_accuracy: Mapped[Optional[float]] = mapped_column(Numeric(7, 5), nullable=True)
    cohort_pooled_accuracy: Mapped[Optional[float]] = mapped_column(Numeric(7, 5), nullable=True)
    tagged_misconception_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    analytics_run: Mapped["AnalyticsRun"] = relationship("AnalyticsRun", back_populates="cohort_snapshots")
    concept: Mapped["app.modules.knowledge.models.Concept"] = relationship("app.modules.knowledge.models.Concept")


class ConceptMasteryPolicy(Base):
    """
    Teacher-configured criteria for determining concept mastery.
    Decoupled from weakness classification.
    """
    __tablename__ = "concept_mastery_policies"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_offering_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    policy_name: Mapped[str] = mapped_column(String(100), nullable=False)
    criteria_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )  # draft | active | retired
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


class StudentConceptMasteryEvaluation(Base):
    """
    Result of evaluating a student's concept performance against a specific mastery policy.
    """
    __tablename__ = "student_concept_mastery_evaluations"
    __table_args__ = (
        UniqueConstraint("student_membership_id", "concept_id", "mastery_policy_id", name="uq_student_concept_mastery_eval"),
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
    course_offering_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    mastery_policy_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("concept_mastery_policies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(30), default="not_evaluated", nullable=False
    )  # not_evaluated | pending_review | mastered | not_mastered
    evidence_summary_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    evaluated_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

