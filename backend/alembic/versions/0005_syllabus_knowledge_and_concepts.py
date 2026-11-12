"""Syllabus versioning, knowledge nodes, concept registry, and pedagogical objectives.

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-11 11:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = '0005'
down_revision: Union[str, None] = '0004'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Course Content Versions
    op.create_table(
        'course_content_versions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('course_offering_id', UUID(as_uuid=True), sa.ForeignKey('course_offerings.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('status', sa.String(length=20), server_default='draft', nullable=False),
        sa.Column('created_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('reviewed_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('published_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('change_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('course_offering_id', 'version_number', name='uq_course_content_version_num'),
    )
    op.create_index('ix_course_content_versions_inst', 'course_content_versions', ['institution_id'])
    op.create_index('ix_course_content_versions_offering', 'course_content_versions', ['course_offering_id'])

    # 2. Syllabus Nodes
    op.create_table(
        'syllabus_nodes',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('course_content_version_id', UUID(as_uuid=True), sa.ForeignKey('course_content_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('parent_node_id', UUID(as_uuid=True), sa.ForeignKey('syllabus_nodes.id', ondelete='CASCADE'), nullable=True),
        sa.Column('node_type', sa.String(length=20), server_default='module', nullable=False),
        sa.Column('title', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('sequence_no', sa.Integer(), server_default='1', nullable=False),
        sa.Column('source_chunk_id', UUID(as_uuid=True), sa.ForeignKey('source_chunks.id', ondelete='SET NULL'), nullable=True),
        sa.Column('review_status', sa.String(length=20), server_default='extracted', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_syllabus_nodes_inst', 'syllabus_nodes', ['institution_id'])
    op.create_index('ix_syllabus_nodes_version', 'syllabus_nodes', ['course_content_version_id'])
    op.create_index('ix_syllabus_nodes_parent', 'syllabus_nodes', ['parent_node_id'])

    # 3. Concepts
    op.create_table(
        'concepts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('concept_code', sa.String(length=50), nullable=True),
        sa.Column('canonical_name', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('institution_id', 'concept_code', name='uq_institution_concept_code'),
    )
    op.create_index('ix_concepts_inst', 'concepts', ['institution_id'])
    op.create_index('ix_concepts_code', 'concepts', ['concept_code'])

    # 4. Concept Versions
    op.create_table(
        'concept_versions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('concept_id', UUID(as_uuid=True), sa.ForeignKey('concepts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('version_number', sa.Integer(), server_default='1', nullable=False),
        sa.Column('definition', sa.Text(), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('review_status', sa.String(length=20), server_default='provisional', nullable=False),
        sa.Column('created_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('approved_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('approved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('concept_id', 'version_number', name='uq_concept_version_number'),
    )
    op.create_index('ix_concept_versions_inst', 'concept_versions', ['institution_id'])
    op.create_index('ix_concept_versions_concept', 'concept_versions', ['concept_id'])

    # 5. Course Content Concepts
    op.create_table(
        'course_content_concepts',
        sa.Column('course_content_version_id', UUID(as_uuid=True), sa.ForeignKey('course_content_versions.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('concept_id', UUID(as_uuid=True), sa.ForeignKey('concepts.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('primary_syllabus_node_id', UUID(as_uuid=True), sa.ForeignKey('syllabus_nodes.id', ondelete='SET NULL'), nullable=True),
        sa.Column('importance_weight', sa.Numeric(precision=4, scale=2), server_default='1.0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_course_content_concepts_inst', 'course_content_concepts', ['institution_id'])
    op.create_index('ix_course_content_concepts_concept', 'course_content_concepts', ['concept_id'])

    # 6. Learning Objectives
    op.create_table(
        'learning_objectives',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('course_content_version_id', UUID(as_uuid=True), sa.ForeignKey('course_content_versions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('syllabus_node_id', UUID(as_uuid=True), sa.ForeignKey('syllabus_nodes.id', ondelete='SET NULL'), nullable=True),
        sa.Column('concept_id', UUID(as_uuid=True), sa.ForeignKey('concepts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('objective_code', sa.String(length=50), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('bloom_level', sa.String(length=30), server_default='understand', nullable=False),
        sa.Column('sequence_no', sa.Integer(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_learning_objectives_inst', 'learning_objectives', ['institution_id'])
    op.create_index('ix_learning_objectives_version', 'learning_objectives', ['course_content_version_id'])


def downgrade() -> None:
    op.drop_table('learning_objectives')
    op.drop_table('course_content_concepts')
    op.drop_table('concept_versions')
    op.drop_table('concepts')
    op.drop_table('syllabus_nodes')
    op.drop_table('course_content_versions')

