# PropIQ Platform — Database Schema Design

## Purpose

This document defines the logical PostgreSQL schema for the PropIQ platform
Phase 1. It specifies every table, every column, every constraint, every index,
and the seed data required to operate.

This document is design-level specification. It is the definitive reference
from which SQLAlchemy models and Alembic migrations will be derived. It
contains no ORM code, no migration scripts, no FastAPI routes, and no
implementation code of any kind.

All terminology matches DOMAIN_GLOSSARY.md.
All table names, naming conventions, and privilege rules derive from
PERSISTENCE_ARCHITECTURE.md.
All column content derives from ENGINE_CONTRACTS.md (for snapshot columns)
and CALCULATION_SPEC.md (for configuration seed values).
All mutability constraints enforce DATA_BOUNDARIES.md classifications.

---

## Document Status

Version: 1.0
Phase coverage: Phase 1 complete
Engine version targeted: 1.0.0
Applicable ADRs: ADR-002, ADR-005, ADR-007, ADR-009, ADR-010, ADR-011,
                 ADR-012, ADR-013, ADR-014

---

## Conventions Used in This Document

```
REQUIRED      — NOT NULL constraint. Column must always have a value.
NULLABLE      — NULL permitted.
PK            — Primary key.
FK → table    — Foreign key referencing the named table.
UNIQUE        — Unique constraint on this column.
CHECK(...)    — Check constraint with condition.
DEFAULT value — Default value applied on insert if not specified.
[IMMUTABLE]   — Column is write-once. Application enforces; DB privilege
                enforces for tables with INSERT-only grants.
```

---

## Decimal Precision Standard

All monetary and financial rate values use `NUMERIC(15, 6)`:
- 15 total digits, 6 decimal places
- Supports values up to £999,999,999.999999
- 6dp provides sub-penny precision for intermediate calculations
- Values are rounded to 2dp at application output layer, not at storage

Percentage values (yield, ICR, LTV, rates) use `NUMERIC(10, 6)`:
- 10 total digits, 6 decimal places
- Supports percentages up to 9999.999999
- More than sufficient for any financial rate value

Engine intermediate precision values use `NUMERIC(15, 10)` where the full
working precision of the engine must be preserved (notably the void rate
decimal and SDLT intermediate computations).

No `FLOAT` or `DOUBLE PRECISION` types are used anywhere in this schema.
These types introduce platform-dependent rounding that would break the
determinism guarantee (ADR-014, ENGINE_CONTRACTS.md Part 7).

---

---

# Section 1 — Enum Type Definitions

PostgreSQL custom enum types are defined once and reused across tables.
All enum values are UPPER_SNAKE_CASE.

---

## ENUM: ownership_structure_enum
```
INDIVIDUAL
LIMITED_COMPANY
```
Used in: investor_profiles, deals (working inputs), snapshot_inputs

---

## ENUM: income_tax_band_enum
```
BASIC_RATE
HIGHER_RATE
ADDITIONAL_RATE
```
Used in: deals (working inputs), snapshot_inputs

---

## ENUM: mortgage_type_enum
```
INTEREST_ONLY
REPAYMENT
```
Used in: deals (working inputs), snapshot_inputs

---

## ENUM: property_type_enum
```
RESIDENTIAL_SINGLE_LET
```
Phase 1 only. Extended in future phases with HMO, MULTI_UNIT_FREEHOLD_BLOCK.

Used in: properties, snapshot_inputs

---

## ENUM: tenure_enum
```
FREEHOLD
LEASEHOLD
```
Used in: properties, snapshot_inputs

---

## ENUM: property_country_enum
```
ENGLAND
```
Phase 1 only. Extended with SCOTLAND, WALES, NORTHERN_IRELAND in future phases.

Used in: properties, snapshot_inputs, config_sdlt_versions

---

## ENUM: deal_status_enum
```
DRAFT
ANALYSED
ARCHIVED
```
Used in: deals

---

## ENUM: user_status_enum
```
ACTIVE
SUSPENDED
ARCHIVED
```
Used in: users

---

## ENUM: calculation_outcome_enum
```
SUCCESS
VALIDATION_FAILURE
ENGINE_ERROR
```
Used in: audit_calculations

---

## ENUM: input_source_enum
```
USER_OVERRIDE
CONFIG_DEFAULT
```
Extended in Phase 3 with EXTERNAL_PROVIDER, and Phase 5 with AI_SUGGESTION.

Used in: snapshot_inputs (_source columns)

---

## ENUM: flag_severity_enum
```
HIGH
MEDIUM
INFO
```
Used in: snapshot_risk_flags

---

---

# Section 2 — Core Domain Tables

---

## Table: users

**Responsibility:** Platform user accounts. Extends the Supabase Auth identity
record. Created on first authenticated login. PII is stored here; this table
is subject to future GDPR anonymisation process (Phase 2).

**Mutability:** OPERATIONALLY MUTABLE. `status` transitions are permitted.
No hard DELETE.

**Privilege:** INSERT, UPDATE. No DELETE.

```
Column                  Type                Constraints             Notes
─────────────────────────────────────────────────────────────────────────────
id                      UUID                PK, REQUIRED            Application-generated UUID v4
supabase_auth_id        UUID                REQUIRED, UNIQUE        Join key to Supabase Auth
email                   TEXT                REQUIRED                Synced from auth; not authoritative here
display_name            TEXT                NULLABLE
status                  user_status_enum    REQUIRED, DEFAULT ACTIVE
created_at              TIMESTAMPTZ         REQUIRED, DEFAULT NOW() [IMMUTABLE]
updated_at              TIMESTAMPTZ         REQUIRED, DEFAULT NOW()
```

**Constraints:**
- `CHECK (email ~* '^[^@]+@[^@]+\.[^@]+$')` — basic email format guard
- `UNIQUE (supabase_auth_id)`

**Indexes:**
- `PRIMARY KEY (id)`
- `UNIQUE INDEX ON users (supabase_auth_id)` — lookup by auth identity
- `INDEX ON users (email)` — lookup by email for auth flow

**Notes:**
The `supabase_auth_id` is the join key to Supabase's own identity store.
When the platform needs to verify a JWT, it resolves the Supabase user ID
to this table. The `email` column is informational — Supabase Auth is the
authoritative source for email. During GDPR anonymisation (Phase 2), this
column is overwritten with a hash; `supabase_auth_id` is NULLed; and
`status` transitions to ARCHIVED. Snapshot records referencing this user
by `user_id` remain intact and unaffected.

---

## Table: investor_profiles

**Responsibility:** Named sets of investor-level tax and ownership preferences.
A user may have multiple profiles (e.g. one for personal ownership, one for
a Ltd Co). Profiles are convenience defaults for deal creation — they are
NOT referenced by snapshots. Profile values are copied into `snapshot_inputs`
at calculation time.

**Mutability:** OPERATIONALLY MUTABLE. Profiles may be updated or archived.
Changes to a profile do not affect historical snapshots.

**Privilege:** INSERT, UPDATE. No DELETE.

```
Column                  Type                      Constraints             Notes
──────────────────────────────────────────────────────────────────────────────
id                      UUID                      PK, REQUIRED
user_id                 UUID                      REQUIRED, FK → users
label                   TEXT                      REQUIRED                e.g. "Personal Name", "PropCo Ltd"
ownership_structure     ownership_structure_enum  REQUIRED
income_tax_band         income_tax_band_enum      NULLABLE                Required if INDIVIDUAL; null for LIMITED_COMPANY
is_default              BOOLEAN                   REQUIRED, DEFAULT FALSE One profile may be flagged as default per user
is_archived             BOOLEAN                   REQUIRED, DEFAULT FALSE
archived_at             TIMESTAMPTZ               NULLABLE
created_at              TIMESTAMPTZ               REQUIRED, DEFAULT NOW() [IMMUTABLE]
updated_at              TIMESTAMPTZ               REQUIRED, DEFAULT NOW()
```

**Constraints:**
- `CHECK (
    (ownership_structure = 'INDIVIDUAL' AND income_tax_band IS NOT NULL) OR
    (ownership_structure = 'LIMITED_COMPANY' AND income_tax_band IS NULL)
  )` — income_tax_band is required for INDIVIDUAL, forbidden for LIMITED_COMPANY

**Indexes:**
- `PRIMARY KEY (id)`
- `INDEX ON investor_profiles (user_id)` — all profiles for a user

