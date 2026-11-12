from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class ConceptAllocationIn(BaseModel):
    concept_id: UUID
    marks_available: float = Field(..., gt=0.0)


class ConceptAllocationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    concept_id: UUID
    marks_available: float


class StudentQuestionOptionOut(BaseModel):
    id: UUID
    option_key: str
    display_text: str


class StudentQuestionPartOut(BaseModel):
    id: UUID
    part_key: str
    part_prompt: str
    sequence_no: int
    marks_available: float
    answer_type: str
    options: List[StudentQuestionOptionOut] = []


class AssessmentItemCreate(BaseModel):
    question_version_id: Optional[UUID] = None
    activity_version_id: Optional[UUID] = None
    sequence_no: int = Field(..., ge=1)
    marks_available: float = Field(..., gt=0.0)
    is_required: bool = True
    concept_allocations: List[ConceptAllocationIn] = []


class AssessmentItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sequence_no: int
    marks_available: float
    is_required: bool
    question_version_id: Optional[UUID] = None
    activity_version_id: Optional[UUID] = None
    activity_type: Optional[str] = None
    title: Optional[str] = None
    student_payload_json: Optional[Dict[str, Any]] = None
    answer_key_json: Optional[Dict[str, Any]] = None
    question_prompt: Optional[str] = None
    question_parts: List[StudentQuestionPartOut] = []
    concept_allocations: List[ConceptAllocationOut] = []


class AssessmentVersionCreate(BaseModel):
    duration_seconds: Optional[int] = Field(None, ge=1)
    max_attempts: Optional[int] = Field(None, ge=1)
    items: List[AssessmentItemCreate] = Field(..., min_length=1)


class AssessmentVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    assessment_id: UUID
    version_number: int
    status: str
    duration_seconds: Optional[int] = None
    max_attempts: Optional[int] = None
    published_at: Optional[datetime] = None
    created_at: datetime
    items: List[AssessmentItemOut] = []


class AssessmentCreate(BaseModel):
    learning_node_id: Optional[UUID] = None
    assessment_type: str = Field(
        "node_practice",
        pattern="^(node_practice|boss|intervention_baseline|intervention_practice|intervention_post)$"
    )
    title: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    version: AssessmentVersionCreate


class AssessmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institution_id: UUID
    course_offering_id: UUID
    learning_node_id: Optional[UUID] = None
    assessment_type: str
    title: str
    description: Optional[str] = None
    status: str
    created_at: datetime
    latest_version: Optional[AssessmentVersionOut] = None


class StartAttemptResponse(BaseModel):
    attempt_id: UUID
    assessment_version_id: UUID
    attempt_number: int
    status: str
    started_at: datetime
    expires_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    items: List[AssessmentItemOut]
    saved_responses: Dict[str, Dict[str, Any]] = {}


class SaveResponseRequest(BaseModel):
    item_id: UUID
    response_payload: Dict[str, Any]
    response_state: str = Field("answered", pattern="^(empty|draft|answered|marked_for_review)$")
    client_event_id: Optional[str] = None


class SubmitAttemptRequest(BaseModel):
    idempotency_key: Optional[str] = None


class ItemScoreOut(BaseModel):
    item_id: UUID
    sequence_no: int
    marks_awarded: float
    marks_available: float
    result_status: str
    selected_option_id: Optional[str] = None
    correct_option_id: Optional[str] = None
    explanation: Optional[str] = None


class ConceptScoreOut(BaseModel):
    concept_id: UUID
    marks_awarded: float
    marks_available: float


class AttemptSummaryOut(BaseModel):
    attempt_id: UUID
    assessment_version_id: UUID
    attempt_number: int
    status: str
    scoring_status: str
    is_valid: bool
    started_at: datetime
    expires_at: Optional[datetime] = None
    submitted_at: Optional[datetime] = None
    finalized_at: Optional[datetime] = None
    marks_awarded: Optional[float] = None
    marks_available: Optional[float] = None
    score_fraction: Optional[float] = None
    item_scores: List[ItemScoreOut] = []
    concept_scores: List[ConceptScoreOut] = []


class QuizQuestionIn(BaseModel):
    statement: str = Field(..., min_length=1)
    options: List[str] = Field(..., min_length=2)
    correct_index: int = Field(..., ge=0)
    explanation: Optional[str] = None
    marks: float = Field(2.0, gt=0.0)
    source_chunk_ids: List[UUID] = []
    concept_ids: List[UUID] = []
    origin_type: str = Field("teacher_authored", pattern="^(teacher_authored|ai_supplementary)$")


class QuizCreateRequest(BaseModel):
    title: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    time_limit_minutes: int = Field(15, ge=1, le=300)
    publish: bool = True
    questions: List[QuizQuestionIn] = Field(..., min_length=1)


class QuizAiGenerateRequest(BaseModel):
    topic: str = Field(..., min_length=2, max_length=255)
    question_count: int = Field(5, ge=1, le=15)
    difficulty: str = Field("Intermediate", min_length=2, max_length=50)


class QuizAiQuestionOut(BaseModel):
    statement: str
    options: List[str]
    correct_index: int
    explanation: str
    marks: float = 2.0
    source_chunk_ids: List[UUID] = []
    concept_ids: List[UUID] = []


class QuizAiSourceOut(BaseModel):
    source_document_id: UUID
    source_chunk_id: UUID
    filename: str
    page_number: Optional[int] = None
    slide_number: Optional[int] = None


class QuizAiGenerateResponse(BaseModel):
    title: str
    description: str
    questions: List[QuizAiQuestionOut]
    sources: List[QuizAiSourceOut] = []


class CourseAssessmentActivityOut(BaseModel):
    attempt_id: UUID
    student_membership_id: UUID
    student_name: str
    assessment_id: UUID
    assessment_title: str
    assessment_type: str
    status: str
    scoring_status: str
    marks_awarded: Optional[float] = None
    marks_available: Optional[float] = None
    started_at: datetime
    submitted_at: Optional[datetime] = None
