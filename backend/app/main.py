"""
FastAPI application factory.

The application is created by `create_app()` rather than defined at module
level. This pattern allows:
  - Tests to create a fresh application instance with different settings
  - The production `app` module-level instance for uvicorn
  - Future lifespan hooks (database pool setup/teardown) without circular imports

Architecture: SERVICE_ARCHITECTURE.md Part 1 — "The API layer is the HTTP
boundary of the backend." No business logic lives here. No calculations.
No database calls. The factory wires together the HTTP layer only.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.v1.router import v1_router
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """
    Application lifespan handler.

    Runs setup logic on startup and teardown logic on shutdown.
    Currently logs startup/shutdown events.

    In Commit 0.5, the database engine will be initialised here.
    In Commit 3.1, connection pool warm-up will be added.
    """
    settings = get_settings()
    logger.info(
        "app.startup",
        environment=settings.environment,
        version=settings.app_version,
    )
    yield
    logger.info("app.shutdown")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application.

    Called once at module level to produce the `app` instance used by
    uvicorn. Also called in tests to produce isolated app instances.
    """
    # Logging must be configured before anything else logs.
    # OBSERVABILITY_ARCHITECTURE.md Part 1.4: structured logging mandatory.
    configure_logging()

    settings = get_settings()

    app = FastAPI(
        title="PropIQ API",
        version=settings.app_version,
        description=(
            "PropIQ — UK property investment underwriting platform. "
            "Deterministic, explainable, and historically reproducible "
            "property deal analysis."
        ),
        # Disable the default /docs and /redoc in production.
        # In development they remain available for convenience.
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
        # OpenAPI schema always available (used by tooling in all envs).
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # Register all v1 routes under /api/v1/
    # SERVICE_ARCHITECTURE.md: "All routes are prefixed with /api/v1/"
    app.include_router(v1_router, prefix="/api/v1")

    # Error handlers will be registered here in Commit 6.2.
    # _register_error_handlers(app)

    return app


# Module-level app instance consumed by uvicorn:
#   uvicorn app.main:app --reload
app = create_app()
