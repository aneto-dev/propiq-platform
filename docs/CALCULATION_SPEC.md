# PropIQ Platform — Calculation Specification

## Purpose

This document defines the underwriting engine behaviour for the platform.

The engine must be:

* deterministic,
* explainable,
* versioned,
* testable,
* and historically reproducible.

AI models must never generate authoritative calculations.

---

# Calculation Principles

## Deterministic Outputs

The same inputs and assumptions must always produce the same outputs.

---

## Explicit Assumptions

All assumptions must:

* be visible,
* configurable,
* and versioned.

---

## Immutable Historical Analysis

Saved calculations are snapshots and must never silently change.

---

# High-Level Calculation Flow

## Step 1 — Validate Inputs

Validate:

* required fields,
* numeric ranges,
* enums,
* financing constraints,
* tax assumptions.

---

## Step 2 — Calculate Acquisition Costs

Includes:

* SDLT
* legal fees
* survey
* refurbishment
* setup costs

Outputs:

* total acquisition cost
* total cash deployed

---

## Step 3 — Calculate Financing

Includes:

* loan amount
* deposit
* mortgage payment
* stressed interest
* LTV

---

## Step 4 — Calculate Effective Rent

Apply:

* void allowance
* effective annual rent

---

## Step 5 — Calculate Operating Costs

Includes:

* management fees
* maintenance reserve
* insurance
* service charges
* ground rent
* HMO licensing

---

## Step 6 — Calculate NOI

Formula:
noi = effective_annual_rent - operating_costs

---

## Step 7 — Calculate Tax

Includes:

* Section 24 handling
* corporation tax handling
* investor type rules

---

## Step 8 — Calculate Cash Flow

Includes:

* mortgage costs
* estimated tax
* annual cash flow
* monthly cash flow

---

## Step 9 — Calculate Yields & Returns

Includes:

* gross yield
* net yield
* cash-on-cash return
* ROCE

---

## Step 10 — Calculate Stress Testing

Includes:

* stressed interest
* ICR
* affordability checks

---

## Step 11 — Generate Risk Flags

Potential flags:

* NEGATIVE_CASHFLOW
* LOW_ICR
* HIGH_LEVERAGE
* LOW_MARGIN_SAFETY
* HIGH_REFURB_RATIO

---

## Step 12 — Persist Snapshot

Snapshot must store:

* all inputs
* assumptions
* version IDs
* engine version
* outputs
* timestamp

Snapshots are immutable.

---

# Versioned Assumptions

The following must remain versioned:

* SDLT tables
* corporation tax rates
* stress test assumptions
* default void rates
* maintenance assumptions
* insurance assumptions

Configuration data is never overwritten.

---

# Recalculation Rules

## Original Analysis

Users must always be able to view the original snapshot.

---

## Recalculate With Latest Rates

Recalculation:

* uses latest assumptions,
* creates new snapshot,
* preserves historical version.

---

# Important Constraints

The platform:

* is not financial advice,
* does not predict future performance,
* does not guarantee profitability,
* and models deals under stated assumptions only.

Outputs are:

* estimates,
* projections,
* and scenario-based calculations.

---

---

# Formula Definitions

This section defines every formula used by the underwriting engine.

All monetary values are in GBP (£).
All rate inputs are expressed as percentages (e.g. 5.0 means 5%) and converted
to decimals inside formulas where shown.
All intermediate values are computed and stored at full precision.
Rounding to two decimal places is applied only at the point of display or
snapshot persistence — never during intermediate calculation steps.

Terminology used in all formulas matches DOMAIN_GLOSSARY.md exactly.

---

## F-01 — Gross Annual Rent

```
gross_annual_rent = monthly_rent × 12
```

Source: DOMAIN_GLOSSARY.md — Gross Annual Rent.

Simplification note: This formula assumes a single consistent monthly rent for
the full year. Rent reviews, mid-tenancy adjustments, and furnished-letting
premiums are not modelled in v1.0.

---

## F-02 — Void Rate Conversion

The void_rate_percent input is expressed as a percentage of the year (0–100).

```
void_rate_decimal = void_rate_percent / 100
```

This decimal is applied in F-03.

---

## F-03 — Effective Annual Rent

```
effective_annual_rent = gross_annual_rent × (1 - void_rate_decimal)
```

Source: DOMAIN_GLOSSARY.md — Effective Annual Rent.

Realism note: Void rate is applied to gross_annual_rent, not effective rent.
This correctly models the full revenue loss during vacant periods including
weeks when rent is contractually due but the property is empty.

---

## F-04 — Loan Amount

```
loan_amount = purchase_price - deposit_amount
```

---

## F-05 — Loan-to-Value (LTV)

```
ltv_percent = (loan_amount / purchase_price) × 100
```

Source: DOMAIN_GLOSSARY.md — Loan-to-Value.

---

## F-06 — Monthly Mortgage Payment

Two pathways based on mortgage_type.

### Interest-Only

```
monthly_mortgage_payment = (loan_amount × (mortgage_interest_rate / 100)) / 12
```

### Repayment (Standard Annuity)

```
r = (mortgage_interest_rate / 100) / 12
n = mortgage_term_years × 12

monthly_mortgage_payment = loan_amount × (r × (1 + r)^n) / ((1 + r)^n - 1)
```

Where r is the monthly interest rate and n is the total number of payments.

Edge case — zero interest rate: If mortgage_interest_rate = 0 (cash purchase
or data error), the repayment formula produces a divide-by-zero. Treat
mortgage_interest_rate = 0 as a cash purchase, set monthly_mortgage_payment = 0,
and apply the CASH_PURCHASE flag. Do not attempt to calculate the repayment
formula.

