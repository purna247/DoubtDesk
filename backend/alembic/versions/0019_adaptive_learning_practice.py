"""Add adaptive student practice session and event tracking tables.

Revision ID: 0019
Revises: 0018
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0019"
down_revision: Union[str, None] = "0018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "student_practice_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("course_offering_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("learning_node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="in_progress"),
        sa.Column("current_difficulty", sa.String(length=16), nullable=False, server_default="easy"),
        sa.Column("in_remediation", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("remediation_for_activity_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("current_activity_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("target_correct_count", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("questions_answered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("correct_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("mistake_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consecutive_mistakes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("easier_followups_triggered", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("hints_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("recovered_after_mistake_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_membership_id"], ["institution_memberships.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_offering_id"], ["course_offerings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["learning_node_id"], ["learning_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["remediation_for_activity_version_id"], ["activity_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["current_activity_version_id"], ["activity_versions.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_student_practice_sessions_institution_id", "student_practice_sessions", ["institution_id"])
    op.create_index("ix_student_practice_sessions_student_membership_id", "student_practice_sessions", ["student_membership_id"])
    op.create_index("ix_student_practice_sessions_course_offering_id", "student_practice_sessions", ["course_offering_id"])
    op.create_index("ix_student_practice_sessions_learning_node_id", "student_practice_sessions", ["learning_node_id"])

    op.create_table(
        "student_practice_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("student_membership_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("learning_node_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("activity_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("difficulty_tier", sa.String(length=16), nullable=False, server_default="easy"),
        sa.Column("is_remediation", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_correct", sa.Boolean(), nullable=True),
        sa.Column("hint_used", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("selected_option_id", sa.String(length=80), nullable=True),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["student_practice_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["student_membership_id"], ["institution_memberships.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["learning_node_id"], ["learning_nodes.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["activity_version_id"], ["activity_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_student_practice_events_institution_id", "student_practice_events", ["institution_id"])
    op.create_index("ix_student_practice_events_session_id", "student_practice_events", ["session_id"])
    op.create_index("ix_student_practice_events_student_membership_id", "student_practice_events", ["student_membership_id"])
    op.create_index("ix_student_practice_events_learning_node_id", "student_practice_events", ["learning_node_id"])
    op.create_index("ix_student_practice_events_activity_version_id", "student_practice_events", ["activity_version_id"])


def downgrade() -> None:
    op.drop_table("student_practice_events")
    op.drop_table("student_practice_sessions")

