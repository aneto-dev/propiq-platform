# PropIQ Platform — Underwriting Engine Architecture

## Purpose

This document defines the internal architecture of the PropIQ underwriting
engine: its boundaries, contracts, execution pipelines, configuration strategy,
error handling, determinism guarantees, and testing approach.

This document is not an implementation specification. It contains no code, no
ORM definitions, no SQL, and no API contracts. It defines how the engine is
structured as a software component so that implementation can proceed from a
stable design.

All terminology matches DOMAIN_GLOSSARY.md. All constraints reflect
ARCHITECTURE.md, CALCULATION_SPEC.md, DECISIONS.md, and SCHEMA_ARCHITECTURE.md.

---

## Governing Constraints

The following constraints govern every design decision in this document.

**Framework independence:** The engine must not import or depend on FastAPI,
SQLAlchemy, Pydantic models, or any persistence layer. It is a pure computation
module. This constraint is non-negotiable and must be enforced structurally,
not just by convention.

**No internal I/O:** The engine never reads from a database, never calls an
external API, and never writes to disk. All inputs — including configuration
values — are injected by the caller.

**Determinism (ADR-001, CALCULATION_SPEC.md):** Given identical inputs and
identical configuration, the engine must always produce identical outputs.
This means no random values, no timestamps generated inside the engine, no
system clock reads, and no floating-point operations that could produce
platform-dependent results.

**Pure functions:** Every calculation step must be a pure function. A pure
function produces its output solely from its arguments, has no side effects,
and can be called in isolation for testing.

**Configuration injection:** The engine receives configuration values as
explicit arguments. It does not know about configuration tables, version IDs,
or how configuration was retrieved. That is the responsibility of the
calculation service that calls the engine.

**Persistence boundary:** The engine produces a result value object. It does
not persist anything. The calculation service is responsible for turning the
result into a snapshot and writing it to the database.

---

---

# Part 1 — Engine Module Boundaries

The engine is a single bounded module with no dependency on any other
application layer. Its boundary can be described as a pure function:

```
EngineResult = engine.run(EngineInput, EngineConfig)
```

Where:

- `EngineInput` contains all user-provided and defaulted deal inputs
- `EngineConfig` contains all versioned configuration values active at the
  time of calculation
- `EngineResult` contains all intermediate values, outputs, validation
  results, and risk flags

Nothing crosses this boundary except plain data. No database sessions, no HTTP
clients, no service locators, no global state.

---

## Internal module structure

The engine is composed of five sub-modules. Each sub-module contains only pure
functions. Sub-modules may call each other but only in the direction defined
below. No circular dependencies.

```
engine/
├── validation/
│   └── Validates EngineInput against all V-01 through V-25 rules.
│       Returns structured ValidationResult.
│       Has no dependency on any other engine sub-module.
│
├── calculations/
│   └── Pure formula functions F-01 through F-22.
│       Each function takes explicit numeric arguments.
│       No function takes EngineInput or EngineConfig directly —
│       values are extracted and passed by the orchestrator.
│       Has no dependency on validation or risk_flags sub-modules.
│
├── tax/
│   └── Tax pathway A (Individual / Section 24) and
│       Tax pathway B (Limited Company / Corporation Tax).
│       Called by the orchestrator after operating costs are resolved.
│       Has no dependency on validation or risk_flags sub-modules.
│
├── risk_flags/
│   └── Evaluates all risk flag conditions defined in CALCULATION_SPEC.md.
│       Receives the completed intermediates and outputs object.
│       Returns a list of triggered RiskFlag values.
│       Has no dependency on calculations, tax, or validation sub-modules.
│
└── orchestrator/
    └── The single entry point for the engine.
        Calls validation, calculations, tax, and risk_flags in order.
        Assembles EngineResult from all intermediate outputs.
        Is the only module that holds the full calculation sequence.
        Has dependency on all four other sub-modules.
```

The dependency rule is strictly one-directional:

```
orchestrator → validation
orchestrator → calculations
orchestrator → tax
orchestrator → risk_flags

calculations has no engine-internal dependencies
tax has no engine-internal dependencies
risk_flags has no engine-internal dependencies
validation has no engine-internal dependencies
```

This means every sub-module other than the orchestrator can be imported and
tested in complete isolation.

---

---

# Part 2 — Engine Input Contract

The `EngineInput` is a plain data object. It contains every value that the
engine needs to perform a calculation. It is assembled by the calculation
service before the engine is called.

The engine receives `EngineInput` already populated with defaults. Default
resolution — determining which optional inputs to fill from configuration and
which have been overridden by the user — happens in the calculation service,
not in the engine. By the time `EngineInput` reaches the engine, every field
has a value. There are no nulls to resolve inside the engine.

---

## Required fields (always present, no default)

These fields have no fallback. The calculation service must refuse to call the
engine if any of these are absent.

