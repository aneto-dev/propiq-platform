"""
Tests for F-02 — Void Rate Conversion.

Formula: void_rate_decimal = void_rate_percent / 100
Source: CALCULATION_SPEC.md F-02.
"""

from decimal import Decimal

from app.engine.calculations.formulas import f02_void_rate_decimal


class TestF02VoidRateConversion:

    def test_default_void_rate(self) -> None:
        """
        Default void rate 3.85% → decimal 0.0385.
        Manual: 3.85 / 100 = 0.0385.
        """
        result = f02_void_rate_decimal(Decimal("3.85"))
        assert result == Decimal("0.0385")

    def test_zero_void_rate(self) -> None:
        """0% void → 0.00 decimal."""
        result = f02_void_rate_decimal(Decimal("0"))
        assert result == Decimal("0")

    def test_full_void_rate(self) -> None:
        """100% void (fully vacant year) → decimal 1.00."""
        result = f02_void_rate_decimal(Decimal("100"))
        assert result == Decimal("1")

    def test_ten_percent_void(self) -> None:
        """
        10% void → decimal 0.10.
        Manual: 10 / 100 = 0.10.
        """
        result = f02_void_rate_decimal(Decimal("10"))
        assert result == Decimal("0.10")

    def test_result_is_decimal(self) -> None:
        """Return type must be Decimal, never float."""
        result = f02_void_rate_decimal(Decimal("5"))
        assert isinstance(result, Decimal)

    def test_two_fifty_two_weeks_void(self) -> None:
        """
        2 weeks void from 52-week year = 3.84615...%.
        This is the basis of the 3.85% default assumption.
        2/52 × 100 = 3.84615384...%
        """
        two_weeks = (Decimal("2") / Decimal("52")) * Decimal("100")
        result = f02_void_rate_decimal(two_weeks)
        assert Decimal("0.038") < result < Decimal("0.040")
