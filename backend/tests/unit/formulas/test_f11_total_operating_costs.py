"""
Tests for F-11 — Total Annual Operating Costs.

Formula:
    total = letting_agent + maintenance + insurance
          + service_charge + ground_rent + accountancy

Source: CALCULATION_SPEC.md F-11.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.engine.calculations.formulas import f11_total_operating_costs

TWO_DP = Decimal("0.01")


def r2(v: Decimal) -> Decimal:
    return v.quantize(TWO_DP, rounding=ROUND_HALF_UP)


class TestF11TotalOperatingCosts:

    def test_e01_components(self) -> None:
        """
        E-01 components (using gross-based letting fee per CALCULATION_SPEC):
          letting=1440.00, maintenance=2000.00, insurance=800.00,
          service=0, ground=0, accountancy=0 → total=4240.00.
        Manual: 1440 + 2000 + 800 + 0 + 0 + 0 = 4240.00.
        Note: F-09 applied to gross_annual_rent=12000 per CALCULATION_SPEC.
        Source: ENGINE_CONTRACTS.md E-01 + CALCULATION_SPEC.md F-09 formula.
        """
        result = f11_total_operating_costs(
            Decimal("1440.00"),
            Decimal("2000.00"),
            Decimal("800.00"),
            Decimal("0"),
            Decimal("0"),
            Decimal("0"),
        )
        assert r2(result) == Decimal("4240.00")

    def test_all_components_sum_correctly(self) -> None:
        """
        All six components contribute to the total.
        Manual: 1000 + 500 + 300 + 200 + 100 + 50 = 2150.00.
        """
        result = f11_total_operating_costs(
            Decimal("1000"),
            Decimal("500"),
            Decimal("300"),
            Decimal("200"),
            Decimal("100"),
            Decimal("50"),
        )
        assert r2(result) == Decimal("2150.00")

    def test_e06_reference_value(self) -> None:
        """
        E-06 leasehold: letting=1224, maintenance=1800, insurance=800,
        service=1200, ground=150, accountancy=0 → 5174.00.
        Manual: 1224 + 1800 + 800 + 1200 + 150 + 0 = 5174.00.
        Source: ENGINE_CONTRACTS.md E-06 intermediates.
        """
        result = f11_total_operating_costs(
            Decimal("1224.00"),
            Decimal("1800.00"),
            Decimal("800.00"),
            Decimal("1200.00"),
            Decimal("150.00"),
            Decimal("0"),
        )
        assert r2(result) == Decimal("5174.00")

    def test_all_zero(self) -> None:
        """All zero components → total is zero."""
        result = f11_total_operating_costs(
            Decimal("0"), Decimal("0"), Decimal("0"),
            Decimal("0"), Decimal("0"), Decimal("0"),
        )
        assert result == Decimal("0")

    def test_result_is_decimal(self) -> None:
        """Return type must be Decimal, never float."""
        result = f11_total_operating_costs(
            Decimal("100"), Decimal("100"), Decimal("100"),
            Decimal("0"), Decimal("0"), Decimal("0"),
        )
        assert isinstance(result, Decimal)