| Field                   | Type    | Source                          |
|-------------------------|---------|---------------------------------|
| purchase_price          | Decimal | User input                      |
| monthly_rent            | Decimal | User input                      |
| deposit_amount          | Decimal | User input                      |
| mortgage_interest_rate  | Decimal | User input                      |
| mortgage_term_years     | Integer | User input                      |
| mortgage_type           | Enum    | User input: INTEREST_ONLY / REPAYMENT |
| ownership_structure     | Enum    | User input: INDIVIDUAL / LIMITED_COMPANY |
| income_tax_band         | Enum    | User input (INDIVIDUAL only): BASIC_RATE / HIGHER_RATE / ADDITIONAL_RATE |
| is_additional_dwelling  | Boolean | User input (default true)       |
| property_type           | Enum    | User input: RESIDENTIAL_SINGLE_LET |
| tenure                  | Enum    | User input: FREEHOLD / LEASEHOLD |
| property_country        | Enum    | User input: ENGLAND             |
| postcode                | String  | User input                      |

---

## Optional fields with defaults (always present after default resolution)

These fields are present in `EngineInput` with either the user-provided value
or the config default applied. The engine never needs to distinguish between
them — it simply uses the value.

| Field                        | Default Source          |
|------------------------------|-------------------------|
| void_rate_percent            | Assumption config       |
| letting_agent_fee_percent    | Assumption config       |
| maintenance_reserve_percent  | Assumption config       |
| landlord_insurance_annual    | Assumption config       |
| purchase_legal_costs         | Assumption config       |
| refurbishment_cost           | 0 (explicit)            |
| annual_service_charge        | 0 (explicit)            |
| annual_ground_rent           | 0 (explicit)            |
| annual_accountancy_cost      | Assumption config (varies by ownership_structure) |
| lease_years_remaining        | null (optional even after default resolution — leasehold only) |

---

## Input source tracking (carried alongside EngineInput)

The calculation service also tracks, per optional input, whether the value
came from a user override or a config default. This tracking data is not
passed to the engine — the engine does not need it. It is carried separately
by the calculation service and written into the snapshot inputs record after
the engine completes.

This separation is deliberate: the engine's job is computation, not audit
trail management.

---

---

# Part 3 — Engine Configuration Contract

The `EngineConfig` is a plain data object containing all versioned
configuration values active at the time of the calculation. It is assembled
by the configuration service before the engine is called.

The engine does not know where these values came from, what database tables
they live in, or what version IDs are associated with them. Version ID
references are tracked by the calculation service alongside `EngineConfig`
and written to the snapshot; they are not passed into the engine.

---

## SDLT configuration

| Field                              | Type            |
|------------------------------------|-----------------|
| sdlt_bands                         | List of SDLTBand |
| additional_dwelling_surcharge_rate | Decimal         |

Where each `SDLTBand` contains:
- band_lower (Decimal)
- band_upper (Decimal, nullable for the top band)
- rate_percent (Decimal)

---

## Corporation tax configuration

| Field                                  | Type    |
|----------------------------------------|---------|
| small_profits_rate_percent             | Decimal |
| small_profits_upper_threshold          | Decimal |
| main_rate_percent                      | Decimal |
| main_rate_lower_threshold              | Decimal |
| marginal_relief_fraction_numerator     | Integer |
| marginal_relief_fraction_denominator   | Integer |

---

## Assumption configuration

| Field                                   | Type    |
|-----------------------------------------|---------|
| void_rate_percent_default               | Decimal |
| letting_agent_fee_percent_default       | Decimal |
| maintenance_reserve_percent_default     | Decimal |
| landlord_insurance_annual_default       | Decimal |
| purchase_legal_costs_default            | Decimal |
| accountancy_cost_individual_default     | Decimal |
| accountancy_cost_ltd_default            | Decimal |
| stress_test_rate_percent                | Decimal |
| icr_threshold_basic_rate_percent        | Decimal |
| icr_threshold_higher_rate_percent       | Decimal |
| letting_agent_vat_rate_percent          | Decimal |

---

## What EngineConfig does not contain

`EngineConfig` does not contain:
- Database primary keys or version IDs
- Effective dates
- Source attribution strings
- Created-by metadata

These are persistence concerns. The calculation service holds them alongside
`EngineConfig` and includes them in the snapshot record. They are not needed
for computation.

---

---

# Part 4 — Engine Output Contract

The `EngineResult` is a plain data object returned by the engine after a
successful calculation run. It contains three categories of data.

---

## 4.1 — Intermediates

All intermediate values produced during the calculation pipeline. These are
stored in the snapshot for auditability and reproducibility.

