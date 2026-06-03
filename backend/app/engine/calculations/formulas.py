"""
Formula functions F-01 through F-08.

Income, void, and financing formulas. Pure functions — every argument is
explicit, every return value is Decimal. No EngineInput, no EngineConfig,
no side effects.

Rounding rules (ENGINE_CONTRACTS.md Part 7):
    - Intermediate calculations: full Decimal precision, no rounding.
    - Values returned from these functions: NOT rounded.
    - Rounding to 2dp with ROUND_HALF_UP occurs ONLY when the orchestrator
      writes values into EngineOutputs or EngineIntermediates.

float is never used. All arguments and return values are Decimal.

CALCULATION_SPEC.md is the authoritative source for every formula.
"""

from __future__ import annotations

from decimal import Decimal
from typing import NamedTuple

from app.domain.enums import MortgageType

# ---------------------------------------------------------------------------
# F-01 — Gross Annual Rent
# CALCULATION_SPEC.md: gross_annual_rent = monthly_rent × 12
# ---------------------------------------------------------------------------


def f01_gross_annual_rent(monthly_rent: Decimal) -> Decimal:
    """
    Gross annual rent before voids and costs.

    gross_annual_rent = monthly_rent × 12

    Assumes a consistent monthly rent for the full year. Rent reviews and
    mid-tenancy adjustments are not modelled in v1.0.

    Args:
        monthly_rent: User-estimated achievable monthly rent in GBP.

    Returns:
        Gross annual rent in GBP at full precision.
    """
    return monthly_rent * Decimal("12")


# ---------------------------------------------------------------------------
# F-02 — Void Rate Conversion
# CALCULATION_SPEC.md: void_rate_decimal = void_rate_percent / 100
# ---------------------------------------------------------------------------


def f02_void_rate_decimal(void_rate_percent: Decimal) -> Decimal:
    """
    Convert void rate from percentage to decimal fraction.

    void_rate_decimal = void_rate_percent / 100

    The void_rate_percent input is a percentage of the year (e.g. 3.85 for
    3.85%). The decimal form is used directly in F-03.

    Args:
        void_rate_percent: Void rate as a percentage value (0–100).

    Returns:
        Void rate as a decimal fraction at full precision.
    """
    return void_rate_percent / Decimal("100")


# ---------------------------------------------------------------------------
# F-03 — Effective Annual Rent
# CALCULATION_SPEC.md F-03:
# effective_annual_rent = gross_annual_rent × (1 - void_rate_decimal)
# ---------------------------------------------------------------------------


def f03_effective_annual_rent(
    gross_annual_rent: Decimal,
    void_rate_decimal: Decimal,
) -> Decimal:
    """
    Annual rent after accounting for void periods.

    effective_annual_rent = gross_annual_rent × (1 - void_rate_decimal)

    Void rate is applied to gross_annual_rent, not effective rent, to correctly
    model full revenue loss during vacant periods including contractual rent
    weeks when the property is empty.

    Args:
        gross_annual_rent: Output of F-01.
        void_rate_decimal: Output of F-02 (fraction, not percentage).

    Returns:
        Effective annual rent in GBP at full precision.
    """
    return gross_annual_rent * (Decimal("1") - void_rate_decimal)


# ---------------------------------------------------------------------------
# F-04 — Loan Amount
# CALCULATION_SPEC.md: loan_amount = purchase_price - deposit_amount
# ---------------------------------------------------------------------------


def f04_loan_amount(
    purchase_price: Decimal,
    deposit_amount: Decimal,
) -> Decimal:
    """
    Mortgage loan amount.

    loan_amount = purchase_price - deposit_amount

    Args:
        purchase_price: Agreed purchase price in GBP.
        deposit_amount: Investor cash deposit in GBP.

    Returns:
        Loan amount in GBP at full precision.
    """
    return purchase_price - deposit_amount


# ---------------------------------------------------------------------------
# F-05 — Loan-to-Value (LTV)
# CALCULATION_SPEC.md: ltv_percent = (loan_amount / purchase_price) × 100
# ---------------------------------------------------------------------------


