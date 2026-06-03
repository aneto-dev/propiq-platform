"""
Shared test fixtures for PropIQ engine tests.

Defines:
  REFERENCE_CONFIG       — the v1.0 EngineConfig used across all scenarios
  ALTERNATIVE_CONFIG_VOID   — REFERENCE_CONFIG with void_rate=5.00%
  ALTERNATIVE_CONFIG_STRESS — REFERENCE_CONFIG with stress_rate=7.00%
  e01_input()  through e12_input()  — scenario input builders
  e01_expected() through e12_expected() — expected result dicts

All expected values are hardcoded from ENGINE_CONTRACTS.md Part 11.
Nothing is computed at fixture-definition time from formulas.

Source: TEST_STRATEGY.md Part 2.1 and 2.2.
        IMPLEMENTATION_ROADMAP.md Commit 2.9.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest

from app.domain.enums import (
    IncomeTaxBand,
    MortgageType,
    OwnershipStructure,
    PropertyCountry,
    PropertyType,
    Tenure,
)
from app.engine.contracts import (
    AssumptionConfig,
    CorporationTaxConfig,
    EngineConfig,
    EngineInput,
    SDLTBand,
    SDLTConfig,
)

# ---------------------------------------------------------------------------
# Reference configuration — v1.0 defaults (ENGINE_CONTRACTS.md Part 2)
# Must never be mutated by any test.
# ---------------------------------------------------------------------------

REFERENCE_CONFIG = EngineConfig(
    sdlt_config=SDLTConfig(
        bands=[
            SDLTBand(Decimal("0"),        Decimal("125000"),  Decimal("0.00")),
            SDLTBand(Decimal("125000"),   Decimal("250000"),  Decimal("0.02")),
            SDLTBand(Decimal("250000"),   Decimal("925000"),  Decimal("0.05")),
            SDLTBand(Decimal("925000"),   Decimal("1500000"), Decimal("0.10")),
            SDLTBand(Decimal("1500000"),  None,               Decimal("0.12")),
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

ALTERNATIVE_CONFIG_VOID = dataclasses.replace(
    REFERENCE_CONFIG,
    assumption_config=dataclasses.replace(
        REFERENCE_CONFIG.assumption_config,
        void_rate_percent_default=Decimal("5.00"),
    ),
)

ALTERNATIVE_CONFIG_STRESS = dataclasses.replace(
    REFERENCE_CONFIG,
    assumption_config=dataclasses.replace(
        REFERENCE_CONFIG.assumption_config,
        stress_test_rate_percent=Decimal("7.00"),
    ),
)


# ---------------------------------------------------------------------------
# Scenario input builders
# ---------------------------------------------------------------------------

def _base_input(**overrides) -> EngineInput:
    """
    E-01 base: £200k, 25% deposit, 4.75% IO, INDIVIDUAL BASIC_RATE, FREEHOLD.
    Override any field explicitly. All optional fields at default-equivalent.
    """
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
        refurbishment_cost=Decimal("0"),
        annual_service_charge=Decimal("0"),
        annual_ground_rent=Decimal("0"),
        annual_accountancy_cost=Decimal("0"),
        lease_years_remaining=None,
    )
    return dataclasses.replace(base, **overrides)


def e01_input() -> EngineInput:
    """E-01: Baseline, INDIVIDUAL BASIC_RATE, 25% deposit, 4.75% IO."""
    return _base_input()


def e02_input() -> EngineInput:
    """E-02: Same as E-01 but HIGHER_RATE taxpayer."""
    return _base_input(income_tax_band=IncomeTaxBand.HIGHER_RATE)


def e03_input() -> EngineInput:
    """E-03: £350k, LIMITED_COMPANY, 5.00% IO, accountancy=£1,200."""
    return _base_input(
        purchase_price=Decimal("350000"),
        monthly_rent=Decimal("1600"),
        deposit_amount=Decimal("87500"),
        mortgage_interest_rate=Decimal("5.00"),
        ownership_structure=OwnershipStructure.LIMITED_COMPANY,
        income_tax_band=None,
        annual_accountancy_cost=Decimal("1200"),
        postcode="M1 1AA",
    )


def e04_input() -> EngineInput:
    """E-04: Same as E-01 but 40% deposit (60% LTV), positive cash flow."""
    return _base_input(deposit_amount=Decimal("80000"))


def e05_input() -> EngineInput:
    """E-05: £600k, LIMITED_COMPANY, 5.25% IO — ATED + LOW_ICR_BASIC."""
    return _base_input(
        purchase_price=Decimal("600000"),
        monthly_rent=Decimal("2400"),
        deposit_amount=Decimal("150000"),
        mortgage_interest_rate=Decimal("5.25"),
        ownership_structure=OwnershipStructure.LIMITED_COMPANY,
        income_tax_band=None,
        annual_accountancy_cost=Decimal("1200"),
        postcode="SW1A 1AA",
    )


def e06_input() -> EngineInput:
    """E-06: Leasehold flat, HIGHER_RATE, service charge, ground rent."""
    return _base_input(
        purchase_price=Decimal("180000"),
        monthly_rent=Decimal("850"),
        deposit_amount=Decimal("45000"),
        mortgage_interest_rate=Decimal("4.75"),
        income_tax_band=IncomeTaxBand.HIGHER_RATE,
        tenure=Tenure.LEASEHOLD,
        annual_service_charge=Decimal("1200"),
        annual_ground_rent=Decimal("150"),
        lease_years_remaining=95,
        postcode="E1 1AA",
    )


def e07_input() -> EngineInput:
    """E-07: Deposit=25,000 (12.5% of 200k) — V-07 HARD failure."""
    return _base_input(deposit_amount=Decimal("25000"))


def e08_input() -> EngineInput:
    """E-08: Deposit=35,000 (17.5% of 200k) — V-08 WARN, calculation proceeds."""
    return _base_input(deposit_amount=Decimal("35000"))


def e09_input() -> EngineInput:
    """E-09: Same as E-06 but lease_years_remaining=72 — LEASEHOLD_SHORT_LEASE."""
    return dataclasses.replace(e06_input(), lease_years_remaining=72)


def e10_input() -> EngineInput:
    """E-10: Same as E-01 but ADDITIONAL_RATE — maximum Section 24 impact."""
    return _base_input(income_tax_band=IncomeTaxBand.ADDITIONAL_RATE)


def e11_input() -> EngineInput:
    """E-11: £220k, 3.80% IO, positive but thin-margin cash flow."""
    return _base_input(
        purchase_price=Decimal("220000"),
        deposit_amount=Decimal("55000"),
        mortgage_interest_rate=Decimal("3.80"),
        postcode="LS1 1AA",
    )


def e12_input() -> EngineInput:
    """E-12: Same as E-01 but refurbishment_cost=25,000 — HIGH_REFURB_RATIO."""
    return _base_input(refurbishment_cost=Decimal("25000"))


# ---------------------------------------------------------------------------
# Expected output dicts (from ENGINE_CONTRACTS.md Part 11)
# All values exactly as documented. Keyed by field name.
# ---------------------------------------------------------------------------

def e01_expected_outputs() -> dict[str, object]:
    """E-01 expected EngineOutputs — ENGINE_CONTRACTS.md E-01."""
    return {
        "gross_annual_rent_gbp":              Decimal("11400.00"),
        "effective_annual_rent_gbp":          Decimal("10961.10"),
        "total_operating_costs_annual_gbp":   Decimal("4168.00"),
        "net_operating_income_gbp":           Decimal("6793.10"),
        "annual_mortgage_cost_gbp":           Decimal("7125.00"),
        "annual_tax_liability_gbp":           Decimal("0.00"),
        "annual_cash_flow_gbp":               Decimal("-331.90"),
        "monthly_cash_flow_gbp":              Decimal("-27.66"),
        "gross_yield_percent":                Decimal("5.70"),
        "net_yield_percent":                  Decimal("3.40"),
        "roce_percent":                       Decimal("11.32"),
        "cash_on_cash_return_percent":        Decimal("-0.55"),
        "ltv_percent":                        Decimal("75.00"),
        "icr_percent":                        Decimal("132.86"),
        "total_sdlt_gbp":                     Decimal("7500.00"),
        "total_acquisition_cost_gbp":         Decimal("210000.00"),
        "total_cash_deployed_gbp":            Decimal("60000.00"),
    }


def e01_expected_flags() -> frozenset[str]:
    return frozenset({"NEGATIVE_CASHFLOW", "RENT_UNVERIFIED"})


def e01_absent_flags() -> frozenset[str]:
    return frozenset({
        "HIGH_LEVERAGE", "LOW_GROSS_YIELD", "LOW_NET_YIELD", "LOW_ICR_BASIC",
        "LOW_ICR_HIGHER_RATE", "SECTION_24_IMPACT", "CASH_FLOW_PRE_TAX_ONLY",
        "LOW_MARGIN_SAFETY", "HIGH_REFURB_RATIO", "ATED_WARNING",
        "LTD_EXTRACTION_UNDISCLOSED", "LEASEHOLD_SHORT_LEASE",
        "NEGATIVE_NOI", "HIGH_LEVERAGE_EXTREME",
    })


def e01_expected_warnings() -> frozenset[str]:
    return frozenset({"V-25"})


def e02_expected_outputs() -> dict[str, object]:
    """E-02 expected EngineOutputs — ENGINE_CONTRACTS.md E-02."""
    return {
        "gross_annual_rent_gbp":              Decimal("11400.00"),
        "effective_annual_rent_gbp":          Decimal("10961.10"),
        "total_operating_costs_annual_gbp":   Decimal("4168.00"),
        "net_operating_income_gbp":           Decimal("6793.10"),
        "annual_mortgage_cost_gbp":           Decimal("7125.00"),
        "annual_tax_liability_gbp":           Decimal("1292.24"),
        "annual_cash_flow_gbp":               Decimal("-1624.14"),
        "monthly_cash_flow_gbp":              Decimal("-135.35"),
        "gross_yield_percent":                Decimal("5.70"),
        "net_yield_percent":                  Decimal("3.40"),
        "roce_percent":                       Decimal("11.32"),
        "cash_on_cash_return_percent":        Decimal("-2.71"),
        "ltv_percent":                        Decimal("75.00"),
        "icr_percent":                        Decimal("132.86"),
        "total_sdlt_gbp":                     Decimal("7500.00"),
        "total_acquisition_cost_gbp":         Decimal("210000.00"),
        "total_cash_deployed_gbp":            Decimal("60000.00"),
    }


def e02_expected_flags() -> frozenset[str]:
    return frozenset({
        "NEGATIVE_CASHFLOW", "SECTION_24_IMPACT",
        "LOW_ICR_HIGHER_RATE", "RENT_UNVERIFIED",
    })


def e02_absent_flags() -> frozenset[str]:
    return frozenset({
        "HIGH_LEVERAGE", "LOW_GROSS_YIELD", "LOW_NET_YIELD",
        "LOW_ICR_BASIC", "ATED_WARNING", "LTD_EXTRACTION_UNDISCLOSED",
        "LEASEHOLD_SHORT_LEASE", "NEGATIVE_NOI",
    })


def e02_expected_warnings() -> frozenset[str]:
    return frozenset({"V-25"})


def e03_expected_outputs() -> dict[str, object]:
    """E-03 expected EngineOutputs — ENGINE_CONTRACTS.md E-03."""
    return {
        "gross_annual_rent_gbp":              Decimal("19200.00"),
        "effective_annual_rent_gbp":          Decimal("18460.80"),
        "total_operating_costs_annual_gbp":   Decimal("7804.00"),
        "net_operating_income_gbp":           Decimal("10656.80"),
        "annual_mortgage_cost_gbp":           Decimal("13125.00"),
        "annual_tax_liability_gbp":           Decimal("0.00"),
        "annual_cash_flow_gbp":               Decimal("-2468.20"),
        "monthly_cash_flow_gbp":              Decimal("-205.68"),
        "gross_yield_percent":                Decimal("5.49"),
        "net_yield_percent":                  Decimal("3.04"),
        "roce_percent":                       Decimal("9.87"),
        "cash_on_cash_return_percent":        Decimal("-2.29"),
        "ltv_percent":                        Decimal("75.00"),
        "icr_percent":                        Decimal("127.87"),
        "total_sdlt_gbp":                     Decimal("18000.00"),
        "total_acquisition_cost_gbp":         Decimal("370500.00"),
        "total_cash_deployed_gbp":            Decimal("108000.00"),
    }


def e03_expected_flags() -> frozenset[str]:
    return frozenset({
        "NEGATIVE_CASHFLOW", "LTD_EXTRACTION_UNDISCLOSED", "RENT_UNVERIFIED",
    })


def e03_absent_flags() -> frozenset[str]:
    return frozenset({
        "SECTION_24_IMPACT", "LOW_ICR_BASIC", "ATED_WARNING",
        "HIGH_LEVERAGE", "LOW_NET_YIELD",
    })


def e03_expected_warnings() -> frozenset[str]:
    return frozenset({"V-25"})


def e04_expected_outputs() -> dict[str, object]:
    """E-04 expected EngineOutputs — ENGINE_CONTRACTS.md E-04."""
    return {
        "gross_annual_rent_gbp":              Decimal("11400.00"),
        "effective_annual_rent_gbp":          Decimal("10961.10"),
        "total_operating_costs_annual_gbp":   Decimal("4168.00"),
        "net_operating_income_gbp":           Decimal("6793.10"),
        "annual_mortgage_cost_gbp":           Decimal("5700.00"),
        "annual_tax_liability_gbp":           Decimal("218.62"),
        "annual_cash_flow_gbp":               Decimal("874.48"),
        "monthly_cash_flow_gbp":              Decimal("72.87"),
        "gross_yield_percent":                Decimal("5.70"),
        "net_yield_percent":                  Decimal("3.40"),
        "roce_percent":                       Decimal("7.55"),
        "cash_on_cash_return_percent":        Decimal("0.97"),
        "ltv_percent":                        Decimal("60.00"),
        "icr_percent":                        Decimal("166.08"),
        "total_sdlt_gbp":                     Decimal("7500.00"),
        "total_acquisition_cost_gbp":         Decimal("210000.00"),
        "total_cash_deployed_gbp":            Decimal("90000.00"),
    }


def e04_expected_flags() -> frozenset[str]:
    return frozenset({"RENT_UNVERIFIED"})


def e04_absent_flags() -> frozenset[str]:
    return frozenset({
        "NEGATIVE_CASHFLOW", "HIGH_LEVERAGE", "LOW_ICR_BASIC",
        "SECTION_24_IMPACT", "LOW_MARGIN_SAFETY",
    })


def e04_expected_warnings() -> frozenset[str]:
    return frozenset({"V-25"})


def e05_expected_outputs() -> dict[str, object]:
    """E-05 expected EngineOutputs — ENGINE_CONTRACTS.md E-05."""
    return {
        "gross_annual_rent_gbp":              Decimal("28800.00"),
        "effective_annual_rent_gbp":          Decimal("27691.20"),
        "total_operating_costs_annual_gbp":   Decimal("11456.00"),
        "net_operating_income_gbp":           Decimal("16235.20"),
        "annual_mortgage_cost_gbp":           Decimal("23625.00"),
        "annual_tax_liability_gbp":           Decimal("0.00"),
        "annual_cash_flow_gbp":               Decimal("-7389.80"),
        "monthly_cash_flow_gbp":              Decimal("-615.82"),
        "gross_yield_percent":                Decimal("4.80"),
        "net_yield_percent":                  Decimal("2.71"),
        "roce_percent":                       Decimal("8.52"),
        "cash_on_cash_return_percent":        Decimal("-3.88"),
        "ltv_percent":                        Decimal("75.00"),
        "icr_percent":                        Decimal("111.88"),
        "total_sdlt_gbp":                     Decimal("38000.00"),
        "total_acquisition_cost_gbp":         Decimal("640500.00"),
        "total_cash_deployed_gbp":            Decimal("190500.00"),
    }


def e05_expected_flags() -> frozenset[str]:
    return frozenset({
        "NEGATIVE_CASHFLOW", "LOW_NET_YIELD", "LOW_ICR_BASIC",
        "ATED_WARNING", "LTD_EXTRACTION_UNDISCLOSED", "RENT_UNVERIFIED",
    })


def e05_absent_flags() -> frozenset[str]:
    return frozenset({"SECTION_24_IMPACT", "HIGH_LEVERAGE"})


def e05_expected_warnings() -> frozenset[str]:
    return frozenset({"V-25"})


def e06_expected_outputs() -> dict[str, object]:
    """E-06 expected EngineOutputs — ENGINE_CONTRACTS.md E-06."""
    return {
        "gross_annual_rent_gbp":              Decimal("10200.00"),
        "effective_annual_rent_gbp":          Decimal("9807.30"),
        "total_operating_costs_annual_gbp":   Decimal("5174.00"),
        "net_operating_income_gbp":           Decimal("4633.30"),
        "annual_mortgage_cost_gbp":           Decimal("6412.50"),
        "annual_tax_liability_gbp":           Decimal("570.82"),
        "annual_cash_flow_gbp":               Decimal("-2350.02"),
        "monthly_cash_flow_gbp":              Decimal("-195.84"),
        "gross_yield_percent":                Decimal("5.67"),
        "net_yield_percent":                  Decimal("2.57"),
        "roce_percent":                       Decimal("8.58"),
        "cash_on_cash_return_percent":        Decimal("-4.35"),
        "ltv_percent":                        Decimal("75.00"),
        "icr_percent":                        Decimal("132.10"),
        "total_sdlt_gbp":                     Decimal("6500.00"),
        "total_acquisition_cost_gbp":         Decimal("189000.00"),
        "total_cash_deployed_gbp":            Decimal("54000.00"),
    }


def e06_expected_flags() -> frozenset[str]:
    return frozenset({
        "NEGATIVE_CASHFLOW", "SECTION_24_IMPACT", "LOW_NET_YIELD",
        "LOW_ICR_HIGHER_RATE", "RENT_UNVERIFIED",
    })


def e06_absent_flags() -> frozenset[str]:
    return frozenset({"LEASEHOLD_SHORT_LEASE", "HIGH_LEVERAGE"})


def e06_expected_warnings() -> frozenset[str]:
    return frozenset({"V-25"})


def e07_expected_hard_error_code() -> str:
    """E-07 expected HARD validation failure code."""
    return "V-07"


def e08_expected_warnings() -> frozenset[str]:
    """E-08: V-08 (deposit < 25%) and V-25 (refurb=0) both fire."""
    return frozenset({"V-08", "V-25"})


def e08_expected_flags() -> frozenset[str]:
    """E-08: HIGH_LEVERAGE fires (ltv=82.50 > 75), plus standard flags."""
    return frozenset({
        "NEGATIVE_CASHFLOW", "HIGH_LEVERAGE", "RENT_UNVERIFIED",
    })


def e08_absent_flags() -> frozenset[str]:
    return frozenset({"HIGH_LEVERAGE_EXTREME"})


def e09_expected_flags() -> frozenset[str]:
    """E-09: Same as E-06 plus LEASEHOLD_SHORT_LEASE."""
    return e06_expected_flags() | frozenset({"LEASEHOLD_SHORT_LEASE"})


def e10_expected_outputs() -> dict[str, object]:
    """E-10 expected EngineOutputs (changes from E-01) — ENGINE_CONTRACTS.md E-10."""
    base = dict(e01_expected_outputs())
    base.update({
        "annual_tax_liability_gbp":           Decimal("1631.90"),
        "annual_cash_flow_gbp":               Decimal("-1963.80"),
        "monthly_cash_flow_gbp":              Decimal("-163.65"),
        "cash_on_cash_return_percent":        Decimal("-3.27"),
    })
    return base


def e10_expected_flags() -> frozenset[str]:
    return frozenset({
        "NEGATIVE_CASHFLOW", "SECTION_24_IMPACT",
        "LOW_ICR_HIGHER_RATE", "RENT_UNVERIFIED",
    })


def e10_expected_warnings() -> frozenset[str]:
    return frozenset({"V-25"})


def e11_expected_outputs() -> dict[str, object]:
    """E-11 expected EngineOutputs — ENGINE_CONTRACTS.md E-11."""
    return {
        "gross_annual_rent_gbp":              Decimal("11400.00"),
        "effective_annual_rent_gbp":          Decimal("10961.10"),
        "total_operating_costs_annual_gbp":   Decimal("4368.00"),
        "net_operating_income_gbp":           Decimal("6593.10"),
        "annual_mortgage_cost_gbp":           Decimal("6270.00"),
        "annual_tax_liability_gbp":           Decimal("64.62"),
        "annual_cash_flow_gbp":               Decimal("258.48"),
        "monthly_cash_flow_gbp":              Decimal("21.54"),
        "gross_yield_percent":                Decimal("5.18"),
        "net_yield_percent":                  Decimal("3.00"),
        "roce_percent":                       Decimal("9.30"),
        "cash_on_cash_return_percent":        Decimal("0.38"),
        "ltv_percent":                        Decimal("75.00"),
        "icr_percent":                        Decimal("150.08"),
        "total_sdlt_gbp":                     Decimal("8500.00"),
        "total_acquisition_cost_gbp":         Decimal("231000.00"),
        "total_cash_deployed_gbp":            Decimal("66000.00"),
    }


def e11_expected_flags() -> frozenset[str]:
    return frozenset({"LOW_MARGIN_SAFETY", "RENT_UNVERIFIED"})


def e11_absent_flags() -> frozenset[str]:
    return frozenset({"NEGATIVE_CASHFLOW", "LOW_ICR_BASIC"})


def e11_expected_warnings() -> frozenset[str]:
    return frozenset({"V-25"})


def e12_expected_outputs() -> dict[str, object]:
    """E-12 expected EngineOutputs — ENGINE_CONTRACTS.md E-12."""
    base = dict(e01_expected_outputs())
    base.update({
        "total_acquisition_cost_gbp":         Decimal("235000.00"),
        "total_cash_deployed_gbp":            Decimal("85000.00"),
        "roce_percent":                       Decimal("7.99"),
        "cash_on_cash_return_percent":        Decimal("-0.39"),
    })
    return base


def e12_expected_flags() -> frozenset[str]:
    return frozenset({
        "NEGATIVE_CASHFLOW", "HIGH_REFURB_RATIO", "RENT_UNVERIFIED",
    })


def e12_absent_flags() -> frozenset[str]:
    return frozenset({"LOW_MARGIN_SAFETY"})


def e12_expected_warnings() -> frozenset[str]:
    """E-12: refurb=25000 so V-25 does NOT fire (refurb > 0)."""
    return frozenset()


# ---------------------------------------------------------------------------
# pytest fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def reference_config() -> EngineConfig:
    """Shared REFERENCE_CONFIG for all tests. Session-scoped — never mutated."""
    return REFERENCE_CONFIG


@pytest.fixture(scope="session")
def alt_config_void() -> EngineConfig:
    return ALTERNATIVE_CONFIG_VOID


@pytest.fixture(scope="session")
def alt_config_stress() -> EngineConfig:
    return ALTERNATIVE_CONFIG_STRESS
