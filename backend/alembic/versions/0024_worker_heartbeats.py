"""Persist ingestion worker liveness independently of jobs."""
from alembic import op
import sqlalchemy as sa

revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('worker_heartbeats',
        sa.Column('worker_id',sa.String(100),primary_key=True),
        sa.Column('last_seen_at',sa.DateTime(timezone=True),nullable=False))
    op.create_index('ix_worker_heartbeats_last_seen_at','worker_heartbeats',['last_seen_at'])


def downgrade():
    op.drop_table('worker_heartbeats')
