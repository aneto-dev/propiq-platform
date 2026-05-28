# PropIQ Platform — Engine Contracts

## Purpose

This document is the executable specification for the PropIQ underwriting
engine. It defines every contract the engine must honour, every guarantee it
must provide, and every canonical scenario it must produce correctly.

This document has a specific authority: it is the source of truth for test
authorship. Every test written against the engine must be traceable to a
contract or scenario defined here. No test may assert a value that conflicts
with this document without a documented revision.

This document contains no code, no framework dependencies, no ORM references,
no HTTP concerns, and no persistence logic. It defines computation contracts
only.

All terminology matches DOMAIN_GLOSSARY.md exactly.
All formulas are sourced from CALCULATION_SPEC.md.
All structural decisions reflect ENGINE_ARCHITECTURE.md.

---

## Document Status

Specification version: 1.0
Engine version covered: 1.0.0
Applicable tax year: 2025/26
SDLT configuration: England, effective 1 April 2025
Last verified: All scenario arithmetic manually computed and cross-checked
               before inclusion.

---

---

# Part 1 — EngineInput Contract

`EngineInput` is the complete set of values passed to the engine. By the time
it reaches the engine, every field is populated. There are no nulls to resolve
inside the engine. Default resolution is the responsibility of the calculation
service layer.

---

## 1.1 — Required Fields

These fields have no default. If any is absent or invalid, the validation
pipeline returns a HARD failure and calculation does not proceed.

| Field                  | Type              | Constraints                                             |
|------------------------|-------------------|---------------------------------------------------------|
| purchase_price         | Decimal           | > 0                                                     |
| monthly_rent           | Decimal           | > 0                                                     |
| deposit_amount         | Decimal           | > 0, < purchase_price, >= purchase_price × 0.15        |
| mortgage_interest_rate | Decimal           | >= 0, <= 20.0 (0 treated as cash purchase)              |
| mortgage_term_years    | Integer           | 5 to 35 inclusive                                       |
| mortgage_type          | MortgageType      | INTEREST_ONLY or REPAYMENT                              |
| ownership_structure    | OwnershipStructure| INDIVIDUAL or LIMITED_COMPANY                           |
| income_tax_band        | IncomeTaxBand     | Required if INDIVIDUAL. BASIC_RATE, HIGHER_RATE, or ADDITIONAL_RATE |
| is_additional_dwelling | Boolean           | No constraint. Defaults to true at service layer.       |
| property_type          | PropertyType      | RESIDENTIAL_SINGLE_LET (only supported value in v1.0)  |
| tenure                 | Tenure            | FREEHOLD or LEASEHOLD                                   |
| property_country       | PropertyCountry   | ENGLAND (only supported value in v1.0)                  |
| postcode               | String            | Valid UK postcode format                                |

---

## 1.2 — Optional Fields (always populated before engine entry)

These fields are populated with user overrides or config defaults by the
calculation service before `engine.run()` is called. The engine treats them
as present and valued.

| Field                       | Type    | Notes                                                      |
|-----------------------------|---------|------------------------------------------------------------|
| void_rate_percent           | Decimal | 0.0 to 100.0                                               |
| letting_agent_fee_percent   | Decimal | 0.0 to 25.0 (WARN above 25)                                |
| maintenance_reserve_percent | Decimal | 0.0 to 5.0 (WARN above 5.0)                                |
| landlord_insurance_annual   | Decimal | >= 0                                                       |
| purchase_legal_costs        | Decimal | >= 0                                                       |
| refurbishment_cost          | Decimal | >= 0 (WARN if 0)                                           |
| annual_service_charge       | Decimal | >= 0. Required non-null if LEASEHOLD.                      |
| annual_ground_rent          | Decimal | >= 0. Required non-null if LEASEHOLD.                      |
| annual_accountancy_cost     | Decimal | >= 0                                                       |
| lease_years_remaining       | Integer | Optional. Nullable even after default resolution.          |

---

## 1.3 — Enum Definitions

```
MortgageType:
    INTEREST_ONLY
    REPAYMENT

OwnershipStructure:
    INDIVIDUAL
    LIMITED_COMPANY

IncomeTaxBand:
    BASIC_RATE       (effective rate: 20%)
    HIGHER_RATE      (effective rate: 40%)
    ADDITIONAL_RATE  (effective rate: 45%)

PropertyType:
    RESIDENTIAL_SINGLE_LET

Tenure:
    FREEHOLD
    LEASEHOLD

PropertyCountry:
    ENGLAND
```

---

---

# Part 2 — EngineConfig Contract

`EngineConfig` contains all versioned configuration values the engine needs
at calculation time. It carries no database identifiers, no effective dates,
and no metadata. Those are held alongside `EngineConfig` by the calculation
service and written to the snapshot separately.

---

## 2.1 — SDLT Configuration

```
SDLTConfig:
    bands: List[SDLTBand]           — ordered list, ascending by band_lower
    additional_dwelling_surcharge_rate: Decimal   — e.g. 0.03 for 3%

SDLTBand:
    band_lower: Decimal             — lower bound of band (inclusive)
    band_upper: Decimal | None      — upper bound (None for top band)
    rate: Decimal                   — e.g. 0.02 for 2%
```

v1.0 reference values (England, effective 1 April 2025):

```
bands = [
    SDLTBand(band_lower=0,         band_upper=125_000,  rate=0.00),
    SDLTBand(band_lower=125_000,   band_upper=250_000,  rate=0.02),
    SDLTBand(band_lower=250_000,   band_upper=925_000,  rate=0.05),
    SDLTBand(band_lower=925_000,   band_upper=1_500_000,rate=0.10),
    SDLTBand(band_lower=1_500_000, band_upper=None,     rate=0.12),
]
additional_dwelling_surcharge_rate = 0.03
```

---

## 2.2 — Corporation Tax Configuration

```
CorporationTaxConfig:
    small_profits_rate: Decimal             — e.g. 0.19
    small_profits_upper_threshold: Decimal  — e.g. 50_000
    main_rate: Decimal                      — e.g. 0.25
    main_rate_lower_threshold: Decimal      — e.g. 250_000
    marginal_relief_numerator: Integer      — e.g. 3
    marginal_relief_denominator: Integer    — e.g. 200
```

v1.0 reference values (2025/26):

```
small_profits_rate = 0.19
small_profits_upper_threshold = 50_000
main_rate = 0.25
main_rate_lower_threshold = 250_000
marginal_relief_numerator = 3
marginal_relief_denominator = 200
```

---

## 2.3 — Assumption Configuration

```
AssumptionConfig:
    void_rate_percent_default: Decimal          — e.g. 3.85
    letting_agent_fee_percent_default: Decimal  — e.g. 10.0
    maintenance_reserve_percent_default: Decimal— e.g. 1.0
    landlord_insurance_annual_default: Decimal  — e.g. 800.00
    purchase_legal_costs_default: Decimal       — e.g. 2_500.00
    accountancy_cost_individual_default: Decimal— e.g. 0.00
    accountancy_cost_ltd_default: Decimal       — e.g. 1_200.00
    stress_test_rate_percent: Decimal           — e.g. 5.5
    icr_threshold_basic_rate_percent: Decimal   — e.g. 125.0
    icr_threshold_higher_rate_percent: Decimal  — e.g. 145.0
    letting_agent_vat_rate_percent: Decimal     — e.g. 20.0
```

---

---

# Part 3 — EngineResult Contract

`EngineResult` is returned on successful calculation (validation passes,
no engine error). It contains three sub-structures.

```
EngineResult:
    intermediates: EngineIntermediates
    outputs: EngineOutputs
    risk_flags: List[RiskFlag]
    validation_warnings: List[ValidationWarning]
```

`EngineResult` contains no timestamps, no snapshot IDs, no database
references, and no version IDs. Those are assigned by the persistence layer.

---

## 3.1 — EngineOutputs

User-facing metrics. Field names match DOMAIN_GLOSSARY.md API field names
exactly. All monetary values in GBP. All percentages as Decimal (e.g. 5.70
means 5.70%).