**Notes:**
Only one profile per user should have `is_default = TRUE`. This is enforced
at the application layer rather than with a partial unique index in Phase 1,
as the uniqueness rule is "at most one default per user" which requires a
WHERE clause filter. A Phase 2 migration may formalise this with a partial
unique index when team accounts are introduced.

---

## Table: properties

**Responsibility:** Physical real-world properties that are the subject of
deal analyses. Holds stable identifying information about the asset. Does not
hold calculated values — those live in snapshots.

**Mutability:** OPERATIONALLY MUTABLE. Property details may be refined.
No hard DELETE. Soft archive via `is_archived`.

**Privilege:** INSERT, UPDATE. No DELETE.

```
Column                  Type                    Constraints             Notes
──────────────────────────────────────────────────────────────────────────────
id                      UUID                    PK, REQUIRED
user_id                 UUID                    REQUIRED, FK → users
address_line_1          TEXT                    REQUIRED
address_line_2          TEXT                    NULLABLE
city                    TEXT                    REQUIRED
postcode                TEXT                    REQUIRED                Validated UK format at application layer
property_type           property_type_enum      REQUIRED
tenure                  tenure_enum             REQUIRED
lease_years_remaining   INTEGER                 NULLABLE                Required if tenure = LEASEHOLD; null for FREEHOLD
bedrooms                SMALLINT                NULLABLE
epc_rating              CHAR(1)                 NULLABLE                A–G; sourced from user or EPC register (Phase 3+)
is_archived             BOOLEAN                 REQUIRED, DEFAULT FALSE
archived_at             TIMESTAMPTZ             NULLABLE
created_at              TIMESTAMPTZ             REQUIRED, DEFAULT NOW() [IMMUTABLE]
updated_at              TIMESTAMPTZ             REQUIRED, DEFAULT NOW()
```

**Constraints:**
- `CHECK (postcode ~ '^[A-Z]{1,2}[0-9][0-9A-Z]?\s*[0-9][A-Z]{2}$')` — UK postcode format
- `CHECK (lease_years_remaining IS NULL OR lease_years_remaining > 0)`
- `CHECK (bedrooms IS NULL OR bedrooms > 0)`
- `CHECK (epc_rating IS NULL OR epc_rating IN ('A','B','C','D','E','F','G'))`
- `CHECK (NOT (tenure = 'LEASEHOLD' AND lease_years_remaining IS NULL))`
  — leasehold properties must declare lease length at the property level.
  Note: this is a property-level field. The snapshot input also captures this
  independently at calculation time.

**Indexes:**
- `PRIMARY KEY (id)`
- `INDEX ON properties (user_id)` — all properties for a user
- `INDEX ON properties (postcode)` — postcode lookup

**Notes:**
The PostGIS extension is enabled in Phase 1 but no geometry column exists on
this table. The `intel_property_locations` table (Phase 3) will hold the
geocoded point geometry, referenced by `property_id`. This keeps the clean
property record free of spatial complexity until Phase 3.

---

## Table: deals

**Responsibility:** The mutable workspace for a property analysis. Holds
the user's current working inputs and a pointer to the latest snapshot.
Does not hold calculation outputs. Represents both the working input state
and the workflow status of an investment analysis.

**Mutability:** OPERATIONALLY MUTABLE. Working inputs change as the user
edits them. Status transitions occur throughout the deal lifecycle.
`latest_snapshot_id` is updated on every new calculation.

**Privilege:** INSERT, UPDATE. No DELETE.

```
Column                          Type                      Constraints             Notes
────────────────────────────────────────────────────────────────────────────────────────
id                              UUID                      PK, REQUIRED
user_id                         UUID                      REQUIRED, FK → users
property_id                     UUID                      REQUIRED, FK → properties
investor_profile_id             UUID                      NULLABLE, FK → investor_profiles  Used to pre-populate; not stored in snapshot
label                           TEXT                      REQUIRED                e.g. "25pct deposit scenario"
status                          deal_status_enum          REQUIRED, DEFAULT DRAFT
latest_snapshot_id              UUID                      NULLABLE, FK → snapshot_calculations  Null until first calculation

--- Working input fields (mutable; copied to snapshot_inputs at calculation time) ---

purchase_price                  NUMERIC(15,6)             NULLABLE                Null until user enters value
monthly_rent                    NUMERIC(15,6)             NULLABLE
deposit_amount                  NUMERIC(15,6)             NULLABLE
mortgage_interest_rate          NUMERIC(10,6)             NULLABLE
mortgage_term_years             SMALLINT                  NULLABLE
mortgage_type                   mortgage_type_enum        NULLABLE
ownership_structure             ownership_structure_enum  NULLABLE
income_tax_band                 income_tax_band_enum      NULLABLE
is_additional_dwelling          BOOLEAN                   NULLABLE                DEFAULT TRUE set at application layer on creation
void_rate_percent               NUMERIC(10,6)             NULLABLE                Null = use config default
letting_agent_fee_percent       NUMERIC(10,6)             NULLABLE
maintenance_reserve_percent     NUMERIC(10,6)             NULLABLE
landlord_insurance_annual       NUMERIC(15,6)             NULLABLE
purchase_legal_costs            NUMERIC(15,6)             NULLABLE
refurbishment_cost              NUMERIC(15,6)             NULLABLE
annual_service_charge           NUMERIC(15,6)             NULLABLE
annual_ground_rent              NUMERIC(15,6)             NULLABLE
annual_accountancy_cost         NUMERIC(15,6)             NULLABLE

created_at                      TIMESTAMPTZ               REQUIRED, DEFAULT NOW() [IMMUTABLE]
updated_at                      TIMESTAMPTZ               REQUIRED, DEFAULT NOW()
```

**Constraints:**
- `CHECK (purchase_price IS NULL OR purchase_price > 0)`
- `CHECK (monthly_rent IS NULL OR monthly_rent > 0)`
- `CHECK (deposit_amount IS NULL OR deposit_amount > 0)`
- `CHECK (mortgage_interest_rate IS NULL OR mortgage_interest_rate >= 0)`
- `CHECK (mortgage_term_years IS NULL OR (mortgage_term_years >= 5 AND mortgage_term_years <= 35))`
- `CHECK (refurbishment_cost IS NULL OR refurbishment_cost >= 0)`
- `CHECK (annual_service_charge IS NULL OR annual_service_charge >= 0)`
- `CHECK (annual_ground_rent IS NULL OR annual_ground_rent >= 0)`

**Indexes:**
- `PRIMARY KEY (id)`
- `INDEX ON deals (user_id)` — all deals for a user
- `INDEX ON deals (property_id)` — all deals against a property
- `INDEX ON deals (latest_snapshot_id)` — FK join efficiency

**Important design note — nullable working inputs:**
Working input columns are nullable because a deal in DRAFT status may not
yet have all values populated. The engine's validation pipeline enforces
completeness at calculation time, not at the database level. A row with
null working inputs is a valid DRAFT deal awaiting user input.

**Important design note — working inputs vs snapshot inputs:**
The values in the working input columns are the user's current editable state.
They are NOT the values used in any calculation. Snapshot inputs (in
`snapshot_inputs`) are the immutable copy made at calculation time. The
working input columns may continue to change after a snapshot is created.
This is the explicit mutable/immutable boundary (DATA_BOUNDARIES.md).

---

---

# Section 3 — Snapshot Domain Tables

All snapshot tables are STRICTLY IMMUTABLE after creation. The application
database role has INSERT privilege only on these tables. No UPDATE, no DELETE.

---

## Table: snapshot_calculations

**Responsibility:** Root record of a single complete underwriting calculation.
Anchors the snapshot family to a deal, a user, a set of configuration version
references, and the engine version that produced the result.

**Mutability:** [IMMUTABLE] except `is_superseded` and `superseded_at`.
See note below.

**Privilege:** INSERT only. Targeted partial UPDATE on `is_superseded` and
`superseded_at` only — enforced by column-level grant, not table-level.

