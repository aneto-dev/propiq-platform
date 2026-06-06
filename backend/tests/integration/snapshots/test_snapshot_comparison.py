"""
Snapshot comparison tests.

Verifies that two snapshots saved for the same deal can be retrieved
independently and compared — the foundation for the "reproduce original"
and "compare scenarios" features.

Architecture:
    DOMAIN_MODEL_ARCHITECTURE.md Part 8 — snapshot immutability.
    REPOSITORY_ARCHITECTURE.md Part 5.1, 6.1.
    SERVICE_ARCHITECTURE.md Part 10 — snapshot-first rendering.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.snapshot_repository import SnapshotRepository
from tests.integration.snapshots.conftest import (
    create_deal,
    create_property,
    create_user,
    get_config_ids,
    make_e01_snapshot,
)


class TestSnapshotComparison:
    async def test_two_snapshots_for_same_deal_are_independently_loadable(
        self, async_session: AsyncSession
    ) -> None:
        """Two snapshots for the same deal load independently with their own data."""
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
        snap2 = make_e01_snapshot(
            deal_id=deal.id,
            user_id=user.id,
            assumption_id=assumption_id,
            sdlt_id=sdlt_id,
            ct_id=ct_id,
        )
        await repo.save(snap1)
        await async_session.commit()
        await repo.save(snap2)
        await async_session.commit()

        loaded1 = await repo.find_by_id(snap1.id)
        loaded2 = await repo.find_by_id(snap2.id)

        assert loaded1 is not None
        assert loaded2 is not None
        assert loaded1.id != loaded2.id
        assert loaded1.deal_id == loaded2.deal_id

    async def test_superseded_snapshot_still_loadable(
        self, async_session: AsyncSession
    ) -> None:
        """Superseded snapshot is not deleted — it remains fully loadable."""
        user = await create_user(async_session)
        prop = await create_property(async_session, user.id)
        deal = await create_deal(async_session, user.id, prop.id)
        assumption_id, sdlt_id, ct_id = await get_config_ids(async_session)
        repo = SnapshotRepository(async_session)

        snap = make_e01_snapshot(
            deal_id=deal.id,
            user_id=user.id,
            assumption_id=assumption_id,
            sdlt_id=sdlt_id,
            ct_id=ct_id,
        )
        await repo.save(snap)
        await async_session.commit()

        from datetime import UTC, datetime

        await repo.mark_superseded(snap.id, datetime.now(UTC))
        await async_session.commit()

        loaded = await repo.find_by_id(snap.id)
        assert loaded is not None
        assert loaded.is_superseded is True
        # Outputs still intact after supersession
        assert loaded.outputs.annual_cash_flow_gbp.amount == Decimal("-331.90")

    async def test_snapshots_have_independent_immutable_inputs(
        self, async_session: AsyncSession
    ) -> None:
        """Each snapshot preserves the exact inputs at calculation time."""
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

        loaded1 = await repo.find_by_id(snap1.id)
        loaded2 = await repo.find_by_id(snap2.id)

        assert loaded1 is not None
        assert loaded2 is not None
        # Same inputs since they're both E-01
        assert loaded1.inputs.purchase_price.amount == loaded2.inputs.purchase_price.amount
        # But they are distinct objects
        assert loaded1.id != loaded2.id

    async def test_find_by_id_outputs_only_does_not_return_intermediates(
        self, async_session: AsyncSession
    ) -> None:
        """The DISPLAY-level projection exposes no intermediates field."""
        user = await create_user(async_session)
        prop = await create_property(async_session, user.id)
        deal = await create_deal(async_session, user.id, prop.id)
        assumption_id, sdlt_id, ct_id = await get_config_ids(async_session)
        repo = SnapshotRepository(async_session)

        snap = make_e01_snapshot(
            deal_id=deal.id,
            user_id=user.id,
            assumption_id=assumption_id,
            sdlt_id=sdlt_id,
            ct_id=ct_id,
        )
        await repo.save(snap)
        await async_session.commit()

        summary = await repo.find_by_id_outputs_only(snap.id)
        assert summary is not None

        from app.repositories.interfaces.i_snapshot import SnapshotSummary

        assert isinstance(summary, SnapshotSummary)
        assert not hasattr(summary, "intermediates")
        assert not hasattr(summary, "inputs")
        # Outputs and flags are present
        assert summary.outputs.annual_cash_flow_gbp.amount == Decimal("-331.90")
        assert len(summary.risk_flags) == 3

    async def test_find_history_for_deal_includes_superseded_snapshots(
        self, async_session: AsyncSession
    ) -> None:
        """History list includes superseded snapshots (they are never deleted)."""
        user = await create_user(async_session)
        prop = await create_property(async_session, user.id)
        deal = await create_deal(async_session, user.id, prop.id)
        assumption_id, sdlt_id, ct_id = await get_config_ids(async_session)
        repo = SnapshotRepository(async_session)

        snap_old = make_e01_snapshot(
            deal_id=deal.id,
            user_id=user.id,
            assumption_id=assumption_id,
            sdlt_id=sdlt_id,
            ct_id=ct_id,
        )
        await repo.save(snap_old)
        await async_session.commit()

        from datetime import UTC, datetime

        await repo.mark_superseded(snap_old.id, datetime.now(UTC))
        await async_session.commit()

        snap_new = make_e01_snapshot(
            deal_id=deal.id,
            user_id=user.id,
            assumption_id=assumption_id,
            sdlt_id=sdlt_id,
            ct_id=ct_id,
        )
        await repo.save(snap_new)
        await async_session.commit()

        history = await repo.find_history_for_deal(deal.id)
        assert len(history) == 2

        ids = {h.id for h in history}
        assert snap_old.id in ids
        assert snap_new.id in ids

        superseded_entries = [h for h in history if h.is_superseded]
        assert len(superseded_entries) == 1
        assert superseded_entries[0].id == snap_old.id
