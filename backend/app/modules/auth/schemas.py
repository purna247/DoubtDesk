from typing import Optional
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    identifier: str = Field(..., description="Student registration number or institutional email")
    password: str = Field(..., min_length=1, description="Account password")


class LoginResponse(BaseModel):
    success: bool
    mfa_required: bool = False
    message: str = "Authentication successful"
    redirect_url: str = "/doubts"


class MFAVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=6, description="6-digit TOTP code")


class UserProfile(BaseModel):
    id: str
    email: str
    registration_number: Optional[str] = None
    full_name: str
    avatar_url: Optional[str] = None
    role: str  # SUPER_ADMIN | ADMIN | TEACHER | STUDENT
    institution_id: Optional[str] = None
    institution_name: Optional[str] = None
    is_mfa_verified: bool = False


class AuthMeResponse(BaseModel):
    authenticated: bool
    mfa_required: bool = False
    user: Optional[UserProfile] = None
    primary_route: str = "/login"


class ForgotPasswordRequest(BaseModel):
    identifier: str = Field(..., description="Registered email or student registration number")


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., description="Cryptographically signed reset token")
    new_password: str = Field(..., min_length=8, description="New password (at least 8 chars)")

