from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, ConfigDict, Field


class CourseAnalyticsPolicyBase(BaseModel):
    min_distinct_questions: int = Field(3, ge=1, le=50)
    weakness_accuracy_threshold: float = Field(0.60, ge=0.0, le=1.0)
    diagnostic_attempt_policy: str = Field("first_valid_submitted_scored", pattern="^(first_valid_submitted_scored)$")
    is_active: bool = True


class CourseAnalyticsPolicyCreate(CourseAnalyticsPolicyBase):
    course_offering_id: Optional[uuid.UUID] = None


class CourseAnalyticsPolicyUpdate(BaseModel):
    min_distinct_questions: Optional[int] = Field(None, ge=1, le=50)
    weakness_accuracy_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    is_active: Optional[bool] = None


class CourseAnalyticsPolicyOut(CourseAnalyticsPolicyBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    institution_id: uuid.UUID
    course_offering_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime


class StudentConceptEvidenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    student_membership_id: uuid.UUID
    student_name: Optional[str] = None
    student_reg_number: Optional[str] = None
    concept_id: uuid.UUID
    concept_name: Optional[str] = None
    distinct_question_count: int
    awarded_marks: float
    available_marks: float
    accuracy: Optional[float] = None
    diagnostic_status: str  # insufficient_evidence | candidate_weakness | confirmed_weakness | not_currently_flagged_as_weak
    computed_at: datetime


class CohortConceptAnalyticsOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    concept_id: uuid.UUID
    concept_code: Optional[str] = None
    concept_name: Optional[str] = None
    enrolled_count: int
    assessed_count: int
    confirmed_weak_count: int
    candidate_weak_count: int
    insufficient_evidence_count: int
    cohort_mean_accuracy: Optional[float] = None
    cohort_pooled_accuracy: Optional[float] = None
    tagged_misconception_count: int
    computed_at: datetime


class SupportingQuestionEvidenceOut(BaseModel):
    item_id: uuid.UUID
    question_or_activity_id: Optional[uuid.UUID] = None
    assessment_id: uuid.UUID
    assessment_title: str
    attempt_id: uuid.UUID
    attempt_number: int
    submitted_at: datetime
    marks_awarded: float
    marks_available: float
    is_diagnostic: bool


class StudentConceptDetailOut(StudentConceptEvidenceOut):
    supporting_evidence: List[SupportingQuestionEvidenceOut] = []


class ConceptAnalyticsDetailOut(BaseModel):
    concept: CohortConceptAnalyticsOut
    policy: CourseAnalyticsPolicyOut
    students: List[StudentConceptDetailOut]


class MisconceptionFrequencyItemOut(BaseModel):
    misconception_id: uuid.UUID
    code: str
    description: str
    concept_id: uuid.UUID
    concept_title: Optional[str] = None
    occurrence_count: int


class MisconceptionReportOut(BaseModel):
    course_offering_id: uuid.UUID
    total_events: int
    misconceptions: List[MisconceptionFrequencyItemOut]


class ConceptMasteryPolicyCreate(BaseModel):
    policy_name: str = Field(..., min_length=2, max_length=100)
    criteria_json: Dict[str, Any]


class ConceptMasteryPolicyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    institution_id: uuid.UUID
    course_offering_id: uuid.UUID
    policy_name: str
    criteria_json: Dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime


class StudentConceptMasteryEvaluationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    student_membership_id: uuid.UUID
    course_offering_id: uuid.UUID
    concept_id: uuid.UUID
    mastery_policy_id: uuid.UUID
    status: str
    evidence_summary_json: Optional[Dict[str, Any]] = None
    evaluated_at: datetime

