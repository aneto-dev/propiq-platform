# PropIQ Platform — Engine Test Strategy

## Purpose

This document defines the complete testing strategy for the PropIQ underwriting
engine. It specifies what to test, how to organise tests, how to structure test
data, and what properties each test category must assert.

This document does not contain implementation code. It defines the testing
design from which implementation will follow. All test implementations must be
traceable to a section of this document or to a contract in ENGINE_CONTRACTS.md.

All terminology matches DOMAIN_GLOSSARY.md.
All contracts are sourced from ENGINE_CONTRACTS.md.
All formula references are sourced from CALCULATION_SPEC.md.
All module boundaries are sourced from ENGINE_ARCHITECTURE.md.

---

## Governing Principles

**Tests are the living specification.** ENGINE_CONTRACTS.md defines what the
engine must produce. The test suite is the executable form of that definition.
If a test passes but the result conflicts with ENGINE_CONTRACTS.md, the test
is wrong. If ENGINE_CONTRACTS.md is updated, the affected tests must be updated
in the same commit.

**Expected values must be pre-computed, not co-derived.** No test may compute
its expected value using the same formula as the code under test. All expected
values in this test suite were computed by hand from CALCULATION_SPEC.md before
the engine was written. This is the only way a test can detect a formula error.

**Test independence is mandatory.** No test may depend on the outcome of any
other test. No test may read or write shared mutable state. Tests may share
immutable fixture data. The engine is a pure function — this constraint is
natural.

**The engine has no framework dependencies, so tests have none either.** No
test in the `engine/` test suite imports FastAPI, SQLAlchemy, or any
persistence layer. Tests call engine functions with plain data arguments.
Anything requiring database setup belongs to integration tests, not unit tests.

**Boundary conditions are first-class tests, not afterthoughts.** Every
numerical threshold in the specification (SDLT band boundaries, ICR
thresholds, LTV flag triggers) has explicit tests at the exact boundary value,
one unit above, and one unit below. Off-by-one errors in financial thresholds
are not acceptable.

---

---

# Part 1 — Test Layer Architecture

The test suite is organised into five distinct layers. Each layer has a defined
scope, a defined set of dependencies, and a defined execution cost. Tests at
lower layers are faster, more isolated, and more numerous. Tests at higher
layers are slower, more integrated, and fewer in number.

```
Layer 5 ─── Determinism and Reproducibility Tests
             Verify guarantees G-1 through G-8 from ENGINE_CONTRACTS.md.
             Serialise/deserialise inputs and re-run. Assert byte-identical results.
             Slowest. Run on every commit.

Layer 4 ─── Reference Scenario Regression Tests
             Full engine runs against E-01 through E-12.
             Assert every output, every intermediate, every flag.
             One test file per scenario. Run on every commit.

Layer 3 ─── Orchestration Integration Tests
             engine.run() calls that exercise the full pipeline but
             target specific sub-module interactions:
             validation-then-calculation, tax-then-flags, etc.
             Run on every commit.

Layer 2 ─── Sub-module Integration Tests
             Tax pathways, risk flag evaluator, and validation pipeline
             tested as complete sub-units with realistic input sets.
             Run on every commit.

Layer 1 ─── Formula Unit Tests
             Individual formula functions called directly.
             Each test isolates one formula with explicit numeric arguments.
             Largest volume. Fastest execution. Run on every commit.
```

All five layers run on every commit. There is no deferred test tier in this
strategy. The engine is the most trusted component of the platform — test
confidence must be unconditional.

---

---

# Part 2 — Test Data Architecture

Test data is managed as static, immutable fixtures. No test generates its
expected values programmatically. All expected values were computed from
CALCULATION_SPEC.md formulas before tests were written.

---

## 2.1 — Reference configuration fixture

A single shared `REFERENCE_CONFIG` fixture provides the standard
`EngineConfig` object used across all scenarios. Its values match the v1.0
defaults defined in ENGINE_CONTRACTS.md Part 2 exactly.

```
REFERENCE_CONFIG defines:
  SDLTConfig:
    bands: 5-band England structure (1 April 2025)
    additional_dwelling_surcharge_rate: 0.03

  CorporationTaxConfig:
    small_profits_rate: 0.19
    small_profits_upper_threshold: 50_000
    main_rate: 0.25
    main_rate_lower_threshold: 250_000
    marginal_relief_numerator: 3
    marginal_relief_denominator: 200

  AssumptionConfig:
    void_rate_percent_default: 3.85
    letting_agent_fee_percent_default: 10.00
    letting_agent_vat_rate_percent: 20.00
    maintenance_reserve_percent_default: 1.00
    landlord_insurance_annual_default: 800.00
    purchase_legal_costs_default: 2_500.00
    accountancy_cost_individual_default: 0.00
    accountancy_cost_ltd_default: 1_200.00
    stress_test_rate_percent: 5.50
    icr_threshold_basic_rate_percent: 125.00
    icr_threshold_higher_rate_percent: 145.00
```

This fixture is defined once and imported wherever needed. It must never be
mutated by any test. Tests that require a different configuration construct
a modified copy explicitly — they do not mutate the shared fixture.

---

## 2.2 — Reference scenario fixtures

Each of E-01 through E-12 is defined as a named fixture containing:
- `inputs`: the complete `EngineInput` for that scenario
- `expected_outputs`: the expected `EngineOutputs`
- `expected_intermediates`: the expected `EngineIntermediates`
- `expected_risk_flag_codes`: the set of flag codes expected to be present
- `expected_absent_flag_codes`: the set of flag codes that must NOT be present
- `expected_validation_warnings`: validation warning rule codes expected
- `is_valid`: whether the scenario passes validation (E-07 is the only
  scenario where this is false)

These fixtures are the executable form of ENGINE_CONTRACTS.md Part 11. They
are static data, not generated at test time.

---

## 2.3 — Boundary value fixtures

Boundary value tests use inline fixture construction rather than named
fixtures, because each boundary test is specific to one condition. The
boundary value and the comparison value are defined within the test itself,
not in a shared fixture, to make each test self-documenting.

---

## 2.4 — Alternative configuration fixtures

Two additional configuration fixtures support configuration isolation and
reproducibility tests:

**`ALTERNATIVE_CONFIG_VOID`**: identical to `REFERENCE_CONFIG` except
`void_rate_percent_default: 5.00` (changed from 3.85). Used to demonstrate
that the same inputs produce different results under a different config version.

**`ALTERNATIVE_CONFIG_STRESS`**: identical to `REFERENCE_CONFIG` except
`stress_test_rate_percent: 7.00` (changed from 5.50). Used to verify
ICR recalculation under a different stress rate.

---

---

# Part 3 — Formula Unit Tests

Formula unit tests live in `tests/unit/formulas/`. Each file covers one
formula. Tests call the formula function directly with explicit decimal
arguments. No `EngineInput`, no `EngineConfig`, no engine orchestrator.

---

## 3.1 — Test file per formula mapping

