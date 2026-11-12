import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String,
    Text,
    Integer,
    Numeric,
    Boolean,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    CheckConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class LearningNode(Base):
    """
    Dynamic learning unit along the course progression map.
    Represents validated academic requirements, concepts, and practice activities.
    """
    __tablename__ = "learning_nodes"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_offering_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_content_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("course_content_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    node_code: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g. NODE-01, M1-T1
    module_title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    difficulty_rank: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sequence_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="draft", nullable=False
    )  # draft | published | archived
    completion_rule_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    offering: Mapped["app.modules.academics.models.CourseOffering"] = relationship("app.modules.academics.models.CourseOffering")
    content_version: Mapped["app.modules.knowledge.models.CourseContentVersion"] = relationship("app.modules.knowledge.models.CourseContentVersion")
    concept_links: Mapped[List["LearningNodeConcept"]] = relationship(
        "LearningNodeConcept", back_populates="learning_node", cascade="all, delete-orphan"
    )
    prerequisites: Mapped[List["LearningNodePrerequisite"]] = relationship(
        "LearningNodePrerequisite", foreign_keys="[LearningNodePrerequisite.learning_node_id]", back_populates="learning_node", cascade="all, delete-orphan"
    )
    activities: Mapped[List["Activity"]] = relationship(
        "Activity", back_populates="learning_node", cascade="all, delete-orphan"
    )


class LearningNodeConcept(Base):
    """Concept mapping binding a learning node to stable institutional concepts."""
    __tablename__ = "learning_node_concepts"
    __table_args__ = (
        UniqueConstraint("learning_node_id", "concept_id", name="uq_learning_node_concept"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    learning_node_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learning_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    concept_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relationship_role: Mapped[str] = mapped_column(
        String(20), default="primary", nullable=False
    )  # primary | supporting
    mapping_status: Mapped[str] = mapped_column(
        String(20), default="teacher_approved", nullable=False
    )  # candidate | teacher_approved | rejected

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    learning_node: Mapped["LearningNode"] = relationship("LearningNode", back_populates="concept_links")
    concept: Mapped["app.modules.knowledge.models.Concept"] = relationship("app.modules.knowledge.models.Concept")


class LearningNodeQuestion(Base):
    """Original/source questions intentionally included in a draft learning node."""
    __tablename__ = "learning_node_questions"
    __table_args__ = (UniqueConstraint("learning_node_id", "question_version_id", name="uq_learning_node_question_version"),)

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True)
    learning_node_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("learning_nodes.id", ondelete="CASCADE"), nullable=False, index=True)
    question_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("questions.id", ondelete="CASCADE"), nullable=False, index=True)
    question_version_id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), ForeignKey("question_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    relationship_role: Mapped[str] = mapped_column(String(20), nullable=False, default="practice")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class LearningNodePrerequisite(Base):
    """Directed dependency requirement between learning nodes."""
    __tablename__ = "learning_node_prerequisites"
    __table_args__ = (
        CheckConstraint("learning_node_id <> prerequisite_node_id", name="chk_node_not_self_prereq"),
        UniqueConstraint("learning_node_id", "prerequisite_node_id", name="uq_node_prerequisite"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    learning_node_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learning_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prerequisite_node_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learning_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    prerequisite_type: Mapped[str] = mapped_column(
        String(20), default="required", nullable=False
    )  # required | recommended

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    learning_node: Mapped["LearningNode"] = relationship("LearningNode", foreign_keys=[learning_node_id], back_populates="prerequisites")
    prerequisite_node: Mapped["LearningNode"] = relationship("LearningNode", foreign_keys=[prerequisite_node_id])


class Activity(Base):
    """
    Stable identity for an interactive learning activity or assessment item.
    May be linked to an underlying Question identity.
    """
    __tablename__ = "activities"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    learning_node_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learning_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("questions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )  # draft | active | archived

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    learning_node: Mapped["LearningNode"] = relationship("LearningNode", back_populates="activities")
    question: Mapped[Optional["app.modules.questions.models.Question"]] = relationship("app.modules.questions.models.Question")
    versions: Mapped[List["ActivityVersion"]] = relationship(
        "ActivityVersion", back_populates="activity", cascade="all, delete-orphan", order_by="ActivityVersion.version_number.desc()"
    )


class ActivityVersion(Base):
    """
    Immutable versioned activity payload.
    Separates student renderer payload (safe, no answers) from server-authoritative answer keys.
    """
    __tablename__ = "activity_versions"
    __table_args__ = (
        UniqueConstraint("activity_id", "version_number", name="uq_activity_version_num"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    activity_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("activities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    question_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("question_versions.id", ondelete="SET NULL"), nullable=True
    )
    question_part_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("question_parts.id", ondelete="SET NULL"), nullable=True
    )
    activity_type: Mapped[str] = mapped_column(
        String(30), nullable=False
    )  # mcq | fill_blank | matching_pairs | ordering | classification | key_points_check
    schema_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    student_payload_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    answer_key_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    scoring_config_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    approval_status: Mapped[str] = mapped_column(
        String(20), default="approved", nullable=False
    )  # draft | approved | rejected | superseded
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    activity: Mapped["Activity"] = relationship("Activity", back_populates="versions")


class StudentPracticeSession(Base):
    """Adaptive Learn-tab practice session state and telemetry per student and learning node."""
    __tablename__ = "student_practice_sessions"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_membership_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institution_memberships.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_offering_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False, index=True
    )
    learning_node_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learning_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="in_progress", nullable=False)  # in_progress | completed
    current_difficulty: Mapped[str] = mapped_column(String(16), default="easy", nullable=False)  # easy | medium | hard
    in_remediation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    remediation_for_activity_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("activity_versions.id", ondelete="SET NULL"), nullable=True
    )
    current_activity_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("activity_versions.id", ondelete="SET NULL"), nullable=True
    )
    target_correct_count: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    questions_answered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    correct_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    mistake_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    consecutive_mistakes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    easier_followups_triggered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    hints_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    recovered_after_mistake_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class StudentPracticeEvent(Base):
    """Append-only interaction log for student practice (answers, hints, remediation, improvement)."""
    __tablename__ = "student_practice_events"

    id: Mapped[uuid.UUID] = mapped_column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("student_practice_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_membership_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institution_memberships.id", ondelete="CASCADE"), nullable=False, index=True
    )
    learning_node_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("learning_nodes.id", ondelete="CASCADE"), nullable=False, index=True
    )
    activity_version_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("activity_versions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)  # hint_requested | answer_submitted | remediation_triggered | node_completed
    difficulty_tier: Mapped[str] = mapped_column(String(16), default="easy", nullable=False)
    is_remediation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_correct: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    hint_used: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    selected_option_id: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


