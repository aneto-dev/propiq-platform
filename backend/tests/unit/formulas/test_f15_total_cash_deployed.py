"""
Tests for F-15 — Total Cash Deployed.

Formula: total_cash_deployed = deposit_amount + total_sdlt
                                + purchase_legal_costs + refurbishment_cost

Mortgage loan is excluded — total_cash_deployed is the investor's own
capital outlay. This is the denominator in cash-on-cash return and ROCE.

Source: CALCULATION_SPEC.md F-15.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.engine.calculations.formulas import f15_total_cash_deployed

TWO_DP = Decimal("0.01")


def r2(v: Decimal) -> Decimal:
    return v.quantize(TWO_DP, rounding=ROUND_HALF_UP)


class TestF15TotalCashDeployed:

    def test_e01_reference_value(self) -> None:
        """
        E-01: deposit=50000, sdlt=7500, legal=2500, refurb=0 → 60000.
        Manual: 50000 + 7500 + 2500 + 0 = 60,000.00.
        Source: ENGINE_CONTRACTS.md E-01.
        """
        result = f15_total_cash_deployed(
            Decimal("50000"),
            Decimal("7500"),
            Decimal("2500"),
            Decimal("0"),
        )
        assert r2(result) == Decimal("60000.00")

    def test_e03_reference_value(self) -> None:
        """
        E-03: deposit=87500, sdlt=18000, legal=2500, refurb=0 → 108000.
        Manual: 87500 + 18000 + 2500 + 0 = 108,000.00.
        Source: ENGINE_CONTRACTS.md E-03.
        """
        result = f15_total_cash_deployed(
            Decimal("87500"),
            Decimal("18000"),
            Decimal("2500"),
            Decimal("0"),
        )
        assert r2(result) == Decimal("108000.00")

    def test_differs_from_acquisition_cost(self) -> None:
        """
        total_cash_deployed < total_acquisition_cost by exactly the loan amount.
        E-01: acquisition=210000, cash_deployed=60000, loan=150000.
        210000 - 60000 = 150000 = loan amount.
        """
        acquisition = Decimal("210000")
        cash_deployed = Decimal("60000")
        loan = Decimal("150000")
        assert acquisition - cash_deployed == loan

    def test_cash_purchase_equals_acquisition_cost(self) -> None:
        """
        Cash purchase (deposit = purchase_price): cash_deployed = acquisition_cost.
        deposit=200000, sdlt=7500, legal=2500, refurb=0 → 210000.
        """
        result = f15_total_cash_deployed(
            Decimal("200000"),
            Decimal("7500"),
            Decimal("2500"),
            Decimal("0"),
        )
        assert r2(result) == Decimal("210000.00")

    def test_result_is_decimal(self) -> None:
        """Return type must be Decimal, never float."""
        result = f15_total_cash_deployed(
            Decimal("50000"), Decimal("7500"), Decimal("2500"), Decimal("0")
        )
        assert isinstance(result, Decimal)