Simplification note: v1.0 calculates a single fixed monthly payment for the
full mortgage term. Variable-rate, tracker, and fixed-then-revert scenarios are
not modelled. This is disclosed to users.

---

## F-07 — Annual Mortgage Cost

```
annual_mortgage_cost = monthly_mortgage_payment × 12
```

---

## F-08 — Annual Mortgage Interest (for tax calculations)

This figure is required separately from total mortgage payments because it feeds
directly into the Section 24 tax credit and limited company deduction
calculations. It must not be conflated with annual_mortgage_cost (which for a
repayment mortgage includes capital repayment).

### Interest-Only

```
annual_mortgage_interest = loan_amount × (mortgage_interest_rate / 100)
```

### Repayment — Year 1 Interest Approximation

For a repayment mortgage, the interest portion reduces each year as capital is
repaid. In v1.0, only year 1 interest is calculated. Full amortisation
schedules are deferred to a future phase.

```
annual_mortgage_interest_year1 = monthly_mortgage_payment × 12 - annual_capital_repaid_year1
```

Where:

```
annual_capital_repaid_year1 = loan_amount - remaining_balance_after_12_payments
```

And remaining_balance_after_12_payments is computed from the standard annuity
balance formula:

```
remaining_balance_after_n_payments = loan_amount × ((1 + r)^n - (1 + r)^payments_made) / ((1 + r)^n - 1)
```

Simplification note: This is disclosed to users. For a repayment mortgage, the
displayed tax estimate is based on year 1 interest only and will overstate tax
relief in later years as the interest portion falls. Users are shown this
limitation.

---

## F-09 — Letting Agent Annual Cost

Letting agent fees are subject to VAT at the standard rate (20%). Residential
landlords cannot reclaim VAT. The VAT uplift is therefore a real cost and must
be included.

```
letting_agent_annual = gross_annual_rent × (letting_agent_fee_percent / 100) × 1.20
```

Realism note: The fee is applied to gross_annual_rent, not effective_annual_rent.
Most letting agent management contracts charge on rent due (i.e. the contractual
rent), not rent received. This is the more conservative and more common
contractual basis. Agreements that charge only on rent received would require
a per-deal override.

---

## F-10 — Annual Maintenance Reserve

```
annual_maintenance_reserve = purchase_price × (maintenance_reserve_percent / 100)
```

Simplification note: This is a smoothed annual reserve, not a prediction of
actual costs in any given year. Major capital items (boiler replacement, roof
repairs) are not separately modelled. Users are shown this limitation.

---

## F-11 — Total Annual Operating Costs

```
total_operating_costs_annual =
    letting_agent_annual
  + annual_maintenance_reserve
  + landlord_insurance_annual
  + annual_service_charge
  + annual_ground_rent
  + annual_accountancy_cost
```

Source: DOMAIN_GLOSSARY.md — Operating Costs.

All components are recurring annual costs. One-off acquisition costs (SDLT,
legal fees, refurbishment) are excluded from this total and tracked separately
under total_acquisition_cost_gbp.

---

## F-12 — Net Operating Income (NOI)

```
net_operating_income = effective_annual_rent - total_operating_costs_annual
```

Source: DOMAIN_GLOSSARY.md — Net Operating Income.

NOI is financing-neutral and tax-neutral. It represents the income-generating
performance of the asset independent of how it is financed or owned.

---

## F-13 — SDLT Calculation

SDLT is calculated using the banded rate structure applicable in England as at
the configuration version referenced by the deal snapshot.

### Base Calculation (all purchases)

SDLT is applied progressively across bands. The tax on each band is calculated
on the portion of the purchase price falling within that band only.

```
For each band where band_lower < purchase_price:
    taxable_in_band = MIN(purchase_price, band_upper) - band_lower
    tax_in_band = taxable_in_band × band_rate_decimal

sdlt_base = SUM(tax_in_band for all applicable bands)
```

### Additional Dwelling Surcharge

When is_additional_dwelling = true, a flat surcharge rate applies across the
entire purchase price. The surcharge is added on top of the banded base
calculation. It is not itself banded.

```
sdlt_surcharge = purchase_price × additional_dwelling_surcharge_rate_decimal
```

### Total SDLT

```
total_sdlt = sdlt_base + sdlt_surcharge
```

### SDLT Configuration (England, effective 1 April 2025)

These values are stored in the versioned configuration table. They must not be
hardcoded. The configuration version referenced by any deal snapshot must be
stored with the snapshot.

Standard residential bands (no surcharge):

| Band Lower  | Band Upper    | Rate |
|-------------|---------------|------|
| £0          | £125,000      | 0%   |
| £125,001    | £250,000      | 2%   |
| £250,001    | £925,000      | 5%   |
| £925,001    | £1,500,000    | 10%  |
| £1,500,001  | No upper limit| 12%  |

Additional dwelling surcharge rate: 3%

This surcharge rate and all band thresholds and rates are admin-configurable
and versioned. Any government change (e.g. Budget announcements) requires a new
configuration version with an effective_from date. Existing snapshots retain a
reference to the configuration version used at the time of calculation.

### Limited Company SDLT

Limited companies are subject to the same banded SDLT rates as individuals for
residential property. The additional dwelling surcharge applies in almost all
cases because a company can never qualify as a first-time buyer and is treated
as holding property if any connected person does.

The platform applies the surcharge by default when ownership_structure =
LIMITED_COMPANY and discloses this assumption. An override is available per deal
for exceptional circumstances, but the user must confirm it manually.

### Out-of-Scope SDLT Scenarios (v1.0)

The following SDLT scenarios are not supported in v1.0. If detected, a
validation error or prominent disclosure is shown:

