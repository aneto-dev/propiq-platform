"""
Configuration repository integration tests.

Verifies ConfigurationRepository against the live test database with seeded
v1.0 configuration data (DATABASE_SCHEMA_DESIGN.md Section 9).

Requires a running test database. Run via:
    make test-int

Architecture:
    REPOSITORY_ARCHITECTURE.md Part 2.6, 5.6, 8.
    IMPLEMENTATION_ROADMAP.md Commit 4.3.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import ConfigurationNotFoundError
from app.repositories.configuration_repository import ConfigurationRepository

# ===========================================================================
# find_active_sdlt_config
# ===========================================================================


class TestFindActiveSdltConfig:
    """
    find_active_sdlt_config(as_of_date) → SDLTConfig

    Seed record: ENGLAND, effective 2025-04-01.
    No config exists before 2025-04-01.
    """

    async def test_returns_record_for_post_effective_date(
        self, async_session: AsyncSession
    ) -> None:
        """
        2025-06-01 > 2025-04-01: the seed record is active.
        IMPLEMENTATION_ROADMAP.md Commit 4.3 test 1.
        """
        repo = ConfigurationRepository(async_session)
        config = await repo.find_active_sdlt_config(date(2025, 6, 1))
        assert config.additional_dwelling_surcharge_rate == Decimal("0.03")
        assert len(config.bands) == 5

    async def test_raises_for_date_before_any_config(
        self, async_session: AsyncSession
    ) -> None:
        """
        2024-12-31 < 2025-04-01: no active config.
        IMPLEMENTATION_ROADMAP.md Commit 4.3 test 2.
        """
        repo = ConfigurationRepository(async_session)
        with pytest.raises(ConfigurationNotFoundError) as exc_info:
            await repo.find_active_sdlt_config(date(2024, 12, 31))
        assert exc_info.value.config_type == "sdlt"

    async def test_bands_ordered_ascending_by_band_lower(
        self, async_session: AsyncSession
    ) -> None:
        """Bands are returned in ascending band_lower order (band_order ASC)."""
        repo = ConfigurationRepository(async_session)
        config = await repo.find_active_sdlt_config(date(2025, 6, 1))
        lowers = [b.band_lower for b in config.bands]
        assert lowers == sorted(lowers)

    async def test_top_band_has_null_upper(
        self, async_session: AsyncSession
    ) -> None:
        """Band 5 (rate=12%) has no upper limit — band_upper is None."""
        repo = ConfigurationRepository(async_session)
        config = await repo.find_active_sdlt_config(date(2025, 6, 1))
        assert config.bands[-1].band_upper is None

    async def test_band_rates_match_seed_data(
        self, async_session: AsyncSession
    ) -> None:
        """All 5 band rates match DATABASE_SCHEMA_DESIGN.md Section 9."""
        repo = ConfigurationRepository(async_session)
        config = await repo.find_active_sdlt_config(date(2025, 6, 1))
        rates = [b.rate for b in config.bands]
        assert rates == [
            Decimal("0.000000"),
            Decimal("0.020000"),
            Decimal("0.050000"),
            Decimal("0.100000"),
            Decimal("0.120000"),
        ]

    async def test_band_boundaries_match_seed_data(
        self, async_session: AsyncSession
    ) -> None:
        """Band thresholds match DATABASE_SCHEMA_DESIGN.md Section 9."""
        repo = ConfigurationRepository(async_session)
        config = await repo.find_active_sdlt_config(date(2025, 6, 1))
        # Band 1: £0 – £125,000
        assert config.bands[0].band_lower == Decimal("0")
        assert config.bands[0].band_upper == Decimal("125000")
        # Band 2: £125,000 – £250,000
        assert config.bands[1].band_lower == Decimal("125000")
        assert config.bands[1].band_upper == Decimal("250000")

    async def test_returns_decimal_not_float(
        self, async_session: AsyncSession
    ) -> None:
        """
        All numeric fields must be Decimal — never float.
        RI-13: REPOSITORY_ARCHITECTURE.md Part 20.
        """
        repo = ConfigurationRepository(async_session)
        config = await repo.find_active_sdlt_config(date(2025, 6, 1))
        assert isinstance(config.additional_dwelling_surcharge_rate, Decimal)
        for band in config.bands:
            assert isinstance(band.band_lower, Decimal)
            assert isinstance(band.rate, Decimal)
            if band.band_upper is not None:
                assert isinstance(band.band_upper, Decimal)

    async def test_on_effective_date_boundary(
        self, async_session: AsyncSession
    ) -> None:
        """as_of_date = effective_from exactly: the record is included (<=)."""
        repo = ConfigurationRepository(async_session)
        config = await repo.find_active_sdlt_config(date(2025, 4, 1))
        assert len(config.bands) == 5


# ===========================================================================
# find_sdlt_config_by_id
# ===========================================================================


class TestFindSdltConfigById:
    """
    find_sdlt_config_by_id(version_id) → SDLTConfig

    Used for snapshot reproduction — loads the exact version referenced by
    a historical snapshot.
    """

    async def test_returns_correct_record(
        self, async_session: AsyncSession, sdlt_version_id: uuid.UUID
    ) -> None:
        """
        Known UUID returns the seeded SDLT version.
        IMPLEMENTATION_ROADMAP.md Commit 4.3 test 3.
        """
        repo = ConfigurationRepository(async_session)
        config = await repo.find_sdlt_config_by_id(sdlt_version_id)
        assert len(config.bands) == 5
        assert config.additional_dwelling_surcharge_rate == Decimal("0.03")

    async def test_result_matches_active_query(
        self, async_session: AsyncSession, sdlt_version_id: uuid.UUID
    ) -> None:
        """
        find_sdlt_config_by_id returns the same data as find_active_sdlt_config
        for the same version — reproducibility guarantee.
        """
        repo = ConfigurationRepository(async_session)
        by_id = await repo.find_sdlt_config_by_id(sdlt_version_id)
        active = await repo.find_active_sdlt_config(date(2025, 6, 1))
        assert by_id.additional_dwelling_surcharge_rate == (
            active.additional_dwelling_surcharge_rate
        )
        assert len(by_id.bands) == len(active.bands)

    async def test_raises_for_unknown_id(
        self, async_session: AsyncSession
    ) -> None:
        """
        Unknown UUID raises ConfigurationNotFoundError.
        IMPLEMENTATION_ROADMAP.md Commit 4.3 test 4.
        """
        repo = ConfigurationRepository(async_session)
        with pytest.raises(ConfigurationNotFoundError) as exc_info:
            await repo.find_sdlt_config_by_id(uuid.uuid4())
        assert exc_info.value.config_type == "sdlt"
        assert exc_info.value.version_id is not None


# ===========================================================================
# find_active_assumption_config
# ===========================================================================


class TestFindActiveAssumptionConfig:
    """
    find_active_assumption_config(as_of_date) → AssumptionConfig

    Seed record: effective 2025-01-01. Values from DATABASE_SCHEMA_DESIGN.md
    Section 9.
    IMPLEMENTATION_ROADMAP.md Commit 4.3 test 5.
    """

    async def test_returns_all_seed_values(
        self, async_session: AsyncSession
    ) -> None:
        """All assumption default values match Section 9 seed data exactly."""
        repo = ConfigurationRepository(async_session)
        config = await repo.find_active_assumption_config(date(2025, 6, 1))
        assert config.void_rate_percent_default == Decimal("3.85")
        assert config.letting_agent_fee_percent_default == Decimal("10.0")
        assert config.letting_agent_vat_rate_percent == Decimal("20.0")
        assert config.maintenance_reserve_percent_default == Decimal("1.0")
        assert config.landlord_insurance_annual_default == Decimal("800.0")
        assert config.purchase_legal_costs_default == Decimal("2500.0")
        assert config.accountancy_cost_individual_default == Decimal("0.0")
        assert config.accountancy_cost_ltd_default == Decimal("1200.0")
        assert config.stress_test_rate_percent == Decimal("5.5")
        assert config.icr_threshold_basic_rate_percent == Decimal("125.0")
        assert config.icr_threshold_higher_rate_percent == Decimal("145.0")

    async def test_raises_for_date_before_any_config(
        self, async_session: AsyncSession
    ) -> None:
        """No assumption config before 2025-01-01."""
        repo = ConfigurationRepository(async_session)
        with pytest.raises(ConfigurationNotFoundError) as exc_info:
            await repo.find_active_assumption_config(date(2024, 12, 31))
        assert exc_info.value.config_type == "assumption"

    async def test_returns_decimal_not_float(
        self, async_session: AsyncSession
    ) -> None:
        """All numeric fields are Decimal — never float (RI-13)."""
        repo = ConfigurationRepository(async_session)
        config = await repo.find_active_assumption_config(date(2025, 6, 1))
        assert isinstance(config.void_rate_percent_default, Decimal)
        assert isinstance(config.stress_test_rate_percent, Decimal)
        assert isinstance(config.landlord_insurance_annual_default, Decimal)
        assert isinstance(config.icr_threshold_basic_rate_percent, Decimal)
        assert isinstance(config.icr_threshold_higher_rate_percent, Decimal)

    async def test_on_effective_date_boundary(
        self, async_session: AsyncSession
    ) -> None:
        """as_of_date = effective_from exactly: the record is included."""
        repo = ConfigurationRepository(async_session)
        config = await repo.find_active_assumption_config(date(2025, 1, 1))
        assert config.void_rate_percent_default == Decimal("3.85")


# ===========================================================================
# find_active_corporation_tax_config
# ===========================================================================


class TestFindActiveCorporationTaxConfig:
    """CT config read — not in the roadmap's minimum test list but correct."""

    async def test_returns_seed_rates(
        self, async_session: AsyncSession
    ) -> None:
        repo = ConfigurationRepository(async_session)
        config = await repo.find_active_corporation_tax_config(date(2025, 6, 1))
        assert config.small_profits_rate == Decimal("0.19")
        assert config.main_rate == Decimal("0.25")
        assert config.marginal_relief_numerator == 3
        assert config.marginal_relief_denominator == 200

    async def test_raises_before_any_config(
        self, async_session: AsyncSession
    ) -> None:
        repo = ConfigurationRepository(async_session)
        with pytest.raises(ConfigurationNotFoundError):
            await repo.find_active_corporation_tax_config(date(2022, 12, 31))
