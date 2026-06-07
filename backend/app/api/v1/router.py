"""
API v1 router.

Aggregates all route modules for the /api/v1/ prefix.
New route modules are registered here as they are added in later commits.

Architecture: SERVICE_ARCHITECTURE.md Part 2 — all routes prefixed /api/v1/.
API versioning from day one (ADR from SERVICE_ARCHITECTURE.md).
"""

from fastapi import APIRouter

from app.api.v1.routes import calculations, deals, health, properties, snapshots

# The main v1 router. Mounted at /api/v1/ in main.py.
v1_router = APIRouter()

# Health — no auth, no prefix beyond /api/v1/
v1_router.include_router(health.router)

# Property and deal CRUD routes (Commit 6.3)
v1_router.include_router(properties.router, prefix="/properties")
v1_router.include_router(deals.router, prefix="/deals")

# Calculation routes (Commit 6.4)
v1_router.include_router(calculations.router, prefix="/calculations")

# Snapshot read routes (Commit 6.5)
v1_router.include_router(snapshots.router, prefix="/snapshots")