```
EngineOutputs:
    gross_annual_rent_gbp: Decimal
    effective_annual_rent_gbp: Decimal
    total_operating_costs_annual_gbp: Decimal
    net_operating_income_gbp: Decimal
    annual_mortgage_cost_gbp: Decimal
    annual_tax_liability_gbp: Decimal
    annual_cash_flow_gbp: Decimal
    monthly_cash_flow_gbp: Decimal
    gross_yield_percent: Decimal
    net_yield_percent: Decimal
    roce_percent: Decimal
    cash_on_cash_return_percent: Decimal
    ltv_percent: Decimal
    icr_percent: Decimal | None     — None when cash purchase (loan = 0)
    total_sdlt_gbp: Decimal
    total_acquisition_cost_gbp: Decimal
    total_cash_deployed_gbp: Decimal
```

---

## 3.2 — EngineIntermediates

All calculated values produced during the pipeline. Required for snapshot
persistence and auditability. Not all fields are displayed to users.

```
EngineIntermediates:
    void_rate_decimal_applied: Decimal
    gross_annual_rent_gbp: Decimal
    effective_annual_rent_gbp: Decimal
    loan_amount_gbp: Decimal
    ltv_percent: Decimal
    monthly_mortgage_payment_gbp: Decimal
    annual_mortgage_cost_gbp: Decimal
    annual_mortgage_interest_gbp: Decimal
    letting_agent_annual_gbp: Decimal
    letting_agent_vat_rate_applied: Decimal
    annual_maintenance_reserve_gbp: Decimal
    total_operating_costs_annual_gbp: Decimal
    net_operating_income_gbp: Decimal
    sdlt_band_breakdown: List[SDLTBandResult]
    sdlt_base_gbp: Decimal
    sdlt_surcharge_gbp: Decimal
    sdlt_surcharge_rate_applied: Decimal
    total_sdlt_gbp: Decimal
    total_acquisition_cost_gbp: Decimal
    total_cash_deployed_gbp: Decimal
    stressed_annual_interest_gbp: Decimal
    stress_test_rate_applied_percent: Decimal
    taxable_income_or_profit_gbp: Decimal
    income_tax_gross_gbp: Decimal | None        — INDIVIDUAL pathway only
    mortgage_interest_tax_credit_gbp: Decimal | None  — INDIVIDUAL only
    corporation_tax_gross_gbp: Decimal | None   — LIMITED_COMPANY only
    annual_tax_liability_gbp: Decimal
    pre_tax_annual_cash_flow_gbp: Decimal
    section_24_applies: Boolean

SDLTBandResult:
    band_lower: Decimal
    band_upper: Decimal | None
    rate: Decimal
    taxable_in_band: Decimal
    tax_in_band: Decimal
```

---

---

# Part 4 — ValidationResult Contract

Returned in place of `EngineResult` when HARD validation rules fail.

```
ValidationResult:
    is_valid: Boolean
    hard_errors: List[ValidationError]
    warnings: List[ValidationWarning]

ValidationError:
    rule_code: String    — e.g. "V-07"
    field: String        — the input field that triggered the rule
    message: String      — user-facing message from CALCULATION_SPEC.md

ValidationWarning:
    rule_code: String
    field: String
    message: String
```

When `is_valid = false`, the engine returns `ValidationResult` and does not
produce any `EngineResult`. Calculation stops at validation.

When `is_valid = true`, the engine proceeds. Any `warnings` present in the
`ValidationResult` are carried forward and included in the final `EngineResult`
as `validation_warnings`.

---

---

# Part 5 — RiskFlag Contract

```
RiskFlag:
    code: String           — e.g. "NEGATIVE_CASHFLOW"
    severity: FlagSeverity — HIGH, MEDIUM, or INFO
    triggered_by_field: String   — the field whose value caused the flag
    triggered_by_value: String   — the value at trigger time (as string)
    message: String        — user-facing message from CALCULATION_SPEC.md

FlagSeverity:
    HIGH    — materially affects deal viability
    MEDIUM  — warrants review
    INFO    — contextual disclosure
```

Risk flags are generated after all calculations are complete. They are
informational. They do not block snapshot creation or deal saving.

The `triggered_by_value` is always stored as a string representation of the
value at trigger time (e.g. "132.86" for an ICR value). This ensures the
snapshot contains a human-readable record of why each flag was triggered,
independent of the output field format at the time of display.

---

---

# Part 6 — EngineError Contract

Returned when an unexpected failure occurs inside the engine after validation
passes. The engine must never raise unhandled exceptions to the caller.

```
EngineError:
    error_code: String   — e.g. "DIVIDE_BY_ZERO", "UNEXPECTED_NONE"
    detail: String       — sanitised description, no stack trace
    engine_version: String
```

The following conditions must be handled inside the engine as defined
scenarios, not as error conditions:

| Condition                         | Handling                                              |
|-----------------------------------|-------------------------------------------------------|
| mortgage_interest_rate = 0        | Cash purchase; set loan = 0, skip mortgage calcs      |
| taxable_income_or_profit <= 0     | Tax liability = 0; no error                           |
| annual_cash_flow < 0              | Permitted result; NEGATIVE_CASHFLOW flag triggered    |
| net_operating_income < 0          | Permitted result; NEGATIVE_NOI flag triggered         |
| total_cash_deployed = 0           | roce_percent and cash_on_cash_return_percent = None   |
| loan_amount = 0 (cash purchase)   | icr_percent = None; ICR flags not evaluated           |

---

---

# Part 7 — Decimal Precision and Rounding Rules

These rules are determinism-critical. Deviations produce incorrect test results
and break historical reproducibility.

---

## 7.1 — Working Precision

All intermediate calculations are performed using decimal arithmetic with a
minimum working precision of 10 significant decimal places.

Python implementation: `decimal.Decimal` with `decimal.getcontext().prec = 10`
or higher. `float` must never be used for any monetary or percentage value.

---

## 7.2 — Rounding Point

Rounding to 2 decimal places occurs ONLY at the following points:
- When values are written into the `EngineOutputs` structure
- When values are written into the `EngineIntermediates` structure

Rounding must NOT occur during intermediate steps. A value rounded partway
through the pipeline and then used in subsequent calculations introduces
compounding errors that are invisible to callers and impossible to audit.

---

## 7.3 — Rounding Mode

All rounding uses ROUND_HALF_UP (conventional rounding). This is the mode
expected by financial calculations and matches HMRC published examples for
SDLT and tax computations.

---

## 7.4 — Percentage Display

Percentage outputs (yield, ICR, LTV, CoC, ROCE) are expressed as the
percentage value, not as a decimal fraction, in both `EngineOutputs` and
`EngineIntermediates`. For example, a gross yield of 5.70% is stored as
`Decimal("5.70")`, not `Decimal("0.057")`.

---

## 7.5 — The Canonical Precision Rule (stated once)

> Compute at full precision. Round only when persisting or displaying.
> Never use the rounded value as the input to a subsequent calculation.

---

---

# Part 8 — Formula Dependency Map

This map defines which inputs each formula depends on. It is the authoritative
reference for understanding calculation order and for verifying that the
orchestration sequence in ENGINE_ARCHITECTURE.md Part 6 is complete.

Each formula lists only its direct inputs. Derived values produced by earlier
formulas are shown as intermediates.

