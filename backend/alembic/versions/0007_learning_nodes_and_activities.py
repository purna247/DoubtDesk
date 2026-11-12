"""Learning nodes, prerequisites, structured activities, and versioned payloads.

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-11 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = '0007'
down_revision: Union[str, None] = '0006'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Learning Nodes
    op.create_table(
        'learning_nodes',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('course_offering_id', UUID(as_uuid=True), sa.ForeignKey('course_offerings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('course_content_version_id', UUID(as_uuid=True), sa.ForeignKey('course_content_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('node_code', sa.String(length=50), nullable=True),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sequence_no', sa.Integer(), server_default='1', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='draft', nullable=False),
        sa.Column('completion_rule_json', JSONB, nullable=True),
        sa.Column('created_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_learning_nodes_inst', 'learning_nodes', ['institution_id'])
    op.create_index('ix_learning_nodes_offering', 'learning_nodes', ['course_offering_id'])

    # 2. Learning Node Concepts
    op.create_table(
        'learning_node_concepts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('learning_node_id', UUID(as_uuid=True), sa.ForeignKey('learning_nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('concept_id', UUID(as_uuid=True), sa.ForeignKey('concepts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('relationship_role', sa.String(length=20), server_default='primary', nullable=False),
        sa.Column('mapping_status', sa.String(length=20), server_default='teacher_approved', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('learning_node_id', 'concept_id', name='uq_learning_node_concept'),
    )

    # 3. Learning Node Prerequisites
    op.create_table(
        'learning_node_prerequisites',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('learning_node_id', UUID(as_uuid=True), sa.ForeignKey('learning_nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('prerequisite_node_id', UUID(as_uuid=True), sa.ForeignKey('learning_nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('prerequisite_type', sa.String(length=20), server_default='required', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('learning_node_id', 'prerequisite_node_id', name='uq_node_prerequisite'),
    )

    # 4. Activities
    op.create_table(
        'activities',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('learning_node_id', UUID(as_uuid=True), sa.ForeignKey('learning_nodes.id', ondelete='CASCADE'), nullable=False),
        sa.Column('question_id', UUID(as_uuid=True), sa.ForeignKey('questions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_activities_inst', 'activities', ['institution_id'])
    op.create_index('ix_activities_node', 'activities', ['learning_node_id'])

    # 5. Activity Versions
    op.create_table(
        'activity_versions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('activity_id', UUID(as_uuid=True), sa.ForeignKey('activities.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_number', sa.Integer(), server_default='1', nullable=False),
        sa.Column('question_version_id', UUID(as_uuid=True), sa.ForeignKey('question_versions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('question_part_id', UUID(as_uuid=True), sa.ForeignKey('question_parts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('activity_type', sa.String(length=30), nullable=False),
        sa.Column('schema_version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('instructions', sa.Text(), nullable=True),
        sa.Column('student_payload_json', JSONB, nullable=False),
        sa.Column('answer_key_json', JSONB, nullable=False),
        sa.Column('scoring_config_json', JSONB, nullable=False),
        sa.Column('approval_status', sa.String(length=20), server_default='approved', nullable=False),
        sa.Column('created_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('approved_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('activity_id', 'version_number', name='uq_activity_version_num'),
    )
    op.create_index('ix_activity_versions_inst', 'activity_versions', ['institution_id'])
    op.create_index('ix_activity_versions_activity', 'activity_versions', ['activity_id'])


def downgrade() -> None:
    op.drop_table('activity_versions')
    op.drop_table('activities')
    op.drop_table('learning_node_prerequisites')
    op.drop_table('learning_node_concepts')
    op.drop_table('learning_nodes')

