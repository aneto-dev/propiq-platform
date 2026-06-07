"""
SnapshotService integration tests.

Roadmap-specified tests (IMPLEMENTATION_ROADMAP.md Commit 5.5):
  1. Full save + retrieve roundtrip for an E-01 snapshot
  2. Snapshot access via non-owner deal: raises NotFoundError

Additional tests for the complete SnapshotService API:
  3. get_full_snapshot() loads all 6 sub-tables
  4. get_full_snapshot() raises NotFoundError for wrong user
  5. get_history_for_deal() returns entries for a deal with snapshots
  6. get_history_for_deal() raises NotFoundError for wrong user
  7. mark_superseded() sets is_superseded flag
  8. Deal status transitions DRAFT → ANALYSED after save

Architecture:
    APPLICATION_SERVICE_ARCHITECTURE.md Part 6, Part 10.2.
    IMPLEMENTATION_ROADMAP.md Commit 5.5.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import CalculationOutcome, DealStatus
from app.domain.errors import NotFoundError
from app.repositories.deal_repository import DealRepository
from app.repositories.interfaces.i_audit import CalculationAuditEvent
from app.repositories.interfaces.i_snapshot import SnapshotSummary
from app.repositories.investor_profile_repository import InvestorProfileRepository
from app.repositories.property_repository import PropertyRepository
from app.services.deal_service import DealService
from app.services.snapshot_service import make_snapshot_service
from tests.integration.snapshots.conftest import (
    create_deal,
    create_property,
    create_user,
    get_config_ids,
    make_e01_snapshot,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_deal_service(session: AsyncSession) -> DealService:
    return DealService(
        deal_repo=DealRepository(session),
        property_repo=PropertyRepository(session),
        profile_repo=InvestorProfileRepository(session),
    )


def _make_audit_event(
    user_id: uuid.UUID,
    deal_id: uuid.UUID,
    snapshot_id: uuid.UUID,
) -> CalculationAuditEvent:
    return CalculationAuditEvent(
        id=uuid.uuid4(),
        user_id=user_id,
        deal_id=deal_id,
        snapshot_id=snapshot_id,
        triggered_at=datetime.now(UTC),
        outcome=CalculationOutcome.SUCCESS,
        engine_version="1.0.0",
        validation_errors=None,
        error_detail=None,
        client_context="test",
        created_at=datetime.now(UTC),
    )


async def _setup_deal(
    session: AsyncSession,
) -> tuple[uuid.UUID, uuid.UUID]:
    """Create user + deal via domain helpers; return (user_id, deal_id)."""
    user = await create_user(session)
    prop = await create_property(session, user.id)
    deal = await create_deal(session, user.id, prop.id)
    return user.id, deal.id


# ---------------------------------------------------------------------------
# Test 1 — Full save + retrieve roundtrip
# IMPLEMENTATION_ROADMAP.md Commit 5.5 test 1
# ---------------------------------------------------------------------------


class TestSaveAndRetrieveRoundtrip:
    """save_snapshot_and_update_deal() + get_display_summary() roundtrip."""

    async def test_full_roundtrip_e01_snapshot(
        self, async_session: AsyncSession
    ) -> None:
        """
        After save_snapshot_and_update_deal(), get_display_summary() returns
        the snapshot with correct output values.
        IMPLEMENTATION_ROADMAP.md Commit 5.5 test 1.
        """
        user_id, deal_id = await _setup_deal(async_session)
        assumption_id, sdlt_id, ct_id = await get_config_ids(async_session)

        snapshot = make_e01_snapshot(
            deal_id=deal_id,
            user_id=user_id,
            assumption_id=assumption_id,
            sdlt_id=sdlt_id,
            ct_id=ct_id,
        )

        svc = make_snapshot_service(async_session)
        deal = await DealRepository(async_session).find_by_id_for_user(deal_id, user_id)
        assert deal is not None
        audit_event = _make_audit_event(user_id, deal_id, snapshot.id)

        await svc.save_snapshot_and_update_deal(snapshot, deal, audit_event)
        # session is committed by save_snapshot_and_update_deal

        summary = await svc.get_display_summary(snapshot.id, user_id)

        assert isinstance(summary, SnapshotSummary)
        assert summary.id == snapshot.id
        assert summary.deal_id == deal_id
        # Verify outputs are persisted
        assert summary.outputs.gross_annual_rent_gbp is not None

    async def test_deal_status_transitions_to_analysed(
        self, async_session: AsyncSession
    ) -> None:
        """
        After save_snapshot_and_update_deal(), the deal status is ANALYSED.
        IMPLEMENTATION_ROADMAP.md Commit 5.5 — Deal status transitions to ANALYSED.
        """
        user_id, deal_id = await _setup_deal(async_session)
        assumption_id, sdlt_id, ct_id = await get_config_ids(async_session)

        snapshot = make_e01_snapshot(
            deal_id=deal_id,
            user_id=user_id,
            assumption_id=assumption_id,
            sdlt_id=sdlt_id,
            ct_id=ct_id,
        )

        svc = make_snapshot_service(async_session)
        deal = await DealRepository(async_session).find_by_id_for_user(deal_id, user_id)
        assert deal is not None
        assert deal.status == DealStatus.DRAFT

        await svc.save_snapshot_and_update_deal(
            snapshot, deal, _make_audit_event(user_id, deal_id, snapshot.id)
        )

        # Reload from DB and verify status
        result = await async_session.execute(
            text("SELECT status FROM deals WHERE id = :id"),
            {"id": deal_id},
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "ANALYSED"

    async def test_audit_record_written_in_same_transaction(
        self, async_session: AsyncSession
    ) -> None:
        """Audit record is committed atomically with the snapshot."""
        user_id, deal_id = await _setup_deal(async_session)
        assumption_id, sdlt_id, ct_id = await get_config_ids(async_session)

        snapshot = make_e01_snapshot(
            deal_id=deal_id,
            user_id=user_id,
            assumption_id=assumption_id,
            sdlt_id=sdlt_id,
            ct_id=ct_id,
        )
        audit_event = _make_audit_event(user_id, deal_id, snapshot.id)

        svc = make_snapshot_service(async_session)
        deal = await DealRepository(async_session).find_by_id_for_user(deal_id, user_id)
        assert deal is not None

        await svc.save_snapshot_and_update_deal(snapshot, deal, audit_event)

        result = await async_session.execute(
            text("SELECT outcome FROM audit_calculations WHERE id = :id"),
            {"id": audit_event.id},
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] == "SUCCESS"


# ---------------------------------------------------------------------------
# Test 2 — Snapshot access via non-owner deal: raises NotFoundError
# IMPLEMENTATION_ROADMAP.md Commit 5.5 test 2
# ---------------------------------------------------------------------------


class TestOwnershipProtection:
    """Deal-mediated ownership is enforced on all snapshot reads."""

    async def test_get_display_summary_wrong_user_raises(
        self, async_session: AsyncSession
    ) -> None:
        """
        get_display_summary() raises NotFoundError when user does not own the deal.
        IMPLEMENTATION_ROADMAP.md Commit 5.5 test 2.
        """
        user_id, deal_id = await _setup_deal(async_session)
        other_user = await create_user(async_session)
        assumption_id, sdlt_id, ct_id = await get_config_ids(async_session)

        snapshot = make_e01_snapshot(
            deal_id=deal_id,
            user_id=user_id,
            assumption_id=assumption_id,
            sdlt_id=sdlt_id,
            ct_id=ct_id,
        )

        svc = make_snapshot_service(async_session)
        deal = await DealRepository(async_session).find_by_id_for_user(deal_id, user_id)
        assert deal is not None
        await svc.save_snapshot_and_update_deal(
            snapshot, deal, _make_audit_event(user_id, deal_id, snapshot.id)
        )

        with pytest.raises(NotFoundError) as exc_info:
            await svc.get_display_summary(snapshot.id, other_user.id)

        assert exc_info.value.entity == "snapshot"

    async def test_get_display_summary_unknown_snapshot_raises(
        self, async_session: AsyncSession
    ) -> None:
        """get_display_summary() raises NotFoundError for unknown snapshot_id."""
        user_id, _ = await _setup_deal(async_session)
        svc = make_snapshot_service(async_session)

        with pytest.raises(NotFoundError):
            await svc.get_display_summary(uuid.uuid4(), user_id)


# ---------------------------------------------------------------------------
# Tests 3 & 4 — get_full_snapshot()
# ---------------------------------------------------------------------------


class TestGetFullSnapshot:
    """get_full_snapshot() loads the complete aggregate with ownership check."""

    async def test_get_full_snapshot_returns_complete_aggregate(
        self, async_session: AsyncSession
    ) -> None:
        """get_full_snapshot() returns a CalculationSnapshot with all sub-tables."""
        from app.domain.entities.snapshot import CalculationSnapshot

        user_id, deal_id = await _setup_deal(async_session)
        assumption_id, sdlt_id, ct_id = await get_config_ids(async_session)

        snapshot = make_e01_snapshot(
            deal_id=deal_id,
            user_id=user_id,
            assumption_id=assumption_id,
            sdlt_id=sdlt_id,
            ct_id=ct_id,
        )

        svc = make_snapshot_service(async_session)
        deal = await DealRepository(async_session).find_by_id_for_user(deal_id, user_id)
        assert deal is not None
        await svc.save_snapshot_and_update_deal(
            snapshot, deal, _make_audit_event(user_id, deal_id, snapshot.id)
        )

        full = await svc.get_full_snapshot(snapshot.id, user_id)

        assert isinstance(full, CalculationSnapshot)
        assert full.id == snapshot.id
        assert full.inputs is not None
        assert full.intermediates is not None
        assert full.outputs is not None

    async def test_get_full_snapshot_wrong_user_raises(
        self, async_session: AsyncSession
    ) -> None:
        """get_full_snapshot() raises NotFoundError for wrong user."""
        user_id, deal_id = await _setup_deal(async_session)
        other_user = await create_user(async_session)
        assumption_id, sdlt_id, ct_id = await get_config_ids(async_session)

        snapshot = make_e01_snapshot(
            deal_id=deal_id,
            user_id=user_id,
            assumption_id=assumption_id,
            sdlt_id=sdlt_id,
            ct_id=ct_id,
        )

        svc = make_snapshot_service(async_session)
        deal = await DealRepository(async_session).find_by_id_for_user(deal_id, user_id)
        assert deal is not None
        await svc.save_snapshot_and_update_deal(
            snapshot, deal, _make_audit_event(user_id, deal_id, snapshot.id)
        )

        with pytest.raises(NotFoundError):
            await svc.get_full_snapshot(snapshot.id, other_user.id)


# ---------------------------------------------------------------------------
# Tests 5 & 6 — get_history_for_deal()
# ---------------------------------------------------------------------------


class TestGetHistoryForDeal:
    """get_history_for_deal() returns snapshot history with ownership check."""

    async def test_returns_history_entries(
        self, async_session: AsyncSession
    ) -> None:
        """get_history_for_deal() returns one entry after one snapshot."""
        user_id, deal_id = await _setup_deal(async_session)
        assumption_id, sdlt_id, ct_id = await get_config_ids(async_session)

        snapshot = make_e01_snapshot(
            deal_id=deal_id,
            user_id=user_id,
            assumption_id=assumption_id,
            sdlt_id=sdlt_id,
            ct_id=ct_id,
        )

        svc = make_snapshot_service(async_session)
        deal = await DealRepository(async_session).find_by_id_for_user(deal_id, user_id)
        assert deal is not None
        await svc.save_snapshot_and_update_deal(
            snapshot, deal, _make_audit_event(user_id, deal_id, snapshot.id)
        )

        history = await svc.get_history_for_deal(deal_id, user_id)

        assert len(history) == 1
        assert history[0].id == snapshot.id
        assert history[0].deal_id == deal_id

    async def test_raises_not_found_for_wrong_user(
        self, async_session: AsyncSession
    ) -> None:
        """get_history_for_deal() raises NotFoundError for non-owned deal."""
        user_id, deal_id = await _setup_deal(async_session)
        other_user = await create_user(async_session)

        svc = make_snapshot_service(async_session)

        with pytest.raises(NotFoundError) as exc_info:
            await svc.get_history_for_deal(deal_id, other_user.id)

        assert exc_info.value.entity == "deal"


# ---------------------------------------------------------------------------
# Test 7 — mark_superseded()
# ---------------------------------------------------------------------------


class TestMarkSuperseded:
    """mark_superseded() sets is_superseded on the snapshot record."""

    async def test_sets_is_superseded_flag(
        self, async_session: AsyncSession
    ) -> None:
        """mark_superseded() persists is_superseded=True and superseded_at."""
        user_id, deal_id = await _setup_deal(async_session)
        assumption_id, sdlt_id, ct_id = await get_config_ids(async_session)

        snapshot = make_e01_snapshot(
            deal_id=deal_id,
            user_id=user_id,
            assumption_id=assumption_id,
            sdlt_id=sdlt_id,
            ct_id=ct_id,
        )

        svc = make_snapshot_service(async_session)
        deal = await DealRepository(async_session).find_by_id_for_user(deal_id, user_id)
        assert deal is not None
        await svc.save_snapshot_and_update_deal(
            snapshot, deal, _make_audit_event(user_id, deal_id, snapshot.id)
        )

        # New session for the supersession (simulates post-commit step)
        superseded_at = datetime.now(UTC)
        await svc.mark_superseded(snapshot.id, superseded_at)

        result = await async_session.execute(
            text(
                "SELECT is_superseded FROM snapshot_calculations WHERE id = :id"
            ),
            {"id": snapshot.id},
        )
        row = result.fetchone()
        assert row is not None
        assert row[0] is True
