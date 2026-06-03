"""Tests for RENT_UNVERIFIED risk flag.

Condition: unconditional (always fires)
Severity: INFO
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


class TestRentUnverified:

    def test_always_fires(self) -> None:
        assert "RENT_UNVERIFIED" in _codes(evaluate_flags(_CTX))

    def test_fires_for_ltd_co(self) -> None:
        flags = evaluate_flags(_ctx(
            ownership_structure=OwnershipStructure.LIMITED_COMPANY,
            income_tax_band=None,
        ))
        assert "RENT_UNVERIFIED" in _codes(flags)

    def test_triggered_by_value_is_monthly_rent(self) -> None:
        flags = evaluate_flags(_CTX)
        flag = next(f for f in flags if f.code == "RENT_UNVERIFIED")
        assert flag.triggered_by_field == "monthly_rent"
        assert flag.triggered_by_value == "950.00"

    def test_severity_is_info(self) -> None:
        flags = evaluate_flags(_CTX)
        flag = next(f for f in flags if f.code == "RENT_UNVERIFIED")
        assert flag.severity == FlagSeverity.INFO
