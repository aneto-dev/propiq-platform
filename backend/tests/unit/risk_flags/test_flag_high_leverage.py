"""Tests for HIGH_LEVERAGE risk flag.

Condition: ltv_percent > 75  Severity: HIGH
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


class TestHighLeverage:

    def test_fires_at_75_01(self) -> None:
        flags = evaluate_flags(_ctx(ltv_percent=Decimal("75.01")))
        assert "HIGH_LEVERAGE" in _codes(flags)

    def test_does_not_fire_at_75_00(self) -> None:
        """Boundary: ltv=75.00 must NOT fire (base context)."""
        assert "HIGH_LEVERAGE" not in _codes(evaluate_flags(_CTX))

    def test_does_not_fire_below_threshold(self) -> None:
        flags = evaluate_flags(_ctx(ltv_percent=Decimal("60.00")))
        assert "HIGH_LEVERAGE" not in _codes(flags)

    def test_triggered_by_field(self) -> None:
        flags = evaluate_flags(_ctx(ltv_percent=Decimal("82.50")))
        flag = next(f for f in flags if f.code == "HIGH_LEVERAGE")
        assert flag.triggered_by_field == "ltv_percent"
        assert flag.triggered_by_value == "82.50"
