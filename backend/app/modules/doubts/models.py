from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional, List
from sqlalchemy import (
    String,
    Text,
    Boolean,
    Integer,
    DateTime,
    ForeignKey,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Doubt(Base):
    """
    Campus academic doubt and discussion thread.
    Supports peer-anonymous posting while preserving true author identity for audited moderation.
    """
    __tablename__ = "doubts"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_offering_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("course_offerings.id", ondelete="SET NULL"), nullable=True, index=True
    )
    canonical_subject_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("canonical_subjects.id", ondelete="SET NULL"), nullable=True, index=True
    )
    concept_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("concepts.id", ondelete="SET NULL"), nullable=True, index=True
    )
    syllabus_node_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("syllabus_nodes.id", ondelete="SET NULL"), nullable=True, index=True
    )
    question_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("questions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    semantic_metadata: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)
    is_anonymous_to_peers: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="open", nullable=False
    )  # open | answered | resolved | archived | removed
    visibility: Mapped[str] = mapped_column(
        String(20), default="course", nullable=False
    )  # institution | course | restricted
    upvote_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    answer_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    author: Mapped["app.modules.auth.models.User"] = relationship("app.modules.auth.models.User", foreign_keys=[author_user_id])
    answers: Mapped[List["DoubtAnswer"]] = relationship(
        "DoubtAnswer", back_populates="doubt", cascade="all, delete-orphan", order_by="DoubtAnswer.created_at.asc()"
    )
    comments: Mapped[List["DoubtComment"]] = relationship(
        "DoubtComment", back_populates="doubt", cascade="all, delete-orphan", order_by="DoubtComment.created_at.asc()"
    )
    votes: Mapped[List["DoubtVote"]] = relationship(
        "DoubtVote", back_populates="doubt", cascade="all, delete-orphan"
    )
    flags: Mapped[List["DoubtFlag"]] = relationship(
        "DoubtFlag", back_populates="doubt", cascade="all, delete-orphan"
    )
    concept: Mapped[Optional["app.modules.knowledge.models.Concept"]] = relationship("app.modules.knowledge.models.Concept")
    syllabus_node: Mapped[Optional["app.modules.knowledge.models.SyllabusNode"]] = relationship("app.modules.knowledge.models.SyllabusNode")


class DoubtAnswer(Base):
    """
    Peer or instructor response to a doubt.
    Includes teacher endorsement/verification distinction.
    """
    __tablename__ = "doubt_answers"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    doubt_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("doubts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    is_teacher_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    verified_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="published", nullable=False
    )  # published | hidden | flagged
    upvote_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    doubt: Mapped["Doubt"] = relationship("Doubt", back_populates="answers")
    author: Mapped["app.modules.auth.models.User"] = relationship("app.modules.auth.models.User", foreign_keys=[author_user_id])
    comments: Mapped[List["DoubtComment"]] = relationship(
        "DoubtComment", back_populates="answer", cascade="all, delete-orphan", order_by="DoubtComment.created_at.asc()"
    )
    votes: Mapped[List["DoubtAnswerVote"]] = relationship(
        "DoubtAnswerVote", back_populates="answer", cascade="all, delete-orphan"
    )


class DoubtComment(Base):
    """
    Lightweight commentary on a doubt or an answer.
    """
    __tablename__ = "doubt_comments"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    doubt_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("doubts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    answer_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("doubt_answers.id", ondelete="CASCADE"), nullable=True, index=True
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    body_markdown: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="published", nullable=False
    )  # published | hidden | flagged

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    doubt: Mapped["Doubt"] = relationship("Doubt", back_populates="comments")
    answer: Mapped[Optional["DoubtAnswer"]] = relationship("DoubtAnswer", back_populates="comments")
    author: Mapped["app.modules.auth.models.User"] = relationship("app.modules.auth.models.User")


class DoubtVote(Base):
    """
    Student or faculty upvote on a doubt.
    """
    __tablename__ = "doubt_votes"
    __table_args__ = (
        UniqueConstraint("doubt_id", "user_id", "vote_type", name="uq_doubt_user_vote"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    doubt_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("doubts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vote_type: Mapped[str] = mapped_column(String(10), default="upvote", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    doubt: Mapped["Doubt"] = relationship("Doubt", back_populates="votes")


class DoubtAnswerVote(Base):
    """
    One-per-user appreciation ("thanks") record on a doubt answer.
    """
    __tablename__ = "doubt_answer_votes"
    __table_args__ = (
        UniqueConstraint("answer_id", "user_id", "vote_type", name="uq_doubt_answer_user_vote"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    answer_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("doubt_answers.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    vote_type: Mapped[str] = mapped_column(String(10), default="thanks", nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    answer: Mapped["DoubtAnswer"] = relationship("DoubtAnswer", back_populates="votes")


class DoubtFlag(Base):
    """
    Moderation flag raised against a doubt for academic policy or community violation.
    """
    __tablename__ = "doubt_flags"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    doubt_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("doubts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reported_by_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reason_code: Mapped[str] = mapped_column(String(50), nullable=False)  # inappropriate | exam_leak | harassment | spam | other
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="open", nullable=False
    )  # open | reviewing | actioned | dismissed
    resolved_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    doubt: Mapped["Doubt"] = relationship("Doubt", back_populates="flags")


class DoubtIdentityDisclosureEvent(Base):
    """
    Immutable audit event logged when an authorized Admin, Super Admin,
    or policy-authorized Teacher reveals the true author of an anonymous doubt.
    """
    __tablename__ = "doubt_identity_disclosure_events"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    doubt_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("doubts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    reason_code: Mapped[str] = mapped_column(String(50), nullable=False)
    reason_text: Mapped[str] = mapped_column(Text, nullable=False)
    policy_basis: Mapped[str] = mapped_column(String(100), default="moderation_investigation", nullable=False)
    disclosed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    audit_event_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("audit_events.id", ondelete="SET NULL"), nullable=True
    )