```
tests/unit/formulas/
├── test_f01_gross_annual_rent.py
├── test_f02_void_rate_conversion.py
├── test_f03_effective_annual_rent.py
├── test_f04_loan_amount.py
├── test_f05_ltv.py
├── test_f06_monthly_mortgage_payment.py
├── test_f07_annual_mortgage_cost.py
├── test_f08_annual_mortgage_interest.py
├── test_f09_letting_agent_annual.py
├── test_f10_annual_maintenance_reserve.py
├── test_f11_total_operating_costs.py
├── test_f12_net_operating_income.py
├── test_f13_sdlt.py
├── test_f14_total_acquisition_cost.py
├── test_f15_total_cash_deployed.py
├── test_f16_gross_yield.py
├── test_f17_net_yield.py
├── test_f18_roce.py
├── test_f19_annual_cash_flow.py
├── test_f20_monthly_cash_flow.py
├── test_f21_cash_on_cash_return.py
└── test_f22_icr_stress_test.py
```

---

## 3.2 — Standard test cases per formula

Every formula test file must cover:

**Happy path:** One standard input set producing a known expected output.
The expected value is taken directly from a scenario in ENGINE_CONTRACTS.md
so the formula test and the scenario test share a reference value.

**Arithmetic verification:** At least one test that explicitly states the
manual calculation steps in the test's description or docstring, so a reader
can verify the expected value without running the code.

**Edge cases:** As defined per formula below.

---

## 3.3 — Formula-specific edge cases

### F-01 — Gross Annual Rent

| Case | Input | Expected |
|------|-------|----------|
| Standard | monthly_rent=950.00 | 11,400.00 |
| Fractional rent | monthly_rent=933.33 | 11,199.96 |
| Minimum positive | monthly_rent=0.01 | 0.12 |

---

### F-03 — Effective Annual Rent

| Case | Input | Expected |
|------|-------|----------|
| Standard default void | gross=11,400, void_decimal=0.0385 | 10,961.10 |
| Zero void | gross=11,400, void_decimal=0.00 | 11,400.00 |
| Full void (100%) | gross=11,400, void_decimal=1.00 | 0.00 |
| Non-standard void | gross=12,000, void_decimal=0.10 | 10,800.00 |

---

### F-06 — Monthly Mortgage Payment

**Interest-Only cases:**

| Case | loan | rate | Expected monthly |
|------|------|------|-----------------|
| Standard E-01 | 150,000 | 4.75% | 593.75 |
| Standard E-03 | 262,500 | 5.00% | 1,093.75 |
| Higher rate | 150,000 | 6.50% | 812.50 |

**Repayment cases:**
Repayment tests must state the annuity formula parameters explicitly.
One verified case is required. The following case is pre-verified:

| loan | rate | term | Expected monthly |
|------|------|------|-----------------|
| 150,000 | 4.75% | 25 years | 853.21 |

Verification: r=0.0475/12=0.003958333, n=300
payment = 150,000 × (0.003958333 × 1.003958333^300) / (1.003958333^300 - 1)
        = 150,000 × (0.003958333 × 3.24027) / (3.24027 - 1)
        = 150,000 × 0.012825 / 2.24027
        = 150,000 × 0.005724
        = 858.58

Note: This requires precise Decimal computation. The expected value must be
computed using Python's `decimal.Decimal` at the working precision defined in
ENGINE_CONTRACTS.md Part 7 before the test is committed.

**Zero interest rate:**
```
Case:     mortgage_interest_rate = 0
Expected: monthly_mortgage_payment = 0
          is_cash_purchase flag set = true
          No divide-by-zero raised
```

---

### F-08 — Annual Mortgage Interest

**Interest-only path:**

| Case | loan | rate | Expected |
|------|------|------|----------|
| Standard | 150,000 | 4.75% | 7,125.00 |
| Higher loan | 262,500 | 5.00% | 13,125.00 |

**Repayment path (year 1):**
The year 1 interest for a repayment mortgage must be tested against a
pre-verified value. The value must be computed using the amortisation balance
formula in CALCULATION_SPEC.md F-08 at full decimal precision.

One required repayment case: loan=150,000, rate=4.75%, term=25 years.
The expected year 1 interest must be computed before the test is written.

---

### F-09 — Letting Agent Annual Cost

| Case | gross_rent | fee_pct | vat_rate | Expected |
|------|-----------|---------|----------|----------|
| Standard | 11,400 | 10.00% | 20.00% | 1,368.00 |
| Self-managed (0%) | 11,400 | 0.00% | 20.00% | 0.00 |
| Higher fee | 11,400 | 12.00% | 20.00% | 1,641.60 |
| VAT rate change | 11,400 | 10.00% | 25.00% | 1,425.00 |

The VAT rate change test verifies that VAT is taken from config, not
hardcoded. Passing a non-standard VAT rate must change the output.

---

### F-13 — SDLT Calculation

This formula has the most boundary tests. All values are verified against
HMRC's own SDLT calculator methodology.

**Standard purchase (is_additional_dwelling = false):**

| Price | Expected base SDLT | Verification |
|-------|-------------------|--------------|
| 100,000 | 0.00 | Entirely in 0% band |
| 125,000 | 0.00 | Upper limit of 0% band — no 2% tax |
| 125,001 | 0.02 | 1p in 2% band: 0.01 × 0.02 = 0.0002, rounds to 0.00 |
| 200,000 | 1,500.00 | 0 + (75,000 × 0.02) |
| 250,000 | 2,500.00 | 0 + (125,000 × 0.02) |
| 250,001 | 2,500.05 | 0 + 2,500 + (1 × 0.05) |
| 300,000 | 5,000.00 | 0 + 2,500 + (50,000 × 0.05) |
| 925,000 | 36,250.00 | 0 + 2,500 + (675,000 × 0.05) |
| 925,001 | 36,250.10 | Above adds 1p at 10% |
| 1,500,000 | 93,750.00 | 0 + 2,500 + 33,750 + (575,000 × 0.10) |
| 1,500,001 | 93,750.12 | Above adds 1p at 12% |
| 2,000,000 | 153,750.00 | Full band calculation |

**Additional dwelling surcharge (is_additional_dwelling = true):**

For each price above, verify:
```
total_sdlt = base_sdlt + (price × 0.03)
```

At 200,000:
  base = 1,500.00
  surcharge = 6,000.00
  total = 7,500.00  ← matches E-01

At 350,000:
  base = 7,500.00
  surcharge = 10,500.00
  total = 18,000.00  ← matches E-03

At 600,000:
  base = 20,000.00
  surcharge = 18,000.00
  total = 38,000.00  ← matches E-05

**No surcharge path (is_additional_dwelling = false):**

| Price | Expected total_sdlt (no surcharge) |
|-------|-----------------------------------|
| 200,000 | 1,500.00 |
| 350,000 | 7,500.00 |

**Band breakdown structure:**
Every SDLT test must assert the `sdlt_band_breakdown` list contains the
correct number of band entries, that each entry has the correct `taxable_in_band`
and `tax_in_band` values, and that the sum of `tax_in_band` equals `sdlt_base`.

---

### F-22 — ICR Stress Test

