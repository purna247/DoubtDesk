"""Separate academic material review from student publication.

Revision ID: 0016
Revises: 0015
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0016"
down_revision: Union[str, None] = "0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "source_documents",
        sa.Column("review_status", sa.String(length=20), nullable=False, server_default="pending_review"),
    )
    op.execute("UPDATE source_documents SET review_status = 'approved' WHERE publication_status = 'published'")
    op.execute("UPDATE source_documents SET review_status = 'rejected' WHERE publication_status = 'rejected'")


def downgrade() -> None:
    op.drop_column("source_documents", "review_status")
