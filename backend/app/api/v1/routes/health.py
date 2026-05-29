"""
Health check endpoint.

GET /api/v1/health → 200 {"status": "ok", "environment": "...", "version": "..."}

No authentication required.

Architecture:
- SERVICE_ARCHITECTURE.md Part 2: "/api/v1/health/ — Liveness and readiness
  checks. No authentication required."
- OBSERVABILITY_ARCHITECTURE.md Part 19.4: health endpoint feeds the API
  performance dashboard.
- Railway deployment: health check configured to poll this endpoint.
"""

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    """Response schema for the health check endpoint."""

    status: str
    environment: str
    version: str


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness check",
    description="Returns 200 when the application is running. No auth required.",
    tags=["health"],
)
async def health() -> HealthResponse:
    """
    Liveness check.

    Used by:
    - Railway deployment health checks
    - Load balancers
    - Uptime monitoring

    Does NOT check database connectivity — that is a readiness concern
    addressed in a future commit when the DB layer is added.
    """
    settings = get_settings()
    return HealthResponse(
        status="ok",
        environment=settings.environment,
        version=settings.app_version,
    )
