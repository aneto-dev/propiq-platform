"""
Tests for F-20 — Monthly Cash Flow.

Formula: monthly_cash_flow = annual_cash_flow / 12

Source: CALCULATION_SPEC.md F-20; TEST_STRATEGY.md Part 3.3.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.engine.calculations.formulas import f20_monthly_cash_flow

_TWO_DP = Decimal("0.01")


def r2(v: Decimal) -> Decimal:
    return v.quantize(_TWO_DP, rounding=ROUND_HALF_UP)

class TestF20MonthlyCashFlow:

    def test_e01_negative_monthly(self) -> None:
        """
        E-01: annual=-331.90
        -331.90 / 12 = -27.658... → -27.66
        Source: ENGINE_CONTRACTS.md E-01.
        """
        result = f20_monthly_cash_flow(annual_cash_flow=Decimal("-331.90"))
        assert r2(result) == Decimal("-27.66")

    def test_positive_annual_divides_by_12(self) -> None:
        """
        annual=3,500 / 12 = 291.666... → 291.67
        """
        result = f20_monthly_cash_flow(annual_cash_flow=Decimal("3500"))
        assert r2(result) == Decimal("291.67")

    def test_zero_annual_produces_zero_monthly(self) -> None:
        result = f20_monthly_cash_flow(annual_cash_flow=Decimal("0"))
        assert result == Decimal("0")

    def test_exact_divisible_amount(self) -> None:
        """annual=1,200 / 12 = 100.00 exactly."""
        result = f20_monthly_cash_flow(annual_cash_flow=Decimal("1200"))
        assert r2(result) == Decimal("100.00")

    def test_returns_decimal_not_float(self) -> None:
        result = f20_monthly_cash_flow(annual_cash_flow=Decimal("-331.90"))
        assert isinstance(result, Decimal)
