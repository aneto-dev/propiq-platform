"""
Tests for F-09 — Letting Agent Annual Cost.

Formula: letting_agent_annual = gross_annual_rent
                                × (fee_pct / 100)
                                × (1 + vat_rate / 100)

Fee applied to gross_annual_rent (contractual rent due), not effective_annual_rent.
VAT rate is taken from configuration — never hardcoded.

Source: CALCULATION_SPEC.md F-09; TEST_STRATEGY.md Section 3.3 F-09.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.engine.calculations.formulas import f09_letting_agent_annual

TWO_DP = Decimal("0.01")


def r2(v: Decimal) -> Decimal:
    return v.quantize(TWO_DP, rounding=ROUND_HALF_UP)


class TestF09LettingAgentAnnual:

    def test_standard_case(self) -> None:
        """
        gross=11400, fee=10%, vat=20% → 1368.00.
        Manual: 11400 × 0.10 × 1.20 = 1,368.00.
        Source: TEST_STRATEGY.md Section 3.3 F-09.
        """
        result = f09_letting_agent_annual(
            Decimal("11400"), Decimal("10.00"), Decimal("20.00")
        )
        assert r2(result) == Decimal("1368.00")

    def test_self_managed_zero_fee(self) -> None:
        """
        Self-managed (fee=0%) → 0.00 regardless of VAT rate.
        Manual: 11400 × 0.00 × 1.20 = 0.00.
        Source: TEST_STRATEGY.md Section 3.3 F-09.
        """
        result = f09_letting_agent_annual(
            Decimal("11400"), Decimal("0.00"), Decimal("20.00")
        )
        assert r2(result) == Decimal("0.00")

    def test_higher_fee(self) -> None:
        """
        gross=11400, fee=12%, vat=20% → 1641.60.
        Manual: 11400 × 0.12 × 1.20 = 1,641.60.
        Source: TEST_STRATEGY.md Section 3.3 F-09.
        """
        result = f09_letting_agent_annual(
            Decimal("11400"), Decimal("12.00"), Decimal("20.00")
        )
        assert r2(result) == Decimal("1641.60")

    def test_vat_rate_from_config(self) -> None:
        """
        VAT rate change test: gross=11400, fee=10%, vat=25% → 1425.00.
        Manual: 11400 × 0.10 × 1.25 = 1,425.00.
        Verifies VAT rate is taken from config, not hardcoded to 20%.
        Source: TEST_STRATEGY.md Section 3.3 F-09.
        """
        result = f09_letting_agent_annual(
            Decimal("11400"), Decimal("10.00"), Decimal("25.00")
        )
        assert r2(result) == Decimal("1425.00")

    def test_applied_to_gross_not_effective(self) -> None:
        """
        Fee is applied to gross_annual_rent, not effective_annual_rent.
        CALCULATION_SPEC.md F-09: "applied to gross_annual_rent, not
        effective_annual_rent. Most letting agent management contracts
        charge on rent due."
        gross=12000 (monthly 1000 × 12), fee=10%, vat=20% → 1440.00.
        Manual: 12000 × 0.10 × 1.20 = 1,440.00.
        Note: ENGINE_CONTRACTS.md E-01 shows 1384.62, which is the
        effective-rent-based result (11538.46 × 0.12). The CALCULATION_SPEC
        formula is the authoritative source and uses gross_annual_rent.
        """
        result = f09_letting_agent_annual(
            Decimal("12000"), Decimal("10.00"), Decimal("20.00")
        )
        assert r2(result) == Decimal("1440.00")

    def test_e05_reference_value(self) -> None:
        """
        E-05: gross=28800, fee=10%, vat=20% → 3456.00.
        Manual: 28800 × 0.10 × 1.20 = 3,456.00.
        Source: ENGINE_CONTRACTS.md E-05 intermediates.
        """
        result = f09_letting_agent_annual(
            Decimal("28800"), Decimal("10.00"), Decimal("20.00")
        )
        assert r2(result) == Decimal("3456.00")

    def test_result_is_decimal(self) -> None:
        """Return type must be Decimal, never float."""
        result = f09_letting_agent_annual(
            Decimal("12000"), Decimal("10"), Decimal("20")
        )
        assert isinstance(result, Decimal)
