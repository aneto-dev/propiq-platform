# PropIQ Platform — Canonical Domain Glossary

## Purpose

This document defines the canonical terminology used across the platform.

It is the authoritative reference for:

* frontend wording,
* backend calculations,
* API contracts,
* database naming,
* documentation,
* and future AI summaries.

The goal is to eliminate ambiguity and ensure all metrics have:

* explicit definitions,
* stable meaning,
* and consistent implementation.

---

# Core Principles

## Explicit Over Ambiguous

Metrics must clearly state:

* what is included,
* what is excluded,
* and how they are calculated.

---

## Historical Consistency

Definitions must not silently change over time.

If a calculation meaning changes:

* engine version increments,
* historical snapshots remain preserved.

---

# Income Terms

## Gross Annual Rent

### Platform Definition

The estimated monthly contractual rent multiplied by 12, before any deductions.

### Formula

gross_annual_rent = monthly_rent × 12

### Includes

* contractual tenant rent

### Excludes

* voids
* costs
* financing
* tax

### API Field

gross_annual_rent_gbp

---

## Effective Annual Rent

### Platform Definition

Gross annual rent adjusted for expected void periods.

### Formula

effective_annual_rent = gross_annual_rent × (1 - void_rate)

### Includes

* vacancy allowance

### Excludes

* operating costs
* financing
* tax

### API Field

effective_annual_rent_gbp

---

## Void Rate

### Platform Definition

The percentage of the year during which the property is assumed not to produce rental income.

### Notes

Void assumptions must:

* remain configurable,
* be versioned,
* and disclose their source.

### API Field

void_rate_percent

---

# Cost Terms

## Acquisition Costs

### Platform Definition

All one-time costs incurred to purchase and prepare the property.

### Includes

* SDLT
* legal fees
* survey
* refurbishment
* letting setup fees

### Excludes

* mortgage payments
* ongoing operating costs

### API Field

total_acquisition_cost_gbp

---

## Operating Costs

### Platform Definition

Recurring annual costs required to operate and maintain the property.

### Includes

* management fees
* maintenance reserve
* insurance
* service charges
* ground rent
* HMO licensing

### Excludes

* financing
* tax

### API Field

total_operating_costs_annual_gbp

---

## Maintenance Reserve

### Platform Definition

An annual reserve allowance for repairs and maintenance.

### Notes

Typically calculated as a configurable percentage of property value.

### API Field

maintenance_reserve_annual_gbp

---

# Yield & Return Terms

## Gross Yield

### Platform Definition

Gross annual rent expressed as a percentage of purchase price.

### Formula

gross_yield = (gross_annual_rent / purchase_price) × 100

### Notes

Gross yield is a headline comparison metric only and does not reflect real profitability.

### API Field

gross_yield_percent

---

## Net Yield

### Platform Definition

Effective annual rent minus operating costs, expressed as a percentage of purchase price.

### Formula

net_yield = ((effective_annual_rent - operating_costs) / purchase_price) × 100

### Excludes

* financing
* tax

### Notes

Net yield is intentionally:

* financing-neutral,
* tax-neutral,
* and suitable for fair comparison between deals.

### API Field

net_yield_percent

---

## Cash-on-Cash Return

### Platform Definition

Annual cash flow after financing and tax, expressed as a percentage of total cash invested.

### Formula

cash_on_cash_return = (annual_cash_flow / total_cash_deployed) × 100

### API Field

cash_on_cash_return_percent

---

## ROCE

### Platform Definition

Net operating income expressed as a percentage of total cash deployed.

### Formula

roce = (net_operating_income / total_cash_deployed) × 100

### Notes

ROCE is financing-neutral and tax-neutral.

### API Field

roce_percent

---

# Cash Flow Terms

## Net Operating Income (NOI)

### Platform Definition

Effective annual rent minus operating costs.

### Formula

noi = effective_annual_rent - operating_costs

### Excludes

* financing
* tax

### API Field

net_operating_income_gbp

---

## Annual Cash Flow

### Platform Definition

Cash remaining after:

* operating costs,
* financing costs,
* and estimated tax.

### Formula

annual_cash_flow = noi - mortgage_costs - tax

### API Field

annual_cash_flow_gbp

---

# Financing Terms

## Loan-to-Value (LTV)

### Platform Definition

Mortgage loan amount expressed as a percentage of purchase price.

### Formula

ltv = (loan_amount / purchase_price) × 100

### API Field

ltv_percent

---

## Interest Coverage Ratio (ICR)

### Platform Definition

Effective annual rent expressed as a percentage of stressed mortgage interest.

### Formula

icr = (effective_annual_rent / stressed_interest) × 100

### API Field

icr_percent

---

## Stress Test Rate

### Platform Definition

The hypothetical interest rate used during lender-style affordability testing.

### Notes

Stress test assumptions must:

* remain configurable,
* versioned,
* and historically auditable.

### API Field

stress_test_rate_percent

---

# Tax Terms

## Section 24

### Platform Definition

UK tax rules restricting mortgage interest relief for individual landlords.

### Notes

Section 24 applies to:

* individual landlords,
* but not limited companies.

### API Field

section_24_applies

---

# Snapshot Terms

## Calculation Snapshot

### Platform Definition

An immutable saved record containing:

* all inputs,
* assumptions,
* versions,
* calculations,
* and outputs

used at the time of analysis.

### Notes

Snapshots are never modified after creation.

Recalculations create new snapshots.

---

## Engine Version

### Platform Definition

The specific underwriting engine version used to generate an analysis.

### Purpose

Supports:

* historical reproducibility,
* auditability,
* and comparison between engine versions.
