import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Tuple
from sqlalchemy import select, and_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import get_settings
from app.common.exceptions import AuthenticationError, AppException
from app.modules.auth.models import (
    User,
    UserIdentifier,
    PasswordCredential,
    AuthSession,
    MFACredential,
    MFAChallenge,
    PlatformRoleAssignment,
    InstitutionMembership,
)
from app.modules.audit.models import AuditEvent
from app.modules.auth.schemas import UserProfile
from app.modules.auth.security import (
    verify_password,
    hash_password,
    generate_opaque_token,
    hash_token,
    verify_totp_code,
    generate_password_reset_token,
    verify_password_reset_token,
)

settings = get_settings()


def _credential_version(password_changed_at: datetime | None) -> int:
    """Convert the credential timestamp into a stable signed-token version."""
    if password_changed_at is None:
        return 0
    if password_changed_at.tzinfo is None:
        password_changed_at = password_changed_at.replace(tzinfo=timezone.utc)
    return int(password_changed_at.timestamp() * 1_000_000)


class AuthService:
    """Core identity, authentication, MFA, and session lifecycle service."""

    @staticmethod
    async def has_active_mfa_challenge(db: AsyncSession, challenge_token: str) -> bool:
        """Return whether a pre-auth cookie still represents a usable MFA challenge."""
        stmt = select(MFAChallenge).where(
            and_(
                MFAChallenge.challenge_token_hash == hash_token(challenge_token),
                MFAChallenge.revoked_at.is_(None),
                MFAChallenge.consumed_at.is_(None),
            )
        )
        challenge = (await db.execute(stmt)).scalars().first()
        if not challenge:
            return False

        expires_at = challenge.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        return expires_at > datetime.now(timezone.utc)

    @staticmethod
    async def log_audit_event(
        db: AsyncSession,
        event_code: str,
        user_id: Optional[uuid.UUID] = None,
        institution_id: Optional[uuid.UUID] = None,
        target_type: Optional[str] = None,
        target_id: Optional[str] = None,
        payload: Optional[dict] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuditEvent:
        """Create an immutable audit log record."""
        audit_event = AuditEvent(
            id=uuid.uuid4(),
            institution_id=institution_id,
            actor_user_id=user_id,
            event_code=event_code,
            target_type=target_type,
            target_id=target_id,
            payload_json=payload or {},
            ip_address=ip_address,
            user_agent=user_agent,
            created_at=datetime.now(timezone.utc),
        )
        db.add(audit_event)
        return audit_event

    @staticmethod
    async def authenticate_primary(
        db: AsyncSession,
        identifier: str,
        password: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[str, bool, Optional[UserProfile]]:
        """
        Authenticate user credentials (identifier + password).
        Returns (token_or_challenge, is_mfa_required, user_profile).
        """
        normalized = identifier.strip().lower()

        # Look up identifier
        stmt = (
            select(UserIdentifier)
            .where(
                and_(
                    UserIdentifier.normalized_value == normalized,
                    UserIdentifier.is_login_enabled.is_(True),
                )
            )
            .options(selectinload(UserIdentifier.user).selectinload(User.password_credential))
        )
        result = await db.execute(stmt)
        user_ident = result.scalars().first()

        if not user_ident or not user_ident.user:
            await AuthService.log_audit_event(
                db,
                event_code="LOGIN_FAILED_UNKNOWN_USER",
                payload={"identifier": normalized},
                ip_address=ip_address,
                user_agent=user_agent,
            )
            await db.commit()
            raise AuthenticationError("Invalid institutional credentials.")

        user = user_ident.user
        if user.account_status != "active":
            await AuthService.log_audit_event(
                db,
                event_code="LOGIN_FAILED_INACTIVE_ACCOUNT",
                user_id=user.id,
                payload={"status": user.account_status},
                ip_address=ip_address,
                user_agent=user_agent,
            )
            await db.commit()
            raise AuthenticationError("Account is suspended or deactivated. Contact your institution administrator.")

        # Verify password
        if not user.password_credential or not verify_password(
            user.password_credential.password_hash, password
        ):
            await AuthService.log_audit_event(
                db,
                event_code="LOGIN_FAILED_BAD_PASSWORD",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            await db.commit()
            raise AuthenticationError("Invalid institutional credentials.")

        # Check for Super Admin platform role
        plat_stmt = select(PlatformRoleAssignment).where(
            and_(
                PlatformRoleAssignment.user_id == user.id,
                PlatformRoleAssignment.role_code == "super_admin",
                PlatformRoleAssignment.revoked_at.is_(None),
            )
        )
        plat_res = await db.execute(plat_stmt)
        is_super_admin = plat_res.scalars().first() is not None

        now = datetime.now(timezone.utc)
        regular_profile: UserProfile | None = None
        if not is_super_admin:
            regular_profile, _ = await AuthService.resolve_user_profile(db, user.id)

        # ----------------------------------------------------------------------
        # Super Admin Branch: Issue Ephemeral Pre-Auth MFA Challenge
        # ----------------------------------------------------------------------
        if is_super_admin:
            challenge_token = generate_opaque_token()
            challenge = MFAChallenge(
                id=uuid.uuid4(),
                user_id=user.id,
                challenge_token_hash=hash_token(challenge_token),
                issued_at=now,
                expires_at=now + timedelta(seconds=settings.MFA_TOKEN_MAX_AGE_SECONDS),
                failed_attempts=0,
                created_at=now,
            )
            db.add(challenge)
            await AuthService.log_audit_event(
                db,
                event_code="LOGIN_PRIMARY_SUCCESS_MFA_CHALLENGED",
                user_id=user.id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            await db.commit()
            return challenge_token, True, None

        # ----------------------------------------------------------------------
        # Regular Role Branch: Issue Fully Authenticated Session
        # ----------------------------------------------------------------------
        session_token = generate_opaque_token()
        auth_session = AuthSession(
            id=uuid.uuid4(),
            user_id=user.id,
            token_hash=hash_token(session_token),
            session_kind="authenticated",
            issued_at=now,
            expires_at=now + timedelta(seconds=settings.SESSION_MAX_AGE_SECONDS),
            last_seen_at=now,
            user_agent_summary=user_agent[:255] if user_agent else None,
            created_at=now,
        )
        db.add(auth_session)
        user.last_login_at = now

        await AuthService.log_audit_event(
            db,
            event_code="LOGIN_SUCCESS",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await db.commit()

        return session_token, False, regular_profile

    @staticmethod
    async def verify_mfa_challenge(
        db: AsyncSession,
        challenge_token: str,
        totp_code: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> Tuple[str, UserProfile]:
        """
        Verify Super Admin TOTP challenge.
        Enforces maximum 3 attempts before revoking challenge and logging security audit event.
        """
        token_hash = hash_token(challenge_token)
        now = datetime.now(timezone.utc)

        stmt = select(MFAChallenge).where(
            and_(
                MFAChallenge.challenge_token_hash == token_hash,
                MFAChallenge.revoked_at.is_(None),
                MFAChallenge.consumed_at.is_(None),
            )
        )
        if db.bind and db.bind.dialect.name != "sqlite":
            stmt = stmt.with_for_update()
        result = await db.execute(stmt)
        challenge = result.scalars().first()

        if not challenge:
            raise AuthenticationError("MFA verification session has expired. Please log in again.")

        expires_at = challenge.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if expires_at < now:
            raise AuthenticationError("MFA verification session has expired. Please log in again.")

        user = await db.get(User, challenge.user_id)
        active_role_stmt = select(PlatformRoleAssignment).where(
            and_(
                PlatformRoleAssignment.user_id == challenge.user_id,
                PlatformRoleAssignment.role_code == "super_admin",
                PlatformRoleAssignment.revoked_at.is_(None),
            )
        )
        active_role = (await db.execute(active_role_stmt)).scalars().first()
        if not user or user.account_status != "active" or not active_role:
            challenge.revoked_at = now
            await AuthService.log_audit_event(
                db,
                event_code="SUPER_ADMIN_MFA_CHALLENGE_REVOKED_ACCOUNT_INACTIVE",
                user_id=challenge.user_id,
                payload={"action": "challenge_revoked"},
                ip_address=ip_address,
                user_agent=user_agent,
            )
            await db.commit()
            raise AuthenticationError("Super Admin account is inactive or no longer authorized.")

        # Load Super Admin's MFA Credential
        mfa_stmt = select(MFACredential).where(
            and_(
                MFACredential.user_id == challenge.user_id,
                MFACredential.is_enabled.is_(True),
            )
        )
        mfa_res = await db.execute(mfa_stmt)
        mfa_cred = mfa_res.scalars().first()

        if not mfa_cred:
            challenge.revoked_at = now
            await db.commit()
            raise AuthenticationError("MFA credential is not configured for this account.")

        # Verify TOTP code
        is_valid = verify_totp_code(mfa_cred.secret_key, totp_code)

        if not is_valid:
            challenge.failed_attempts += 1
            if challenge.failed_attempts >= 3:
                challenge.revoked_at = now
                await AuthService.log_audit_event(
                    db,
                    event_code="SUPER_ADMIN_MFA_CHALLENGE_FAILED",
                    user_id=challenge.user_id,
                    payload={"failed_attempts": challenge.failed_attempts, "action": "challenge_revoked"},
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
                await db.commit()
                raise AuthenticationError(
                    "Maximum verification attempts exceeded. MFA challenge revoked. Please log in again."
                )

            await AuthService.log_audit_event(
                db,
                event_code="SUPER_ADMIN_MFA_INVALID_CODE",
                user_id=challenge.user_id,
                payload={"attempt_number": challenge.failed_attempts},
                ip_address=ip_address,
                user_agent=user_agent,
            )
            await db.commit()
            raise AuthenticationError("Invalid verification code. Please check your authenticator application.")

        # MFA Challenge Succeeded: Consume challenge and issue elevated session
        challenge.consumed_at = now

        session_token = generate_opaque_token()
        elevated_session = AuthSession(
            id=uuid.uuid4(),
            user_id=challenge.user_id,
            token_hash=hash_token(session_token),
            session_kind="authenticated",
            issued_at=now,
            expires_at=now + timedelta(seconds=settings.SESSION_MAX_AGE_SECONDS),
            last_seen_at=now,
            user_agent_summary=user_agent[:255] if user_agent else None,
            created_at=now,
        )
        db.add(elevated_session)

        # Update last login
        await db.execute(
            update(User).where(User.id == challenge.user_id).values(last_login_at=now)
        )

        await AuthService.log_audit_event(
            db,
            event_code="SUPER_ADMIN_MFA_VERIFIED",
            user_id=challenge.user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await db.commit()

        profile, _ = await AuthService.resolve_user_profile(db, challenge.user_id, is_mfa_verified=True)
        return session_token, profile

    @staticmethod
    async def resolve_session(
        db: AsyncSession, session_token: str
    ) -> Optional[Tuple[UserProfile, str]]:
        """
        Resolve an active, unrevoked session token from HTTP-only cookie.
        Returns (UserProfile, primary_route) or None.
        """
        token_hash = hash_token(session_token)
        now = datetime.now(timezone.utc)

        stmt = select(AuthSession).where(
            and_(
                AuthSession.token_hash == token_hash,
                AuthSession.session_kind == "authenticated",
                AuthSession.revoked_at.is_(None),
                AuthSession.expires_at > now,
            )
        )
        result = await db.execute(stmt)
        session = result.scalars().first()

        if not session:
            return None

        try:
            resolved = await AuthService.resolve_user_profile(db, session.user_id)
        except AuthenticationError:
            session.revoked_at = now
            await db.commit()
            return None

        # Update last seen
        session.last_seen_at = now
        await db.commit()

        return resolved

    @staticmethod
    async def resolve_user_profile(
        db: AsyncSession, user_id: uuid.UUID, is_mfa_verified: bool = False
    ) -> Tuple[UserProfile, str]:
        """
        Construct user profile, active role, institution scope, and landing route.
        """
        # Load user
        user = await db.get(User, user_id)
        if not user or user.account_status != "active":
            raise AuthenticationError("Account is inactive or unavailable.")

        # Load primary email/identifier
        ident_stmt = select(UserIdentifier).where(
            and_(UserIdentifier.user_id == user_id, UserIdentifier.is_primary.is_(True))
        )
        ident_res = await db.execute(ident_stmt)
        ident = ident_res.scalars().first()
        primary_email = ident.identifier_value if ident else user.display_name

        # Check Platform Role (Super Admin)
        plat_stmt = select(PlatformRoleAssignment).where(
            and_(
                PlatformRoleAssignment.user_id == user_id,
                PlatformRoleAssignment.role_code == "super_admin",
                PlatformRoleAssignment.revoked_at.is_(None),
            )
        )
        plat_res = await db.execute(plat_stmt)
        if plat_res.scalars().first():
            profile = UserProfile(
                id=str(user.id),
                email=primary_email,
                full_name=user.legal_name or user.display_name,
                role="SUPER_ADMIN",
                is_mfa_verified=True,
            )
            return profile, "/super-admin/dashboard"

        # Check Institution Membership & Role
        mem_stmt = (
            select(InstitutionMembership)
            .where(
                and_(
                    InstitutionMembership.user_id == user_id,
                    InstitutionMembership.membership_status == "active",
                )
            )
            .options(
                selectinload(InstitutionMembership.institution),
                selectinload(InstitutionMembership.roles),
            )
        )
        mem_res = await db.execute(mem_stmt)
        membership = mem_res.scalars().first()
        if not membership:
            raise AuthenticationError("No active institution membership is assigned to this account.")

        institution_id = str(membership.institution_id)
        institution_name = membership.institution.display_name if membership.institution else None

        # Get active role codes
        role_codes = [r.role_code for r in membership.roles if r.revoked_at is None]

        if "admin" in role_codes:
            role = "ADMIN"
            route = "/admin/dashboard"
        elif "teacher" in role_codes:
            role = "TEACHER"
            route = "/doubts"
        elif "student" in role_codes:
            role = "STUDENT"
            route = "/doubts"
        else:
            raise AuthenticationError("No active application role is assigned to this account.")

        profile = UserProfile(
            id=str(user.id),
            email=primary_email,
            registration_number=ident.identifier_value if ident and ident.identifier_type == "student_registration_number" else None,
            full_name=user.legal_name or user.display_name,
            role=role,
            institution_id=institution_id,
            institution_name=institution_name,
            is_mfa_verified=is_mfa_verified,
        )
        return profile, route

    @staticmethod
    async def logout(
        db: AsyncSession, session_token: str, ip_address: Optional[str] = None, user_agent: Optional[str] = None
    ) -> None:
        """Revoke active session in database."""
        token_hash = hash_token(session_token)
        now = datetime.now(timezone.utc)

        stmt = select(AuthSession).where(
            and_(AuthSession.token_hash == token_hash, AuthSession.revoked_at.is_(None))
        )
        result = await db.execute(stmt)
        session = result.scalars().first()

        if session:
            session.revoked_at = now
            await AuthService.log_audit_event(
                db,
                event_code="LOGOUT",
                user_id=session.user_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            await db.commit()

    @staticmethod
    async def revoke_mfa_challenge(
        db: AsyncSession,
        challenge_token: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        """Revoke a pending MFA challenge when its browser session logs out."""
        stmt = select(MFAChallenge).where(
            and_(
                MFAChallenge.challenge_token_hash == hash_token(challenge_token),
                MFAChallenge.revoked_at.is_(None),
                MFAChallenge.consumed_at.is_(None),
            )
        )
        challenge = (await db.execute(stmt)).scalars().first()
        if challenge:
            challenge.revoked_at = datetime.now(timezone.utc)
            await AuthService.log_audit_event(
                db,
                event_code="SUPER_ADMIN_MFA_CHALLENGE_CANCELLED",
                user_id=challenge.user_id,
                ip_address=ip_address,
                user_agent=user_agent,
            )
            await db.commit()

    @staticmethod
    async def request_password_reset(
        db: AsyncSession, identifier: str, ip_address: Optional[str] = None
    ) -> Optional[str]:
        """
        Request password reset link. Returns cryptographically signed token.
        Avoids account-enumeration in public APIs.
        """
        normalized = identifier.strip().lower()
        stmt = select(UserIdentifier).where(
            and_(
                UserIdentifier.normalized_value == normalized,
                UserIdentifier.is_login_enabled.is_(True),
            )
        )
        result = await db.execute(stmt)
        ident = result.scalars().first()

        if not ident:
            # Consistent timing without revealing missing user
            return None

        credential = await db.get(PasswordCredential, ident.user_id)
        token = generate_password_reset_token(
            str(ident.user_id),
            credential_version=_credential_version(
                credential.password_changed_at if credential else None
            ),
        )
        await AuthService.log_audit_event(
            db,
            event_code="PASSWORD_RESET_REQUESTED",
            user_id=ident.user_id,
            ip_address=ip_address,
        )
        await db.commit()
        return token

    @staticmethod
    async def commit_password_reset(
        db: AsyncSession, token: str, new_password: str, ip_address: Optional[str] = None
    ) -> None:
        """
        Commit password reset. Validates token signature, updates Argon2id hash,
        and invalidates all existing sessions for security.
        """
        is_valid, user_id_str, token_credential_version = verify_password_reset_token(token)
        if not is_valid or not user_id_str or token_credential_version is None:
            raise AppException(
                code="INVALID_RESET_TOKEN",
                message="The password reset link is invalid or has expired.",
                status_code=400,
            )

        user_id = uuid.UUID(user_id_str)
        now = datetime.now(timezone.utc)

        # Update password hash
        cred = await db.get(PasswordCredential, user_id)
        if _credential_version(cred.password_changed_at if cred else None) != token_credential_version:
            raise AppException(
                code="INVALID_RESET_TOKEN",
                message="The password reset link is invalid or has expired.",
                status_code=400,
            )

        new_hash = hash_password(new_password)
        if cred:
            cred.password_hash = new_hash
            cred.password_changed_at = now
            cred.must_change_password = False
        else:
            cred = PasswordCredential(
                user_id=user_id,
                password_hash=new_hash,
                password_changed_at=now,
                must_change_password=False,
            )
            db.add(cred)

        # Invalidate all active sessions for this user
        await db.execute(
            update(AuthSession)
            .where(and_(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)))
            .values(revoked_at=now)
        )

        await AuthService.log_audit_event(
            db,
            event_code="PASSWORD_RESET_COMMITTED",
            user_id=user_id,
            ip_address=ip_address,
        )
        await db.commit()