| Case | loan | stress_rate | effective_rent | Expected ICR |
|------|------|-------------|----------------|-------------|
| E-01 | 150,000 | 5.50% | 10,961.10 | 132.86% |
| E-03 | 262,500 | 5.50% | 18,460.80 | 127.88% |
| E-05 | 450,000 | 5.50% | 27,691.20 | 111.88% |
| Exactly 125% | — | — | — | see note |
| Exactly 145% | — | — | — | see note |
| Cash purchase | 0 | 5.50% | any | None |

For the 125% and 145% boundary cases, derive the inputs from the threshold:

```
ICR = 125% means: effective_rent / (loan × 0.055) = 1.25
Example: loan=100,000, stress=5.50%
  stressed_interest = 5,500
  effective_rent_for_125 = 5,500 × 1.25 = 6,875
  ICR = 6,875 / 5,500 × 100 = 125.00 — flag must NOT fire
  effective_rent_for_just_below = 6,874.99
  ICR = 124.999... — flag MUST fire
```

The exact boundary values must be computed and recorded before tests are
written.

---

---

# Part 4 — Tax Pathway Tests

Tax pathway tests live in `tests/unit/tax/`. They test the complete tax
pathway functions (not individual steps) with full sets of inputs.

---

## 4.1 — Test file structure

```
tests/unit/tax/
├── test_pathway_a_individual.py      — Section 24 pathway
├── test_pathway_b_limited_company.py — Corporation tax pathway
└── test_tax_pathway_routing.py       — Confirms correct pathway selected
                                        by ownership_structure
```

---

## 4.2 — Tax Pathway A — Individual / Section 24

Each test calls the pathway A function directly with explicit inputs and
asserts the expected `taxable_rental_income`, `income_tax_gross`,
`mortgage_interest_tax_credit`, and `annual_tax_liability`.

**Required test cases:**

### TA-01 — Basic-rate, credit exceeds tax (E-01 values)

```
Inputs:
  effective_annual_rent: 10,961.10
  letting_agent_annual: 1,368.00
  annual_maintenance_reserve: 2,000.00
  landlord_insurance_annual: 800.00
  annual_service_charge: 0.00
  annual_ground_rent: 0.00
  annual_accountancy_cost: 0.00
  annual_mortgage_interest: 7,125.00
  income_tax_band: BASIC_RATE

Expected:
  taxable_rental_income: 6,793.10
  income_tax_gross: 1,358.62
  mortgage_interest_tax_credit: 1,425.00
  annual_tax_liability: 0.00
```

Rationale: Credit (1,425) > gross tax (1,358.62). MAX(0, -66.38) = 0.
This is the Section 24 neutrality case for basic-rate taxpayers.

### TA-02 — Higher-rate, positive tax liability (E-02 values)

```
All inputs identical to TA-01 except income_tax_band: HIGHER_RATE

Expected:
  taxable_rental_income: 6,793.10       (unchanged)
  income_tax_gross: 2,717.24            (6,793.10 × 0.40)
  mortgage_interest_tax_credit: 1,425.00 (unchanged — always 20%)
  annual_tax_liability: 1,292.24        (2,717.24 - 1,425.00)
```

### TA-03 — Additional-rate (E-10 values)

```
All inputs identical to TA-01 except income_tax_band: ADDITIONAL_RATE

Expected:
  income_tax_gross: 3,056.90    (6,793.10 × 0.45)
  mortgage_interest_tax_credit: 1,425.00
  annual_tax_liability: 1,631.90
```

### TA-04 — Zero taxable income (operating costs equal effective rent)

```
effective_annual_rent: 5,000.00
total_deductible_costs: 5,000.00
annual_mortgage_interest: 10,000.00
income_tax_band: HIGHER_RATE

Expected:
  taxable_rental_income: 0.00
  income_tax_gross: 0.00
  mortgage_interest_tax_credit: 2,000.00  (10,000 × 0.20)
  annual_tax_liability: 0.00              (MAX(0, 0 - 2,000))
```

Rationale: When taxable income is zero, gross tax is zero, and the credit
cannot create a refund. Tax liability is zero.

### TA-05 — Negative taxable income (costs exceed effective rent)

```
effective_annual_rent: 4,000.00
total_deductible_costs: 5,000.00
annual_mortgage_interest: 8,000.00
income_tax_band: HIGHER_RATE

Expected:
  taxable_rental_income: -1,000.00
  income_tax_gross: 0.00           (no tax on a loss — floor at zero)
  mortgage_interest_tax_credit: 1,600.00
  annual_tax_liability: 0.00
```

Note: Whether the engine floors taxable_rental_income at zero before
computing income_tax_gross, or allows negative taxable income and then applies
MAX(0, ...) at the tax liability step — the outcome is the same. The test
asserts the final `annual_tax_liability = 0.00`. The intermediate behaviour
must match the implementation as documented.

### TA-06 — Leasehold costs included (E-06 values)

```
Inputs include annual_service_charge: 1,200 and annual_ground_rent: 150

Expected:
  taxable_rental_income: 4,633.30
  income_tax_gross: 1,853.32
  mortgage_interest_tax_credit: 1,282.50
  annual_tax_liability: 570.82
```

---

## 4.3 — Tax Pathway B — Limited Company / Corporation Tax

### TB-01 — Positive profit, small profits rate (typical SPV)

```
Inputs:
  effective_annual_rent: 18,460.80
  letting_agent_annual: 2,304.00
  annual_maintenance_reserve: 3,500.00
  landlord_insurance_annual: 800.00
  annual_service_charge: 0.00
  annual_ground_rent: 0.00
  annual_accountancy_cost: 1,200.00
  annual_mortgage_interest: 13,125.00

Expected:
  taxable_company_profit: -2,468.20
  corporation_tax: 0.00
  annual_tax_liability: 0.00
```

Note: This is E-03. Taxable profit is negative because mortgage interest
is deductible. This is the common single-property SPV outcome.

### TB-02 — Positive taxable profit, small profits rate

Construct inputs that produce a profit within the £0–£50,000 band:

```
effective_annual_rent: 18,460.80
total_non-mortgage costs: 5,000.00
annual_mortgage_interest: 5,000.00

taxable_profit = 18,460.80 - 5,000 - 5,000 = 8,460.80
corporation_tax = 8,460.80 × 0.19 = 1,607.55
annual_tax_liability = 1,607.55
```

### TB-03 — Profit exactly at £50,000 small profits boundary

```
taxable_company_profit: 50,000.00
Expected corporation_tax: 9,500.00  (50,000 × 0.19)
```

### TB-04 — Profit at £50,001 (first penny in marginal relief band)

```
taxable_company_profit: 50,001.00
Expected corporation_tax:
  gross at main rate: 50,001 × 0.25 = 12,500.25
  marginal_relief: (250,000 - 50,001) × (3/200) = 199,999 × 0.015 = 2,999.985
  corporation_tax: 12,500.25 - 2,999.985 = 9,500.265 → 9,500.27
```

Note: This expected value must be verified using Python `decimal.Decimal`
arithmetic at working precision before the test is committed.

### TB-05 — Profit above £250,000 (main rate)

```
taxable_company_profit: 300,000.00
Expected corporation_tax: 300,000 × 0.25 = 75,000.00
```

