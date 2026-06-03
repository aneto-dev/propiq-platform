"""Tests for NEGATIVE_CASHFLOW risk flag.

Condition: annual_cash_flow < 0  Severity: HIGH
"""
import dataclasses
from decimal import Decimal

from app.domain.enums import IncomeTaxBand, OwnershipStructure, Tenure
from app.engine.contracts import FlagSeverity
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


class TestNegativeCashflow:

    def test_fires_when_negative(self) -> None:
        """annual_cash_flow=-0.01 fires. Source: TEST_STRATEGY.md 6.3."""
        flags = evaluate_flags(_ctx(annual_cash_flow=Decimal("-0.01")))
        assert "NEGATIVE_CASHFLOW" in _codes(flags)

    def test_severity_is_high(self) -> None:
        flags = evaluate_flags(_ctx(annual_cash_flow=Decimal("-1")))
        flag = next(f for f in flags if f.code == "NEGATIVE_CASHFLOW")
        assert flag.severity == FlagSeverity.HIGH

    def test_does_not_fire_at_zero(self) -> None:
        """annual_cash_flow=0.00 does NOT fire. Source: TEST_STRATEGY.md 6.3."""
        flags = evaluate_flags(_ctx(annual_cash_flow=Decimal("0")))
        assert "NEGATIVE_CASHFLOW" not in _codes(flags)

    def test_does_not_fire_when_positive(self) -> None:
        assert "NEGATIVE_CASHFLOW" not in _codes(evaluate_flags(_CTX))

    def test_triggered_by_value(self) -> None:
        flags = evaluate_flags(_ctx(annual_cash_flow=Decimal("-331.90")))
        flag = next(f for f in flags if f.code == "NEGATIVE_CASHFLOW")
        assert flag.triggered_by_value == "-331.90"
        assert flag.triggered_by_field == "annual_cash_flow_gbp"
