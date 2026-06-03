"""
Risk flag definitions — all 16 flags as declarative data.

Flags are informational. They do not block snapshot creation.
Each definition contains a condition callable that receives an
EvaluationContext and returns True when the flag should fire.

EvaluationContext is a frozen dataclass containing the exact fields
referenced by flag conditions — extracted from outputs, intermediates,
and inputs. No condition accesses EngineInput or EngineConfig directly.

The FLAG_DEFINITIONS list is ordered HIGH → MEDIUM → INFO, and within
each severity level by the order in CALCULATION_SPEC.md. The evaluator
iterates in declaration order, so result ordering is deterministic.

Ambiguity resolutions (Commit 2.7 planning):
  LOW_ICR_BASIC:        ownership check omitted — all valid structures are
                        already in {INDIVIDUAL, LIMITED_COMPANY}. None guard
                        is mandatory (cash purchase → icr_percent = None).
  LOW_MARGIN_SAFETY:    condition is strictly < 0.05. TEST_STRATEGY.md label
                        typo noted; CALCULATION_SPEC.md governs.
  LEASEHOLD_SHORT_LEASE: lease_years_remaining is int | None at the engine
                          boundary. None = no fire (guard required).

Source: CALCULATION_SPEC.md — Risk Flag Definitions.
        ENGINE_ARCHITECTURE.md — Risk flag evaluation structure.
        ENGINE_CONTRACTS.md — RiskFlag, FlagSeverity.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from decimal import Decimal

from app.domain.enums import FlagSeverity, IncomeTaxBand, OwnershipStructure, Tenure
from app.engine.contracts import RiskFlag

# ---------------------------------------------------------------------------
# EvaluationContext — immutable, explicit, no EngineInput/EngineConfig
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvaluationContext:
    """
    Extracted context passed to every flag condition.

    All fields are named explicitly. No condition may access EngineInput
    or EngineConfig — the orchestrator populates this context from the
    assembled outputs and intermediates.

    Fields from outputs:
        annual_cash_flow        — post-tax, post-mortgage
        gross_annual_rent       — F-01
        net_operating_income    — F-12
        gross_yield_percent     — F-16
        net_yield_percent       — F-17
        ltv_percent             — F-05
        icr_percent             — F-22b (None for cash purchase)

    Fields from intermediates:
        pre_tax_annual_cash_flow — noi - annual_mortgage_cost

    Fields from inputs (structural — not calculated):
        ownership_structure
        income_tax_band         — None for LIMITED_COMPANY
        tenure
        lease_years_remaining   — int | None (None for FREEHOLD;
                                  optionally None for LEASEHOLD)
        purchase_price
        refurbishment_cost
        monthly_rent
    """

    # outputs
    annual_cash_flow: Decimal
    gross_annual_rent: Decimal
    net_operating_income: Decimal
    gross_yield_percent: Decimal
    net_yield_percent: Decimal
    ltv_percent: Decimal
    icr_percent: Decimal | None

    # intermediates
    pre_tax_annual_cash_flow: Decimal

    # inputs (structural)
    ownership_structure: OwnershipStructure
    income_tax_band: IncomeTaxBand | None
    tenure: Tenure
    lease_years_remaining: int | None
    purchase_price: Decimal
    refurbishment_cost: Decimal
    monthly_rent: Decimal


# ---------------------------------------------------------------------------
# RiskFlagDefinition — declarative data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RiskFlagDefinition:
    """
    Declarative definition of a single risk flag.

    condition:       receives EvaluationContext, returns True when flag fires.
    value_extractor: receives EvaluationContext, returns the trigger value as
                     a string for storage in RiskFlag.triggered_by_value.
    """

    code: str
    severity: FlagSeverity
    triggered_by_field: str
    condition: Callable[[EvaluationContext], bool]
    value_extractor: Callable[[EvaluationContext], str]
    message: str


# ---------------------------------------------------------------------------
# Flag definitions — HIGH severity (ordered per CALCULATION_SPEC.md)
# ---------------------------------------------------------------------------

FLAG_DEFINITIONS: list[RiskFlagDefinition] = [
    # NEGATIVE_CASHFLOW
    RiskFlagDefinition(
        code="NEGATIVE_CASHFLOW",
        severity=FlagSeverity.HIGH,
        triggered_by_field="annual_cash_flow_gbp",
        condition=lambda c: c.annual_cash_flow < Decimal("0"),
        value_extractor=lambda c: str(c.annual_cash_flow.quantize(Decimal("0.01"))),
        message=(
            "This deal produces negative cash flow after all costs, mortgage "
            "payments, and estimated tax. You will need to fund a monthly "
            "shortfall from other income."
        ),
    ),
    # NEGATIVE_NOI
    RiskFlagDefinition(
        code="NEGATIVE_NOI",
        severity=FlagSeverity.HIGH,
        triggered_by_field="net_operating_income_gbp",
        condition=lambda c: c.net_operating_income < Decimal("0"),
        value_extractor=lambda c: str(c.net_operating_income.quantize(Decimal("0.01"))),
        message=(
            "Operating costs exceed effective rental income before any "
            "financing costs. This deal does not cover its own running costs."
        ),
    ),
    # LOW_GROSS_YIELD
    RiskFlagDefinition(
        code="LOW_GROSS_YIELD",
        severity=FlagSeverity.HIGH,
        triggered_by_field="gross_yield_percent",
        condition=lambda c: c.gross_yield_percent < Decimal("4.0"),
        value_extractor=lambda c: str(c.gross_yield_percent.quantize(Decimal("0.01"))),
        message=(
            "Gross yield is below 4%. After costs and financing this deal is "
            "likely to produce negative cash flow in most financing scenarios."
        ),
    ),
    # LOW_ICR_BASIC
    # Ownership check omitted: all valid OwnershipStructure values are already
    # in {INDIVIDUAL, LIMITED_COMPANY}. The check in CALCULATION_SPEC.md is
    # a documentation annotation. The None guard is mandatory — icr_percent
    # is None for cash purchases (ENGINE_CONTRACTS.md Part 6).
    RiskFlagDefinition(
        code="LOW_ICR_BASIC",
        severity=FlagSeverity.HIGH,
        triggered_by_field="icr_percent",
        condition=lambda c: (
            c.icr_percent is not None
            and c.icr_percent < Decimal("125")
        ),
        value_extractor=lambda c: (
            str(c.icr_percent.quantize(Decimal("0.01")))
            if c.icr_percent is not None
            else ""
        ),
        message=(
            "Interest coverage ratio is below 125%. This deal is unlikely to "
            "meet standard BTL mortgage affordability requirements at the "
            "stress test rate."
        ),
    ),
    # LOW_ICR_HIGHER_RATE
    RiskFlagDefinition(
        code="LOW_ICR_HIGHER_RATE",
        severity=FlagSeverity.HIGH,
        triggered_by_field="icr_percent",
        condition=lambda c: (
            c.icr_percent is not None
            and Decimal("125") <= c.icr_percent < Decimal("145")
            and c.income_tax_band in (
                IncomeTaxBand.HIGHER_RATE,
                IncomeTaxBand.ADDITIONAL_RATE,
            )
        ),
        value_extractor=lambda c: (
            str(c.icr_percent.quantize(Decimal("0.01")))
            if c.icr_percent is not None
            else ""
        ),
        message=(
            "ICR is below 145%. Higher-rate taxpayers face stricter lender "
            "requirements. Mortgage approval may be difficult even though "
            "the basic 125% threshold is met."
        ),
    ),
    # HIGH_LEVERAGE
    RiskFlagDefinition(
        code="HIGH_LEVERAGE",
        severity=FlagSeverity.HIGH,
        triggered_by_field="ltv_percent",
        condition=lambda c: c.ltv_percent > Decimal("75"),
        value_extractor=lambda c: str(c.ltv_percent.quantize(Decimal("0.01"))),
        message=(
            "LTV is above 75%. Most BTL lenders cap lending at 75% LTV. "
            "Product availability will be significantly limited above "
            "this threshold."
        ),
    ),
    # HIGH_LEVERAGE_EXTREME
    RiskFlagDefinition(
        code="HIGH_LEVERAGE_EXTREME",
        severity=FlagSeverity.HIGH,
        triggered_by_field="ltv_percent",
        condition=lambda c: c.ltv_percent > Decimal("85"),
        value_extractor=lambda c: str(c.ltv_percent.quantize(Decimal("0.01"))),
        message=(
            "LTV is above 85%. BTL mortgages at this leverage level are "
            "extremely rare. The deal as structured is unlikely to be "
            "mortgageable."
        ),
    ),
    # SECTION_24_IMPACT
    RiskFlagDefinition(
        code="SECTION_24_IMPACT",
        severity=FlagSeverity.HIGH,
        triggered_by_field="income_tax_band",
        condition=lambda c: (
            c.ownership_structure == OwnershipStructure.INDIVIDUAL
            and c.income_tax_band in (
                IncomeTaxBand.HIGHER_RATE,
                IncomeTaxBand.ADDITIONAL_RATE,
            )
        ),
        value_extractor=lambda c: c.income_tax_band.value if c.income_tax_band else "",
        message=(
            "As a higher or additional rate taxpayer, Section 24 significantly "
            "restricts your mortgage interest relief. Your post-tax returns are "
            "materially lower than pre-tax figures suggest. Consider whether a "
            "limited company structure is appropriate — take professional "
            "tax advice."
        ),
    ),
    # LEASEHOLD_SHORT_LEASE
    # lease_years_remaining is int | None at the engine boundary.
    # None = no fire (data-incomplete — guard required per TEST_STRATEGY.md 6.3).
    RiskFlagDefinition(
        code="LEASEHOLD_SHORT_LEASE",
        severity=FlagSeverity.HIGH,
        triggered_by_field="lease_years_remaining",
        condition=lambda c: (
            c.tenure == Tenure.LEASEHOLD
            and c.lease_years_remaining is not None
            and c.lease_years_remaining < 80
        ),
        value_extractor=lambda c: str(c.lease_years_remaining),
        message=(
            "Lease has fewer than 80 years remaining. This may affect mortgage "
            "availability and future saleability. Extending the lease before "
            "purchase is strongly advisable."
        ),
    ),
    # CASH_FLOW_PRE_TAX_ONLY
    RiskFlagDefinition(
        code="CASH_FLOW_PRE_TAX_ONLY",
        severity=FlagSeverity.HIGH,
        triggered_by_field="annual_cash_flow_gbp",
        condition=lambda c: (
            c.pre_tax_annual_cash_flow >= Decimal("0")
            and c.annual_cash_flow < Decimal("0")
        ),
        value_extractor=lambda c: str(c.annual_cash_flow.quantize(Decimal("0.01"))),
        message=(
            "This deal is cash flow positive before tax but negative after tax. "
            "Tax liability converts a pre-tax surplus into a post-tax shortfall. "
            "Review your tax position or consider a different ownership structure."
        ),
    ),
    # ---------------------------------------------------------------------------
    # MEDIUM severity
    # ---------------------------------------------------------------------------
    # LOW_NET_YIELD
    RiskFlagDefinition(
        code="LOW_NET_YIELD",
        severity=FlagSeverity.MEDIUM,
        triggered_by_field="net_yield_percent",
        condition=lambda c: c.net_yield_percent < Decimal("3.0"),
        value_extractor=lambda c: str(c.net_yield_percent.quantize(Decimal("0.01"))),
        message=(
            "Net yield is below 3%. The asset return after operating costs is "
            "low relative to financing costs in the current rate environment."
        ),
    ),
    # LOW_MARGIN_SAFETY
    # Condition is strictly < 0.05. TEST_STRATEGY.md has a "Fires:" label typo
    # on the boundary-exact case; CALCULATION_SPEC.md governs (strict inequality).
    RiskFlagDefinition(
        code="LOW_MARGIN_SAFETY",
        severity=FlagSeverity.MEDIUM,
        triggered_by_field="annual_cash_flow_gbp",
        condition=lambda c: (
            c.annual_cash_flow >= Decimal("0")
            and c.gross_annual_rent > Decimal("0")
            and (c.annual_cash_flow / c.gross_annual_rent) < Decimal("0.05")
        ),
        value_extractor=lambda c: str(c.annual_cash_flow.quantize(Decimal("0.01"))),
        message=(
            "Cash flow margin is very thin — less than 5% of gross rent. "
            "A modest increase in costs, void periods, or interest rates "
            "could push this deal into negative cash flow."
        ),
    ),
    # HIGH_REFURB_RATIO
    RiskFlagDefinition(
        code="HIGH_REFURB_RATIO",
        severity=FlagSeverity.MEDIUM,
        triggered_by_field="refurbishment_cost",
        condition=lambda c: (
            c.refurbishment_cost > c.purchase_price * Decimal("0.10")
        ),
        value_extractor=lambda c: str(c.refurbishment_cost.quantize(Decimal("0.01"))),
        message=(
            "Refurbishment cost exceeds 10% of purchase price. Verify that the "
            "refurbishment budget is realistic and that the post-refurbishment "
            "rental value supports the projected figures."
        ),
    ),
    # ATED_WARNING
    RiskFlagDefinition(
        code="ATED_WARNING",
        severity=FlagSeverity.MEDIUM,
        triggered_by_field="purchase_price",
        condition=lambda c: (
            c.ownership_structure == OwnershipStructure.LIMITED_COMPANY
            and c.purchase_price > Decimal("500000")
        ),
        value_extractor=lambda c: str(c.purchase_price.quantize(Decimal("0.01"))),
        message=(
            "Properties held in a limited company worth over £500,000 may be "
            "subject to ATED (Annual Tax on Enveloped Dwellings). This is not "
            "calculated here. Take professional advice before proceeding."
        ),
    ),
    # ---------------------------------------------------------------------------
    # INFO severity
    # ---------------------------------------------------------------------------
    # LTD_EXTRACTION_UNDISCLOSED — always fires for LIMITED_COMPANY
    RiskFlagDefinition(
        code="LTD_EXTRACTION_UNDISCLOSED",
        severity=FlagSeverity.INFO,
        triggered_by_field="ownership_structure",
        condition=lambda c: (
            c.ownership_structure == OwnershipStructure.LIMITED_COMPANY
        ),
        value_extractor=lambda c: c.ownership_structure.value,
        message=(
            "Profit extraction from a limited company (salary, dividends, or "
            "director's loan) incurs additional personal tax not modelled here. "
            "The post-tax return to you personally will be lower than the "
            "company-level figures shown."
        ),
    ),
    # RENT_UNVERIFIED — always fires (monthly_rent is always user-entered)
    RiskFlagDefinition(
        code="RENT_UNVERIFIED",
        severity=FlagSeverity.INFO,
        triggered_by_field="monthly_rent",
        condition=lambda c: True,
        value_extractor=lambda c: str(c.monthly_rent.quantize(Decimal("0.01"))),
        message=(
            "Monthly rent is an estimate entered by you. Actual achievable rent "
            "should be verified against comparable local lettings before "
            "committing to this deal."
        ),
    ),
]


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


def evaluate_flags(context: EvaluationContext) -> list[RiskFlag]:
    """
    Evaluate all flag definitions against the given context.

    Iterates FLAG_DEFINITIONS in declaration order (HIGH → MEDIUM → INFO).
    All flags are evaluated — no flag evaluation is skipped because another
    flag already fired.

    Returns a list of RiskFlag instances for all triggered definitions,
    in declaration order.

    Source: ENGINE_ARCHITECTURE.md — Risk flag evaluation structure.
    """
    results: list[RiskFlag] = []
    for defn in FLAG_DEFINITIONS:
        if defn.condition(context):
            results.append(
                RiskFlag(
                    code=defn.code,
                    severity=defn.severity,
                    triggered_by_field=defn.triggered_by_field,
                    triggered_by_value=defn.value_extractor(context),
                    message=defn.message,
                )
            )
    return results