| Field                              | Formula Reference |
|------------------------------------|-------------------|
| gross_annual_rent                  | F-01              |
| void_rate_decimal_applied          | F-02              |
| effective_annual_rent              | F-03              |
| loan_amount                        | F-04              |
| ltv_percent                        | F-05              |
| monthly_mortgage_payment           | F-06              |
| annual_mortgage_cost               | F-07              |
| annual_mortgage_interest           | F-08              |
| letting_agent_annual               | F-09              |
| letting_agent_vat_rate_applied     | F-09 (config value used) |
| annual_maintenance_reserve         | F-10              |
| total_operating_costs_annual       | F-11              |
| net_operating_income               | F-12              |
| sdlt_band_breakdown                | F-13 (structured) |
| sdlt_base                          | F-13              |
| sdlt_surcharge                     | F-13              |
| sdlt_surcharge_rate_applied        | F-13 (config value used) |
| total_sdlt                         | F-13              |
| total_acquisition_cost             | F-14              |
| total_cash_deployed                | F-15              |
| stressed_annual_interest           | F-22              |
| stress_test_rate_applied           | F-22 (config value used) |
| taxable_income_or_profit           | Tax pathway A or B |
| income_tax_gross                   | Tax pathway A      |
| mortgage_interest_tax_credit       | Tax pathway A      |
| corporation_tax_gross              | Tax pathway B      |
| annual_tax_liability               | Tax pathway A or B |
| section_24_applies                 | Derived boolean    |

---

## 4.2 — Outputs

User-facing output metrics. These are the values displayed on the deal summary
and stored in the snapshot outputs record. Field names match DOMAIN_GLOSSARY.md
API field names exactly.

| Field                           | Formula Reference |
|---------------------------------|-------------------|
| gross_annual_rent_gbp           | F-01              |
| effective_annual_rent_gbp       | F-03              |
| total_operating_costs_annual_gbp| F-11              |
| net_operating_income_gbp        | F-12              |
| annual_mortgage_cost_gbp        | F-07              |
| annual_tax_liability_gbp        | Tax pathway       |
| annual_cash_flow_gbp            | F-19              |
| monthly_cash_flow_gbp           | F-20              |
| gross_yield_percent             | F-16              |
| net_yield_percent               | F-17              |
| roce_percent                    | F-18              |
| cash_on_cash_return_percent     | F-21              |
| ltv_percent                     | F-05              |
| icr_percent                     | F-22              |
| total_sdlt_gbp                  | F-13              |
| total_acquisition_cost_gbp      | F-14              |
| total_cash_deployed_gbp         | F-15              |

---

## 4.3 — Risk flags

A list of zero or more `RiskFlag` values, each containing:

| Field             | Content                                              |
|-------------------|------------------------------------------------------|
| code              | Flag code string (e.g. NEGATIVE_CASHFLOW)            |
| severity          | HIGH / MEDIUM / INFO                                 |
| triggered_by_field| The output or intermediate field that triggered it   |
| triggered_by_value| The actual value of that field at trigger time       |
| message           | The user-facing message defined in CALCULATION_SPEC  |

---

## What EngineResult does not contain

- Snapshot IDs or database references
- Timestamps (timestamps are assigned by the persistence layer)
- Configuration version IDs (tracked by the calculation service)
- User IDs or deal IDs (tracking concerns, not calculation concerns)

---

---

# Part 5 — Validation Pipeline Architecture

Validation runs before any calculation begins. It is a discrete pipeline stage,
not inline checks scattered through the calculation code.

---

## Validation pipeline structure

```
EngineInput
    │
    ▼
┌─────────────────────────────────────────────────────┐
│  VALIDATION PIPELINE                                │
│                                                     │
│  Stage 1: Presence checks                           │
│    — All required fields present and non-null       │
│                                                     │
│  Stage 2: Type and range checks                     │
│    — Numeric fields within defined bounds           │
│    — Enum fields contain supported values           │
│                                                     │
│  Stage 3: Cross-field constraint checks             │
│    — deposit_amount < purchase_price                │
│    — deposit_amount >= 15% of purchase_price        │
│    — income_tax_band present if INDIVIDUAL          │
│    — leasehold fields present if LEASEHOLD          │
│                                                     │
│  Stage 4: Unsupported scenario checks               │
│    — property_country = ENGLAND                     │
│    — property_type = RESIDENTIAL_SINGLE_LET         │
│    — ownership_structure != LLP                     │
└────────────────────────┬────────────────────────────┘
                         │
               ┌─────────┴──────────┐
               │                    │
     Any HARD failure?        WARN failures only?
               │                    │
               ▼                    ▼
     ValidationFailure        ValidationWarnings
     (calculation stops)      (calculation proceeds,
                               warnings carried into
                               EngineResult)
```

---

## Validation result structure

Validation produces a `ValidationResult` containing:

- `is_valid` (Boolean) — false if any HARD rule failed
- `hard_errors` — list of `ValidationError` values
- `warnings` — list of `ValidationWarning` values

Each `ValidationError` and `ValidationWarning` contains:
- `rule_code` (e.g. V-07)
- `field` (the field that triggered the rule)
- `message` (the user-facing message from CALCULATION_SPEC.md)

If `is_valid` is false, the orchestrator returns immediately without
proceeding to any calculation step. The `ValidationResult` is carried back
to the calculation service, which records it in the audit log.

---

## Validation rules are data, not conditionals

Validation rules must be defined as a declarative list of rule objects, not
as a sequence of if-statements. Each rule object describes:

- The field it applies to
- The condition that triggers it
- Whether it is HARD or WARN
- The message to return

This design means:
- New validation rules are added by adding to the list, not by modifying
  control flow
- Rules can be tested individually by constructing inputs that trigger exactly
  one rule
