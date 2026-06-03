"""
IDealRepository — abstract interface for deal persistence.

Also defines DealSummary, the projection type for deal list views.

Architecture: REPOSITORY_ARCHITECTURE.md Part 2.2, 5.2.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol, runtime_checkable

from app.domain.entities.deal import Deal
from app.domain.enums import DealStatus
from app.repositories.pagination import Page, PageRequest

# ---------------------------------------------------------------------------
# Projection type — read projection for deal list and summary views.
# Not a full Deal aggregate (no working_inputs detail).
# Architecture: REPOSITORY_ARCHITECTURE.md Part 5.2.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DealSummary:
    """
    Lightweight read projection for deal list views and dashboard.

    Includes core deal identity and the most recent snapshot's key metrics
    (joined from snapshot_outputs via deals.latest_snapshot_id).

    All latest_snapshot_* fields are None for DRAFT deals (no snapshot yet).

    Architecture: REPOSITORY_ARCHITECTURE.md Part 5.2.
    """

    id: uuid.UUID
    label: str
    status: DealStatus
    property_id: uuid.UUID
    latest_snapshot_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime

    # Joined from snapshot_outputs — None for DRAFT deals
    latest_snapshot_cash_flow_gbp: Decimal | None
    latest_snapshot_gross_yield: Decimal | None
    latest_snapshot_calculated_at: datetime | None
    latest_snapshot_risk_flag_count_high: int | None


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------


@runtime_checkable
class IDealRepository(Protocol):
    """
    Persists and loads Deal aggregates.

    Deals are the primary domain concept — the mutable workspace for a
    property analysis. Working inputs change freely; each calculation
    creates a new immutable snapshot.

    Architecture: REPOSITORY_ARCHITECTURE.md Part 2.2, 5.2.
    """

    async def save(self, deal: Deal) -> None:
        """
        Insert a new deal.
        Raises DealAlreadyExistsError if a deal with this id already exists.
        """
        ...

    async def update(self, deal: Deal) -> None:
        """
        Persist mutations to an existing deal.

        Updates: label, status, working_inputs, latest_snapshot_id,
                 investor_profile_id, updated_at.
        Never updates: user_id, property_id, created_at.

        Raises DealNotFoundError if the deal id is not present.
        """
        ...

    async def find_by_id(self, deal_id: uuid.UUID) -> Deal | None:
        """Return the deal with this id (any user), or None if not found."""
        ...

    async def find_by_id_for_user(
        self, deal_id: uuid.UUID, user_id: uuid.UUID
    ) -> Deal | None:
        """
        Ownership-aware load.
        Returns None if not found OR if the deal belongs to a different user.
        Never distinguishes between the two cases (RI-06).
        """
        ...

    async def find_all_for_user(
        self,
        user_id: uuid.UUID,
        status_filter: DealStatus | None,
        page: PageRequest,
    ) -> Page[DealSummary]:
        """
        Paginated list of deal summaries for a user.

        status_filter=None returns all statuses.
        Includes latest snapshot key metrics (JOIN to snapshot_outputs).
        Ordered by updated_at DESC.

        Architecture: REPOSITORY_ARCHITECTURE.md Part 5.2.
        """
        ...

    async def find_all_for_property(
        self, property_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[DealSummary]:
        """
        All deals against a specific property, ownership-filtered.

        Not paginated: a property is expected to have fewer than 50 deals.
        (RI-09 justification: REPOSITORY_ARCHITECTURE.md Part 15.3.)
        """
        ...

    async def count_for_user(self, user_id: uuid.UUID) -> int:
        """
        Count of non-archived deals for a user.
        Used for dashboard summary. Does not count ARCHIVED deals.
        """
        ...