def f05_ltv_percent(
    loan_amount: Decimal,
    purchase_price: Decimal,
) -> Decimal:
    """
    Loan-to-value ratio expressed as a percentage.

    ltv_percent = (loan_amount / purchase_price) × 100

    Returns a percentage value (e.g. 75.0 for 75% LTV).
    Returns Decimal("0") for a cash purchase (loan_amount = 0).

    Args:
        loan_amount: Output of F-04.
        purchase_price: Agreed purchase price in GBP.

    Returns:
        LTV as a percentage value at full precision.
    """
    if purchase_price == Decimal("0"):
        return Decimal("0")
    return (loan_amount / purchase_price) * Decimal("100")


# ---------------------------------------------------------------------------
# F-06 — Monthly Mortgage Payment
# CALCULATION_SPEC.md: two pathways — interest-only and repayment annuity
# ---------------------------------------------------------------------------


def f06_monthly_mortgage_payment(
    loan_amount: Decimal,
    mortgage_interest_rate: Decimal,
    mortgage_term_years: int,
    mortgage_type: MortgageType,
) -> Decimal:
    """
    Monthly mortgage payment.

    Interest-only:
        monthly_payment = (loan_amount × (rate / 100)) / 12

    Repayment (standard annuity):
        r = (rate / 100) / 12          (monthly rate)
        n = term_years × 12            (total payments)
        monthly_payment = loan_amount × (r × (1+r)^n) / ((1+r)^n - 1)

    Zero interest rate (cash purchase):
        Returns Decimal("0"). The orchestrator applies the CASH_PURCHASE
        path. Do not attempt the repayment formula with rate=0.

    All arithmetic uses Decimal throughout. float is never introduced.

    Args:
        loan_amount: Output of F-04.
        mortgage_interest_rate: Annual interest rate as a percentage (e.g. 4.75).
        mortgage_term_years: Loan term in years (5–35).
        mortgage_type: INTEREST_ONLY or REPAYMENT.

    Returns:
        Monthly mortgage payment in GBP at full precision.
    """
    if mortgage_interest_rate == Decimal("0"):
        return Decimal("0")

    if mortgage_type == MortgageType.INTEREST_ONLY:
        return (loan_amount * (mortgage_interest_rate / Decimal("100"))) / Decimal("12")

    # Repayment — standard annuity formula using Decimal arithmetic
    # r = monthly rate, n = total number of payments
    r = (mortgage_interest_rate / Decimal("100")) / Decimal("12")
    n = mortgage_term_years * 12

    # (1 + r)^n using Decimal power (integer exponent is exact)
    one_plus_r_to_n = (Decimal("1") + r) ** n

    numerator = loan_amount * r * one_plus_r_to_n
    denominator = one_plus_r_to_n - Decimal("1")

    return numerator / denominator


# ---------------------------------------------------------------------------
# F-07 — Annual Mortgage Cost
# CALCULATION_SPEC.md: annual_mortgage_cost = monthly_mortgage_payment × 12
# ---------------------------------------------------------------------------


def f07_annual_mortgage_cost(monthly_mortgage_payment: Decimal) -> Decimal:
    """
    Total annual mortgage payments (principal + interest for repayment).

    annual_mortgage_cost = monthly_mortgage_payment × 12

    For tax purposes, only the interest component (F-08) is deductible.
    This total cost is used in cash flow calculations (F-19).

    Args:
        monthly_mortgage_payment: Output of F-06.

    Returns:
        Annual mortgage cost in GBP at full precision.
    """
    return monthly_mortgage_payment * Decimal("12")


# ---------------------------------------------------------------------------
# F-08 — Annual Mortgage Interest (for tax calculations)
# CALCULATION_SPEC.md: separates interest from capital for Section 24 and CT
# ---------------------------------------------------------------------------


