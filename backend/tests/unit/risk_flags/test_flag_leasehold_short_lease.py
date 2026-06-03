"""Tests for LEASEHOLD_SHORT_LEASE risk flag.

Condition: LEASEHOLD AND lease_years_remaining is not None AND < 80
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


class TestLeaseholdShortLease:

    def test_fires_at_79_years(self) -> None:
        flags = evaluate_flags(_ctx(tenure=Tenure.LEASEHOLD, lease_years_remaining=79))
        assert "LEASEHOLD_SHORT_LEASE" in _codes(flags)

    def test_does_not_fire_at_80_years(self) -> None:
        flags = evaluate_flags(_ctx(tenure=Tenure.LEASEHOLD, lease_years_remaining=80))
        assert "LEASEHOLD_SHORT_LEASE" not in _codes(flags)

    def test_does_not_fire_for_freehold(self) -> None:
        flags = evaluate_flags(_ctx(tenure=Tenure.FREEHOLD, lease_years_remaining=79))
        assert "LEASEHOLD_SHORT_LEASE" not in _codes(flags)

    def test_does_not_fire_for_null_lease_years(self) -> None:
        """LEASEHOLD + lease_years=None must NOT fire. TEST_STRATEGY.md 6.3."""
        flags = evaluate_flags(_ctx(
            tenure=Tenure.LEASEHOLD,
            lease_years_remaining=None,
        ))
        assert "LEASEHOLD_SHORT_LEASE" not in _codes(flags)

    def test_triggered_by_value_is_years_as_string(self) -> None:
        flags = evaluate_flags(_ctx(tenure=Tenure.LEASEHOLD, lease_years_remaining=72))
        flag = next(f for f in flags if f.code == "LEASEHOLD_SHORT_LEASE")
        assert flag.triggered_by_field == "lease_years_remaining"
        assert flag.triggered_by_value == "72"
