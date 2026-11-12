from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


class AuthorPublicOut(BaseModel):
    user_id: Optional[uuid.UUID] = None
    display_name: str
    avatar_url: Optional[str] = None
    role_label: str
    is_anonymous: bool = False


class DoubtCreate(BaseModel):
    course_offering_id: Optional[uuid.UUID] = None
    canonical_subject_id: Optional[uuid.UUID] = None
    concept_id: Optional[uuid.UUID] = None
    question_id: Optional[uuid.UUID] = None
    title: str = Field(..., min_length=3, max_length=255)
    body_markdown: str = Field(..., min_length=5)
    is_anonymous_to_peers: bool = False
    visibility: str = Field("course", pattern="^(institution|course|restricted)$")


class DoubtCommentCreate(BaseModel):
    answer_id: Optional[uuid.UUID] = None
    body_markdown: str = Field(..., min_length=2)


class DoubtCommentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    doubt_id: uuid.UUID
    answer_id: Optional[uuid.UUID] = None
    author: AuthorPublicOut
    body_markdown: str
    created_at: datetime


class DoubtAnswerCreate(BaseModel):
    body_markdown: str = Field(..., min_length=2)


class DoubtAnswerOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    doubt_id: uuid.UUID
    author: AuthorPublicOut
    body_markdown: str
    is_teacher_verified: bool
    verified_at: Optional[datetime] = None
    upvote_count: int
    has_thanked: bool = False
    created_at: datetime
    comments: List[DoubtCommentOut] = []


class DoubtOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    institution_id: uuid.UUID
    course_offering_id: Optional[uuid.UUID] = None
    canonical_subject_id: Optional[uuid.UUID] = None
    concept_id: Optional[uuid.UUID] = None
    concept_name: Optional[str] = None
    title: str
    body_markdown: str
    is_anonymous_to_peers: bool
    author: AuthorPublicOut
    status: str
    visibility: str
    upvote_count: int
    answer_count: int
    created_at: datetime
    updated_at: datetime
    answers: List[DoubtAnswerOut] = []
    comments: List[DoubtCommentOut] = []


class DoubtFlagCreate(BaseModel):
    reason_code: str = Field(..., min_length=2, max_length=50)
    details: Optional[str] = None


class DoubtFlagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    doubt_id: uuid.UUID
    reported_by_user_id: uuid.UUID
    reason_code: str
    details: Optional[str] = None
    status: str
    created_at: datetime


class DoubtUnmaskRequest(BaseModel):
    reason_code: str = Field(..., min_length=2, max_length=50)
    reason_text: str = Field(..., min_length=5)


class DoubtUnmaskOut(BaseModel):
    doubt_id: uuid.UUID
    author_user_id: uuid.UUID
    author_display_name: str
    author_email: Optional[str] = None
    disclosed_at: datetime
    audit_event_id: Optional[uuid.UUID] = None


class InfluencePeriodStats(BaseModel):
    popularity: int = 0
    popularity_delta_pct: Optional[int] = None
    best_answers: int = 0
    best_answers_delta_pct: Optional[int] = None
    thanks: int = 0
    thanks_delta_pct: Optional[int] = None


class MyDoubtStatsOut(BaseModel):
    asked_count: int = 0
    answered_count: int = 0
    verified_answers_count: int = 0
    thanks_count: int = 0
    last_7_days: InfluencePeriodStats
    overall: InfluencePeriodStats