def f08_annual_mortgage_interest(
    loan_amount: Decimal,
    mortgage_interest_rate: Decimal,
    mortgage_type: MortgageType,
    monthly_mortgage_payment: Decimal,
) -> Decimal:
    """
    Annual mortgage interest portion (for tax pathway calculations).

    Required separately from annual_mortgage_cost because:
    - Section 24 (INDIVIDUAL): basic-rate tax credit on interest only
    - Ltd Co (LIMITED_COMPANY): interest is fully deductible as a business cost

    Interest-only:
        annual_mortgage_interest = loan_amount × (rate / 100)
        (equals annual_mortgage_cost exactly for interest-only)

    Repayment — Year 1 interest approximation:
        The interest portion reduces each year as capital is repaid. v1.0
        uses year 1 interest only, derived from the annuity balance formula.

        r = (rate / 100) / 12
        n = total payments (term × 12)

        remaining_balance_after_12 =
            loan_amount × ((1+r)^n - (1+r)^12) / ((1+r)^n - 1)

        annual_capital_repaid_year1 = loan_amount - remaining_balance_after_12
        annual_mortgage_interest = (monthly_payment × 12) - annual_capital_repaid_year1

        This overstates tax relief in later years as interest falls. This
        limitation is disclosed to users.

    Zero rate (cash purchase):
        Returns Decimal("0").

    Args:
        loan_amount: Output of F-04.
        mortgage_interest_rate: Annual rate as a percentage.
        mortgage_type: INTEREST_ONLY or REPAYMENT.
        monthly_mortgage_payment: Output of F-06 (needed for repayment path).

    Returns:
        Annual mortgage interest in GBP at full precision.
    """
    if mortgage_interest_rate == Decimal("0"):
        return Decimal("0")

    if mortgage_type == MortgageType.INTEREST_ONLY:
        return loan_amount * (mortgage_interest_rate / Decimal("100"))

    # Repayment — year 1 interest approximation
    r = (mortgage_interest_rate / Decimal("100")) / Decimal("12")
    # Use the mortgage_term_years embedded in the monthly payment via n.
    # We cannot accept term as a parameter without changing the signature,
    # so we derive from the relationship: n is not directly available here.
    # Instead use the standard annuity interest extraction for year 1:
    #
    #   annual_interest_year1 = sum of monthly interests for months 1–12
    #   monthly_interest_m    = remaining_balance_(m-1) × r
    #
    # This is exact and avoids storing n. The loop runs exactly 12 times.
    balance = loan_amount
    total_interest = Decimal("0")
    for _ in range(12):
        monthly_interest = balance * r
        capital_repaid = monthly_mortgage_payment - monthly_interest
        total_interest += monthly_interest
        balance -= capital_repaid

    return total_interest

# ── ADDITIONS to formulas.py ─────────────────────────────────────────────────
# Append these functions after f08_annual_mortgage_interest in formulas.py.
# ---------------------------------------------------------------------------
# F-09 — Letting Agent Annual Cost
# CALCULATION_SPEC.md F-09:
# letting_agent_annual = gross_annual_rent × (fee_pct / 100) × (1 + vat_pct / 100)
#
# Applied to gross_annual_rent (contractual rent), not effective_annual_rent.
# Most management contracts charge on rent due, not rent received.
# See CALCULATION_SPEC.md F-09 realism note.
# ---------------------------------------------------------------------------


def f09_letting_agent_annual(
    gross_annual_rent: Decimal,
    letting_agent_fee_percent: Decimal,
    letting_agent_vat_rate_percent: Decimal,
) -> Decimal:
    """
    Annual letting agent management fee including VAT.

    letting_agent_annual = gross_annual_rent
                           × (letting_agent_fee_percent / 100)
                           × (1 + letting_agent_vat_rate_percent / 100)

    Applied to gross_annual_rent (contractual rent due), not effective_annual_rent.
    Residential landlords cannot reclaim VAT on management fees.
    VAT rate is taken from configuration — never hardcoded.

    Args:
        gross_annual_rent: Output of F-01 (monthly_rent × 12).
        letting_agent_fee_percent: Management fee as a percentage (e.g. 10.0).
        letting_agent_vat_rate_percent: VAT rate as a percentage (e.g. 20.0).

    Returns:
        Annual letting agent cost in GBP at full precision.
    """
    fee_decimal = letting_agent_fee_percent / Decimal("100")
    vat_multiplier = Decimal("1") + (letting_agent_vat_rate_percent / Decimal("100"))
    return gross_annual_rent * fee_decimal * vat_multiplier


