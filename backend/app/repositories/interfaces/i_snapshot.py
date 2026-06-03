"""
ISnapshotRepository — abstract interface for calculation snapshot persistence.

Also defines SnapshotSummary and SnapshotHistoryEntry projection types.

Architecture: REPOSITORY_ARCHITECTURE.md Part 2.1, 5.1.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Protocol, runtime_checkable

from app.domain.entities.snapshot import (
    CalculationSnapshot,
    ConfigVersionRefs,
    RiskFlag,
    SnapshotOutputs,
    ValidationWarning,
)

# ---------------------------------------------------------------------------
# Projection types
# Architecture: REPOSITORY_ARCHITECTURE.md Part 5.1, 6.1.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SnapshotSummary:
    """
    DISPLAY-level projection: root + outputs + risk flags + warnings.
    Does NOT include intermediates (expensive; not needed for display).

    Used by: deal summary display, snapshot detail page.
    Loading level: DISPLAY (REPOSITORY_ARCHITECTURE.md Part 6.1).
    """

    id: uuid.UUID
    deal_id: uuid.UUID
    engine_version: str
    calculated_at: datetime
    is_superseded: bool
    outputs: SnapshotOutputs
    risk_flags: list[RiskFlag]
    validation_warnings: list[ValidationWarning]
    config_version_refs: ConfigVersionRefs


@dataclass(frozen=True)
class SnapshotHistoryEntry:
    """
    SUMMARY-level projection: root record + key output metrics + flag counts.
    No inputs, no intermediates, no full outputs list.

    Used by: snapshot history list view.
    Loading level: SUMMARY (REPOSITORY_ARCHITECTURE.md Part 6.1).
    """

    id: uuid.UUID
    deal_id: uuid.UUID
    engine_version: str
    calculated_at: datetime
    is_superseded: bool
    risk_flag_count_high: int
    risk_flag_count_medium: int
    risk_flag_count_info: int
    # Key metrics from snapshot_outputs for the list view
    annual_cash_flow_gbp: Decimal
    gross_yield_percent: Decimal


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------


@runtime_checkable
class ISnapshotRepository(Protocol):
    """
    Persists and loads the CalculationSnapshot aggregate.

    The snapshot aggregate spans six database tables. The save() operation
    is the most critical transaction in the system — all sub-tables plus the
    deal pointer update commit atomically or not at all (RI-01, RI-02).

    Loading levels expose different depths of the aggregate:
        find_history_for_deal     → SUMMARY (root + key metrics + flag counts)
        find_by_id_outputs_only   → DISPLAY (root + outputs + flags + warnings)
        find_by_id                → FULL (all 6 tables)

    Architecture: REPOSITORY_ARCHITECTURE.md Part 2.1, 5.1, 6.1–6.3.
    """

    async def save(self, snapshot: CalculationSnapshot) -> None:
        """
        Atomically persist the complete snapshot aggregate.

        Writes (in one database transaction):
          - snapshot_calculations (root)
          - snapshot_inputs
          - snapshot_outputs
          - snapshot_intermediates
          - snapshot_risk_flags (one row per flag)
          - snapshot_validation_warnings (one row per warning)
          - deals.latest_snapshot_id (UPDATE)

        Either all writes succeed or all roll back (RI-02).
        Raises SnapshotPersistenceError on failure.

        Architecture: REPOSITORY_ARCHITECTURE.md Part 10.2.
        """
        ...

    async def find_by_id(
        self, snapshot_id: uuid.UUID
    ) -> CalculationSnapshot | None:
        """
        Load the full snapshot aggregate (FULL level: all 6 tables).
        Returns None if not found.

        Loading: 6 sequential queries, all indexed on snapshot_id.
        Architecture: REPOSITORY_ARCHITECTURE.md Part 7.1.
        """
        ...

    async def find_by_id_outputs_only(
        self, snapshot_id: uuid.UUID
    ) -> SnapshotSummary | None:
        """
        Load root + outputs + risk flags + warnings (DISPLAY level).
        Does NOT load intermediates.
        Returns None if not found.

        Used for deal summary display. Intermediates loaded only on demand.
        Architecture: REPOSITORY_ARCHITECTURE.md Part 7.2.
        """
        ...

    async def find_history_for_deal(
        self, deal_id: uuid.UUID
    ) -> list[SnapshotHistoryEntry]:
        """
        Load SUMMARY entries for all snapshots of a deal (SUMMARY level).
        Ordered by calculated_at DESC.

        Not paginated: deal snapshot history is bounded in practice
        (expected < 100 per deal). (RI-09 justification.)

        Computes risk flag counts via aggregating query — not N+1.
        Architecture: REPOSITORY_ARCHITECTURE.md Part 7.3, 15.3.
        """
        ...

    async def mark_superseded(
        self, snapshot_id: uuid.UUID, superseded_at: datetime
    ) -> None:
        """
        Set is_superseded=True and superseded_at on the specified snapshot.

        The only permitted UPDATE on any snapshot table (RI-03).
        Column-level privilege grant enforces this at the database level.
        Raises SnapshotNotFoundError if snapshot_id does not exist.
        """
        ...
