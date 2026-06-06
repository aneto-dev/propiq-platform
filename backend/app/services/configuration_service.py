"""
ConfigurationService — loads and translates versioned configuration.

Responsibilities (APPLICATION_SERVICE_ARCHITECTURE.md Part 9):
  - Load the three active configuration versions from the database
  - Translate them into EngineConfig (plain values; no UUIDs)
  - Return ConfigVersionRefs alongside EngineConfig for snapshot persistence
  - Resolve optional input defaults against the active AssumptionConfig

Types defined here (service-layer only — not domain entities, not engine contracts):
  RawCalculationInputs  — API-layer inputs before default resolution
  ResolvedInputs        — all optional fields populated; ready for engine assembly
  InputSourceMap        — provenance (USER_OVERRIDE / CONFIG_DEFAULT) per optional field
  ConfigBundle          — EngineConfig + ConfigVersionRefs + assumption domain object
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.domain.entities.snapshot import ConfigVersionRefs
from app.domain.enums import (
    IncomeTaxBand,
    InputSource,
    MortgageType,
    OwnershipStructure,
    PropertyCountry,
    PropertyType,
    Tenure,
)
from app.engine.contracts import (
    AssumptionConfig,
    CorporationTaxConfig,
    EngineConfig,
    SDLTBand,
    SDLTConfig,
)
from app.repositories.interfaces.i_configuration import (
    AssumptionConfiguration,
    CorporationTaxConfiguration,
    IConfigurationRepository,
    SDLTConfiguration,
)

# ---------------------------------------------------------------------------
# Service-layer input/output types
# APPLICATION_SERVICE_ARCHITECTURE.md Part 15.3
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RawCalculationInputs:
    """
    Service-layer representation of user-supplied calculation inputs.

    Required fields are always present. Optional fields are None when the
    user has not supplied a value — resolve_defaults fills them in before
    the engine is called.

    This is a plain frozen dataclass, not a Pydantic model. Validation of
    required fields is the engine's responsibility.

    Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 15.3.
    """

    # --- Required ---
    purchase_price: Decimal
    monthly_rent: Decimal
    deposit_amount: Decimal
    mortgage_interest_rate: Decimal
    mortgage_term_years: int
    mortgage_type: MortgageType
    ownership_structure: OwnershipStructure
    income_tax_band: IncomeTaxBand | None
    is_additional_dwelling: bool
    property_type: PropertyType
    tenure: Tenure
    property_country: PropertyCountry
    postcode: str

    # --- Optional — None means "use config default" ---
    void_rate_percent: Decimal | None = None
    letting_agent_fee_percent: Decimal | None = None
    maintenance_reserve_percent: Decimal | None = None
    landlord_insurance_annual: Decimal | None = None
    purchase_legal_costs: Decimal | None = None
    refurbishment_cost: Decimal | None = None
    annual_service_charge: Decimal | None = None
    annual_ground_rent: Decimal | None = None
    annual_accountancy_cost: Decimal | None = None
    lease_years_remaining: int | None = None


@dataclass(frozen=True)
class ResolvedInputs:
    """
    All calculation inputs after default resolution.

    Every optional field is populated — either from the user's explicit
    value or from the active AssumptionConfig default. Ready to be assembled
    into EngineInput.

    Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 9.2.
    """

    # --- Required (passed through unchanged) ---
    purchase_price: Decimal
    monthly_rent: Decimal
    deposit_amount: Decimal
    mortgage_interest_rate: Decimal
    mortgage_term_years: int
    mortgage_type: MortgageType
    ownership_structure: OwnershipStructure
    income_tax_band: IncomeTaxBand | None
    is_additional_dwelling: bool
    property_type: PropertyType
    tenure: Tenure
    property_country: PropertyCountry
    postcode: str

    # --- Optional — always populated after resolution ---
    void_rate_percent: Decimal
    letting_agent_fee_percent: Decimal
    maintenance_reserve_percent: Decimal
    landlord_insurance_annual: Decimal
    purchase_legal_costs: Decimal
    refurbishment_cost: Decimal
    annual_service_charge: Decimal
    annual_ground_rent: Decimal
    annual_accountancy_cost: Decimal
    lease_years_remaining: int | None  # None for FREEHOLD; may remain None for LEASEHOLD


@dataclass(frozen=True)
class InputSourceMap:
    """
    Provenance of each optional input after default resolution.

    One InputSource value per optional field — USER_OVERRIDE if the user
    supplied the value, CONFIG_DEFAULT if the assumption config default was
    applied.

    Written to snapshot_inputs paired _source columns per ADR-009.

    Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 9.2.
    """

    void_rate_percent_source: InputSource
    letting_agent_fee_percent_source: InputSource
    maintenance_reserve_percent_source: InputSource
    landlord_insurance_annual_source: InputSource
    purchase_legal_costs_source: InputSource
    refurbishment_cost_source: InputSource
    annual_service_charge_source: InputSource
    annual_ground_rent_source: InputSource
    annual_accountancy_cost_source: InputSource


@dataclass(frozen=True)
class ConfigBundle:
    """
    Output of ConfigurationService.load_for_calculation / load_specific_versions.

    Carries everything CalculationService needs from the configuration layer:
      engine_config           — passed directly to engine.run()
      version_refs            — stored in the snapshot; never passed to engine
      assumption_config_domain — retained for resolve_defaults; not passed to engine

    Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 9, Part 15.3.
    """

    engine_config: EngineConfig
    version_refs: ConfigVersionRefs
    assumption_config_domain: AssumptionConfiguration


# ---------------------------------------------------------------------------
# ConfigurationService
# ---------------------------------------------------------------------------

class ConfigurationService:
    """
    Loads versioned configuration and resolves optional input defaults.

    Depends on IConfigurationRepository (injected). Does not commit or
    manage session lifecycle — the caller owns the session.

    Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 9.
    """

    def __init__(self, repo: IConfigurationRepository) -> None:
        self._repo = repo

    # ------------------------------------------------------------------
    # Standard resolution — for new calculations
    # APPLICATION_SERVICE_ARCHITECTURE.md Part 9.1
    # ------------------------------------------------------------------

    async def load_for_calculation(self, calculation_date: date) -> ConfigBundle:
        """
        Load the three active configuration versions as of calculation_date
        and translate them into a ConfigBundle.

        Raises ConfigurationNotFoundError if any configuration is absent
        for the given date.
        """
        sdlt = await self._repo.find_active_sdlt_config(calculation_date)
        ct = await self._repo.find_active_corporation_tax_config(calculation_date)
        assumption = await self._repo.find_active_assumption_config(calculation_date)
        return self._bundle(sdlt, ct, assumption)

    # ------------------------------------------------------------------
    # Version-specific resolution — for snapshot reproduction
    # APPLICATION_SERVICE_ARCHITECTURE.md Part 9.3
    # ------------------------------------------------------------------

    async def load_specific_versions(
        self, version_refs: ConfigVersionRefs
    ) -> ConfigBundle:
        """
        Load the exact configuration versions referenced by a snapshot.

        Used when reproducing a historical calculation. The engine receives
        identical EngineConfig whether loading by date or by specific IDs.

        Raises ConfigurationNotFoundError if any referenced version is absent.
        """
        sdlt = await self._repo.find_sdlt_config_by_id(
            version_refs.sdlt_config_version_id
        )
        ct = await self._repo.find_corporation_tax_config_by_id(
            version_refs.corporation_tax_config_version_id
        )
        assumption = await self._repo.find_assumption_config_by_id(
            version_refs.assumption_config_version_id
        )
        return self._bundle(sdlt, ct, assumption)

    # ------------------------------------------------------------------
    # Default resolution — enforces ADR-013
    # APPLICATION_SERVICE_ARCHITECTURE.md Part 9.2
    # ------------------------------------------------------------------

    def resolve_defaults(
        self,
        raw_inputs: RawCalculationInputs,
        assumption_config: AssumptionConfiguration,
        ownership_structure: OwnershipStructure,
    ) -> tuple[ResolvedInputs, InputSourceMap]:
        """
        Populate all optional inputs with user values or config defaults.

        Returns (ResolvedInputs, InputSourceMap). Every optional field in
        ResolvedInputs is guaranteed non-None (except lease_years_remaining,
        which is structurally nullable for FREEHOLD properties).

        USER_OVERRIDE: raw_inputs.<field> was not None.
        CONFIG_DEFAULT: raw_inputs.<field> was None; default applied.

        Accountancy cost special case: selects individual or Ltd Co default
        based on ownership_structure when the user has not supplied a value.

        Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 9.2.
        """

        def _resolve(
            user_val: Decimal | None, default: Decimal
        ) -> tuple[Decimal, InputSource]:
            if user_val is not None:
                return user_val, InputSource.USER_OVERRIDE
            return default, InputSource.CONFIG_DEFAULT

        void_rate, void_src = _resolve(
            raw_inputs.void_rate_percent,
            assumption_config.void_rate_percent_default,
        )
        letting_fee, letting_src = _resolve(
            raw_inputs.letting_agent_fee_percent,
            assumption_config.letting_agent_fee_percent_default,
        )
        maintenance, maintenance_src = _resolve(
            raw_inputs.maintenance_reserve_percent,
            assumption_config.maintenance_reserve_percent_default,
        )
        insurance, insurance_src = _resolve(
            raw_inputs.landlord_insurance_annual,
            assumption_config.landlord_insurance_annual_default,
        )
        legal, legal_src = _resolve(
            raw_inputs.purchase_legal_costs,
            assumption_config.purchase_legal_costs_default,
        )
        refurb, refurb_src = _resolve(
            raw_inputs.refurbishment_cost,
            Decimal("0"),
        )
        service_charge, service_src = _resolve(
            raw_inputs.annual_service_charge,
            Decimal("0"),
        )
        ground_rent, ground_src = _resolve(
            raw_inputs.annual_ground_rent,
            Decimal("0"),
        )

        # Accountancy cost — ownership-structure-aware default
        if raw_inputs.annual_accountancy_cost is not None:
            accountancy = raw_inputs.annual_accountancy_cost
            accountancy_src = InputSource.USER_OVERRIDE
        elif ownership_structure == OwnershipStructure.INDIVIDUAL:
            accountancy = assumption_config.accountancy_cost_individual_default
            accountancy_src = InputSource.CONFIG_DEFAULT
        else:
            accountancy = assumption_config.accountancy_cost_ltd_default
            accountancy_src = InputSource.CONFIG_DEFAULT

        resolved = ResolvedInputs(
            purchase_price=raw_inputs.purchase_price,
            monthly_rent=raw_inputs.monthly_rent,
            deposit_amount=raw_inputs.deposit_amount,
            mortgage_interest_rate=raw_inputs.mortgage_interest_rate,
            mortgage_term_years=raw_inputs.mortgage_term_years,
            mortgage_type=raw_inputs.mortgage_type,
            ownership_structure=raw_inputs.ownership_structure,
            income_tax_band=raw_inputs.income_tax_band,
            is_additional_dwelling=raw_inputs.is_additional_dwelling,
            property_type=raw_inputs.property_type,
            tenure=raw_inputs.tenure,
            property_country=raw_inputs.property_country,
            postcode=raw_inputs.postcode,
            void_rate_percent=void_rate,
            letting_agent_fee_percent=letting_fee,
            maintenance_reserve_percent=maintenance,
            landlord_insurance_annual=insurance,
            purchase_legal_costs=legal,
            refurbishment_cost=refurb,
            annual_service_charge=service_charge,
            annual_ground_rent=ground_rent,
            annual_accountancy_cost=accountancy,
            lease_years_remaining=raw_inputs.lease_years_remaining,
        )

        sources = InputSourceMap(
            void_rate_percent_source=void_src,
            letting_agent_fee_percent_source=letting_src,
            maintenance_reserve_percent_source=maintenance_src,
            landlord_insurance_annual_source=insurance_src,
            purchase_legal_costs_source=legal_src,
            refurbishment_cost_source=refurb_src,
            annual_service_charge_source=service_src,
            annual_ground_rent_source=ground_src,
            annual_accountancy_cost_source=accountancy_src,
        )

        return resolved, sources

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _bundle(
        self,
        sdlt: SDLTConfiguration,
        ct: CorporationTaxConfiguration,
        assumption: AssumptionConfiguration,
    ) -> ConfigBundle:
        """Translate three config domain objects into a ConfigBundle."""
        engine_config = EngineConfig(
            sdlt_config=SDLTConfig(
                bands=tuple(
                    SDLTBand(
                        band_lower=b.band_lower,
                        band_upper=b.band_upper,
                        rate=b.rate,
                    )
                    for b in sdlt.bands
                ),
                additional_dwelling_surcharge_rate=sdlt.additional_dwelling_surcharge_rate,
            ),
            corporation_tax_config=CorporationTaxConfig(
                small_profits_rate=ct.small_profits_rate,
                small_profits_upper_threshold=ct.small_profits_upper_threshold,
                main_rate=ct.main_rate,
                main_rate_lower_threshold=ct.main_rate_lower_threshold,
                marginal_relief_numerator=ct.marginal_relief_numerator,
                marginal_relief_denominator=ct.marginal_relief_denominator,
            ),
            assumption_config=AssumptionConfig(
                void_rate_percent_default=assumption.void_rate_percent_default,
                letting_agent_fee_percent_default=assumption.letting_agent_fee_percent_default,
                letting_agent_vat_rate_percent=assumption.letting_agent_vat_rate_percent,
                maintenance_reserve_percent_default=assumption.maintenance_reserve_percent_default,
                landlord_insurance_annual_default=assumption.landlord_insurance_annual_default,
                purchase_legal_costs_default=assumption.purchase_legal_costs_default,
                accountancy_cost_individual_default=assumption.accountancy_cost_individual_default,
                accountancy_cost_ltd_default=assumption.accountancy_cost_ltd_default,
                stress_test_rate_percent=assumption.stress_test_rate_percent,
                icr_threshold_basic_rate_percent=assumption.icr_threshold_basic_rate_percent,
                icr_threshold_higher_rate_percent=assumption.icr_threshold_higher_rate_percent,
            ),
        )

        version_refs = ConfigVersionRefs(
            sdlt_config_version_id=sdlt.id,
            corporation_tax_config_version_id=ct.id,
            assumption_config_version_id=assumption.id,
        )

        return ConfigBundle(
            engine_config=engine_config,
            version_refs=version_refs,
            assumption_config_domain=assumption,
        )
