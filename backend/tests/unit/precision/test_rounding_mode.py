"""
PREC-05 — ROUND_HALF_UP rounding mode.

Values at x.005 must round up, not to even (banker's rounding).

Source: TEST_STRATEGY.md Part 9.4; ENGINE_CONTRACTS.md Part 7.3.
"""

from decimal import ROUND_HALF_UP, Decimal


class TestRoundingMode:

    def test_half_up_1_005_rounds_to_1_01(self) -> None:
        """
        PREC-05: 1.005 rounds to 1.01 under ROUND_HALF_UP.
        Source: TEST_STRATEGY.md PREC-05.
        """
        value = Decimal("1.005")
        result = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        assert result == Decimal("1.01")

    def test_half_up_2_125_rounds_to_2_13(self) -> None:
        """2.125 rounds to 2.13 under ROUND_HALF_UP."""
        value = Decimal("2.125")
        result = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        assert result == Decimal("2.13")

    def test_half_up_1_004_rounds_to_1_00(self) -> None:
        """1.004 rounds down to 1.00 (not at the half boundary)."""
        value = Decimal("1.004")
        result = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        assert result == Decimal("1.00")
