"""
Tests for F-12 — Net Operating Income (NOI).

Formula: net_operating_income = effective_annual_rent - total_operating_costs

NOI is financing-neutral and tax-neutral. May be negative.

Source: CALCULATION_SPEC.md F-12.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.engine.calculations.formulas import f12_net_operating_income

TWO_DP = Decimal("0.01")


def r2(v: Decimal) -> Decimal:
    return v.quantize(TWO_DP, rounding=ROUND_HALF_UP)


class TestF12NetOperatingIncome:

    def test_e01_reference_value(self) -> None:
        """
        E-01: effective=11538.46, total_ops=4240.00 → NOI=7298.46.
        Manual: 11538.46 - 4240.00 = 7298.46.
        Note: uses CALCULATION_SPEC-correct operating costs (gross-based F-09).
        Source: ENGINE_CONTRACTS.md E-01 + CALCULATION_SPEC.md.
        """
        result = f12_net_operating_income(
            Decimal("11538.46"), Decimal("4240.00")
        )
        assert r2(result) == Decimal("7298.46")

    def test_positive_noi(self) -> None:
        """Rent exceeds costs → positive NOI."""
        result = f12_net_operating_income(
            Decimal("10000"), Decimal("4000")
        )
        assert r2(result) == Decimal("6000.00")

    def test_negative_noi(self) -> None:
        """
        Costs exceed effective rent → negative NOI.
        Negative NOI is architecturally valid per DOMAIN_MODEL_ARCHITECTURE.md
        Part 8.3. It represents a property losing money before financing.
        Manual: 3000 - 5000 = -2000.00.
        """
        result = f12_net_operating_income(
            Decimal("3000"), Decimal("5000")
        )
        assert r2(result) == Decimal("-2000.00")

    def test_zero_costs(self) -> None:
        """Zero costs → NOI equals effective rent."""
        result = f12_net_operating_income(
            Decimal("12000"), Decimal("0")
        )
        assert result == Decimal("12000")

    def test_result_is_decimal(self) -> None:
        """Return type must be Decimal, never float."""
        result = f12_net_operating_income(Decimal("10000"), Decimal("4000"))
        assert isinstance(result, Decimal)
