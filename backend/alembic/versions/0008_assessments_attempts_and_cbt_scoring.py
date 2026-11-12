"""Assessments, items, attempts, response projections, events, and CBT scoring.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-11 14:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = '0008'
down_revision: Union[str, None] = '0007'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Assessments
    op.create_table(
        'assessments',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('course_offering_id', UUID(as_uuid=True), sa.ForeignKey('course_offerings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('learning_node_id', UUID(as_uuid=True), sa.ForeignKey('learning_nodes.id', ondelete='SET NULL'), nullable=True),
        sa.Column('assessment_type', sa.String(length=40), server_default='node_practice', nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='draft', nullable=False),
        sa.Column('created_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_assessments_inst', 'assessments', ['institution_id'])
    op.create_index('ix_assessments_offering', 'assessments', ['course_offering_id'])

    # 2. Assessment Versions
    op.create_table(
        'assessment_versions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assessment_id', UUID(as_uuid=True), sa.ForeignKey('assessments.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_number', sa.Integer(), server_default='1', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='draft', nullable=False),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('max_attempts', sa.Integer(), nullable=True),
        sa.Column('retake_policy_json', JSONB, nullable=True),
        sa.Column('unlock_policy_json', JSONB, nullable=True),
        sa.Column('pass_criteria_json', JSONB, nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('assessment_id', 'version_number', name='uq_assessment_version_num'),
    )
    op.create_index('ix_assessment_versions_inst', 'assessment_versions', ['institution_id'])
    op.create_index('ix_assessment_versions_assessment', 'assessment_versions', ['assessment_id'])

    # 3. Assessment Items
    op.create_table(
        'assessment_items',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assessment_version_id', UUID(as_uuid=True), sa.ForeignKey('assessment_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question_version_id', UUID(as_uuid=True), sa.ForeignKey('question_versions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('activity_version_id', UUID(as_uuid=True), sa.ForeignKey('activity_versions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('sequence_no', sa.Integer(), nullable=False),
        sa.Column('marks_available', sa.Numeric(precision=8, scale=2), server_default='1.0', nullable=False),
        sa.Column('is_required', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('assessment_version_id', 'sequence_no', name='uq_assessment_item_seq'),
    )
    op.create_index('ix_assessment_items_inst', 'assessment_items', ['institution_id'])
    op.create_index('ix_assessment_items_version', 'assessment_items', ['assessment_version_id'])

    # 4. Assessment Item Concept Allocations
    op.create_table(
        'assessment_item_concept_allocations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assessment_item_id', UUID(as_uuid=True), sa.ForeignKey('assessment_items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('concept_id', UUID(as_uuid=True), sa.ForeignKey('concepts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('marks_available', sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column('allocation_source', sa.String(length=30), server_default='question_part_mapping', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('assessment_item_id', 'concept_id', name='uq_assessment_item_concept'),
    )

    # 5. Assessment Attempts
    op.create_table(
        'assessment_attempts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assessment_version_id', UUID(as_uuid=True), sa.ForeignKey('assessment_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_membership_id', UUID(as_uuid=True), sa.ForeignKey('institution_memberships.id', ondelete='CASCADE'), nullable=False),
        sa.Column('attempt_number', sa.Integer(), server_default='1', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='in_progress', nullable=False),
        sa.Column('scoring_status', sa.String(length=20), server_default='not_scored', nullable=False),
        sa.Column('is_valid', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finalized_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_synced_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('marks_awarded', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('marks_available', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('score_fraction', sa.Numeric(precision=7, scale=5), nullable=True),
        sa.Column('idempotency_key', sa.String(length=100), nullable=True),
        sa.Column('scoring_policy_snapshot', JSONB, nullable=True),
        sa.Column('invalid_reason', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('assessment_version_id', 'student_membership_id', 'attempt_number', name='uq_attempt_number'),
    )
    op.create_index('ix_assessment_attempts_inst', 'assessment_attempts', ['institution_id'])
    op.create_index('ix_assessment_attempts_student', 'assessment_attempts', ['student_membership_id'])

    # 6. Assessment Responses
    op.create_table(
        'assessment_responses',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assessment_attempt_id', UUID(as_uuid=True), sa.ForeignKey('assessment_attempts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assessment_item_id', UUID(as_uuid=True), sa.ForeignKey('assessment_items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('response_payload_json', JSONB, nullable=True),
        sa.Column('response_state', sa.String(length=25), server_default='empty', nullable=False),
        sa.Column('visited_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('first_saved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_saved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('response_version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('assessment_attempt_id', 'assessment_item_id', name='uq_attempt_item_response'),
    )

    # 7. Assessment Response Events
    op.create_table(
        'assessment_response_events',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assessment_attempt_id', UUID(as_uuid=True), sa.ForeignKey('assessment_attempts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assessment_item_id', UUID(as_uuid=True), sa.ForeignKey('assessment_items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(length=30), nullable=False),
        sa.Column('response_payload_json', JSONB, nullable=True),
        sa.Column('client_event_id', sa.String(length=100), nullable=True),
        sa.Column('server_received_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 8. Assessment Item Scores
    op.create_table(
        'assessment_item_scores',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assessment_attempt_id', UUID(as_uuid=True), sa.ForeignKey('assessment_attempts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assessment_item_id', UUID(as_uuid=True), sa.ForeignKey('assessment_items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('marks_awarded', sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column('marks_available', sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column('result_status', sa.String(length=30), nullable=False),
        sa.Column('scored_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('scoring_version', sa.Integer(), server_default='1', nullable=False),
        sa.UniqueConstraint('assessment_attempt_id', 'assessment_item_id', name='uq_attempt_item_score'),
    )

    # 9. Assessment Concept Scores
    op.create_table(
        'assessment_concept_scores',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('course_offering_id', UUID(as_uuid=True), sa.ForeignKey('course_offerings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assessment_attempt_id', UUID(as_uuid=True), sa.ForeignKey('assessment_attempts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('assessment_item_id', UUID(as_uuid=True), sa.ForeignKey('assessment_items.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question_id', UUID(as_uuid=True), sa.ForeignKey('questions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('concept_id', UUID(as_uuid=True), sa.ForeignKey('concepts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('marks_awarded', sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column('marks_available', sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column('scored_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('assessment_attempt_id', 'assessment_item_id', 'concept_id', name='uq_attempt_concept_score'),
    )
    op.create_index('ix_assessment_concept_scores_offering', 'assessment_concept_scores', ['course_offering_id'])
    op.create_index('ix_assessment_concept_scores_concept', 'assessment_concept_scores', ['concept_id'])

    # 10. Student Learning Node Progress
    op.create_table(
        'student_learning_node_progress',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('student_membership_id', UUID(as_uuid=True), sa.ForeignKey('institution_memberships.id', ondelete='CASCADE'), nullable=False),
        sa.Column('learning_node_id', UUID(as_uuid=True), sa.ForeignKey('learning_nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('progress_status', sa.String(length=20), server_default='available', nullable=False),
        sa.Column('first_started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('latest_attempt_id', UUID(as_uuid=True), sa.ForeignKey('assessment_attempts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('student_membership_id', 'learning_node_id', name='uq_student_node_progress'),
    )


def downgrade() -> None:
    op.drop_table('student_learning_node_progress')
    op.drop_table('assessment_concept_scores')
    op.drop_table('assessment_item_scores')
    op.drop_table('assessment_response_events')
    op.drop_table('assessment_responses')
    op.drop_table('assessment_attempts')
    op.drop_table('assessment_item_concept_allocations')
    op.drop_table('assessment_items')
    op.drop_table('assessment_versions')
    op.drop_table('assessments')