```
Column                              Type          Constraints              Notes
──────────────────────────────────────────────────────────────────────────────────
id                                  UUID          PK, REQUIRED             [IMMUTABLE]
deal_id                             UUID          REQUIRED, FK → deals     [IMMUTABLE]
user_id                             UUID          REQUIRED, FK → users     [IMMUTABLE] Denormalised for audit
engine_version                      TEXT          REQUIRED                 [IMMUTABLE] e.g. "1.0.0"
assumption_config_version_id        UUID          REQUIRED, FK → config_assumption_versions  [IMMUTABLE]
sdlt_config_version_id              UUID          REQUIRED, FK → config_sdlt_versions        [IMMUTABLE]
corporation_tax_config_version_id   UUID          REQUIRED, FK → config_corporation_tax_versions  [IMMUTABLE]
calculated_at                       TIMESTAMPTZ   REQUIRED                 [IMMUTABLE] Assigned by persistence layer at INSERT
is_superseded                       BOOLEAN       REQUIRED, DEFAULT FALSE  MUTABLE — only permitted mutation
superseded_at                       TIMESTAMPTZ   NULLABLE                 MUTABLE — set when is_superseded transitions to TRUE
calculation_duration_ms             INTEGER       NULLABLE                 [IMMUTABLE] Operational diagnostic
created_at                          TIMESTAMPTZ   REQUIRED, DEFAULT NOW()  [IMMUTABLE]
```

**Constraints:**
- `CHECK (is_superseded = FALSE OR superseded_at IS NOT NULL)` — if superseded, timestamp must be set
- `CHECK (calculated_at IS NOT NULL)` — always explicitly set; cannot rely on DEFAULT for auditability

**Indexes:**
- `PRIMARY KEY (id)`
- `INDEX ON snapshot_calculations (deal_id)` — snapshot history for a deal
- `INDEX ON snapshot_calculations (deal_id, is_superseded)` — current snapshot for a deal
- `INDEX ON snapshot_calculations (user_id)` — all calculations by a user
- `INDEX ON snapshot_calculations (engine_version)` — version audit queries

**Notes on is_superseded mutation:**
This is the single permitted exception to full snapshot immutability. The
column-level UPDATE grant is:
```
GRANT UPDATE (is_superseded, superseded_at)
  ON snapshot_calculations
  TO propiq_app_user;
```
No other column may be updated. All other columns use the INSERT-only table
grant.

---

## Table: snapshot_inputs

**Responsibility:** Complete record of every input value used in one
calculation. Stores both required inputs and optional inputs, with provenance
source flags for every optional field. This table, combined with the
configuration version references on `snapshot_calculations`, provides the
complete data required to reproduce the calculation.

**Mutability:** STRICTLY IMMUTABLE.

**Privilege:** INSERT only. No UPDATE, no DELETE.

```
Column                              Type                        Constraints     Notes
────────────────────────────────────────────────────────────────────────────────────────────
id                                  UUID                        PK, REQUIRED    [IMMUTABLE]
snapshot_id                         UUID                        REQUIRED, UNIQUE, FK → snapshot_calculations  Enforces 1:1

--- Required inputs (always present; engine validation confirmed these before calculation) ---

purchase_price                      NUMERIC(15,6)               REQUIRED        [IMMUTABLE]
monthly_rent                        NUMERIC(15,6)               REQUIRED        [IMMUTABLE]
deposit_amount                      NUMERIC(15,6)               REQUIRED        [IMMUTABLE]
mortgage_interest_rate              NUMERIC(10,6)               REQUIRED        [IMMUTABLE]
mortgage_term_years                 SMALLINT                    REQUIRED        [IMMUTABLE]
mortgage_type                       mortgage_type_enum          REQUIRED        [IMMUTABLE]
ownership_structure                 ownership_structure_enum    REQUIRED        [IMMUTABLE]
income_tax_band                     income_tax_band_enum        NULLABLE        [IMMUTABLE] NULL for LIMITED_COMPANY
is_additional_dwelling              BOOLEAN                     REQUIRED        [IMMUTABLE]
property_type                       property_type_enum          REQUIRED        [IMMUTABLE]
tenure                              tenure_enum                 REQUIRED        [IMMUTABLE]
property_country                    property_country_enum       REQUIRED        [IMMUTABLE]
postcode                            TEXT                        REQUIRED        [IMMUTABLE]
lease_years_remaining               SMALLINT                    NULLABLE        [IMMUTABLE] NULL for FREEHOLD

--- Optional inputs: each has a value column and a paired _source column ---
--- Source = USER_OVERRIDE if user provided this value; CONFIG_DEFAULT if drawn from assumption config ---

void_rate_percent                   NUMERIC(10,6)               REQUIRED        [IMMUTABLE]
void_rate_percent_source            input_source_enum           REQUIRED        [IMMUTABLE]

letting_agent_fee_percent           NUMERIC(10,6)               REQUIRED        [IMMUTABLE]
letting_agent_fee_percent_source    input_source_enum           REQUIRED        [IMMUTABLE]

maintenance_reserve_percent         NUMERIC(10,6)               REQUIRED        [IMMUTABLE]
maintenance_reserve_percent_source  input_source_enum           REQUIRED        [IMMUTABLE]

landlord_insurance_annual           NUMERIC(15,6)               REQUIRED        [IMMUTABLE]
landlord_insurance_annual_source    input_source_enum           REQUIRED        [IMMUTABLE]

purchase_legal_costs                NUMERIC(15,6)               REQUIRED        [IMMUTABLE]
purchase_legal_costs_source         input_source_enum           REQUIRED        [IMMUTABLE]

refurbishment_cost                  NUMERIC(15,6)               REQUIRED        [IMMUTABLE]
refurbishment_cost_source           input_source_enum           REQUIRED        [IMMUTABLE]

annual_service_charge               NUMERIC(15,6)               REQUIRED        [IMMUTABLE]
annual_service_charge_source        input_source_enum           REQUIRED        [IMMUTABLE]

annual_ground_rent                  NUMERIC(15,6)               REQUIRED        [IMMUTABLE]
annual_ground_rent_source           input_source_enum           REQUIRED        [IMMUTABLE]

annual_accountancy_cost             NUMERIC(15,6)               REQUIRED        [IMMUTABLE]
annual_accountancy_cost_source      input_source_enum           REQUIRED        [IMMUTABLE]

created_at                          TIMESTAMPTZ                 REQUIRED, DEFAULT NOW()  [IMMUTABLE]
```

**Constraints:**
- `UNIQUE (snapshot_id)` — enforces one-to-one relationship
- `CHECK (purchase_price > 0)`
- `CHECK (monthly_rent > 0)`
- `CHECK (deposit_amount > 0 AND deposit_amount < purchase_price)`
- `CHECK (mortgage_interest_rate >= 0)`
- `CHECK (mortgage_term_years >= 5 AND mortgage_term_years <= 35)`
- `CHECK (void_rate_percent >= 0 AND void_rate_percent <= 100)`
- `CHECK (refurbishment_cost >= 0)`
- `CHECK (annual_service_charge >= 0)`
- `CHECK (annual_ground_rent >= 0)`
- `CHECK (annual_accountancy_cost >= 0)`
- `CHECK (
    (ownership_structure = 'INDIVIDUAL' AND income_tax_band IS NOT NULL) OR
    (ownership_structure = 'LIMITED_COMPANY' AND income_tax_band IS NULL)
  )`

**Indexes:**
- `PRIMARY KEY (id)`
- `UNIQUE INDEX ON snapshot_inputs (snapshot_id)` — enforces 1:1, enables efficient join

**Design note — why all optional inputs are REQUIRED in snapshot_inputs:**
In the `deals` table, working input columns are nullable because the deal may
be incomplete. In `snapshot_inputs`, all optional inputs are REQUIRED because
by the time a snapshot is created, the calculation service has resolved every
optional input to either a user value or a config default. A snapshot with a
null optional input is an engine contract violation — it must never occur.

**Design note — provenance columns are never nullable:**
Every `_source` column is REQUIRED. There is no scenario where an input is
used in a calculation but its provenance is unknown. A null source column
would mean we cannot answer "was this the user's choice or our default?" —
which directly violates ADR-009 (assumption provenance) and ADR-013 (user
override precedence).

---

## Table: snapshot_outputs

**Responsibility:** All user-facing output metrics produced by the calculation.
Column names match `EngineOutputs` field names in ENGINE_CONTRACTS.md Part 3.1
exactly, which also match DOMAIN_GLOSSARY.md API field names. This alignment
ensures the persistence layer, the engine contract, and the API response
schema speak the same language.

**Mutability:** STRICTLY IMMUTABLE.

**Privilege:** INSERT only. No UPDATE, no DELETE.