# ---------------------------------------------------------------------------
# F-10 — Annual Maintenance Reserve
# CALCULATION_SPEC.md F-10:
# annual_maintenance_reserve = purchase_price × (maintenance_reserve_percent / 100)
# ---------------------------------------------------------------------------


def f10_annual_maintenance_reserve(
    purchase_price: Decimal,
    maintenance_reserve_percent: Decimal,
) -> Decimal:
    """
    Annual maintenance reserve as a percentage of purchase price.

    annual_maintenance_reserve = purchase_price × (maintenance_reserve_percent / 100)

    A smoothed annual reserve for repairs and maintenance. Does not model
    major capital items (roof, boiler). Users are shown this limitation.

    Args:
        purchase_price: Agreed purchase price in GBP.
        maintenance_reserve_percent: Reserve rate as a percentage (e.g. 1.0).

    Returns:
        Annual maintenance reserve in GBP at full precision.
    """
    return purchase_price * (maintenance_reserve_percent / Decimal("100"))


# ---------------------------------------------------------------------------
# F-11 — Total Annual Operating Costs
# CALCULATION_SPEC.md F-11: sum of six recurring annual cost components.
# One-off acquisition costs (SDLT, legal, refurb) are excluded.
# ---------------------------------------------------------------------------


def f11_total_operating_costs(
    letting_agent_annual: Decimal,
    annual_maintenance_reserve: Decimal,
    landlord_insurance_annual: Decimal,
    annual_service_charge: Decimal,
    annual_ground_rent: Decimal,
    annual_accountancy_cost: Decimal,
) -> Decimal:
    """
    Total recurring annual operating costs.

    total_operating_costs =
        letting_agent_annual
      + annual_maintenance_reserve
      + landlord_insurance_annual
      + annual_service_charge
      + annual_ground_rent
      + annual_accountancy_cost

    Excludes one-off acquisition costs (SDLT, legal fees, refurbishment).
    All six components must be provided; use Decimal("0") for absent items.

    Args:
        letting_agent_annual: Output of F-09.
        annual_maintenance_reserve: Output of F-10.
        landlord_insurance_annual: From EngineInput (user or config default).
        annual_service_charge: From EngineInput (0 for freehold).
        annual_ground_rent: From EngineInput (0 for freehold).
        annual_accountancy_cost: From EngineInput (user or config default).

    Returns:
        Total annual operating costs in GBP at full precision.
    """
    return (
        letting_agent_annual
        + annual_maintenance_reserve
        + landlord_insurance_annual
        + annual_service_charge
        + annual_ground_rent
        + annual_accountancy_cost
    )


# ---------------------------------------------------------------------------
# F-12 — Net Operating Income (NOI)
# CALCULATION_SPEC.md F-12:
# net_operating_income = effective_annual_rent − total_operating_costs_annual
# ---------------------------------------------------------------------------


def f12_net_operating_income(
    effective_annual_rent: Decimal,
    total_operating_costs: Decimal,
) -> Decimal:
    """
    Net operating income — financing-neutral, tax-neutral.

    net_operating_income = effective_annual_rent - total_operating_costs

    Represents the income-generating performance of the asset independent
    of how it is financed or owned. May be negative if costs exceed rent.

    Args:
        effective_annual_rent: Output of F-03.
        total_operating_costs: Output of F-11.

    Returns:
        NOI in GBP at full precision. May be negative.
    """
    return effective_annual_rent - total_operating_costs


# ---------------------------------------------------------------------------
# F-13 — SDLT Calculation
# CALCULATION_SPEC.md F-13: progressive banded calculation + flat surcharge.
#
# Return type: SDLTResult NamedTuple defined below.
# Band inputs: plain tuples of (band_lower, band_upper|None, rate) as Decimal.
# The orchestrator unpacks SDLTBand objects into this plain-tuple format
# before calling this function, keeping formulas.py import-free from
# app.engine.contracts. (ENGINE_ARCHITECTURE.md — calculations has no
# engine-internal dependencies.)
# ---------------------------------------------------------------------------


