"""
Tests for orchestrator LIMITED_COMPANY pathway (Tax Pathway B).

Source: ENGINE_CONTRACTS.md E-03.
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

def make_e03_input():
    """
    E-03: £350k purchase, Ltd Co, IO, 5%.
    Source: ENGINE_CONTRACTS.md E-03.
    """
    return dataclasses.replace(
        make_e01_input(),
        purchase_price=Decimal("350000"),
        monthly_rent=Decimal("1600"),
        deposit_amount=Decimal("87500"),
        mortgage_interest_rate=Decimal("5.00"),
        ownership_structure=OwnershipStructure.LIMITED_COMPANY,
        income_tax_band=None,
        annual_accountancy_cost=Decimal("1200"),
    )


class TestOrchestratorLtdCo:

    def test_section_24_applies_is_false(self) -> None:
        """Pathway B: section_24_applies always False."""
        result = run(make_e03_input(), make_reference_config())
        assert isinstance(result, EngineResult)
        assert result.intermediates.section_24_applies is False

    def test_income_tax_gross_is_none(self) -> None:
        """INDIVIDUAL pathway fields are None for LIMITED_COMPANY."""
        result = run(make_e03_input(), make_reference_config())
        assert isinstance(result, EngineResult)
        assert result.intermediates.income_tax_gross_gbp is None
        assert result.intermediates.mortgage_interest_tax_credit_gbp is None

    def test_corporation_tax_gross_is_decimal(self) -> None:
        """Pathway B: corporation_tax_gross_gbp is always Decimal (even when 0)."""
        result = run(make_e03_input(), make_reference_config())
        assert isinstance(result, EngineResult)
        assert isinstance(
            result.intermediates.corporation_tax_gross_gbp, Decimal
        )

    def test_ltd_extraction_undisclosed_in_flags(self) -> None:
        """LTD_EXTRACTION_UNDISCLOSED always fires for LIMITED_COMPANY."""
        result = run(make_e03_input(), make_reference_config())
        assert isinstance(result, EngineResult)
        codes = {f.code for f in result.risk_flags}
        assert "LTD_EXTRACTION_UNDISCLOSED" in codes

    def test_section_24_impact_not_in_flags(self) -> None:
        """SECTION_24_IMPACT must not fire for LIMITED_COMPANY."""
        result = run(make_e03_input(), make_reference_config())
        assert isinstance(result, EngineResult)
        codes = {f.code for f in result.risk_flags}
        assert "SECTION_24_IMPACT" not in codes
