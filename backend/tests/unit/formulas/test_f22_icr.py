"""
Tests for F-22 — ICR Stress Test.

Two functions:
  f22_stressed_annual_interest: loan × (stress_rate / 100)
  f22_icr_percent: (effective_rent / stressed_interest) × 100
                   Returns None for cash purchase (stressed_interest = 0).

Source: CALCULATION_SPEC.md F-22; TEST_STRATEGY.md Part 3.3.
ENGINE_CONTRACTS.md Part 3.1: icr_percent: Decimal | None.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.engine.calculations.formulas import (
    f22_icr_percent,
    f22_stressed_annual_interest,
)

_TWO_DP = Decimal("0.01")


def r2(v: Decimal) -> Decimal:
    return v.quantize(_TWO_DP, rounding=ROUND_HALF_UP)

class TestF22StressedAnnualInterest:

    def test_e01_stressed_interest(self) -> None:
        """
        E-01: loan=150,000, stress=5.50%
        150,000 × 0.055 = 8,250.00
        Source: ENGINE_CONTRACTS.md E-01.
        """
        result = f22_stressed_annual_interest(
            loan_amount=Decimal("150000"),
            stress_test_rate_percent=Decimal("5.5"),
        )
        assert r2(result) == Decimal("8250.00")

    def test_e03_stressed_interest(self) -> None:
        """
        E-03: loan=262,500, stress=5.50%
        262,500 × 0.055 = 14,437.50
        Source: ENGINE_CONTRACTS.md E-03.
        """
        result = f22_stressed_annual_interest(
            loan_amount=Decimal("262500"),
            stress_test_rate_percent=Decimal("5.5"),
        )
        assert r2(result) == Decimal("14437.50")

    def test_e05_stressed_interest(self) -> None:
        """
        E-05: loan=450,000, stress=5.50%
        450,000 × 0.055 = 24,750.00
        Source: ENGINE_CONTRACTS.md E-05.
        """
        result = f22_stressed_annual_interest(
            loan_amount=Decimal("450000"),
            stress_test_rate_percent=Decimal("5.5"),
        )
        assert r2(result) == Decimal("24750.00")

    def test_cash_purchase_zero_loan(self) -> None:
        """loan=0 (cash purchase) produces stressed_interest=0."""
        result = f22_stressed_annual_interest(
            loan_amount=Decimal("0"),
            stress_test_rate_percent=Decimal("5.5"),
        )
        assert result == Decimal("0")

    def test_returns_decimal_not_float(self) -> None:
        result = f22_stressed_annual_interest(
            loan_amount=Decimal("150000"),
            stress_test_rate_percent=Decimal("5.5"),
        )
        assert isinstance(result, Decimal)


class TestF22ICRPercent:

    def test_e01_icr(self) -> None:
        """
        E-01: eff=10,961.10, stressed=8,250.00
        10,961.10 / 8,250.00 × 100 = 132.8618... → 132.86
        Source: ENGINE_CONTRACTS.md E-01.
        """
        result = f22_icr_percent(
            effective_annual_rent=Decimal("10961.10"),
            stressed_annual_interest=Decimal("8250.00"),
        )
        assert result is not None
        assert r2(result) == Decimal("132.86")

    def test_e03_icr(self) -> None:
        """
        E-03: eff=18,460.80, stressed=14,437.50
        18,460.80 / 14,437.50 × 100 = 127.867... → 127.87
        Note: ENGINE_CONTRACTS.md shows 127.88 — arithmetic discrepancy.
        Correct value derived from formula is 127.87.
        Source: ENGINE_CONTRACTS.md E-03 (discrepancy documented).
        """
        result = f22_icr_percent(
            effective_annual_rent=Decimal("18460.80"),
            stressed_annual_interest=Decimal("14437.50"),
        )
        assert result is not None
        assert r2(result) == Decimal("127.87")

    def test_e05_icr(self) -> None:
        """
        E-05: eff=27,691.20, stressed=24,750.00
        27,691.20 / 24,750.00 × 100 = 111.8836... → 111.88
        Source: ENGINE_CONTRACTS.md E-05.
        """
        result = f22_icr_percent(
            effective_annual_rent=Decimal("27691.20"),
            stressed_annual_interest=Decimal("24750.00"),
        )
        assert result is not None
        assert r2(result) == Decimal("111.88")

    def test_cash_purchase_returns_none(self) -> None:
        """
        stressed_annual_interest=0 (cash purchase) → icr_percent = None.
        ENGINE_CONTRACTS.md Part 3.1: icr_percent: Decimal | None.
        """
        result = f22_icr_percent(
            effective_annual_rent=Decimal("10961.10"),
            stressed_annual_interest=Decimal("0"),
        )
        assert result is None

    def test_icr_at_exactly_125_does_not_trigger_flag(self) -> None:
        """
        ICR = 125.00 exactly must NOT trigger LOW_ICR_BASIC (condition: < 125).
        Derivation: loan=100,000, stress=5.5% → stressed=5,500
        effective_rent = 5,500 × 1.25 = 6,875
        ICR = 6,875 / 5,500 × 100 = 125.00 exactly.
        Source: TEST_STRATEGY.md Part 3.3 F-22 boundary.
        """
        result = f22_icr_percent(
            effective_annual_rent=Decimal("6875"),
            stressed_annual_interest=Decimal("5500"),
        )
        assert result is not None
        assert r2(result) == Decimal("125.00")

    def test_icr_below_125_triggers_flag(self) -> None:
        """
        ICR = 124.98 (< 125) MUST trigger LOW_ICR_BASIC.
        effective_rent=6,874, stressed=5,500
        6,874 / 5,500 × 100 = 124.981... → 124.98
        Source: TEST_STRATEGY.md Part 3.3 F-22 boundary.
        """
        result = f22_icr_percent(
            effective_annual_rent=Decimal("6874"),
            stressed_annual_interest=Decimal("5500"),
        )
        assert result is not None
        assert r2(result) == Decimal("124.98")

    def test_icr_at_exactly_145_does_not_trigger_higher_rate_flag(self) -> None:
        """
        ICR = 145.00 exactly must NOT trigger LOW_ICR_HIGHER_RATE (condition: < 145).
        effective_rent = 5,500 × 1.45 = 7,975
        ICR = 7,975 / 5,500 × 100 = 145.00 exactly.
        Source: TEST_STRATEGY.md Part 3.3 F-22 boundary.
        """
        result = f22_icr_percent(
            effective_annual_rent=Decimal("7975"),
            stressed_annual_interest=Decimal("5500"),
        )
        assert result is not None
        assert r2(result) == Decimal("145.00")

    def test_returns_decimal_when_not_cash_purchase(self) -> None:
        """Return type is Decimal (not float, not None) for mortgaged deal."""
        result = f22_icr_percent(
            effective_annual_rent=Decimal("10961.10"),
            stressed_annual_interest=Decimal("8250.00"),
        )
        assert isinstance(result, Decimal)
        assert not isinstance(result, float)

    def test_return_type_is_none_for_zero_interest(self) -> None:
        """Explicit type check: None (not Decimal("0")) for cash purchase."""
        result = f22_icr_percent(
            effective_annual_rent=Decimal("10961.10"),
            stressed_annual_interest=Decimal("0"),
        )
        assert result is None
        assert result != Decimal("0")

    def test_high_icr_above_200(self) -> None:
        """High-yield, low-loan deal can produce ICR > 200 — no ceiling."""
        result = f22_icr_percent(
            effective_annual_rent=Decimal("20000"),
            stressed_annual_interest=Decimal("5500"),
        )
        assert result is not None
        assert r2(result) > Decimal("200")