```
Column                              Type            Constraints     Notes
──────────────────────────────────────────────────────────────────────────────
id                                  UUID            PK, REQUIRED    [IMMUTABLE]
snapshot_id                         UUID            REQUIRED, UNIQUE, FK → snapshot_calculations

gross_annual_rent_gbp               NUMERIC(15,6)   REQUIRED        [IMMUTABLE]
effective_annual_rent_gbp           NUMERIC(15,6)   REQUIRED        [IMMUTABLE]
total_operating_costs_annual_gbp    NUMERIC(15,6)   REQUIRED        [IMMUTABLE]
net_operating_income_gbp            NUMERIC(15,6)   REQUIRED        [IMMUTABLE]
annual_mortgage_cost_gbp            NUMERIC(15,6)   REQUIRED        [IMMUTABLE]
annual_tax_liability_gbp            NUMERIC(15,6)   REQUIRED        [IMMUTABLE]
annual_cash_flow_gbp                NUMERIC(15,6)   REQUIRED        [IMMUTABLE] May be negative
monthly_cash_flow_gbp               NUMERIC(15,6)   REQUIRED        [IMMUTABLE] May be negative
gross_yield_percent                 NUMERIC(10,6)   REQUIRED        [IMMUTABLE]
net_yield_percent                   NUMERIC(10,6)   REQUIRED        [IMMUTABLE]
roce_percent                        NUMERIC(10,6)   REQUIRED        [IMMUTABLE]
cash_on_cash_return_percent         NUMERIC(10,6)   REQUIRED        [IMMUTABLE] May be negative
ltv_percent                         NUMERIC(10,6)   REQUIRED        [IMMUTABLE]
icr_percent                         NUMERIC(10,6)   NULLABLE        [IMMUTABLE] NULL for cash purchase (loan = 0)
total_sdlt_gbp                      NUMERIC(15,6)   REQUIRED        [IMMUTABLE]
total_acquisition_cost_gbp          NUMERIC(15,6)   REQUIRED        [IMMUTABLE]
total_cash_deployed_gbp             NUMERIC(15,6)   REQUIRED        [IMMUTABLE]

created_at                          TIMESTAMPTZ     REQUIRED, DEFAULT NOW()  [IMMUTABLE]
```

**Constraints:**
- `UNIQUE (snapshot_id)`
- `CHECK (gross_annual_rent_gbp >= 0)`
- `CHECK (effective_annual_rent_gbp >= 0)`
- `CHECK (total_operating_costs_annual_gbp >= 0)`
- `CHECK (annual_tax_liability_gbp >= 0)`
- `CHECK (total_sdlt_gbp >= 0)`
- `CHECK (total_acquisition_cost_gbp >= 0)`
- `CHECK (total_cash_deployed_gbp >= 0)`
- `CHECK (ltv_percent >= 0 AND ltv_percent <= 100)`
- `CHECK (icr_percent IS NULL OR icr_percent >= 0)`
- `CHECK (gross_yield_percent >= 0)`

Note: `annual_cash_flow_gbp`, `monthly_cash_flow_gbp`, `cash_on_cash_return_percent`,
`net_operating_income_gbp`, `roce_percent`, and `net_yield_percent` have NO lower
bound check because negative values are valid calculation results.

**Indexes:**
- `PRIMARY KEY (id)`
- `UNIQUE INDEX ON snapshot_outputs (snapshot_id)` — enforces 1:1, enables efficient join

---

## Table: snapshot_intermediates

**Responsibility:** Every intermediate calculated value produced during the
engine pipeline. Not displayed to users in routine operation. Loaded on demand
for audit views, explainability features (Phase 3+), and reproducibility
verification. Contains the full calculation lineage.

**Mutability:** STRICTLY IMMUTABLE.

**Privilege:** INSERT only. No UPDATE, no DELETE.

```
Column                              Type             Constraints     Notes
────────────────────────────────────────────────────────────────────────────────
id                                  UUID             PK, REQUIRED    [IMMUTABLE]
snapshot_id                         UUID             REQUIRED, UNIQUE, FK → snapshot_calculations

void_rate_decimal_applied           NUMERIC(15,10)   REQUIRED        [IMMUTABLE] Higher precision: full working value
gross_annual_rent_gbp               NUMERIC(15,6)    REQUIRED        [IMMUTABLE]
effective_annual_rent_gbp           NUMERIC(15,6)    REQUIRED        [IMMUTABLE]
loan_amount_gbp                     NUMERIC(15,6)    REQUIRED        [IMMUTABLE]
ltv_percent                         NUMERIC(10,6)    REQUIRED        [IMMUTABLE]
monthly_mortgage_payment_gbp        NUMERIC(15,6)    REQUIRED        [IMMUTABLE]
annual_mortgage_cost_gbp            NUMERIC(15,6)    REQUIRED        [IMMUTABLE]
annual_mortgage_interest_gbp        NUMERIC(15,6)    REQUIRED        [IMMUTABLE]
letting_agent_annual_gbp            NUMERIC(15,6)    REQUIRED        [IMMUTABLE]
letting_agent_vat_rate_applied      NUMERIC(10,6)    REQUIRED        [IMMUTABLE] Config value used
annual_maintenance_reserve_gbp      NUMERIC(15,6)    REQUIRED        [IMMUTABLE]
total_operating_costs_annual_gbp    NUMERIC(15,6)    REQUIRED        [IMMUTABLE]
net_operating_income_gbp            NUMERIC(15,6)    REQUIRED        [IMMUTABLE]
sdlt_band_breakdown                 JSONB            REQUIRED        [IMMUTABLE] See JSONB structure below
sdlt_base_gbp                       NUMERIC(15,6)    REQUIRED        [IMMUTABLE]
sdlt_surcharge_gbp                  NUMERIC(15,6)    REQUIRED        [IMMUTABLE]
sdlt_surcharge_rate_applied         NUMERIC(10,6)    REQUIRED        [IMMUTABLE] Config value used
total_sdlt_gbp                      NUMERIC(15,6)    REQUIRED        [IMMUTABLE]
total_acquisition_cost_gbp          NUMERIC(15,6)    REQUIRED        [IMMUTABLE]
total_cash_deployed_gbp             NUMERIC(15,6)    REQUIRED        [IMMUTABLE]
stressed_annual_interest_gbp        NUMERIC(15,6)    REQUIRED        [IMMUTABLE]
stress_test_rate_applied_percent    NUMERIC(10,6)    REQUIRED        [IMMUTABLE] Config value used
taxable_income_or_profit_gbp        NUMERIC(15,6)    REQUIRED        [IMMUTABLE] May be negative
income_tax_gross_gbp                NUMERIC(15,6)    NULLABLE        [IMMUTABLE] NULL for LIMITED_COMPANY pathway
mortgage_interest_tax_credit_gbp    NUMERIC(15,6)    NULLABLE        [IMMUTABLE] NULL for LIMITED_COMPANY pathway
corporation_tax_gross_gbp           NUMERIC(15,6)    NULLABLE        [IMMUTABLE] NULL for INDIVIDUAL pathway
annual_tax_liability_gbp            NUMERIC(15,6)    REQUIRED        [IMMUTABLE]
pre_tax_annual_cash_flow_gbp        NUMERIC(15,6)    REQUIRED        [IMMUTABLE] May be negative
section_24_applies                  BOOLEAN          REQUIRED        [IMMUTABLE]

created_at                          TIMESTAMPTZ      REQUIRED, DEFAULT NOW()  [IMMUTABLE]
```

**Constraints:**
- `UNIQUE (snapshot_id)`
- `CHECK (void_rate_decimal_applied >= 0 AND void_rate_decimal_applied <= 1)`
- `CHECK (loan_amount_gbp >= 0)`
- `CHECK (ltv_percent >= 0 AND ltv_percent <= 100)`
- `CHECK (sdlt_base_gbp >= 0)`
- `CHECK (sdlt_surcharge_gbp >= 0)`
- `CHECK (total_sdlt_gbp >= 0)`
- `CHECK (annual_tax_liability_gbp >= 0)`
- `CHECK (income_tax_gross_gbp IS NULL OR income_tax_gross_gbp >= 0)`
- `CHECK (mortgage_interest_tax_credit_gbp IS NULL OR mortgage_interest_tax_credit_gbp >= 0)`
- `CHECK (corporation_tax_gross_gbp IS NULL OR corporation_tax_gross_gbp >= 0)`

**JSONB structure for sdlt_band_breakdown:**
Stored as an ordered JSON array. Each element represents one SDLT band.
All numeric values are stored as strings to prevent floating-point
representation loss.

