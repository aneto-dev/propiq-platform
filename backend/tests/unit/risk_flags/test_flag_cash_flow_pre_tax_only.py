"""Tests for CASH_FLOW_PRE_TAX_ONLY risk flag.

Condition: pre_tax_annual_cash_flow >= 0 AND annual_cash_flow < 0
Severity: HIGH
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


class TestCashFlowPreTaxOnly:

    def test_fires_when_pre_tax_positive_post_tax_negative(self) -> None:
        flags = evaluate_flags(_ctx(pre_tax_annual_cash_flow=Decimal("100"),
            annual_cash_flow=Decimal("-200")))
        assert "CASH_FLOW_PRE_TAX_ONLY" in _codes(flags)

    def test_does_not_fire_when_both_negative(self) -> None:
        flags = evaluate_flags(_ctx(pre_tax_annual_cash_flow=Decimal("-100"),
            annual_cash_flow=Decimal("-200")))
        assert "CASH_FLOW_PRE_TAX_ONLY" not in _codes(flags)

    def test_does_not_fire_when_both_positive(self) -> None:
        flags = evaluate_flags(_ctx(pre_tax_annual_cash_flow=Decimal("100"),
            annual_cash_flow=Decimal("50")))
        assert "CASH_FLOW_PRE_TAX_ONLY" not in _codes(flags)

    def test_triggered_by_field(self) -> None:
        flags = evaluate_flags(_ctx(pre_tax_annual_cash_flow=Decimal("1000"),
            annual_cash_flow=Decimal("-200")))
        flag = next(f for f in flags if f.code == "CASH_FLOW_PRE_TAX_ONLY")
        assert flag.triggered_by_field == "annual_cash_flow_gbp"