- The complete set of rules is inspectable as data

---

---

# Part 6 — Calculation Orchestration Flow

The orchestrator is the engine's single entry point. It calls the sub-modules
in strict order. Each step receives only the values it needs. No step receives
the full `EngineInput` — values are extracted explicitly.

This explicit passing of values, rather than passing the full input object
down the chain, makes dependencies visible and prevents steps from secretly
depending on fields they should not access.

---

## Orchestration sequence

```
STEP 0 — Run validation pipeline
    Input: EngineInput
    Output: ValidationResult
    If any HARD error: return EngineFailure(validation_result)
    WARN errors: carry forward into result, do not stop

STEP 1 — Resolve mortgage scenario
    Input: mortgage_interest_rate, mortgage_type
    Output: is_cash_purchase (Boolean)
    If is_cash_purchase: set loan_amount = 0, monthly_mortgage_payment = 0
    Carry CASH_PURCHASE flag if applicable

STEP 2 — Calculate income
    F-01: gross_annual_rent ← monthly_rent
    F-02: void_rate_decimal ← void_rate_percent
    F-03: effective_annual_rent ← gross_annual_rent, void_rate_decimal

STEP 3 — Calculate financing
    F-04: loan_amount ← purchase_price, deposit_amount
    F-05: ltv_percent ← loan_amount, purchase_price
    F-06: monthly_mortgage_payment ← loan_amount, mortgage_interest_rate,
                                      mortgage_term_years, mortgage_type
    F-07: annual_mortgage_cost ← monthly_mortgage_payment
    F-08: annual_mortgage_interest ← loan_amount, mortgage_interest_rate,
                                      mortgage_type, monthly_mortgage_payment

STEP 4 — Calculate SDLT
    F-13: sdlt_result ← purchase_price, is_additional_dwelling,
                         config.sdlt_bands,
                         config.additional_dwelling_surcharge_rate
    Produces: sdlt_band_breakdown, sdlt_base, sdlt_surcharge, total_sdlt

STEP 5 — Calculate acquisition totals
    F-14: total_acquisition_cost ← purchase_price, total_sdlt,
                                    purchase_legal_costs, refurbishment_cost
    F-15: total_cash_deployed ← deposit_amount, total_sdlt,
                                  purchase_legal_costs, refurbishment_cost

STEP 6 — Calculate operating costs
    F-09: letting_agent_annual ← gross_annual_rent,
                                  letting_agent_fee_percent,
                                  config.letting_agent_vat_rate_percent
    F-10: annual_maintenance_reserve ← purchase_price,
                                        maintenance_reserve_percent
    F-11: total_operating_costs_annual ← letting_agent_annual,
                                          annual_maintenance_reserve,
                                          landlord_insurance_annual,
                                          annual_service_charge,
                                          annual_ground_rent,
                                          annual_accountancy_cost

STEP 7 — Calculate NOI
    F-12: net_operating_income ← effective_annual_rent,
                                   total_operating_costs_annual

STEP 8 — Calculate tax
    Branch on ownership_structure:

    INDIVIDUAL pathway:
        Derive section_24_applies = true
        Tax Pathway A:
            taxable_rental_income ← effective_annual_rent, operating cost components
            income_tax_on_rental ← taxable_rental_income, income_tax_band
            mortgage_interest_tax_credit ← annual_mortgage_interest
            annual_tax_liability ← MAX(0, income_tax_on_rental - credit)

    LIMITED_COMPANY pathway:
        Derive section_24_applies = false
        Tax Pathway B:
            taxable_company_profit ← effective_annual_rent,
                                      operating cost components,
                                      annual_mortgage_interest (deducted)
            corporation_tax ← taxable_company_profit, config.corp_tax_config
            annual_tax_liability ← MAX(0, corporation_tax)
            post_tax_retained_profit ← taxable_company_profit - annual_tax_liability

STEP 9 — Calculate cash flow
    F-19: annual_cash_flow ← net_operating_income,
                               annual_mortgage_cost,
                               annual_tax_liability
    F-20: monthly_cash_flow ← annual_cash_flow

STEP 10 — Calculate yields and returns
    F-16: gross_yield_percent ← gross_annual_rent, purchase_price
    F-17: net_yield_percent ← net_operating_income, purchase_price
    F-18: roce_percent ← net_operating_income, total_cash_deployed
    F-21: cash_on_cash_return_percent ← annual_cash_flow, total_cash_deployed

STEP 11 — Calculate stress test
    F-22: stressed_annual_interest ← loan_amount,
                                      config.stress_test_rate_percent
    F-22: icr_percent ← effective_annual_rent, stressed_annual_interest

STEP 12 — Evaluate risk flags
    Input: all intermediates and outputs assembled so far
    Input: ownership_structure, income_tax_band, tenure, lease_years_remaining
    Output: list of triggered RiskFlag values
    See Part 7 for risk flag evaluation pipeline.

STEP 13 — Assemble EngineResult
    Combine: intermediates, outputs, risk_flags, validation_warnings
    Return: EngineResult
```

---

## Pre-tax cash flow as an intermediate

