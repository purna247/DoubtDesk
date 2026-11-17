"""Teacher-only editable drafts, independent of published assessment records."""
from collections import Counter
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.modules.assessments.schemas import QuizQuestionIn


class DraftQuestion(QuizQuestionIn):
    options: list[str] = Field(min_length=2, max_length=6)
    statement: str = Field(min_length=3, max_length=5000)
    marks: float = Field(default=1, gt=0, le=100, allow_inf_nan=False)

    @model_validator(mode="after")
    def validate_options(self):
        options = [option.strip().casefold() for option in self.options]
        if not all(options) or len(set(options)) != len(options):
            raise ValueError("Answer options must be nonempty and distinct.")
        if self.correct_index >= len(self.options):
            raise ValueError("Choose a valid correct answer.")
        if not self.statement.strip():
            raise ValueError("Question text is required.")
        return self


class DraftSource(BaseModel):
    source_chunk_id: UUID
    source_document_id: UUID
    filename: str
    page: int | None = None
    slide: int | None = None
    text: str


class InterventionDraft(BaseModel):
    concept_id: UUID
    title: str = Field(min_length=3, max_length=255)
    study_guide: str = Field(min_length=1, max_length=30000)
    baseline: list[DraftQuestion] = Field(min_length=1, max_length=10)
    reassessment: list[DraftQuestion] = Field(min_length=1, max_length=10)
    practice: list[DraftQuestion] = Field(default_factory=list, max_length=10)
    sources: list[DraftSource] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def validate_matched_pair(self):
        if not self.title.strip() or not self.study_guide.strip():
            raise ValueError("Title and study guide are required.")
        def profile(questions):
            return Counter((q.marks, q.difficulty_level, q.cognitive_level) for q in questions)
        if profile(self.baseline) != profile(self.reassessment):
            raise ValueError("Baseline and reassessment must match in marks, difficulty and cognitive level.")
        prompts = [" ".join(q.statement.casefold().split()) for q in self.baseline + self.reassessment]
        if len(set(prompts)) != len(prompts):
            raise ValueError("Use distinct questions in the baseline and reassessment.")
        return self


class GenerateInterventionRequest(BaseModel):
    concept_id: UUID
    question_count: int = Field(default=3, ge=1, le=5)
    include_practice: bool = False
    difficulty: Literal["easy", "medium", "hard"] = "medium"


class ApproveInterventionDraft(InterventionDraft):
    student_membership_ids: list[UUID] = Field(min_length=1)