```
F-01  gross_annual_rent
      ← monthly_rent

F-02  void_rate_decimal
      ← void_rate_percent

F-03  effective_annual_rent
      ← gross_annual_rent (F-01)
      ← void_rate_decimal (F-02)

F-04  loan_amount
      ← purchase_price
      ← deposit_amount

F-05  ltv_percent
      ← loan_amount (F-04)
      ← purchase_price

F-06  monthly_mortgage_payment
      ← loan_amount (F-04)
      ← mortgage_interest_rate
      ← mortgage_term_years
      ← mortgage_type

F-07  annual_mortgage_cost
      ← monthly_mortgage_payment (F-06)

F-08  annual_mortgage_interest
      ← loan_amount (F-04)
      ← mortgage_interest_rate
      ← mortgage_type
      ← monthly_mortgage_payment (F-06)  [repayment path only]

F-09  letting_agent_annual
      ← gross_annual_rent (F-01)
      ← letting_agent_fee_percent
      ← letting_agent_vat_rate_percent [from config]

F-10  annual_maintenance_reserve
      ← purchase_price
      ← maintenance_reserve_percent

F-11  total_operating_costs_annual
      ← letting_agent_annual (F-09)
      ← annual_maintenance_reserve (F-10)
      ← landlord_insurance_annual
      ← annual_service_charge
      ← annual_ground_rent
      ← annual_accountancy_cost

F-12  net_operating_income
      ← effective_annual_rent (F-03)
      ← total_operating_costs_annual (F-11)

F-13  sdlt_result
      ← purchase_price
      ← is_additional_dwelling
      ← sdlt_bands [from config]
      ← additional_dwelling_surcharge_rate [from config]

F-14  total_acquisition_cost
      ← purchase_price
      ← total_sdlt (F-13)
      ← purchase_legal_costs
      ← refurbishment_cost

F-15  total_cash_deployed
      ← deposit_amount
      ← total_sdlt (F-13)
      ← purchase_legal_costs
      ← refurbishment_cost

F-16  gross_yield_percent
      ← gross_annual_rent (F-01)
      ← purchase_price

F-17  net_yield_percent
      ← net_operating_income (F-12)
      ← purchase_price

F-18  roce_percent
      ← net_operating_income (F-12)
      ← total_cash_deployed (F-15)

TAX-A  annual_tax_liability [INDIVIDUAL]
       ← effective_annual_rent (F-03)
       ← letting_agent_annual (F-09)
       ← annual_maintenance_reserve (F-10)
       ← landlord_insurance_annual
       ← annual_service_charge
       ← annual_ground_rent
       ← annual_accountancy_cost
       ← annual_mortgage_interest (F-08)
       ← income_tax_band

TAX-B  annual_tax_liability [LIMITED_COMPANY]
       ← effective_annual_rent (F-03)
       ← letting_agent_annual (F-09)
       ← annual_maintenance_reserve (F-10)
       ← landlord_insurance_annual
       ← annual_service_charge
       ← annual_ground_rent
       ← annual_accountancy_cost
       ← annual_mortgage_interest (F-08)
       ← corp_tax_config [from config]

F-19  annual_cash_flow
      ← net_operating_income (F-12)
      ← annual_mortgage_cost (F-07)
      ← annual_tax_liability (TAX-A or TAX-B)

F-20  monthly_cash_flow
      ← annual_cash_flow (F-19)

F-21  cash_on_cash_return_percent
      ← annual_cash_flow (F-19)
      ← total_cash_deployed (F-15)

F-22  icr_percent
      ← effective_annual_rent (F-03)
      ← loan_amount (F-04)
      ← stress_test_rate_percent [from config]

pre_tax_annual_cash_flow [intermediate only]
      ← net_operating_income (F-12)
      ← annual_mortgage_cost (F-07)
```

---

---

# Part 9 — Deterministic Execution Guarantees

These are the contractual guarantees the engine provides to all callers.

---

## G-1 — Identical inputs produce identical outputs

`engine.run(input_A, config_A) == engine.run(input_A, config_A)` is always
true, regardless of when the calls are made, what other calls have been made,
or what process or thread executes them.

---

## G-2 — No internal state between calls

The engine holds no mutable state. Each call is fully independent. The result
of one call cannot affect the result of any other call.

---

## G-3 — No system clock reads

The engine never calls any time or date function. Timestamps in the result
are the caller's responsibility. Two identical calls made at different times
produce identical `EngineResult` values.

---

## G-4 — No I/O

The engine never reads from or writes to a database, file, network socket, or
any external resource. All values it needs are passed explicitly as arguments.

---

## G-5 — No random values

The engine never calls any random number generator or uses any
non-deterministic data source.

---

## G-6 — Decimal arithmetic throughout

All monetary and percentage computations use decimal arithmetic. Float is never
used. This ensures platform-independent reproducibility and eliminates
accumulation of floating-point rounding errors.

---

## G-7 — Calculation order is fixed

The orchestration sequence defined in ENGINE_ARCHITECTURE.md Part 6 is
executed in the stated order without variation. No step may be reordered,
skipped, or parallelised. The sequence is the specification.

---

## G-8 — Configuration is fully injected before entry

The engine receives all configuration values as explicit arguments in
`EngineConfig`. It does not access any external configuration source. Changing
the configuration injected changes the result; the engine itself does not change.

---

---

# Part 10 — Engine Version Contract

```
Engine version: 1.0.0
Encoded as: MAJOR.MINOR.PATCH semantic version string
Stored as: constant inside the engine module
```

**MAJOR increment:** Formula logic or methodology change that produces
different outputs for the same inputs. Requires a documented entry in
DECISIONS.md. Existing snapshots remain valid under their original version.

**MINOR increment:** Addition of new calculation steps, new output fields, or
new risk flags. Does not alter any existing output value.

**PATCH increment:** Bug fix, refactoring, or non-functional change.

The version string is embedded in every snapshot at calculation time. It is
the permanent record of which formula logic produced the result. It must be a
constant — never derived, never read from a file.

---

---

# Part 11 — Canonical Reference Scenarios

These scenarios are the primary regression test suite for the underwriting
engine. All expected values have been computed by hand from the formulas in
CALCULATION_SPEC.md and cross-checked independently before inclusion.

A test implementation is correct if and only if it produces the expected
outputs for each scenario. Any deviation from these values is either a
calculation bug or an undocumented change to a formula that requires a MAJOR
engine version increment.

All monetary values are in GBP. All percentages are in percent form
(e.g. 5.70, not 0.057). All values are given to 2 decimal places as they
would appear in `EngineOutputs` and `EngineIntermediates` after rounding.

The assumption configuration used for all scenarios unless stated otherwise:

```
REFERENCE CONFIG (v1.0 defaults):
  void_rate_percent:              3.85
  letting_agent_fee_percent:      10.00
  letting_agent_vat_rate_percent: 20.00
  maintenance_reserve_percent:    1.00
  landlord_insurance_annual:      800.00
  purchase_legal_costs:           2500.00
  accountancy_cost_individual:    0.00
  accountancy_cost_ltd:           1200.00
  stress_test_rate_percent:       5.50
  icr_threshold_basic_rate:       125.00
  icr_threshold_higher_rate:      145.00
  additional_dwelling_surcharge:  0.03

SDLT BANDS (England, 1 April 2025):
  0 – 125,000:     0%
  125,001 – 250,000: 2%
  250,001 – 925,000: 5%
  925,001 – 1,500,000: 10%
  1,500,001+:      12%
```

---

## E-01 — Standard BTL, Basic-Rate Taxpayer, All Defaults

**Purpose:** Baseline scenario. Standard single-let residential purchase,
individual ownership, basic-rate taxpayer, interest-only mortgage, all
assumption defaults applied, no overrides. Demonstrates that a 5.70% gross
yield property at 75% LTV produces negative cash flow after accounting for
realistic costs.

### Inputs

```
purchase_price:           200,000.00
monthly_rent:             950.00
deposit_amount:           50,000.00
mortgage_interest_rate:   4.75
mortgage_term_years:      25
mortgage_type:            INTEREST_ONLY
ownership_structure:      INDIVIDUAL
income_tax_band:          BASIC_RATE
is_additional_dwelling:   true
property_type:            RESIDENTIAL_SINGLE_LET
tenure:                   FREEHOLD
property_country:         ENGLAND
postcode:                 NG1 1AA

All optional inputs: REFERENCE CONFIG defaults
refurbishment_cost:       0.00
annual_service_charge:    0.00
annual_ground_rent:       0.00
```

### Expected Intermediates

