import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.config import get_settings
from app.database import engine
from app.common.errors import register_error_handlers
from app.modules.auth.router import router as auth_router
from app.modules.academics.router import router as academics_router, offerings_router
from app.modules.sources.router import router as sources_router
from app.modules.knowledge.router import router as knowledge_router
from app.modules.questions.router import router as questions_router
from app.modules.learning.router import router as learning_router
from app.modules.assessments.router import router as assessments_router
from app.modules.analytics.router import router as analytics_router
from app.modules.interventions.router import router as interventions_router
from app.modules.doubts.router import router as doubts_router
from app.modules.notifications.router import router as notifications_router
from app.modules.audit.router import router as audit_router
from app.modules.institutions.router import router as institutions_router
from app.modules.rbac.dependencies import (
    require_super_admin,
    require_institution_admin,
    require_teacher,
    require_student,
    enforce_tenant_boundary,
    get_current_user,
)
from app.modules.auth.schemas import UserProfile
from fastapi import Depends
from app.common.gemini_client import gemini_gateway

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("doubtdesk.api")
settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle management."""
    logger.info(f"Starting {settings.APP_NAME} in {settings.APP_ENV} mode...")
    
    # Ensure local upload directories exist
    settings.LOCAL_STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    
    yield
    
    logger.info("Shutting down database connections...")
    await engine.dispose()
    logger.info("Shutdown complete.")


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception handlers
register_error_handlers(app)


@app.get("/health", tags=["System"])
async def health_check() -> dict:
    """Liveness probe: verifies API process is alive."""
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "env": settings.APP_ENV,
        "version": "1.0.0",
    }


@app.get("/ready", tags=["System"])
async def readiness_check() -> JSONResponse:
    """Readiness probe: verifies database connectivity and core infrastructure."""
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "status": "ready",
                "database": "connected",
                "storage": settings.STORAGE_TYPE,
            },
        )
    except Exception:
        # Driver exceptions can include the full connection URL, including credentials.
        logger.error("Readiness check failed: database connectivity is unavailable.")
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={
                "status": "not_ready",
                "database": "disconnected",
                "error": "Database connectivity is unavailable.",
            },
        )


# Register Modules Routers
app.include_router(auth_router, prefix=settings.API_V1_PREFIX)
app.include_router(academics_router, prefix=settings.API_V1_PREFIX)
app.include_router(offerings_router, prefix=settings.API_V1_PREFIX)
app.include_router(sources_router, prefix=settings.API_V1_PREFIX)
app.include_router(knowledge_router, prefix=settings.API_V1_PREFIX)
app.include_router(questions_router, prefix=settings.API_V1_PREFIX)
app.include_router(learning_router, prefix=settings.API_V1_PREFIX)
app.include_router(assessments_router, prefix=settings.API_V1_PREFIX)
app.include_router(analytics_router, prefix=settings.API_V1_PREFIX)
app.include_router(interventions_router, prefix=settings.API_V1_PREFIX)
app.include_router(doubts_router, prefix=settings.API_V1_PREFIX)
app.include_router(notifications_router, prefix=settings.API_V1_PREFIX)
app.include_router(audit_router, prefix=settings.API_V1_PREFIX)
app.include_router(institutions_router, prefix=settings.API_V1_PREFIX)


# Protected Test & RBAC Probe Endpoints
@app.get(f"{settings.API_V1_PREFIX}/protected/super-admin", tags=["RBAC Probe"])
async def probe_super_admin(user: UserProfile = Depends(require_super_admin)) -> dict:
    return {"message": "Super Admin access granted", "user_id": user.id}


@app.get(f"{settings.API_V1_PREFIX}/protected/admin", tags=["RBAC Probe"])
async def probe_admin(user: UserProfile = Depends(require_institution_admin)) -> dict:
    return {"message": "Institution Admin access granted", "institution_id": user.institution_id}


@app.get(f"{settings.API_V1_PREFIX}/protected/teacher", tags=["RBAC Probe"])
async def probe_teacher(user: UserProfile = Depends(require_teacher)) -> dict:
    return {"message": "Faculty access granted", "user_id": user.id}


@app.get(f"{settings.API_V1_PREFIX}/protected/student", tags=["RBAC Probe"])
async def probe_student(user: UserProfile = Depends(require_student)) -> dict:
    return {"message": "Student access granted", "user_id": user.id}


@app.get(f"{settings.API_V1_PREFIX}/protected/tenant/{{target_institution_id}}", tags=["RBAC Probe"])
async def probe_tenant_access(
    target_institution_id: str, user: UserProfile = Depends(get_current_user)
) -> dict:
    enforce_tenant_boundary(target_institution_id, user)
    return {"message": "Tenant boundary verified", "target_institution_id": target_institution_id}


@app.get(f"{settings.API_V1_PREFIX}/ping", tags=["System"])
async def api_v1_ping() -> dict:
    """API v1 ping test endpoint."""
    return {"message": "DoubtDesk API v1 is operational"}


@app.get(f"{settings.API_V1_PREFIX}/system/gemini-telemetry", tags=["System"])
async def get_gemini_telemetry() -> dict:
    """Real-time Gemini gateway metrics, quota limits, circuit breaker, and cache hit ratios."""
    return gemini_gateway.get_telemetry()


