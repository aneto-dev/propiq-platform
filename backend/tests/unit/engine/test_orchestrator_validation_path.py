"""
Tests for orchestrator validation path (Step 0).

Verifies: HARD failure → ValidationResult; WARN-only → EngineResult with
warnings populated; clean input → EngineResult with empty warnings.

Source: ENGINE_ARCHITECTURE.md Part 6 Step 0.
"""

import dataclasses
from decimal import Decimal

from app.domain.enums import (
    IncomeTaxBand,
    MortgageType,
    OwnershipStructure,
    PropertyCountry,
    PropertyType,
    Tenure,
)
from app.engine import run
from app.engine.contracts import (
    AssumptionConfig,
    CorporationTaxConfig,
    EngineConfig,
    EngineInput,
    EngineResult,
    SDLTBand,
    SDLTConfig,
    ValidationResult,
)


def make_reference_config() -> EngineConfig:
    """
    v1.0 reference EngineConfig from ENGINE_CONTRACTS.md Part 2.
    Used across all orchestrator tests.
    """
    return EngineConfig(
        sdlt_config=SDLTConfig(
            bands=[
                SDLTBand(Decimal("0"),       Decimal("125000"),  Decimal("0.00")),
                SDLTBand(Decimal("125000"),  Decimal("250000"),  Decimal("0.02")),
                SDLTBand(Decimal("250000"),  Decimal("925000"),  Decimal("0.05")),
                SDLTBand(Decimal("925000"),  Decimal("1500000"), Decimal("0.10")),
                SDLTBand(Decimal("1500000"), None,               Decimal("0.12")),
            ],
            additional_dwelling_surcharge_rate=Decimal("0.03"),
        ),
        corporation_tax_config=CorporationTaxConfig(
            small_profits_rate=Decimal("0.19"),
            small_profits_upper_threshold=Decimal("50000"),
            main_rate=Decimal("0.25"),
            main_rate_lower_threshold=Decimal("250000"),
            marginal_relief_numerator=3,
            marginal_relief_denominator=200,
        ),
        assumption_config=AssumptionConfig(
            void_rate_percent_default=Decimal("3.85"),
            letting_agent_fee_percent_default=Decimal("10.00"),
            letting_agent_vat_rate_percent=Decimal("20.00"),
            maintenance_reserve_percent_default=Decimal("1.00"),
            landlord_insurance_annual_default=Decimal("800.00"),
            purchase_legal_costs_default=Decimal("2500.00"),
            accountancy_cost_individual_default=Decimal("0.00"),
            accountancy_cost_ltd_default=Decimal("1200.00"),
            stress_test_rate_percent=Decimal("5.5"),
            icr_threshold_basic_rate_percent=Decimal("125.00"),
            icr_threshold_higher_rate_percent=Decimal("145.00"),
        ),
    )


def make_e01_input() -> EngineInput:
    """
    E-01 baseline: £200k, 25% deposit, 4.75% IO, INDIVIDUAL BASIC_RATE.
    Source: ENGINE_CONTRACTS.md E-01.
    """
    return EngineInput(
        purchase_price=Decimal("200000"),
        monthly_rent=Decimal("950"),
        deposit_amount=Decimal("50000"),
        mortgage_interest_rate=Decimal("4.75"),
        mortgage_term_years=25,
        mortgage_type=MortgageType.INTEREST_ONLY,
        ownership_structure=OwnershipStructure.INDIVIDUAL,
        income_tax_band=IncomeTaxBand.BASIC_RATE,
        is_additional_dwelling=True,
        property_type=PropertyType.RESIDENTIAL_SINGLE_LET,
        tenure=Tenure.FREEHOLD,
        property_country=PropertyCountry.ENGLAND,
        postcode="NG1 1AA",
        void_rate_percent=Decimal("3.85"),
        letting_agent_fee_percent=Decimal("10"),
        maintenance_reserve_percent=Decimal("1"),
        landlord_insurance_annual=Decimal("800"),
        purchase_legal_costs=Decimal("2500"),
        refurbishment_cost=Decimal("0"),
        annual_service_charge=Decimal("0"),
        annual_ground_rent=Decimal("0"),
        annual_accountancy_cost=Decimal("0"),
        lease_years_remaining=None,
    )

class TestOrchestratorValidationPath:

    def test_hard_failure_returns_validation_result(self) -> None:
        """
        purchase_price=0 triggers V-01 (HARD) → ValidationResult returned.
        EngineResult is never produced.
        """
        bad_input = dataclasses.replace(
            make_e01_input(), purchase_price=Decimal("0")
        )
        result = run(bad_input, make_reference_config())
        assert isinstance(result, ValidationResult)
        assert result.is_valid is False
        assert any(e.rule_code == "V-01" for e in result.hard_errors)

    def test_hard_failure_does_not_produce_engine_result(self) -> None:
        bad_input = dataclasses.replace(
            make_e01_input(), purchase_price=Decimal("0")
        )
        result = run(bad_input, make_reference_config())
        assert not isinstance(result, EngineResult)

    def test_warn_only_produces_engine_result(self) -> None:
        """
        refurbishment_cost=0 triggers V-25 (WARN only) → EngineResult returned.
        validation_warnings contains V-25.
        EngineResult has no is_valid field — its existence confirms success.
        Source: ENGINE_CONTRACTS.md Part 3 (EngineResult field list).
        """
        result = run(make_e01_input(), make_reference_config())
        assert isinstance(result, EngineResult)
        warn_codes = {w.rule_code for w in result.validation_warnings}
        assert "V-25" in warn_codes

    def test_warn_does_not_stop_calculation(self) -> None:
        """WARN-only result still contains fully populated outputs."""
        result = run(make_e01_input(), make_reference_config())
        assert isinstance(result, EngineResult)
        assert result.outputs.gross_annual_rent_gbp == Decimal("11400.00")

    def test_clean_input_produces_empty_validation_warnings(self) -> None:
        """
        Input with refurbishment_cost=100 and no other WARN triggers →
        validation_warnings is empty (no WARN rules fire).
        """
        clean = dataclasses.replace(make_e01_input(), refurbishment_cost=Decimal("100"))
        result = run(clean, make_reference_config())
        assert isinstance(result, EngineResult)
        assert result.validation_warnings == []
