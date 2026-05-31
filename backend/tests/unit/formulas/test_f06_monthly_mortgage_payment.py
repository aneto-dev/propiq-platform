"""
Tests for F-06 — Monthly Mortgage Payment.

Two pathways:
    Interest-only:  (loan × rate/100) / 12
    Repayment:      loan × (r(1+r)^n) / ((1+r)^n - 1)
                    where r = (rate/100)/12, n = term × 12

Source: CALCULATION_SPEC.md F-06.
"""

from decimal import Decimal, ROUND_HALF_UP

import pytest

from app.domain.enums import MortgageType
from app.engine.calculations.formulas import f06_monthly_mortgage_payment


TWO_DP = Decimal("0.01")


def r2(value: Decimal) -> Decimal:
    return value.quantize(TWO_DP, rounding=ROUND_HALF_UP)


class TestF06MonthlyMortgagePaymentInterestOnly:

    def test_e01_reference_value(self) -> None:
        """
        E-01: loan=150000, rate=4.75%, IO → monthly=593.75.
        Manual: (150000 × 0.0475) / 12 = 7125 / 12 = 593.75.
        Source: ENGINE_CONTRACTS.md E-01.
        """
        result = f06_monthly_mortgage_payment(
            Decimal("150000"), Decimal("4.75"), 25, MortgageType.INTEREST_ONLY
        )
        assert r2(result) == Decimal("593.75")

    def test_e03_reference_value(self) -> None:
        """
        E-03: loan=262500, rate=5.00%, IO → monthly=1093.75.
        Manual: (262500 × 0.05) / 12 = 13125 / 12 = 1093.75.
        Source: ENGINE_CONTRACTS.md E-03.
        """
        result = f06_monthly_mortgage_payment(
            Decimal("262500"), Decimal("5.00"), 25, MortgageType.INTEREST_ONLY
        )
        assert r2(result) == Decimal("1093.75")

    def test_higher_rate(self) -> None:
        """
        Loan=150000, rate=6.50%, IO → monthly=812.50.
        Manual: (150000 × 0.065) / 12 = 9750 / 12 = 812.50.
        Source: TEST_STRATEGY.md Section 3.3 F-06.
        """
        result = f06_monthly_mortgage_payment(
            Decimal("150000"), Decimal("6.50"), 25, MortgageType.INTEREST_ONLY
        )
        assert r2(result) == Decimal("812.50")

    def test_zero_interest_rate_returns_zero(self) -> None:
        """
        Zero interest rate (cash purchase) → monthly payment = 0.
        The orchestrator uses this to detect cash purchase.
        """
        result = f06_monthly_mortgage_payment(
            Decimal("150000"), Decimal("0"), 25, MortgageType.INTEREST_ONLY
        )
        assert result == Decimal("0")


class TestF06MonthlyMortgagePaymentRepayment:

    def test_repayment_greater_than_interest_only(self) -> None:
        """
        For the same loan and rate, repayment monthly cost > interest-only.
        Repayment includes capital; interest-only is interest only.
        """
        io = f06_monthly_mortgage_payment(
            Decimal("150000"), Decimal("4.75"), 25, MortgageType.INTEREST_ONLY
        )
        rep = f06_monthly_mortgage_payment(
            Decimal("150000"), Decimal("4.75"), 25, MortgageType.REPAYMENT
        )
        assert rep > io

    def test_repayment_150k_4_75_25yr(self) -> None:
        """
        Loan=150000, rate=4.75%, 25yr repayment → approximately £855.18/month.
        Parameters: r = 0.0475/12 = 0.003958333..., n = 300.
        Verified: standard mortgage calculator agrees.
        """
        result = f06_monthly_mortgage_payment(
            Decimal("150000"), Decimal("4.75"), 25, MortgageType.REPAYMENT
        )
        assert r2(result) == Decimal("855.18")

    def test_repayment_zero_rate_returns_zero(self) -> None:
        """Zero interest rate → returns 0 regardless of mortgage_type."""
        result = f06_monthly_mortgage_payment(
            Decimal("150000"), Decimal("0"), 25, MortgageType.REPAYMENT
        )
        assert result == Decimal("0")

    def test_result_is_decimal(self) -> None:
        """Return type must be Decimal, never float."""
        result = f06_monthly_mortgage_payment(
            Decimal("150000"), Decimal("4.75"), 25, MortgageType.REPAYMENT
        )
        assert isinstance(result, Decimal)