```
void_rate_decimal_applied:      0.0385
gross_annual_rent_gbp:          11,400.00
effective_annual_rent_gbp:      10,961.10
loan_amount_gbp:                150,000.00
ltv_percent:                    75.00
monthly_mortgage_payment_gbp:   593.75
annual_mortgage_cost_gbp:       7,125.00
annual_mortgage_interest_gbp:   7,125.00
letting_agent_annual_gbp:       1,368.00
letting_agent_vat_rate_applied: 20.00
annual_maintenance_reserve_gbp: 2,000.00
total_operating_costs_annual:   4,168.00
net_operating_income_gbp:       6,793.10
sdlt_band_breakdown:
  Band 0–125,000:   taxable=125,000.00  rate=0%  tax=0.00
  Band 125–250,000: taxable=75,000.00   rate=2%  tax=1,500.00
sdlt_base_gbp:                  1,500.00
sdlt_surcharge_gbp:             6,000.00
sdlt_surcharge_rate_applied:    0.03
total_sdlt_gbp:                 7,500.00
total_acquisition_cost_gbp:     210,000.00
total_cash_deployed_gbp:        60,000.00
stressed_annual_interest_gbp:   8,250.00
stress_test_rate_applied:       5.50
taxable_income_or_profit_gbp:   6,793.10
income_tax_gross_gbp:           1,358.62
mortgage_interest_tax_credit:   1,425.00
corporation_tax_gross_gbp:      null
annual_tax_liability_gbp:       0.00
pre_tax_annual_cash_flow_gbp:   -331.90
section_24_applies:             true
```

Note on tax liability: income_tax_gross (1,358.62) minus credit (1,425.00)
= -66.38. MAX(0, -66.38) = 0.00. The credit fully offsets the tax liability
because the basic-rate credit equals the basic-rate tax. This is the
characteristic Section 24 behaviour for basic-rate taxpayers.

### Expected Outputs

```
gross_annual_rent_gbp:              11,400.00
effective_annual_rent_gbp:          10,961.10
total_operating_costs_annual_gbp:    4,168.00
net_operating_income_gbp:            6,793.10
annual_mortgage_cost_gbp:            7,125.00
annual_tax_liability_gbp:               0.00
annual_cash_flow_gbp:                 -331.90
monthly_cash_flow_gbp:                 -27.66
gross_yield_percent:                    5.70
net_yield_percent:                      3.40
roce_percent:                          11.32
cash_on_cash_return_percent:            -0.55
ltv_percent:                           75.00
icr_percent:                          132.86
total_sdlt_gbp:                       7,500.00
total_acquisition_cost_gbp:         210,000.00
total_cash_deployed_gbp:             60,000.00
```

### Expected Risk Flags

```
NEGATIVE_CASHFLOW:  severity=HIGH,   triggered_by_field=annual_cash_flow_gbp,
                    triggered_by_value="-331.90"
RENT_UNVERIFIED:    severity=INFO,   triggered_by_field=monthly_rent,
                    triggered_by_value="950.00"
```

### Expected Validation Warnings

```
V-25: refurbishment_cost = 0. "No refurbishment cost entered..."
```

### Flags NOT triggered (verify absence)

```
HIGH_LEVERAGE           — ltv=75.00 is not > 75
LOW_GROSS_YIELD         — 5.70 is not < 4.0
LOW_NET_YIELD           — 3.40 is not < 3.0
LOW_ICR_BASIC           — 132.86 is not < 125
LOW_ICR_HIGHER_RATE     — income_tax_band is BASIC_RATE
SECTION_24_IMPACT       — income_tax_band is BASIC_RATE
CASH_FLOW_PRE_TAX_ONLY  — pre_tax = -331.90 (< 0, so condition not met)
LOW_MARGIN_SAFETY       — annual_cash_flow < 0 (condition requires >= 0)
HIGH_REFURB_RATIO       — refurb=0
ATED_WARNING            — not LIMITED_COMPANY
LTD_EXTRACTION          — not LIMITED_COMPANY
LEASEHOLD_SHORT_LEASE   — FREEHOLD
NEGATIVE_NOI            — NOI=6,793.10 > 0
```

---

## E-02 — Standard BTL, Higher-Rate Taxpayer, Section 24 Impact

**Purpose:** Same property and mortgage as E-01, but investor is a higher-rate
taxpayer. Demonstrates the material impact of Section 24 on post-tax cash flow
and the additional risk flags triggered.

### Inputs

All inputs identical to E-01 except:
```
income_tax_band: HIGHER_RATE
```

### Expected Intermediates (changes from E-01 only)

```
taxable_income_or_profit_gbp:   6,793.10    (unchanged)
income_tax_gross_gbp:           2,717.24    (6,793.10 × 0.40)
mortgage_interest_tax_credit:   1,425.00    (unchanged — always 20%)
annual_tax_liability_gbp:       1,292.24    (2,717.24 - 1,425.00)
pre_tax_annual_cash_flow_gbp:   -331.90     (unchanged)
section_24_applies:             true
```

### Expected Outputs (changes from E-01 only)

```
annual_tax_liability_gbp:         1,292.24
annual_cash_flow_gbp:            -1,624.14
monthly_cash_flow_gbp:             -135.35
cash_on_cash_return_percent:         -2.71
```

All other outputs identical to E-01.

### Expected Risk Flags

```
NEGATIVE_CASHFLOW:    severity=HIGH
SECTION_24_IMPACT:    severity=HIGH,   triggered_by_field=income_tax_band,
                      triggered_by_value="HIGHER_RATE"
LOW_ICR_HIGHER_RATE:  severity=HIGH,   triggered_by_field=icr_percent,
                      triggered_by_value="132.86"
                      (132.86 >= 125 AND < 145, income_tax_band=HIGHER_RATE)
RENT_UNVERIFIED:      severity=INFO
```

### Expected Validation Warnings

```
V-25: refurbishment_cost = 0
```

---

## E-03 — Mid-Range BTL, Limited Company, Standard Case

**Purpose:** £350,000 purchase via limited company SPV, interest-only. Demonstrates
corporation tax pathway, Ltd Co defaults (accountancy cost), and the absence of
Section 24 impact.

### Inputs

```
purchase_price:           350,000.00
monthly_rent:             1,600.00
deposit_amount:           87,500.00
mortgage_interest_rate:   5.00
mortgage_term_years:      25
mortgage_type:            INTEREST_ONLY
ownership_structure:      LIMITED_COMPANY
income_tax_band:          null
is_additional_dwelling:   true
property_type:            RESIDENTIAL_SINGLE_LET
tenure:                   FREEHOLD
property_country:         ENGLAND
postcode:                 M1 1AA

Optional overrides from REFERENCE CONFIG:
annual_accountancy_cost:  1,200.00  (Ltd Co default)
All other optionals:      REFERENCE CONFIG defaults
refurbishment_cost:       0.00
annual_service_charge:    0.00
annual_ground_rent:       0.00
```

### Expected Intermediates

```
void_rate_decimal_applied:      0.0385
gross_annual_rent_gbp:          19,200.00
effective_annual_rent_gbp:      18,460.80
loan_amount_gbp:                262,500.00
ltv_percent:                    75.00
monthly_mortgage_payment_gbp:   1,093.75
annual_mortgage_cost_gbp:       13,125.00
annual_mortgage_interest_gbp:   13,125.00
letting_agent_annual_gbp:       2,304.00
annual_maintenance_reserve_gbp: 3,500.00
total_operating_costs_annual:   7,804.00
net_operating_income_gbp:       10,656.80
sdlt_band_breakdown:
  Band 0–125,000:   tax=0.00
  Band 125–250,000: taxable=125,000  tax=2,500.00
  Band 250–350,000: taxable=100,000  rate=5%  tax=5,000.00
sdlt_base_gbp:                  7,500.00
sdlt_surcharge_gbp:             10,500.00
total_sdlt_gbp:                 18,000.00
total_acquisition_cost_gbp:     370,500.00
total_cash_deployed_gbp:        108,000.00
stressed_annual_interest_gbp:   14,437.50
stress_test_rate_applied:       5.50
taxable_income_or_profit_gbp:   -2,468.20
corporation_tax_gross_gbp:      0.00
income_tax_gross_gbp:           null
mortgage_interest_tax_credit:   null
annual_tax_liability_gbp:       0.00
pre_tax_annual_cash_flow_gbp:   -2,468.20
section_24_applies:             false
```