```json
[
  {
    "band_lower": "0.00",
    "band_upper": "125000.00",
    "rate": "0.00",
    "taxable_in_band": "125000.00",
    "tax_in_band": "0.00"
  },
  {
    "band_lower": "125000.00",
    "band_upper": "250000.00",
    "rate": "0.02",
    "taxable_in_band": "75000.00",
    "tax_in_band": "1500.00"
  }
]
```

Only the bands that apply (where `taxable_in_band > 0`) are included. The
top band (band_upper = null in the config) stores band_upper as null in
the JSON.

**Indexes:**
- `PRIMARY KEY (id)`
- `UNIQUE INDEX ON snapshot_intermediates (snapshot_id)` — enforces 1:1

---

## Table: snapshot_risk_flags

**Responsibility:** One row per triggered risk flag per calculation. Stored
as rows (not JSON) to enable cross-snapshot querying and future portfolio
analytics (Phase 4).

**Mutability:** STRICTLY IMMUTABLE.

**Privilege:** INSERT only. No UPDATE, no DELETE.

```
Column                  Type                Constraints     Notes
──────────────────────────────────────────────────────────────────────────────
id                      UUID                PK, REQUIRED    [IMMUTABLE]
snapshot_id             UUID                REQUIRED, FK → snapshot_calculations

flag_code               TEXT                REQUIRED        [IMMUTABLE] e.g. "NEGATIVE_CASHFLOW"
severity                flag_severity_enum  REQUIRED        [IMMUTABLE]
triggered_by_field      TEXT                REQUIRED        [IMMUTABLE] e.g. "annual_cash_flow_gbp"
triggered_by_value      TEXT                REQUIRED        [IMMUTABLE] String representation of the value at trigger
message                 TEXT                REQUIRED        [IMMUTABLE] User-facing message at time of calculation

created_at              TIMESTAMPTZ         REQUIRED, DEFAULT NOW()  [IMMUTABLE]
```

**Constraints:**
- `CHECK (flag_code <> '')` — non-empty code
- `CHECK (triggered_by_field <> '')`
- `CHECK (triggered_by_value <> '')`
- `CHECK (message <> '')`

**Valid flag_code values (enforced at application layer, documented here):**
```
NEGATIVE_CASHFLOW
NEGATIVE_NOI
LOW_GROSS_YIELD
LOW_NET_YIELD
LOW_ICR_BASIC
LOW_ICR_HIGHER_RATE
HIGH_LEVERAGE
HIGH_LEVERAGE_EXTREME
LOW_MARGIN_SAFETY
HIGH_REFURB_RATIO
SECTION_24_IMPACT
ATED_WARNING
LEASEHOLD_SHORT_LEASE
CASH_FLOW_PRE_TAX_ONLY
LTD_EXTRACTION_UNDISCLOSED
RENT_UNVERIFIED
```

Note: A CHECK constraint on flag_code is not added at the database level in
Phase 1 because new flag codes will be added with future engine versions.
A database-level constraint would require a migration every time a new flag
is introduced. Application-layer validation is sufficient.

**Indexes:**
- `PRIMARY KEY (id)`
- `INDEX ON snapshot_risk_flags (snapshot_id)` — all flags for a snapshot
- `INDEX ON snapshot_risk_flags (flag_code)` — cross-deal flag analytics (Phase 4)

---

## Table: snapshot_validation_warnings

**Responsibility:** One row per validation warning (WARN-severity rules that
did not block calculation) recorded at the time of calculation. Stores the
exact warning message shown to the user for explainability and audit.

**Mutability:** STRICTLY IMMUTABLE.

**Privilege:** INSERT only. No UPDATE, no DELETE.

```
Column                  Type            Constraints     Notes
──────────────────────────────────────────────────────────────────────────────
id                      UUID            PK, REQUIRED    [IMMUTABLE]
snapshot_id             UUID            REQUIRED, FK → snapshot_calculations

rule_code               TEXT            REQUIRED        [IMMUTABLE] e.g. "V-08"
field                   TEXT            REQUIRED        [IMMUTABLE] Input field that triggered the warning
message                 TEXT            REQUIRED        [IMMUTABLE] User-facing message at time of calculation

created_at              TIMESTAMPTZ     REQUIRED, DEFAULT NOW()  [IMMUTABLE]
```

**Constraints:**
- `CHECK (rule_code ~ '^V-[0-9]+$')` — validates rule code format
- `CHECK (field <> '')`
- `CHECK (message <> '')`

**Indexes:**
- `PRIMARY KEY (id)`
- `INDEX ON snapshot_validation_warnings (snapshot_id)` — all warnings for a snapshot

---

---

# Section 4 — Configuration Domain Tables

All configuration tables are STRICTLY APPEND-ONLY. Records are inserted and
never updated or deleted. Each table uses an `effective_from` DATE to define
when a version became active.

**Privilege on all config tables:** INSERT only. No UPDATE, no DELETE.

---

## Table: config_engine_versions

**Responsibility:** Registry of all deployed engine versions. Provides a
human-readable reference for what formula logic corresponds to the
`engine_version` string stored in `snapshot_calculations`.

**Note:** This table uses the semantic version string as the primary key,
not a UUID. This makes snapshot records self-documenting — `engine_version = "1.0.0"`
is immediately interpretable without a join.

```
Column                  Type        Constraints                 Notes
──────────────────────────────────────────────────────────────────────────
version_string          TEXT        PK, REQUIRED                e.g. "1.0.0"
released_at             TIMESTAMPTZ REQUIRED
change_summary          TEXT        REQUIRED
is_breaking_change      BOOLEAN     REQUIRED                    TRUE for MAJOR version increments
specification_ref       TEXT        NULLABLE                    e.g. git commit hash or CALCULATION_SPEC version
created_at              TIMESTAMPTZ REQUIRED, DEFAULT NOW()
```

**Indexes:**
- `PRIMARY KEY (version_string)`

---

## Table: config_sdlt_versions

**Responsibility:** Versioned SDLT configuration root record. One record per
effective SDLT rate change. Child `config_sdlt_bands` records hold the actual
band structure.

```
Column                              Type                    Constraints         Notes
──────────────────────────────────────────────────────────────────────────────────────
id                                  UUID                    PK, REQUIRED
effective_from                      DATE                    REQUIRED            Date rates became effective
property_country                    property_country_enum   REQUIRED            ENGLAND in Phase 1
additional_dwelling_surcharge_rate  NUMERIC(10,6)           REQUIRED            e.g. 0.03 for 3%
notes                               TEXT                    NULLABLE            e.g. "Post-April 2025 threshold reversion"
source_attribution                  TEXT                    NULLABLE            e.g. "Finance Act 2024, HMRC guidance"
created_at                          TIMESTAMPTZ             REQUIRED, DEFAULT NOW()
created_by_user_id                  UUID                    NULLABLE, FK → users  Admin who inserted this version
```

**Constraints:**
- `CHECK (additional_dwelling_surcharge_rate >= 0 AND additional_dwelling_surcharge_rate <= 1)`
- `UNIQUE (effective_from, property_country)` — one SDLT version per country per date

**Indexes:**
- `PRIMARY KEY (id)`
- `INDEX ON config_sdlt_versions (effective_from DESC)` — active config resolution
- `INDEX ON config_sdlt_versions (property_country, effective_from DESC)` — country-filtered resolution

---

## Table: config_sdlt_bands

**Responsibility:** Individual band records for each SDLT configuration version.
One row per band. Together with the parent `config_sdlt_versions` record, these
define the complete banded rate structure used in SDLT calculation (F-13).

```
Column              Type                Constraints             Notes
──────────────────────────────────────────────────────────────────────────
id                  UUID                PK, REQUIRED
sdlt_version_id     UUID                REQUIRED, FK → config_sdlt_versions
band_order          SMALLINT            REQUIRED                1-based, ascending; defines display and iteration order
band_lower          NUMERIC(15,6)       REQUIRED                Lower bound (inclusive), e.g. 0 or 125000
band_upper          NUMERIC(15,6)       NULLABLE                Upper bound (exclusive); NULL for the top band
rate                NUMERIC(10,6)       REQUIRED                e.g. 0.02 for 2%
created_at          TIMESTAMPTZ         REQUIRED, DEFAULT NOW()
```

