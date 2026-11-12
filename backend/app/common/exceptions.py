from typing import Any, Dict, Optional
from fastapi import status


class AppException(Exception):
    """Base application exception for all domain errors."""
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class AuthenticationError(AppException):
    def __init__(self, message: str = "Invalid credentials", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="AUTHENTICATION_FAILED",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


class MFARequiredError(AppException):
    def __init__(self, message: str = "Second-factor MFA verification required", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="MFA_REQUIRED",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


class AuthorizationError(AppException):
    def __init__(self, message: str = "Access forbidden", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="ACCESS_FORBIDDEN",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class NotFoundError(AppException):
    def __init__(self, message: str = "Resource not found", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="RESOURCE_NOT_FOUND",
            message=message,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class ConflictError(AppException):
    def __init__(self, message: str = "Resource conflict", details: Optional[Dict[str, Any]] = None):
        super().__init__(
            code="RESOURCE_CONFLICT",
            message=message,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class InterventionPhaseLockedError(AppException):
    def __init__(self, required_phase: str, message: str = "Intervention phase is locked"):
        super().__init__(
            code="INTERVENTION_PHASE_LOCKED",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
            details={"required_phase": required_phase},
        )