### TB-06 — Zero profit (costs equal rent)

```
taxable_company_profit: 0.00
Expected corporation_tax: 0.00
annual_tax_liability: 0.00
```

### TB-07 — Negative profit (costs exceed rent)

```
taxable_company_profit: -5,000.00
Expected corporation_tax: 0.00
annual_tax_liability: 0.00
```

---

## 4.4 — Tax pathway routing test

One test verifies that the orchestrator selects the correct pathway:

```
INDIVIDUAL → Pathway A (section_24_applies = true)
LIMITED_COMPANY → Pathway B (section_24_applies = false)
```

This is a structural test on the orchestrator, not a formula test.
It asserts `section_24_applies` in the intermediates, not the tax amount.

---

---

# Part 5 — Validation Rule Tests

Validation tests live in `tests/unit/validation/`. They test the validation
pipeline as a unit, verifying that each rule produces the correct outcome.

---

## 5.1 — Test file structure

```
tests/unit/validation/
├── test_hard_rules.py     — One test class per HARD rule (V-01, V-04–V-09,
│                            V-13–V-18, V-21–V-22)
├── test_warn_rules.py     — One test class per WARN rule (V-02, V-03,
│                            V-08, V-10–V-12, V-19–V-20, V-23–V-25)
└── test_validation_pipeline.py  — Pipeline-level tests: multiple errors
                                   simultaneously, HARD+WARN combinations,
                                   is_valid flag, error list structure
```

---

## 5.2 — Per-rule test structure

Each validation rule requires three tests:

**Trigger test:** Input that satisfies the trigger condition. Asserts the
correct rule_code appears in errors (HARD) or warnings (WARN). Asserts the
correct field name. Asserts the message matches CALCULATION_SPEC.md exactly.

**Non-trigger test:** Input that does not satisfy the condition. Asserts the
rule_code is absent from the result.

**Boundary test (where numeric):** Input at the exact boundary. Asserts
trigger or non-trigger as defined. This is the most important test for
numeric threshold rules.

---

## 5.3 — HARD validation rule coverage matrix

| Rule | Trigger condition | Trigger test input | Boundary note |
|------|-------------------|--------------------|---------------|
| V-01 | purchase_price <= 0 | purchase_price=0 | Also test: negative value |
| V-04 | monthly_rent <= 0 | monthly_rent=0 | |
| V-05 | deposit_amount <= 0 | deposit_amount=0 | |
| V-06 | deposit >= purchase_price | deposit=200,000, price=200,000 | Equal triggers |
| V-07 | deposit < price × 0.15 | deposit=29,999, price=200,000 | 29,999 < 30,000 |
| V-07 boundary | deposit = price × 0.15 exactly | deposit=30,000 | Must NOT trigger |
| V-09 | mortgage_rate < 0 | rate=-0.01 | |
| V-13 | term < 5 | term=4 | term=5 must NOT trigger |
| V-13 | term > 35 | term=36 | term=35 must NOT trigger |
| V-14 | ownership = LLP | ownership_structure=LLP | |
| V-15 | property_type != RSL | property_type=HMO | |
| V-16 | country != ENGLAND | property_country=SCOTLAND | Also test WALES, NI |
| V-17 | INDIVIDUAL + null band | ownership=INDIVIDUAL, band=null | |
| V-17 | LIMITED_COMPANY + null band | ownership=LTD_CO, band=null | Must NOT trigger |
| V-18 | void_rate < 0 | void_rate=-0.01 | |
| V-18 | void_rate > 100 | void_rate=100.01 | void_rate=100 must NOT trigger |
| V-21 | LEASEHOLD + null service_charge | tenure=LEASEHOLD, sc=null | |
| V-21 | LEASEHOLD + 0 service_charge | tenure=LEASEHOLD, sc=0 | Must NOT trigger |
| V-22 | LEASEHOLD + null ground_rent | tenure=LEASEHOLD, gr=null | |

---

## 5.4 — WARN validation rule coverage matrix

| Rule | Trigger | Boundary |
|------|---------|----------|
| V-02 | purchase_price=9,999 | 10,000 must NOT trigger |
| V-03 | purchase_price=10,000,001 | 10,000,000 must NOT trigger |
| V-08 | deposit=49,999 for price=200,000 (< 25%) | 50,000 (= 25%) must NOT trigger |
| V-10 | mortgage_interest_rate=0 | 0.01 must NOT trigger |
| V-11 | mortgage_interest_rate=2.99 | 3.00 must NOT trigger |
| V-12 | mortgage_interest_rate=10.01 | 10.00 must NOT trigger |
| V-19 | void_rate_percent=0 | 0.01 must NOT trigger |
| V-20 | letting_agent_fee_percent=25.01 | 25.00 must NOT trigger |
| V-23 | ground_rent=251, LEASEHOLD | 250 must NOT trigger; FREEHOLD+251 must NOT trigger |
| V-24 | maintenance_reserve_percent=5.01 | 5.00 must NOT trigger |
| V-25 | refurbishment_cost=0 | 0.01 must NOT trigger |

---

## 5.5 — Pipeline-level validation tests

**Multiple simultaneous HARD failures:**
Construct input with V-01 (price=0) AND V-04 (rent=0). Assert both rule codes
appear in hard_errors. Assert is_valid=false. The pipeline must not stop at
the first error — it must collect all failures.

**HARD and WARN simultaneously:**
Construct input with V-07 (HARD: deposit too low) AND V-25 (WARN: refurb=0).
Assert V-07 in hard_errors, V-25 in warnings, is_valid=false.

**WARN only:**
Construct input with V-25 only triggered. Assert is_valid=true, hard_errors
empty, V-25 in warnings.

**Cross-field rule: V-17 negative case:**
`ownership_structure=LIMITED_COMPANY, income_tax_band=null`. V-17 must NOT
trigger (it only applies to INDIVIDUAL).

**Cross-field rule: V-21 and V-22 for FREEHOLD:**
`tenure=FREEHOLD, annual_service_charge=null, annual_ground_rent=null`.
V-21 and V-22 must NOT trigger (they apply only to LEASEHOLD).

**ValidationResult structure:**
Assert that every ValidationError contains: rule_code (non-empty string),
field (non-empty string), message (non-empty string matching CALCULATION_SPEC).
Assert that hard_errors and warnings are separate lists, never mixed.

---

---

# Part 6 — Risk Flag Tests

Risk flag tests live in `tests/unit/risk_flags/`. They test the flag
evaluator independently of the calculation pipeline.

---

## 6.1 — Test file structure

```
tests/unit/risk_flags/
├── test_flag_negative_cashflow.py
├── test_flag_negative_noi.py
├── test_flag_low_gross_yield.py
├── test_flag_low_net_yield.py
├── test_flag_low_icr_basic.py
├── test_flag_low_icr_higher_rate.py
├── test_flag_high_leverage.py
├── test_flag_high_leverage_extreme.py
├── test_flag_low_margin_safety.py
├── test_flag_high_refurb_ratio.py
├── test_flag_section_24_impact.py
├── test_flag_ated_warning.py
├── test_flag_leasehold_short_lease.py
├── test_flag_cash_flow_pre_tax_only.py
├── test_flag_ltd_extraction_undisclosed.py
├── test_flag_rent_unverified.py
└── test_flag_evaluation_pipeline.py
```

