from typing import Optional
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database import get_db
from app.common.exceptions import AuthenticationError
from app.modules.auth.schemas import (
    LoginRequest,
    LoginResponse,
    MFAVerifyRequest,
    AuthMeResponse,
    ForgotPasswordRequest,
    ResetPasswordRequest,
)
from app.modules.auth.service import AuthService

settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Authentication"])

PRE_AUTH_COOKIE_NAME = "doubtdesk_pre_auth"


def _get_client_ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def _get_user_agent(request: Request) -> Optional[str]:
    return request.headers.get("user-agent")


@router.post("/login", response_model=LoginResponse, summary="Primary Credential Login")
async def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """
    Authenticate user via identifier (email / student registration number) and password.
    For regular roles, sets secure session cookie.
    For Super Admin, branches to mandatory second-factor MFA challenge.
    """
    token_or_challenge, is_mfa_required, profile = await AuthService.authenticate_primary(
        db=db,
        identifier=req.identifier,
        password=req.password,
        ip_address=_get_client_ip(request),
        user_agent=_get_user_agent(request),
    )

    if is_mfa_required:
        # Issue short-lived pre-auth MFA challenge cookie
        response.set_cookie(
            key=PRE_AUTH_COOKIE_NAME,
            value=token_or_challenge,
            max_age=settings.MFA_TOKEN_MAX_AGE_SECONDS,
            httponly=True,
            secure=settings.SESSION_COOKIE_SECURE,
            samesite=settings.SESSION_COOKIE_SAMESITE,
            path="/",
        )
        return LoginResponse(
            success=True,
            mfa_required=True,
            message="Second-factor authentication challenge required.",
            redirect_url="/login/mfa",
        )

    # Standard Role: Set fully authenticated session cookie and discard stale MFA state.
    response.delete_cookie(key=PRE_AUTH_COOKIE_NAME, path="/")
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=token_or_challenge,
        max_age=settings.SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        path="/",
    )

    # Determine primary landing route
    primary_route = "/doubts"
    if profile:
        if profile.role == "ADMIN":
            primary_route = "/admin/dashboard"
        elif profile.role == "TEACHER":
            primary_route = "/teacher/dashboard"

    return LoginResponse(
        success=True,
        mfa_required=False,
        message="Authentication successful",
        redirect_url=primary_route,
    )


@router.post("/mfa/verify", response_model=LoginResponse, summary="Super Admin MFA Verification")
async def verify_mfa(
    req: MFAVerifyRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """
    Verify 6-digit TOTP code for Super Admin accounts.
    Issues elevated session cookie upon success; enforces 3-attempt lockout.
    """
    challenge_token = request.cookies.get(PRE_AUTH_COOKIE_NAME)
    if not challenge_token:
        raise AuthenticationError("No pending MFA challenge found. Please sign in again.")

    session_token, _ = await AuthService.verify_mfa_challenge(
        db=db,
        challenge_token=challenge_token,
        totp_code=req.code,
        ip_address=_get_client_ip(request),
        user_agent=_get_user_agent(request),
    )

    # Issue elevated session cookie
    response.set_cookie(
        key=settings.SESSION_COOKIE_NAME,
        value=session_token,
        max_age=settings.SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.SESSION_COOKIE_SECURE,
        samesite=settings.SESSION_COOKIE_SAMESITE,
        path="/",
    )
    # Clear ephemeral pre-auth cookie
    response.delete_cookie(key=PRE_AUTH_COOKIE_NAME, path="/")

    return LoginResponse(
        success=True,
        mfa_required=False,
        message="MFA challenge verified. Session elevated.",
        redirect_url="/super-admin/dashboard",
    )


@router.get("/me", response_model=AuthMeResponse, summary="Authoritative Session Resolution")
async def get_me(request: Request, db: AsyncSession = Depends(get_db)) -> AuthMeResponse:
    """
    Authoritatively resolve current authenticated session identity, role, and tenant scope.
    Returns authenticated: false if no valid session cookie is active.
    """
    session_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    challenge_token = request.cookies.get(PRE_AUTH_COOKIE_NAME)
    if session_token:
        resolved = await AuthService.resolve_session(db, session_token)
        if resolved:
            profile, route = resolved
            return AuthMeResponse(authenticated=True, user=profile, primary_route=route)

    mfa_required = bool(
        challenge_token and await AuthService.has_active_mfa_challenge(db, challenge_token)
    )
    return AuthMeResponse(
        authenticated=False,
        mfa_required=mfa_required,
        user=None,
        primary_route="/login/mfa" if mfa_required else "/login",
    )


@router.post("/logout", summary="Session Invalidation")
async def logout(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Revoke active session in database and delete cookies.
    """
    session_token = request.cookies.get(settings.SESSION_COOKIE_NAME)
    challenge_token = request.cookies.get(PRE_AUTH_COOKIE_NAME)
    if session_token:
        await AuthService.logout(
            db=db,
            session_token=session_token,
            ip_address=_get_client_ip(request),
            user_agent=_get_user_agent(request),
        )
    if challenge_token:
        await AuthService.revoke_mfa_challenge(
            db=db,
            challenge_token=challenge_token,
            ip_address=_get_client_ip(request),
            user_agent=_get_user_agent(request),
        )

    response.delete_cookie(key=settings.SESSION_COOKIE_NAME, path="/")
    response.delete_cookie(key=PRE_AUTH_COOKIE_NAME, path="/")
    return {"message": "Session terminated successfully."}


@router.post("/forgot-password", summary="Request Password Reset Link")
async def forgot_password(
    req: ForgotPasswordRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Generate cryptographically signed, time-limited reset link.
    Never exposes whether an account exists.
    """
    token = await AuthService.request_password_reset(
        db=db, identifier=req.identifier, ip_address=_get_client_ip(request)
    )

    # In local development mode, if DEBUG is True, we can expose the token in details for testing
    details = {}
    if settings.DEBUG and token:
        details["dev_reset_token"] = token

    return {
        "message": "If an account matches this identifier, a password recovery link has been dispatched.",
        **details,
    }


@router.post("/reset-password", summary="Commit Password Reset")
async def reset_password(
    req: ResetPasswordRequest, request: Request, db: AsyncSession = Depends(get_db)
) -> dict:
    """
    Verify reset token signature and commit new Argon2id password hash.
    Invalidates all active sessions for that account.
    """
    await AuthService.commit_password_reset(
        db=db,
        token=req.token,
        new_password=req.new_password,
        ip_address=_get_client_ip(request),
    )
    return {"message": "Password updated successfully. You may now sign in."}

