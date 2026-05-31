"""
Tests for F-08 — Annual Mortgage Interest.

Separates interest from capital for use in tax calculations (Section 24
and Corporation Tax). The interest component differs from annual_mortgage_cost
for repayment mortgages.

Interest-only:
    annual_interest = loan_amount × (rate / 100)
    (equals annual_mortgage_cost exactly)

Repayment (year 1 approximation):
    12-month loop summing monthly interest on declining balance.
    Limitation: overstates tax relief in later years. Disclosed to users.

Source: CALCULATION_SPEC.md F-08.
"""

from decimal import Decimal, ROUND_HALF_UP

import pytest

from app.domain.enums import MortgageType
from app.engine.calculations.formulas import (
    f06_monthly_mortgage_payment,
    f07_annual_mortgage_cost,
    f08_annual_mortgage_interest,
)


TWO_DP = Decimal("0.01")


def r2(value: Decimal) -> Decimal:
    return value.quantize(TWO_DP, rounding=ROUND_HALF_UP)


class TestF08AnnualMortgageInterestInterestOnly:

    def test_e01_reference_value(self) -> None:
        """
        E-01 IO: loan=150000, rate=4.75% → interest=7125.00.
        Manual: 150000 × 0.0475 = 7125.00.
        For interest-only, annual_interest = annual_mortgage_cost exactly.
        Source: ENGINE_CONTRACTS.md E-01.
        """
        result = f08_annual_mortgage_interest(
            Decimal("150000"), Decimal("4.75"),
            MortgageType.INTEREST_ONLY, Decimal("593.75")
        )
        assert r2(result) == Decimal("7125.00")

    def test_io_equals_annual_cost(self) -> None:
        """
        For interest-only mortgages, annual interest equals annual mortgage cost.
        No capital repayment element exists.
        """
        monthly = f06_monthly_mortgage_payment(
            Decimal("150000"), Decimal("5.00"), 25, MortgageType.INTEREST_ONLY
        )
        annual_cost = f07_annual_mortgage_cost(monthly)
        annual_interest = f08_annual_mortgage_interest(
            Decimal("150000"), Decimal("5.00"), MortgageType.INTEREST_ONLY, monthly
        )
        assert r2(annual_interest) == r2(annual_cost)

    def test_zero_rate_returns_zero(self) -> None:
        """Cash purchase: rate=0 → interest=0."""
        result = f08_annual_mortgage_interest(
            Decimal("150000"), Decimal("0"),
            MortgageType.INTEREST_ONLY, Decimal("0")
        )
        assert result == Decimal("0")


class TestF08AnnualMortgageInterestRepayment:

    def test_repayment_interest_less_than_total_cost(self) -> None:
        """
        For a repayment mortgage, annual interest (year 1) is less than the
        total annual mortgage cost because the payment also includes capital.
        """
        monthly = f06_monthly_mortgage_payment(
            Decimal("150000"), Decimal("4.75"), 25, MortgageType.REPAYMENT
        )
        annual_cost = f07_annual_mortgage_cost(monthly)
        annual_interest = f08_annual_mortgage_interest(
            Decimal("150000"), Decimal("4.75"), MortgageType.REPAYMENT, monthly
        )
        assert annual_interest < annual_cost

    def test_repayment_interest_positive(self) -> None:
        """Year 1 interest is always positive for a non-zero rate."""
        monthly = f06_monthly_mortgage_payment(
            Decimal("150000"), Decimal("4.75"), 25, MortgageType.REPAYMENT
        )
        result = f08_annual_mortgage_interest(
            Decimal("150000"), Decimal("4.75"), MortgageType.REPAYMENT, monthly
        )
        assert result > Decimal("0")

    def test_repayment_zero_rate_returns_zero(self) -> None:
        """Zero rate: no interest element regardless of mortgage type."""
        result = f08_annual_mortgage_interest(
            Decimal("150000"), Decimal("0"),
            MortgageType.REPAYMENT, Decimal("0")
        )
        assert result == Decimal("0")

    def test_result_is_decimal(self) -> None:
        """Return type must be Decimal, never float."""
        monthly = f06_monthly_mortgage_payment(
            Decimal("150000"), Decimal("4.75"), 25, MortgageType.REPAYMENT
        )
        result = f08_annual_mortgage_interest(
            Decimal("150000"), Decimal("4.75"), MortgageType.REPAYMENT, monthly
        )
        assert isinstance(result, Decimal)
