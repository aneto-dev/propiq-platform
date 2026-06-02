"""
Tests for F-10 — Annual Maintenance Reserve.

Formula: annual_maintenance_reserve = purchase_price × (maintenance_pct / 100)

Source: CALCULATION_SPEC.md F-10; TEST_STRATEGY.md Section 3.3.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.engine.calculations.formulas import f10_annual_maintenance_reserve

TWO_DP = Decimal("0.01")


def r2(v: Decimal) -> Decimal:
    return v.quantize(TWO_DP, rounding=ROUND_HALF_UP)


class TestF10AnnualMaintenanceReserve:

    def test_e01_reference_value(self) -> None:
        """
        E-01: purchase=200000, reserve=1% → 2000.00.
        Manual: 200000 × 0.01 = 2,000.00.
        Source: ENGINE_CONTRACTS.md E-01.
        """
        result = f10_annual_maintenance_reserve(
            Decimal("200000"), Decimal("1.0")
        )
        assert r2(result) == Decimal("2000.00")

    def test_zero_reserve_rate(self) -> None:
        """
        Zero reserve rate → 0.00.
        Manual: 200000 × 0.00 = 0.00.
        """
        result = f10_annual_maintenance_reserve(
            Decimal("200000"), Decimal("0")
        )
        assert r2(result) == Decimal("0.00")

    def test_e05_reference_value(self) -> None:
        """
        E-05: purchase=600000, reserve=1% → 6000.00.
        Manual: 600000 × 0.01 = 6,000.00.
        Source: ENGINE_CONTRACTS.md E-05.
        """
        result = f10_annual_maintenance_reserve(
            Decimal("600000"), Decimal("1.0")
        )
        assert r2(result) == Decimal("6000.00")

    def test_higher_reserve_rate(self) -> None:
        """
        purchase=200000, reserve=2% → 4000.00.
        Manual: 200000 × 0.02 = 4,000.00.
        """
        result = f10_annual_maintenance_reserve(
            Decimal("200000"), Decimal("2.0")
        )
        assert r2(result) == Decimal("4000.00")

    def test_result_is_decimal(self) -> None:
        """Return type must be Decimal, never float."""
        result = f10_annual_maintenance_reserve(Decimal("200000"), Decimal("1"))
        assert isinstance(result, Decimal)
