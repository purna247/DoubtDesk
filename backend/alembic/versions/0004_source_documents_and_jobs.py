"""Source document storage, extraction provenance, and persistent background jobs.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-11 10:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = '0004'
down_revision: Union[str, None] = '0003'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Source Documents
    op.create_table(
        'source_documents',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('uploaded_by_membership_id', UUID(as_uuid=True), sa.ForeignKey('institution_memberships.id', ondelete='CASCADE'), nullable=False),
        sa.Column('original_filename', sa.Text(), nullable=False),
        sa.Column('display_filename', sa.Text(), nullable=False),
        sa.Column('storage_backend', sa.String(length=20), server_default='local', nullable=False),
        sa.Column('storage_key', sa.Text(), nullable=False, unique=True),
        sa.Column('mime_type', sa.String(length=100), nullable=False),
        sa.Column('file_extension', sa.String(length=20), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('sha256_checksum', sa.String(length=64), nullable=False),
        sa.Column('source_type', sa.String(length=30), server_default='syllabus', nullable=False),
        sa.Column('status', sa.String(length=20), server_default='uploaded', nullable=False),
        sa.Column('visibility', sa.String(length=20), server_default='course', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_source_documents_inst_status', 'source_documents', ['institution_id', 'status'])

    # 2. Scope Links
    op.create_table(
        'source_document_course_offerings',
        sa.Column('source_document_id', UUID(as_uuid=True), sa.ForeignKey('source_documents.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('course_offering_id', UUID(as_uuid=True), sa.ForeignKey('course_offerings.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('source_document_id', 'course_offering_id', name='uq_src_doc_course_offering'),
    )

    op.create_table(
        'source_document_curriculum_versions',
        sa.Column('source_document_id', UUID(as_uuid=True), sa.ForeignKey('source_documents.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('curriculum_version_id', UUID(as_uuid=True), sa.ForeignKey('curriculum_versions.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('source_document_id', 'curriculum_version_id', name='uq_src_doc_curriculum_ver'),
    )

    # 3. Source Extractions
    op.create_table(
        'source_extractions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_document_id', UUID(as_uuid=True), sa.ForeignKey('source_documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('extractor_name', sa.String(length=50), nullable=False),
        sa.Column('extractor_version', sa.String(length=30), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='queued', nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('warnings_json', JSONB, nullable=True),
        sa.Column('error_code', sa.String(length=50), nullable=True),
        sa.Column('safe_error_summary', sa.Text(), nullable=True),
        sa.Column('raw_text_checksum', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 4. Source Chunks
    op.create_table(
        'source_chunks',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_document_id', UUID(as_uuid=True), sa.ForeignKey('source_documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_extraction_id', UUID(as_uuid=True), sa.ForeignKey('source_extractions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('chunk_index', sa.Integer(), nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('slide_number', sa.Integer(), nullable=True),
        sa.Column('section_path', sa.Text(), nullable=True),
        sa.Column('chunk_type', sa.String(length=30), server_default='paragraph', nullable=False),
        sa.Column('content_text', sa.Text(), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('metadata_json', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('source_extraction_id', 'chunk_index', name='uq_src_chunk_idx'),
    )

    # 5. Source Assets
    op.create_table(
        'source_assets',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_document_id', UUID(as_uuid=True), sa.ForeignKey('source_documents.id', ondelete='CASCADE'), nullable=False),
        sa.Column('source_extraction_id', UUID(as_uuid=True), sa.ForeignKey('source_extractions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('storage_backend', sa.String(length=20), server_default='local', nullable=False),
        sa.Column('storage_key', sa.Text(), nullable=False),
        sa.Column('asset_type', sa.String(length=30), server_default='image', nullable=False),
        sa.Column('page_number', sa.Integer(), nullable=True),
        sa.Column('slide_number', sa.Integer(), nullable=True),
        sa.Column('surrounding_text', sa.Text(), nullable=True),
        sa.Column('sha256_checksum', sa.String(length=64), nullable=False),
        sa.Column('metadata_json', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 6. Background Jobs
    op.create_table(
        'background_jobs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=True),
        sa.Column('requested_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('job_type', sa.String(length=50), nullable=False),
        sa.Column('target_entity_type', sa.String(length=50), nullable=False),
        sa.Column('target_entity_id', UUID(as_uuid=True), nullable=True),
        sa.Column('scope_course_offering_id', UUID(as_uuid=True), sa.ForeignKey('course_offerings.id', ondelete='SET NULL'), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='queued', nullable=False),
        sa.Column('current_stage', sa.String(length=50), server_default='queued', nullable=False),
        sa.Column('progress_percent', sa.Numeric(precision=5, scale=2), server_default='0', nullable=False),
        sa.Column('attempt_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('max_attempts', sa.Integer(), server_default='3', nullable=False),
        sa.Column('lease_owner', sa.String(length=100), nullable=True),
        sa.Column('lease_expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('next_retry_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('idempotency_key', sa.String(length=100), nullable=True),
        sa.Column('input_reference_json', JSONB, nullable=True),
        sa.Column('checkpoint_json', JSONB, nullable=True),
        sa.Column('result_reference_json', JSONB, nullable=True),
        sa.Column('error_code', sa.String(length=50), nullable=True),
        sa.Column('safe_error_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_background_jobs_status_created', 'background_jobs', ['status', 'created_at'])
    op.create_index('ix_background_jobs_lease_expires', 'background_jobs', ['lease_expires_at'])

    # 7. Background Job Events
    op.create_table(
        'background_job_events',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('job_id', UUID(as_uuid=True), sa.ForeignKey('background_jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('stage_name', sa.String(length=50), nullable=True),
        sa.Column('progress_percent', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('message_safe', sa.Text(), nullable=False),
        sa.Column('details_json', JSONB, nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('background_job_events')
    op.drop_table('background_jobs')
    op.drop_table('source_assets')
    op.drop_table('source_chunks')
    op.drop_table('source_extractions')
    op.drop_table('source_document_curriculum_versions')
    op.drop_table('source_document_course_offerings')
    op.drop_table('source_documents')

