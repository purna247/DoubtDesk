"""Add syllabus_node_id and semantic_metadata to doubts for semantic topic analysis.

Revision ID: 0021
Revises: 0020
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0021"
down_revision: Union[str, None] = "0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "doubts",
        sa.Column(
            "syllabus_node_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("syllabus_nodes.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "doubts",
        sa.Column(
            "semantic_metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.create_index("ix_doubts_syllabus_node", "doubts", ["syllabus_node_id"])


def downgrade() -> None:
    op.drop_index("ix_doubts_syllabus_node", table_name="doubts")
    op.drop_column("doubts", "semantic_metadata")
    op.drop_column("doubts", "syllabus_node_id")