The orchestrator calculates `pre_tax_annual_cash_flow` as an intermediate
value during Step 8/9:

```
pre_tax_annual_cash_flow = net_operating_income - annual_mortgage_cost
```

This value is carried in the intermediates and is used by the
`CASH_FLOW_PRE_TAX_ONLY` risk flag. It is not a primary output but must be
stored in the snapshot intermediates for auditability.

---

---

# Part 7 — Risk Flag Evaluation Pipeline

Risk flags are evaluated in a single pass after all calculations are complete.
The flag evaluator receives a fully assembled intermediates and outputs object.
It does not perform any calculations — it only compares values against the
threshold conditions defined in CALCULATION_SPEC.md.

---

## Risk flag evaluation structure

Like validation rules, risk flag definitions are data, not conditionals.
Each flag definition contains:

- `code` — the flag code string
- `severity` — HIGH / MEDIUM / INFO
- `condition` — a function that takes the assembled calculation context
  and returns Boolean (triggered or not)
- `triggered_by_field` — the field name to record when the flag fires
- `message` — the user-facing message string

The evaluator iterates over all flag definitions and calls each condition.
All conditions are evaluated — flags are not mutually exclusive unless
explicitly documented in CALCULATION_SPEC.md (e.g. HIGH_LEVERAGE and
HIGH_LEVERAGE_EXTREME can both fire independently).

---

## Flag evaluation context

The evaluation context passed to each condition function contains:

From outputs:
- annual_cash_flow, gross_annual_rent, net_operating_income
- gross_yield_percent, net_yield_percent, ltv_percent, icr_percent

From intermediates:
- pre_tax_annual_cash_flow

From inputs (structural — not calculated):
- ownership_structure, income_tax_band, tenure, lease_years_remaining
- purchase_price, refurbishment_cost

No condition function has access to EngineConfig or EngineInput directly.
Values are extracted and named explicitly in the context object. This prevents
flag conditions from accidentally depending on configuration values they
should not access.

---

## Risk flags always fired (INFO level)

Two flags fire unconditionally regardless of calculated values:

- `RENT_UNVERIFIED` — always fires because monthly_rent is always user-entered
- `LTD_EXTRACTION_UNDISCLOSED` — fires whenever ownership_structure =
  LIMITED_COMPANY

These are structural disclosures, not threshold-based warnings. They are
included in the flag definitions list alongside all other flags and are
handled uniformly.

---

---

# Part 8 — Configuration Loading Strategy

Configuration loading is entirely outside the engine. The calculation service
is responsible for loading configuration before calling the engine.

---

## Loading sequence (in the calculation service, not the engine)

```
1. Determine the calculation date (UTC date at time of request)

2. Load active SDLT configuration:
   Query: SELECT * FROM sdlt_config
          WHERE effective_from <= calculation_date
          ORDER BY effective_from DESC LIMIT 1
   Also load: associated SDLT rate band records for this version
   Record: sdlt_config_version_id for snapshot

3. Load active Corporation Tax configuration:
   Query: SELECT * FROM corporation_tax_config
          WHERE effective_from <= calculation_date
          ORDER BY effective_from DESC LIMIT 1
   Record: corporation_tax_config_version_id for snapshot

4. Load active Assumption configuration:
   Query: SELECT * FROM assumption_config
          WHERE effective_from <= calculation_date
          ORDER BY effective_from DESC LIMIT 1
   Record: assumption_config_version_id for snapshot

5. Resolve optional input defaults:
   For each optional input in EngineInput:
     If user provided a value: use it, record source = USER_OVERRIDE
     If not: use value from assumption_config, record source = CONFIG_DEFAULT

6. Assemble EngineConfig from loaded configuration records

7. Call engine.run(engine_input, engine_config)
```

---

## Recalculation configuration strategy

When recalculating a deal:

- **Reproduce original:** Load the specific configuration version IDs stored
  in the original snapshot. Pass those exact configuration values to the
  engine. The result must be identical to the original (given the same inputs).

- **Recalculate with latest:** Use the standard loading sequence above (latest
  active versions). This produces a new snapshot with current rates.

Both paths call the same engine. The engine does not know which path is in use.
This is the fundamental guarantee of historical reproducibility.

---

## Configuration caching

Configuration records are append-only and have stable IDs. They are safe to
cache. The calculation service may cache loaded configuration in memory for the
duration of a request. Cross-request caching requires a cache invalidation
strategy and is a Phase 2 concern.

---

---

# Part 9 — Snapshot Creation Flow

Snapshot creation is outside the engine. It is the responsibility of the
calculation service. The engine produces an `EngineResult`; the calculation
service turns it into a persisted snapshot.

---

## Snapshot creation sequence

