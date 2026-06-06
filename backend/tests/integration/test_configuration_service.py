"""
ConfigurationService integration tests.

Verifies ConfigurationService against the live test database with seeded
v1.0 configuration data (DATABASE_SCHEMA_DESIGN.md Section 9).

Requires a running test database. Run via:
    make test-int

Architecture:
    APPLICATION_SERVICE_ARCHITECTURE.md Part 9.
    IMPLEMENTATION_ROADMAP.md Commit 5.1.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import (
    IncomeTaxBand,
    InputSource,
    MortgageType,
    OwnershipStructure,
    PropertyCountry,
    PropertyType,
    Tenure,
)
from app.engine.contracts import EngineConfig
from app.repositories.configuration_repository import ConfigurationRepository
from app.services.configuration_service import (
    ConfigBundle,
    ConfigurationService,
    InputSourceMap,
    RawCalculationInputs,
    ResolvedInputs,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service(session: AsyncSession) -> ConfigurationService:
    return ConfigurationService(ConfigurationRepository(session))


def _base_raw(**overrides) -> RawCalculationInputs:
    """Minimal required-field RawCalculationInputs with no optional values set."""
    base = RawCalculationInputs(
        purchase_price=Decimal("200000"),
        monthly_rent=Decimal("950"),
        deposit_amount=Decimal("50000"),
        mortgage_interest_rate=Decimal("4.75"),
        mortgage_term_years=25,
        mortgage_type=MortgageType.INTEREST_ONLY,
        ownership_structure=OwnershipStructure.INDIVIDUAL,
        income_tax_band=IncomeTaxBand.BASIC_RATE,
        is_additional_dwelling=True,
        property_type=PropertyType.RESIDENTIAL_SINGLE_LET,
        tenure=Tenure.FREEHOLD,
        property_country=PropertyCountry.ENGLAND,
        postcode="NG1 1AA",
    )
    import dataclasses
    return dataclasses.replace(base, **overrides)


# ---------------------------------------------------------------------------
# Tests: load_for_calculation
# ---------------------------------------------------------------------------


class TestLoadForCalculation:
    """load_for_calculation returns a complete ConfigBundle from seed data."""

    async def test_returns_config_bundle(
        self, async_session: AsyncSession
    ) -> None:
        """load_for_calculation(today) returns a ConfigBundle instance."""
        svc = _make_service(async_session)
        bundle = await svc.load_for_calculation(date(2025, 6, 1))
        assert isinstance(bundle, ConfigBundle)

    async def test_engine_config_has_no_uuids(
        self, async_session: AsyncSession
    ) -> None:
        """
        EngineConfig must contain only plain values — no UUIDs, no effective
        dates. The engine is unaware of versioning.
        IMPLEMENTATION_ROADMAP.md Commit 5.1 test 2.
        """
        svc = _make_service(async_session)
        bundle = await svc.load_for_calculation(date(2025, 6, 1))
        cfg = bundle.engine_config
        assert isinstance(cfg, EngineConfig)
        # Verify no UUID fields exist on EngineConfig or its sub-configs
        assert not hasattr(cfg, "id")
        assert not hasattr(cfg.sdlt_config, "id")
        assert not hasattr(cfg.corporation_tax_config, "id")
        assert not hasattr(cfg.assumption_config, "id")

    async def test_config_version_refs_has_all_three_ids(
        self, async_session: AsyncSession
    ) -> None:
        """
        ConfigVersionRefs must carry three non-null UUIDs.
        IMPLEMENTATION_ROADMAP.md Commit 5.1 test 3.
        """
        svc = _make_service(async_session)
        bundle = await svc.load_for_calculation(date(2025, 6, 1))
        refs = bundle.version_refs
        assert isinstance(refs.sdlt_config_version_id, uuid.UUID)
        assert isinstance(refs.corporation_tax_config_version_id, uuid.UUID)
        assert isinstance(refs.assumption_config_version_id, uuid.UUID)

    async def test_sdlt_config_has_five_bands(
        self, async_session: AsyncSession
    ) -> None:
        """SDLT config from seed has 5 bands."""
        svc = _make_service(async_session)
        bundle = await svc.load_for_calculation(date(2025, 6, 1))
        assert len(bundle.engine_config.sdlt_config.bands) == 5

    async def test_sdlt_surcharge_rate_matches_seed(
        self, async_session: AsyncSession
    ) -> None:
        """Additional dwelling surcharge rate = 0.03 from seed data."""
        svc = _make_service(async_session)
        bundle = await svc.load_for_calculation(date(2025, 6, 1))
        assert bundle.engine_config.sdlt_config.additional_dwelling_surcharge_rate == Decimal("0.030000")

    async def test_assumption_config_domain_retained(
        self, async_session: AsyncSession
    ) -> None:
        """ConfigBundle retains assumption_config_domain for resolve_defaults."""
        svc = _make_service(async_session)
        bundle = await svc.load_for_calculation(date(2025, 6, 1))
        assert bundle.assumption_config_domain is not None
        assert bundle.assumption_config_domain.void_rate_percent_default == Decimal("3.850000")

    async def test_raises_for_date_before_any_config(
        self, async_session: AsyncSession
    ) -> None:
        """ConfigurationNotFoundError when no config exists for the date."""
        from app.domain.errors import ConfigurationNotFoundError
        svc = _make_service(async_session)
        with pytest.raises(ConfigurationNotFoundError):
            await svc.load_for_calculation(date(2024, 12, 31))


# ---------------------------------------------------------------------------
# Tests: load_specific_versions
# ---------------------------------------------------------------------------


class TestLoadSpecificVersions:
    """load_specific_versions reproduces config from explicit version IDs."""

    async def test_returns_same_engine_config_as_active(
        self, async_session: AsyncSession
    ) -> None:
        """
        Loading by specific version IDs produces the same EngineConfig
        as loading by date — reproducibility guarantee.
        """
        svc = _make_service(async_session)
        by_date = await svc.load_for_calculation(date(2025, 6, 1))
        by_id = await svc.load_specific_versions(by_date.version_refs)
        # Both should produce identical engine configs
        assert by_id.engine_config == by_date.engine_config

    async def test_raises_for_unknown_version_id(
        self, async_session: AsyncSession
    ) -> None:
        """ConfigurationNotFoundError for a version ID that does not exist."""
        from app.domain.entities.snapshot import ConfigVersionRefs
        from app.domain.errors import ConfigurationNotFoundError
        svc = _make_service(async_session)
        bad_refs = ConfigVersionRefs(
            sdlt_config_version_id=uuid.uuid4(),
            corporation_tax_config_version_id=uuid.uuid4(),
            assumption_config_version_id=uuid.uuid4(),
        )
        with pytest.raises(ConfigurationNotFoundError):
            await svc.load_specific_versions(bad_refs)


# ---------------------------------------------------------------------------
# Tests: resolve_defaults
# ---------------------------------------------------------------------------


class TestResolveDefaultsAllUserOverride:
    """
    resolve_defaults with all optional inputs supplied → all USER_OVERRIDE.
    IMPLEMENTATION_ROADMAP.md Commit 5.1 test 4.
    """

    async def test_all_user_override_when_all_supplied(
        self, async_session: AsyncSession
    ) -> None:
        svc = _make_service(async_session)
        bundle = await svc.load_for_calculation(date(2025, 6, 1))
        raw = _base_raw(
            void_rate_percent=Decimal("5.00"),
            letting_agent_fee_percent=Decimal("12.00"),
            maintenance_reserve_percent=Decimal("2.00"),
            landlord_insurance_annual=Decimal("900"),
            purchase_legal_costs=Decimal("3000"),
            refurbishment_cost=Decimal("5000"),
            annual_service_charge=Decimal("1200"),
            annual_ground_rent=Decimal("150"),
            annual_accountancy_cost=Decimal("1500"),
        )
        _, sources = svc.resolve_defaults(
            raw, bundle.assumption_config_domain, OwnershipStructure.INDIVIDUAL
        )
        assert sources.void_rate_percent_source == InputSource.USER_OVERRIDE
        assert sources.letting_agent_fee_percent_source == InputSource.USER_OVERRIDE
        assert sources.maintenance_reserve_percent_source == InputSource.USER_OVERRIDE
        assert sources.landlord_insurance_annual_source == InputSource.USER_OVERRIDE
        assert sources.purchase_legal_costs_source == InputSource.USER_OVERRIDE
        assert sources.refurbishment_cost_source == InputSource.USER_OVERRIDE
        assert sources.annual_service_charge_source == InputSource.USER_OVERRIDE
        assert sources.annual_ground_rent_source == InputSource.USER_OVERRIDE
        assert sources.annual_accountancy_cost_source == InputSource.USER_OVERRIDE

    async def test_resolved_values_match_user_input(
        self, async_session: AsyncSession
    ) -> None:
        svc = _make_service(async_session)
        bundle = await svc.load_for_calculation(date(2025, 6, 1))
        raw = _base_raw(
            void_rate_percent=Decimal("5.00"),
            letting_agent_fee_percent=Decimal("12.00"),
            annual_accountancy_cost=Decimal("1500"),
        )
        resolved, _ = svc.resolve_defaults(
            raw, bundle.assumption_config_domain, OwnershipStructure.INDIVIDUAL
        )
        assert resolved.void_rate_percent == Decimal("5.00")
        assert resolved.letting_agent_fee_percent == Decimal("12.00")
        assert resolved.annual_accountancy_cost == Decimal("1500")


class TestResolveDefaultsAllConfigDefault:
    """
    resolve_defaults with no optional inputs → all CONFIG_DEFAULT.
    IMPLEMENTATION_ROADMAP.md Commit 5.1 test 5.
    """

    async def test_all_config_default_when_none_supplied(
        self, async_session: AsyncSession
    ) -> None:
        svc = _make_service(async_session)
        bundle = await svc.load_for_calculation(date(2025, 6, 1))
        raw = _base_raw()  # no optional fields set
        _, sources = svc.resolve_defaults(
            raw, bundle.assumption_config_domain, OwnershipStructure.INDIVIDUAL
        )
        assert sources.void_rate_percent_source == InputSource.CONFIG_DEFAULT
        assert sources.letting_agent_fee_percent_source == InputSource.CONFIG_DEFAULT
        assert sources.maintenance_reserve_percent_source == InputSource.CONFIG_DEFAULT
        assert sources.landlord_insurance_annual_source == InputSource.CONFIG_DEFAULT
        assert sources.purchase_legal_costs_source == InputSource.CONFIG_DEFAULT
        assert sources.refurbishment_cost_source == InputSource.CONFIG_DEFAULT
        assert sources.annual_service_charge_source == InputSource.CONFIG_DEFAULT
        assert sources.annual_ground_rent_source == InputSource.CONFIG_DEFAULT
        assert sources.annual_accountancy_cost_source == InputSource.CONFIG_DEFAULT

    async def test_resolved_values_match_seed_defaults(
        self, async_session: AsyncSession
    ) -> None:
        svc = _make_service(async_session)
        bundle = await svc.load_for_calculation(date(2025, 6, 1))
        raw = _base_raw()
        resolved, _ = svc.resolve_defaults(
            raw, bundle.assumption_config_domain, OwnershipStructure.INDIVIDUAL
        )
        assert resolved.void_rate_percent == Decimal("3.850000")
        assert resolved.letting_agent_fee_percent == Decimal("10.000000")
        assert resolved.landlord_insurance_annual == Decimal("800.000000")
        assert resolved.purchase_legal_costs == Decimal("2500.000000")
        assert resolved.annual_accountancy_cost == Decimal("0.000000")  # INDIVIDUAL default

    async def test_ltd_co_accountancy_default(
        self, async_session: AsyncSession
    ) -> None:
        """LIMITED_COMPANY with no accountancy cost uses ltd_default (£1,200)."""
        svc = _make_service(async_session)
        bundle = await svc.load_for_calculation(date(2025, 6, 1))
        raw = _base_raw(
            ownership_structure=OwnershipStructure.LIMITED_COMPANY,
            income_tax_band=None,
        )
        resolved, sources = svc.resolve_defaults(
            raw, bundle.assumption_config_domain, OwnershipStructure.LIMITED_COMPANY
        )
        assert resolved.annual_accountancy_cost == Decimal("1200.000000")
        assert sources.annual_accountancy_cost_source == InputSource.CONFIG_DEFAULT

    async def test_zero_defaults_for_non_assumption_fields(
        self, async_session: AsyncSession
    ) -> None:
        """refurbishment, service_charge, ground_rent default to zero."""
        svc = _make_service(async_session)
        bundle = await svc.load_for_calculation(date(2025, 6, 1))
        raw = _base_raw()
        resolved, _ = svc.resolve_defaults(
            raw, bundle.assumption_config_domain, OwnershipStructure.INDIVIDUAL
        )
        assert resolved.refurbishment_cost == Decimal("0")
        assert resolved.annual_service_charge == Decimal("0")
        assert resolved.annual_ground_rent == Decimal("0")

    async def test_returns_resolved_inputs_type(
        self, async_session: AsyncSession
    ) -> None:
        """resolve_defaults returns (ResolvedInputs, InputSourceMap)."""
        svc = _make_service(async_session)
        bundle = await svc.load_for_calculation(date(2025, 6, 1))
        raw = _base_raw()
        result = svc.resolve_defaults(
            raw, bundle.assumption_config_domain, OwnershipStructure.INDIVIDUAL
        )
        assert isinstance(result[0], ResolvedInputs)
        assert isinstance(result[1], InputSourceMap)
