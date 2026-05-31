"""
CalculationSnapshot aggregate entity and all sub-entities.

The CalculationSnapshot is the platform's primary trust artefact. Once
created it is permanent and immutable. It records exactly what was analysed,
under which assumptions, by which engine version, and what the result was.

All sub-entities (SnapshotInputs, SnapshotOutputs, SnapshotIntermediates,
SDLTBandResult, RiskFlag, ValidationWarning, ConfigVersionRefs) are
frozen=True dataclasses — immutable after construction.

CalculationSnapshot itself is a regular (mutable) dataclass because
is_superseded and superseded_at are updated when a newer snapshot is created
for the same deal. These are the only permitted mutations and are enforced by
the repository layer's column-level privilege grant.

No behaviour methods. This is a pure data structure. The service layer
constructs instances; the repository layer persists and loads them.

Architecture:
    DOMAIN_MODEL_ARCHITECTURE.md Part 8 — CalculationSnapshot aggregate design
    DATABASE_SCHEMA_DESIGN.md Section 3 — snapshot domain tables
    PERSISTENCE_ARCHITECTURE.md Part 3 — snapshot storage model
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from app.domain.enums import (
    FlagSeverity,
    IncomeTaxBand,
    InputSource,
    MortgageType,
    OwnershipStructure,
    PropertyCountry,
    PropertyType,
    Tenure,
)
from app.domain.value_objects.money import Money
from app.domain.value_objects.rate import Rate

# ---------------------------------------------------------------------------
# Supporting frozen sub-types
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SDLTBandResult:
    """
    The contribution of one SDLT band to the total tax calculation.

    band_upper is None for the top band (no upper limit).
    Only bands with taxable_in_band > 0 are included in the breakdown list.

    Architecture: DATABASE_SCHEMA_DESIGN.md — sdlt_band_breakdown JSONB.
    DOMAIN_MODEL_ARCHITECTURE.md Part 8.4.
    """

    band_lower: Money
    band_upper: Money | None  # None for the top band
    rate: Rate
    taxable_in_band: Money
    tax_in_band: Money


@dataclass(frozen=True)
class ConfigVersionRefs:
    """
    The three configuration version UUIDs active at calculation time.

    Stored on the snapshot root so that any historical snapshot can be
    exactly reproduced by loading these specific configuration records.

    These IDs are never passed to the engine — the engine receives
    EngineConfig (plain values). ConfigVersionRefs is a persistence
    and auditability concern only.

    Architecture: DOMAIN_MODEL_ARCHITECTURE.md Part 5.11.
    """

    assumption_config_version_id: uuid.UUID
    sdlt_config_version_id: uuid.UUID
    corporation_tax_config_version_id: uuid.UUID


@dataclass(frozen=True)
class RiskFlag:
    """
    A triggered risk flag from the calculation pipeline.

    Flags are informational — none block snapshot creation. The message
    stored here is the exact text shown to the user at calculation time.
    If the wording changes in a future engine version, historical snapshots
    retain what they originally said.

    triggered_by_value is a string representation regardless of the
    originating type (numeric, enum, boolean) to ensure consistent storage.

    Architecture: DOMAIN_MODEL_ARCHITECTURE.md Part 12.
    """

    code: str
    severity: FlagSeverity
    triggered_by_field: str
    triggered_by_value: str
    message: str


@dataclass(frozen=True)
class ValidationWarning:
    """
    A WARN-severity validation rule that did not block the calculation.

    Stored with the snapshot so the user can see what caveats applied at
    calculation time, even when reviewing the snapshot later.

    Architecture: DOMAIN_MODEL_ARCHITECTURE.md Part 13.
    """

    rule_code: str
    field: str
    message: str


# ---------------------------------------------------------------------------
# Snapshot sub-entities — one-to-one with CalculationSnapshot
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SnapshotInputs:
    """
    Complete record of every input value used in one calculation.

    All fields are required (no None for optional inputs) because by the
    time a snapshot is created, the InputDefaultResolutionService has resolved
    every optional input to either a user value or a config default. A
    snapshot with a null optional input is an engine contract violation.

    Every optional input has a paired _source field recording whether the
    value came from the user (USER_OVERRIDE) or the active assumption
    configuration (CONFIG_DEFAULT). Provenance is mandatory — ADR-009.

    Required inputs use Money for monetary fields and Rate for percentages.
    Optional inputs follow the same typing convention.
    income_tax_band is None for LIMITED_COMPANY (domain invariant I-06).
    lease_years_remaining is None for FREEHOLD tenure.

    Architecture: DOMAIN_MODEL_ARCHITECTURE.md Part 8.2.
    DATABASE_SCHEMA_DESIGN.md — snapshot_inputs table.
    """

    # --- Required inputs -------------------------------------------------
    purchase_price: Money
    monthly_rent: Money
    deposit_amount: Money
    mortgage_interest_rate: Rate
    mortgage_term_years: int
    mortgage_type: MortgageType
    ownership_structure: OwnershipStructure
    income_tax_band: IncomeTaxBand | None  # None for LIMITED_COMPANY
    is_additional_dwelling: bool
    property_type: PropertyType
    tenure: Tenure
    property_country: PropertyCountry
    postcode: str
    lease_years_remaining: int | None  # None for FREEHOLD

    # --- Optional inputs — each paired with a _source field --------------
    void_rate_percent: Rate
    void_rate_percent_source: InputSource

    letting_agent_fee_percent: Rate
    letting_agent_fee_percent_source: InputSource

    maintenance_reserve_percent: Rate
    maintenance_reserve_percent_source: InputSource

    landlord_insurance_annual: Money
    landlord_insurance_annual_source: InputSource

    purchase_legal_costs: Money
    purchase_legal_costs_source: InputSource

    refurbishment_cost: Money
    refurbishment_cost_source: InputSource

    annual_service_charge: Money
    annual_service_charge_source: InputSource

    annual_ground_rent: Money
    annual_ground_rent_source: InputSource

    annual_accountancy_cost: Money
    annual_accountancy_cost_source: InputSource


@dataclass(frozen=True)
class SnapshotOutputs:
    """
    All user-facing output metrics produced by the calculation.

    Field names match ENGINE_CONTRACTS.md EngineOutputs and DOMAIN_GLOSSARY.md
    API field names exactly. This alignment ensures the domain entity, the
    engine contract, and the API response schema speak the same language.

    Cash flow and return fields may be negative — a negative cash flow is a
    valid calculation result, not a data error. icr_percent is None when
    there is no mortgage (cash purchase).

    Architecture: DOMAIN_MODEL_ARCHITECTURE.md Part 8.3.
    DATABASE_SCHEMA_DESIGN.md — snapshot_outputs table.
    """

    gross_annual_rent_gbp: Money
    effective_annual_rent_gbp: Money
    total_operating_costs_annual_gbp: Money
    net_operating_income_gbp: Money       # may be negative
    annual_mortgage_cost_gbp: Money
    annual_tax_liability_gbp: Money
    annual_cash_flow_gbp: Money           # may be negative
    monthly_cash_flow_gbp: Money          # may be negative
    gross_yield_percent: Rate
    net_yield_percent: Rate               # may be negative
    roce_percent: Rate                    # may be negative
    cash_on_cash_return_percent: Rate     # may be negative
    ltv_percent: Rate
    icr_percent: Rate | None              # None for cash purchase (no mortgage)
    total_sdlt_gbp: Money
    total_acquisition_cost_gbp: Money
    total_cash_deployed_gbp: Money


@dataclass(frozen=True)
class SnapshotIntermediates:
    """
    Every intermediate value from the calculation pipeline.

    Exists for auditability, reproducibility verification, and future
    explainability features (Phase 3+). Not loaded in routine display
    operations — loaded on demand for audit and debugging.

    void_rate_decimal_applied is a Decimal fraction (e.g. 0.0385 for 3.85%)
    stored at higher precision than standard monetary fields. It uses bare
    Decimal rather than Rate because Rate stores percentages (3.85), not
    fractions, and the engine works with the fraction internally.

    Tax pathway fields are None based on ownership structure:
        income_tax_gross_gbp:           None for LIMITED_COMPANY
        mortgage_interest_tax_credit:   None for LIMITED_COMPANY
        corporation_tax_gross_gbp:      None for INDIVIDUAL

    Architecture: DOMAIN_MODEL_ARCHITECTURE.md Part 8.4.
    DATABASE_SCHEMA_DESIGN.md — snapshot_intermediates table.
    """

    # Void and rent
    void_rate_decimal_applied: Decimal    # fraction form, higher precision
    gross_annual_rent_gbp: Money
    effective_annual_rent_gbp: Money

    # Mortgage
    loan_amount_gbp: Money
    ltv_percent: Rate
    monthly_mortgage_payment_gbp: Money
    annual_mortgage_cost_gbp: Money
    annual_mortgage_interest_gbp: Money   # interest component only (for tax)

    # Operating costs
    letting_agent_annual_gbp: Money       # includes VAT uplift
    letting_agent_vat_rate_applied: Rate  # VAT rate used (config value)
    annual_maintenance_reserve_gbp: Money
    total_operating_costs_annual_gbp: Money
    net_operating_income_gbp: Money       # may be negative

    # SDLT
    sdlt_band_breakdown: tuple[SDLTBandResult, ...]  # ordered; frozen-safe
    sdlt_base_gbp: Money
    sdlt_surcharge_gbp: Money
    sdlt_surcharge_rate_applied: Rate     # config value used
    total_sdlt_gbp: Money

    # Acquisition
    total_acquisition_cost_gbp: Money
    total_cash_deployed_gbp: Money

    # Stress test
    stressed_annual_interest_gbp: Money
    stress_test_rate_applied_percent: Rate

    # Tax
    taxable_income_or_profit_gbp: Money   # may be negative
    income_tax_gross_gbp: Money | None    # INDIVIDUAL pathway only
    mortgage_interest_tax_credit_gbp: Money | None  # INDIVIDUAL pathway only
    corporation_tax_gross_gbp: Money | None  # LIMITED_COMPANY pathway only
    annual_tax_liability_gbp: Money

    # Cash flow
    pre_tax_annual_cash_flow_gbp: Money   # may be negative

    # Flags
    section_24_applies: bool


# ---------------------------------------------------------------------------
# Aggregate root
# ---------------------------------------------------------------------------


@dataclass
class CalculationSnapshot:
    """
    Root of the CalculationSnapshot aggregate.

    Every field except is_superseded and superseded_at is immutable after
    creation. The repository layer enforces this via column-level privilege
    grants — no UPDATE is permitted on any other column.

    is_superseded is set to True and superseded_at is populated when a new
    calculation is performed for the same deal. The previous snapshot becomes
    superseded but is never deleted. Both snapshots remain accessible.

    CalculationSnapshot is a regular (mutable) dataclass precisely because
    of this one permitted mutation. All sub-entities are frozen=True.

    No behaviour methods. The service layer calls mark_superseded() on the
    repository directly. The domain entity does not own this transition.

    Architecture: DOMAIN_MODEL_ARCHITECTURE.md Part 8.1.
    DATABASE_SCHEMA_DESIGN.md — snapshot_calculations table.
    """

    # Identity
    id: uuid.UUID
    deal_id: uuid.UUID
    user_id: uuid.UUID                   # denormalised for audit

    # Version traceability
    engine_version: str                  # e.g. "1.0.0"
    config_version_refs: ConfigVersionRefs

    # Timing
    calculated_at: datetime

    # Sub-entities — all immutable
    inputs: SnapshotInputs
    outputs: SnapshotOutputs
    intermediates: SnapshotIntermediates
    risk_flags: list[RiskFlag]
    validation_warnings: list[ValidationWarning]

    # The only mutable fields — default to not-yet-superseded
    is_superseded: bool = False
    superseded_at: datetime | None = None

    # Operational diagnostic — may be None if not measured
    calculation_duration_ms: int | None = None
