"""Prevent duplicate source records for identical course materials.

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-11 20:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0013"
down_revision: Union[str, None] = "0012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("source_documents", sa.Column("content_dedupe_key", sa.String(length=128), nullable=True))
    op.add_column(
        "source_documents",
        sa.Column("publication_status", sa.String(length=20), nullable=False, server_default="pending_review"),
    )
    # Keep the oldest row as the canonical target for repeat uploads. Leave legacy
    # duplicate records and their extraction provenance intact with a NULL key.
    op.execute(sa.text("""
        WITH ranked AS (
            SELECT id, row_number() OVER (
                PARTITION BY institution_id, sha256_checksum
                ORDER BY created_at ASC, id ASC
            ) AS duplicate_rank
            FROM source_documents
        )
        UPDATE source_documents AS source
        SET content_dedupe_key = CASE WHEN ranked.duplicate_rank = 1
            THEN source.sha256_checksum
            ELSE NULL END
        FROM ranked
        WHERE source.id = ranked.id
    """))
    op.create_unique_constraint(
        "uq_source_document_dedupe_key",
        "source_documents",
        ["institution_id", "content_dedupe_key"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_source_document_dedupe_key", "source_documents", type_="unique")
    op.drop_column("source_documents", "publication_status")
    op.drop_column("source_documents", "content_dedupe_key")