**Constraints:**
- `CHECK (band_lower >= 0)`
- `CHECK (band_upper IS NULL OR band_upper > band_lower)`
- `CHECK (rate >= 0 AND rate <= 1)`
- `CHECK (band_order > 0)`
- `UNIQUE (sdlt_version_id, band_order)` — each band position is unique per version

**Indexes:**
- `PRIMARY KEY (id)`
- `INDEX ON config_sdlt_bands (sdlt_version_id, band_order)` — ordered band retrieval for a version

---

## Table: config_corporation_tax_versions

**Responsibility:** Versioned Corporation Tax rate and threshold configuration.
Stores all values required for the Tax Pathway B calculation in the engine,
including the marginal relief fraction.

```
Column                              Type            Constraints         Notes
──────────────────────────────────────────────────────────────────────────────
id                                  UUID            PK, REQUIRED
effective_from                      DATE            REQUIRED
small_profits_rate                  NUMERIC(10,6)   REQUIRED            e.g. 0.19 for 19%
small_profits_upper_threshold       NUMERIC(15,6)   REQUIRED            e.g. 50000
main_rate                           NUMERIC(10,6)   REQUIRED            e.g. 0.25 for 25%
main_rate_lower_threshold           NUMERIC(15,6)   REQUIRED            e.g. 250000
marginal_relief_numerator           SMALLINT        REQUIRED            e.g. 3
marginal_relief_denominator         SMALLINT        REQUIRED            e.g. 200
notes                               TEXT            NULLABLE
source_attribution                  TEXT            NULLABLE            e.g. "Finance Act 2023"
created_at                          TIMESTAMPTZ     REQUIRED, DEFAULT NOW()
created_by_user_id                  UUID            NULLABLE, FK → users
```

**Constraints:**
- `UNIQUE (effective_from)` — one CT version per effective date
- `CHECK (small_profits_rate >= 0 AND small_profits_rate <= 1)`
- `CHECK (main_rate >= 0 AND main_rate <= 1)`
- `CHECK (small_profits_upper_threshold < main_rate_lower_threshold)`
- `CHECK (marginal_relief_numerator > 0)`
- `CHECK (marginal_relief_denominator > 0)`

**Indexes:**
- `PRIMARY KEY (id)`
- `INDEX ON config_corporation_tax_versions (effective_from DESC)` — active config resolution

---

## Table: config_assumption_versions

**Responsibility:** Versioned operational assumption defaults. One record per
version containing all default values used when a user does not override an
optional input. A complete record is inserted when any default changes — all
values are copied forward for unchanged assumptions.

```
Column                                  Type            Constraints         Notes
────────────────────────────────────────────────────────────────────────────────────
id                                      UUID            PK, REQUIRED
effective_from                          DATE            REQUIRED
void_rate_percent_default               NUMERIC(10,6)   REQUIRED            e.g. 3.85
letting_agent_fee_percent_default       NUMERIC(10,6)   REQUIRED            e.g. 10.0 (VAT applied separately in engine)
letting_agent_vat_rate_percent          NUMERIC(10,6)   REQUIRED            e.g. 20.0
maintenance_reserve_percent_default     NUMERIC(10,6)   REQUIRED            e.g. 1.0
landlord_insurance_annual_default       NUMERIC(15,6)   REQUIRED            e.g. 800.00
purchase_legal_costs_default            NUMERIC(15,6)   REQUIRED            e.g. 2500.00
accountancy_cost_individual_default     NUMERIC(15,6)   REQUIRED            e.g. 0.00
accountancy_cost_ltd_default            NUMERIC(15,6)   REQUIRED            e.g. 1200.00
stress_test_rate_percent                NUMERIC(10,6)   REQUIRED            e.g. 5.5
icr_threshold_basic_rate_percent        NUMERIC(10,6)   REQUIRED            e.g. 125.0
icr_threshold_higher_rate_percent       NUMERIC(10,6)   REQUIRED            e.g. 145.0
notes                                   TEXT            NULLABLE
source_attribution                      TEXT            NULLABLE
created_at                              TIMESTAMPTZ     REQUIRED, DEFAULT NOW()
created_by_user_id                      UUID            NULLABLE, FK → users
```

**Constraints:**
- `UNIQUE (effective_from)` — one assumption version per effective date
- `CHECK (void_rate_percent_default >= 0 AND void_rate_percent_default <= 100)`
- `CHECK (letting_agent_fee_percent_default >= 0)`
- `CHECK (letting_agent_vat_rate_percent >= 0)`
- `CHECK (maintenance_reserve_percent_default >= 0)`
- `CHECK (landlord_insurance_annual_default >= 0)`
- `CHECK (purchase_legal_costs_default >= 0)`
- `CHECK (accountancy_cost_individual_default >= 0)`
- `CHECK (accountancy_cost_ltd_default >= 0)`
- `CHECK (stress_test_rate_percent > 0)`
- `CHECK (icr_threshold_basic_rate_percent > 0)`
- `CHECK (icr_threshold_higher_rate_percent >= icr_threshold_basic_rate_percent)`

**Indexes:**
- `PRIMARY KEY (id)`
- `INDEX ON config_assumption_versions (effective_from DESC)` — active config resolution

---

---

# Section 5 — Audit Domain Tables

Audit tables are append-only. The application database role has INSERT
privilege only.

---

## Table: audit_calculations

**Responsibility:** Records every calculation attempt regardless of outcome.
This table is the operational audit record of the calculation service's
behaviour.

**Mutability:** STRICTLY APPEND-ONLY. INSERT only, no UPDATE, no DELETE.

**Privilege:** INSERT only.

```
Column                  Type                        Constraints         Notes
──────────────────────────────────────────────────────────────────────────────────
id                      UUID                        PK, REQUIRED
user_id                 UUID                        REQUIRED, FK → users
deal_id                 UUID                        REQUIRED, FK → deals
snapshot_id             UUID                        NULLABLE, FK → snapshot_calculations  NULL for failure outcomes
triggered_at            TIMESTAMPTZ                 REQUIRED            When the calculation was initiated
outcome                 calculation_outcome_enum    REQUIRED
engine_version          TEXT                        REQUIRED            Engine version at time of attempt
validation_errors       JSONB                       NULLABLE            For VALIDATION_FAILURE: [{rule_code, field, message}]
error_detail            TEXT                        NULLABLE            For ENGINE_ERROR: sanitised description
client_context          TEXT                        NULLABLE            e.g. "web", "api"
created_at              TIMESTAMPTZ                 REQUIRED, DEFAULT NOW()
```

**Constraints:**
- `CHECK (outcome <> 'SUCCESS' OR snapshot_id IS NOT NULL)` — SUCCESS must have a snapshot
- `CHECK (outcome <> 'VALIDATION_FAILURE' OR validation_errors IS NOT NULL)` — failures must have errors
- `CHECK (triggered_at IS NOT NULL)`

**Indexes:**
- `PRIMARY KEY (id)`
- `INDEX ON audit_calculations (user_id, triggered_at DESC)` — user's calculation history
- `INDEX ON audit_calculations (deal_id, triggered_at DESC)` — calculation history for a deal
- `INDEX ON audit_calculations (outcome)` — failure analysis queries

---

---

# Section 6 — Foreign Key Relationship Map

This section summarises all foreign key relationships defined in the schema.

```
snapshot_calculations.deal_id
    → deals.id

snapshot_calculations.user_id
    → users.id

snapshot_calculations.assumption_config_version_id
    → config_assumption_versions.id

snapshot_calculations.sdlt_config_version_id
    → config_sdlt_versions.id

snapshot_calculations.corporation_tax_config_version_id
    → config_corporation_tax_versions.id

snapshot_inputs.snapshot_id
    → snapshot_calculations.id  [UNIQUE — enforces 1:1]

snapshot_outputs.snapshot_id
    → snapshot_calculations.id  [UNIQUE — enforces 1:1]

snapshot_intermediates.snapshot_id
    → snapshot_calculations.id  [UNIQUE — enforces 1:1]

snapshot_risk_flags.snapshot_id
    → snapshot_calculations.id

snapshot_validation_warnings.snapshot_id
    → snapshot_calculations.id

config_sdlt_bands.sdlt_version_id
    → config_sdlt_versions.id

config_sdlt_versions.created_by_user_id
    → users.id  [NULLABLE]

config_corporation_tax_versions.created_by_user_id
    → users.id  [NULLABLE]

config_assumption_versions.created_by_user_id
    → users.id  [NULLABLE]

audit_calculations.user_id
    → users.id

audit_calculations.deal_id
    → deals.id

audit_calculations.snapshot_id
    → snapshot_calculations.id  [NULLABLE]

deals.user_id
    → users.id

deals.property_id
    → properties.id

deals.latest_snapshot_id
    → snapshot_calculations.id  [NULLABLE]

deals.investor_profile_id
    → investor_profiles.id  [NULLABLE]

investor_profiles.user_id
    → users.id

properties.user_id
    → users.id
```