class SDLTBandCalculation(NamedTuple):
    """
    Per-band result from the SDLT calculation.

    All values are Decimal. rate is a decimal fraction (e.g. 0.02 for 2%).
    band_upper is None for the top band.

    This type is defined in formulas.py to keep the calculations submodule
    free from imports of app.engine.contracts or app.domain.
    The orchestrator maps SDLTBandCalculation → SDLTBandResult (contracts)
    when assembling EngineIntermediates.
    """

    band_lower: Decimal
    band_upper: Decimal | None
    rate: Decimal
    taxable_in_band: Decimal
    tax_in_band: Decimal


class SDLTResult(NamedTuple):
    """
    Complete result of the SDLT calculation (F-13).

    sdlt_base, sdlt_surcharge, and total_sdlt are all rounded to 2dp.
    band_breakdown contains every band where taxable_in_band > 0,
    ordered ascending by band_lower.

    total_sdlt = sdlt_base + sdlt_surcharge.
    sum(b.tax_in_band for b in band_breakdown) == sdlt_base (verified by tests).
    """

    sdlt_base: Decimal
    sdlt_surcharge: Decimal
    total_sdlt: Decimal
    band_breakdown: tuple[SDLTBandCalculation, ...]


def f13_sdlt(
    purchase_price: Decimal,
    bands: tuple[tuple[Decimal, Decimal | None, Decimal], ...],
    additional_dwelling_surcharge_rate: Decimal,
    is_additional_dwelling: bool,
) -> SDLTResult:
    """
    SDLT calculation — progressive banded rate structure plus optional surcharge.

    Base calculation (all purchases):
        For each band where band_lower < purchase_price:
            taxable_in_band = MIN(purchase_price, band_upper) - band_lower
            tax_in_band     = taxable_in_band × rate
        sdlt_base = SUM(tax_in_band for all applicable bands)

    Additional dwelling surcharge (when is_additional_dwelling = True):
        sdlt_surcharge = purchase_price × additional_dwelling_surcharge_rate

    Total:
        total_sdlt = sdlt_base + sdlt_surcharge

    SDLT rates and thresholds are NEVER hardcoded. They come from the versioned
    configuration passed by the orchestrator. This function is configuration-
    agnostic — it works for any banded structure.

    Args:
        purchase_price: Agreed purchase price in GBP.
        bands: Ordered tuple of (band_lower, band_upper|None, rate) tuples.
               rate is a decimal fraction (e.g. Decimal("0.02") for 2%).
               band_upper is None for the top band.
        additional_dwelling_surcharge_rate: Decimal fraction (e.g. 0.03 for 3%).
        is_additional_dwelling: True applies the surcharge to the full price.

    Returns:
        SDLTResult with sdlt_base, sdlt_surcharge, total_sdlt, band_breakdown.
    """
    sdlt_base = Decimal("0")
    band_results: list[SDLTBandCalculation] = []

    for band_lower, band_upper, rate in bands:
        if purchase_price <= band_lower:
            break
        # Taxable amount in this band
        upper = band_upper if band_upper is not None else purchase_price
        taxable = min(purchase_price, upper) - band_lower
        tax = taxable * rate
        band_results.append(
            SDLTBandCalculation(
                band_lower=band_lower,
                band_upper=band_upper,
                rate=rate,
                taxable_in_band=taxable,
                tax_in_band=tax,
            )
        )
        sdlt_base += tax

    sdlt_surcharge = (
        purchase_price * additional_dwelling_surcharge_rate
        if is_additional_dwelling
        else Decimal("0")
    )
    total_sdlt = sdlt_base + sdlt_surcharge

    return SDLTResult(
        sdlt_base=sdlt_base,
        sdlt_surcharge=sdlt_surcharge,
        total_sdlt=total_sdlt,
        band_breakdown=tuple(band_results),
    )


# ---------------------------------------------------------------------------
# F-14 — Total Acquisition Cost
# CALCULATION_SPEC.md F-14:
# total_acquisition_cost = purchase_price + total_sdlt
#                          + purchase_legal_costs + refurbishment_cost
# ---------------------------------------------------------------------------