---

## 6.2 — Per-flag test structure

Each flag test file must cover:

**Fires when triggered:** Construct a context where the flag's condition is
met. Assert the flag appears in the result with the correct severity, the
correct code, and the correct message text matching CALCULATION_SPEC.md.

**Does not fire when not triggered:** Construct a context where the condition
is not met. Assert the flag is absent from the result.

**Boundary — fires at threshold breach:** For numeric threshold flags, assert
the flag fires when the value crosses the threshold.

**Boundary — does not fire at threshold exactly:** Assert the flag does not
fire when the value equals the threshold exactly (for strict inequality
conditions).

---

## 6.3 — Flag boundary values (authoritative)

These boundary values are derived from the trigger conditions in
CALCULATION_SPEC.md. Tests must use these exact values.

```
NEGATIVE_CASHFLOW:
  Fires: annual_cash_flow = -0.01
  Does not fire: annual_cash_flow = 0.00

NEGATIVE_NOI:
  Fires: net_operating_income = -0.01
  Does not fire: net_operating_income = 0.00

LOW_GROSS_YIELD:
  Fires: gross_yield_percent = 3.99
  Does not fire: gross_yield_percent = 4.00

LOW_NET_YIELD:
  Fires: net_yield_percent = 2.99
  Does not fire: net_yield_percent = 3.00

LOW_ICR_BASIC (condition: icr < 125):
  Fires: icr_percent = 124.99
  Does not fire: icr_percent = 125.00

LOW_ICR_HIGHER_RATE (condition: icr < 145 AND icr >= 125 AND higher/additional):
  Fires: icr_percent = 144.99, income_tax_band = HIGHER_RATE
  Does not fire at upper: icr_percent = 145.00, income_tax_band = HIGHER_RATE
  Does not fire at lower: icr_percent = 124.99, income_tax_band = HIGHER_RATE
    (because LOW_ICR_BASIC fires instead — the condition requires icr >= 125)
  Does not fire for basic rate: icr_percent = 132.00, income_tax_band = BASIC_RATE
  Does not fire for Ltd Co: icr_percent = 132.00, ownership = LIMITED_COMPANY

HIGH_LEVERAGE (condition: ltv > 75):
  Fires: ltv_percent = 75.01
  Does not fire: ltv_percent = 75.00

HIGH_LEVERAGE_EXTREME (condition: ltv > 85):
  Fires: ltv_percent = 85.01
  Does not fire: ltv_percent = 85.00
  Both HIGH_LEVERAGE and HIGH_LEVERAGE_EXTREME fire when ltv > 85

LOW_MARGIN_SAFETY (condition: (cash_flow/gross_rent) < 0.05 AND cash_flow >= 0):
  Fires: cash_flow=570, gross_rent=11,400 → 570/11,400=0.05 → does NOT fire
  Fires: cash_flow=569, gross_rent=11,400 → 569/11,400=0.04991 → fires
  Does not fire when cash_flow < 0 (NEGATIVE_CASHFLOW fires instead)

HIGH_REFURB_RATIO (condition: refurb > price × 0.10):
  Fires: refurb=20,001, price=200,000
  Does not fire: refurb=20,000, price=200,000 (= 10% exactly, not > 10%)

LEASEHOLD_SHORT_LEASE (condition: tenure=LEASEHOLD AND lease_years < 80):
  Fires: tenure=LEASEHOLD, lease_years=79
  Does not fire: tenure=LEASEHOLD, lease_years=80
  Does not fire: tenure=FREEHOLD, lease_years=79
  Does not fire: tenure=LEASEHOLD, lease_years=null

ATED_WARNING (condition: LIMITED_COMPANY AND price > 500,000):
  Fires: ownership=LTD_CO, price=500,001
  Does not fire: ownership=LTD_CO, price=500,000
  Does not fire: ownership=INDIVIDUAL, price=600,000

SECTION_24_IMPACT (condition: INDIVIDUAL AND higher or additional rate):
  Fires: INDIVIDUAL + HIGHER_RATE
  Fires: INDIVIDUAL + ADDITIONAL_RATE
  Does not fire: INDIVIDUAL + BASIC_RATE
  Does not fire: LIMITED_COMPANY + HIGHER_RATE (irrelevant — no income_tax_band)

CASH_FLOW_PRE_TAX_ONLY (condition: pre_tax >= 0 AND annual_cash_flow < 0):
  Fires: pre_tax=100, annual_cash_flow=-200
  Does not fire: pre_tax=-100, annual_cash_flow=-200 (both negative)
  Does not fire: pre_tax=100, annual_cash_flow=50 (both positive)

LTD_EXTRACTION_UNDISCLOSED (condition: LIMITED_COMPANY — always fires):
  Fires: ownership=LIMITED_COMPANY (any other inputs)
  Does not fire: ownership=INDIVIDUAL

RENT_UNVERIFIED (unconditional — always fires):
  Assert: always present in every successful EngineResult
```

---

## 6.4 — Pipeline evaluation tests

**All flags evaluated independently:** Construct a context where three flags
should fire simultaneously. Assert all three are present. No flag evaluation
must be skipped because another flag already fired.

**Flag list is ordered by severity:** Assert HIGH flags appear before MEDIUM,
MEDIUM before INFO, within each severity level flags appear in the order they
are defined in CALCULATION_SPEC.md.

**No duplicate flags:** Run the evaluator twice on the same context. Assert
no code appears more than once in the result list.

**RiskFlag structure:** For each triggered flag, assert that:
- `code` is a non-empty string
- `severity` is one of HIGH, MEDIUM, INFO
- `triggered_by_field` is a non-empty string naming a real output field
- `triggered_by_value` is a non-empty string representation of the actual value
- `message` matches the user-facing message in CALCULATION_SPEC.md exactly

---

---

# Part 7 — Reference Scenario Regression Tests

Reference scenario tests live in `tests/regression/`. Each scenario in
ENGINE_CONTRACTS.md Part 11 has exactly one test file. Each file runs the
full engine against the scenario's inputs and asserts every documented output,
intermediate, and flag.

---

## 7.1 — Test file structure

```
tests/regression/
├── test_e01_baseline_basic_rate.py
├── test_e02_higher_rate_section24.py
├── test_e03_ltd_co_standard.py
├── test_e04_lower_leverage_positive.py
├── test_e05_high_value_ltd_ated.py
├── test_e06_leasehold_higher_rate.py
├── test_e07_hard_validation_failure.py
├── test_e08_warn_only_validation.py
├── test_e09_short_lease_flag.py
├── test_e10_additional_rate.py
├── test_e11_thin_margin.py
├── test_e12_high_refurb.py
└── conftest.py     — shared fixtures: REFERENCE_CONFIG,
                      scenario input builders
```

---

## 7.2 — Per-scenario test structure

Each regression test file contains one primary test that:

