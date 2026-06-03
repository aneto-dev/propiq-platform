"""
Tests for F-18 — ROCE.

Formula: roce_percent = (net_operating_income / total_cash_deployed) × 100

Source: CALCULATION_SPEC.md F-18; TEST_STRATEGY.md Part 3.3.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.engine.calculations.formulas import f18_roce_percent

_TWO_DP = Decimal("0.01")


def r2(v: Decimal) -> Decimal:
    return v.quantize(_TWO_DP, rounding=ROUND_HALF_UP)

class TestF18ROCE:

    def test_e01_standard_case(self) -> None:
        """
        E-01: noi=6,793.10, cash_deployed=60,000
        6,793.10 / 60,000 × 100 = 11.32183... → 11.32
        Source: ENGINE_CONTRACTS.md E-01.
        """
        result = f18_roce_percent(
            net_operating_income=Decimal("6793.10"),
            total_cash_deployed=Decimal("60000"),
        )
        assert r2(result) == Decimal("11.32")

    def test_negative_noi_produces_negative_roce(self) -> None:
        """Negative NOI produces negative ROCE — no floor applied."""
        result = f18_roce_percent(
            net_operating_income=Decimal("-1000"),
            total_cash_deployed=Decimal("60000"),
        )
        assert r2(result) == Decimal("-1.67")

    def test_zero_noi_produces_zero_roce(self) -> None:
        result = f18_roce_percent(
            net_operating_income=Decimal("0"),
            total_cash_deployed=Decimal("60000"),
        )
        assert result == Decimal("0")

    def test_zero_deployed_guard(self) -> None:
        """total_cash_deployed=0 returns 0 without raising ZeroDivisionError."""
        result = f18_roce_percent(
            net_operating_income=Decimal("6793.10"),
            total_cash_deployed=Decimal("0"),
        )
        assert result == Decimal("0")

    def test_returns_decimal_not_float(self) -> None:
        result = f18_roce_percent(
            net_operating_income=Decimal("6793.10"),
            total_cash_deployed=Decimal("60000"),
        )
        assert isinstance(result, Decimal)
