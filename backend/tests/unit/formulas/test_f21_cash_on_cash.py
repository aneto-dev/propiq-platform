"""
Tests for F-21 — Cash-on-Cash Return.

Formula: cash_on_cash_return_percent = (annual_cash_flow / total_cash_deployed) × 100

Source: CALCULATION_SPEC.md F-21; TEST_STRATEGY.md Part 3.3.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.engine.calculations.formulas import f21_cash_on_cash_return_percent

_TWO_DP = Decimal("0.01")


def r2(v: Decimal) -> Decimal:
    return v.quantize(_TWO_DP, rounding=ROUND_HALF_UP)

class TestF21CashOnCash:

    def test_e01_negative_return(self) -> None:
        """
        E-01: annual=-331.90, deployed=60,000
        -331.90 / 60,000 × 100 = -0.5531... → -0.55
        Source: ENGINE_CONTRACTS.md E-01.
        """
        result = f21_cash_on_cash_return_percent(
            annual_cash_flow=Decimal("-331.90"),
            total_cash_deployed=Decimal("60000"),
        )
        assert r2(result) == Decimal("-0.55")

    def test_positive_return(self) -> None:
        """
        annual=3,500, deployed=60,000
        3,500 / 60,000 × 100 = 5.833... → 5.83
        """
        result = f21_cash_on_cash_return_percent(
            annual_cash_flow=Decimal("3500"),
            total_cash_deployed=Decimal("60000"),
        )
        assert r2(result) == Decimal("5.83")

    def test_zero_cash_flow_produces_zero_return(self) -> None:
        result = f21_cash_on_cash_return_percent(
            annual_cash_flow=Decimal("0"),
            total_cash_deployed=Decimal("60000"),
        )
        assert result == Decimal("0")

    def test_zero_deployed_guard(self) -> None:
        """total_cash_deployed=0 returns 0 without raising ZeroDivisionError."""
        result = f21_cash_on_cash_return_percent(
            annual_cash_flow=Decimal("3500"),
            total_cash_deployed=Decimal("0"),
        )
        assert result == Decimal("0")

    def test_returns_decimal_not_float(self) -> None:
        result = f21_cash_on_cash_return_percent(
            annual_cash_flow=Decimal("-331.90"),
            total_cash_deployed=Decimal("60000"),
        )
        assert isinstance(result, Decimal)