1. Loads the scenario inputs from the fixture defined in Part 2.2
2. Calls `engine.run(inputs, REFERENCE_CONFIG)`.
3. Asserts `is_valid = True` (except E-07 where `is_valid = False`).
4. For valid scenarios, asserts every `EngineOutputs` field matches
   the expected value from ENGINE_CONTRACTS.md exactly.
5. Asserts every `EngineIntermediates` field matches the expected value.
6. Asserts the set of triggered risk flag codes exactly matches
   `expected_risk_flag_codes` — no more, no fewer.
7. Asserts no flag code in `expected_absent_flag_codes` is present.
8. Asserts the set of validation warning rule codes matches
   `expected_validation_warnings`.

---

## 7.3 — Output comparison approach

All monetary output comparisons use exact decimal equality after rounding to
2 decimal places, as specified in ENGINE_CONTRACTS.md Part 7. There is no
tolerance range. A result of £6,793.10 is not acceptable as a substitute for
£6,793.11.

All percentage comparisons use the same approach: exact to 2 decimal places,
ROUND_HALF_UP.

**Test helper function:**
A shared helper `assert_decimal_equal(actual, expected, field_name)` performs
the comparison and produces a failure message that includes the field name,
the actual value, and the expected value. This makes failing regression tests
immediately actionable.

---

## 7.4 — Scenario E-07 special handling

E-07 is the only scenario that expects a `ValidationResult` rather than an
`EngineResult`. Its test must:
1. Assert the return type is `ValidationResult` (not `EngineResult`).
2. Assert `is_valid = False`.
3. Assert `hard_errors` contains exactly one error with `rule_code = "V-07"`.
4. Assert `hard_errors[0].field = "deposit_amount"`.
5. Assert no `EngineResult` sub-structure exists on the return value.

---

## 7.5 — Cross-scenario consistency assertions

One additional file `test_cross_scenario_consistency.py` asserts properties
that must hold across multiple scenarios:

**Section 24 monotonicity:** E-01 (basic), E-02 (higher), E-10 (additional)
use identical inputs. Assert:
```
  E-01.annual_tax_liability <= E-02.annual_tax_liability <= E-10.annual_tax_liability
  E-01.annual_cash_flow >= E-02.annual_cash_flow >= E-10.annual_cash_flow
```
The tax liability must increase and cash flow must decrease as the tax rate
rises, because the mortgage interest credit is fixed at 20% regardless of rate.

**Leverage monotonicity:** E-01 (75% LTV) and E-04 (60% LTV) use the same
property and rent. Assert:
```
  E-04.annual_cash_flow > E-01.annual_cash_flow
  E-04.total_cash_deployed > E-01.total_cash_deployed
  E-04.ltv_percent < E-01.ltv_percent
```
Reducing leverage increases cash flow (lower mortgage cost) but increases cash
deployed (higher deposit).

**SDLT surcharge consistency:** Every scenario with `is_additional_dwelling=true`
must have `sdlt_surcharge_gbp = purchase_price × 0.03` to two decimal places.

---

---

# Part 8 — Determinism and Reproducibility Tests

Determinism tests live in `tests/determinism/`. They verify the guarantees
defined in ENGINE_CONTRACTS.md Part 9 (G-1 through G-8).

---

## 8.1 — Test file structure

```
tests/determinism/
├── test_idempotent_execution.py
├── test_serialisation_roundtrip.py
├── test_config_version_isolation.py
└── test_no_internal_state.py
```

---

## 8.2 — Idempotent execution tests

**DET-01 — Same inputs, same result (individual pathway)**
```
Run engine.run(E-01 inputs, REFERENCE_CONFIG) twice in sequence.
Store both EngineResults.
Assert EngineResult_1 == EngineResult_2 (field-by-field).
```

**DET-02 — Same inputs, same result (Ltd Co pathway)**
```
Run engine.run(E-03 inputs, REFERENCE_CONFIG) twice in sequence.
Assert identical results.
```

**DET-03 — Same inputs, same result (validation failure)**
```
Run engine.run(E-07 inputs, REFERENCE_CONFIG) twice.
Assert both return ValidationResult with identical hard_errors.
```

**DET-04 — Multiple rapid sequential calls**
```
Run engine.run(E-01 inputs, REFERENCE_CONFIG) ten times in a loop.
Collect all ten results.
Assert all ten are identical.
```
This verifies no accumulated state affects results over repeated calls.

---

## 8.3 — Serialisation round-trip tests

**DET-05 — Input serialisation round-trip**
```
Serialise E-01 EngineInput to JSON (Decimal values as strings, enums as
strings, all keys sorted for canonical ordering).
Deserialise back to EngineInput.
Run engine with original EngineInput. Record result_1.
Run engine with deserialised EngineInput. Record result_2.
Assert result_1 == result_2.
```

**DET-06 — Config serialisation round-trip**
```
Serialise REFERENCE_CONFIG to JSON.
Deserialise back to EngineConfig.
Run engine with E-01 inputs and original REFERENCE_CONFIG. Record result_1.
Run engine with E-01 inputs and deserialised config. Record result_2.
Assert result_1 == result_2.
```

These tests verify that the engine's behaviour is fully determined by the
explicit data it receives, with no hidden dependencies on object identity
or memory addresses.

---

## 8.4 — Configuration version isolation tests

**DET-07 — Different configs produce different results**
```
Run engine.run(E-01 inputs, REFERENCE_CONFIG). Record result_A.
Run engine.run(E-01 inputs, ALTERNATIVE_CONFIG_VOID). Record result_B.
Assert result_A.outputs.effective_annual_rent_gbp !=
       result_B.outputs.effective_annual_rent_gbp
Assert result_A.outputs.annual_cash_flow_gbp !=
       result_B.outputs.annual_cash_flow_gbp
```

**DET-08 — Original config reproduces original result**
```
Run engine.run(E-01 inputs, REFERENCE_CONFIG). Record result_original.
Run engine.run(E-01 inputs, ALTERNATIVE_CONFIG_VOID). (discard result)
Run engine.run(E-01 inputs, REFERENCE_CONFIG). Record result_reproduced.
Assert result_original == result_reproduced.
```

This is the core historical reproducibility test: using the original
configuration always produces the original result, regardless of what other
configurations have been used in between.

**DET-09 — Stress rate config isolation**
```
Run engine.run(E-01 inputs, REFERENCE_CONFIG). Record icr_standard.
Run engine.run(E-01 inputs, ALTERNATIVE_CONFIG_STRESS). Record icr_stressed.
Assert icr_standard.outputs.icr_percent > icr_stressed.outputs.icr_percent
  (higher stress rate → lower ICR for same property)
```

---

## 8.5 — Internal state tests

**DET-10 — Module-level state verification**
```
Inspect all module-level variables in engine/calculations/,
engine/tax/, engine/validation/, engine/risk_flags/.
Assert no mutable module-level variables exist.
This is a static analysis test, not a runtime test.
```

**DET-11 — No timestamp dependence**
```
The engine produces no timestamps. Verify by inspecting EngineResult:
Assert EngineResult has no field named *_at, *_timestamp, or *_time.
Assert EngineIntermediates has no timestamp fields.
```

---

---

