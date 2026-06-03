"""
PREC-06 — Float is never used in engine calculation results.

Runs the full engine and asserts no leaf value in EngineOutputs or
EngineIntermediates is of type float.

Source: TEST_STRATEGY.md Part 9.5.
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


def _make_config() -> EngineConfig:
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


def _make_input(**overrides) -> EngineInput:
    base = EngineInput(
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
        refurbishment_cost=Decimal("100"),
        annual_service_charge=Decimal("0"),
        annual_ground_rent=Decimal("0"),
        annual_accountancy_cost=Decimal("0"),
        lease_years_remaining=None,
    )
    return dataclasses.replace(base, **overrides)

class TestNoFloatArithmetic:

    def test_no_float_in_engine_outputs(self) -> None:
        """
        PREC-06: Every monetary/percentage field in EngineOutputs is Decimal.
        float must never appear as a calculation result.
        Source: TEST_STRATEGY.md PREC-06.
        """
        result = run(_make_input(), _make_config())
        assert isinstance(result, EngineResult)
        out = result.outputs
        for field_name in out.__dataclass_fields__:
            val = getattr(out, field_name)
            if val is not None:
                assert not isinstance(val, float), (
                    f"EngineOutputs.{field_name} is float: {val}"
                )

    def test_no_float_in_engine_intermediates(self) -> None:
        """
        PREC-06: Every Decimal/bool field in EngineIntermediates is its
        declared type — never float.
        """
        result = run(_make_input(), _make_config())
        assert isinstance(result, EngineResult)
        inter = result.intermediates
        for field_name in inter.__dataclass_fields__:
            val = getattr(inter, field_name)
            if val is not None and not isinstance(val, (bool | list)):
                assert not isinstance(val, float), (
                    f"EngineIntermediates.{field_name} is float: {val}"
                )
