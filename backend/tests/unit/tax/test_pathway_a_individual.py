"""
Tests for Tax Pathway A — Individual ownership, Section 24.

Tests call calculate_individual_tax() directly with explicit inputs
and assert all four intermediates plus section_24_applies.

All expected values pre-computed from CALCULATION_SPEC.md formulas
and verified against ENGINE_CONTRACTS.md reference scenarios before
these tests were written. Expected values are not derived from the
implementation under test.

Source: TEST_STRATEGY.md Part 4.2 — Tax Pathway A test cases TA-01 to TA-06.
"""

from decimal import ROUND_HALF_UP, Decimal

from app.domain.enums import IncomeTaxBand
from app.engine.tax.individual import IndividualTaxResult, calculate_individual_tax

TWO_DP = Decimal("0.01")


def r2(v: Decimal) -> Decimal:
    return v.quantize(TWO_DP, rounding=ROUND_HALF_UP)


# ---------------------------------------------------------------------------
# Standard E-01 inputs used across TA-01 through TA-03
# Source: ENGINE_CONTRACTS.md E-01 expected intermediates
# ---------------------------------------------------------------------------
E01_INPUTS = {
    "effective_annual_rent": Decimal("10961.10"),
    "letting_agent_annual": Decimal("1368.00"),
    "annual_maintenance_reserve": Decimal("2000.00"),
    "landlord_insurance_annual": Decimal("800.00"),
    "annual_service_charge": Decimal("0.00"),
    "annual_ground_rent": Decimal("0.00"),
    "annual_accountancy_cost": Decimal("0.00"),
    "annual_mortgage_interest": Decimal("7125.00"),
}


class TestPathwayABasicRate:

    def test_ta01_basic_rate_credit_exceeds_tax(self) -> None:
        """
        TA-01: E-01 inputs, BASIC_RATE — credit exceeds gross tax.

        income_tax_gross = 6793.10 × 0.20 = 1358.62
        credit           = 7125.00 × 0.20 = 1425.00
        liability        = MAX(0, 1358.62 - 1425.00) = MAX(0, -66.38) = 0.00

        This is the Section 24 neutrality case: the 20% credit exactly
        offsets the 20% tax for a basic-rate taxpayer.
        Source: ENGINE_CONTRACTS.md E-01. TEST_STRATEGY.md TA-01.
        """
        result = calculate_individual_tax(
            **E01_INPUTS, income_tax_band=IncomeTaxBand.BASIC_RATE
        )
        assert r2(result.taxable_rental_income)     == Decimal("6793.10")
        assert r2(result.income_tax_gross)          == Decimal("1358.62")
        assert r2(result.mortgage_interest_tax_credit) == Decimal("1425.00")
        assert r2(result.annual_tax_liability)      == Decimal("0.00")
        assert result.section_24_applies is True

    def test_ta01_taxable_income_excludes_mortgage_interest(self) -> None:
        """
        taxable_rental_income must NOT include mortgage interest deduction.
        The defining feature of Section 24: interest is not deductible.
        """
        result = calculate_individual_tax(
            **E01_INPUTS, income_tax_band=IncomeTaxBand.BASIC_RATE
        )
        # Would be 6793.10 - 7125.00 = -331.90 if interest were deducted
        assert r2(result.taxable_rental_income) == Decimal("6793.10")
        assert r2(result.taxable_rental_income) != Decimal("-331.90")


class TestPathwayAHigherRate:

    def test_ta02_higher_rate_positive_liability(self) -> None:
        """
        TA-02: E-02 inputs, HIGHER_RATE — positive tax liability.

        income_tax_gross = 6793.10 × 0.40 = 2717.24
        credit           = 7125.00 × 0.20 = 1425.00  (credit is always 20%)
        liability        = 2717.24 - 1425.00 = 1292.24

        Section 24 impact: higher-rate taxpayer pays 40% but receives only
        a 20% credit, creating a real additional tax cost vs pre-2020.
        Source: ENGINE_CONTRACTS.md E-02. TEST_STRATEGY.md TA-02.
        """
        result = calculate_individual_tax(
            **E01_INPUTS, income_tax_band=IncomeTaxBand.HIGHER_RATE
        )
        assert r2(result.taxable_rental_income)        == Decimal("6793.10")
        assert r2(result.income_tax_gross)             == Decimal("2717.24")
        assert r2(result.mortgage_interest_tax_credit) == Decimal("1425.00")
        assert r2(result.annual_tax_liability)         == Decimal("1292.24")
        assert result.section_24_applies is True

    def test_ta02_credit_rate_unchanged_at_higher_rate(self) -> None:
        """
        Mortgage interest credit is always 20% regardless of marginal rate.
        This is the legislative definition of Section 24.
        """
        result = calculate_individual_tax(
            **E01_INPUTS, income_tax_band=IncomeTaxBand.HIGHER_RATE
        )
        # Credit must be 20% of interest — not 40%
        expected_credit_at_20pct = r2(Decimal("7125.00") * Decimal("0.20"))
        wrong_credit_at_40pct    = r2(Decimal("7125.00") * Decimal("0.40"))
        assert r2(result.mortgage_interest_tax_credit) == expected_credit_at_20pct
        assert r2(result.mortgage_interest_tax_credit) != wrong_credit_at_40pct


