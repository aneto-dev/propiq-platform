"""
Tests for F-05 — Loan-to-Value (LTV).

Formula: ltv_percent = (loan_amount / purchase_price) × 100
Source: CALCULATION_SPEC.md F-05.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.engine.calculations.formulas import f05_ltv_percent

TWO_DP = Decimal("0.01")


def r2(value: Decimal) -> Decimal:
    return value.quantize(TWO_DP, rounding=ROUND_HALF_UP)


class TestF05LTV:

    def test_e01_reference_value(self) -> None:
        """
        E-01: loan=150000, purchase=200000 → LTV=75.00%.
        Manual: (150000/200000) × 100 = 75.00.
        Source: ENGINE_CONTRACTS.md E-01.
        """
        result = f05_ltv_percent(Decimal("150000"), Decimal("200000"))
        assert r2(result) == Decimal("75.00")

    def test_sixty_percent_ltv(self) -> None:
        """
        Loan £180,000 on £300,000 property → LTV 60.00%.
        Manual: (180000/300000) × 100 = 60.00.
        """
        result = f05_ltv_percent(Decimal("180000"), Decimal("300000"))
        assert r2(result) == Decimal("60.00")

    def test_cash_purchase_zero_ltv(self) -> None:
        """Cash purchase: loan=0 → LTV=0.00%."""
        result = f05_ltv_percent(Decimal("0"), Decimal("200000"))
        assert result == Decimal("0")

    def test_zero_purchase_price_returns_zero(self) -> None:
        """Guard against division by zero: purchase_price=0 → returns 0."""
        result = f05_ltv_percent(Decimal("0"), Decimal("0"))
        assert result == Decimal("0")

    def test_result_is_decimal(self) -> None:
        """Return type must be Decimal, never float."""
        result = f05_ltv_percent(Decimal("150000"), Decimal("200000"))
        assert isinstance(result, Decimal)
