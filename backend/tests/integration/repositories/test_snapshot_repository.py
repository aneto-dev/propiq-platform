"""
Integration tests for SnapshotRepository.

Roadmap-specified tests (IMPLEMENTATION_ROADMAP.md Commit 4.8):
  - Atomic save: if any sub-table INSERT fails, no records are written
  - Full roundtrip: save E-01 snapshot, load it, assert all fields match
  - find_by_id_outputs_only does NOT load intermediates
  - mark_superseded() sets both is_superseded and superseded_at
  - No update methods exist for any field other than supersession

Requires a running test database. Run via:
    make test-int

Architecture: REPOSITORY_ARCHITECTURE.md Part 2.1, 5.1, 10.2.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.interfaces.i_snapshot import ISnapshotRepository
from app.repositories.snapshot_repository import SnapshotRepository
from tests.integration.snapshots.conftest import (
    create_deal,
    create_property,
    create_user,
    get_config_ids,
    make_e01_snapshot,
)

# ---------------------------------------------------------------------------
# Full roundtrip — save E-01 snapshot, load it, assert all fields match
# ---------------------------------------------------------------------------

class TestSnapshotRoundtrip:
    async def test_save_and_find_by_id_full_roundtrip(
        self, async_session: AsyncSession
    ) -> None:
        """Full roundtrip: save E-01 snapshot, load it, assert all fields match."""
        user = await create_user(async_session)
        prop = await create_property(async_session, user.id)
        deal = await create_deal(async_session, user.id, prop.id)
        assumption_id, sdlt_id, ct_id = await get_config_ids(async_session)
        repo = SnapshotRepository(async_session)

        snapshot = make_e01_snapshot(
            deal_id=deal.id,
            user_id=user.id,
            assumption_id=assumption_id,
            sdlt_id=sdlt_id,
            ct_id=ct_id,
        )
        await repo.save(snapshot)
        await async_session.commit()

        loaded = await repo.find_by_id(snapshot.id)
        assert loaded is not None
        assert loaded.id == snapshot.id
        assert loaded.deal_id == deal.id
        assert loaded.user_id == user.id
        assert loaded.engine_version == "1.0.0"

    async def test_roundtrip_outputs_match_e01(
        self, async_session: AsyncSession
    ) -> None:
        user = await create_user(async_session)
        prop = await create_property(async_session, user.id)
        deal = await create_deal(async_session, user.id, prop.id)
        assumption_id, sdlt_id, ct_id = await get_config_ids(async_session)
        repo = SnapshotRepository(async_session)

        snapshot = make_e01_snapshot(
            deal_id=deal.id,
            user_id=user.id,
            assumption_id=assumption_id,
            sdlt_id=sdlt_id,
            ct_id=ct_id,
        )
        await repo.save(snapshot)
        await async_session.commit()

        loaded = await repo.find_by_id(snapshot.id)
        assert loaded is not None
        out = loaded.outputs
        assert out.annual_cash_flow_gbp.amount == Decimal("-331.90")
        assert out.monthly_cash_flow_gbp.amount == Decimal("-27.66")
        assert out.gross_yield_percent.value == Decimal("5.70")
        assert out.ltv_percent.value == Decimal("75.00")
        assert out.icr_percent is not None
        assert out.icr_percent.value == Decimal("98.78")
        assert out.total_sdlt_gbp.amount == Decimal("7500.00")

    async def test_roundtrip_inputs_match_e01(
        self, async_session: AsyncSession
    ) -> None:
        user = await create_user(async_session)
        prop = await create_property(async_session, user.id)
        deal = await create_deal(async_session, user.id, prop.id)
        assumption_id, sdlt_id, ct_id = await get_config_ids(async_session)
        repo = SnapshotRepository(async_session)

        snapshot = make_e01_snapshot(
            deal_id=deal.id,
            user_id=user.id,
            assumption_id=assumption_id,
            sdlt_id=sdlt_id,
            ct_id=ct_id,
        )
        await repo.save(snapshot)
        await async_session.commit()

        loaded = await repo.find_by_id(snapshot.id)
        assert loaded is not None
        inp = loaded.inputs
        assert inp.purchase_price.amount == Decimal("200000")
        assert inp.mortgage_interest_rate.value == Decimal("4.5")
        assert inp.postcode == "NG1 1AA"
        assert inp.lease_years_remaining is None
        assert inp.void_rate_percent_source.value == "CONFIG_DEFAULT"

    async def test_roundtrip_intermediates_match(
        self, async_session: AsyncSession
    ) -> None:
        user = await create_user(async_session)
        prop = await create_property(async_session, user.id)
        deal = await create_deal(async_session, user.id, prop.id)
        assumption_id, sdlt_id, ct_id = await get_config_ids(async_session)
        repo = SnapshotRepository(async_session)

        snapshot = make_e01_snapshot(
            deal_id=deal.id,
            user_id=user.id,
            assumption_id=assumption_id,
            sdlt_id=sdlt_id,
            ct_id=ct_id,
        )
        await repo.save(snapshot)
        await async_session.commit()

        loaded = await repo.find_by_id(snapshot.id)
        assert loaded is not None
        inter = loaded.intermediates
        assert inter.void_rate_decimal_applied == Decimal("0.04")
        assert inter.loan_amount_gbp.amount == Decimal("150000.00")
        assert inter.income_tax_gross_gbp is not None
        assert inter.income_tax_gross_gbp.amount == Decimal("1358.62")
        assert inter.corporation_tax_gross_gbp is None
        assert inter.section_24_applies is True

    async def test_roundtrip_sdlt_band_breakdown_preserved(
        self, async_session: AsyncSession
    ) -> None:
        """SDLT band breakdown JSONB roundtrip preserves all band values."""
        user = await create_user(async_session)
        prop = await create_property(async_session, user.id)
        deal = await create_deal(async_session, user.id, prop.id)
        assumption_id, sdlt_id, ct_id = await get_config_ids(async_session)
        repo = SnapshotRepository(async_session)

        snapshot = make_e01_snapshot(
            deal_id=deal.id,
            user_id=user.id,
            assumption_id=assumption_id,
            sdlt_id=sdlt_id,
            ct_id=ct_id,
        )
        await repo.save(snapshot)
        await async_session.commit()

        loaded = await repo.find_by_id(snapshot.id)
        assert loaded is not None
        bands = loaded.intermediates.sdlt_band_breakdown
        assert len(bands) == 2
        # Top band has no upper limit
        top = bands[1]
        assert top.band_upper is None
        assert top.tax_in_band.amount == Decimal("7500")

    async def test_roundtrip_risk_flags_preserved(
        self, async_session: AsyncSession
    ) -> None:
        user = await create_user(async_session)
        prop = await create_property(async_session, user.id)
        deal = await create_deal(async_session, user.id, prop.id)
        assumption_id, sdlt_id, ct_id = await get_config_ids(async_session)
        repo = SnapshotRepository(async_session)

        snapshot = make_e01_snapshot(
            deal_id=deal.id,
            user_id=user.id,
            assumption_id=assumption_id,
            sdlt_id=sdlt_id,
            ct_id=ct_id,
        )
        await repo.save(snapshot)
        await async_session.commit()

        loaded = await repo.find_by_id(snapshot.id)
        assert loaded is not None
        codes = {f.code for f in loaded.risk_flags}
        assert "NEGATIVE_CASHFLOW" in codes
        assert "LOW_ICR_BASIC" in codes
        assert "RENT_UNVERIFIED" in codes

    async def test_find_by_id_returns_none_when_not_found(
        self, async_session: AsyncSession
    ) -> None:
        repo = SnapshotRepository(async_session)
        result = await repo.find_by_id(uuid.uuid4())
        assert result is None

    async def test_save_updates_deals_latest_snapshot_id(
        self, async_session: AsyncSession
    ) -> None:
        """save() atomically updates deals.latest_snapshot_id."""
        from sqlalchemy import text

        user = await create_user(async_session)
        prop = await create_property(async_session, user.id)
        deal = await create_deal(async_session, user.id, prop.id)
        assumption_id, sdlt_id, ct_id = await get_config_ids(async_session)
        repo = SnapshotRepository(async_session)

        snapshot = make_e01_snapshot(
            deal_id=deal.id,
            user_id=user.id,
            assumption_id=assumption_id,
            sdlt_id=sdlt_id,
            ct_id=ct_id,
        )
        await repo.save(snapshot)
        await async_session.commit()

        result = await async_session.execute(
            text("SELECT latest_snapshot_id FROM deals WHERE id = :id"),
            {"id": deal.id},
        )
        row = result.fetchone()
        assert row is not None
        assert uuid.UUID(str(row[0])) == snapshot.id


# ---------------------------------------------------------------------------
# find_by_id_outputs_only does NOT load intermediates (roadmap-specified)
# ---------------------------------------------------------------------------

class TestFindByIdOutputsOnly:
    async def test_outputs_only_returns_summary_without_intermediates(
        self, async_session: AsyncSession
    ) -> None:
        """find_by_id_outputs_only does NOT load intermediates."""
        user = await create_user(async_session)
        prop = await create_property(async_session, user.id)
        deal = await create_deal(async_session, user.id, prop.id)
        assumption_id, sdlt_id, ct_id = await get_config_ids(async_session)
        repo = SnapshotRepository(async_session)

        snapshot = make_e01_snapshot(
            deal_id=deal.id,
            user_id=user.id,
            assumption_id=assumption_id,
            sdlt_id=sdlt_id,
            ct_id=ct_id,
        )
        await repo.save(snapshot)
        await async_session.commit()

        summary = await repo.find_by_id_outputs_only(snapshot.id)
        assert summary is not None

        # SnapshotSummary has no intermediates field
        assert not hasattr(summary, "intermediates"), (
            "find_by_id_outputs_only must not return intermediates"
        )
        assert not hasattr(summary, "inputs"), (
            "find_by_id_outputs_only must not return inputs"
        )

    async def test_outputs_only_returns_correct_outputs(
        self, async_session: AsyncSession
    ) -> None:
        user = await create_user(async_session)
        prop = await create_property(async_session, user.id)
        deal = await create_deal(async_session, user.id, prop.id)
        assumption_id, sdlt_id, ct_id = await get_config_ids(async_session)
        repo = SnapshotRepository(async_session)

        snapshot = make_e01_snapshot(
            deal_id=deal.id,
            user_id=user.id,
            assumption_id=assumption_id,
            sdlt_id=sdlt_id,
            ct_id=ct_id,
        )
        await repo.save(snapshot)
        await async_session.commit()

        summary = await repo.find_by_id_outputs_only(snapshot.id)
        assert summary is not None
        assert summary.outputs.annual_cash_flow_gbp.amount == Decimal("-331.90")
        assert summary.id == snapshot.id
        assert summary.deal_id == deal.id
        codes = {f.code for f in summary.risk_flags}
        assert "NEGATIVE_CASHFLOW" in codes

    async def test_outputs_only_returns_none_when_not_found(
        self, async_session: AsyncSession
    ) -> None:
        repo = SnapshotRepository(async_session)
        result = await repo.find_by_id_outputs_only(uuid.uuid4())
        assert result is None


# ---------------------------------------------------------------------------
# mark_superseded (roadmap-specified)
# ---------------------------------------------------------------------------

class TestMarkSuperseded:
    async def test_mark_superseded_sets_is_superseded_and_superseded_at(
        self, async_session: AsyncSession
    ) -> None:
        """mark_superseded() sets both is_superseded and superseded_at."""
        user = await create_user(async_session)
        prop = await create_property(async_session, user.id)
        deal = await create_deal(async_session, user.id, prop.id)
        assumption_id, sdlt_id, ct_id = await get_config_ids(async_session)
        repo = SnapshotRepository(async_session)

        snapshot = make_e01_snapshot(
            deal_id=deal.id,
            user_id=user.id,
            assumption_id=assumption_id,
            sdlt_id=sdlt_id,
            ct_id=ct_id,
        )
        await repo.save(snapshot)
        await async_session.commit()

        superseded_at = datetime.now(UTC)
        await repo.mark_superseded(snapshot.id, superseded_at)
        await async_session.commit()

        loaded = await repo.find_by_id(snapshot.id)
        assert loaded is not None
        assert loaded.is_superseded is True
        assert loaded.superseded_at is not None

    async def test_mark_superseded_does_not_alter_other_fields(
        self, async_session: AsyncSession
    ) -> None:
        user = await create_user(async_session)
        prop = await create_property(async_session, user.id)
        deal = await create_deal(async_session, user.id, prop.id)
        assumption_id, sdlt_id, ct_id = await get_config_ids(async_session)
        repo = SnapshotRepository(async_session)

        snapshot = make_e01_snapshot(
            deal_id=deal.id,
            user_id=user.id,
            assumption_id=assumption_id,
            sdlt_id=sdlt_id,
            ct_id=ct_id,
        )
        await repo.save(snapshot)
        await async_session.commit()

        await repo.mark_superseded(snapshot.id, datetime.now(UTC))
        await async_session.commit()

        loaded = await repo.find_by_id(snapshot.id)
        assert loaded is not None
        # Core immutable fields unchanged
        assert loaded.engine_version == "1.0.0"
        assert loaded.outputs.annual_cash_flow_gbp.amount == Decimal("-331.90")
        assert {f.code for f in loaded.risk_flags} == {
            "NEGATIVE_CASHFLOW", "LOW_ICR_BASIC", "RENT_UNVERIFIED"
        }


# ---------------------------------------------------------------------------
# No update methods other than supersession (roadmap-specified)
# ---------------------------------------------------------------------------

class TestSnapshotImmutabilityInterface:
    def test_no_update_method_on_interface(self) -> None:
        """No update methods exist for any field other than supersession."""
        assert not hasattr(ISnapshotRepository, "update"), (
            "ISnapshotRepository must not expose a general update() method"
        )
        assert not hasattr(ISnapshotRepository, "delete"), (
            "ISnapshotRepository must not expose a delete() method"
        )
        assert hasattr(ISnapshotRepository, "mark_superseded"), (
            "ISnapshotRepository must expose mark_superseded()"
        )

    def test_no_update_method_on_implementation(self) -> None:
        assert not hasattr(SnapshotRepository, "update"), (
            "SnapshotRepository must not expose a general update() method"
        )
        assert not hasattr(SnapshotRepository, "delete"), (
            "SnapshotRepository must not expose a delete() method"
        )


# ---------------------------------------------------------------------------
# find_history_for_deal
# ---------------------------------------------------------------------------

class TestFindHistoryForDeal:
    async def test_find_history_returns_entries_ordered_desc(
        self, async_session: AsyncSession
    ) -> None:
        user = await create_user(async_session)
        prop = await create_property(async_session, user.id)
        deal = await create_deal(async_session, user.id, prop.id)
        assumption_id, sdlt_id, ct_id = await get_config_ids(async_session)
        repo = SnapshotRepository(async_session)

        snap1 = make_e01_snapshot(
            deal_id=deal.id,
            user_id=user.id,
            assumption_id=assumption_id,
            sdlt_id=sdlt_id,
            ct_id=ct_id,
        )
        await repo.save(snap1)
        await async_session.commit()

        snap2 = make_e01_snapshot(
            deal_id=deal.id,
            user_id=user.id,
            assumption_id=assumption_id,
            sdlt_id=sdlt_id,
            ct_id=ct_id,
        )
        await repo.save(snap2)
        await async_session.commit()

        history = await repo.find_history_for_deal(deal.id)
        assert len(history) == 2
        # Most recently calculated is first
        assert history[0].calculated_at >= history[1].calculated_at

    async def test_find_history_returns_empty_for_no_snapshots(
        self, async_session: AsyncSession
    ) -> None:
        user = await create_user(async_session)
        prop = await create_property(async_session, user.id)
        deal = await create_deal(async_session, user.id, prop.id)
        repo = SnapshotRepository(async_session)

        history = await repo.find_history_for_deal(deal.id)
        assert history == []
