"""Persist academic AI extraction runs, batches, and node question links.

Revision ID: 0017
Revises: 0016
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0017"
down_revision: Union[str, None] = "0016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "academic_extraction_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("source_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("course_offering_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("course_offerings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("content_checksum", sa.String(64), nullable=False),
        sa.Column("pipeline_key", sa.String(128), nullable=False),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("prompt_version", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("has_warnings", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("warnings_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("safe_error_summary", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("course_offering_id", "pipeline_key", name="uq_academic_run_cache_key"),
    )
    op.create_index("ix_academic_extraction_runs_institution_id", "academic_extraction_runs", ["institution_id"])
    op.create_index("ix_academic_extraction_runs_source_document_id", "academic_extraction_runs", ["source_document_id"])
    op.create_index("ix_academic_extraction_runs_course_offering_id", "academic_extraction_runs", ["course_offering_id"])
    op.create_table(
        "academic_extraction_batches",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("academic_extraction_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage", sa.String(30), nullable=False),
        sa.Column("batch_index", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("source_chunk_ids", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("response_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("warning_code", sa.String(50), nullable=True),
        sa.Column("warning_message", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("run_id", "stage", "batch_index", name="uq_academic_batch"),
    )
    op.create_index("ix_academic_extraction_batches_run_id", "academic_extraction_batches", ["run_id"])
    op.create_table(
        "learning_node_questions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("institution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("learning_node_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("learning_nodes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("questions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("question_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relationship_role", sa.String(20), nullable=False, server_default="practice"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("learning_node_id", "question_version_id", name="uq_learning_node_question_version"),
    )
    for name, table, column in [
        ("ix_learning_node_questions_institution_id", "learning_node_questions", "institution_id"),
        ("ix_learning_node_questions_learning_node_id", "learning_node_questions", "learning_node_id"),
        ("ix_learning_node_questions_question_id", "learning_node_questions", "question_id"),
        ("ix_learning_node_questions_question_version_id", "learning_node_questions", "question_version_id"),
    ]:
        op.create_index(name, table, [column])
    op.create_table(
        "gemini_quota_windows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("model_name", sa.String(100), nullable=False),
        sa.Column("quota_date", sa.Date(), nullable=False),
        sa.Column("requests_used", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tokens_in_window", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_request_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("model_name", "quota_date", name="uq_gemini_quota_day"),
    )


def downgrade() -> None:
    op.drop_table("gemini_quota_windows")
    for name in ("ix_learning_node_questions_question_version_id", "ix_learning_node_questions_question_id", "ix_learning_node_questions_learning_node_id", "ix_learning_node_questions_institution_id"):
        op.drop_index(name, table_name="learning_node_questions")
    op.drop_table("learning_node_questions")
    op.drop_index("ix_academic_extraction_batches_run_id", table_name="academic_extraction_batches")
    op.drop_table("academic_extraction_batches")
    for name in ("ix_academic_extraction_runs_course_offering_id", "ix_academic_extraction_runs_source_document_id", "ix_academic_extraction_runs_institution_id"):
        op.drop_index(name, table_name="academic_extraction_runs")
    op.drop_table("academic_extraction_runs")