---

## ON DELETE behaviour for all foreign keys

All foreign keys use `ON DELETE RESTRICT`. No cascade deletes are permitted.

Rationale: Hard deletion is not permitted at the application layer for any
table. The RESTRICT constraint prevents hard deletion at the database layer
as a safety net. If a future operation attempts to delete a user who has
deals and snapshots, the database rejects it — forcing the application to
use the soft archive path.

---

---

# Section 7 — Application Database Role Permissions

---

## Role: propiq_app (runtime application role)

This is the role used by the FastAPI backend at runtime.

```
TABLE                               SELECT  INSERT  UPDATE  DELETE
───────────────────────────────────────────────────────────────────
users                               YES     YES     YES     NO
investor_profiles                   YES     YES     YES     NO
properties                          YES     YES     YES     NO
deals                               YES     YES     YES     NO

snapshot_calculations               YES     YES     NO*     NO
snapshot_inputs                     YES     YES     NO      NO
snapshot_outputs                    YES     YES     NO      NO
snapshot_intermediates              YES     YES     NO      NO
snapshot_risk_flags                 YES     YES     NO      NO
snapshot_validation_warnings        YES     YES     NO      NO

config_engine_versions              YES     NO      NO      NO
config_sdlt_versions                YES     NO      NO      NO
config_sdlt_bands                   YES     NO      NO      NO
config_corporation_tax_versions     YES     NO      NO      NO
config_assumption_versions          YES     NO      NO      NO

audit_calculations                  YES     YES     NO      NO
```

* `snapshot_calculations`: Column-level UPDATE grant on `is_superseded`
  and `superseded_at` only:
  ```
  GRANT UPDATE (is_superseded, superseded_at)
    ON snapshot_calculations
    TO propiq_app;
  ```

---

## Role: propiq_admin (admin operations and configuration management)

Used by admin-only API routes for configuration version insertion and by
migration scripts.

```
TABLE                               SELECT  INSERT  UPDATE  DELETE
───────────────────────────────────────────────────────────────────
All tables above                    YES     YES     NO      NO
config_sdlt_versions                YES     YES     NO      NO
config_sdlt_bands                   YES     YES     NO      NO
config_corporation_tax_versions     YES     YES     NO      NO
config_assumption_versions          YES     YES     NO      NO
config_engine_versions              YES     YES     NO      NO
```

Note: Even the admin role has no UPDATE or DELETE on any table. New
configuration versions are always INSERTs. Admin configuration is just the
runtime app role with broader INSERT permission on config tables.

---

## Role: propiq_migrations (migration execution)

Used exclusively by Alembic migration execution. Has superuser-equivalent
DDL privileges. Never used by the application at runtime.

```
SUPERUSER capabilities for DDL:
  CREATE TABLE, ALTER TABLE, DROP TABLE (migration only)
  CREATE INDEX, DROP INDEX
  CREATE TYPE, DROP TYPE
  GRANT privileges to other roles
```

This role is not available to any application code path.

---

---

# Section 8 — Complete Index Reference

All indexes defined for Phase 1, organised by table.

```
TABLE: users
  PRIMARY KEY (id)
  UNIQUE INDEX ON users (supabase_auth_id)
  INDEX ON users (email)

TABLE: investor_profiles
  PRIMARY KEY (id)
  INDEX ON investor_profiles (user_id)

TABLE: properties
  PRIMARY KEY (id)
  INDEX ON properties (user_id)
  INDEX ON properties (postcode)

TABLE: deals
  PRIMARY KEY (id)
  INDEX ON deals (user_id)
  INDEX ON deals (property_id)
  INDEX ON deals (latest_snapshot_id)

TABLE: snapshot_calculations
  PRIMARY KEY (id)
  INDEX ON snapshot_calculations (deal_id)
  INDEX ON snapshot_calculations (deal_id, is_superseded)
  INDEX ON snapshot_calculations (user_id)
  INDEX ON snapshot_calculations (engine_version)

TABLE: snapshot_inputs
  PRIMARY KEY (id)
  UNIQUE INDEX ON snapshot_inputs (snapshot_id)

TABLE: snapshot_outputs
  PRIMARY KEY (id)
  UNIQUE INDEX ON snapshot_outputs (snapshot_id)

TABLE: snapshot_intermediates
  PRIMARY KEY (id)
  UNIQUE INDEX ON snapshot_intermediates (snapshot_id)

TABLE: snapshot_risk_flags
  PRIMARY KEY (id)
  INDEX ON snapshot_risk_flags (snapshot_id)
  INDEX ON snapshot_risk_flags (flag_code)

TABLE: snapshot_validation_warnings
  PRIMARY KEY (id)
  INDEX ON snapshot_validation_warnings (snapshot_id)

TABLE: config_engine_versions
  PRIMARY KEY (version_string)

TABLE: config_sdlt_versions
  PRIMARY KEY (id)
  INDEX ON config_sdlt_versions (effective_from DESC)
  INDEX ON config_sdlt_versions (property_country, effective_from DESC)
  UNIQUE (effective_from, property_country)

TABLE: config_sdlt_bands
  PRIMARY KEY (id)
  INDEX ON config_sdlt_bands (sdlt_version_id, band_order)
  UNIQUE (sdlt_version_id, band_order)

TABLE: config_corporation_tax_versions
  PRIMARY KEY (id)
  INDEX ON config_corporation_tax_versions (effective_from DESC)
  UNIQUE (effective_from)

TABLE: config_assumption_versions
  PRIMARY KEY (id)
  INDEX ON config_assumption_versions (effective_from DESC)
  UNIQUE (effective_from)

TABLE: audit_calculations
  PRIMARY KEY (id)
  INDEX ON audit_calculations (user_id, triggered_at DESC)
  INDEX ON audit_calculations (deal_id, triggered_at DESC)
  INDEX ON audit_calculations (outcome)
```

---

---

# Section 9 — Configuration Seed Data

This section defines the exact values to be inserted into configuration tables
when the database is first provisioned. These values are sourced from
ENGINE_CONTRACTS.md Part 2 and CALCULATION_SPEC.md.

Seed data is inserted via a separate idempotent seed script (not inside
migration files). The script checks for existing records before inserting
and is safe to re-run.

---

## Seed: config_engine_versions

```
version_string:     "1.0.0"
released_at:        (deployment timestamp)
change_summary:     "Initial engine release. Implements CALCULATION_SPEC v1.0.
                    Covers RESIDENTIAL_SINGLE_LET, ENGLAND, INDIVIDUAL and
                    LIMITED_COMPANY ownership, interest-only and repayment
                    mortgages, SDLT with additional dwelling surcharge,
                    Section 24 tax handling, Corporation Tax Pathway B."
is_breaking_change: FALSE
specification_ref:  "CALCULATION_SPEC.md v1.0"
```

---

## Seed: config_sdlt_versions (England, effective 1 April 2025)

```
effective_from:                     2025-04-01
property_country:                   ENGLAND
additional_dwelling_surcharge_rate: 0.030000
notes:                              "Post-temporary threshold reversion.
                                    Residential rates effective from 1 April 2025."
source_attribution:                 "HMRC SDLT guidance. Finance Act 2024.
                                    Temporary nil-rate band threshold ended March 2025."
```

---

## Seed: config_sdlt_bands (for the above SDLT version)

```
Band 1:
  band_order: 1
  band_lower: 0.00
  band_upper: 125000.00
  rate:       0.000000

Band 2:
  band_order: 2
  band_lower: 125000.00
  band_upper: 250000.00
  rate:       0.020000

Band 3:
  band_order: 3
  band_lower: 250000.00
  band_upper: 925000.00
  rate:       0.050000

Band 4:
  band_order: 4
  band_lower: 925000.00
  band_upper: 1500000.00
  rate:       0.100000

Band 5:
  band_order: 5
  band_lower: 1500000.00
  band_upper: NULL         (top band — no upper limit)
  rate:       0.120000
```

