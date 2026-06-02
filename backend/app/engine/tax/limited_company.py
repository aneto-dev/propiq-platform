"""
Tax Pathway B — Limited company ownership and Corporation Tax.

Implements the Corporation Tax calculation for a limited company SPV.
Mortgage interest is fully deductible as a business expense. Section 24
does not apply.

Legislative basis: Finance Act 2023. Small profits rate 19% on profits
up to £50,000. Main rate 25% above £250,000. Marginal relief between
£50,001 and £250,000. Rates effective from 1 April 2023.

The Corporation Tax configuration (rates, thresholds, marginal relief
fraction) is always drawn from versioned configuration. Values are never
hardcoded in this module.

Architecture:
    CALCULATION_SPEC.md — Tax Pathway B, Steps B-1 through B-4.
"""

from __future__ import annotations

from decimal import Decimal
from typing import NamedTuple


class LimitedCompanyTaxResult(NamedTuple):
    """
    Complete result of the limited company (Pathway B) tax calculation.

    All intermediates required by EngineIntermediates and the snapshot
    persistence layer are included.

    section_24_applies is always False for Pathway B. Section 24 does
    not apply to limited companies. Included so the orchestrator can
    populate EngineIntermediates.section_24_applies without branching.

    post_tax_retained_profit is the profit available within the company
    before any extraction (salary, dividends, or director's loan). Profit
    extraction incurs further personal tax — not modelled in v1.0.
    """

    taxable_company_profit: Decimal
    corporation_tax_gross: Decimal
    annual_tax_liability: Decimal
    post_tax_retained_profit: Decimal
    section_24_applies: bool  # always False


def calculate_limited_company_tax(
    effective_annual_rent: Decimal,
    letting_agent_annual: Decimal,
    annual_maintenance_reserve: Decimal,
    landlord_insurance_annual: Decimal,
    annual_service_charge: Decimal,
    annual_ground_rent: Decimal,
    annual_accountancy_cost: Decimal,
    annual_mortgage_interest: Decimal,
    small_profits_rate: Decimal,
    small_profits_upper_threshold: Decimal,
    main_rate: Decimal,
    main_rate_lower_threshold: Decimal,
    marginal_relief_numerator: int,
    marginal_relief_denominator: int,
) -> LimitedCompanyTaxResult:
    """
    Calculate annual Corporation Tax liability for a limited company landlord.

    Steps:

    B-1. Taxable company profit:
         effective_annual_rent minus all operating costs INCLUDING mortgage
         interest. Mortgage interest is fully deductible for a limited
         company — this is the key difference from Pathway A.

    B-2. Corporation Tax (banded, from configuration):
         If profit <= 0:          corporation_tax = 0
         If profit <= small_upper: corporation_tax = profit × small_rate
         If profit > main_lower:   corporation_tax = profit × main_rate
         Else (marginal relief):
           corporation_tax = profit × main_rate
                           − (main_lower − profit)
                             × (marginal_relief_numerator / marginal_relief_denominator)

    B-3. Net tax liability:
         MAX(0, corporation_tax) — floor at zero.

    B-4. Post-tax retained profit:
         taxable_company_profit − annual_tax_liability

    Source: CALCULATION_SPEC.md Tax Pathway B, Steps B-1 through B-4.

    Args:
        effective_annual_rent:          Output of F-03.
        letting_agent_annual:           Output of F-09.
        annual_maintenance_reserve:     Output of F-10.
        landlord_insurance_annual:      From EngineInput.
        annual_service_charge:          From EngineInput.
        annual_ground_rent:             From EngineInput.
        annual_accountancy_cost:        From EngineInput.
        annual_mortgage_interest:       Output of F-08. Zero for cash purchase.
        small_profits_rate:             From CorporationTaxConfig (e.g. 0.19).
        small_profits_upper_threshold:  From CorporationTaxConfig (e.g. 50000).
        main_rate:                      From CorporationTaxConfig (e.g. 0.25).
        main_rate_lower_threshold:      From CorporationTaxConfig (e.g. 250000).
        marginal_relief_numerator:      From CorporationTaxConfig (e.g. 3).
        marginal_relief_denominator:    From CorporationTaxConfig (e.g. 200).

    Returns:
        LimitedCompanyTaxResult with all four intermediates and
        section_24_applies = False.
    """
    # Step B-1 — Taxable company profit (mortgage interest IS deductible)
    taxable_company_profit = (
        effective_annual_rent
        - letting_agent_annual
        - annual_maintenance_reserve
        - landlord_insurance_annual
        - annual_service_charge
        - annual_ground_rent
        - annual_accountancy_cost
        - annual_mortgage_interest
    )

    # Step B-2 — Corporation Tax (banded, from configuration — never hardcoded)
    mr_num_d   = Decimal(marginal_relief_numerator)
    mr_den_d   = Decimal(marginal_relief_denominator)
    mr_fraction = mr_num_d / mr_den_d

    if taxable_company_profit <= Decimal("0"):
        corporation_tax_gross = Decimal("0")
    elif taxable_company_profit <= small_profits_upper_threshold:
        corporation_tax_gross = taxable_company_profit * small_profits_rate
    elif taxable_company_profit > main_rate_lower_threshold:
        corporation_tax_gross = taxable_company_profit * main_rate
    else:
        # Marginal relief band
        gross = taxable_company_profit * main_rate
        relief = (main_rate_lower_threshold - taxable_company_profit) * mr_fraction
        corporation_tax_gross = gross - relief

    # Step B-3 — Net tax liability (floor at zero)
    annual_tax_liability = max(Decimal("0"), corporation_tax_gross)

    # Step B-4 — Post-tax retained profit
    post_tax_retained_profit = taxable_company_profit - annual_tax_liability

    return LimitedCompanyTaxResult(
        taxable_company_profit=taxable_company_profit,
        corporation_tax_gross=corporation_tax_gross,
        annual_tax_liability=annual_tax_liability,
        post_tax_retained_profit=post_tax_retained_profit,
        section_24_applies=False,
    )
