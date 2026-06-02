"""
Tests for Tax Pathway B — Limited company, Corporation Tax.

Tests call calculate_limited_company_tax() with explicit inputs and
assert all four intermediates. Corporation Tax config arguments are
passed explicitly — never hardcoded inside the function.

All expected values pre-computed from CALCULATION_SPEC.md formulas
and verified before these tests were written. Expected values are not
derived from the implementation under test.

Source: TEST_STRATEGY.md Part 4.3 — Tax Pathway B test cases TB-01 to TB-07.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.engine.tax.limited_company import (
    LimitedCompanyTaxResult,
    calculate_limited_company_tax,
)

TWO_DP = Decimal("0.01")


def r2(v: Decimal) -> Decimal:
    return v.quantize(TWO_DP, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Reference CT config (2025/26 — matches ENGINE_CONTRACTS.md seed data)
# Passed explicitly to every call — never hardcoded inside the function.
# ---------------------------------------------------------------------------
CT_CONFIG = {
    "small_profits_rate": Decimal("0.19"),
    "small_profits_upper_threshold": Decimal("50000"),
    "main_rate": Decimal("0.25"),
    "main_rate_lower_threshold": Decimal("250000"),
    "marginal_relief_numerator": 3,
    "marginal_relief_denominator": 200,
}


def _call(
    effective_annual_rent: Decimal,
    letting: Decimal,
    maint: Decimal,
    insur: Decimal,
    svc: Decimal,
    grd: Decimal,
    acct: Decimal,
    mtg_int: Decimal,
) -> LimitedCompanyTaxResult:
    """Helper: call with explicit CT config."""
    return calculate_limited_company_tax(
        effective_annual_rent=effective_annual_rent,
        letting_agent_annual=letting,
        annual_maintenance_reserve=maint,
        landlord_insurance_annual=insur,
        annual_service_charge=svc,
        annual_ground_rent=grd,
        annual_accountancy_cost=acct,
        annual_mortgage_interest=mtg_int,
        **CT_CONFIG,
    )


class TestPathwayBNegativeProfit:

    def test_tb01_e03_negative_taxable_profit(self) -> None:
        """
        TB-01: E-03 inputs — negative taxable profit, zero tax.

        Mortgage interest (13,125) is fully deductible.
        18460.80 - 2304 - 3500 - 800 - 0 - 0 - 1200 - 13125 = -2468.20

        Negative profit → corporation_tax = 0. This is the common outcome
        for a single-property SPV with a mortgage.

        Source: ENGINE_CONTRACTS.md E-03. TEST_STRATEGY.md TB-01.
        """
        result = _call(
            Decimal("18460.80"), Decimal("2304.00"), Decimal("3500.00"),
            Decimal("800.00"),   Decimal("0.00"),    Decimal("0.00"),
            Decimal("1200.00"), Decimal("13125.00"),
        )
        assert r2(result.taxable_company_profit) == Decimal("-2468.20")
        assert r2(result.corporation_tax_gross)  == Decimal("0.00")
        assert r2(result.annual_tax_liability)   == Decimal("0.00")
        assert result.section_24_applies is False

    def test_tb01_mortgage_interest_is_deductible(self) -> None:
        """
        Mortgage interest must be deducted from taxable profit in Pathway B.
        This is the key difference from Pathway A (Section 24).
        If interest were not deducted, profit would be positive.
        """
        result = _call(
            Decimal("18460.80"), Decimal("2304.00"), Decimal("3500.00"),
            Decimal("800.00"),   Decimal("0.00"),    Decimal("0.00"),
            Decimal("1200.00"), Decimal("13125.00"),
        )
        # Without interest deduction, profit = 10,656.80 (positive)
        # With interest deduction, profit = -2,468.20 (negative)
        assert result.taxable_company_profit < Decimal("0")


class TestPathwayBSmallProfitsRate:

    def test_tb02_positive_profit_small_profits_rate(self) -> None:
        """
        TB-02: Positive profit within small profits band (< £50,000).

        effective=18460.80, all non-mtg costs=5000, mtg_int=5000
        taxable = 18460.80 - 5000 - 5000 = 8460.80
        ct      = 8460.80 × 0.19 = 1607.55

        Source: TEST_STRATEGY.md TB-02.
        """
        result = _call(
            Decimal("18460.80"), Decimal("5000.00"), Decimal("0.00"),
            Decimal("0.00"),     Decimal("0.00"),    Decimal("0.00"),
            Decimal("0.00"),     Decimal("5000.00"),
        )
        assert r2(result.taxable_company_profit) == Decimal("8460.80")
        assert r2(result.corporation_tax_gross)  == Decimal("1607.55")
        assert r2(result.annual_tax_liability)   == Decimal("1607.55")

    def test_tb02_retained_profit_is_after_tax(self) -> None:
        """
        post_tax_retained_profit = taxable_profit - annual_tax_liability.
        Manual: 8460.80 - 1607.55 = 6853.25.
        """
        result = _call(
            Decimal("18460.80"), Decimal("5000.00"), Decimal("0.00"),
            Decimal("0.00"),     Decimal("0.00"),    Decimal("0.00"),
            Decimal("0.00"),     Decimal("5000.00"),
        )
        assert r2(result.post_tax_retained_profit) == Decimal("6853.25")

    def test_tb03_profit_exactly_at_small_profits_boundary(self) -> None:
        """
        TB-03: Taxable profit exactly £50,000 — small profits rate applies.

        ct = 50,000 × 0.19 = 9,500.00.
        At exactly £50,000 the small profits rate applies (not marginal relief).

        Source: TEST_STRATEGY.md TB-03.
        """
        result = _call(
            Decimal("50000"), Decimal("0"), Decimal("0"),
            Decimal("0"),     Decimal("0"), Decimal("0"),
            Decimal("0"),     Decimal("0"),
        )
        assert r2(result.taxable_company_profit) == Decimal("50000.00")
        assert r2(result.corporation_tax_gross)  == Decimal("9500.00")
        assert r2(result.annual_tax_liability)   == Decimal("9500.00")


class TestPathwayBMarginalRelief:

    def test_tb04_profit_at_50001_marginal_relief_band_entry(self) -> None:
        """
        TB-04: £50,001 — first penny in marginal relief band.

        gross = 50001 × 0.25 = 12,500.25
        relief = (250,000 - 50,001) × (3/200) = 199,999 × 0.015 = 2,999.985
        ct = 12,500.25 - 2,999.985 = 9,500.265 → rounds to 9,500.27

        Source: TEST_STRATEGY.md TB-04 (verified with Decimal arithmetic).
        """
        result = _call(
            Decimal("50001"), Decimal("0"), Decimal("0"),
            Decimal("0"),     Decimal("0"), Decimal("0"),
            Decimal("0"),     Decimal("0"),
        )
        assert r2(result.taxable_company_profit) == Decimal("50001.00")
        assert r2(result.corporation_tax_gross)  == Decimal("9500.27")
        assert r2(result.annual_tax_liability)   == Decimal("9500.27")

    def test_tb04_marginal_relief_uses_config_fraction(self) -> None:
        """
        Marginal relief fraction (3/200) must come from config, not hardcode.
        Test with an alternative fraction to confirm config is used.
        Using marginal_relief_numerator=1, denominator=100 (1/100 = 0.01).
        """
        result = calculate_limited_company_tax(
            effective_annual_rent=Decimal("50001"),
            letting_agent_annual=Decimal("0"),
            annual_maintenance_reserve=Decimal("0"),
            landlord_insurance_annual=Decimal("0"),
            annual_service_charge=Decimal("0"),
            annual_ground_rent=Decimal("0"),
            annual_accountancy_cost=Decimal("0"),
            annual_mortgage_interest=Decimal("0"),
            small_profits_rate=Decimal("0.19"),
            small_profits_upper_threshold=Decimal("50000"),
            main_rate=Decimal("0.25"),
            main_rate_lower_threshold=Decimal("250000"),
            marginal_relief_numerator=1,        # non-standard
            marginal_relief_denominator=100,    # fraction = 0.01
        )
        # With 1/100 relief: 50001 × 0.25 - (250000-50001) × 0.01
        # = 12500.25 - 1999.99 = 10500.26
        assert r2(result.corporation_tax_gross) == Decimal("10500.26")

    def test_tb05_profit_at_top_of_marginal_band(self) -> None:
        """
        TB-05: £250,000 — top of marginal relief band.

        At £250,000 the marginal relief formula produces:
        250,000 × 0.25 - (250,000 - 250,000) × (3/200)
        = 62,500 - 0 = 62,500.00

        Source: TEST_STRATEGY.md TB-05.
        """
        result = _call(
            Decimal("250000"), Decimal("0"), Decimal("0"),
            Decimal("0"),      Decimal("0"), Decimal("0"),
            Decimal("0"),      Decimal("0"),
        )
        assert r2(result.corporation_tax_gross) == Decimal("62500.00")
        assert r2(result.annual_tax_liability)  == Decimal("62500.00")


class TestPathwayBMainRate:

    def test_tb06_profit_above_250000_main_rate(self) -> None:
        """
        TB-06: £300,000 — above main rate threshold, full 25% applies.

        ct = 300,000 × 0.25 = 75,000.00.

        Source: TEST_STRATEGY.md TB-06.
        """
        result = _call(
            Decimal("300000"), Decimal("0"), Decimal("0"),
            Decimal("0"),      Decimal("0"), Decimal("0"),
            Decimal("0"),      Decimal("0"),
        )
        assert r2(result.taxable_company_profit) == Decimal("300000.00")
        assert r2(result.corporation_tax_gross)  == Decimal("75000.00")
        assert r2(result.annual_tax_liability)   == Decimal("75000.00")


class TestPathwayBEdgeCases:

    def test_tb07_zero_taxable_profit(self) -> None:
        """
        TB-07: Exactly zero taxable profit — no tax.

        Source: TEST_STRATEGY.md TB-07.
        """
        result = _call(
            Decimal("10000"), Decimal("10000"), Decimal("0"),
            Decimal("0"),     Decimal("0"),     Decimal("0"),
            Decimal("0"),     Decimal("0"),
        )
        assert r2(result.taxable_company_profit) == Decimal("0.00")
        assert r2(result.corporation_tax_gross)  == Decimal("0.00")
        assert r2(result.annual_tax_liability)   == Decimal("0.00")

    def test_section_24_always_false_for_pathway_b(self) -> None:
        """
        section_24_applies is always False for Pathway B.
        Section 24 does not apply to limited companies.
        Source: CALCULATION_SPEC.md — section_24_applies Derived Flag.
        """
        for mtg_int in [Decimal("0"), Decimal("7125"), Decimal("13125")]:
            result = _call(
                Decimal("18460.80"), Decimal("2304"), Decimal("3500"),
                Decimal("800"),      Decimal("0"),    Decimal("0"),
                Decimal("1200"),     mtg_int,
            )
            assert result.section_24_applies is False, (
                f"Expected section_24_applies=False for Ltd Co, "
                f"got True with mtg_int={mtg_int}"
            )

    def test_result_is_limited_company_tax_result(self) -> None:
        """Return type is LimitedCompanyTaxResult (a NamedTuple)."""
        result = _call(
            Decimal("18460.80"), Decimal("2304"), Decimal("3500"),
            Decimal("800"),      Decimal("0"),    Decimal("0"),
            Decimal("1200"),     Decimal("13125"),
        )
        assert isinstance(result, LimitedCompanyTaxResult)
        assert hasattr(result, "taxable_company_profit")
        assert hasattr(result, "corporation_tax_gross")
        assert hasattr(result, "annual_tax_liability")
        assert hasattr(result, "post_tax_retained_profit")
        assert hasattr(result, "section_24_applies")

    def test_all_numeric_fields_are_decimal(self) -> None:
        """All numeric fields are Decimal. section_24_applies is bool."""
        result = _call(
            Decimal("18460.80"), Decimal("2304"), Decimal("3500"),
            Decimal("800"),      Decimal("0"),    Decimal("0"),
            Decimal("1200"),     Decimal("13125"),
        )
        assert isinstance(result.taxable_company_profit,   Decimal)
        assert isinstance(result.corporation_tax_gross,    Decimal)
        assert isinstance(result.annual_tax_liability,     Decimal)
        assert isinstance(result.post_tax_retained_profit, Decimal)
        assert isinstance(result.section_24_applies,       bool)