Taxable profit derivation:
18,460.80 - 2,304 - 3,500 - 800 - 0 - 0 - 1,200 - 13,125 = -2,468.20
Negative profit → corporation_tax = 0.

### Expected Outputs

```
gross_annual_rent_gbp:              19,200.00
effective_annual_rent_gbp:          18,460.80
total_operating_costs_annual_gbp:    7,804.00
net_operating_income_gbp:           10,656.80
annual_mortgage_cost_gbp:           13,125.00
annual_tax_liability_gbp:               0.00
annual_cash_flow_gbp:               -2,468.20
monthly_cash_flow_gbp:               -205.68
gross_yield_percent:                    5.49
net_yield_percent:                      3.04
roce_percent:                           9.87
cash_on_cash_return_percent:            -2.29
ltv_percent:                           75.00
icr_percent:                          127.88
total_sdlt_gbp:                      18,000.00
total_acquisition_cost_gbp:         370,500.00
total_cash_deployed_gbp:            108,000.00
```

### Expected Risk Flags

```
NEGATIVE_CASHFLOW:          severity=HIGH
LTD_EXTRACTION_UNDISCLOSED: severity=INFO
RENT_UNVERIFIED:            severity=INFO
```

### Expected Validation Warnings

```
V-25: refurbishment_cost = 0
```

### Flags NOT triggered (verify absence)

```
SECTION_24_IMPACT   — LIMITED_COMPANY, not applicable
LOW_ICR_BASIC       — 127.88 >= 125
ATED_WARNING        — 350,000 < 500,000
HIGH_LEVERAGE       — 75.00 not > 75
LOW_NET_YIELD       — 3.04 >= 3.0
```

---

## E-04 — Lower Leverage, Positive Cash Flow, Basic-Rate

**Purpose:** Same property as E-01 with a 40% deposit. Demonstrates that
reducing leverage to 60% LTV at the same rent produces positive cash flow and
no HIGH risk flags. The baseline scenario for a conservative investor.

### Inputs

All inputs identical to E-01 except:
```
deposit_amount: 80,000.00
```

Derived: loan_amount = 120,000.00, ltv = 60.00%

### Expected Intermediates (changes from E-01)

```
loan_amount_gbp:                120,000.00
ltv_percent:                    60.00
monthly_mortgage_payment_gbp:   475.00
annual_mortgage_cost_gbp:       5,700.00
annual_mortgage_interest_gbp:   5,700.00
total_cash_deployed_gbp:        90,000.00
stressed_annual_interest_gbp:   6,600.00
income_tax_gross_gbp:           1,358.62
mortgage_interest_tax_credit:   1,140.00    (5,700 × 0.20)
annual_tax_liability_gbp:       218.62      (1,358.62 - 1,140.00)
pre_tax_annual_cash_flow_gbp:   1,093.10    (6,793.10 - 5,700.00)
```

All rent, operating cost, SDLT, NOI intermediates unchanged from E-01.
total_sdlt, purchase_legal_costs unchanged → total_cash_deployed = 80,000 + 7,500 + 2,500 = 90,000.

### Expected Outputs

```
gross_annual_rent_gbp:              11,400.00
effective_annual_rent_gbp:          10,961.10
total_operating_costs_annual_gbp:    4,168.00
net_operating_income_gbp:            6,793.10
annual_mortgage_cost_gbp:            5,700.00
annual_tax_liability_gbp:              218.62
annual_cash_flow_gbp:                  874.48
monthly_cash_flow_gbp:                  72.87
gross_yield_percent:                    5.70
net_yield_percent:                      3.40
roce_percent:                           7.55
cash_on_cash_return_percent:            0.97
ltv_percent:                           60.00
icr_percent:                          166.08
total_sdlt_gbp:                       7,500.00
total_acquisition_cost_gbp:         210,000.00
total_cash_deployed_gbp:             90,000.00
```

### Expected Risk Flags

```
RENT_UNVERIFIED: severity=INFO
```

### Expected Validation Warnings

```
V-25: refurbishment_cost = 0
```

### Flags NOT triggered (verify absence)

```
NEGATIVE_CASHFLOW   — 874.48 > 0
HIGH_LEVERAGE       — 60.00 not > 75
LOW_ICR_BASIC       — 166.08 >= 125
SECTION_24_IMPACT   — BASIC_RATE
LOW_MARGIN_SAFETY   — margin = 874.48/11,400 = 7.67%, >= 5%
```

---

## E-05 — High Value Ltd Co Purchase, ATED Threshold, Low ICR

**Purpose:** £600,000 purchase via limited company. Demonstrates ATED warning,
LOW_ICR_BASIC flag, and NEGATIVE_CASHFLOW on a high-value property.

### Inputs

```
purchase_price:           600,000.00
monthly_rent:             2,400.00
deposit_amount:           150,000.00
mortgage_interest_rate:   5.25
mortgage_term_years:      25
mortgage_type:            INTEREST_ONLY
ownership_structure:      LIMITED_COMPANY
income_tax_band:          null
is_additional_dwelling:   true
property_type:            RESIDENTIAL_SINGLE_LET
tenure:                   FREEHOLD
property_country:         ENGLAND
postcode:                 SW1A 1AA

annual_accountancy_cost:  1,200.00
All other optionals:      REFERENCE CONFIG defaults
```

### Expected Intermediates

```
gross_annual_rent_gbp:          28,800.00
effective_annual_rent_gbp:      27,691.20
loan_amount_gbp:                450,000.00
ltv_percent:                    75.00
monthly_mortgage_payment_gbp:   1,968.75
annual_mortgage_cost_gbp:       23,625.00
annual_mortgage_interest_gbp:   23,625.00
letting_agent_annual_gbp:       3,456.00
annual_maintenance_reserve_gbp: 6,000.00
total_operating_costs_annual:   11,456.00
net_operating_income_gbp:       16,235.20
sdlt_band_breakdown:
  Band 0–125,000:   tax=0.00
  Band 125–250,000: taxable=125,000  rate=2%  tax=2,500.00
  Band 250–600,000: taxable=350,000  rate=5%  tax=17,500.00
sdlt_base_gbp:                  20,000.00
sdlt_surcharge_gbp:             18,000.00
total_sdlt_gbp:                 38,000.00
total_acquisition_cost_gbp:     640,500.00
total_cash_deployed_gbp:        190,500.00
stressed_annual_interest_gbp:   24,750.00
taxable_income_or_profit_gbp:   -7,389.80
corporation_tax_gross_gbp:      0.00
annual_tax_liability_gbp:       0.00
pre_tax_annual_cash_flow_gbp:   -7,389.80
section_24_applies:             false
```

Taxable profit: 27,691.20 - 3,456 - 6,000 - 800 - 0 - 0 - 1,200 - 23,625 = -7,389.80

### Expected Outputs

```
gross_annual_rent_gbp:              28,800.00
effective_annual_rent_gbp:          27,691.20
total_operating_costs_annual_gbp:   11,456.00
net_operating_income_gbp:           16,235.20
annual_mortgage_cost_gbp:           23,625.00
annual_tax_liability_gbp:               0.00
annual_cash_flow_gbp:               -7,389.80
monthly_cash_flow_gbp:               -615.82
gross_yield_percent:                    4.80
net_yield_percent:                      2.71
roce_percent:                           8.52
cash_on_cash_return_percent:            -3.88
ltv_percent:                           75.00
icr_percent:                          111.88
total_sdlt_gbp:                      38,000.00
total_acquisition_cost_gbp:         640,500.00
total_cash_deployed_gbp:            190,500.00
```

### Expected Risk Flags

```
NEGATIVE_CASHFLOW:          severity=HIGH,
                            triggered_by_value="-7389.80"
LOW_NET_YIELD:              severity=MEDIUM,
                            triggered_by_field=net_yield_percent,
                            triggered_by_value="2.71"
LOW_ICR_BASIC:              severity=HIGH,
                            triggered_by_field=icr_percent,
                            triggered_by_value="111.88"
ATED_WARNING:               severity=MEDIUM,
                            triggered_by_field=purchase_price,
                            triggered_by_value="600000.00"
LTD_EXTRACTION_UNDISCLOSED: severity=INFO
RENT_UNVERIFIED:            severity=INFO
```

