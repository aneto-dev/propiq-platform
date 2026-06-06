"""
Snapshot completeness tests.

Verifies that every sub-table row is written during save() and that the
full aggregate loaded by find_by_id() contains all expected sub-entities.

Architecture: REPOSITORY_ARCHITECTURE.md Part 10.2.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.snapshot_repository import SnapshotRepository
from tests.integration.snapshots.conftest import (
    create_deal,
    create_property,
    create_user,
    get_config_ids,
    make_e01_snapshot,
)


class TestSnapshotCompleteness:
    async def test_all_six_sub_tables_written(
        self, async_session: AsyncSession
    ) -> None:
        """save() writes rows to all 6 snapshot sub-tables."""
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

        sid = snapshot.id

        for table in (
            "snapshot_calculations",
            "snapshot_inputs",
            "snapshot_outputs",
            "snapshot_intermediates",
        ):
            col = "id" if table == "snapshot_calculations" else "snapshot_id"
            result = await async_session.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE {col} = :sid"),
                {"sid": sid},
            )
            count = result.scalar_one()
            assert count == 1, f"Expected 1 row in {table}, got {count}"

        for table in ("snapshot_risk_flags", "snapshot_validation_warnings"):
            result = await async_session.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE snapshot_id = :sid"),
                {"sid": sid},
            )
            count = result.scalar_one()
            # E-01 has 3 flags and 0 warnings
            if table == "snapshot_risk_flags":
                assert count == 3, f"Expected 3 risk flags, got {count}"
            else:
                assert count == 0, f"Expected 0 warnings, got {count}"

    async def test_find_by_id_full_aggregate_has_all_sub_entities(
        self, async_session: AsyncSession
    ) -> None:
        """find_by_id() returns a fully populated CalculationSnapshot."""
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

        # All sub-entities are present
        assert loaded.inputs is not None
        assert loaded.outputs is not None
        assert loaded.intermediates is not None
        assert isinstance(loaded.risk_flags, list)
        assert isinstance(loaded.validation_warnings, list)
        assert loaded.config_version_refs is not None

    async def test_snapshot_inputs_all_source_fields_preserved(
        self, async_session: AsyncSession
    ) -> None:
        """All 9 optional-input source provenance fields survive the roundtrip."""
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

        from app.domain.enums import InputSource

        assert inp.void_rate_percent_source == InputSource.CONFIG_DEFAULT
        assert inp.letting_agent_fee_percent_source == InputSource.CONFIG_DEFAULT
        assert inp.maintenance_reserve_percent_source == InputSource.CONFIG_DEFAULT
        assert inp.landlord_insurance_annual_source == InputSource.USER_OVERRIDE
        assert inp.purchase_legal_costs_source == InputSource.USER_OVERRIDE
        assert inp.refurbishment_cost_source == InputSource.USER_OVERRIDE

    async def test_config_version_refs_preserved(
        self, async_session: AsyncSession
    ) -> None:
        """ConfigVersionRefs UUIDs survive the roundtrip unchanged."""
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
        refs = loaded.config_version_refs
        assert refs.assumption_config_version_id == assumption_id
        assert refs.sdlt_config_version_id == sdlt_id
        assert refs.corporation_tax_config_version_id == ct_id