```
1. Calculation service calls engine.run(engine_input, engine_config)

2. If engine returns EngineFailure (HARD validation error):
   — Write audit log entry with outcome = VALIDATION_FAILURE
   — Record validation errors in audit log
   — Do not create snapshot
   — Return error response to API layer

3. If engine returns EngineResult (success):

   a. Open a database transaction

   b. Write Snapshot root record:
      — snapshot_id (UUID generated by persistence layer)
      — deal_id
      — user_id
      — engine_version (from engine constant, not from EngineResult)
      — assumption_config_version_id (tracked alongside EngineConfig)
      — sdlt_config_version_id (tracked alongside EngineConfig)
      — corporation_tax_config_version_id (tracked alongside EngineConfig)
      — calculated_at (UTC timestamp — assigned by persistence layer)

   c. Write Snapshot Inputs record:
      — All required inputs from EngineInput
      — All optional inputs from EngineInput with their source flags
        (USER_OVERRIDE / CONFIG_DEFAULT) from input source tracking

   d. Write Snapshot Outputs record:
      — All output fields from EngineResult.outputs

   e. Write Snapshot Intermediates record:
      — All intermediate fields from EngineResult.intermediates

   f. Write Snapshot Risk Flags records:
      — One row per flag in EngineResult.risk_flags

   g. Update Deal.latest_snapshot_id to new snapshot_id
      (this is the only UPDATE permitted in the snapshot flow)

   h. Write Calculation Audit Log entry:
      — outcome = SUCCESS
      — snapshot reference

   i. Commit transaction

4. Return snapshot_id to API layer
```

---

## Transaction integrity

Steps b through i must be atomic. If any write fails, the transaction rolls
back. A partial snapshot must never exist in the database. The audit log entry
is written inside the same transaction so the audit record and the snapshot
are always consistent.

---

## Timestamp responsibility

The engine never generates timestamps. All timestamps are assigned by the
persistence layer at the moment of write. This means:

- The engine does not know when it is being called
- Two identical engine calls produce identical `EngineResult` values
- The calculation_at timestamp in the snapshot is the persistence layer's
  responsibility, not the engine's

This is required for determinism: if the engine generated timestamps internally,
two calls with identical inputs would produce different `EngineResult` values.

---

---

# Part 10 — Recalculation Flow

Recalculation is a first-class operation, not an edge case. It is implemented
using the same engine and the same snapshot creation flow.

---

## Recalculation variants

**Variant A — Reproduce original result:**
The calculation service loads the exact configuration version IDs from the
original snapshot. It reconstructs `EngineConfig` from those specific records.
It uses the original snapshot's inputs as `EngineInput`. The engine produces
an identical result to the original. This is used to verify historical
reproducibility.

**Variant B — Recalculate with current assumptions:**
The calculation service loads the latest active configuration versions using
the standard loading sequence. It uses the deal's current working inputs.
The engine produces a new result under current rates and assumptions.

In both variants:
- The original snapshot is never modified
- A new snapshot is created
- The original snapshot's `is_superseded` flag is set to true
- Both snapshots remain accessible and queryable

---

## What does not change in recalculation

The engine itself does not change. The formulas do not change. The only
difference between an original calculation and a recalculation is the
configuration values injected into `EngineConfig`. This is the direct
consequence of configuration injection — the engine is not aware of
"recalculation" as a concept.

---

---

# Part 11 — Error Handling Strategy

The engine distinguishes three outcome categories. These map to the audit log
outcome field.

---

## Outcome 1 — ValidationFailure

Produced when one or more HARD validation rules are triggered.

Contains:
- `hard_errors` — list of ValidationError (rule code, field, message)
- `warnings` — list of ValidationWarning that were also triggered

The calculation service records this in the audit log and returns structured
error information to the API layer. The API layer formats this into field-level
validation messages for the frontend.

Calculation does not proceed. No snapshot is created.

---

## Outcome 2 — EngineResult (success with optional warnings)

Produced when validation passes (even if WARN rules were triggered).

Contains all intermediates, outputs, risk flags, and any validation warnings
from WARN rules. The calculation service proceeds to snapshot creation.

Validation warnings are stored in the snapshot inputs record alongside the
input values that triggered them. They are surfaced to the user in the deal
summary as contextual information, distinct from risk flags.

---

## Outcome 3 — EngineError (unexpected failure)

Produced when an unhandled exception occurs during calculation — for example,
a divide-by-zero that was not caught by validation, an unexpected null value,
or a programming error.

The engine must not raise unhandled exceptions to the calculation service.
It must catch all internal errors and return an `EngineError` value containing:
- A sanitised error description (no stack traces, no internal state)
- The engine version at the time of failure

The calculation service records this in the audit log with outcome =
ENGINE_ERROR and returns a generic error response to the API layer. The user
sees a "calculation could not be completed" message; not an internal error.

---

## Edge cases that must not produce EngineError

These specific edge cases must be handled inside the engine as defined
scenarios, not as error conditions:

| Condition                           | Handling                                              |
|-------------------------------------|-------------------------------------------------------|
| mortgage_interest_rate = 0          | Treated as cash purchase; mortgage calculations skipped |
| taxable_income_or_profit <= 0       | Tax liability = 0; no error                           |
| annual_cash_flow < 0                | Permitted result; triggers NEGATIVE_CASHFLOW flag     |
| net_operating_income < 0            | Permitted result; triggers NEGATIVE_NOI flag          |
| total_cash_deployed = 0             | Guard against divide-by-zero in ROCE / CoC; return null for those metrics |
| icr denominator = 0 (cash purchase) | ICR = null; ICR flags not evaluated                   |