### Expected Validation Warnings

```
V-25: refurbishment_cost = 0
```

---

## E-06 — Leasehold Property, Service Charge and Ground Rent, Higher-Rate

**Purpose:** Leasehold flat purchase by a higher-rate individual taxpayer with
annual service charge and ground rent. Demonstrates leasehold cost inputs,
INFO flag for leasehold disclosure, and combined Section 24 + ICR flags.
Lease is above 80 years so LEASEHOLD_SHORT_LEASE does not fire.

### Inputs

```
purchase_price:           180,000.00
monthly_rent:             850.00
deposit_amount:           45,000.00
mortgage_interest_rate:   4.75
mortgage_term_years:      25
mortgage_type:            INTEREST_ONLY
ownership_structure:      INDIVIDUAL
income_tax_band:          HIGHER_RATE
is_additional_dwelling:   true
property_type:            RESIDENTIAL_SINGLE_LET
tenure:                   LEASEHOLD
lease_years_remaining:    95
property_country:         ENGLAND
postcode:                 B1 1AA

annual_service_charge:    1,200.00
annual_ground_rent:       150.00
refurbishment_cost:       0.00
annual_accountancy_cost:  0.00     (individual default)
All other optionals:      REFERENCE CONFIG defaults
```

### Expected Intermediates

```
gross_annual_rent_gbp:          10,200.00
effective_annual_rent_gbp:       9,807.30
loan_amount_gbp:                135,000.00
ltv_percent:                    75.00
monthly_mortgage_payment_gbp:   534.38
annual_mortgage_cost_gbp:       6,412.50
annual_mortgage_interest_gbp:   6,412.50
letting_agent_annual_gbp:       1,224.00
annual_maintenance_reserve_gbp: 1,800.00
total_operating_costs_annual:   5,174.00
net_operating_income_gbp:       4,633.30
sdlt_band_breakdown:
  Band 0–125,000:   tax=0.00
  Band 125–180,000: taxable=55,000  rate=2%  tax=1,100.00
sdlt_base_gbp:                  1,100.00
sdlt_surcharge_gbp:             5,400.00
total_sdlt_gbp:                 6,500.00
total_acquisition_cost_gbp:     189,000.00
total_cash_deployed_gbp:        54,000.00
stressed_annual_interest_gbp:   7,425.00
taxable_income_or_profit_gbp:   4,633.30
income_tax_gross_gbp:           1,853.32
mortgage_interest_tax_credit:   1,282.50
annual_tax_liability_gbp:       570.82
pre_tax_annual_cash_flow_gbp:   -1,779.20
section_24_applies:             true
```

Operating costs: 1,224 + 1,800 + 800 + 1,200 + 150 + 0 = 5,174.00
Taxable income: 9,807.30 - 1,224 - 1,800 - 800 - 1,200 - 150 - 0 = 4,633.30
income_tax_gross: 4,633.30 × 0.40 = 1,853.32
credit: 6,412.50 × 0.20 = 1,282.50
tax_liability: 1,853.32 - 1,282.50 = 570.82
pre_tax: 4,633.30 - 6,412.50 = -1,779.20

### Expected Outputs

```
gross_annual_rent_gbp:              10,200.00
effective_annual_rent_gbp:           9,807.30
total_operating_costs_annual_gbp:    5,174.00
net_operating_income_gbp:            4,633.30
annual_mortgage_cost_gbp:            6,412.50
annual_tax_liability_gbp:              570.82
annual_cash_flow_gbp:               -2,350.02
monthly_cash_flow_gbp:               -195.84
gross_yield_percent:                    5.67
net_yield_percent:                      2.57
roce_percent:                           8.58
cash_on_cash_return_percent:            -4.35
ltv_percent:                           75.00
icr_percent:                          132.10
total_sdlt_gbp:                       6,500.00
total_acquisition_cost_gbp:         189,000.00
total_cash_deployed_gbp:             54,000.00
```

### Expected Risk Flags

```
NEGATIVE_CASHFLOW:     severity=HIGH
SECTION_24_IMPACT:     severity=HIGH
LOW_NET_YIELD:         severity=MEDIUM   (2.57 < 3.0)
LOW_ICR_HIGHER_RATE:   severity=HIGH     (132.10 >= 125, < 145, HIGHER_RATE)
RENT_UNVERIFIED:       severity=INFO
```

### Expected Validation Warnings

```
V-25: refurbishment_cost = 0
```

### Flags NOT triggered (verify absence)

```
LEASEHOLD_SHORT_LEASE — lease_years_remaining=95, not < 80
V-23                  — ground_rent=150, not > 250
```

---

## E-07 — Validation: HARD Failure, Deposit Below 15% Threshold

**Purpose:** Confirms that V-07 (deposit below 15% of purchase price) produces
a HARD validation failure and blocks all calculation.

### Inputs

```
purchase_price:     200,000.00
monthly_rent:       950.00
deposit_amount:     25,000.00     ← 12.5% of purchase price, below 15% threshold
mortgage_interest_rate: 4.75
mortgage_term_years: 25
mortgage_type:      INTEREST_ONLY
ownership_structure: INDIVIDUAL
income_tax_band:    BASIC_RATE
is_additional_dwelling: true
property_type:      RESIDENTIAL_SINGLE_LET
tenure:             FREEHOLD
property_country:   ENGLAND
postcode:           NG1 1AA
```

### Expected Result: ValidationResult (not EngineResult)

```
is_valid: false
hard_errors: [
    ValidationError(
        rule_code: "V-07",
        field:     "deposit_amount",
        message:   "Deposit is below 15% of the purchase price.
                    BTL mortgages are not available below this threshold."
    )
]
warnings: []
```

No `EngineResult` is produced. No snapshot is created.

---

## E-08 — Validation: WARN Only, Deposit Below 25%, Calculation Proceeds

**Purpose:** Confirms that V-08 (deposit below 25%) produces a WARN that is
carried into the result but does not block calculation.

### Inputs

All inputs identical to E-01 except:
```
deposit_amount: 35,000.00     ← 17.5% of purchase price (above 15%, below 25%)
```

### Expected ValidationResult

```
is_valid: true
hard_errors: []
warnings: [
    ValidationWarning(
        rule_code: "V-08",
        field:     "deposit_amount",
        message:   "Deposit is below 25%. Most BTL lenders require a minimum
                    25% deposit. Product availability may be limited."
    ),
    ValidationWarning(
        rule_code: "V-25",
        field:     "refurbishment_cost",
        message:   "No refurbishment cost entered..."
    )
]
```

Calculation proceeds. `EngineResult` is produced. V-08 warning is included
in `EngineResult.validation_warnings`.

Key derived values for verification:
```
loan_amount:    165,000.00
ltv_percent:    82.50
```

### Expected Risk Flags (additional to E-01)

```
HIGH_LEVERAGE:          severity=HIGH   (82.50 > 75)
HIGH_LEVERAGE_EXTREME:  severity=HIGH   (82.50 > 85? No — 82.50 < 85 → NOT triggered)
NEGATIVE_CASHFLOW:      severity=HIGH   (mortgage higher, cash flow more negative)
RENT_UNVERIFIED:        severity=INFO
```

Note: HIGH_LEVERAGE_EXTREME triggers only when ltv > 85. At 82.50%, only
HIGH_LEVERAGE fires.

---

## E-09 — Short Lease Leasehold, Lease Below 80 Years

**Purpose:** Confirms LEASEHOLD_SHORT_LEASE flag triggers when
lease_years_remaining < 80.

### Inputs

All inputs identical to E-06 except:
```
lease_years_remaining: 72     ← below 80-year threshold
```

### Expected Risk Flags (additions to E-06 flags)

```
LEASEHOLD_SHORT_LEASE: severity=HIGH,
                       triggered_by_field=lease_years_remaining,
                       triggered_by_value="72"
```

All other flags from E-06 remain. No change to calculated values.

---

## E-10 — Additional Rate Taxpayer, Section 24 Maximum Impact

