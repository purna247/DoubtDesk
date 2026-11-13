from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


class LearningNodePrerequisiteCreate(BaseModel):
    prerequisite_node_id: UUID
    prerequisite_type: str = Field("required", pattern="^(required|recommended)$")


class LearningNodePrerequisiteOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    learning_node_id: UUID
    prerequisite_node_id: UUID
    prerequisite_type: str
    created_at: datetime


class LearningNodeCreate(BaseModel):
    node_code: Optional[str] = Field(None, max_length=50)
    module_title: Optional[str] = Field(None, max_length=255)
    difficulty_rank: Optional[int] = Field(None, ge=1, le=1000)
    title: str = Field(..., min_length=2, max_length=255)
    description: Optional[str] = None
    sequence_no: int = 1
    completion_rule_json: Optional[Dict[str, Any]] = None
    concept_ids: List[UUID] = []
    prerequisite_node_ids: List[UUID] = []


class LearningNodeUpdate(BaseModel):
    node_code: Optional[str] = Field(None, max_length=50)
    title: Optional[str] = Field(None, min_length=2, max_length=255)
    description: Optional[str] = None
    sequence_no: Optional[int] = None
    completion_rule_json: Optional[Dict[str, Any]] = None
    expected_revision: Optional[int] = Field(None, ge=1)


class LearningNodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institution_id: UUID
    course_offering_id: UUID
    course_content_version_id: UUID
    node_code: Optional[str] = None
    module_title: Optional[str] = None
    difficulty_rank: Optional[int] = None
    title: str
    description: Optional[str] = None
    sequence_no: int
    revision: int = 1
    status: str
    completion_rule_json: Optional[Dict[str, Any]] = None
    created_by_user_id: Optional[UUID] = None
    published_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    concept_ids: List[UUID] = []
    prerequisite_node_ids: List[UUID] = []
    is_unlocked: Optional[bool] = None
    progress_status: Optional[str] = None
    question_count: int = 0
    practice_summary: Optional[Dict[str, Any]] = None


class ActivityCreate(BaseModel):
    question_id: Optional[UUID] = None
    activity_type: str = Field(
        ...,
        pattern="^(mcq|fill_blank|matching_pairs|ordering|classification|key_points_check)$"
    )
    title: str = Field(..., min_length=2, max_length=255)
    instructions: Optional[str] = None
    authoring_payload: Dict[str, Any]
    scoring_config: Optional[Dict[str, Any]] = None


class ActivityVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institution_id: UUID
    activity_id: UUID
    version_number: int
    activity_type: str
    schema_version: int
    title: str
    instructions: Optional[str] = None
    student_payload_json: Dict[str, Any]
    answer_key_json: Optional[Dict[str, Any]] = None  # Populated only for teacher views
    scoring_config_json: Dict[str, Any]
    approval_status: str
    created_at: datetime


class ActivityOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institution_id: UUID
    learning_node_id: UUID
    question_id: Optional[UUID] = None
    status: str
    created_at: datetime
    latest_version: Optional[ActivityVersionOut] = None


class ActivityEvaluateRequest(BaseModel):
    response_data: Dict[str, Any]


class CourseLearningMapResponse(BaseModel):
    course_offering_id: UUID
    course_content_version_id: UUID
    nodes: List[LearningNodeOut]


class PracticeQuestionOut(BaseModel):
    activity_version_id: UUID
    title: str
    question: str
    activity_type: str = "mcq"
    options: List[Dict[str, str]] = Field(default_factory=list)
    payload: Dict[str, Any] = Field(default_factory=dict)
    difficulty: str
    is_remediation: bool = False
    has_hint: bool = True
    citation: Optional[str] = None


class PracticeSessionStateOut(BaseModel):
    id: UUID
    learning_node_id: UUID
    status: str
    current_difficulty: str
    in_remediation: bool
    target_correct_count: int
    questions_answered: int
    correct_count: int
    mistake_count: int
    consecutive_mistakes: int
    easier_followups_triggered: int
    hints_used: int
    recovered_after_mistake_count: int
    repeated_mistakes: bool = False
    needs_easier_questions: bool = False
    improving: bool = False


class PracticeSessionStartOut(BaseModel):
    node_id: UUID
    node_title: str
    module_title: Optional[str] = None
    session: PracticeSessionStateOut
    current_question: Optional[PracticeQuestionOut] = None


class PracticeHintOut(BaseModel):
    hint: str
    hints_used: int


class PracticeAnswerRequest(BaseModel):
    activity_version_id: UUID
    selected_option_id: Optional[str] = Field(default=None, max_length=120)
    text_answer: Optional[str] = Field(default=None, max_length=500)
    answers: Optional[Dict[str, str]] = None
    pairs: Optional[List[Dict[str, str]]] = None
    order: Optional[List[str]] = None
    classifications: Optional[Dict[str, str]] = None


class PracticeAnswerResultOut(BaseModel):
    is_correct: bool
    correct_option_id: Optional[str] = None
    explanation: str
    feedback_summary: str
    citation: Optional[str] = None
    node_completed: bool
    session: PracticeSessionStateOut
    next_question: Optional[PracticeQuestionOut] = None


