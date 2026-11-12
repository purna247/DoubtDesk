from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Notification(Base):
    """
    In-app notification ledger for targeted academic and workflow events.
    Recipient targeting adheres strictly to privacy rules:
    notifications for anonymous doubts never disclose the anonymous author identity.
    """
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    notification_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # intervention_assigned | phase_unlocked | doubt_answered | answer_verified | moderation_alert | system_notice
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    target_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # intervention | doubt | course | assessment
    target_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # Relationships
    recipient: Mapped["app.modules.auth.models.User"] = relationship(
        "app.modules.auth.models.User", foreign_keys=[user_id]
    )
    actor: Mapped[Optional["app.modules.auth.models.User"]] = relationship(
        "app.modules.auth.models.User", foreign_keys=[actor_user_id]
    )

