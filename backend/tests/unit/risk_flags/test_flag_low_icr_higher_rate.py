"""Tests for LOW_ICR_HIGHER_RATE risk flag.

Condition: 125 <= icr_percent < 145 AND income_tax_band in HIGHER/ADDITIONAL
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


class TestLowICRHigherRate:

    def test_fires_for_higher_rate_at_144_99(self) -> None:
        flags = evaluate_flags(_ctx(
            icr_percent=Decimal("144.99"),
            income_tax_band=IncomeTaxBand.HIGHER_RATE,
        ))
        assert "LOW_ICR_HIGHER_RATE" in _codes(flags)

    def test_fires_for_additional_rate(self) -> None:
        flags = evaluate_flags(_ctx(
            icr_percent=Decimal("132.86"),
            income_tax_band=IncomeTaxBand.ADDITIONAL_RATE,
        ))
        assert "LOW_ICR_HIGHER_RATE" in _codes(flags)

    def test_does_not_fire_at_145_upper_boundary(self) -> None:
        """Boundary: icr=145.00, HIGHER_RATE does NOT fire."""
        flags = evaluate_flags(_ctx(
            icr_percent=Decimal("145.00"),
            income_tax_band=IncomeTaxBand.HIGHER_RATE,
        ))
        assert "LOW_ICR_HIGHER_RATE" not in _codes(flags)

    def test_does_not_fire_below_125_lower_boundary(self) -> None:
        """icr=124.99 HIGHER_RATE: LOW_ICR_BASIC fires, LOW_ICR_HIGHER_RATE does NOT."""
        flags = evaluate_flags(_ctx(
            icr_percent=Decimal("124.99"),
            income_tax_band=IncomeTaxBand.HIGHER_RATE,
        ))
        assert "LOW_ICR_HIGHER_RATE" not in _codes(flags)
        assert "LOW_ICR_BASIC" in _codes(flags)

    def test_does_not_fire_for_basic_rate(self) -> None:
        flags = evaluate_flags(_ctx(
            icr_percent=Decimal("132.00"),
            income_tax_band=IncomeTaxBand.BASIC_RATE,
        ))
        assert "LOW_ICR_HIGHER_RATE" not in _codes(flags)

    def test_does_not_fire_for_ltd_co(self) -> None:
        flags = evaluate_flags(_ctx(
            icr_percent=Decimal("132.00"),
            ownership_structure=OwnershipStructure.LIMITED_COMPANY,
            income_tax_band=None,
        ))
        assert "LOW_ICR_HIGHER_RATE" not in _codes(flags)

    def test_does_not_fire_for_cash_purchase(self) -> None:
        flags = evaluate_flags(_ctx(
            icr_percent=None,
            income_tax_band=IncomeTaxBand.HIGHER_RATE,
        ))
        assert "LOW_ICR_HIGHER_RATE" not in _codes(flags)
