"""Academic doubts, answers, comments, peer-anonymity safeguards, and audited disclosure.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-11 18:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = '0011'
down_revision: Union[str, None] = '0010'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Doubts
    op.create_table(
        'doubts',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('author_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('course_offering_id', UUID(as_uuid=True), sa.ForeignKey('course_offerings.id', ondelete='SET NULL'), nullable=True),
        sa.Column('canonical_subject_id', UUID(as_uuid=True), sa.ForeignKey('canonical_subjects.id', ondelete='SET NULL'), nullable=True),
        sa.Column('concept_id', UUID(as_uuid=True), sa.ForeignKey('concepts.id', ondelete='SET NULL'), nullable=True),
        sa.Column('question_id', UUID(as_uuid=True), sa.ForeignKey('questions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('body_markdown', sa.Text(), nullable=False),
        sa.Column('is_anonymous_to_peers', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('status', sa.String(20), nullable=False, server_default='open'),
        sa.Column('visibility', sa.String(20), nullable=False, server_default='course'),
        sa.Column('upvote_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('answer_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_doubts_institution', 'doubts', ['institution_id'])
    op.create_index('ix_doubts_author', 'doubts', ['author_user_id'])
    op.create_index('ix_doubts_offering', 'doubts', ['course_offering_id'])
    op.create_index('ix_doubts_concept', 'doubts', ['concept_id'])

    # 2. Doubt answers
    op.create_table(
        'doubt_answers',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('doubt_id', UUID(as_uuid=True), sa.ForeignKey('doubts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('author_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('body_markdown', sa.Text(), nullable=False),
        sa.Column('is_teacher_verified', sa.Boolean(), nullable=False, server_default=sa.text('false')),
        sa.Column('verified_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='published'),
        sa.Column('upvote_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_doubt_answers_inst', 'doubt_answers', ['institution_id'])
    op.create_index('ix_doubt_answers_doubt', 'doubt_answers', ['doubt_id'])
    op.create_index('ix_doubt_answers_author', 'doubt_answers', ['author_user_id'])

    # 3. Doubt comments
    op.create_table(
        'doubt_comments',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('doubt_id', UUID(as_uuid=True), sa.ForeignKey('doubts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('answer_id', UUID(as_uuid=True), sa.ForeignKey('doubt_answers.id', ondelete='CASCADE'), nullable=True),
        sa.Column('author_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('body_markdown', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='published'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_doubt_comments_inst', 'doubt_comments', ['institution_id'])
    op.create_index('ix_doubt_comments_doubt', 'doubt_comments', ['doubt_id'])
    op.create_index('ix_doubt_comments_answer', 'doubt_comments', ['answer_id'])

    # 4. Doubt votes
    op.create_table(
        'doubt_votes',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('doubt_id', UUID(as_uuid=True), sa.ForeignKey('doubts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('vote_type', sa.String(10), nullable=False, server_default='upvote'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.UniqueConstraint('doubt_id', 'user_id', 'vote_type', name='uq_doubt_user_vote'),
    )
    op.create_index('ix_doubt_votes_inst', 'doubt_votes', ['institution_id'])
    op.create_index('ix_doubt_votes_doubt', 'doubt_votes', ['doubt_id'])

    # 5. Doubt flags
    op.create_table(
        'doubt_flags',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('doubt_id', UUID(as_uuid=True), sa.ForeignKey('doubts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reported_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reason_code', sa.String(50), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='open'),
        sa.Column('resolved_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    )
    op.create_index('ix_doubt_flags_inst', 'doubt_flags', ['institution_id'])
    op.create_index('ix_doubt_flags_doubt', 'doubt_flags', ['doubt_id'])

    # 6. Doubt identity disclosure events
    op.create_table(
        'doubt_identity_disclosure_events',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('doubt_id', UUID(as_uuid=True), sa.ForeignKey('doubts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('author_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('actor_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('reason_code', sa.String(50), nullable=False),
        sa.Column('reason_text', sa.Text(), nullable=False),
        sa.Column('policy_basis', sa.String(100), nullable=False, server_default='moderation_investigation'),
        sa.Column('disclosed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('audit_event_id', UUID(as_uuid=True), sa.ForeignKey('audit_events.id', ondelete='SET NULL'), nullable=True),
    )
    op.create_index('ix_disclosure_inst', 'doubt_identity_disclosure_events', ['institution_id'])
    op.create_index('ix_disclosure_doubt', 'doubt_identity_disclosure_events', ['doubt_id'])
    op.create_index('ix_disclosure_actor', 'doubt_identity_disclosure_events', ['actor_user_id'])


def downgrade() -> None:
    op.drop_table('doubt_identity_disclosure_events')
    op.drop_table('doubt_flags')
    op.drop_table('doubt_votes')
    op.drop_table('doubt_comments')
    op.drop_table('doubt_answers')
    op.drop_table('doubts')