**Purpose:** Demonstrates Section 24 at 45% additional rate. Confirms the
credit calculation remains 20% regardless of marginal rate, and shows the
maximum divergence between pre-tax and post-tax outcomes.

### Inputs

All inputs identical to E-01 except:
```
income_tax_band: ADDITIONAL_RATE
```

### Expected Intermediates (changes from E-01)

```
taxable_income_or_profit_gbp:   6,793.10    (unchanged)
income_tax_gross_gbp:           3,056.90    (6,793.10 × 0.45)
mortgage_interest_tax_credit:   1,425.00    (unchanged — always 20%)
annual_tax_liability_gbp:       1,631.90    (3,056.90 - 1,425.00)
```

### Expected Outputs (changes from E-01)

```
annual_tax_liability_gbp:    1,631.90
annual_cash_flow_gbp:       -1,963.80
monthly_cash_flow_gbp:        -163.65
cash_on_cash_return_percent:    -3.27
```

### Expected Risk Flags

```
NEGATIVE_CASHFLOW:    severity=HIGH
SECTION_24_IMPACT:    severity=HIGH   (ADDITIONAL_RATE)
LOW_ICR_HIGHER_RATE:  severity=HIGH   (132.86 >= 125, < 145, ADDITIONAL_RATE)
RENT_UNVERIFIED:      severity=INFO
```

---

## E-11 — Thin Margin Safety, Positive Cash Flow

**Purpose:** A deal that produces positive cash flow but with a margin below
5% of gross rent, triggering LOW_MARGIN_SAFETY.

### Inputs

```
purchase_price:           220,000.00
monthly_rent:             950.00
deposit_amount:           55,000.00
mortgage_interest_rate:   4.50
mortgage_term_years:      25
mortgage_type:            INTEREST_ONLY
ownership_structure:      INDIVIDUAL
income_tax_band:          BASIC_RATE
is_additional_dwelling:   true
property_type:            RESIDENTIAL_SINGLE_LET
tenure:                   FREEHOLD
property_country:         ENGLAND
postcode:                 LS1 1AA
refurbishment_cost:       0.00
All other optionals:      REFERENCE CONFIG defaults
```

### Key Working

```
gross_annual_rent:     11,400.00
effective_annual_rent: 10,961.10
loan_amount:          165,000.00
ltv:                   75.00
annual_mortgage_cost: (165,000 × 0.045) = 7,425.00
annual_mortgage_interest: 7,425.00
maintenance:          220,000 × 0.01 = 2,200.00
total_operating:      1,368 + 2,200 + 800 = 4,368.00
NOI:                  10,961.10 - 4,368.00 = 6,593.10
taxable_income:       6,593.10
income_tax:           6,593.10 × 0.20 = 1,318.62
credit:               7,425.00 × 0.20 = 1,485.00
tax_liability:        MAX(0, 1,318.62 - 1,485.00) = 0.00
annual_cash_flow:     6,593.10 - 7,425.00 - 0.00 = -831.90
```

Cash flow is negative. This does not demonstrate thin margin. Adjusting
to show a positive-but-thin margin scenario requires a lower rate. Using
mortgage_interest_rate: 3.50 to demonstrate the flag.

### Revised Inputs

```
mortgage_interest_rate: 3.50
```

```
annual_mortgage_cost:     165,000 × 0.035 = 5,775.00
annual_mortgage_interest: 5,775.00
income_tax:               6,593.10 × 0.20 = 1,318.62
credit:                   5,775.00 × 0.20 = 1,155.00
tax_liability:            MAX(0, 1,318.62 - 1,155.00) = 163.62
annual_cash_flow:         6,593.10 - 5,775.00 - 163.62 = 654.48
monthly_cash_flow:        54.54
margin:                   654.48 / 11,400 = 0.0574 = 5.74%
```

At 5.74% margin this does NOT trigger LOW_MARGIN_SAFETY (threshold < 5%).
Further reducing mortgage rate to produce sub-5% margin:

Using mortgage_interest_rate: 3.80

```
annual_mortgage_cost:     165,000 × 0.038 = 6,270.00
income_tax:               1,318.62
credit:                   6,270.00 × 0.20 = 1,254.00
tax_liability:            MAX(0, 1,318.62 - 1,254.00) = 64.62
annual_cash_flow:         6,593.10 - 6,270.00 - 64.62 = 258.48
margin:                   258.48 / 11,400 = 0.0227 = 2.27% < 5%
```

### Final Inputs for E-11

```
purchase_price:           220,000.00
monthly_rent:             950.00
deposit_amount:           55,000.00
mortgage_interest_rate:   3.80
mortgage_term_years:      25
mortgage_type:            INTEREST_ONLY
ownership_structure:      INDIVIDUAL
income_tax_band:          BASIC_RATE
is_additional_dwelling:   true
property_type:            RESIDENTIAL_SINGLE_LET
tenure:                   FREEHOLD
property_country:         ENGLAND
postcode:                 LS1 1AA
```

### Expected Outputs

```
gross_annual_rent_gbp:              11,400.00
effective_annual_rent_gbp:          10,961.10
total_operating_costs_annual_gbp:    4,368.00
net_operating_income_gbp:            6,593.10
annual_mortgage_cost_gbp:            6,270.00
annual_tax_liability_gbp:               64.62
annual_cash_flow_gbp:                  258.48
monthly_cash_flow_gbp:                  21.54
gross_yield_percent:                    5.18
net_yield_percent:                      3.00
roce_percent:                           9.30
cash_on_cash_return_percent:            0.38
ltv_percent:                           75.00
icr_percent:                          150.08
```

SDLT on 220,000:
  base: 125k@0% + 95k@2% = 1,900
  surcharge: 220,000 × 0.03 = 6,600
  total_sdlt: 8,500

```
total_sdlt_gbp:          8,500.00
total_cash_deployed_gbp: 66,000.00   (55,000 + 8,500 + 2,500)
```

### Expected Risk Flags

```
LOW_MARGIN_SAFETY:  severity=MEDIUM
                    triggered_by_field=annual_cash_flow_gbp,
                    triggered_by_value="258.48"
                    (258.48 / 11,400 = 2.27%, < 5%, cash_flow >= 0)
RENT_UNVERIFIED:    severity=INFO
```

### Expected Validation Warnings

```
V-11: mortgage_interest_rate=3.80, < 3.0? No → NOT triggered
      (3.80 is not < 3.0)
V-25: refurbishment_cost = 0
```

Note: V-11 triggers only when rate < 3.0 AND > 0. At 3.80, V-11 does not
trigger. V-08 does not trigger (deposit = 55,000 = 25% of 220,000 exactly).

---

## E-12 — High Refurbishment Ratio

**Purpose:** Confirms HIGH_REFURB_RATIO flag triggers when refurbishment
exceeds 10% of purchase price.

### Inputs

All inputs identical to E-01 except:
```
refurbishment_cost: 25,000.00     ← 12.5% of 200,000 purchase price
```

### Key Changes

```
total_sdlt:          7,500.00     (unchanged)
total_acquisition:   210,000 + 25,000 = 235,000.00
total_cash_deployed: 50,000 + 7,500 + 2,500 + 25,000 = 85,000.00
```

All income, operating cost, NOI, yield, mortgage, tax outputs identical to E-01
except:

```
total_acquisition_cost_gbp: 235,000.00
total_cash_deployed_gbp:     85,000.00
roce_percent:               (6,793.10 / 85,000) × 100 = 7.99
cash_on_cash_return_percent: (-331.90 / 85,000) × 100 = -0.39
```

### Expected Risk Flags

```
NEGATIVE_CASHFLOW:   severity=HIGH
HIGH_REFURB_RATIO:   severity=MEDIUM,
                     triggered_by_field=refurbishment_cost,
                     triggered_by_value="25000.00"
                     (25,000 > 200,000 × 0.10 = 20,000)
RENT_UNVERIFIED:     severity=INFO
```

### Expected Validation Warnings

V-25 (refurb=0) NOT triggered because refurbishment_cost = 25,000 (not 0).

---

---

