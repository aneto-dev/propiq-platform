"""
Tests for F-16 — Gross Yield.

Formula: gross_yield_percent = (gross_annual_rent / purchase_price) × 100

Source: CALCULATION_SPEC.md F-16; TEST_STRATEGY.md Part 3.3.
All expected values computed independently before tests were written.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.engine.calculations.formulas import f16_gross_yield_percent

_TWO_DP = Decimal("0.01")


def r2(v: Decimal) -> Decimal:
    return v.quantize(_TWO_DP, rounding=ROUND_HALF_UP)

class TestF16GrossYield:

    def test_e01_standard_case(self) -> None:
        """
        E-01: gross=11,400, price=200,000
        11,400 / 200,000 × 100 = 5.70
        Source: ENGINE_CONTRACTS.md E-01.
        """
        result = f16_gross_yield_percent(
            gross_annual_rent=Decimal("11400"),
            purchase_price=Decimal("200000"),
        )
        assert r2(result) == Decimal("5.70")

    def test_e03_ltd_co_case(self) -> None:
        """
        E-03: gross=19,200, price=350,000
        19,200 / 350,000 × 100 = 5.49
        Source: ENGINE_CONTRACTS.md E-03.
        Note: ENGINE_CONTRACTS.md shows 4.80 for E-03 — arithmetic error.
        Correct value is 5.49 (19200 / 350000 × 100 = 5.4857... → 5.49).
        """
        result = f16_gross_yield_percent(
            gross_annual_rent=Decimal("19200"),
            purchase_price=Decimal("350000"),
        )
        assert r2(result) == Decimal("5.49")

    def test_e05_higher_price(self) -> None:
        """
        E-05: gross=28,800, price=600,000
        28,800 / 600,000 × 100 = 4.80
        Source: ENGINE_CONTRACTS.md E-05.
        """
        result = f16_gross_yield_percent(
            gross_annual_rent=Decimal("28800"),
            purchase_price=Decimal("600000"),
        )
        assert r2(result) == Decimal("4.80")

    def test_returns_full_precision_decimal(self) -> None:
        """Result is Decimal at full precision; rounding by orchestrator only."""
        result = f16_gross_yield_percent(
            gross_annual_rent=Decimal("11400"),
            purchase_price=Decimal("200000"),
        )
        assert isinstance(result, Decimal)
        assert not isinstance(result, float)

    def test_zero_denominator_guard(self) -> None:
        """purchase_price=0 returns 0 without raising ZeroDivisionError."""
        result = f16_gross_yield_percent(
            gross_annual_rent=Decimal("11400"),
            purchase_price=Decimal("0"),
        )
        assert result == Decimal("0")
