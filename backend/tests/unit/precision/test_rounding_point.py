"""
PREC-03 and PREC-04 — Rounding occurs only at output stage.

Full-precision intermediates are computed first; rounding to 2dp happens
only when writing EngineOutputs and EngineIntermediates (Step 13).

Source: TEST_STRATEGY.md Part 9.3; ENGINE_CONTRACTS.md Part 7.2.
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

class TestRoundingPoint:

    def test_prec03_effective_rent_rounded_at_output_only(self) -> None:
        """
        PREC-03: monthly_rent=933.33, void=3.85%
          gross_annual_rent = 933.33 × 12 = 11,199.96 (exact)
          void_decimal = 3.85 / 100 = 0.0385
          effective (full precision) = 11,199.96 × (1 − 0.0385)
                                     = 11,199.96 × 0.9615
                                     = 10,768.76154 (verified)
          Output: 10,768.76 (rounded to 2dp at output stage only)

        Note: TEST_STRATEGY.md PREC-03 states 10,776.96174 as the product of
        11,199.96 × 0.9615. This is an arithmetic error in that document.
        The correct product is 10,768.76154. This test uses the arithmetically
        correct expected value, derived from CALCULATION_SPEC.md F-01 through F-03.

        Source: CALCULATION_SPEC.md F-01, F-02, F-03.
        """
        result = run(
            _make_input(monthly_rent=Decimal("933.33")),
            _make_config(),
        )
        assert isinstance(result, EngineResult)
        # 933.33 × 12 = 11199.96
        # 11199.96 × 0.9615 = 10768.76154...  rounds to 10768.76
        assert result.outputs.effective_annual_rent_gbp == Decimal("10768.76")
        assert result.intermediates.effective_annual_rent_gbp == Decimal("10768.76")

    def test_prec04_sdlt_no_intermediate_rounding(self) -> None:
        """
        PREC-04: purchase_price=300000.33
          Band 0-125000:    taxable=125000,    tax=0.00
          Band 125000-250000: taxable=125000.33, tax=125000.33 × 0.02 = 2500.0066
          Band 250000-300000.33: taxable=50000.33, tax=50000.33 × 0.05 = 2500.0165
          sdlt_base = 0 + 2500.0066 + 2500.0165 = 5000.0231

        Rounded at output: sdlt_base_gbp = 5000.02 (not 5000.00)
        If bands were rounded before summing: 2500.01 + 2500.02 = 5000.03 (wrong)

        Source: TEST_STRATEGY.md PREC-04.
        Note: The spec example uses 5000.0066 for a different price;
        this test uses 300000.33 to guarantee sub-cent band arithmetic.
        """
        result = run(
            _make_input(purchase_price=Decimal("300000.33"),
                        deposit_amount=Decimal("75001")),
            _make_config(),
        )
        assert isinstance(result, EngineResult)
        # sdlt_base = 2500.0066 + 2500.0165 = 5000.0231 → rounds to 5000.02
        assert result.intermediates.sdlt_base_gbp == Decimal("5000.02")

    def test_output_fields_are_two_decimal_places(self) -> None:
        """All output monetary/percentage fields are rounded to exactly 2dp."""
        result = run(_make_input(), _make_config())
        assert isinstance(result, EngineResult)
        for field_name, val in [
            ("gross_annual_rent_gbp", result.outputs.gross_annual_rent_gbp),
            ("ltv_percent", result.outputs.ltv_percent),
            ("total_sdlt_gbp", result.outputs.total_sdlt_gbp),
        ]:
            sign, digits, exp = val.as_tuple()
            assert exp >= -2, (
                f"{field_name} has more than 2dp: {val}"
            )
