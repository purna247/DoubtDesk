"""Track study guide acknowledgment while preserving existing intervention progression."""
from alembic import op
import sqlalchemy as sa

revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("interventions", sa.Column("require_primer_acknowledgment", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("intervention_assignments", sa.Column("phase_b_primer_acknowledged_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("intervention_assignments", "phase_b_primer_acknowledged_at")
    op.drop_column("interventions", "require_primer_acknowledgment")
