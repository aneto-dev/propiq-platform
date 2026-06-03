"""
Tests for orchestrator happy-path calculation (E-01 key outputs).

Verifies that the full 13-step pipeline produces correct key outputs
and that return types are correct.

Source: ENGINE_CONTRACTS.md E-01.
"""
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

class TestOrchestratorCalculationPath:

    def test_returns_engine_result(self) -> None:
        """Valid input → EngineResult."""
        result = run(make_e01_input(), make_reference_config())
        assert isinstance(result, EngineResult)

    def test_e01_gross_annual_rent(self) -> None:
        """950 × 12 = 11,400.00. Source: ENGINE_CONTRACTS.md E-01."""
        result = run(make_e01_input(), make_reference_config())
        assert isinstance(result, EngineResult)
        assert result.outputs.gross_annual_rent_gbp == Decimal("11400.00")

    def test_e01_ltv_percent(self) -> None:
        """loan=150000, price=200000 → ltv=75.00. Source: E-01."""
        result = run(make_e01_input(), make_reference_config())
        assert isinstance(result, EngineResult)
        assert result.outputs.ltv_percent == Decimal("75.00")

    def test_e01_total_sdlt(self) -> None:
        """price=200000, additional → total_sdlt=7500.00. Source: E-01."""
        result = run(make_e01_input(), make_reference_config())
        assert isinstance(result, EngineResult)
        assert result.outputs.total_sdlt_gbp == Decimal("7500.00")

    def test_e01_total_cash_deployed(self) -> None:
        """deposit+sdlt+legal = 50000+7500+2500 = 60000.00. Source: E-01."""
        result = run(make_e01_input(), make_reference_config())
        assert isinstance(result, EngineResult)
        assert result.outputs.total_cash_deployed_gbp == Decimal("60000.00")

    def test_rent_unverified_always_in_flags(self) -> None:
        """RENT_UNVERIFIED fires unconditionally. Source: CALCULATION_SPEC.md."""
        result = run(make_e01_input(), make_reference_config())
        assert isinstance(result, EngineResult)
        codes = {f.code for f in result.risk_flags}
        assert "RENT_UNVERIFIED" in codes

    def test_result_has_no_timestamps(self) -> None:
        """EngineResult contains no timestamps. Source: ENGINE_CONTRACTS.md Part 3."""
        result = run(make_e01_input(), make_reference_config())
        assert isinstance(result, EngineResult)
        for attr in dir(result):
            assert not attr.endswith("_at"), f"Unexpected timestamp field: {attr}"
            assert not attr.endswith("_time"), f"Unexpected time field: {attr}"
