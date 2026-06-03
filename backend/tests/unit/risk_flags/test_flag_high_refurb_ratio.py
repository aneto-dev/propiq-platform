"""Tests for HIGH_REFURB_RATIO risk flag.

Condition: refurbishment_cost > purchase_price x 0.10  Severity: MEDIUM
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


class TestHighRefurbRatio:

    def test_fires_when_above_10_pct(self) -> None:
        """refurb=20001, price=200000 fires. TEST_STRATEGY.md 6.3."""
        flags = evaluate_flags(_ctx(
            refurbishment_cost=Decimal("20001"),
            purchase_price=Decimal("200000",
        )))
        assert "HIGH_REFURB_RATIO" in _codes(flags)

    def test_does_not_fire_at_exactly_10_pct(self) -> None:
        """refurb=20000, price=200000 is exactly 10% - does NOT fire."""
        flags = evaluate_flags(_ctx(
            refurbishment_cost=Decimal("20000"),
            purchase_price=Decimal("200000",
        )))
        assert "HIGH_REFURB_RATIO" not in _codes(flags)

    def test_does_not_fire_below_10_pct(self) -> None:
        assert "HIGH_REFURB_RATIO" not in _codes(evaluate_flags(_CTX))

    def test_triggered_by_field(self) -> None:
        flags = evaluate_flags(_ctx(
            refurbishment_cost=Decimal("25000"),
            purchase_price=Decimal("200000",
        )))
        flag = next(f for f in flags if f.code == "HIGH_REFURB_RATIO")
        assert flag.triggered_by_field == "refurbishment_cost"
        assert flag.triggered_by_value == "25000.00"
