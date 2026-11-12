import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Boolean, Integer, Numeric, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.database import Base


class Institution(Base):
    """Authoritative tenant university or educational institution."""
    __tablename__ = "institutions"

    id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    institution_code: Mapped[str] = mapped_column(
        String(40), unique=True, nullable=False, index=True
    )
    legal_name: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    primary_domain: Mapped[Optional[str]] = mapped_column(Text, nullable=True, index=True)
    logo_storage_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="active", nullable=False
    )  # provisioning | active | suspended | decommissioned
    timezone: Mapped[str] = mapped_column(String(64), default="Asia/Kolkata", nullable=False)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    settings: Mapped[Optional["InstitutionSettings"]] = relationship(
        "InstitutionSettings", back_populates="institution", uselist=False, cascade="all, delete-orphan"
    )
    memberships: Mapped[list["InstitutionMembership"]] = relationship(
        "InstitutionMembership", back_populates="institution"
    )


class InstitutionSettings(Base):
    """Database-backed runtime policies for an institution tenant."""
    __tablename__ = "institution_settings"

    institution_id: Mapped[uuid.UUID] = mapped_column(
        PG_UUID(as_uuid=True), ForeignKey("institutions.id", ondelete="CASCADE"), primary_key=True
    )
    allow_teacher_view_anonymous: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    min_distinct_questions_for_gap: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    weakness_accuracy_threshold: Mapped[float] = mapped_column(
        Numeric(5, 4), default=0.6000, nullable=False
    )
    default_upload_limit_mb: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    policy_json: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    institution: Mapped["Institution"] = relationship("Institution", back_populates="settings")

