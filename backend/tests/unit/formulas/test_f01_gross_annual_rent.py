"""
Tests for F-01 — Gross Annual Rent.

Formula: gross_annual_rent = monthly_rent × 12
Source: CALCULATION_SPEC.md F-01.
"""

from decimal import Decimal

from app.engine.calculations.formulas import f01_gross_annual_rent


class TestF01GrossAnnualRent:

    def test_standard_monthly_rent(self) -> None:
        """
        Monthly rent £1,000 → gross annual rent £12,000.
        Manual: 1000 × 12 = 12000.
        """
        result = f01_gross_annual_rent(Decimal("1000"))
        assert result == Decimal("12000")

    def test_e01_reference_value(self) -> None:
        """
        E-01 scenario: monthly_rent=1000 → gross_annual_rent=12000.
        Source: ENGINE_CONTRACTS.md E-01.
        """
        result = f01_gross_annual_rent(Decimal("1000"))
        assert result == Decimal("12000")

    def test_fractional_monthly_rent(self) -> None:
        """
        Monthly rent £933.33 → gross annual £11,199.96.
        Manual: 933.33 × 12 = 11199.96.
        Source: TEST_STRATEGY.md Section 3.3 F-01.
        """
        result = f01_gross_annual_rent(Decimal("933.33"))
        assert result == Decimal("11199.96")

    def test_minimum_positive_rent(self) -> None:
        """
        Monthly rent £0.01 → gross annual £0.12.
        Manual: 0.01 × 12 = 0.12.
        Source: TEST_STRATEGY.md Section 3.3 F-01.
        """
        result = f01_gross_annual_rent(Decimal("0.01"))
        assert result == Decimal("0.12")

    def test_result_is_decimal(self) -> None:
        """Return type must be Decimal, never float."""
        result = f01_gross_annual_rent(Decimal("1200"))
        assert isinstance(result, Decimal)

    def test_high_value_property(self) -> None:
        """London premium: monthly rent £5,000 → gross annual £60,000."""
        result = f01_gross_annual_rent(Decimal("5000"))
        assert result == Decimal("60000")
