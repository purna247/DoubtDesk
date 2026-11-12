"""Identity, authentication, tenant membership, and audit tables.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-11 09:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = '0002'
down_revision: Union[str, None] = '0001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Institutions
    op.create_table(
        'institutions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_code', sa.String(length=40), nullable=False, unique=True),
        sa.Column('legal_name', sa.Text(), nullable=False),
        sa.Column('display_name', sa.Text(), nullable=False),
        sa.Column('primary_domain', sa.Text(), nullable=True),
        sa.Column('logo_storage_key', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('timezone', sa.String(length=64), server_default='Asia/Kolkata', nullable=False),
        sa.Column('metadata_json', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_institutions_code', 'institutions', ['institution_code'])
    op.create_index('ix_institutions_domain', 'institutions', ['primary_domain'])

    # 2. Institution Settings
    op.create_table(
        'institution_settings',
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('allow_teacher_view_anonymous', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('min_distinct_questions_for_gap', sa.Integer(), server_default='3', nullable=False),
        sa.Column('weakness_accuracy_threshold', sa.Numeric(precision=5, scale=4), server_default='0.6000', nullable=False),
        sa.Column('default_upload_limit_mb', sa.Integer(), server_default='50', nullable=False),
        sa.Column('policy_json', JSONB(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 3. Users
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('display_name', sa.Text(), nullable=False),
        sa.Column('legal_name', sa.Text(), nullable=True),
        sa.Column('avatar_storage_key', sa.Text(), nullable=True),
        sa.Column('account_status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 4. User Identifiers
    op.create_table(
        'user_identifiers',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='RESTRICT'), nullable=False),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=True),
        sa.Column('identifier_type', sa.String(length=30), nullable=False),
        sa.Column('identifier_value', sa.Text(), nullable=False),
        sa.Column('normalized_value', sa.Text(), nullable=False),
        sa.Column('is_login_enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('is_primary', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('verified_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_user_identifiers_normalized', 'user_identifiers', ['normalized_value'])
    op.create_index('ix_user_identifiers_user', 'user_identifiers', ['user_id'])

    # 5. Password Credentials
    op.create_table(
        'password_credentials',
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('password_changed_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('must_change_password', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 6. Auth Sessions
    op.create_table(
        'auth_sessions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token_hash', sa.Text(), nullable=False, unique=True),
        sa.Column('session_kind', sa.String(length=20), server_default='authenticated', nullable=False),
        sa.Column('issued_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('user_agent_summary', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_auth_sessions_token_hash', 'auth_sessions', ['token_hash'])
    op.create_index('ix_auth_sessions_user_expires', 'auth_sessions', ['user_id', 'expires_at'])

    # 7. MFA Credentials
    op.create_table(
        'mfa_credentials',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('secret_key', sa.Text(), nullable=False),
        sa.Column('is_enabled', sa.Boolean(), server_default='true', nullable=False),
        sa.Column('enrolled_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # 8. MFA Challenges
    op.create_table(
        'mfa_challenges',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('challenge_token_hash', sa.Text(), unique=True, nullable=False),
        sa.Column('issued_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('failed_attempts', sa.Integer(), server_default='0', nullable=False),
        sa.Column('consumed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_mfa_challenges_token_hash', 'mfa_challenges', ['challenge_token_hash'])

    # 9. Platform Role Assignments
    op.create_table(
        'platform_role_assignments',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role_code', sa.String(length=30), server_default='super_admin', nullable=False),
        sa.Column('granted_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('granted_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('reason', sa.Text(), nullable=True),
    )

    # 10. Institution Memberships
    op.create_table(
        'institution_memberships',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('membership_status', sa.String(length=20), server_default='active', nullable=False),
        sa.Column('joined_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('institution_id', 'user_id', name='uq_institution_user_membership'),
    )

    # 11. Institution Membership Roles
    op.create_table(
        'institution_membership_roles',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('institution_membership_id', UUID(as_uuid=True), sa.ForeignKey('institution_memberships.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role_code', sa.String(length=30), nullable=False),
        sa.Column('granted_by_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('granted_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index('ix_inst_role_code', 'institution_membership_roles', ['institution_membership_id', 'role_code'])

    # 12. Audit Events
    op.create_table(
        'audit_events',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('institution_id', UUID(as_uuid=True), sa.ForeignKey('institutions.id', ondelete='SET NULL'), nullable=True),
        sa.Column('actor_user_id', UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('event_code', sa.String(length=64), nullable=False),
        sa.Column('target_type', sa.String(length=64), nullable=True),
        sa.Column('target_id', sa.Text(), nullable=True),
        sa.Column('payload_json', JSONB(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index('ix_audit_events_event_code', 'audit_events', ['event_code', 'created_at'])


def downgrade() -> None:
    op.drop_table('audit_events')
    op.drop_table('institution_membership_roles')
    op.drop_table('institution_memberships')
    op.drop_table('platform_role_assignments')
    op.drop_table('mfa_challenges')
    op.drop_table('mfa_credentials')
    op.drop_table('auth_sessions')
    op.drop_table('password_credentials')
    op.drop_table('user_identifiers')
    op.drop_table('users')
    op.drop_table('institution_settings')
    op.drop_table('institutions')

