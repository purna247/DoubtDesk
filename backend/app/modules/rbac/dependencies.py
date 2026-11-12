from typing import List, Optional
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.common.exceptions import AuthenticationError, AuthorizationError
from app.modules.auth.schemas import UserProfile
from app.modules.auth.service import AuthService

settings = get_settings()


async def get_current_user(
    request: Request, db: AsyncSession = Depends(get_db)
) -> UserProfile:
    """
    FastAPI dependency that extracts and validates the secure HTTP-only session cookie.
    Rejects missing, expired, or pre-authentication MFA challenge cookies.
    """
    session_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    if not session_token:
        raise AuthenticationError("Authentication session required. Please sign in.")

    resolved = await AuthService.resolve_session(db, session_token)
    if not resolved:
        raise AuthenticationError("Session has expired or is invalid. Please sign in again.")

    user_profile, _ = resolved
    return user_profile


def require_role(*allowed_roles: str):
    """
    Role-based access control dependency factory.
    Enforces that the authenticated user possesses one of the allowed role codes.
    """
    async def role_checker(current_user: UserProfile = Depends(get_current_user)) -> UserProfile:
        if current_user.role not in allowed_roles:
            raise AuthorizationError(
                f"Access forbidden: Role '{current_user.role}' lacks permission for this endpoint."
            )
        return current_user

    return role_checker


# Named pre-configured role dependencies
require_super_admin = require_role("SUPER_ADMIN")
require_institution_admin = require_role("ADMIN", "SUPER_ADMIN")
require_teacher = require_role("TEACHER", "ADMIN", "SUPER_ADMIN")
require_student = require_role("STUDENT", "ADMIN", "SUPER_ADMIN")


def enforce_tenant_boundary(resource_institution_id: str, current_user: UserProfile) -> None:
    """
    Multi-tenant isolation validator.
    Ensures institution-scoped members cannot access records belonging to another institution.
    Super Admins are platform-scoped and bypass single-tenant limits for administration.
    """
    if current_user.role == "SUPER_ADMIN":
        return

    if not current_user.institution_id or current_user.institution_id != resource_institution_id:
        raise AuthorizationError("Tenant isolation violation: Access across institutions is forbidden.")

