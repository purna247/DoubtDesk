"""Add doubt_answer_votes table for one-thanks-per-user-per-answer enforcement.

Revision ID: 0014
Revises: 0013
Create Date: 2026-11-11 20:30:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0014"
down_revision: Union[str, None] = "0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "doubt_answer_votes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("answer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vote_type", sa.String(length=10), nullable=False, server_default="thanks"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["institution_id"], ["institutions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["answer_id"], ["doubt_answers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("answer_id", "user_id", "vote_type", name="uq_doubt_answer_user_vote"),
    )
    op.create_index(op.f("ix_doubt_answer_votes_institution_id"), "doubt_answer_votes", ["institution_id"], unique=False)
    op.create_index(op.f("ix_doubt_answer_votes_answer_id"), "doubt_answer_votes", ["answer_id"], unique=False)
    op.create_index(op.f("ix_doubt_answer_votes_user_id"), "doubt_answer_votes", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_doubt_answer_votes_user_id"), table_name="doubt_answer_votes")
    op.drop_index(op.f("ix_doubt_answer_votes_answer_id"), table_name="doubt_answer_votes")
    op.drop_index(op.f("ix_doubt_answer_votes_institution_id"), table_name="doubt_answer_votes")
    op.drop_table("doubt_answer_votes")

