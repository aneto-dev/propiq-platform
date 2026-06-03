"""Tests for LOW_ICR_BASIC risk flag.

Condition: icr_percent is not None AND icr_percent < 125  Severity: HIGH
"""
import dataclasses
from decimal import Decimal

from app.domain.enums import IncomeTaxBand, OwnershipStructure, Tenure
from app.engine.risk_flags.definitions import EvaluationContext, evaluate_flags

_CTX = EvaluationContext(
    annual_cash_flow=Decimal("874.48"),
    gross_annual_rent=Decimal("11400"),
    net_operating_income=Decimal("6793.10"),
    gross_yield_percent=Decimal("5.70"),
    net_yield_percent=Decimal("3.40"),
    ltv_percent=Decimal("75.00"),
    icr_percent=Decimal("132.86"),
    pre_tax_annual_cash_flow=Decimal("1093.10"),
    ownership_structure=OwnershipStructure.INDIVIDUAL,
    income_tax_band=IncomeTaxBand.BASIC_RATE,
    tenure=Tenure.FREEHOLD,
    lease_years_remaining=None,
    purchase_price=Decimal("200000"),
    refurbishment_cost=Decimal("100"),
    monthly_rent=Decimal("950"),
)


def _ctx(**overrides):
    return dataclasses.replace(_CTX, **overrides)


def _codes(flags):
    return {f.code for f in flags}


class TestLowICRBasic:

    def test_fires_at_124_99(self) -> None:
        """icr_percent=124.99 fires. Source: TEST_STRATEGY.md 6.3."""
        flags = evaluate_flags(_ctx(icr_percent=Decimal("124.99")))
        assert "LOW_ICR_BASIC" in _codes(flags)

    def test_does_not_fire_at_125_00(self) -> None:
        """Boundary: 125.00 must NOT fire. Source: TEST_STRATEGY.md 6.3."""
        flags = evaluate_flags(_ctx(icr_percent=Decimal("125.00")))
        assert "LOW_ICR_BASIC" not in _codes(flags)

    def test_does_not_fire_above_threshold(self) -> None:
        assert "LOW_ICR_BASIC" not in _codes(evaluate_flags(_CTX))

    def test_does_not_fire_for_cash_purchase(self) -> None:
        """Cash purchase: icr_percent=None must NOT fire. ENGINE_CONTRACTS.md Part 6."""
        assert "LOW_ICR_BASIC" not in _codes(evaluate_flags(_ctx(icr_percent=None)))

    def test_triggered_by_field(self) -> None:
        flags = evaluate_flags(_ctx(icr_percent=Decimal("111.88")))
        flag = next(f for f in flags if f.code == "LOW_ICR_BASIC")
        assert flag.triggered_by_field == "icr_percent"
        assert flag.triggered_by_value == "111.88"
