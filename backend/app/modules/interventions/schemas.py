from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class InterventionConceptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    concept_id: uuid.UUID
    canonical_name: Optional[str] = None
    concept_code: Optional[str] = None
    target_notes: Optional[str] = None


class InterventionCreate(BaseModel):
    title: str = Field(..., min_length=3, max_length=255)
    description: Optional[str] = None
    concept_ids: List[uuid.UUID] = Field(..., min_length=1)
    student_membership_ids: List[uuid.UUID] = Field(..., min_length=1)
    phase_a_assessment_id: uuid.UUID
    phase_b_primer_content: Optional[str] = None
    phase_b_practice_assessment_id: uuid.UUID
    phase_b_completion_rule: str = Field(
        "all_required_items",
        pattern="^(all_required_items|designated_core_items|minimum_count)$",
    )
    phase_b_required_count: Optional[int] = Field(None, ge=1)
    phase_c_assessment_id: uuid.UUID
    assignment_starts_at: Optional[datetime] = None
    assignment_ends_at: Optional[datetime] = None


class InterventionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    institution_id: uuid.UUID
    course_offering_id: uuid.UUID
    title: str
    description: Optional[str] = None
    status: str
    phase_a_assessment_id: Optional[uuid.UUID] = None
    phase_b_primer_content: Optional[str] = None
    phase_b_practice_assessment_id: Optional[uuid.UUID] = None
    phase_b_completion_rule: str
    phase_b_required_count: Optional[int] = None
    phase_c_assessment_id: Optional[uuid.UUID] = None
    approved_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    target_concepts: List[InterventionConceptOut] = []
    assigned_students_count: int = 0


class InterventionAssignmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    intervention_id: uuid.UUID
    student_membership_id: uuid.UUID
    student_name: Optional[str] = None
    target_evidence_status: str
    assignment_status: str
    phase_a_completed_at: Optional[datetime] = None
    phase_a_score: Optional[float] = None
    phase_b_completed_at: Optional[datetime] = None
    phase_b_items_completed_count: int = 0
    phase_c_completed_at: Optional[datetime] = None
    phase_c_score: Optional[float] = None
    observed_score_change: Optional[float] = None
    outcome_status: Optional[str] = None
    assigned_at: datetime


class StudentInterventionViewOut(BaseModel):
    intervention_id: uuid.UUID
    title: str
    description: Optional[str] = None
    current_phase: str  # phase_a | phase_b | phase_c | completed
    # Phase A status
    phase_a_unlocked: bool
    phase_a_completed: bool
    phase_a_assessment_id: Optional[uuid.UUID] = None
    phase_a_score: Optional[float] = None
    # Phase B status
    phase_b_unlocked: bool
    phase_b_completed: bool
    phase_b_primer_content: Optional[str] = None
    phase_b_practice_assessment_id: Optional[uuid.UUID] = None
    phase_b_items_completed: int
    phase_b_rule_description: str
    # Phase C status
    phase_c_unlocked: bool
    phase_c_completed: bool
    phase_c_assessment_id: Optional[uuid.UUID] = None
    phase_c_score: Optional[float] = None
    # Outcome
    observed_score_change: Optional[float] = None
    outcome_status: Optional[str] = None


class StudentInterventionListOut(StudentInterventionViewOut):
    course_offering_id: uuid.UUID


class InterventionReportOut(BaseModel):
    intervention_id: uuid.UUID
    title: str
    status: str
    total_assigned_count: int
    phase_a_completed_count: int
    phase_b_completed_count: int
    phase_c_completed_count: int
    matched_completed_count: int
    improved_count: int
    unchanged_count: int
    declined_count: int
    incomplete_count: int
    average_phase_a_score: Optional[float] = None
    average_phase_c_score: Optional[float] = None
    average_observed_change: Optional[float] = None
    disclaimer: str = (
        "Observed pre/post score change across matched student completions. "
        "Does not constitute causal evidence of mastery or intervention impact."
    )
    assignments: List[InterventionAssignmentOut] = []

