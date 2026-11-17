"""Add formal quiz scheduling, question shuffling, and student makeup overrides.

Revision ID: 0022
Revises: 0021
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0022"
down_revision: Union[str, None] = "0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add formal quiz scheduling and finalization columns to assessments
    op.add_column("assessments", sa.Column("is_formal_quiz", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("assessments", sa.Column("scheduled_start_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("assessments", sa.Column("scheduled_end_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("assessments", sa.Column("shuffle_questions", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("assessments", sa.Column("shuffle_options", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("assessments", sa.Column("is_finalized", sa.Boolean(), server_default="false", nullable=False))
    op.add_column("assessments", sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "assessments",
        sa.Column(
            "finalized_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # 2. Add teacher override columns to assessment_attempts
    op.add_column("assessment_attempts", sa.Column("faculty_override_marks", sa.Numeric(10, 2), nullable=True))
    op.add_column("assessment_attempts", sa.Column("override_reason", sa.Text(), nullable=True))
    op.add_column(
        "assessment_attempts",
        sa.Column(
            "override_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # 3. Create assessment_student_overrides table
    op.create_table(
        "assessment_student_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "institution_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("institutions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "assessment_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assessments.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "student_membership_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("institution_memberships.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("override_type", sa.String(30), server_default="makeup_window", nullable=False),
        sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column(
            "granted_by_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "resulting_attempt_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("assessment_attempts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now(), nullable=False),
    )

    op.create_index(
        "uq_single_active_makeup_per_student",
        "assessment_student_overrides",
        ["assessment_id", "student_membership_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active' AND override_type = 'makeup_window'"),
    )


def downgrade() -> None:
    op.drop_index("uq_single_active_makeup_per_student", table_name="assessment_student_overrides")
    op.drop_table("assessment_student_overrides")
    op.drop_column("assessment_attempts", "override_by_user_id")
    op.drop_column("assessment_attempts", "override_reason")
    op.drop_column("assessment_attempts", "faculty_override_marks")
    op.drop_column("assessments", "finalized_by_user_id")
    op.drop_column("assessments", "finalized_at")
    op.drop_column("assessments", "is_finalized")
    op.drop_column("assessments", "shuffle_options")
    op.drop_column("assessments", "shuffle_questions")
    op.drop_column("assessments", "scheduled_end_at")
    op.drop_column("assessments", "scheduled_start_at")
    op.drop_column("assessments", "is_formal_quiz")
