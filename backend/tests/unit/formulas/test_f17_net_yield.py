"""
Tests for F-17 — Net Yield.

Formula: net_yield_percent = (net_operating_income / purchase_price) × 100

Financing-neutral and tax-neutral by design (ADR-004).
Source: CALCULATION_SPEC.md F-17; TEST_STRATEGY.md Part 3.3.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.engine.calculations.formulas import f17_net_yield_percent

_TWO_DP = Decimal("0.01")


def r2(v: Decimal) -> Decimal:
    return v.quantize(_TWO_DP, rounding=ROUND_HALF_UP)

class TestF17NetYield:

    def test_e01_standard_case(self) -> None:
        """
        E-01: noi=6,793.10, price=200,000
        6,793.10 / 200,000 × 100 = 3.396550 → 3.40
        Source: ENGINE_CONTRACTS.md E-01.
        """
        result = f17_net_yield_percent(
            net_operating_income=Decimal("6793.10"),
            purchase_price=Decimal("200000"),
        )
        assert r2(result) == Decimal("3.40")

    def test_negative_noi_produces_negative_yield(self) -> None:
        """
        noi=-500, price=200,000 → -500/200000×100 = -0.25
        Net yield may be negative when costs exceed effective rent.
        """
        result = f17_net_yield_percent(
            net_operating_income=Decimal("-500"),
            purchase_price=Decimal("200000"),
        )
        assert r2(result) == Decimal("-0.25")

    def test_zero_noi_produces_zero_yield(self) -> None:
        result = f17_net_yield_percent(
            net_operating_income=Decimal("0"),
            purchase_price=Decimal("200000"),
        )
        assert result == Decimal("0")

    def test_returns_decimal_not_float(self) -> None:
        result = f17_net_yield_percent(
            net_operating_income=Decimal("6793.10"),
            purchase_price=Decimal("200000"),
        )
        assert isinstance(result, Decimal)

    def test_zero_price_guard(self) -> None:
        """purchase_price=0 returns 0 without raising ZeroDivisionError."""
        result = f17_net_yield_percent(
            net_operating_income=Decimal("6793.10"),
            purchase_price=Decimal("0"),
        )
        assert result == Decimal("0")
