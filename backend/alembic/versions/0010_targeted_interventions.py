"""Targeted interventions, 3-phase gating, and matched pre-post tracking.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-11 17:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = '0010'
down_revision: Union[str, None] = '0009'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Interventions
    op.create_table(
        'interventions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('course_offering_id', UUID(as_uuid=True), sa.ForeignKey('course_offerings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(30), nullable=False, server_default='draft'),
        sa.Column('created_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('approved_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('assignment_starts_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('assignment_ends_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('phase_a_assessment_id', UUID(as_uuid=True), sa.ForeignKey('assessments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('phase_b_primer_content', sa.Text(), nullable=True),
        sa.Column('phase_b_practice_assessment_id', UUID(as_uuid=True), sa.ForeignKey('assessments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('phase_b_completion_rule', sa.String(50), nullable=False, server_default='all_required_items'),
        sa.Column('phase_b_required_count', sa.Integer(), nullable=True),
        sa.Column('phase_c_assessment_id', UUID(as_uuid=True), sa.ForeignKey('assessments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_interventions_inst', 'interventions', ['institution_id'])
    op.create_index('ix_interventions_offering', 'interventions', ['course_offering_id'])

    # 2. Intervention concepts
    op.create_table(
        'intervention_concepts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('intervention_id', UUID(as_uuid=True), sa.ForeignKey('interventions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('concept_id', UUID(as_uuid=True), sa.ForeignKey('concepts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('intervention_id', 'concept_id', name='uq_intervention_concept'),
    )
    op.create_index('ix_intervention_concepts_inst', 'intervention_concepts', ['institution_id'])
    op.create_index('ix_intervention_concepts_intv', 'intervention_concepts', ['intervention_id'])
    op.create_index('ix_intervention_concepts_concept', 'intervention_concepts', ['concept_id'])

    # 3. Intervention assignments
    op.create_table(
        'intervention_assignments',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('intervention_id', UUID(as_uuid=True), sa.ForeignKey('interventions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_membership_id', UUID(as_uuid=True), sa.ForeignKey('institution_memberships.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_evidence_status', sa.String(40), nullable=False, server_default='confirmed_weakness'),
        sa.Column('assignment_status', sa.String(30), nullable=False, server_default='assigned'),
        sa.Column('phase_a_attempt_id', UUID(as_uuid=True), sa.ForeignKey('assessment_attempts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('phase_a_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('phase_a_score', sa.Numeric(8, 2), nullable=True),
        sa.Column('phase_b_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('phase_b_items_completed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('phase_c_attempt_id', UUID(as_uuid=True), sa.ForeignKey('assessment_attempts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('phase_c_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('phase_c_score', sa.Numeric(8, 2), nullable=True),
        sa.Column('observed_score_change', sa.Numeric(8, 2), nullable=True),
        sa.Column('outcome_status', sa.String(30), nullable=True),
        sa.Column('assigned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('intervention_id', 'student_membership_id', name='uq_intervention_student_assignment'),
    )
    op.create_index('ix_intervention_assignments_inst', 'intervention_assignments', ['institution_id'])
    op.create_index('ix_intervention_assignments_intv', 'intervention_assignments', ['intervention_id'])
    op.create_index('ix_intervention_assignments_student', 'intervention_assignments', ['student_membership_id'])


def downgrade() -> None:
    op.drop_table('intervention_assignments')
    op.drop_table('intervention_concepts')
    op.drop_table('interventions')

