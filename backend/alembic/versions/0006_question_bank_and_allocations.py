"""Question bank, parts, objective options, concept allocations, and coverage events.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-11 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = '0006'
down_revision: Union[str, None] = '0005'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Questions
    op.create_table(
        'questions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('origin_type', sa.String(length=30), server_default='teacher_authored', nullable=False),
        sa.Column('lifecycle_status', sa.String(length=20), server_default='draft', nullable=False),
        sa.Column('is_ai_generated', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_questions_inst', 'questions', ['institution_id'])

    # 2. Question Versions
    op.create_table(
        'question_versions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question_id', UUID(as_uuid=True), sa.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_number', sa.Integer(), server_default='1', nullable=False),
        sa.Column('prompt_text', sa.Text(), nullable=False),
        sa.Column('question_type', sa.String(length=30), server_default='mcq', nullable=False),
        sa.Column('command_verb', sa.String(length=50), nullable=True),
        sa.Column('expected_answer_depth', sa.String(length=30), nullable=True),
        sa.Column('marks_total', sa.Numeric(precision=8, scale=2), server_default='1.0', nullable=False),
        sa.Column('difficulty_level', sa.String(length=20), server_default='medium', nullable=False),
        sa.Column('cognitive_level', sa.String(length=30), nullable=True),
        sa.Column('approval_status', sa.String(length=20), server_default='draft', nullable=False),
        sa.Column('created_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reviewed_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('rejection_reason', sa.Text(), nullable=True),
        sa.Column('marking_guidance', sa.Text(), nullable=True),
        sa.Column('metadata_json', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('question_id', 'version_number', name='uq_question_version_num'),
    )
    op.create_index('ix_question_versions_inst', 'question_versions', ['institution_id'])
    op.create_index('ix_question_versions_question', 'question_versions', ['question_id'])

    # 3. Question Parts
    op.create_table(
        'question_parts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question_version_id', UUID(as_uuid=True), sa.ForeignKey('question_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('part_key', sa.String(length=20), server_default='A', nullable=False),
        sa.Column('part_prompt', sa.Text(), nullable=False),
        sa.Column('sequence_no', sa.Integer(), server_default='1', nullable=False),
        sa.Column('marks_available', sa.Numeric(precision=8, scale=2), server_default='1.0', nullable=False),
        sa.Column('answer_type', sa.String(length=30), server_default='mcq', nullable=False),
        sa.Column('expected_answer_depth', sa.String(length=30), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('question_version_id', 'part_key', name='uq_question_part_key'),
    )
    op.create_index('ix_question_parts_inst', 'question_parts', ['institution_id'])
    op.create_index('ix_question_parts_version', 'question_parts', ['question_version_id'])

    # 4. Misconceptions
    op.create_table(
        'misconceptions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('concept_id', UUID(as_uuid=True), sa.ForeignKey('concepts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('code', sa.String(length=50), nullable=False),
        sa.Column('label', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('review_status', sa.String(length=20), server_default='teacher_approved', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('institution_id', 'code', name='uq_institution_misconception_code'),
    )
    op.create_index('ix_misconceptions_inst', 'misconceptions', ['institution_id'])
    op.create_index('ix_misconceptions_concept', 'misconceptions', ['concept_id'])

    # 5. Question Part Options
    op.create_table(
        'question_part_options',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question_part_id', UUID(as_uuid=True), sa.ForeignKey('question_parts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('option_key', sa.String(length=10), nullable=False),
        sa.Column('display_text', sa.Text(), nullable=False),
        sa.Column('sequence_no', sa.Integer(), server_default='1', nullable=False),
        sa.Column('is_correct', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('misconception_id', UUID(as_uuid=True), sa.ForeignKey('misconceptions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('question_part_id', 'option_key', name='uq_part_option_key'),
    )
    op.create_index('ix_question_part_options_inst', 'question_part_options', ['institution_id'])
    op.create_index('ix_question_part_options_part', 'question_part_options', ['question_part_id'])

    # 6. Question Part Concept Allocations
    op.create_table(
        'question_part_concept_allocations',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question_part_id', UUID(as_uuid=True), sa.ForeignKey('question_parts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('concept_id', UUID(as_uuid=True), sa.ForeignKey('concepts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('allocated_marks', sa.Numeric(precision=8, scale=2), nullable=False),
        sa.Column('allocation_note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('question_part_id', 'concept_id', name='uq_part_concept_alloc'),
    )
    op.create_index('ix_part_concept_alloc_inst', 'question_part_concept_allocations', ['institution_id'])
    op.create_index('ix_part_concept_alloc_part', 'question_part_concept_allocations', ['question_part_id'])

    # 7. Question Version Learning Objectives
    op.create_table(
        'question_version_learning_objectives',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question_version_id', UUID(as_uuid=True), sa.ForeignKey('question_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('learning_objective_id', UUID(as_uuid=True), sa.ForeignKey('learning_objectives.id', ondelete='CASCADE'), nullable=False),
        sa.Column('relationship_role', sa.String(length=20), server_default='primary', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('question_version_id', 'learning_objective_id', name='uq_qversion_lo'),
    )

    # 8. Question Version Sources
    op.create_table(
        'question_version_sources',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question_version_id', UUID(as_uuid=True), sa.ForeignKey('question_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_chunk_id', UUID(as_uuid=True), sa.ForeignKey('source_chunks.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reference_role', sa.String(length=30), server_default='origin', nullable=False),
        sa.Column('excerpt', sa.Text(), nullable=True),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 9. Question Relationships
    op.create_table(
        'question_relationships',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_question_id', UUID(as_uuid=True), sa.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('target_question_id', UUID(as_uuid=True), sa.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('relationship_type', sa.String(length=40), nullable=False),
        sa.Column('confidence', sa.Numeric(precision=4, scale=3), nullable=True),
        sa.Column('review_status', sa.String(length=20), server_default='provisional', nullable=False),
        sa.Column('created_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('approved_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('source_question_id', 'target_question_id', 'relationship_type', name='uq_question_rel'),
    )

    # 10. Question Coverage Events
    op.create_table(
        'question_coverage_events',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('course_offering_id', UUID(as_uuid=True), sa.ForeignKey('course_offerings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question_id', UUID(as_uuid=True), sa.ForeignKey('questions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question_version_id', UUID(as_uuid=True), sa.ForeignKey('question_versions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('event_type', sa.String(length=40), nullable=False),
        sa.Column('actor_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('details_json', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_question_coverage_events_offering', 'question_coverage_events', ['course_offering_id'])


def downgrade() -> None:
    op.drop_table('question_coverage_events')
    op.drop_table('question_relationships')
    op.drop_table('question_version_sources')
    op.drop_table('question_version_learning_objectives')
    op.drop_table('question_part_concept_allocations')
    op.drop_table('question_part_options')
    op.drop_table('misconceptions')
    op.drop_table('question_parts')
    op.drop_table('question_versions')
    op.drop_table('questions')

