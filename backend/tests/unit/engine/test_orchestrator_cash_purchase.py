"""
Tests for orchestrator cash purchase path (mortgage_interest_rate = 0).

Source: ENGINE_CONTRACTS.md Part 6 — defined scenarios.
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

class TestOrchestratorCashPurchase:

    def _cash_input(self):
        # Cash purchase: rate=0 indicates no mortgage.
        # Deposit must remain below purchase_price to avoid V-06.
        return dataclasses.replace(
            make_e01_input(),
            mortgage_interest_rate=Decimal("0"),
        )

    def test_icr_is_computed_when_rate_zero_but_loan_nonzero(self) -> None:
        """
        rate=0 with deposit=50,000 < price=200,000 → loan=150,000.
        stressed_annual_interest = 150,000 × 5.5% = 8,250 (non-zero).
        icr_percent is therefore a Decimal, not None.

        ENGINE_CONTRACTS.md Part 6: icr_percent=None only when loan_amount=0.
        loan_amount=0 requires deposit=purchase_price, which V-06 (HARD) blocks
        for any valid EngineInput. rate=0 does NOT force loan=0.
        """
        result = run(self._cash_input(), make_reference_config())
        assert isinstance(result, EngineResult)
        assert isinstance(result.outputs.icr_percent, Decimal)

    def test_loan_amount_equals_price_minus_deposit(self) -> None:
        """
        rate=0 does not override the loan calculation.
        loan_amount = purchase_price - deposit_amount = 200,000 - 50,000 = 150,000.
        F-04 is unconditional: CALCULATION_SPEC.md F-04.
        """
        result = run(self._cash_input(), make_reference_config())
        assert isinstance(result, EngineResult)
        assert result.intermediates.loan_amount_gbp == Decimal("150000.00")

    def test_annual_mortgage_cost_is_zero(self) -> None:
        result = run(self._cash_input(), make_reference_config())
        assert isinstance(result, EngineResult)
        assert result.outputs.annual_mortgage_cost_gbp == Decimal("0.00")

    def test_high_leverage_not_triggered_for_cash(self) -> None:
        """ltv=0 → HIGH_LEVERAGE (>75) must not fire."""
        result = run(self._cash_input(), make_reference_config())
        assert isinstance(result, EngineResult)
        codes = {f.code for f in result.risk_flags}
        assert "HIGH_LEVERAGE" not in codes

    def test_v10_warn_in_validation_warnings(self) -> None:
        """
        V-10: interest rate=0 → WARN 'treated as cash purchase'.
        Carried forward into EngineResult.validation_warnings.
        """
        result = run(self._cash_input(), make_reference_config())
        assert isinstance(result, EngineResult)
        warn_codes = {w.rule_code for w in result.validation_warnings}
        assert "V-10" in warn_codes
