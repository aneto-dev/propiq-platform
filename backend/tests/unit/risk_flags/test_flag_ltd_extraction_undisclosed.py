"""Tests for LTD_EXTRACTION_UNDISCLOSED risk flag.

Condition: ownership_structure == LIMITED_COMPANY (always fires for Ltd Co)
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


class TestLtdExtractionUndisclosed:

    def test_fires_for_limited_company(self) -> None:
        flags = evaluate_flags(_ctx(
            ownership_structure=OwnershipStructure.LIMITED_COMPANY,
            income_tax_band=None,
        ))
        assert "LTD_EXTRACTION_UNDISCLOSED" in _codes(flags)

    def test_does_not_fire_for_individual(self) -> None:
        assert "LTD_EXTRACTION_UNDISCLOSED" not in _codes(evaluate_flags(_CTX))

    def test_severity_is_info(self) -> None:
        flags = evaluate_flags(_ctx(
            ownership_structure=OwnershipStructure.LIMITED_COMPANY,
            income_tax_band=None,
        ))
        flag = next(f for f in flags if f.code == "LTD_EXTRACTION_UNDISCLOSED")
        assert flag.severity == FlagSeverity.INFO