---

---

# Part 12 — Deterministic Execution Guarantees

The following guarantees are required by ADR-001 and the historical
reproducibility requirement in CALCULATION_SPEC.md.

---

## Guarantee 1 — No internal state

The engine holds no mutable state between calls. Every call to `engine.run()`
is completely independent. State shared between calls would make outputs
dependent on call order, which would break determinism.

---

## Guarantee 2 — No timestamps or random values

The engine never calls the system clock or any random number generator.
All time-dependent behaviour (e.g. "which configuration is active now?") is
resolved outside the engine before `engine.run()` is called.

---

## Guarantee 3 — Decimal arithmetic, not floating-point

All monetary calculations must use decimal arithmetic (Python's `decimal.Decimal`
or equivalent), not floating-point (`float`). Floating-point arithmetic is not
deterministic across platforms and introduces rounding errors that compound
through a multi-step calculation pipeline.

The chosen precision must be documented. A working precision of 10 decimal
places throughout the pipeline, rounded to 2 decimal places only at output
persistence, is the recommended approach. This must not be changed without
a MAJOR engine version increment.

---

## Guarantee 4 — Configuration fully injected before engine entry

The engine must not query a database, read environment variables, or access
any external resource. If it did, the same `EngineInput` could produce
different results depending on when it was called. Full configuration injection
before engine entry is the structural enforcement of this guarantee.

---

## Guarantee 5 — Formula functions are stateless and side-effect-free

Every function in the `calculations/` and `tax/` sub-modules must:
- Take only explicit arguments
- Return only its computed value
- Not modify any argument passed to it
- Not write to any shared variable or external resource

This makes every formula independently callable for testing without any
setup or teardown.

---

## Guarantee 6 — Calculation order is fixed and documented

The orchestration sequence in Part 6 is the authoritative definition of
calculation order. Intermediate values are computed in that order and must not
be reordered. Dependencies are explicit: each step lists the exact values it
consumes. If a step is found to depend on a value not listed in its inputs,
that is a specification defect to be corrected in this document before the
engine code is changed.

---

---

# Part 13 — Testing Strategy

The engine's architecture is designed to make every calculation independently
testable. The following testing layers are defined.

---

## Layer 1 — Formula unit tests

Each function in `calculations/` and `tax/` has its own unit tests.
Tests call the function directly with explicit numeric arguments. No engine
setup, no configuration objects, no database.

**What to test:**
- Correct output for a known input (happy path)
- Edge cases defined in CALCULATION_SPEC.md (zero interest rate, zero NOI,
  negative cash flow, top SDLT band, marginal relief boundary)
- Each SDLT band boundary exactly (£125,000, £250,001, £925,001, £1,500,001)
- Section 24 tax credit at each tax band (20%, 40%, 45%)
- Corporation tax at small profits rate, main rate, and marginal relief band

**Test values must be manually verified.** For any formula test, the expected
value must be computed independently (by hand or in a spreadsheet) before the
test is written. Tests that derive expected values from the same formula they
are testing provide no verification.

---

## Layer 2 — Validation rule unit tests

Each validation rule in `validation/` has its own unit tests.
Tests call the validation pipeline with an `EngineInput` constructed to trigger
exactly one rule.

**What to test:**
- Each HARD rule produces a ValidationFailure with the correct rule code
- Each WARN rule produces a ValidationWarning and does not block calculation
- Cross-field rules (deposit threshold, leasehold fields, income_tax_band
  required for INDIVIDUAL) are tested as combinations of fields, not
  individual fields in isolation

---

## Layer 3 — Risk flag unit tests

Each risk flag condition in `risk_flags/` has its own unit tests.
Tests call the flag evaluator with a constructed context object that triggers
exactly one flag.

**What to test:**
- Flag fires when condition is met
- Flag does not fire when condition is not met
- Boundary conditions (e.g. ICR exactly at 125.0 does not trigger LOW_ICR_BASIC;
  ICR at 124.9 does)

---

## Layer 4 — Tax pathway integration tests

Tax pathway tests call the full tax pathway function (not individual steps)
with a complete set of inputs and verify the final `annual_tax_liability`.

**Scenario matrix to cover:**

| Scenario | Ownership | Tax Band | Mortgage Type | Notes |
|----------|-----------|----------|---------------|-------|
| T-01 | INDIVIDUAL | BASIC_RATE | INTEREST_ONLY | Section 24 broadly neutral |
| T-02 | INDIVIDUAL | HIGHER_RATE | INTEREST_ONLY | Section 24 material impact |
| T-03 | INDIVIDUAL | ADDITIONAL_RATE | INTEREST_ONLY | Section 24 at maximum impact |
| T-04 | INDIVIDUAL | HIGHER_RATE | REPAYMENT | Year 1 interest approximation |
| T-05 | LIMITED_COMPANY | — | INTEREST_ONLY | Interest deductible |
| T-06 | LIMITED_COMPANY | — | REPAYMENT | Year 1 interest approximation |
| T-07 | LIMITED_COMPANY | — | INTEREST_ONLY | High profit — main rate |
| T-08 | INDIVIDUAL | BASIC_RATE | INTEREST_ONLY | Zero NOI (high costs) |

