"""Pipeline-level tests for the flag evaluator.

Tests: ordering, simultaneous flags, no duplicates, RiskFlag structure, E-01 flag set.
Source: TEST_STRATEGY.md Part 6.4.
"""
import dataclasses
from decimal import Decimal

from app.domain.enums import IncomeTaxBand, OwnershipStructure, Tenure
from app.engine.contracts import FlagSeverity, RiskFlag
from app.engine.risk_flags.definitions import (
    FLAG_DEFINITIONS,
    EvaluationContext,
    evaluate_flags,
)

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

class TestFlagEvaluationPipeline:

    def test_16_flags_defined(self) -> None:
        assert len(FLAG_DEFINITIONS) == 16

    def test_flag_codes_are_unique(self) -> None:
        codes = [d.code for d in FLAG_DEFINITIONS]
        assert len(codes) == len(set(codes))

    def test_all_flags_evaluated_simultaneously(self) -> None:
        """Multiple flags fire at once. TEST_STRATEGY.md 6.4."""
        flags = evaluate_flags(_ctx(annual_cash_flow=Decimal("-500"),
            gross_yield_percent=Decimal("3.50")))
        codes = _codes(flags)
        assert "NEGATIVE_CASHFLOW" in codes
        assert "LOW_GROSS_YIELD" in codes
        assert "RENT_UNVERIFIED" in codes

    def test_ordering_high_before_medium_before_info(self) -> None:
        """Result list follows FLAG_DEFINITIONS order:
        HIGH before MEDIUM before INFO."""
        flags = evaluate_flags(_ctx(annual_cash_flow=Decimal("-500"),
            net_yield_percent=Decimal("2.50")))
        severities = [f.severity for f in flags]
        high_idx = [i for i, s in enumerate(severities) if s == FlagSeverity.HIGH]
        med_idx  = [i for i, s in enumerate(severities) if s == FlagSeverity.MEDIUM]
        info_idx = [i for i, s in enumerate(severities) if s == FlagSeverity.INFO]
        if high_idx and med_idx:
            assert max(high_idx) < min(med_idx)
        if med_idx and info_idx:
            assert max(med_idx) < min(info_idx)

    def test_no_duplicate_flags(self) -> None:
        flags = evaluate_flags(_ctx(annual_cash_flow=Decimal("-500"),
            net_yield_percent=Decimal("2.50"), gross_yield_percent=Decimal("3.50")))
        codes = [f.code for f in flags]
        assert len(codes) == len(set(codes))

    def test_risk_flag_structure(self) -> None:
        """Every RiskFlag has non-empty required fields. TEST_STRATEGY.md 6.4."""
        for flag in evaluate_flags(_ctx(annual_cash_flow=Decimal("-331.90"))):
            assert isinstance(flag, RiskFlag)
            assert isinstance(flag.code, str) and flag.code
            assert flag.severity in (
                FlagSeverity.HIGH, FlagSeverity.MEDIUM, FlagSeverity.INFO
            )
            assert isinstance(flag.triggered_by_field, str) and flag.triggered_by_field
            assert isinstance(flag.triggered_by_value, str) and flag.triggered_by_value
            assert isinstance(flag.message, str) and flag.message

    def test_e01_flag_set(self) -> None:
        """E-01: NEGATIVE_CASHFLOW and RENT_UNVERIFIED fire. All others absent.
        Source: ENGINE_CONTRACTS.md E-01."""
        e01 = EvaluationContext(
            annual_cash_flow=Decimal("-331.90"),
            gross_annual_rent=Decimal("11400"),
            net_operating_income=Decimal("6793.10"),
            gross_yield_percent=Decimal("5.70"),
            net_yield_percent=Decimal("3.40"),
            ltv_percent=Decimal("75.00"),
            icr_percent=Decimal("132.86"),
            pre_tax_annual_cash_flow=Decimal("-331.90"),
            ownership_structure=OwnershipStructure.INDIVIDUAL,
            income_tax_band=IncomeTaxBand.BASIC_RATE,
            tenure=Tenure.FREEHOLD,
            lease_years_remaining=None,
            purchase_price=Decimal("200000"),
            refurbishment_cost=Decimal("0"),
            monthly_rent=Decimal("950"),
        )
        codes = _codes(evaluate_flags(e01))
        assert "NEGATIVE_CASHFLOW" in codes
        assert "RENT_UNVERIFIED" in codes
        for absent in ["HIGH_LEVERAGE", "LOW_GROSS_YIELD", "LOW_NET_YIELD",
                        "LOW_ICR_BASIC", "LOW_ICR_HIGHER_RATE", "SECTION_24_IMPACT",
                        "NEGATIVE_NOI", "ATED_WARNING", "LTD_EXTRACTION_UNDISCLOSED"]:
            assert absent not in codes, f"{absent} must not fire for E-01"

    def test_rent_unverified_always_present(self) -> None:
        """RENT_UNVERIFIED must appear in every evaluation result."""
        for ctx in [_CTX,
                    _ctx(annual_cash_flow=Decimal("-500")),
                    _ctx(
                        ownership_structure=OwnershipStructure.LIMITED_COMPANY,
                        income_tax_band=None,
                    )]:
            assert "RENT_UNVERIFIED" in _codes(evaluate_flags(ctx))
