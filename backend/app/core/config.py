"""
Application configuration.

Reads all settings from environment variables (or .env file in development).
Pydantic BaseSettings validates types and raises a clear error at startup if
any required variable is missing.

Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 1.4 — services are
stateless; all configuration is injected from the environment, never hardcoded.
"""

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    All application settings loaded from environment variables.

    Field names map directly to environment variable names (case-insensitive).
    Types are validated at startup — a bad DATABASE_URL will fail immediately,
    not on the first database call.
    """

    model_config = SettingsConfigDict(
        # Read from .env file when present (development only).
        # In staging/production, env vars are set by the hosting platform.
        env_file=".env",
        env_file_encoding="utf-8",
        # Ignore extra env vars that don't correspond to a field.
        extra="ignore",
    )

    # ---- Database ---------------------------------------------------
    # Full asyncpg connection string.
    # Format: postgresql+asyncpg://user:password@host:port/dbname
    # The +asyncpg prefix is required by SQLAlchemy 2.0 async engine.
    database_url: str = ""

    # Separate test database — never the same as database_url.
    # Used by pytest fixtures. Run against docker-compose.test.yml.
    test_database_url: str = "postgresql+asyncpg://propiq:propiq@localhost:5433/propiq_test"

    # ---- Supabase Auth ---------------------------------------------
    # Project URL from Supabase dashboard (e.g. https://xyz.supabase.co)
    supabase_url: str = ""

    # Anon public key — safe to expose in frontend but not secret.
    supabase_anon_key: str = ""

    # JWT secret for verifying Supabase-issued tokens.
    # Found in Supabase dashboard → Settings → API → JWT Settings.
    # AUTHORIZATION_MODEL.md Part 1.2: tokens are RS256-signed.
    supabase_jwt_secret: str = ""

    # ---- Application -----------------------------------------------
    # Controls logging format and behaviour.
    # OBSERVABILITY_ARCHITECTURE.md Part 2.1: production uses JSON,
    # development uses pretty console output.
    environment: Literal["development", "staging", "production"] = "development"

    # Log level gate. OBSERVABILITY_ARCHITECTURE.md Part 2.1.
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    # Application version — embedded in every log entry and API response.
    # OBSERVABILITY_ARCHITECTURE.md Part 3.1 base fields: "version".
    app_version: str = "1.0.0"

    # ---- CORS -------------------------------------------------------
    # Comma-separated list of allowed frontend origins.
    # Example: https://propiq-staging.vercel.app,http://localhost:3000
    # In development, CORSMiddleware falls back to ["*"] regardless of this value.
    # In staging/production, only the origins listed here are permitted.
    # IMPLEMENTATION_ROADMAP.md Commit 8.3.
    allowed_origins: list[str] = []

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: object) -> list[str]:
        """
        Accept either a comma-separated string or a list.

        Railway sets env vars as strings; pydantic-settings passes the raw
        string here before coercion. Split on commas and strip whitespace.
        """
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        if isinstance(v, list):
            return [str(item) for item in v]
        return []

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    """
    Return the cached Settings instance.

    Using lru_cache means environment variables are read exactly once at
    first call, not on every request. In tests, clear the cache with
    get_settings.cache_clear() before overriding settings.
    """
    return Settings()
