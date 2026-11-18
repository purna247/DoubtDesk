"""Initial database setup and extension enablement.

Revision ID: 0001
Revises: 
Create Date: 2026-11-11 08:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '0001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable UUID extension if supported by dialect
    conn = op.get_bind()
    dialect_name = conn.dialect.name
    if dialect_name == "postgresql":
        try:
            op.execute(sa.text('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";'))
        except Exception:
            pass
        try:
            op.execute(sa.text('CREATE EXTENSION IF NOT EXISTS "pgcrypto";'))
        except Exception:
            pass
        # Try to enable pgvector extension only if available in PostgreSQL installation
        try:
            result = conn.execute(sa.text("SELECT 1 FROM pg_available_extensions WHERE name = 'vector';")).scalar()
            if result:
                op.execute(sa.text('CREATE EXTENSION IF NOT EXISTS "vector";'))
        except Exception:
            pass

    # Baseline schema metadata table
    op.create_table(
        'system_metadata',
        sa.Column('key', sa.String(length=100), primary_key=True),
        sa.Column('value', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('system_metadata')