* Multiple dwellings relief (MDR)
* Mixed-use property rates
* Linked transactions
* SDLT group relief
* Charities relief
* Scotland (LBTT) and Wales (LTT) — blocked at validation

### SDLT Output Structure

Each deal snapshot stores the full SDLT breakdown, not just the total.
This includes every band applied, the taxable amount in each band, the rate,
and the tax computed per band, plus the surcharge as a separate line.

---

## F-14 — Total Acquisition Cost

```
total_acquisition_cost = purchase_price + total_sdlt + purchase_legal_costs + refurbishment_cost
```

Source: DOMAIN_GLOSSARY.md — Acquisition Costs.

---

## F-15 — Total Cash Deployed

This is the investor's actual cash outlay. It is used as the denominator in
cash-on-cash return and ROCE calculations.

```
total_cash_deployed = deposit_amount + total_sdlt + purchase_legal_costs + refurbishment_cost
```

Note: The mortgage loan is excluded because it is not the investor's own cash.
Using total_cash_deployed rather than purchase_price as the denominator in
return calculations correctly reflects the leveraged nature of the investment.

Source: DOMAIN_GLOSSARY.md — Cash-on-Cash Return, ROCE.

---

## F-16 — Gross Yield

```
gross_yield_percent = (gross_annual_rent / purchase_price) × 100
```

Source: DOMAIN_GLOSSARY.md — Gross Yield.

Disclosure: Gross yield is a headline comparison metric only. It does not
reflect voids, costs, financing, or tax. The platform always shows net yield
alongside gross yield and never presents gross yield as a measure of
profitability.

---

## F-17 — Net Yield

```
net_yield_percent = (net_operating_income / purchase_price) × 100
```

Source: DOMAIN_GLOSSARY.md — Net Yield.
Decision reference: ADR-004.

Net yield is financing-neutral and tax-neutral by design. This allows fair
comparison between deals regardless of financing structure or investor tax
position. Financing and tax impacts are shown separately in cash flow outputs.

---

## F-18 — ROCE

```
roce_percent = (net_operating_income / total_cash_deployed) × 100
```

Source: DOMAIN_GLOSSARY.md — ROCE.

