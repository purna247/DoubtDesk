from functools import lru_cache
from pathlib import Path
from typing import List
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """
    Authoritative configuration for DoubtDesk Backend & Worker.
    Loads from the canonical v1/.env file or environment variables.
    """
    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
    )

    # Application
    APP_NAME: str = "DoubtDesk"
    APP_ENV: str = Field(default="development", description="development | staging | production")
    DEBUG: bool = Field(default=True)
    API_V1_PREFIX: str = "/api/v1"

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug_profile(cls, value):
        """Accept common build-profile values forwarded by the host environment."""
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"release", "production", "prod", "false", "0", "no", "off"}:
                return False
            if normalized in {"debug", "development", "dev", "true", "1", "yes", "on"}:
                return True
        return value

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]

    # Database
    DATABASE_URL: str = Field(default="", description="Async PostgreSQL connection URL")
    DATABASE_HOST: str | None = None
    DATABASE_PORT: int = Field(default=5432, ge=1, le=65535)
    POSTGRES_USER: str = "doubtdesk"
    POSTGRES_PASSWORD: SecretStr = SecretStr("doubtdesk")
    POSTGRES_DB: str = "doubtdesk"
    DATABASE_POOL_SIZE: int = Field(default=20)
    DATABASE_MAX_OVERFLOW: int = Field(default=10)
    DATABASE_ECHO: bool = Field(default=False)

    # Security & Sessions
    SECRET_KEY: str = Field(
        default="doubtdesk-local-insecure-secret-key-change-in-production-1234567890",
        description="Used for signing session hashes and cryptographically signed tokens",
    )
    SESSION_COOKIE_NAME: str = "doubtdesk_session"
    SESSION_MAX_AGE_SECONDS: int = 86400 * 7  # 7 days
    SESSION_COOKIE_SECURE: bool = Field(default=False, description="Set True in HTTPS production")
    SESSION_COOKIE_SAMESITE: str = "lax"  # lax for local dev navigation, strict in production

    # Multi-Factor Authentication (Super Admin)
    MFA_ISSUER_NAME: str = "DoubtDesk Platform"
    MFA_TOKEN_MAX_AGE_SECONDS: int = 300  # 5 minutes for pre-auth MFA challenge

    # Super Admin Bootstrap Credentials (loaded from .env, never hardcoded in source)
    SUPERADMIN_EMAIL: str = Field(default="", description="Bootstrap Super Admin email")
    SUPERADMIN_PASSWORD: str = Field(default="", description="Bootstrap Super Admin initial password")
    SUPERADMIN_TOTP_SECRET: str = Field(default="", description="Bootstrap Super Admin TOTP Base32 secret")

    # LLM & AI Services
    GEMINI_API_KEY: str = Field(default="", description="Gemini API Key")
    GEMINI_MODEL: str = Field(default="gemini-3.5-flash-lite", description="Primary Tier-1 Gemini model")
    GEMINI_FALLBACK_MODELS: str = Field(default="gemini-3.1-flash-lite,gemini-flash-lite-latest", description="Comma-separated Tier-1 fallback models")
    GEMINI_REPAIR_MODEL: str = Field(default="gemini-3.5-flash-lite", description="Higher-volume model for surgical item repairs")
    GEMINI_MAX_OUTPUT_TOKENS: int = Field(default=24000, ge=1000, le=240000)

    # Local File Storage
    STORAGE_TYPE: str = Field(default="local", description="local | r2")
    LOCAL_STORAGE_DIR: Path = Field(
        default=Path("local_storage/uploads"),
        description="Root directory for uploaded syllabus and examination papers",
    )
    MAX_UPLOAD_SIZE_BYTES: int = 50 * 1024 * 1024  # 50MB

    # Pedagogical & Analytics Defaults (Configurable Pilot Baseline)
    WEAKNESS_ACCURACY_THRESHOLD: float = 0.60
    MIN_DISTINCT_QUESTIONS_THRESHOLD: int = 3
    BOSS_ARENA_DEFAULT_COOLDOWN_HOURS: int = 24

    # Background Worker
    WORKER_POLL_INTERVAL_SECONDS: float = 2.0
    WORKER_JOB_LEASE_SECONDS: int = 300

    @field_validator("LOCAL_STORAGE_DIR")
    @classmethod
    def resolve_storage_dir(cls, value: Path) -> Path:
        """Resolve relative storage paths against the backend package, not the process CWD."""
        return value if value.is_absolute() else BASE_DIR / value

    @model_validator(mode="after")
    def complete_and_validate_runtime_config(self) -> "Settings":
        """Build a safely escaped database URL and reject unsafe production defaults."""
        if not self.DATABASE_URL:
            self.DATABASE_URL = URL.create(
                "postgresql+asyncpg",
                username=self.POSTGRES_USER,
                password=self.POSTGRES_PASSWORD.get_secret_value(),
                host=self.DATABASE_HOST or "localhost",
                port=self.DATABASE_PORT,
                database=self.POSTGRES_DB,
            ).render_as_string(hide_password=False)
        elif self.DATABASE_HOST:
            self.DATABASE_URL = make_url(self.DATABASE_URL).set(
                host=self.DATABASE_HOST
            ).render_as_string(hide_password=False)

        if self.APP_ENV.lower() in {"prod", "production"}:
            if self.DEBUG:
                raise ValueError("DEBUG must be false in production.")
            if len(self.SECRET_KEY) < 32 or self.SECRET_KEY.startswith("doubtdesk-local-"):
                raise ValueError("A unique SECRET_KEY of at least 32 characters is required in production.")
            if not self.SESSION_COOKIE_SECURE:
                raise ValueError("SESSION_COOKIE_SECURE must be true in production.")
            if any(
                "localhost" in origin or "127.0.0.1" in origin
                for origin in self.CORS_ORIGINS
            ):
                raise ValueError("CORS_ORIGINS must be configured for production domains.")

        return self


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()

