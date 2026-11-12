from __future__ import annotations
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field


# ==========================================
# Concept & Concept Version Schemas
# ==========================================

class ConceptVersionCreate(BaseModel):
    definition: str = Field(..., min_length=3)
    explanation: Optional[str] = None


class ConceptVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institution_id: UUID
    concept_id: UUID
    version_number: int
    definition: str
    explanation: Optional[str] = None
    review_status: str
    created_by_user_id: Optional[UUID] = None
    approved_by_user_id: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    created_at: datetime


class ConceptCreate(BaseModel):
    concept_code: Optional[str] = None
    canonical_name: str = Field(..., min_length=2, max_length=255)
    definition: str = Field(..., min_length=3)
    explanation: Optional[str] = None


class ConceptUpdate(BaseModel):
    canonical_name: Optional[str] = Field(None, min_length=2, max_length=255)
    status: Optional[str] = Field(None, pattern="^(active|retired)$")


class ConceptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institution_id: UUID
    concept_code: Optional[str] = None
    canonical_name: str
    status: str
    created_at: datetime
    updated_at: datetime
    latest_version: Optional[ConceptVersionOut] = None


class ConceptSummaryOut(BaseModel):
    id: UUID
    concept_code: Optional[str] = None
    canonical_name: str
    definition: str
    importance_weight: Optional[float] = 1.0
    primary_syllabus_node_id: Optional[UUID] = None


# ==========================================
# Learning Objective Schemas
# ==========================================

class LearningObjectiveCreate(BaseModel):
    objective_code: str = Field(..., min_length=1, max_length=50)
    description: str = Field(..., min_length=3)
    bloom_level: str = Field("understand", pattern="^(remember|understand|apply|analyze|evaluate|create)$")
    syllabus_node_id: Optional[UUID] = None
    concept_id: Optional[UUID] = None
    sequence_no: int = 1


class LearningObjectiveOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institution_id: UUID
    course_content_version_id: UUID
    syllabus_node_id: Optional[UUID] = None
    concept_id: Optional[UUID] = None
    objective_code: str
    description: str
    bloom_level: str
    sequence_no: int
    created_at: datetime


# ==========================================
# Course Content Version Schemas
# ==========================================

class CourseContentVersionCreate(BaseModel):
    change_summary: Optional[str] = None


class PublishContentVersionRequest(BaseModel):
    change_summary: Optional[str] = None


class CourseContentVersionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institution_id: UUID
    course_offering_id: UUID
    version_number: int
    status: str
    created_by_user_id: Optional[UUID] = None
    reviewed_by_user_id: Optional[UUID] = None
    approved_at: Optional[datetime] = None
    published_at: Optional[datetime] = None
    change_summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime


# ==========================================
# Syllabus Node Schemas
# ==========================================

class SyllabusNodeCreate(BaseModel):
    parent_node_id: Optional[UUID] = None
    node_type: str = Field("module", pattern="^(module|topic|subtopic)$")
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    sequence_no: int = 1
    source_chunk_id: Optional[UUID] = None


class SyllabusNodeUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    sequence_no: Optional[int] = None
    parent_node_id: Optional[UUID] = None
    review_status: Optional[str] = Field(None, pattern="^(extracted|needs_review|approved|rejected)$")


class SyllabusNodeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    institution_id: UUID
    course_content_version_id: UUID
    parent_node_id: Optional[UUID] = None
    node_type: str
    title: str
    description: Optional[str] = None
    sequence_no: int
    source_chunk_id: Optional[UUID] = None
    review_status: str
    created_at: datetime
    updated_at: datetime


class SyllabusNodeTreeOut(SyllabusNodeOut):
    children: List[SyllabusNodeTreeOut] = []
    learning_objectives: List[LearningObjectiveOut] = []


# ==========================================
# Concept Bindings Schemas
# ==========================================

class CourseContentConceptBindRequest(BaseModel):
    concept_id: UUID
    primary_syllabus_node_id: Optional[UUID] = None
    importance_weight: float = Field(1.0, ge=0.0, le=10.0)


class CourseContentConceptOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    course_content_version_id: UUID
    concept_id: UUID
    institution_id: UUID
    primary_syllabus_node_id: Optional[UUID] = None
    importance_weight: float
    created_at: datetime


# ==========================================
# Full Syllabus Response
# ==========================================

class SyllabusTreeResponse(BaseModel):
    version: CourseContentVersionOut
    nodes: List[SyllabusNodeTreeOut]
    concepts: List[ConceptSummaryOut]