All expected values in tax tests must be computed and verified independently
before tests are written.

---

## Layer 5 — Orchestrator end-to-end tests

Full engine runs using `engine.run(engine_input, engine_config)` with known
input sets and known expected outputs. These tests verify that the orchestration
sequence produces correct results when all sub-modules interact.

**Reference scenarios (minimum required):**

| Scenario | Description |
|----------|-------------|
| E-01 | £200k purchase, 25% deposit, 4.75% interest-only, individual basic-rate |
| E-02 | £200k purchase, 25% deposit, 4.75% interest-only, individual higher-rate |
| E-03 | £350k purchase, 25% deposit, 5.0% interest-only, limited company |
| E-04 | £200k purchase, 40% deposit (cash-heavy), individual basic-rate |
| E-05 | £600k purchase, 25% deposit, limited company (ATED threshold crossed) |
| E-06 | Leasehold property, service charge and ground rent present |
| E-07 | Zero refurbishment cost (WARN expected) |
| E-08 | Deposit below 25% but above 15% (WARN expected, calculation proceeds) |
| E-09 | Negative cash flow scenario (NEGATIVE_CASHFLOW flag expected) |
| E-10 | High LTV scenario (HIGH_LEVERAGE flag expected) |

All expected output values for E-01 through E-10 must be manually computed and
documented as a reference table before the tests are written. This reference
table becomes the living specification for what correct output looks like.

---

## Layer 6 — Historical reproducibility tests

These tests verify that the recalculation guarantee holds: given the same
`EngineInput` and the same `EngineConfig`, the engine must always produce
the same `EngineResult`.

**Test structure:**
1. Run the engine with a known input and config. Record the full `EngineResult`.
2. Serialise both input and config to a deterministic format (JSON with sorted
   keys, Decimal values as strings).
3. Deserialise. Run the engine again with the deserialised values.
4. Assert that the two `EngineResult` values are identical, field by field.

These tests must be run on every engine version. If they fail after a code
change, that change either introduced non-determinism (a bug) or changed
calculation logic (requires a MAJOR version increment and documentation in
DECISIONS.md).

---

## Layer 7 — Configuration version isolation tests

These tests verify that different configuration versions produce different
results for the same inputs, and that the original configuration always
reproduces the original result.

**Test structure:**
1. Run the engine with config version A and record EngineResult(A).
2. Run the engine with config version B (different SDLT rates or assumptions).
3. Assert that EngineResult(A) != EngineResult(B) where expected.
4. Run the engine again with config version A.
5. Assert that the result equals EngineResult(A) exactly.

This tests that the engine has no hidden dependency on any external state that
could cause the same config version to produce different results over time.

---

## Test data management

All test inputs and expected outputs are stored as static data files in the
test suite, not generated at runtime. This means:

- Tests are readable without running them
- Test failures are unambiguous — the actual value differs from the recorded
  expected value
- Adding a new test requires computing and recording the expected value first

The reference scenario table for E-01 through E-10 is the primary test data
artefact. It should be reviewed and approved before implementation begins, as
it encodes what "correct" means for the underwriting engine.

---

---

# Part 14 — Engine Version Contract

The engine version is a semantic version string (MAJOR.MINOR.PATCH) embedded
as a constant in the engine module itself. It is not read from a database or
configuration file.

**MAJOR** — formula logic or methodology change that produces different outputs
for the same inputs. Requires a documented entry in DECISIONS.md. All existing
snapshots remain valid under their original engine version. New snapshots are
calculated under the new version.

**MINOR** — new calculation step, new output field, or new risk flag added.
Does not change existing output values.

**PATCH** — bug fix, refactoring, or non-functional change.

The engine version embedded in a snapshot is the permanent record of which
formula logic was used. It must be a constant, not derived or computed.

---

---

# Part 15 — What Lives Outside the Engine

For clarity, the following responsibilities are explicitly outside the engine
boundary and belong to the layers described in SCHEMA_ARCHITECTURE.md and
ARCHITECTURE.md.

| Responsibility                              | Owner                      |
|---------------------------------------------|----------------------------|
| Loading configuration from database         | Configuration service      |
| Resolving optional input defaults           | Calculation service        |
| Tracking input source (override vs default) | Calculation service        |
| Assigning snapshot UUIDs                    | Persistence layer          |
| Assigning calculation timestamps            | Persistence layer          |
| Writing snapshot to database                | Snapshot persistence service |
| Updating Deal.latest_snapshot_id            | Snapshot persistence service |
| Writing audit log entries                   | Calculation service        |
| Authentication and authorisation            | API layer / Supabase Auth  |
| Request/response serialisation              | API layer (FastAPI)        |
| Deal and property CRUD                      | Domain services            |
| AI-assisted summaries (Phase 5)             | Separate AI service        |