def f14_total_acquisition_cost(
    purchase_price: Decimal,
    total_sdlt: Decimal,
    purchase_legal_costs: Decimal,
    refurbishment_cost: Decimal,
) -> Decimal:
    """
    Total acquisition cost — all one-time costs to purchase and prepare.

    total_acquisition_cost = purchase_price
                             + total_sdlt
                             + purchase_legal_costs
                             + refurbishment_cost

    Args:
        purchase_price: Agreed purchase price in GBP.
        total_sdlt: Output of F-13 (SDLTResult.total_sdlt).
        purchase_legal_costs: Conveyancing and survey fees.
        refurbishment_cost: One-off pre-let costs (may be 0).

    Returns:
        Total acquisition cost in GBP at full precision.
    """
    return purchase_price + total_sdlt + purchase_legal_costs + refurbishment_cost


# ---------------------------------------------------------------------------
# F-15 — Total Cash Deployed
# CALCULATION_SPEC.md F-15:
# total_cash_deployed = deposit_amount + total_sdlt
#                       + purchase_legal_costs + refurbishment_cost
#
# The loan amount is excluded. total_cash_deployed represents the investor's
# own cash outlay — the denominator in cash-on-cash return and ROCE.
# ---------------------------------------------------------------------------


def f15_total_cash_deployed(
    deposit_amount: Decimal,
    total_sdlt: Decimal,
    purchase_legal_costs: Decimal,
    refurbishment_cost: Decimal,
) -> Decimal:
    """
    Total investor cash deployed — own capital only, loan excluded.

    total_cash_deployed = deposit_amount
                          + total_sdlt
                          + purchase_legal_costs
                          + refurbishment_cost

    The mortgage loan is excluded because it is not the investor's own cash.
    This figure is the denominator in cash-on-cash return (F-21) and ROCE (F-18).

    Args:
        deposit_amount: Investor cash deposit (purchase_price - loan_amount).
        total_sdlt: Output of F-13.
        purchase_legal_costs: Conveyancing and survey fees.
        refurbishment_cost: One-off pre-let costs (may be 0).

    Returns:
        Total cash deployed in GBP at full precision.
    """
    return deposit_amount + total_sdlt + purchase_legal_costs + refurbishment_cost



# ---------------------------------------------------------------------------
# F-16 — Gross Yield
# ---------------------------------------------------------------------------


def f16_gross_yield_percent(
    gross_annual_rent: Decimal,
    purchase_price: Decimal,
) -> Decimal:
    """
    Gross yield as a percentage of purchase price.

    gross_yield_percent = (gross_annual_rent / purchase_price) × 100

    Disclosure: gross yield is a headline comparison metric only.
    It does not reflect voids, costs, financing, or tax.

    Source: CALCULATION_SPEC.md F-16; DOMAIN_GLOSSARY.md — Gross Yield.
    """
    if purchase_price == Decimal("0"):
        return Decimal("0")
    return gross_annual_rent / purchase_price * Decimal("100")


# ---------------------------------------------------------------------------
# F-17 — Net Yield
# ---------------------------------------------------------------------------


def f17_net_yield_percent(
    net_operating_income: Decimal,
    purchase_price: Decimal,
) -> Decimal:
    """
    Net yield as a percentage of purchase price.

    net_yield_percent = (net_operating_income / purchase_price) × 100

    Financing-neutral and tax-neutral by design (ADR-004).
    May be negative when operating costs exceed effective rent.

    Source: CALCULATION_SPEC.md F-17; DOMAIN_GLOSSARY.md — Net Yield.
    """
    if purchase_price == Decimal("0"):
        return Decimal("0")
    return net_operating_income / purchase_price * Decimal("100")


# ---------------------------------------------------------------------------
# F-18 — ROCE
# ---------------------------------------------------------------------------


def f18_roce_percent(
    net_operating_income: Decimal,
    total_cash_deployed: Decimal,
) -> Decimal:
    """
    Return on Capital Employed as a percentage of total cash deployed.

    roce_percent = (net_operating_income / total_cash_deployed) × 100

    Financing-neutral and tax-neutral. Uses total_cash_deployed (investor's
    actual cash) as denominator rather than purchase_price, reflecting the
    leveraged nature of the investment.

    Zero guard: V-05 prevents deposit=0 so total_cash_deployed is always
    > 0 after successful validation. The guard handles the theoretically
    unreachable case without raising.

    Source: CALCULATION_SPEC.md F-18; DOMAIN_GLOSSARY.md — ROCE.
    """
    if total_cash_deployed == Decimal("0"):
        return Decimal("0")
    return net_operating_income / total_cash_deployed * Decimal("100")