class TestPathwayAAdditionalRate:

    def test_ta03_additional_rate_maximum_s24_impact(self) -> None:
        """
        TA-03: E-10 inputs, ADDITIONAL_RATE — maximum Section 24 divergence.

        income_tax_gross = 6793.10 × 0.45 = 3056.90
        credit           = 7125.00 × 0.20 = 1425.00
        liability        = 3056.90 - 1425.00 = 1631.90

        Source: ENGINE_CONTRACTS.md E-10. TEST_STRATEGY.md TA-03.
        """
        result = calculate_individual_tax(
            **E01_INPUTS, income_tax_band=IncomeTaxBand.ADDITIONAL_RATE
        )
        assert r2(result.income_tax_gross)             == Decimal("3056.90")
        assert r2(result.mortgage_interest_tax_credit) == Decimal("1425.00")
        assert r2(result.annual_tax_liability)         == Decimal("1631.90")
        assert result.section_24_applies is True


class TestPathwayAEdgeCases:

    def test_ta04_zero_taxable_income_no_liability(self) -> None:
        """
        TA-04: Costs equal effective rent — taxable income is zero.

        taxable_rental_income = 0.00
        income_tax_gross      = MAX(0, 0.00) × 0.40 = 0.00
        credit                = 10,000 × 0.20 = 2,000.00
        liability             = MAX(0, 0.00 - 2000.00) = 0.00

        When taxable income is zero, the credit cannot create a refund.
        Source: TEST_STRATEGY.md TA-04.
        """
        result = calculate_individual_tax(
            effective_annual_rent=Decimal("5000.00"),
            letting_agent_annual=Decimal("5000.00"),
            annual_maintenance_reserve=Decimal("0.00"),
            landlord_insurance_annual=Decimal("0.00"),
            annual_service_charge=Decimal("0.00"),
            annual_ground_rent=Decimal("0.00"),
            annual_accountancy_cost=Decimal("0.00"),
            annual_mortgage_interest=Decimal("10000.00"),
            income_tax_band=IncomeTaxBand.HIGHER_RATE,
        )
        assert r2(result.taxable_rental_income)     == Decimal("0.00")
        assert r2(result.income_tax_gross)          == Decimal("0.00")
        assert r2(result.mortgage_interest_tax_credit) == Decimal("2000.00")
        assert r2(result.annual_tax_liability)      == Decimal("0.00")

    def test_ta05_negative_taxable_income_income_tax_zero(self) -> None:
        """
        TA-05: Costs exceed effective rent — taxable income is negative.

        Per CALCULATION_SPEC.md Step A-2 (updated): income_tax_gross uses
        MAX(0, taxable_rental_income) × rate. A rental loss does not attract
        income tax. income_tax_gross is zero.

        taxable_rental_income = 4000 - 5000 = -1000.00
        income_tax_gross      = MAX(0, -1000) × 0.40 = 0.00
        credit                = 8000 × 0.20 = 1600.00
        liability             = MAX(0, 0.00 - 1600.00) = 0.00

        Source: TEST_STRATEGY.md TA-05. CALCULATION_SPEC.md Step A-2.
        """
        result = calculate_individual_tax(
            effective_annual_rent=Decimal("4000.00"),
            letting_agent_annual=Decimal("5000.00"),
            annual_maintenance_reserve=Decimal("0.00"),
            landlord_insurance_annual=Decimal("0.00"),
            annual_service_charge=Decimal("0.00"),
            annual_ground_rent=Decimal("0.00"),
            annual_accountancy_cost=Decimal("0.00"),
            annual_mortgage_interest=Decimal("8000.00"),
            income_tax_band=IncomeTaxBand.HIGHER_RATE,
        )
        assert r2(result.taxable_rental_income)  == Decimal("-1000.00")
        assert r2(result.income_tax_gross)       == Decimal("0.00")
        assert r2(result.mortgage_interest_tax_credit) == Decimal("1600.00")
        assert r2(result.annual_tax_liability)   == Decimal("0.00")

    def test_ta06_leasehold_service_charge_ground_rent(self) -> None:
        """
        TA-06: E-06 leasehold inputs with service charge and ground rent.

        Service charge (1,200) and ground rent (150) are both deductible
        from taxable income for an individual landlord.

        effective=9807.30, letting=1224, maint=1800, insur=800,
        service=1200, ground=150, acct=0
        taxable = 9807.30 - 1224 - 1800 - 800 - 1200 - 150 = 4633.30
        gross   = 4633.30 × 0.40 = 1853.32
        credit  = 6412.50 × 0.20 = 1282.50
        liability = 1853.32 - 1282.50 = 570.82

        Source: ENGINE_CONTRACTS.md E-06. TEST_STRATEGY.md TA-06.
        """
        result = calculate_individual_tax(
            effective_annual_rent=Decimal("9807.30"),
            letting_agent_annual=Decimal("1224.00"),
            annual_maintenance_reserve=Decimal("1800.00"),
            landlord_insurance_annual=Decimal("800.00"),
            annual_service_charge=Decimal("1200.00"),
            annual_ground_rent=Decimal("150.00"),
            annual_accountancy_cost=Decimal("0.00"),
            annual_mortgage_interest=Decimal("6412.50"),
            income_tax_band=IncomeTaxBand.HIGHER_RATE,
        )
        assert r2(result.taxable_rental_income)        == Decimal("4633.30")
        assert r2(result.income_tax_gross)             == Decimal("1853.32")
        assert r2(result.mortgage_interest_tax_credit) == Decimal("1282.50")
        assert r2(result.annual_tax_liability)         == Decimal("570.82")
        assert result.section_24_applies is True

    def test_section_24_applies_true_with_mortgage(self) -> None:
        """
        section_24_applies is True when annual_mortgage_interest > 0.
        Source: CALCULATION_SPEC.md — section_24_applies Derived Flag.
        """
        result = calculate_individual_tax(
            **E01_INPUTS, income_tax_band=IncomeTaxBand.BASIC_RATE
        )
        assert result.section_24_applies is True

    def test_section_24_applies_false_cash_purchase(self) -> None:
        """
        section_24_applies is False for a cash-purchase individual landlord.
        annual_mortgage_interest = 0 means Section 24 has no applicable
        interest to restrict.
        Source: CALCULATION_SPEC.md — section_24_applies Derived Flag.
        """
        result = calculate_individual_tax(
            effective_annual_rent=Decimal("10961.10"),
            letting_agent_annual=Decimal("1368.00"),
            annual_maintenance_reserve=Decimal("2000.00"),
            landlord_insurance_annual=Decimal("800.00"),
            annual_service_charge=Decimal("0.00"),
            annual_ground_rent=Decimal("0.00"),
            annual_accountancy_cost=Decimal("0.00"),
            annual_mortgage_interest=Decimal("0.00"),   # cash purchase
            income_tax_band=IncomeTaxBand.BASIC_RATE,
        )
        assert result.section_24_applies is False

    def test_result_is_individual_tax_result(self) -> None:
        """Return type is IndividualTaxResult (a NamedTuple)."""
        result = calculate_individual_tax(
            **E01_INPUTS, income_tax_band=IncomeTaxBand.BASIC_RATE
        )
        assert isinstance(result, IndividualTaxResult)
        assert hasattr(result, "taxable_rental_income")
        assert hasattr(result, "income_tax_gross")
        assert hasattr(result, "mortgage_interest_tax_credit")
        assert hasattr(result, "annual_tax_liability")
        assert hasattr(result, "section_24_applies")

    def test_all_fields_are_decimal_except_flag(self) -> None:
        """All numeric fields are Decimal. section_24_applies is bool."""
        result = calculate_individual_tax(
            **E01_INPUTS, income_tax_band=IncomeTaxBand.BASIC_RATE
        )
        assert isinstance(result.taxable_rental_income,        Decimal)
        assert isinstance(result.income_tax_gross,             Decimal)
        assert isinstance(result.mortgage_interest_tax_credit, Decimal)
        assert isinstance(result.annual_tax_liability,         Decimal)
        assert isinstance(result.section_24_applies,           bool)
