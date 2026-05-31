"""
Tests for F-03 — Effective Annual Rent.

Formula: effective_annual_rent = gross_annual_rent × (1 - void_rate_decimal)
Source: CALCULATION_SPEC.md F-03.
"""

from decimal import Decimal, ROUND_HALF_UP

import pytest

from app.engine.calculations.formulas import f03_effective_annual_rent


TWO_DP = Decimal("0.01")


def r2(value: Decimal) -> Decimal:
    """Round to 2dp ROUND_HALF_UP — matches engine output rounding."""
    return value.quantize(TWO_DP, rounding=ROUND_HALF_UP)


class TestF03EffectiveAnnualRent:

    def test_standard_default_void(self) -> None:
        """
        Gross £12,000 with 3.85% void → effective £11,538.00.
        Manual: 12000 × (1 - 0.0385) = 12000 × 0.9615 = 11538.00.
        """
        result = f03_effective_annual_rent(Decimal("12000"), Decimal("0.0385"))
        assert r2(result) == Decimal("11538.00")

    def test_zero_void(self) -> None:
        """
        Zero void → effective rent equals gross rent.
        Manual: 12000 × (1 - 0) = 12000.
        Source: TEST_STRATEGY.md Section 3.3 F-03.
        """
        result = f03_effective_annual_rent(Decimal("12000"), Decimal("0"))
        assert result == Decimal("12000")

    def test_full_void(self) -> None:
        """
        100% void → effective rent is zero.
        Manual: 12000 × (1 - 1) = 0.
        Source: TEST_STRATEGY.md Section 3.3 F-03.
        """
        result = f03_effective_annual_rent(Decimal("12000"), Decimal("1"))
        assert result == Decimal("0")

    def test_ten_percent_void(self) -> None:
        """
        Gross £12,000 with 10% void → effective £10,800.00.
        Manual: 12000 × (1 - 0.10) = 12000 × 0.90 = 10800.00.
        Source: TEST_STRATEGY.md Section 3.3 F-03.
        """
        result = f03_effective_annual_rent(Decimal("12000"), Decimal("0.10"))
        assert r2(result) == Decimal("10800.00")

    def test_result_is_decimal(self) -> None:
        """Return type must be Decimal, never float."""
        result = f03_effective_annual_rent(Decimal("10000"), Decimal("0.05"))
        assert isinstance(result, Decimal)

    def test_void_applied_to_gross_not_net(self) -> None:
        """
        Void is applied to gross_annual_rent, not to a partially adjusted rent.
        This test verifies the formula uses the correct base.
        """
        gross = Decimal("11400")
        void = Decimal("0.0385")
        result = f03_effective_annual_rent(gross, void)
        expected = gross * (Decimal("1") - void)
        assert result == expected
