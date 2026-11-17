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


class Intervention(Base):
    """
    Teacher-curated targeted learning intervention.
    Enforces sequential Phase A (baseline) -> Phase B (primer/practice) -> Phase C (reassessment) gating.
    """
    __tablename__ = "interventions"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_offering_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(30), default="draft", nullable=False
    )  # draft | pending_approval | approved | published | active | completed | archived | cancelled
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    assignment_starts_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    assignment_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Phase A Baseline Assessment
    phase_a_assessment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="SET NULL"), nullable=True
    )

    # Phase B Primer and Practice
    phase_b_primer_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phase_b_practice_assessment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="SET NULL"), nullable=True
    )
    phase_b_completion_rule: Mapped[str] = mapped_column(
        String(50), default="all_required_items", nullable=False
    )  # all_required_items | designated_core_items | minimum_count
    phase_b_required_count: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    require_primer_acknowledgment: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Phase C Post Assessment (Must be strictly disjoint from Phase A)
    phase_c_assessment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assessments.id", ondelete="SET NULL"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    concepts: Mapped[List["InterventionConcept"]] = relationship(
        "InterventionConcept", back_populates="intervention", cascade="all, delete-orphan"
    )
    assignments: Mapped[List["InterventionAssignment"]] = relationship(
        "InterventionAssignment", back_populates="intervention", cascade="all, delete-orphan"
    )
    phase_a_assessment: Mapped[Optional["app.modules.assessments.models.Assessment"]] = relationship(
        "app.modules.assessments.models.Assessment", foreign_keys=[phase_a_assessment_id]
    )
    phase_b_practice_assessment: Mapped[Optional["app.modules.assessments.models.Assessment"]] = relationship(
        "app.modules.assessments.models.Assessment", foreign_keys=[phase_b_practice_assessment_id]
    )
    phase_c_assessment: Mapped[Optional["app.modules.assessments.models.Assessment"]] = relationship(
        "app.modules.assessments.models.Assessment", foreign_keys=[phase_c_assessment_id]
    )


class InterventionConcept(Base):
    """
    Binding of target learning concepts to an intervention.
    """
    __tablename__ = "intervention_concepts"
    __table_args__ = (
        UniqueConstraint("intervention_id", "concept_id", name="uq_intervention_concept"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    intervention_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("interventions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    intervention: Mapped["Intervention"] = relationship("Intervention", back_populates="concepts")
    concept: Mapped["app.modules.knowledge.models.Concept"] = relationship("app.modules.knowledge.models.Concept")


class InterventionAssignment(Base):
    """
    Per-student tracking across the three-phase intervention lifecycle.
    """
    __tablename__ = "intervention_assignments"
    __table_args__ = (
        UniqueConstraint("intervention_id", "student_membership_id", name="uq_intervention_student_assignment"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    intervention_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("interventions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_membership_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institution_memberships.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_evidence_status: Mapped[str] = mapped_column(
        String(40), default="confirmed_weakness", nullable=False
    )  # confirmed_weakness | candidate_weakness | manual_teacher_selection
    assignment_status: Mapped[str] = mapped_column(
        String(30), default="assigned", nullable=False
    )  # assigned | phase_a_in_progress | phase_a_completed | phase_b_in_progress | phase_b_completed | phase_c_in_progress | completed | exempted | expired

    # Phase A tracking
    phase_a_attempt_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assessment_attempts.id", ondelete="SET NULL"), nullable=True
    )
    phase_a_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    phase_a_score: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)

    # Phase B tracking
    phase_b_primer_acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    phase_b_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    phase_b_items_completed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Phase C tracking
    phase_c_attempt_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("assessment_attempts.id", ondelete="SET NULL"), nullable=True
    )
    phase_c_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    phase_c_score: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)

    # Matched comparison outcomes
    observed_score_change: Mapped[Optional[float]] = mapped_column(Numeric(8, 2), nullable=True)
    outcome_status: Mapped[Optional[str]] = mapped_column(
        String(30), nullable=True
    )  # improved | unchanged | declined | incomplete

    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    intervention: Mapped["Intervention"] = relationship("Intervention", back_populates="assignments")
    student_membership: Mapped["app.modules.auth.models.InstitutionMembership"] = relationship("app.modules.auth.models.InstitutionMembership")

