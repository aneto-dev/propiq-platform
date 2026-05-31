"""
Engine input/output contract types.

All types that cross the engine boundary are defined here. These are the
only types the service layer and engine share. Nothing else from the
application domain enters the engine; nothing from the engine's internal
implementation leaks out.

Design principles:
    - All types are frozen dataclasses. The engine does not mutate its
      inputs, and outputs are produced fresh each call.
    - All numeric fields use Decimal. float is never used.
    - No infrastructure imports (no SQLAlchemy, no FastAPI, no pydantic).
    - Importing this module has zero side effects.

Architecture:
    ENGINE_ARCHITECTURE.md Part 1 — pure function boundary.
    ENGINE_CONTRACTS.md Parts 1–6 — authoritative field specifications.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.enums import (
    FlagSeverity,
    IncomeTaxBand,
    MortgageType,
    OwnershipStructure,
    PropertyCountry,
    PropertyType,
    Tenure,
)

# ===========================================================================
# EngineConfig types
# ===========================================================================
# Plain values only. No database IDs, no effective dates, no metadata.
# Source: ENGINE_CONTRACTS.md Part 2.


@dataclass(frozen=True)
class SDLTBand:
    """
    One band in the SDLT banded rate structure.

    rate is a decimal fraction (e.g. Decimal("0.02") for 2%).
    band_upper is None for the top band (no upper limit).

    Source: ENGINE_CONTRACTS.md Part 2.1.
    """

    band_lower: Decimal
    band_upper: Decimal | None  # None for the top band
    rate: Decimal               # decimal fraction: 0.02 = 2%


@dataclass(frozen=True)
class SDLTConfig:
    """
    Complete SDLT configuration active at calculation time.

    additional_dwelling_surcharge_rate is a decimal fraction
    (e.g. Decimal("0.03") for 3%).

    Source: ENGINE_CONTRACTS.md Part 2.1.
    """

    bands: tuple[SDLTBand, ...]  # ordered ascending by band_lower
    additional_dwelling_surcharge_rate: Decimal  # decimal fraction


@dataclass(frozen=True)
class CorporationTaxConfig:
    """
    Corporation Tax rates and thresholds active at calculation time.

    Rates are decimal fractions (e.g. Decimal("0.19") for 19%).
    Thresholds are GBP amounts.

    Source: ENGINE_CONTRACTS.md Part 2.2.
    """

    small_profits_rate: Decimal            # decimal fraction
    small_profits_upper_threshold: Decimal # GBP amount
    main_rate: Decimal                     # decimal fraction
    main_rate_lower_threshold: Decimal     # GBP amount
    marginal_relief_numerator: int
    marginal_relief_denominator: int


@dataclass(frozen=True)
class AssumptionConfig:
    """
    Operational assumption defaults active at calculation time.

    Percentage fields are stored as percentage values (e.g. Decimal("3.85")
    for 3.85%), not as fractions. The engine applies the ÷100 conversion
    internally where needed.

    Source: ENGINE_CONTRACTS.md Part 2.3.
    """

    void_rate_percent_default: Decimal
    letting_agent_fee_percent_default: Decimal
    letting_agent_vat_rate_percent: Decimal
    maintenance_reserve_percent_default: Decimal
    landlord_insurance_annual_default: Decimal
    purchase_legal_costs_default: Decimal
    accountancy_cost_individual_default: Decimal
    accountancy_cost_ltd_default: Decimal
    stress_test_rate_percent: Decimal
    icr_threshold_basic_rate_percent: Decimal
    icr_threshold_higher_rate_percent: Decimal


@dataclass(frozen=True)
class EngineConfig:
    """
    Complete configuration bundle passed to the engine.

    Contains no database identifiers, no version IDs, no effective dates.
    Those are tracked by the calculation service alongside EngineConfig and
    written to the snapshot separately — the engine does not need them.

    Source: ENGINE_CONTRACTS.md Part 2; ENGINE_ARCHITECTURE.md Part 3.
    """

    sdlt_config: SDLTConfig
    corporation_tax_config: CorporationTaxConfig
    assumption_config: AssumptionConfig


# ===========================================================================
# EngineInput
# ===========================================================================
# Source: ENGINE_CONTRACTS.md Part 1.


@dataclass(frozen=True)
class EngineInput:
    """
    Complete set of values passed to the engine for one calculation.

    By the time EngineInput reaches the engine, every field is populated.
    There are no nulls to resolve inside the engine. Default resolution is
    the responsibility of the calculation service layer (InputDefaultResolutionService).

    Required inputs have no defaults. Optional inputs are always present
    (resolved to user value or config default by the service layer before
    engine.run() is called).

    All numeric fields use Decimal. All enum fields use the domain enums.
    float is never used anywhere in this type.

    income_tax_band is None for LIMITED_COMPANY (domain invariant I-06).
    lease_years_remaining is None for FREEHOLD tenure and remains optional
    even after default resolution.

    Source: ENGINE_CONTRACTS.md Part 1.1 and 1.2.
    """

    # --- Required inputs — no defaults -----------------------------------
    purchase_price: Decimal
    monthly_rent: Decimal
    deposit_amount: Decimal
    mortgage_interest_rate: Decimal  # 0 treated as cash purchase
    mortgage_term_years: int
    mortgage_type: MortgageType
    ownership_structure: OwnershipStructure
    income_tax_band: IncomeTaxBand | None   # required for INDIVIDUAL; None for LTD
    is_additional_dwelling: bool
    property_type: PropertyType
    tenure: Tenure
    property_country: PropertyCountry
    postcode: str

    # --- Optional inputs — always populated before engine entry ----------
    void_rate_percent: Decimal
    letting_agent_fee_percent: Decimal
    maintenance_reserve_percent: Decimal
    landlord_insurance_annual: Decimal
    purchase_legal_costs: Decimal
    refurbishment_cost: Decimal
    annual_service_charge: Decimal
    annual_ground_rent: Decimal
    annual_accountancy_cost: Decimal
    lease_years_remaining: int | None       # None for FREEHOLD; optional for LEASEHOLD


# ===========================================================================
# EngineResult types
# ===========================================================================
# Source: ENGINE_CONTRACTS.md Part 3.


@dataclass(frozen=True)
class SDLTBandResult:
    """
    Contribution of one SDLT band to the total SDLT calculation.

    All numeric values are Decimal. rate is a decimal fraction.
    band_upper is None for the top band.

    Source: ENGINE_CONTRACTS.md Part 3.2.
    """

    band_lower: Decimal
    band_upper: Decimal | None
    rate: Decimal           # decimal fraction
    taxable_in_band: Decimal
    tax_in_band: Decimal


@dataclass(frozen=True)
class EngineOutputs:
    """
    User-facing output metrics produced by the calculation.

    Field names match DOMAIN_GLOSSARY.md API field names exactly.
    All monetary values are GBP. All percentages are Decimal percentage
    values (e.g. Decimal("5.70") means 5.70%).

    icr_percent is None for cash purchases (no loan, no mortgage).
    cash_on_cash_return_percent and net_yield_percent may be negative.

    Source: ENGINE_CONTRACTS.md Part 3.1.
    """

    gross_annual_rent_gbp: Decimal
    effective_annual_rent_gbp: Decimal
    total_operating_costs_annual_gbp: Decimal
    net_operating_income_gbp: Decimal
    annual_mortgage_cost_gbp: Decimal
    annual_tax_liability_gbp: Decimal
    annual_cash_flow_gbp: Decimal
    monthly_cash_flow_gbp: Decimal
    gross_yield_percent: Decimal
    net_yield_percent: Decimal
    roce_percent: Decimal
    cash_on_cash_return_percent: Decimal
    ltv_percent: Decimal
    icr_percent: Decimal | None    # None for cash purchase (loan = 0)
    total_sdlt_gbp: Decimal
    total_acquisition_cost_gbp: Decimal
    total_cash_deployed_gbp: Decimal


@dataclass(frozen=True)
class EngineIntermediates:
    """
    All intermediate values produced during the calculation pipeline.

    Required for snapshot persistence, auditability, and reproducibility.
    Not all fields are displayed to users in routine operation.

    Tax pathway fields are None based on ownership_structure:
        income_tax_gross_gbp:           None for LIMITED_COMPANY
        mortgage_interest_tax_credit_gbp: None for LIMITED_COMPANY
        corporation_tax_gross_gbp:      None for INDIVIDUAL

    sdlt_band_breakdown is a list (not tuple) because the engine produces
    it as a plain list. The persistence layer converts to the domain entity
    representation (tuple in SnapshotIntermediates for frozen-compatibility).

    Source: ENGINE_CONTRACTS.md Part 3.2.
    """

    void_rate_decimal_applied: Decimal
    gross_annual_rent_gbp: Decimal
    effective_annual_rent_gbp: Decimal
    loan_amount_gbp: Decimal
    ltv_percent: Decimal
    monthly_mortgage_payment_gbp: Decimal
    annual_mortgage_cost_gbp: Decimal
    annual_mortgage_interest_gbp: Decimal
    letting_agent_annual_gbp: Decimal
    letting_agent_vat_rate_applied: Decimal
    annual_maintenance_reserve_gbp: Decimal
    total_operating_costs_annual_gbp: Decimal
    net_operating_income_gbp: Decimal
    sdlt_band_breakdown: tuple[SDLTBandResult, ...]  # ordered
    sdlt_base_gbp: Decimal
    sdlt_surcharge_gbp: Decimal
    sdlt_surcharge_rate_applied: Decimal
    total_sdlt_gbp: Decimal
    total_acquisition_cost_gbp: Decimal
    total_cash_deployed_gbp: Decimal
    stressed_annual_interest_gbp: Decimal
    stress_test_rate_applied_percent: Decimal
    taxable_income_or_profit_gbp: Decimal
    income_tax_gross_gbp: Decimal | None           # INDIVIDUAL pathway only
    mortgage_interest_tax_credit_gbp: Decimal | None  # INDIVIDUAL pathway only
    corporation_tax_gross_gbp: Decimal | None      # LIMITED_COMPANY pathway only
    annual_tax_liability_gbp: Decimal
    pre_tax_annual_cash_flow_gbp: Decimal
    section_24_applies: bool


@dataclass(frozen=True)
class RiskFlag:
    """
    A triggered risk flag from the calculation pipeline.

    triggered_by_value is always a string representation of the value at
    trigger time (e.g. "-331.90" for a cash flow value), ensuring a
    human-readable record independent of field format.

    Source: ENGINE_CONTRACTS.md Part 5.
    """

    code: str
    severity: FlagSeverity
    triggered_by_field: str
    triggered_by_value: str  # always a string regardless of originating type
    message: str


@dataclass(frozen=True)
class ValidationWarning:
    """
    A WARN-severity validation result that does not block calculation.

    Carried forward from the validation pipeline into EngineResult.
    Stored in the snapshot so the user can see what caveats applied.

    Source: ENGINE_CONTRACTS.md Part 4.
    """

    rule_code: str
    field: str
    message: str


@dataclass(frozen=True)
class EngineResult:
    """
    Returned by engine.run() on successful calculation.

    Contains no timestamps, no snapshot IDs, no database references, no
    version IDs, no user IDs, no deal IDs. Those are assigned by the
    persistence layer.

    Source: ENGINE_CONTRACTS.md Part 3.
    """

    outputs: EngineOutputs
    intermediates: EngineIntermediates
    risk_flags: list[RiskFlag]
    validation_warnings: list[ValidationWarning]


# ===========================================================================
# Validation types
# ===========================================================================
# Source: ENGINE_CONTRACTS.md Part 4.


@dataclass(frozen=True)
class ValidationError:
    """
    A HARD validation failure that blocks calculation.

    Source: ENGINE_CONTRACTS.md Part 4.
    """

    rule_code: str  # e.g. "V-07"
    field: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    """
    Returned by engine.run() when HARD validation rules fail.

    When is_valid is False, hard_errors is non-empty and no EngineResult
    is produced. warnings may be non-empty in both valid and invalid cases.

    Source: ENGINE_CONTRACTS.md Part 4.
    """

    is_valid: bool
    hard_errors: list[ValidationError]
    warnings: list[ValidationWarning]


# ===========================================================================
# EngineError
# ===========================================================================
# Source: ENGINE_CONTRACTS.md Part 6.


@dataclass(frozen=True)
class EngineError:
    """
    Returned by engine.run() on unexpected engine failure.

    The engine must never raise unhandled exceptions. All unexpected failures
    are caught and returned as EngineError.

    detail is sanitised — no stack traces. Server-side logs hold full detail.
    The calculation service logs the detail server-side, stores only a
    generic description in the audit record, and returns a generic error
    message to the API caller.

    Source: ENGINE_CONTRACTS.md Part 6.
    """

    error_code: str    # e.g. "DIVIDE_BY_ZERO", "UNEXPECTED_NONE"
    detail: str        # sanitised description
    engine_version: str
