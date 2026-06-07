"""
Snapshot read routes.

Routes:
    GET /api/v1/snapshots/{snapshot_id}/      → 200 SnapshotSummaryResponse
    GET /api/v1/snapshots/{snapshot_id}/full/ → 200 SnapshotFullResponse
    GET /api/v1/snapshots/?deal_id={id}       → 200 list[SnapshotHistoryEntryResponse]

All routes require authentication (get_current_user dependency).
Ownership is verified by SnapshotService via the parent deal — a snapshot
for a deal owned by a different user returns 404, not 403.

Architecture:
    SERVICE_ARCHITECTURE.md — API layer calls services only.
    APPLICATION_SERVICE_ARCHITECTURE.md Part 6.2 — read loading levels.
    IMPLEMENTATION_ROADMAP.md Commit 6.5.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user, get_snapshot_service
from app.api.v1.schemas.snapshot import (
    SnapshotFullResponse,
    SnapshotHistoryEntryResponse,
    SnapshotSummaryResponse,
)
from app.domain.entities.user import User
from app.services.snapshot_service import SnapshotService

router = APIRouter(tags=["snapshots"])


@router.get(
    "/{snapshot_id}",
    response_model=SnapshotSummaryResponse,
    summary="Get snapshot (display level)",
)
async def get_snapshot(
    snapshot_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: SnapshotService = Depends(get_snapshot_service),
) -> SnapshotSummaryResponse:
    """
    Load root + outputs + risk flags + warnings. Does not include intermediates.

    Raises 404 if snapshot not found or deal not owned by the authenticated user.
    """
    summary = await svc.get_display_summary(snapshot_id, current_user.id)
    return SnapshotSummaryResponse.from_snapshot_summary(summary)


@router.get(
    "/{snapshot_id}/full",
    response_model=SnapshotFullResponse,
    summary="Get snapshot (full level — includes intermediates)",
)
async def get_full_snapshot(
    snapshot_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: SnapshotService = Depends(get_snapshot_service),
) -> SnapshotFullResponse:
    """
    Load the complete snapshot aggregate including all intermediates.

    Used for audit display and reproducibility verification.
    Raises 404 if snapshot not found or deal not owned by the authenticated user.
    """
    snapshot = await svc.get_full_snapshot(snapshot_id, current_user.id)
    return SnapshotFullResponse.from_full_snapshot(snapshot)


@router.get(
    "/",
    response_model=list[SnapshotHistoryEntryResponse],
    summary="List snapshot history for a deal",
)
async def list_snapshot_history(
    deal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: SnapshotService = Depends(get_snapshot_service),
) -> list[SnapshotHistoryEntryResponse]:
    """
    Return snapshot history for a deal, ordered by calculated_at DESC.

    deal_id is a required query parameter.
    Raises 404 if the deal is not found or not owned by the authenticated user.
    """
    entries = await svc.get_history_for_deal(deal_id, current_user.id)
    return [SnapshotHistoryEntryResponse.from_history_entry(e) for e in entries]
