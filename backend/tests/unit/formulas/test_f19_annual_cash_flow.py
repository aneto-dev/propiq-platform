"""
Tests for F-19 — Annual Cash Flow.

Formula: annual_cash_flow = noi - annual_mortgage_cost - annual_tax_liability

Source: CALCULATION_SPEC.md F-19; TEST_STRATEGY.md Part 3.3.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.engine.calculations.formulas import f19_annual_cash_flow

_TWO_DP = Decimal("0.01")


def r2(v: Decimal) -> Decimal:
    return v.quantize(_TWO_DP, rounding=ROUND_HALF_UP)

class TestF19AnnualCashFlow:

    def test_e01_negative_cash_flow(self) -> None:
        """
        E-01: noi=6,793.10, mortgage=7,125.00, tax=0.00
        6,793.10 - 7,125.00 - 0.00 = -331.90
        Source: ENGINE_CONTRACTS.md E-01.
        """
        result = f19_annual_cash_flow(
            net_operating_income=Decimal("6793.10"),
            annual_mortgage_cost=Decimal("7125.00"),
            annual_tax_liability=Decimal("0.00"),
        )
        assert r2(result) == Decimal("-331.90")

    def test_positive_cash_flow(self) -> None:
        """
        noi=8,000, mortgage=4,000, tax=500
        8,000 - 4,000 - 500 = 3,500.00
        """
        result = f19_annual_cash_flow(
            net_operating_income=Decimal("8000"),
            annual_mortgage_cost=Decimal("4000"),
            annual_tax_liability=Decimal("500"),
        )
        assert r2(result) == Decimal("3500.00")

    def test_zero_mortgage_and_tax(self) -> None:
        """Cash purchase with zero tax: cash_flow = noi."""
        result = f19_annual_cash_flow(
            net_operating_income=Decimal("6793.10"),
            annual_mortgage_cost=Decimal("0"),
            annual_tax_liability=Decimal("0"),
        )
        assert result == Decimal("6793.10")

    def test_no_floor_applied(self) -> None:
        """Negative result is valid — no floor at zero."""
        result = f19_annual_cash_flow(
            net_operating_income=Decimal("-500"),
            annual_mortgage_cost=Decimal("2000"),
            annual_tax_liability=Decimal("0"),
        )
        assert r2(result) == Decimal("-2500.00")

    def test_returns_decimal_not_float(self) -> None:
        result = f19_annual_cash_flow(
            net_operating_income=Decimal("6793.10"),
            annual_mortgage_cost=Decimal("7125.00"),
            annual_tax_liability=Decimal("0.00"),
        )
        assert isinstance(result, Decimal)

    def test_all_zero_inputs_returns_zero(self) -> None:
        result = f19_annual_cash_flow(
            net_operating_income=Decimal("0"),
            annual_mortgage_cost=Decimal("0"),
            annual_tax_liability=Decimal("0"),
        )
        assert result == Decimal("0")
