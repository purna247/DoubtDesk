from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


class MisconceptionCreate(BaseModel):
    concept_id: UUID
    code: str = Field(..., min_length=2, max_length=50)
    label: str = Field(..., min_length=2)
    description: str = Field(..., min_length=2)


class MisconceptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institution_id: UUID
    concept_id: UUID
    code: str
    label: str
    description: str
    created_at: datetime


class OptionCreate(BaseModel):
    option_key: str = Field(..., min_length=1, max_length=10)
    display_text: str = Field(..., min_length=1)
    sequence_no: int = 1
    is_correct: bool = False
    misconception_id: Optional[UUID] = None


class OptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    option_key: str
    display_text: str
    sequence_no: int
    is_correct: bool
    misconception_id: Optional[UUID] = None


class ConceptAllocationCreate(BaseModel):
    concept_id: UUID
    allocated_marks: float = Field(..., gt=0.0)
    allocation_note: Optional[str] = None


class ConceptAllocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    question_part_id: UUID
    concept_id: UUID
    allocated_marks: float
    allocation_note: Optional[str] = None


class QuestionPartCreate(BaseModel):
    part_key: str = Field("A", min_length=1, max_length=20)
    part_prompt: str = Field(..., min_length=1)
    sequence_no: int = 1
    marks_available: float = Field(1.0, gt=0.0)
    answer_type: str = Field("mcq", pattern="^(mcq|fill_blank|matching_pairs|ordering|classification|key_points_check|descriptive)$")
    expected_answer_depth: Optional[str] = None
    options: List[OptionCreate] = []
    concept_allocations: List[ConceptAllocationCreate] = []

    @model_validator(mode="after")
    def validate_part_allocations(self) -> QuestionPartCreate:
        if self.concept_allocations:
            alloc_sum = sum(a.allocated_marks for a in self.concept_allocations)
            if round(alloc_sum, 2) != round(self.marks_available, 2):
                raise ValueError(
                    f"Sum of concept allocations ({alloc_sum}) must equal part marks available ({self.marks_available})"
                )
        return self


class QuestionPartOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    part_key: str
    part_prompt: str
    sequence_no: int
    marks_available: float
    answer_type: str
    expected_answer_depth: Optional[str] = None
    options: List[OptionOut] = []
    concept_allocations: List[ConceptAllocationOut] = []


class QuestionVersionCreate(BaseModel):
    prompt_text: str = Field(..., min_length=3)
    question_type: str = Field("mcq", pattern="^(mcq|fill_blank|matching_pairs|ordering|classification|key_points_check|descriptive)$")
    command_verb: Optional[str] = None
    expected_answer_depth: Optional[str] = None
    marks_total: float = Field(1.0, gt=0.0)
    difficulty_level: str = Field("medium", pattern="^(very_easy|easy|medium|hard|very_hard|unrated)$")
    cognitive_level: Optional[str] = Field("understand", pattern="^(remember|understand|apply|analyze|evaluate|create)$")
    marking_guidance: Optional[str] = None
    parts: List[QuestionPartCreate] = []
    learning_objective_ids: List[UUID] = []
    source_chunk_id: Optional[UUID] = None

    @model_validator(mode="after")
    def validate_version_parts_sum(self) -> QuestionVersionCreate:
        if self.parts:
            parts_sum = sum(p.marks_available for p in self.parts)
            if round(parts_sum, 2) != round(self.marks_total, 2):
                raise ValueError(
                    f"Sum of part marks ({parts_sum}) must equal question marks total ({self.marks_total})"
                )
        return self


class QuestionVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institution_id: UUID
    question_id: UUID
    version_number: int
    prompt_text: str
    question_type: str
    command_verb: Optional[str] = None
    expected_answer_depth: Optional[str] = None
    marks_total: float
    difficulty_level: str
    cognitive_level: Optional[str] = None
    approval_status: str
    created_by_user_id: Optional[UUID] = None
    reviewed_by_user_id: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    rejection_reason: Optional[str] = None
    marking_guidance: Optional[str] = None
    source_chunk_ids: List[UUID] = []
    created_at: datetime
    parts: List[QuestionPartOut] = []


class QuestionCreate(BaseModel):
    origin_type: str = Field("teacher_authored", pattern="^(original_exam|teacher_authored|imported|ai_supplementary)$")
    is_ai_generated: bool = False
    course_offering_id: Optional[UUID] = None
    version: QuestionVersionCreate


class QuestionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institution_id: UUID
    created_by_user_id: Optional[UUID] = None
    origin_type: str
    lifecycle_status: str
    is_ai_generated: bool
    created_at: datetime
    updated_at: datetime
    latest_version: Optional[QuestionVersionOut] = None


class QuestionReviewRequest(BaseModel):
    approval_status: str = Field(..., pattern="^(approved|rejected)$")
    rejection_reason: Optional[str] = None


class QuestionRelationshipCreate(BaseModel):
    target_question_id: UUID
    relationship_type: str = Field(
        ...,
        pattern="^(related|possible_near_duplicate|variant_of|broader_requirement|narrower_requirement|prerequisite_for|same_learning_objective)$"
    )
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)


class QuestionRelationshipOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institution_id: UUID
    source_question_id: UUID
    target_question_id: UUID
    relationship_type: str
    confidence: Optional[float] = None
    review_status: str
    created_at: datetime


class QuestionCoverageEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institution_id: UUID
    course_offering_id: UUID
    question_id: UUID
    event_type: str
    actor_user_id: Optional[UUID] = None
    details_json: Optional[Dict[str, Any]] = None
    created_at: datetime


class CourseQuestionCoverageReport(BaseModel):
    course_offering_id: UUID
    total_questions: int
    extracted_count: int
    concept_mapped_count: int
    approved_count: int
    assessment_included_count: int