# ---------------------------------------------------------------------------
# F-19 — Annual Cash Flow
# ---------------------------------------------------------------------------


def f19_annual_cash_flow(
    net_operating_income: Decimal,
    annual_mortgage_cost: Decimal,
    annual_tax_liability: Decimal,
) -> Decimal:
    """
    Annual cash flow after operating costs, financing, and estimated tax.

    annual_cash_flow = net_operating_income
                     - annual_mortgage_cost
                     - annual_tax_liability

    May be negative. No floor is applied — a negative result is a valid
    and meaningful output (the investor must fund a monthly shortfall).

    Source: CALCULATION_SPEC.md F-19; DOMAIN_GLOSSARY.md — Annual Cash Flow.
    """
    return net_operating_income - annual_mortgage_cost - annual_tax_liability


# ---------------------------------------------------------------------------
# F-20 — Monthly Cash Flow
# ---------------------------------------------------------------------------


def f20_monthly_cash_flow(
    annual_cash_flow: Decimal,
) -> Decimal:
    """
    Monthly cash flow derived from annual cash flow.

    monthly_cash_flow = annual_cash_flow / 12

    May be negative. No floor applied.

    Source: CALCULATION_SPEC.md F-20.
    """
    return annual_cash_flow / Decimal("12")


# ---------------------------------------------------------------------------
# F-21 — Cash-on-Cash Return
# ---------------------------------------------------------------------------


def f21_cash_on_cash_return_percent(
    annual_cash_flow: Decimal,
    total_cash_deployed: Decimal,
) -> Decimal:
    """
    Cash-on-cash return as a percentage of total cash deployed.

    cash_on_cash_return_percent = (annual_cash_flow / total_cash_deployed) × 100

    Post-financing and post-tax. The most meaningful return metric for a
    leveraged investor assessing actual cash generated relative to cash
    committed. May be negative.

    Zero guard matches F-18 rationale — unreachable after V-05 but defensive.

    Source: CALCULATION_SPEC.md F-21; DOMAIN_GLOSSARY.md — Cash-on-Cash Return.
    """
    if total_cash_deployed == Decimal("0"):
        return Decimal("0")
    return annual_cash_flow / total_cash_deployed * Decimal("100")


# ---------------------------------------------------------------------------
# F-22 — ICR Stress Test
# Split into two functions per ENGINE_ARCHITECTURE.md Step 11.
# ---------------------------------------------------------------------------


def f22_stressed_annual_interest(
    loan_amount: Decimal,
    stress_test_rate_percent: Decimal,
) -> Decimal:
    """
    Stressed annual interest at the lender stress-test rate.

    stressed_annual_interest = loan_amount × (stress_test_rate_percent / 100)

    The rate is applied as interest-only regardless of actual mortgage type.
    This reflects standard BTL lender affordability methodology.

    For a cash purchase (loan_amount = 0), returns 0. The orchestrator
    detects this and sets icr_percent = None.

    Source: CALCULATION_SPEC.md F-22 (Stressed Annual Interest).
    """
    return loan_amount * (stress_test_rate_percent / Decimal("100"))


def f22_icr_percent(
    effective_annual_rent: Decimal,
    stressed_annual_interest: Decimal,
) -> Decimal | None:
    """
    Interest Coverage Ratio as a percentage of stressed annual interest.

    icr_percent = (effective_annual_rent / stressed_annual_interest) × 100

    Returns None when stressed_annual_interest is zero (cash purchase —
    loan_amount = 0). The caller must handle None explicitly.

    ENGINE_CONTRACTS.md Part 3.1: icr_percent: Decimal | None —
    None when cash purchase (loan = 0).

    Source: CALCULATION_SPEC.md F-22 (ICR); DOMAIN_GLOSSARY.md — ICR.
    """
    if stressed_annual_interest == Decimal("0"):
        return None
    return effective_annual_rent / stressed_annual_interest * Decimal("100")