**SDLT Band Boundary Verification (from CALCULATION_SPEC.md F-13):**
On a purchase of £200,000 with is_additional_dwelling = true:
- Band 1: £125,000 × 0% = £0.00
- Band 2: £75,000 × 2% = £1,500.00
- sdlt_base = £1,500.00
- surcharge = £200,000 × 3% = £6,000.00
- total_sdlt = £7,500.00
Matches ENGINE_CONTRACTS.md E-01 expected value. Seed data verified.

---

## Seed: config_corporation_tax_versions (2025/26)

```
effective_from:                  2023-04-01
small_profits_rate:              0.190000
small_profits_upper_threshold:   50000.00
main_rate:                       0.250000
main_rate_lower_threshold:       250000.00
marginal_relief_numerator:       3
marginal_relief_denominator:     200
notes:                           "Finance Act 2023. Small profits rate 19%.
                                 Main rate 25%. Marginal relief 3/200 fraction.
                                 Rates effective from 1 April 2023."
source_attribution:              "Finance Act 2023. HMRC Corporation Tax guidance."
```

---

## Seed: config_assumption_versions (v1.0 defaults)

```
effective_from:                          2025-01-01
void_rate_percent_default:               3.850000
  (Rationale: 2/52 weeks void = 3.846%. Source: ARLA Propertymark 2023/24 data.)

letting_agent_fee_percent_default:       10.000000
  (Rationale: Mid-market full management fee, England. Range: 8-15% + VAT.
   VAT (20%) is applied at calculation time, not stored here.)

letting_agent_vat_rate_percent:          20.000000
  (Current UK standard VAT rate.)

maintenance_reserve_percent_default:     1.000000
  (Rationale: Standard UK rule of thumb: 1% of property value per year.)

landlord_insurance_annual_default:       800.000000
  (Rationale: Mid-market estimate, standard single-let England. Range: £300-£1,500.)

purchase_legal_costs_default:            2500.000000
  (Rationale: Conveyancing £1,000-£2,000 + RICS Level 2 survey £300-£600.)

accountancy_cost_individual_default:     0.000000
  (Rationale: Individual landlords frequently self-file. Users who use
   an accountant should override this.)

accountancy_cost_ltd_default:            1200.000000
  (Rationale: Estimate for simple SPV annual accounts + CT return.
   Range: £800-£2,500.)

stress_test_rate_percent:                5.500000
  (Rationale: Conservative floor rate. Typical lender stress range: 5.5%-7.0%.
   This is a configurable assumption, not a regulatory requirement.)

icr_threshold_basic_rate_percent:        125.000000
  (Rationale: Standard BTL lender threshold. Source: PRA guidance and
   common lender practice.)

icr_threshold_higher_rate_percent:       145.000000
  (Rationale: Higher threshold for higher/additional rate taxpayers, reflecting
   Section 24 impact. Applied by many lenders post-2017 reforms.)

notes:                                   "Initial v1.0 assumption defaults.
                                         Sources: ARLA Propertymark, HMRC,
                                         industry market data 2023/24."
source_attribution:                      "ARLA Propertymark Letting Agent Survey 2023.
                                         HMRC landlord guidance 2024.
                                         PRA supervisory statement SS13/16."
```

---

---

# Section 10 — Schema Decisions Deferred to Later Phases

The following schema elements are intentionally excluded from Phase 1. Each
is designed for in PERSISTENCE_ARCHITECTURE.md and noted here to ensure
Phase 1 implementation does not inadvertently foreclose them.

---

## Phase 2 Additions

**snapshot_calculations: nullable scenario columns**
```
scenario_label      TEXT        NULLABLE  — user-defined scenario name
scenario_type       TEXT        NULLABLE  — BASE_CASE, STRESS_CASE, REFINANCE, etc.
```
Added as a migration. Existing records have null; not a breaking change.

**New table: snapshot_comparisons**
```
id, deal_id, user_id, label, snapshot_a_id, snapshot_b_id, created_at
```
Read-only after creation. Does not cache differences — always derived at
read time from immutable snapshot records.

**New table: deal_workflow_events** (append-only event log)
```
id, deal_id, event_type, event_data (JSONB), recorded_by_user_id,
recorded_at, created_at
```
One row per workflow stage transition or operational event. Never updated.

**investor_profiles: additional preference columns**
```
minimum_cash_flow_monthly   NUMERIC(15,6) NULLABLE
target_yield_percent        NUMERIC(10,6) NULLABLE
maximum_ltv_percent         NUMERIC(10,6) NULLABLE
preferred_property_types    TEXT[]        NULLABLE
risk_tolerance              TEXT          NULLABLE
```

**audit_config_changes: new admin audit table**
```
id, config_table_name, config_version_id, action (INSERT only),
admin_user_id, notes, created_at
```

**users: GDPR anonymisation support**
```
anonymised_at   TIMESTAMPTZ   NULLABLE  — set when PII is removed
```

---

## Phase 3 Additions

**New table: intel_property_locations**
```
id, property_id (FK → properties), location (GEOMETRY(POINT,4326)),
geocoded_at, geocode_source, geocode_confidence, created_at
```
GiST spatial index on `location`.

**New table: intel_area_records** (area intelligence records)
```
id, data_type, geographic_area_reference, data_source_identifier,
effective_from, data_payload (JSONB), freshness metadata columns,
imported_at, created_at
```

**config_assumption_versions: provenance extension**
```
source_provider_name    TEXT        NULLABLE
source_url              TEXT        NULLABLE
collection_date         DATE        NULLABLE
last_verified_date      DATE        NULLABLE
confidence_level        TEXT        NULLABLE  (HIGH, MEDIUM, LOW, UNVERIFIED)
```

**snapshot_inputs: intelligence FK columns (all nullable)**
```
area_intel_record_id    UUID    NULLABLE, FK → intel_area_records
epc_record_id           UUID    NULLABLE
flood_risk_record_id    UUID    NULLABLE
```

**input_source_enum: new value**
```
EXTERNAL_PROVIDER   — value was sourced from an external intelligence provider
```

---

## Phase 4 Additions

Portfolio analytics tables. Not designed in detail here. Will aggregate from
existing snapshot data without modifying it.

---

## Phase 5 Additions

**New table: ai_summaries**
```
id, snapshot_id (FK → snapshot_calculations), generated_at, model_version,
prompt_version, summary_text, summary_type, created_at
```
FK direction: ai_summaries → snapshot_calculations. Never the reverse.
AI summaries are never stored in or on snapshot tables.

**input_source_enum: new value**
```
AI_SUGGESTION   — value was suggested by AI (must be explicitly confirmed
                  by user to be promoted to USER_OVERRIDE)
```

---

---

# Section 11 — Schema Invariants

These invariants must hold for the lifetime of the database. They may not
be relaxed without a documented entry in DECISIONS.md.

1. **No float/double precision columns.** All numeric financial values use
   NUMERIC type. No FLOAT, no REAL, no DOUBLE PRECISION anywhere in the schema.

2. **All primary keys are UUID.** No SERIAL, no BIGSERIAL, no auto-increment
   integer on any table.

3. **All timestamps are TIMESTAMPTZ.** No TIMESTAMP WITHOUT TIME ZONE. The
   database timezone setting is UTC.

4. **Snapshot tables have no updated_at.** If a table has `updated_at`, it is
   mutable. Snapshot tables are immutable and have `created_at` only.

5. **All snapshot FK columns are REQUIRED.** A snapshot record must always
   reference its deal, user, and all three configuration versions. Nullable
   configuration FKs on snapshots are not permitted.

6. **Every optional input in snapshot_inputs has a paired _source column.**
   The source column is REQUIRED (not nullable). Source provenance is
   mandatory, not optional.

7. **All FK constraints use ON DELETE RESTRICT.** No CASCADE, no SET NULL on
   any foreign key in this schema.

8. **Config tables have no updated_at and no is_archived column.** They are
   append-only. Archiving is not a concept that applies to configuration records.

9. **The `is_superseded` column is the only mutable field on any snapshot
   table.** Any addition of UPDATE grants on other snapshot columns requires
   a DECISIONS.md entry.

10. **No calculated output values outside snapshot_outputs.** Columns like
    `annual_cash_flow_gbp` or `gross_yield_percent` exist only in
    `snapshot_outputs`. They are never duplicated in `deals` or `properties`.