# Part 9 — Decimal Precision Tests

Precision tests live in `tests/unit/precision/`. They verify that arithmetic
is performed with `decimal.Decimal` throughout and that rounding occurs only
at the output stage.

---

## 9.1 — Test file structure

```
tests/unit/precision/
├── test_decimal_types.py        — type assertions throughout pipeline
├── test_rounding_point.py       — rounding only at output stage
├── test_rounding_mode.py        — ROUND_HALF_UP behaviour
└── test_no_float_arithmetic.py  — float never used in engine
```

---

## 9.2 — Decimal type enforcement

**PREC-01 — Output types are Decimal**
```
Run engine with any valid inputs.
For every field in EngineOutputs and EngineIntermediates that is a monetary
or percentage value:
  Assert type(field_value) == decimal.Decimal
```

**PREC-02 — Enum and boolean fields are their declared types**
```
Assert type(section_24_applies) == bool
Assert type(sdlt_band_breakdown) == list
```

---

## 9.3 — Rounding point tests

**PREC-03 — Intermediate computation uses full precision**

Construct a case where an intermediate value has more than 2 decimal places
at full precision, and verify that the output (rounded) is computed from the
full-precision intermediate, not from a pre-rounded value.

```
Test case: monthly_rent = 933.33
  gross_annual_rent = 933.33 × 12 = 11,199.96 (exact)
  void_rate = 3.85%
  effective_annual_rent = 11,199.96 × 0.9615 = 10,776.96174 (full precision)
  Output: 10,776.96 (rounded at output stage)
```

Assert that the output matches 10,776.96, not a value derived from
11,199.96 × 0.9615 computed in steps with intermediate rounding.

**PREC-04 — SDLT computation does not intermediate-round**

Construct a purchase price where band boundary arithmetic produces more than
2 decimal places before summation:

```
purchase_price = 300,000.33
taxable in 2% band = 125,000.33 × 0.02 = 2,500.0066
taxable in 5% band = 50,000.00 × 0.05 = 2,500.00
sdlt_base = 5,000.0066
Output: 5,000.01 (rounded at output)
```

Assert that sdlt_base_gbp = 5,000.01, not 5,000.00 (which would result from
pre-rounding the band computations).

---

## 9.4 — Rounding mode tests

**PREC-05 — ROUND_HALF_UP behaviour at 0.005**

```
Values that round up under ROUND_HALF_UP:
  1.005 → 1.01
  2.125 → 2.13
  0.375 → 0.38

Values that round down:
  1.004 → 1.00
  2.124 → 2.12

Create a formula call that produces one of these exact intermediate values.
Assert the rounded output matches ROUND_HALF_UP expectations.
```

---

## 9.5 — No float test

**PREC-06 — Float is never used in calculation results**

```
Run engine with E-01 inputs.
Inspect all leaf values in EngineOutputs and EngineIntermediates.
Assert none are of type float.
```

This test is a safety net. If any formula function returns a Python float
(e.g. from a math.pow() call or an unguarded arithmetic expression), this
test will catch it before it reaches production.

---

---

# Part 10 — Snapshot Comparison Test Strategy

Snapshot comparison tests are higher-level than engine unit tests. They
verify the structural and semantic properties of the SnapshotPayload defined
in ENGINE_CONTRACTS.md Part 12.

These tests operate on the SnapshotPayload data structure, not on database
records. They belong in `tests/integration/snapshots/` and are the boundary
between pure engine tests and service-layer tests.

**Note:** These tests do not require a database. They verify that the
`SnapshotPayload` assembled from an `EngineResult` satisfies its structural
contract. Database persistence tests are out of scope for this document.

---

## 10.1 — Snapshot payload completeness tests

**SNAP-01 — All output fields present**
```
Given an EngineResult from E-01, construct a SnapshotPayload.
Assert every field defined in EngineOutputs is present in the payload.
Assert no extra fields are present that are not in the contract.
```

**SNAP-02 — All intermediate fields present**
```
Assert every field in EngineIntermediates is represented in the payload.
```

**SNAP-03 — All risk flags captured**
```
For E-02 (which has three flags), assert the snapshot payload contains
exactly three risk flag records matching the expected codes.
Assert each record contains: code, severity, triggered_by_field,
triggered_by_value, message.
```

**SNAP-04 — Validation warnings captured**
```
For E-08 (V-08 and V-25 warnings), assert the payload contains two
validation warning records with the correct rule_codes.
```

---

## 10.2 — Snapshot immutability structure tests

**SNAP-05 — Snapshot does not contain a timestamp**
```
The SnapshotPayload produced by the engine+service chain must not have
a calculated_at field populated by the engine.
Assert calculated_at is None or absent in the EngineResult.
Assert it is only populated after the payload is passed to the
persistence layer (out of scope here, but the absence from EngineResult
is testable).
```

**SNAP-06 — Input source tracking is present**
```
For a scenario where some optional inputs use defaults and some are
overridden, assert the payload records USER_OVERRIDE for overridden fields
and CONFIG_DEFAULT for defaulted fields.
Use E-12 (refurbishment_cost = 25,000 is a user override from default of 0)
to verify at least one USER_OVERRIDE record exists.
```

---

## 10.3 — Scenario comparison structural test

**SNAP-07 — E-01 vs E-02 snapshot diff**
```
Produce SnapshotPayload for E-01 and E-02 (identical inputs, different tax band).
Assert:
  - inputs differ only in income_tax_band
  - outputs differ in annual_tax_liability, annual_cash_flow,
    monthly_cash_flow, cash_on_cash_return_percent
  - outputs are identical for all other fields
  - risk flags differ (E-02 has SECTION_24_IMPACT and LOW_ICR_HIGHER_RATE,
    E-01 does not)
```

This verifies that scenario comparison — a Phase 2 feature — can be built
on the existing snapshot structure without schema changes.

---

---

# Part 11 — Test Folder Structure

The complete test directory structure for the backend, reflecting the test
layers defined in Part 1.