# Part 12 — Snapshot Payload Specification

When the calculation service persists an `EngineResult`, the following
payload structure must be written atomically. This is not the database schema
— it is the logical structure the persistence layer must produce from the
`EngineResult` and its surrounding context.

```
SnapshotPayload:

  identity:
    snapshot_id:          UUID (assigned by persistence layer)
    deal_id:              UUID (from calling context)
    user_id:              UUID (from calling context)
    calculated_at:        UTC datetime (assigned by persistence layer)
    engine_version:       String (from engine module constant)
    is_superseded:        false (set true only when next snapshot created)

  version_references:
    assumption_config_version_id:      UUID (from ConfigBundle.version_refs)
    sdlt_config_version_id:            UUID (from ConfigBundle.version_refs)
    corporation_tax_config_version_id: UUID (from ConfigBundle.version_refs)

  inputs:
    [all fields from EngineInput — required and optional]
    [per optional field: value_used and source (USER_OVERRIDE/CONFIG_DEFAULT)]

  outputs:
    [all fields from EngineOutputs]

  intermediates:
    [all fields from EngineIntermediates]

  risk_flags:
    [one record per RiskFlag in EngineResult.risk_flags]
    [each record: code, severity, triggered_by_field,
                  triggered_by_value, message]

  validation_warnings:
    [one record per ValidationWarning in EngineResult.validation_warnings]
    [each record: rule_code, field, message]
```

---

---

# Part 13 — Formula Catalogue Reference

Quick reference mapping formula identifiers to their canonical definitions
in CALCULATION_SPEC.md.

| Formula | Name                          | CALCULATION_SPEC Reference |
|---------|-------------------------------|----------------------------|
| F-01    | Gross Annual Rent             | Formula Definitions: F-01  |
| F-02    | Void Rate Conversion          | Formula Definitions: F-02  |
| F-03    | Effective Annual Rent         | Formula Definitions: F-03  |
| F-04    | Loan Amount                   | Formula Definitions: F-04  |
| F-05    | LTV                           | Formula Definitions: F-05  |
| F-06    | Monthly Mortgage Payment      | Formula Definitions: F-06  |
| F-07    | Annual Mortgage Cost          | Formula Definitions: F-07  |
| F-08    | Annual Mortgage Interest      | Formula Definitions: F-08  |
| F-09    | Letting Agent Annual Cost     | Formula Definitions: F-09  |
| F-10    | Annual Maintenance Reserve    | Formula Definitions: F-10  |
| F-11    | Total Annual Operating Costs  | Formula Definitions: F-11  |
| F-12    | Net Operating Income          | Formula Definitions: F-12  |
| F-13    | SDLT Calculation              | Formula Definitions: F-13  |
| F-14    | Total Acquisition Cost        | Formula Definitions: F-14  |
| F-15    | Total Cash Deployed           | Formula Definitions: F-15  |
| F-16    | Gross Yield                   | Formula Definitions: F-16  |
| F-17    | Net Yield                     | Formula Definitions: F-17  |
| F-18    | ROCE                          | Formula Definitions: F-18  |
| F-19    | Annual Cash Flow              | Formula Definitions: F-19  |
| F-20    | Monthly Cash Flow             | Formula Definitions: F-20  |
| F-21    | Cash-on-Cash Return           | Formula Definitions: F-21  |
| F-22    | ICR Stress Test               | Formula Definitions: F-22  |
| TAX-A   | Individual / Section 24       | Tax Calculations: Pathway A|
| TAX-B   | Limited Company / Corp Tax    | Tax Calculations: Pathway B|

---

---

# Part 14 — Regression Test Coverage Requirements

Every test scenario in Part 11 must have a corresponding automated test.
The following coverage requirements apply to the test suite.

---

## Scenario coverage

| Scenario | Primary Coverage                                                    |
|----------|---------------------------------------------------------------------|
| E-01     | All formulas, basic-rate tax, zero tax liability, Section 24 credit |
| E-02     | Section 24 higher-rate, SECTION_24_IMPACT flag, LOW_ICR_HIGHER_RATE|
| E-03     | Ltd Co pathway, accountancy default, negative taxable profit        |
| E-04     | Lower leverage, positive cash flow, no HIGH flags                   |
| E-05     | ATED warning, LOW_ICR_BASIC, SDLT on 5% band extension             |
| E-06     | Leasehold inputs, service charge, ground rent, HIGHER_RATE          |
| E-07     | HARD validation failure, engine does not calculate                  |
| E-08     | WARN-only validation, calculation proceeds, HIGH_LEVERAGE flag      |
| E-09     | LEASEHOLD_SHORT_LEASE flag trigger                                  |
| E-10     | Additional-rate tax, maximum Section 24 impact                      |
| E-11     | LOW_MARGIN_SAFETY flag, thin but positive cash flow                 |
| E-12     | HIGH_REFURB_RATIO flag, acquisition cost and cash deployed changes  |

---

## Additional unit test requirements

Beyond the end-to-end scenarios, the following specific formula cases must
have dedicated unit tests:

**SDLT boundary tests:**
- Purchase price exactly at £125,000 (only the 0% band applies)
- Purchase price at £125,001 (first penny of 2% band)
- Purchase price at £250,000 (top of 2% band)
- Purchase price at £250,001 (first penny of 5% band)
- Purchase price at £925,001 (first penny of 10% band)
- Purchase price at £1,500,001 (first penny of 12% band)
- All the above with is_additional_dwelling = true (surcharge applied)
- All the above with is_additional_dwelling = false (no surcharge)

**Mortgage formula tests:**
- Interest-only: verify monthly = (loan × rate) / 12
- Repayment: verify standard annuity formula output for a known case
- Zero interest rate: treated as cash purchase, no mortgage calculations

**Tax boundary tests:**
- BASIC_RATE with credit exactly equal to tax (net liability = 0)
- HIGHER_RATE with credit less than tax (positive net liability)
- ADDITIONAL_RATE at maximum divergence
- Negative taxable income (NOI barely covers costs): tax = 0
- Ltd Co taxable profit exactly at £50,000 small profits boundary
- Ltd Co taxable profit at £50,001 (marginal relief band entry)
- Ltd Co taxable profit <= 0 (no tax)

**ICR edge cases:**
- Cash purchase (loan = 0): icr_percent = None
- ICR exactly at 125.00: LOW_ICR_BASIC does NOT fire
- ICR at 124.99: LOW_ICR_BASIC fires
- ICR at 145.00 for higher-rate: LOW_ICR_HIGHER_RATE does NOT fire
- ICR at 144.99 for higher-rate: LOW_ICR_HIGHER_RATE fires

**Risk flag boundary tests:**
- LOW_MARGIN_SAFETY: margin at exactly 5.00% (does not fire)
- LOW_MARGIN_SAFETY: margin at 4.99% (fires)
- HIGH_LEVERAGE: ltv at exactly 75.00 (does not fire)
- HIGH_LEVERAGE: ltv at 75.01 (fires)
- HIGH_LEVERAGE_EXTREME: ltv at 85.00 (does not fire)
- HIGH_LEVERAGE_EXTREME: ltv at 85.01 (fires)
- LOW_GROSS_YIELD: yield at exactly 4.00 (does not fire)
- LOW_GROSS_YIELD: yield at 3.99 (fires)
- LEASEHOLD_SHORT_LEASE: lease_years = 80 (does not fire)
- LEASEHOLD_SHORT_LEASE: lease_years = 79 (fires)
- LEASEHOLD_SHORT_LEASE: lease_years = null (does not fire)

---

## Determinism tests

These tests must run on every code change:

1. Run engine with E-01 inputs twice. Assert results are byte-for-byte identical.
2. Serialise E-01 EngineInput and EngineConfig to JSON. Deserialise. Run again.
   Assert result identical to original.
3. Run engine with E-03 inputs (Ltd Co) twice. Assert identical.
4. Run engine with E-07 inputs. Assert ValidationFailure returned, no EngineResult.
5. Run any scenario with config version A. Record result. Run with config version B
   (different assumption config). Assert results differ. Run again with config A.
   Assert result matches first run exactly.
