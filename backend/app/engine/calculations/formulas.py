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
