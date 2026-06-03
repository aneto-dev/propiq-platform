"""Tests for HIGH_LEVERAGE_EXTREME risk flag.

Condition: ltv_percent > 85  Severity: HIGH
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


class TestHighLeverageExtreme:

    def test_fires_at_85_01(self) -> None:
        flags = evaluate_flags(_ctx(ltv_percent=Decimal("85.01")))
        assert "HIGH_LEVERAGE_EXTREME" in _codes(flags)

    def test_does_not_fire_at_85_00(self) -> None:
        flags = evaluate_flags(_ctx(ltv_percent=Decimal("85.00")))
        assert "HIGH_LEVERAGE_EXTREME" not in _codes(flags)

    def test_does_not_fire_below_85(self) -> None:
        flags = evaluate_flags(_ctx(ltv_percent=Decimal("75.01")))
        assert "HIGH_LEVERAGE_EXTREME" not in _codes(flags)

    def test_both_high_leverage_flags_fire_above_85(self) -> None:
        """Both HIGH_LEVERAGE (>75) and HIGH_LEVERAGE_EXTREME (>85) fire.
        TEST_STRATEGY.md 6.3."""
        flags = evaluate_flags(_ctx(ltv_percent=Decimal("85.01")))
        assert "HIGH_LEVERAGE" in _codes(flags)
        assert "HIGH_LEVERAGE_EXTREME" in _codes(flags)

    def test_triggered_by_field(self) -> None:
        flags = evaluate_flags(_ctx(ltv_percent=Decimal("90.00")))
        flag = next(f for f in flags if f.code == "HIGH_LEVERAGE_EXTREME")
        assert flag.triggered_by_field == "ltv_percent"
