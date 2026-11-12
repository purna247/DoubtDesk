"""Concept analytics policies, diagnostic evidence snapshots, cohort metrics, and mastery.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-11 16:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = '0009'
down_revision: Union[str, None] = '0008'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Course analytics policies
    op.create_table(
        'course_analytics_policies',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('course_offering_id', UUID(as_uuid=True), sa.ForeignKey('course_offerings.id', ondelete='CASCADE'), nullable=True),
        sa.Column('min_distinct_questions', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('weakness_accuracy_threshold', sa.Numeric(5, 4), nullable=False, server_default='0.6000'),
        sa.Column('diagnostic_attempt_policy', sa.String(50), nullable=False, server_default='first_valid_submitted_scored'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('effective_from', sa.DateTime(timezone=True), nullable=True),
        sa.Column('effective_to', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('institution_id', 'course_offering_id', name='uq_institution_offering_analytics_policy'),
    )
    op.create_index('ix_course_analytics_policies_inst', 'course_analytics_policies', ['institution_id'])
    op.create_index('ix_course_analytics_policies_offering', 'course_analytics_policies', ['course_offering_id'])

    # 2. Misconception events
    op.create_table(
        'misconception_events',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assessment_attempt_id', UUID(as_uuid=True), sa.ForeignKey('assessment_attempts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assessment_item_id', UUID(as_uuid=True), sa.ForeignKey('assessment_items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assessment_response_id', UUID(as_uuid=True), sa.ForeignKey('assessment_responses.id', ondelete='CASCADE'), nullable=True),
        sa.Column('selected_option_id', UUID(as_uuid=True), sa.ForeignKey('question_part_options.id', ondelete='CASCADE'), nullable=False),
        sa.Column('misconception_id', UUID(as_uuid=True), sa.ForeignKey('misconceptions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_membership_id', UUID(as_uuid=True), sa.ForeignKey('institution_memberships.id', ondelete='CASCADE'), nullable=False),
        sa.Column('course_offering_id', UUID(as_uuid=True), sa.ForeignKey('course_offerings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('assessment_response_id', 'selected_option_id', 'misconception_id', name='uq_resp_opt_misconception'),
    )
    op.create_index('ix_misconception_events_inst', 'misconception_events', ['institution_id'])
    op.create_index('ix_misconception_events_attempt', 'misconception_events', ['assessment_attempt_id'])
    op.create_index('ix_misconception_events_misc', 'misconception_events', ['misconception_id'])
    op.create_index('ix_misconception_events_offering', 'misconception_events', ['course_offering_id'])

    # 3. Analytics runs
    op.create_table(
        'analytics_runs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('course_offering_id', UUID(as_uuid=True), sa.ForeignKey('course_offerings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('policy_id', UUID(as_uuid=True), sa.ForeignKey('course_analytics_policies.id', ondelete='SET NULL'), nullable=True),
        sa.Column('run_type', sa.String(30), nullable=False, server_default='manual'),
        sa.Column('status', sa.String(20), nullable=False, server_default='completed'),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('source_watermark', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_analytics_runs_inst', 'analytics_runs', ['institution_id'])
    op.create_index('ix_analytics_runs_offering', 'analytics_runs', ['course_offering_id'])

    # 4. Student concept evidence snapshots
    op.create_table(
        'student_concept_evidence_snapshots',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('analytics_run_id', UUID(as_uuid=True), sa.ForeignKey('analytics_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('course_offering_id', UUID(as_uuid=True), sa.ForeignKey('course_offerings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_membership_id', UUID(as_uuid=True), sa.ForeignKey('institution_memberships.id', ondelete='CASCADE'), nullable=False),
        sa.Column('concept_id', UUID(as_uuid=True), sa.ForeignKey('concepts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('distinct_question_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('awarded_marks', sa.Numeric(10, 2), nullable=False, server_default='0.0'),
        sa.Column('available_marks', sa.Numeric(10, 2), nullable=False, server_default='0.0'),
        sa.Column('accuracy', sa.Numeric(7, 5), nullable=True),
        sa.Column('diagnostic_status', sa.String(40), nullable=False, server_default='insufficient_evidence'),
        sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('analytics_run_id', 'student_membership_id', 'concept_id', name='uq_run_student_concept_snapshot'),
    )
    op.create_index('ix_student_concept_evidence_inst', 'student_concept_evidence_snapshots', ['institution_id'])
    op.create_index('ix_student_concept_evidence_run', 'student_concept_evidence_snapshots', ['analytics_run_id'])
    op.create_index('ix_student_concept_evidence_student', 'student_concept_evidence_snapshots', ['student_membership_id'])
    op.create_index('ix_student_concept_evidence_concept', 'student_concept_evidence_snapshots', ['concept_id'])

    # 5. Cohort concept analytics
    op.create_table(
        'cohort_concept_analytics',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('analytics_run_id', UUID(as_uuid=True), sa.ForeignKey('analytics_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('course_offering_id', UUID(as_uuid=True), sa.ForeignKey('course_offerings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('concept_id', UUID(as_uuid=True), sa.ForeignKey('concepts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('enrolled_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('assessed_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('confirmed_weak_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('candidate_weak_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('insufficient_evidence_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cohort_mean_accuracy', sa.Numeric(7, 5), nullable=True),
        sa.Column('cohort_pooled_accuracy', sa.Numeric(7, 5), nullable=True),
        sa.Column('tagged_misconception_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('analytics_run_id', 'concept_id', name='uq_run_concept_cohort_analytics'),
    )
    op.create_index('ix_cohort_concept_analytics_inst', 'cohort_concept_analytics', ['institution_id'])
    op.create_index('ix_cohort_concept_analytics_run', 'cohort_concept_analytics', ['analytics_run_id'])
    op.create_index('ix_cohort_concept_analytics_offering', 'cohort_concept_analytics', ['course_offering_id'])
    op.create_index('ix_cohort_concept_analytics_concept', 'cohort_concept_analytics', ['concept_id'])

    # 6. Concept mastery policies
    op.create_table(
        'concept_mastery_policies',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('course_offering_id', UUID(as_uuid=True), sa.ForeignKey('course_offerings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('policy_name', sa.String(100), nullable=False),
        sa.Column('criteria_json', JSONB, nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='active'),
        sa.Column('created_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('approved_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_concept_mastery_policies_inst', 'concept_mastery_policies', ['institution_id'])
    op.create_index('ix_concept_mastery_policies_offering', 'concept_mastery_policies', ['course_offering_id'])

    # 7. Student concept mastery evaluations
    op.create_table(
        'student_concept_mastery_evaluations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_membership_id', UUID(as_uuid=True), sa.ForeignKey('institution_memberships.id', ondelete='CASCADE'), nullable=False),
        sa.Column('course_offering_id', UUID(as_uuid=True), sa.ForeignKey('course_offerings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('concept_id', UUID(as_uuid=True), sa.ForeignKey('concepts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('mastery_policy_id', UUID(as_uuid=True), sa.ForeignKey('concept_mastery_policies.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(30), nullable=False, server_default='not_evaluated'),
        sa.Column('evidence_summary_json', JSONB, nullable=True),
        sa.Column('evaluated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('evaluated_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.UniqueConstraint('student_membership_id', 'concept_id', 'mastery_policy_id', name='uq_student_concept_mastery_eval'),
    )
    op.create_index('ix_student_concept_mastery_inst', 'student_concept_mastery_evaluations', ['institution_id'])
    op.create_index('ix_student_concept_mastery_student', 'student_concept_mastery_evaluations', ['student_membership_id'])
    op.create_index('ix_student_concept_mastery_concept', 'student_concept_mastery_evaluations', ['concept_id'])


def downgrade() -> None:
    op.drop_table('student_concept_mastery_evaluations')
    op.drop_table('concept_mastery_policies')
    op.drop_table('cohort_concept_analytics')
    op.drop_table('student_concept_evidence_snapshots')
    op.drop_table('analytics_runs')
    op.drop_table('misconception_events')
    op.drop_table('course_analytics_policies')

