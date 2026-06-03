"""Tests for LOW_MARGIN_SAFETY risk flag.

Condition: annual_cash_flow >= 0 AND (cash_flow/gross_rent) < 0.05
Severity: MEDIUM
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


class TestLowMarginSafety:

    def test_fires_when_margin_below_5_pct(self) -> None:
        """cash_flow=569, gross=11400 -> 0.04991 < 0.05 fires. TEST_STRATEGY.md 6.3."""
        flags = evaluate_flags(_ctx(
            annual_cash_flow=Decimal("569"),
            gross_annual_rent=Decimal("11400",
        )))
        assert "LOW_MARGIN_SAFETY" in _codes(flags)

    def test_does_not_fire_at_exactly_5_pct(self) -> None:
        """cash_flow=570, gross=11400 -> 0.05 exactly. Condition is strictly < 0.05.
        TEST_STRATEGY.md has a mislabelled 'Fires:' on this entry;
        CALCULATION_SPEC.md (strict inequality) governs.
        """
        flags = evaluate_flags(_ctx(
            annual_cash_flow=Decimal("570"),
            gross_annual_rent=Decimal("11400",
        )))
        assert "LOW_MARGIN_SAFETY" not in _codes(flags)

    def test_does_not_fire_when_cash_flow_negative(self) -> None:
        """cash_flow < 0: NEGATIVE_CASHFLOW fires; LOW_MARGIN_SAFETY requires >= 0."""
        flags = evaluate_flags(_ctx(
            annual_cash_flow=Decimal("-100"),
            gross_annual_rent=Decimal("11400",
        )))
        assert "LOW_MARGIN_SAFETY" not in _codes(flags)

    def test_does_not_fire_when_margin_adequate(self) -> None:
        assert "LOW_MARGIN_SAFETY" not in _codes(evaluate_flags(_CTX))

    def test_triggered_by_field(self) -> None:
        flags = evaluate_flags(_ctx(
            annual_cash_flow=Decimal("500"),
            gross_annual_rent=Decimal("11400",
        )))
        flag = next(f for f in flags if f.code == "LOW_MARGIN_SAFETY")
        assert flag.triggered_by_field == "annual_cash_flow_gbp"
