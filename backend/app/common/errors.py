import logging
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from app.common.exceptions import AppException

logger = logging.getLogger("doubtdesk.errors")


def register_error_handlers(app: FastAPI) -> None:
    """Register uniform JSON error envelopes for all unhandled and domain exceptions."""

    @app.exception_handler(AppException)
    async def app_exception_handler(_request: Request, exc: AppException) -> JSONResponse:
        logger.warning(f"Domain exception: code={exc.code} status={exc.status_code} msg={exc.message}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(_request: Request, exc: RequestValidationError) -> JSONResponse:
        # Validation inputs may contain passwords, MFA codes, reset tokens, or uploaded data.
        safe_errors = [
            {key: error[key] for key in ("loc", "type", "msg") if key in error}
            for error in exc.errors()
        ]
        logger.warning("Request validation failed (%d field errors).", len(safe_errors))
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid request parameters or payload",
                    "details": {"validation_errors": jsonable_encoder(safe_errors)},
                }
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        # Exception messages can include connection strings or request-controlled content.
        logger.error(
            "Unhandled server error at %s (%s).",
            _request.url.path,
            type(exc).__name__,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected server error occurred",
                    "details": {},
                }
            },
        )

