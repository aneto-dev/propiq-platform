"""
Tax Pathway A — Individual ownership with Section 24 restriction.

Implements the four-step Section 24 calculation for individual landlords.
All arithmetic uses Decimal. float is never introduced.

Legislative basis: Section 24 of the Finance (No. 2) Act 2015, fully
effective April 2020. Mortgage interest is no longer deductible from rental
income. A 20% tax credit is applied to the resulting liability instead.

Architecture:
    CALCULATION_SPEC.md — Tax Pathway A, Steps A-1 through A-4.
    CALCULATION_SPEC.md — section_24_applies Derived Flag.
"""

from __future__ import annotations

from decimal import Decimal
from typing import NamedTuple

from app.domain.enums import IncomeTaxBand


class IndividualTaxResult(NamedTuple):
    """
    Complete result of the individual (Pathway A) tax calculation.

    All four intermediates required by EngineIntermediates and the
    snapshot persistence layer are included. The orchestrator maps
    these directly into EngineIntermediates fields.

    section_24_applies is True when annual_mortgage_interest > 0.
    It is False for a cash-purchase individual landlord.
    """

    taxable_rental_income: Decimal
    income_tax_gross: Decimal
    mortgage_interest_tax_credit: Decimal
    annual_tax_liability: Decimal
    section_24_applies: bool


# Mapping from IncomeTaxBand enum to rate as a Decimal fraction.
# Stored at module level — never hardcoded in the calculation function.
_INCOME_TAX_RATES: dict[IncomeTaxBand, Decimal] = {
    IncomeTaxBand.BASIC_RATE:       Decimal("0.20"),
    IncomeTaxBand.HIGHER_RATE:      Decimal("0.40"),
    IncomeTaxBand.ADDITIONAL_RATE:  Decimal("0.45"),
}

_S24_CREDIT_RATE = Decimal("0.20")  # always 20% per Finance (No. 2) Act 2015


def calculate_individual_tax(
    effective_annual_rent: Decimal,
    letting_agent_annual: Decimal,
    annual_maintenance_reserve: Decimal,
    landlord_insurance_annual: Decimal,
    annual_service_charge: Decimal,
    annual_ground_rent: Decimal,
    annual_accountancy_cost: Decimal,
    annual_mortgage_interest: Decimal,
    income_tax_band: IncomeTaxBand,
) -> IndividualTaxResult:
    """
    Calculate annual tax liability for an individual landlord under Section 24.

    Steps:

    A-1. Taxable rental income:
         effective_annual_rent minus all operating costs EXCEPT mortgage
         interest. This is the defining feature of Section 24 — mortgage
         interest is no longer a deductible expense.

    A-2. Income tax on rental:
         MAX(0, taxable_rental_income) × rate
         The floor reflects HMRC rules: income tax applies only to profits.
         When taxable_rental_income is negative, income_tax_gross is zero.

    A-3. Mortgage interest tax credit:
         annual_mortgage_interest × 0.20
         The credit is always 20% regardless of the investor's marginal rate.
         This is the mechanism of Section 24: higher-rate taxpayers pay 40%
         tax on rental profits but receive only a 20% credit on the interest.

    A-4. Net tax liability:
         MAX(0, income_tax_gross − mortgage_interest_tax_credit)
         The floor prevents a negative liability. The credit cannot create
         a tax refund.

    Source: CALCULATION_SPEC.md Tax Pathway A, Steps A-1 through A-4
    (updated to include MAX(0, ...) floor on taxable income at Step A-2).

    Args:
        effective_annual_rent:      Output of F-03.
        letting_agent_annual:       Output of F-09.
        annual_maintenance_reserve: Output of F-10.
        landlord_insurance_annual:  From EngineInput (user or config default).
        annual_service_charge:      From EngineInput (0 for freehold).
        annual_ground_rent:         From EngineInput (0 for freehold).
        annual_accountancy_cost:    From EngineInput (user or config default).
        annual_mortgage_interest:   Output of F-08. Zero for cash purchase.
        income_tax_band:            From EngineInput. Must be BASIC_RATE,
                                    HIGHER_RATE, or ADDITIONAL_RATE.

    Returns:
        IndividualTaxResult with all four intermediates and section_24_applies.
    """
    # Step A-1 — Taxable rental income (mortgage interest deliberately excluded)
    taxable_rental_income = (
        effective_annual_rent
        - letting_agent_annual
        - annual_maintenance_reserve
        - landlord_insurance_annual
        - annual_service_charge
        - annual_ground_rent
        - annual_accountancy_cost
    )

    # Step A-2 — Income tax on rental (floored at zero — no tax on a loss)
    rate = _INCOME_TAX_RATES[income_tax_band]
    income_tax_gross = max(Decimal("0"), taxable_rental_income) * rate

    # Step A-3 — Mortgage interest tax credit (always 20%)
    mortgage_interest_tax_credit = annual_mortgage_interest * _S24_CREDIT_RATE

    # Step A-4 — Net tax liability (floored at zero — credit cannot create refund)
    annual_tax_liability = max(
        Decimal("0"),
        income_tax_gross - mortgage_interest_tax_credit,
    )

    # Derived flag — True when there is mortgage interest to restrict
    section_24_applies = annual_mortgage_interest > Decimal("0")

    return IndividualTaxResult(
        taxable_rental_income=taxable_rental_income,
        income_tax_gross=income_tax_gross,
        mortgage_interest_tax_credit=mortgage_interest_tax_credit,
        annual_tax_liability=annual_tax_liability,
        section_24_applies=section_24_applies,
    )