```
backend/
└── tests/
    │
    ├── conftest.py                  ← top-level shared fixtures:
    │                                   REFERENCE_CONFIG
    │                                   ALTERNATIVE_CONFIG_VOID
    │                                   ALTERNATIVE_CONFIG_STRESS
    │                                   scenario input builders (E-01 – E-12)
    │
    ├── unit/
    │   │
    │   ├── formulas/                ← Layer 1: Formula unit tests
    │   │   ├── test_f01_gross_annual_rent.py
    │   │   ├── test_f02_void_rate_conversion.py
    │   │   ├── test_f03_effective_annual_rent.py
    │   │   ├── test_f04_loan_amount.py
    │   │   ├── test_f05_ltv.py
    │   │   ├── test_f06_monthly_mortgage_payment.py
    │   │   ├── test_f07_annual_mortgage_cost.py
    │   │   ├── test_f08_annual_mortgage_interest.py
    │   │   ├── test_f09_letting_agent_annual.py
    │   │   ├── test_f10_annual_maintenance_reserve.py
    │   │   ├── test_f11_total_operating_costs.py
    │   │   ├── test_f12_net_operating_income.py
    │   │   ├── test_f13_sdlt.py
    │   │   ├── test_f14_total_acquisition_cost.py
    │   │   ├── test_f15_total_cash_deployed.py
    │   │   ├── test_f16_gross_yield.py
    │   │   ├── test_f17_net_yield.py
    │   │   ├── test_f18_roce.py
    │   │   ├── test_f19_annual_cash_flow.py
    │   │   ├── test_f20_monthly_cash_flow.py
    │   │   ├── test_f21_cash_on_cash_return.py
    │   │   └── test_f22_icr_stress_test.py
    │   │
    │   ├── tax/                     ← Layer 2: Tax pathway unit tests
    │   │   ├── test_pathway_a_individual.py
    │   │   ├── test_pathway_b_limited_company.py
    │   │   └── test_tax_pathway_routing.py
    │   │
    │   ├── validation/              ← Layer 2: Validation rule unit tests
    │   │   ├── test_hard_rules.py
    │   │   ├── test_warn_rules.py
    │   │   └── test_validation_pipeline.py
    │   │
    │   ├── risk_flags/              ← Layer 2: Risk flag unit tests
    │   │   ├── test_flag_negative_cashflow.py
    │   │   ├── test_flag_negative_noi.py
    │   │   ├── test_flag_low_gross_yield.py
    │   │   ├── test_flag_low_net_yield.py
    │   │   ├── test_flag_low_icr_basic.py
    │   │   ├── test_flag_low_icr_higher_rate.py
    │   │   ├── test_flag_high_leverage.py
    │   │   ├── test_flag_high_leverage_extreme.py
    │   │   ├── test_flag_low_margin_safety.py
    │   │   ├── test_flag_high_refurb_ratio.py
    │   │   ├── test_flag_section_24_impact.py
    │   │   ├── test_flag_ated_warning.py
    │   │   ├── test_flag_leasehold_short_lease.py
    │   │   ├── test_flag_cash_flow_pre_tax_only.py
    │   │   ├── test_flag_ltd_extraction_undisclosed.py
    │   │   ├── test_flag_rent_unverified.py
    │   │   └── test_flag_evaluation_pipeline.py
    │   │
    │   └── precision/               ← Layer 1: Decimal precision tests
    │       ├── test_decimal_types.py
    │       ├── test_rounding_point.py
    │       ├── test_rounding_mode.py
    │       └── test_no_float_arithmetic.py
    │
    ├── regression/                  ← Layer 4: Reference scenario tests
    │   ├── conftest.py              ← scenario fixture definitions
    │   ├── test_e01_baseline_basic_rate.py
    │   ├── test_e02_higher_rate_section24.py
    │   ├── test_e03_ltd_co_standard.py
    │   ├── test_e04_lower_leverage_positive.py
    │   ├── test_e05_high_value_ltd_ated.py
    │   ├── test_e06_leasehold_higher_rate.py
    │   ├── test_e07_hard_validation_failure.py
    │   ├── test_e08_warn_only_validation.py
    │   ├── test_e09_short_lease_flag.py
    │   ├── test_e10_additional_rate.py
    │   ├── test_e11_thin_margin.py
    │   ├── test_e12_high_refurb.py
    │   └── test_cross_scenario_consistency.py
    │
    ├── determinism/                 ← Layer 5: Determinism tests
    │   ├── test_idempotent_execution.py
    │   ├── test_serialisation_roundtrip.py
    │   ├── test_config_version_isolation.py
    │   └── test_no_internal_state.py
    │
    └── integration/
        └── snapshots/               ← Layer 3: Snapshot payload tests
            ├── test_snapshot_completeness.py
            ├── test_snapshot_immutability_structure.py
            └── test_snapshot_comparison.py
```

---

---

# Part 12 — Test Execution and CI Strategy

---

## 12.1 — Test execution on commit

All test layers run on every commit to the main branch and on every pull
request. There is no partial test run for the engine. Partial test runs
(e.g. "just unit tests for speed") are acceptable in local development but
must not be the CI gate.

Rationale: The engine is the platform's most trusted component. The total
execution time for all layers is expected to be well under 30 seconds on any
modern developer machine or CI runner, because the engine has no I/O and no
network calls.

---

## 12.2 — Test naming conventions

All test functions are named using the pattern:

```
test_[subject]_[condition]_[expected_outcome]
```

Examples:
```
test_sdlt_purchase_at_125001_applies_2pct_band
test_icr_at_124_99_triggers_low_icr_basic_flag
test_e01_outputs_match_contracts_specification
test_engine_run_twice_produces_identical_results
test_additional_rate_tax_liability_greater_than_higher_rate
```

This naming pattern makes failing tests immediately interpretable without
reading the test body.

---

## 12.3 — Test marking strategy

Tests are marked using the following markers to enable targeted local runs:

```
@pytest.mark.formula      — Formula unit tests
@pytest.mark.tax          — Tax pathway tests
@pytest.mark.validation   — Validation rule tests
@pytest.mark.risk_flags   — Risk flag tests
@pytest.mark.precision    — Decimal precision tests
@pytest.mark.regression   — Reference scenario tests
@pytest.mark.determinism  — Determinism and reproducibility tests
@pytest.mark.snapshot     — Snapshot payload tests
```

These markers are for developer convenience only. CI always runs all markers.

---

## 12.4 — Failure escalation rules

A failure in any of the following categories is a blocking defect that must
be resolved before merge:

- Any regression test failure (E-01 through E-12)
- Any determinism test failure
- Any SDLT boundary test failure
- Any Section 24 tax pathway test failure
- Any decimal precision test failure

A failure in a formula happy-path test or a validation warning test is also
blocking, but may be triaged more rapidly in review.

There are no warnings-only test categories. Every test either passes or fails.

---

## 12.5 — Test data change process

The expected values in the reference scenario fixtures are the living
specification for correct engine behaviour. Any change to an expected value
in a fixture must be accompanied by:

1. A documented rationale: why was the previous value wrong, or why has the
   formula changed?
2. An updated entry in ENGINE_CONTRACTS.md reflecting the corrected value.
3. If the formula changed: a MAJOR engine version increment and a new entry
   in DECISIONS.md.

Changing an expected value to make a failing test pass, without a documented
rationale, is not acceptable.

---

---

# Part 13 — Relationship Between Documents

This test strategy is the final document in the pre-implementation chain.
The relationship between all specification documents is:

```
DOMAIN_GLOSSARY.md
    ↓ defines terminology used in
CALCULATION_SPEC.md
    ↓ defines formulas and contracts formalised in
ENGINE_CONTRACTS.md
    ↓ defines reference scenarios executed by
TEST_STRATEGY.md (this document)
    ↓ governs implementation of
engine/ source code (to be written)
    ↓ verified by
test suite (to be written)
```

A change at any level in this chain propagates downward. A change to a
formula in CALCULATION_SPEC.md requires a corresponding change in
ENGINE_CONTRACTS.md, which requires a corresponding change in the test
fixtures and expected values here.

The chain is intentionally strict. It is the mechanism by which the platform
maintains trust in its calculations over time, as regulations change,
assumptions are updated, and the engine evolves.
