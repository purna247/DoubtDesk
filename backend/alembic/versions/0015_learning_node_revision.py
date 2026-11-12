"""Add optimistic revision checks for teacher-edited learning nodes.

Revision ID: 0015
Revises: 0014
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "0015"
down_revision: Union[str, None] = "0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "learning_nodes",
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    )


def downgrade() -> None:
    op.drop_column("learning_nodes", "revision")
