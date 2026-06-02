"""
Tests for F-14 — Total Acquisition Cost.

Formula: total_acquisition_cost = purchase_price + total_sdlt
                                   + purchase_legal_costs + refurbishment_cost

Source: CALCULATION_SPEC.md F-14.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.engine.calculations.formulas import f14_total_acquisition_cost

TWO_DP = Decimal("0.01")


def r2(v: Decimal) -> Decimal:
    return v.quantize(TWO_DP, rounding=ROUND_HALF_UP)


class TestF14TotalAcquisitionCost:

    def test_e01_reference_value(self) -> None:
        """
        E-01: purchase=200000, sdlt=7500, legal=2500, refurb=0 → 210000.
        Manual: 200000 + 7500 + 2500 + 0 = 210,000.00.
        Source: ENGINE_CONTRACTS.md E-01.
        """
        result = f14_total_acquisition_cost(
            Decimal("200000"),
            Decimal("7500"),
            Decimal("2500"),
            Decimal("0"),
        )
        assert r2(result) == Decimal("210000.00")

    def test_e03_reference_value(self) -> None:
        """
        E-03: purchase=350000, sdlt=18000, legal=2500, refurb=0 → 370500.
        Manual: 350000 + 18000 + 2500 + 0 = 370,500.00.
        Source: ENGINE_CONTRACTS.md E-03.
        """
        result = f14_total_acquisition_cost(
            Decimal("350000"),
            Decimal("18000"),
            Decimal("2500"),
            Decimal("0"),
        )
        assert r2(result) == Decimal("370500.00")

    def test_with_refurbishment(self) -> None:
        """
        Including refurbishment cost:
        purchase=200000, sdlt=7500, legal=2500, refurb=15000 → 225000.
        Manual: 200000 + 7500 + 2500 + 15000 = 225,000.00.
        """
        result = f14_total_acquisition_cost(
            Decimal("200000"),
            Decimal("7500"),
            Decimal("2500"),
            Decimal("15000"),
        )
        assert r2(result) == Decimal("225000.00")

    def test_zero_sdlt_cash_purchase(self) -> None:
        """
        Zero SDLT (e.g. below threshold, no surcharge):
        purchase=100000, sdlt=0, legal=1500, refurb=0 → 101500.
        """
        result = f14_total_acquisition_cost(
            Decimal("100000"),
            Decimal("0"),
            Decimal("1500"),
            Decimal("0"),
        )
        assert r2(result) == Decimal("101500.00")

    def test_result_is_decimal(self) -> None:
        """Return type must be Decimal, never float."""
        result = f14_total_acquisition_cost(
            Decimal("200000"), Decimal("7500"), Decimal("2500"), Decimal("0")
        )
        assert isinstance(result, Decimal)