ROCE is financing-neutral and tax-neutral. It differs from net yield in that
it uses total_cash_deployed (investor's actual cash) as the denominator rather
than purchase_price.

---

## F-19 — Annual Cash Flow

```
annual_cash_flow = net_operating_income - annual_mortgage_cost - annual_tax_liability
```

Source: DOMAIN_GLOSSARY.md — Annual Cash Flow.

The tax pathway (annual_tax_liability) differs by ownership_structure. See
Section: Tax Calculations.

---

## F-20 — Monthly Cash Flow

```
monthly_cash_flow = annual_cash_flow / 12
```

---

## F-21 — Cash-on-Cash Return

```
cash_on_cash_return_percent = (annual_cash_flow / total_cash_deployed) × 100
```

Source: DOMAIN_GLOSSARY.md — Cash-on-Cash Return.

Annual cash flow is post-financing and post-tax. This is the most meaningful
return metric for a leveraged investor assessing actual cash generated relative
to cash committed.

---

## F-22 — ICR Stress Test

### Stressed Annual Interest

```
stressed_annual_interest = loan_amount × (stress_test_rate_percent / 100)
```

The stress test rate is applied to the loan amount as an interest-only figure,
regardless of the actual mortgage type. This reflects how lenders calculate
BTL affordability: they assess whether rent covers the interest at a
hypothetical higher rate, not actual payments.

### ICR

```
icr_percent = (effective_annual_rent / stressed_annual_interest) × 100
```

Source: DOMAIN_GLOSSARY.md — Interest Coverage Ratio.

### ICR Thresholds

These thresholds are stored in the versioned configuration table and are
admin-configurable. They reflect typical lender requirements and must not be
treated as universal rules — individual lenders vary.

| Investor Type                             | Minimum ICR Threshold |
|-------------------------------------------|-----------------------|
| Individual — basic rate taxpayer          | 125%                  |
| Individual — higher or additional rate    | 145%                  |
| Limited company                           | 125%                  |

The higher threshold for higher/additional rate individual taxpayers reflects
lender requirements introduced in response to the Section 24 restriction.
Many lenders apply 145% to personal-name borrowers who declare higher-rate
tax status.

Disclosure: ICR thresholds are indicative. Lenders apply their own criteria,
which vary and change. The platform does not constitute a lending decision.

---

---

# Tax Calculations

Tax calculations branch based on ownership_structure. The two supported
pathways in v1.0 are INDIVIDUAL and LIMITED_COMPANY.

Both pathways use annual_mortgage_interest (F-08) rather than
annual_mortgage_cost (F-07). Only the interest component has tax implications.
For a repayment mortgage the capital repayment element is never tax-deductible.

---

## Tax Pathway A — Individual Ownership and Section 24

### Legislative basis

Section 24 of the Finance (No. 2) Act 2015, fully effective from April 2020,
restricts mortgage interest relief for individual landlords. Mortgage interest
is no longer deductible as an expense from rental income. Instead, a 20% tax
credit is applied against the resulting tax liability.

This affects higher-rate (40%) and additional-rate (45%) taxpayers materially.
For a basic-rate (20%) taxpayer the net effect is broadly neutral in most
cases, though not always.

### Step A-1 — Taxable Rental Income

Under Section 24, taxable rental income is calculated without any mortgage
interest deduction.

```
taxable_rental_income =
    effective_annual_rent
  - letting_agent_annual
  - annual_maintenance_reserve
  - landlord_insurance_annual
  - annual_service_charge
  - annual_ground_rent
  - annual_accountancy_cost
```

Note: annual_mortgage_interest is deliberately excluded from this deduction.
This is the defining feature of Section 24 and must not be altered.

### Step A-2 — Income Tax on Rental Income

```
income_tax_on_rental = taxable_rental_income × income_tax_rate_decimal
```

Where income_tax_rate_decimal is:
* 0.20 for BASIC_RATE
* 0.40 for HIGHER_RATE
* 0.45 for ADDITIONAL_RATE

### Step A-3 — Mortgage Interest Tax Credit

```
mortgage_interest_tax_credit = annual_mortgage_interest × 0.20
```

The credit is always 20% regardless of the investor's marginal rate. This is
the mechanism of the Section 24 restriction: higher-rate taxpayers pay 40% tax
on rental profits but only receive a 20% credit on the mortgage interest.

### Step A-4 — Net Tax Liability

```
annual_tax_liability = MAX(0, income_tax_on_rental - mortgage_interest_tax_credit)
```

The floor of zero prevents a negative tax liability. In practice, on low-yield
properties with high mortgage costs, taxable_rental_income may already be small
or negative before the credit is applied, though the credit cannot create a
refund.

### Simplification disclosures — Individual pathway

The following simplifications are applied in v1.0 and must be disclosed to
users:

1. The calculation assumes all rental income falls within the investor's
declared tax band. In reality, rental income is added to all other income
(salary, dividends, pension) which may push some or all rental income into a
higher band.

2. The personal allowance (£12,570 for 2025/26) is not modelled. If the
investor has unused personal allowance that could shelter some rental income,
the actual tax liability would be lower than calculated here. The platform is
intentionally conservative.

3. National Insurance is not applicable to rental income for most individual
landlords and is not modelled.

4. For repayment mortgages, only year 1 interest is used. Tax estimates become
less accurate in later years as the interest component reduces.

5. This is an estimate. The investor must take advice from a qualified tax
adviser for accurate personal tax planning.

---

## Tax Pathway B — Limited Company Ownership

### Legislative basis

A limited company holding UK residential property pays Corporation Tax on
rental profits. Mortgage interest is fully deductible as a business expense
for a limited company. The Section 24 restriction does not apply.

### Corporation Tax Rate Configuration (2025/26)

Corporation tax rates are stored in the versioned configuration table and must
not be hardcoded.

| Profit Band          | Rate |
|----------------------|------|
| £0 – £50,000         | 19%  |
| £50,001 – £250,000   | Marginal relief |
| Above £250,000       | 25%  |

Marginal relief between £50,000 and £250,000 is a tapering mechanism defined
by HMRC. Full marginal relief calculation is not implemented in v1.0 (see
simplification note below).

### Step B-1 — Taxable Company Profit

```
taxable_company_profit =
    effective_annual_rent
  - letting_agent_annual
  - annual_maintenance_reserve
  - landlord_insurance_annual
  - annual_service_charge
  - annual_ground_rent
  - annual_accountancy_cost
  - annual_mortgage_interest
```

Note: annual_mortgage_interest IS deducted here. This is the key difference
from the individual pathway.

### Step B-2 — Corporation Tax

```
If taxable_company_profit <= 0:
    corporation_tax = 0

Else if taxable_company_profit <= 50,000:
    corporation_tax = taxable_company_profit × 0.19

Else if taxable_company_profit > 250,000:
    corporation_tax = taxable_company_profit × 0.25

Else (marginal relief band £50,001 – £250,000):
    corporation_tax = taxable_company_profit × 0.25 - marginal_relief_fraction
```

Marginal relief fraction (simplified for v1.0):

```
    marginal_relief_fraction = (250,000 - taxable_company_profit) × (3 / 200)
```

This formula matches HMRC's marginal relief calculation for a standalone
company with no associated companies and no augmented profits from other sources.

Simplification note: For single-property SPVs (the most common Ltd Co BTL
structure) taxable profits will almost always fall below £50,000, making the
19% small profits rate applicable in almost all Phase 1 use cases. The
marginal relief formula is included for completeness but the platform discloses
that it applies a simplified version for companies with associated companies or
non-property income.

### Step B-3 — Net Tax Liability

```
annual_tax_liability = MAX(0, corporation_tax)
```

### Step B-4 — Post-Corporation-Tax Profit (retained in company)

```
post_tax_retained_profit = taxable_company_profit - annual_tax_liability
```

This is the profit available within the company before any extraction.

### Simplification disclosures — Limited company pathway

1. The calculation models company-level tax only. Profit extraction — whether
as salary (PAYE and National Insurance apply), dividends (dividend tax applies
at 8.75%, 33.75%, or 39.35% depending on band), or director's loan — incurs
further personal tax. The effective total tax burden of a Ltd Co structure
depends heavily on extraction strategy and the investor's personal income.
This is not modelled in v1.0 and is prominently disclosed.

2. ATED (Annual Tax on Enveloped Dwellings) applies to companies owning
residential property worth over £500,000 used as a dwelling. ATED is not
calculated in v1.0. A risk flag is generated when purchase_price > £500,000
and ownership_structure = LIMITED_COMPANY.

3. Associated company rules can reduce the profit thresholds for the small
profits rate. A company with one associated company has its thresholds halved
(to £25,000 and £125,000). This is not modelled. Users with multiple
associated companies must take accountancy advice.

4. The corporation tax configuration version used for the calculation is
stored with the snapshot.

---

---

# Input Definitions

This section defines every input to the underwriting engine: its type,
constraints, default value where applicable, whether it is required or
optional, and whether it is user-editable per deal or admin-configurable only.

Required inputs have no default. The engine must refuse to calculate if they
are absent or invalid.

Optional inputs have a default value drawn from the versioned assumption
configuration. Users may override these per deal. Any override is stored
in the snapshot alongside the default value that was in effect, so the
deviation is auditable.

---

## Required Inputs

| Field                        | Type    | Constraints                                      | Notes                                                    |
|------------------------------|---------|--------------------------------------------------|----------------------------------------------------------|
| purchase_price               | Decimal | > 0                                              | Agreed purchase price, not asking price or valuation     |
| monthly_rent                 | Decimal | > 0                                              | User-estimated achievable rent, not listed asking rent   |
| deposit_amount               | Decimal | > 0, < purchase_price, >= 15% of purchase_price | Actual cash deposit; not expressed as a percentage       |
| mortgage_interest_rate       | Decimal | >= 0, <= 20                                      | Actual rate, not SVR; 0 treated as cash purchase         |
| mortgage_term_years          | Integer | 5 – 35                                           |                                                          |
| mortgage_type                | Enum    | INTEREST_ONLY, REPAYMENT                         |                                                          |
| ownership_structure          | Enum    | INDIVIDUAL, LIMITED_COMPANY                      | LLP not supported in v1.0                                |
| income_tax_band              | Enum    | BASIC_RATE, HIGHER_RATE, ADDITIONAL_RATE         | Required when ownership_structure = INDIVIDUAL           |
| is_additional_dwelling       | Boolean | —                                                | Default true; almost always true for investment purchases |
| property_type                | Enum    | RESIDENTIAL_SINGLE_LET                           | Only supported value in v1.0                             |
| tenure                       | Enum    | FREEHOLD, LEASEHOLD                              |                                                          |
| property_country             | Enum    | ENGLAND                                          | Only supported value in v1.0                             |
| postcode                     | String  | Valid UK postcode format                         | Used for audit trail; area intelligence in Phase 3       |

---

## Optional Inputs — User-Editable Per Deal

These default to the values in the active assumption configuration version.
When a user overrides any of these, both the override and the default are stored
in the snapshot.

| Field                          | Default Source        | Notes                                                                    |
|--------------------------------|-----------------------|--------------------------------------------------------------------------|
| void_rate_percent              | Assumption config     | See assumption defaults section                                          |
| letting_agent_fee_percent      | Assumption config     | Set to 0 for self-managed properties; the platform does not default to 0 |
| maintenance_reserve_percent    | Assumption config     | Applied to purchase_price                                                |
| landlord_insurance_annual      | Assumption config     | Fixed £ amount, not percentage                                           |
| purchase_legal_costs           | Assumption config     | Conveyancing and survey fees, excluding SDLT                             |
| refurbishment_cost             | 0                     | One-off pre-let cost; zero default is acceptable but shown to user       |
| annual_service_charge          | 0                     | Required for leasehold; 0 for freehold                                   |
| annual_ground_rent             | 0                     | Required for leasehold; 0 for freehold                                   |
| annual_accountancy_cost        | Assumption config     | Varies by ownership_structure                                            |

---

## Assumption Configuration Defaults

These defaults are stored in the versioned assumption configuration table.
They are admin-configurable and must never be hardcoded. Every deal snapshot
stores a reference to the configuration version active at the time of
calculation.

| Parameter                            | v1.0 Default               | Rationale and Source                                                                                                                                                          |
|--------------------------------------|----------------------------|-------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| void_rate_percent                    | 3.85% (approx 2 weeks/yr)  | Derived from ARLA Propertymark data. 2 weeks void per year = 2/52 = 3.846%. Expressed as a percentage of annual rent for formula consistency.                                 |
| letting_agent_fee_percent            | 10.0%                      | Mid-market full management fee in England. VAT uplift (×1.20) applied in F-09. Range in market: 8–15% + VAT.                                                                  |
| maintenance_reserve_percent          | 1.0%                       | Standard UK property management rule of thumb: 1% of property value per year. Does not cover major capital expenditure.                                                       |
| landlord_insurance_annual            | £800                       | Mid-market estimate for a standard single-let residential property in England. Range: £300–£1,500 depending on property size, location, and coverage level.                   |
| purchase_legal_costs                 | £2,500                     | Estimate covering conveyancing (£1,000–£2,000) and RICS Level 2 homebuyer survey (£300–£600). Complex or leasehold purchases will be higher.                                  |
| annual_accountancy_cost (INDIVIDUAL) | £0                         | Individual landlords often manage their own self-assessment. Users who use an accountant should override this.                                                                 |
| annual_accountancy_cost (LTD CO)     | £1,200                     | Estimate for a simple SPV with annual accounts preparation and corporation tax return. Range: £800–£2,500 depending on complexity and accountant.                              |
| stress_test_rate_percent             | 5.5%                       | Conservative floor rate reflecting typical BTL lender stress test levels. Range used by lenders: 5.5%–7.0%. This is a configurable assumption, not a regulatory requirement. |
| icr_threshold_basic_rate             | 125%                       | Standard BTL lender threshold for basic-rate taxpayers. Derived from PRA guidance and common lender practice.                                                                 |
| icr_threshold_higher_rate            | 145%                       | Higher threshold applied by many lenders for higher and additional rate taxpayers, reflecting Section 24 impact on affordability.                                              |

---

---

# Validation Rules

Validation runs before any calculation begins.

A validation failure must return a structured error identifying the field and
the rule that failed. The engine must not proceed to calculation with invalid
inputs. Validation errors are never silently ignored.

Rules marked HARD produce errors that block calculation.
Rules marked WARN produce warnings that are shown to users but do not block
calculation.

| Code | Field                      | Condition                                              | Severity | Message                                                                                                                |
|------|----------------------------|--------------------------------------------------------|----------|------------------------------------------------------------------------------------------------------------------------|
| V-01 | purchase_price             | <= 0                                                   | HARD     | Purchase price must be greater than zero.                                                                              |
| V-02 | purchase_price             | < 10,000                                               | WARN     | Purchase price is unusually low. Please verify.                                                                        |
| V-03 | purchase_price             | > 10,000,000                                           | WARN     | Purchase price is unusually high. Please verify.                                                                       |
| V-04 | monthly_rent               | <= 0                                                   | HARD     | Monthly rent estimate must be greater than zero.                                                                       |
| V-05 | deposit_amount             | <= 0                                                   | HARD     | Deposit amount must be greater than zero.                                                                              |
| V-06 | deposit_amount             | >= purchase_price                                      | HARD     | Deposit cannot equal or exceed the purchase price.                                                                     |
| V-07 | deposit_amount             | < purchase_price × 0.15                                | HARD     | Deposit is below 15% of the purchase price. BTL mortgages are not available below this threshold.                      |
| V-08 | deposit_amount             | < purchase_price × 0.25                                | WARN     | Deposit is below 25%. Most BTL lenders require a minimum 25% deposit. Product availability may be limited.            |
| V-09 | mortgage_interest_rate     | < 0                                                    | HARD     | Mortgage interest rate cannot be negative.                                                                             |
| V-10 | mortgage_interest_rate     | = 0                                                    | WARN     | Interest rate is zero. This will be treated as a cash purchase. Mortgage calculations will not apply.                 |
| V-11 | mortgage_interest_rate     | < 3.0 and > 0                                          | WARN     | Interest rate is unusually low for a BTL mortgage. Please verify.                                                     |
| V-12 | mortgage_interest_rate     | > 10.0                                                 | WARN     | Interest rate is unusually high. Please verify.                                                                        |
| V-13 | mortgage_term_years        | < 5 or > 35                                            | HARD     | Mortgage term must be between 5 and 35 years.                                                                          |
| V-14 | ownership_structure        | = LLP                                                  | HARD     | LLP ownership structure is not supported in v1.0.                                                                      |
| V-15 | property_type              | != RESIDENTIAL_SINGLE_LET                              | HARD     | Only residential single-let properties are supported in v1.0.                                                          |
| V-16 | property_country           | != ENGLAND                                             | HARD     | Only England is supported in v1.0. Scotland, Wales, and Northern Ireland use different transaction tax regimes.        |
| V-17 | income_tax_band            | null when ownership_structure = INDIVIDUAL             | HARD     | Income tax band is required for individual ownership.                                                                  |
| V-18 | void_rate_percent          | < 0 or > 100                                           | HARD     | Void rate must be between 0% and 100%.                                                                                 |
| V-19 | void_rate_percent          | = 0                                                    | WARN     | Void rate is set to zero. Consider whether this is realistic — most properties experience some vacancy between tenancies. |
| V-20 | letting_agent_fee_percent  | > 25                                                   | WARN     | Letting agent fee above 25% is unusually high. Please verify.                                                          |
| V-21 | annual_service_charge      | null when tenure = LEASEHOLD                           | HARD     | Annual service charge must be provided for leasehold properties. Enter 0 if genuinely not applicable.                 |
| V-22 | annual_ground_rent         | null when tenure = LEASEHOLD                           | HARD     | Annual ground rent must be provided for leasehold properties. Enter 0 if genuinely not applicable.                    |
| V-23 | annual_ground_rent         | > 250 and tenure = LEASEHOLD                           | WARN     | Ground rent above £250/year. Pre-2022 leases above this threshold may affect mortgage availability. Take legal advice. |
| V-24 | maintenance_reserve_percent| > 5.0                                                  | WARN     | Maintenance reserve above 5% of purchase price is unusually high. Please verify.                                       |
| V-25 | refurbishment_cost         | = 0                                                    | WARN     | No refurbishment cost entered. If works are required before letting, ensure this is accounted for.                     |

---

---

# Risk Flag Definitions

Risk flags are generated after all calculations are complete.

Each flag has a code, a severity, a trigger condition expressed against
calculated outputs, and a user-facing message.

Flags are informational. They do not block the user from saving a deal.
They must be prominently displayed on the deal summary and stored in the
snapshot.

Severities:

* HIGH — materially affects deal viability; requires user attention
* MEDIUM — warrants review; may affect financing or returns
* INFO — contextual disclosure; no immediate action required

---

| Code                   | Severity | Trigger Condition                                                                                   | User-Facing Message                                                                                                                                                                    |
|------------------------|----------|-----------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| NEGATIVE_CASHFLOW      | HIGH     | annual_cash_flow < 0                                                                                | This deal produces negative cash flow after all costs, mortgage payments, and estimated tax. You will need to fund a monthly shortfall from other income.                              |
| NEGATIVE_NOI           | HIGH     | net_operating_income < 0                                                                            | Operating costs exceed effective rental income before any financing costs. This deal does not cover its own running costs.                                                             |
| LOW_GROSS_YIELD        | HIGH     | gross_yield_percent < 4.0                                                                           | Gross yield is below 4%. After costs and financing this deal is likely to produce negative cash flow in most financing scenarios.                                                      |
| LOW_NET_YIELD          | MEDIUM   | net_yield_percent < 3.0                                                                             | Net yield is below 3%. The asset return after operating costs is low relative to financing costs in the current rate environment.                                                      |
| LOW_ICR_BASIC          | HIGH     | icr_percent < 125 and ownership_structure in [INDIVIDUAL, LIMITED_COMPANY]                          | Interest coverage ratio is below 125%. This deal is unlikely to meet standard BTL mortgage affordability requirements at the stress test rate.                                        |
| LOW_ICR_HIGHER_RATE    | HIGH     | icr_percent < 145 and icr_percent >= 125 and income_tax_band in [HIGHER_RATE, ADDITIONAL_RATE]     | ICR is below 145%. Higher-rate taxpayers face stricter lender requirements. Mortgage approval may be difficult even though the basic 125% threshold is met.                           |
| HIGH_LEVERAGE          | HIGH     | ltv_percent > 75                                                                                    | LTV is above 75%. Most BTL lenders cap lending at 75% LTV. Product availability will be significantly limited above this threshold.                                                   |
| HIGH_LEVERAGE_EXTREME  | HIGH     | ltv_percent > 85                                                                                    | LTV is above 85%. BTL mortgages at this leverage level are extremely rare. The deal as structured is unlikely to be mortgageable.                                                     |
| LOW_MARGIN_SAFETY      | MEDIUM   | (annual_cash_flow / gross_annual_rent) < 0.05 and annual_cash_flow >= 0                            | Cash flow margin is very thin — less than 5% of gross rent. A modest increase in costs, void periods, or interest rates could push this deal into negative cash flow.                |
| HIGH_REFURB_RATIO      | MEDIUM   | refurbishment_cost > purchase_price × 0.10                                                         | Refurbishment cost exceeds 10% of purchase price. Verify that the refurbishment budget is realistic and that the post-refurbishment rental value supports the projected figures.      |
| SECTION_24_IMPACT      | HIGH     | ownership_structure = INDIVIDUAL and income_tax_band in [HIGHER_RATE, ADDITIONAL_RATE]             | As a higher or additional rate taxpayer, Section 24 significantly restricts your mortgage interest relief. Your post-tax returns are materially lower than pre-tax figures suggest. Consider whether a limited company structure is appropriate — take professional tax advice. |
| ATED_WARNING           | MEDIUM   | ownership_structure = LIMITED_COMPANY and purchase_price > 500,000                                 | Properties held in a limited company worth over £500,000 may be subject to ATED (Annual Tax on Enveloped Dwellings). This is not calculated here. Take professional advice before proceeding. |
| LEASEHOLD_SHORT_LEASE  | HIGH     | tenure = LEASEHOLD and lease_years_remaining is not null and lease_years_remaining < 80            | Lease length is below 80 years. Mortgage availability on short-lease properties is significantly restricted. Lease extension costs should be factored into the acquisition budget.    |
| CASH_FLOW_PRE_TAX_ONLY | MEDIUM   | pre_tax_cash_flow >= 0 and annual_cash_flow < 0                                                    | This deal is cash flow positive before tax but negative after estimated tax. The tax liability — particularly under Section 24 — has a material impact on this deal.                  |
| LTD_EXTRACTION_UNDISCLOSED | INFO  | ownership_structure = LIMITED_COMPANY                                                               | Post-corporation-tax profit retained in the company will incur further personal tax on extraction. The total effective tax burden depends on your extraction strategy. Take accountancy advice. |
| RENT_UNVERIFIED        | INFO     | always (monthly_rent is always user-entered in v1.0)                                               | Rental income is based on your estimate and has not been independently verified. Obtain rental appraisals from at least two local letting agents before relying on this figure.        |

---

---

# Snapshot Versioning Behaviour

This section defines how snapshots are created, what they store, and how
versioning is enforced. This implements ADR-002 and ADR-005.

---

## What a Snapshot Is

A calculation snapshot is an immutable record of a single complete analysis.

It is not a summary. It is the full state of the calculation at the time it
was run: every input provided by the user, every default assumption that was
active, the exact version of the engine and configuration that was used, every
intermediate value, and every output.

A snapshot can be used to exactly reproduce the calculation that produced it,
independent of any subsequent changes to the engine, tax rates, or assumptions.

---

## Snapshot Contents

Every snapshot must store the following categories of data:

### Identity

* snapshot_id — unique identifier (UUID)
* created_at — UTC timestamp of creation
* deal_id — reference to the parent deal record
* user_id — reference to the user who triggered the calculation

### Version References

* engine_version — the semantic version of the underwriting engine (e.g. 1.0.0)
* assumption_config_version_id — foreign key to the assumption configuration
  record active at the time of calculation
* sdlt_config_version_id — foreign key to the SDLT rate table record active
  at the time of calculation
* corporation_tax_config_version_id — foreign key to the corporation tax rate
  record active at the time of calculation

All version references are foreign keys to append-only configuration tables.
Configuration records are never updated or deleted.

### Inputs — User-Provided

All required and optional inputs provided by the user, stored at their actual
values used in this calculation.

### Inputs — Defaults Applied

For every optional input where the user did not provide a value, both the
default that was applied and the assumption_config_version_id it came from
are stored.

For every optional input where the user provided an override, the override
value and the default that was in effect are both stored so the deviation
is auditable.

### Intermediate Values

All intermediate calculated values are stored. This includes:

* gross_annual_rent
* void_rate_decimal applied
* effective_annual_rent
* letting_agent_annual (including VAT uplift applied)
* annual_maintenance_reserve
* total_operating_costs_annual
* net_operating_income
* loan_amount
* ltv_percent
* monthly_mortgage_payment
* annual_mortgage_cost
* annual_mortgage_interest
* taxable_rental_income (or taxable_company_profit)
* income_tax_on_rental (or corporation_tax)
* mortgage_interest_tax_credit (INDIVIDUAL pathway only)
* annual_tax_liability
* annual_cash_flow
* monthly_cash_flow
* SDLT band-by-band breakdown
* sdlt_surcharge
* total_sdlt
* total_acquisition_cost
* total_cash_deployed
* stressed_annual_interest
* icr_percent

### Outputs

All user-facing output values.

### Risk Flags

All risk flags generated for this snapshot, including their codes, severities,
and the trigger condition values that caused them.

---

## Immutability Enforcement

Snapshots are append-only. Once written, no field in a snapshot record may
be updated or deleted.

Application-level enforcement: the snapshot write service must not expose any
update or delete operation.

Database-level enforcement: the snapshots table must not have update or delete
permissions granted to the application database user. Inserts only.

If a calculation needs to be corrected or updated — for example because an
input was wrong — a new snapshot is created. The original snapshot remains
visible to the user with a label indicating it has been superseded.

---

## Recalculation Behaviour

A recalculation does not modify the original snapshot.

Recalculation creates a new snapshot against the same deal_id, using either:

* the same assumption_config_version_id as the original (to reproduce the
  original result), or
* the latest active configuration version (to see the deal modelled under
  current assumptions).

Both the original and recalculated snapshots are stored and accessible.

The deal record holds a reference to the latest snapshot for display purposes,
but all previous snapshots remain accessible for comparison and audit.

---

## Configuration Table Versioning

Assumption configuration tables, SDLT rate tables, and tax rate tables all
follow the same versioning pattern:

* Records are insert-only. No updates. No deletes.
* Each record has an effective_from date.
* The engine always uses the record where effective_from is the most recent
  date that is on or before the calculation date.
* When a new rate or assumption takes effect, a new record is inserted with
  the appropriate effective_from date. The previous record remains in place.

This ensures that a historical snapshot can always be reproduced by re-running
the engine with the same inputs and the same configuration version.

---

## Engine Versioning

The engine version is a semantic version string (MAJOR.MINOR.PATCH) stored in
the engine codebase and embedded in every snapshot at calculation time.

MAJOR increment: a change to formula logic or calculation methodology that
would produce different outputs for the same inputs. This constitutes a
breaking change to the calculation specification.

MINOR increment: addition of new calculations, inputs, or outputs that do not
change existing formula results.

PATCH increment: bug fixes, performance improvements, or non-functional changes.

A MAJOR version increment requires a documented entry in DECISIONS.md explaining
the change and its rationale.

---

---

# Disclosed Limitations

These limitations apply to all calculations produced by v1.0 of the engine.
They must be visible to users on every deal analysis output and stored in the
snapshot.

1. Rental valuations are user-provided and are not independently verified by
this platform. Obtain rental appraisals from local letting agents before
relying on this estimate.

2. Tax calculations are estimates based on the investor's declared tax band.
Rental income is added to total income, which may affect the applicable rate.
Take advice from a qualified accountant or tax adviser.

3. For individual ownership, the tax estimate does not model use of the
personal allowance, which may reduce actual tax liability. The platform is
intentionally conservative.

4. For limited company ownership, the calculation models company-level tax
only. Profit extraction (salary, dividends, director's loan) incurs additional
personal tax. The effective total tax burden depends on individual circumstances.

5. For repayment mortgages, the tax calculation uses year 1 interest only.
Tax estimates become less accurate in later years.

6. Mortgage availability is not guaranteed. ICR results are indicative. Lenders
apply their own criteria, which change. This platform does not constitute a
mortgage offer or decision in principle.

7. Capital growth is not modelled. Calculations assume no appreciation in
property value. Total investment return including capital growth is not shown.

8. The platform covers England only. Scotland uses Land and Buildings
Transaction Tax (LBTT). Wales uses Land Transaction Tax (LTT).

9. ATED (Annual Tax on Enveloped Dwellings) is not calculated for limited
company purchases above £500,000. A risk flag is shown.

10. This platform does not constitute financial, mortgage, tax, or legal advice.

---

---

# Future Extensibility Notes

The following areas are intentionally simplified or deferred in v1.0. They are
recorded here so the engine can evolve to accommodate them without requiring
structural changes to the specification.

---

## Calculations with a high probability of regulatory change

| Area                          | Change Risk | Trigger                                              |
|-------------------------------|-------------|------------------------------------------------------|
| SDLT bands and rates          | HIGH        | Budget announcements; has changed multiple times since 2020 |
| Additional dwelling surcharge | HIGH        | Budget announcements                                 |
| Corporation tax rates         | MEDIUM      | Finance Acts                                         |
| Section 24 mechanism          | MEDIUM      | Further reform possible; politically complex to reverse |
| EPC minimum standards         | HIGH        | Proposed minimum EPC C for new BTL lettings; not yet law |
| HMO licensing requirements    | HIGH        | Council-specific; changes frequently                 |
| Ground rent rules             | MEDIUM      | Leasehold Reform Act 2022 ongoing                    |
| ICR thresholds                | MEDIUM      | PRA guidance and lender policy changes               |

Any change in the above areas requires a new versioned configuration entry
and, if formula logic changes, a MAJOR engine version increment.

---

## Deferred calculation features

* Full mortgage amortisation schedule (year-by-year capital and interest split)
* Multi-scenario comparison (e.g. individual vs Ltd Co for the same deal)
* Sensitivity tables (cash flow impact of interest rate changes, void changes)
* HMO per-room income modelling
* Bridging finance and development finance scenarios
* Leasehold extension cost modelling
* Corporation tax marginal relief for companies with associated companies
* Profit extraction modelling for Ltd Co structures
* SDLT multiple dwellings relief
* Scotland (LBTT) and Wales (LTT) transaction tax calculations

Each of these is an additive extension. The calculation flow structure defined
in this specification is designed to accommodate them without requiring
existing formula definitions to be altered.
