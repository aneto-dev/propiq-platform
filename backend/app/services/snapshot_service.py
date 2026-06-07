"""
SnapshotService — persist and read calculation snapshots.

Complete Phase 1 public API (APPLICATION_SERVICE_ARCHITECTURE.md Part 6):

  save_snapshot_and_update_deal(snapshot, deal, audit_event) → None
      Atomic transaction: snapshot rows + audit record + deal status update.
      All writes commit together or all roll back (SI-06).

  get_display_summary(snapshot_id, user_id) → SnapshotSummary | None
      DISPLAY level: root + outputs + risk flags + warnings.
      Ownership verified via deal. Returns None if not found or wrong user.

  get_full_snapshot(snapshot_id, user_id) → CalculationSnapshot | None
      FULL level: all 6 snapshot sub-tables including intermediates.
      Ownership verified via deal. Returns None if not found or wrong user.

  get_history_for_deal(deal_id, user_id) → list[SnapshotHistoryEntry]
      SUMMARY level: history entries ordered by calculated_at DESC.
      Ownership verified via deal. Returns [] if deal not found or wrong user.

  mark_superseded(snapshot_id, superseded_at) → None
      Sets is_superseded=True. Called by CalculationService outside the
      main transaction — failure is tolerated (deal pointer is authoritative).

Ownership model: snapshots carry no direct user FK. Access is always mediated
through the parent deal (APPLICATION_SERVICE_ARCHITECTURE.md Part 10.2).

Architecture:
    APPLICATION_SERVICE_ARCHITECTURE.md Part 6, Part 10.2, SI-06.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.deal import Deal
from app.domain.entities.snapshot import CalculationSnapshot
from app.domain.errors import NotFoundError
from app.repositories.audit_repository import AuditRepository
from app.repositories.deal_repository import DealRepository
from app.repositories.interfaces.i_audit import (
    CalculationAuditEvent,
    IAuditRepository,
)
from app.repositories.interfaces.i_deal import IDealRepository
from app.repositories.interfaces.i_snapshot import (
    ISnapshotRepository,
    SnapshotHistoryEntry,
    SnapshotSummary,
)
from app.repositories.snapshot_repository import SnapshotRepository


class SnapshotService:
    """
    Orchestrates snapshot persistence and access.

    Constructor arguments:
        session — the live AsyncSession. SnapshotService controls the commit
                  in save_snapshot_and_update_deal() to guarantee atomicity.
        snapshot_repo — ISnapshotRepository bound to the same session.
        deal_repo     — IDealRepository bound to the same session.
        audit_repo    — IAuditRepository bound to the same session.

    Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 6.
    """

    def __init__(
        self,
        session: AsyncSession,
        snapshot_repo: ISnapshotRepository,
        deal_repo: IDealRepository,
        audit_repo: IAuditRepository,
    ) -> None:
        self._session = session
        self._snapshot_repo = snapshot_repo
        self._deal_repo = deal_repo
        self._audit_repo = audit_repo

    # ------------------------------------------------------------------
    # Write — atomic transaction (SI-06)
    # APPLICATION_SERVICE_ARCHITECTURE.md Part 6.1
    # ------------------------------------------------------------------

    async def save_snapshot_and_update_deal(
        self,
        snapshot: CalculationSnapshot,
        deal: Deal,
        audit_event: CalculationAuditEvent,
    ) -> None:
        """
        Atomically persist the snapshot, audit event, and deal status update.

        Steps (all inside one transaction):
          1. snapshot_repo.save(snapshot) — 6 sub-table INSERTs + deal pointer UPDATE
          2. deal.apply_snapshot_created(snapshot.id) — DRAFT → ANALYSED transition
          3. deal_repo.update(deal) — persists status and latest_snapshot_id
          4. audit_repo.save(audit_event) — SUCCESS audit INSERT
          5. session.commit()

        If any step fails, the entire transaction is rolled back (SI-06).

        Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 6.1.
        """
        await self._snapshot_repo.save(snapshot)
        deal.apply_snapshot_created(snapshot.id)
        await self._deal_repo.update(deal)
        await self._audit_repo.save(audit_event)
        await self._session.commit()

    # ------------------------------------------------------------------
    # Read — DISPLAY level
    # APPLICATION_SERVICE_ARCHITECTURE.md Part 6.2
    # ------------------------------------------------------------------

    async def get_display_summary(
        self,
        snapshot_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> SnapshotSummary:
        """
        Load root + outputs + risk flags + warnings (no intermediates).

        Ownership is verified via the parent deal: if the snapshot exists but
        its deal belongs to a different user, NotFoundError is raised — the
        caller cannot distinguish "not found" from "wrong owner" (SI-13).

        Raises NotFoundError if snapshot not found or deal not owned by user.

        Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 6.2, Part 10.2.
        """
        summary = await self._snapshot_repo.find_by_id_outputs_only(snapshot_id)
        if summary is None:
            raise NotFoundError(entity="snapshot", id=snapshot_id)
        deal = await self._deal_repo.find_by_id_for_user(summary.deal_id, user_id)
        if deal is None:
            raise NotFoundError(entity="snapshot", id=snapshot_id)
        return summary

    # ------------------------------------------------------------------
    # Read — FULL level (all 6 sub-tables)
    # APPLICATION_SERVICE_ARCHITECTURE.md Part 6.2
    # ------------------------------------------------------------------

    async def get_full_snapshot(
        self,
        snapshot_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> CalculationSnapshot:
        """
        Load the full snapshot aggregate including intermediates.

        Used for audit display and reproducibility verification.
        Ownership verified via deal (Part 10.2).

        Raises NotFoundError if snapshot not found or deal not owned by user.

        Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 6.2, Part 10.2.
        """
        snapshot = await self._snapshot_repo.find_by_id(snapshot_id)
        if snapshot is None:
            raise NotFoundError(entity="snapshot", id=snapshot_id)
        deal = await self._deal_repo.find_by_id_for_user(snapshot.deal_id, user_id)
        if deal is None:
            raise NotFoundError(entity="snapshot", id=snapshot_id)
        return snapshot

    # ------------------------------------------------------------------
    # Read — SUMMARY level (history list)
    # APPLICATION_SERVICE_ARCHITECTURE.md Part 6.2
    # ------------------------------------------------------------------

    async def get_history_for_deal(
        self,
        deal_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> list[SnapshotHistoryEntry]:
        """
        Return snapshot history entries for a deal, ordered by calculated_at DESC.

        Ownership is verified on the deal before the snapshot query runs.
        Returns an empty list if the deal has no snapshots.

        Raises NotFoundError if deal not found or belongs to another user.

        Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 6.2, Part 10.2.
        """
        deal = await self._deal_repo.find_by_id_for_user(deal_id, user_id)
        if deal is None:
            raise NotFoundError(entity="deal", id=deal_id)
        return await self._snapshot_repo.find_history_for_deal(deal_id)

    # ------------------------------------------------------------------
    # Write — supersession mark (outside main transaction)
    # APPLICATION_SERVICE_ARCHITECTURE.md Part 5.3, Part 6.2
    # ------------------------------------------------------------------

    async def mark_superseded(
        self,
        snapshot_id: uuid.UUID,
        superseded_at: datetime,
    ) -> None:
        """
        Mark a snapshot as superseded after a new calculation succeeds.

        Called by CalculationService after the main transaction commits.
        Not inside the new snapshot's transaction — failure is tolerated
        (the deal's latest_snapshot_id is the authoritative "current" pointer).

        Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 5.3, Part 6.2.
        """
        await self._snapshot_repo.mark_superseded(snapshot_id, superseded_at)
        await self._session.commit()


# ---------------------------------------------------------------------------
# Factory helper — construct SnapshotService with concrete implementations
# ---------------------------------------------------------------------------

def make_snapshot_service(session: AsyncSession) -> SnapshotService:
    """
    Construct a SnapshotService with all concrete repository implementations
    bound to the given session.

    Convenience for service construction in tests and application wiring.
    """
    return SnapshotService(
        session=session,
        snapshot_repo=SnapshotRepository(session),
        deal_repo=DealRepository(session),
        audit_repo=AuditRepository(session),
    )
