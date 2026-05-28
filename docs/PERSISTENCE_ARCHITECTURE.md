# PropIQ Platform — Persistence Architecture

## Purpose

This document defines the persistence architecture for the PropIQ platform.
It specifies how data is stored, classified, protected, related, and evolved
across the PostgreSQL database.

This document is not a schema implementation. It contains no SQLAlchemy models,
no Alembic migrations, no SQL DDL, and no ORM code. It defines the logical
persistence design from which schema implementation will be derived.

All terminology matches DOMAIN_GLOSSARY.md exactly.
All mutability boundaries reflect DATA_BOUNDARIES.md.
All trust requirements reflect TRUST_MODEL.md.
All architectural decisions reflect DECISIONS.md (ADR-001 through ADR-014).
All entity relationships reflect SCHEMA_ARCHITECTURE.md.

---

## Document Status

Version: 1.0
Covers: Phase 1 core persistence with explicit hooks for Phase 2-5 extensions
Applicable ADRs: ADR-002, ADR-005, ADR-007, ADR-009, ADR-010, ADR-011,
                 ADR-012, ADR-013, ADR-014

---

---

# Part 1 — PostgreSQL Persistence Philosophy

---

## 1.1 — Trust-First Storage

Persistence design follows the trust-first principle established in TRUST_MODEL.md.
The most important guarantees the database must enforce are not performance
characteristics, not query convenience, and not schema normalisation — they are
correctness and historical integrity.

A user who runs an analysis today must be able to retrieve that exact analysis
in five years and see the same numbers, the same assumptions, the same risk
flags, and understand exactly why that result was produced. The database is
the permanent record of that guarantee.

Every design decision in this document is evaluated against that requirement.

---

## 1.2 — Data Classification Governs Design

DATA_BOUNDARIES.md classifies every domain into one of four categories.
Persistence design follows directly from classification. Classification
determines mutability rules, indexing strategy, retention policy, and
the type of database-level enforcement applied.

```
IMMUTABLE (append-only, no UPDATE/DELETE permitted by application user)
    Underwriting snapshots
    Snapshot inputs
    Snapshot outputs
    Snapshot intermediates
    Snapshot risk flags
    Snapshot validation warnings
    Engine configuration records (SDLT, CT, Assumptions)
    Calculation audit log

VERSIONED MUTABLE (records never overwritten, new versions inserted)
    Engine configuration tables — append-only with effective_from dates
    Assumption configuration

OPERATIONALLY MUTABLE (changes expected and permitted)
    Users
    Investor profiles
    Properties
    Deals (workflow state)

ADVISORY / EPHEMERAL (refreshable, no historical guarantee)
    AI summary records
    Cached external intelligence records (Phase 3+)
    Area intelligence enrichment records (Phase 3+)
```

---

## 1.3 — Database-Level Enforcement of Immutability

Application-layer constraints are necessary but not sufficient. A bug, a
deployment error, or a direct database connection can bypass application code.
Immutability of snapshots and configuration records must be enforced at the
database layer.

**Mechanism: Privilege separation**

The application database user (the role used by the FastAPI backend) is
granted only the privileges it needs:

```
Snapshot tables:      INSERT only (no UPDATE, no DELETE)
Configuration tables: INSERT only (no UPDATE, no DELETE)
Audit log table:      INSERT only (no UPDATE, no DELETE)
Mutable tables:       INSERT, UPDATE (no DELETE — soft retention)
```

A superuser role (for migrations and admin operations) is separate from the
application user. The application never uses the superuser role at runtime.

This two-role design means that even if application code contained a bug that
attempted to update a snapshot record, the database would reject it at the
privilege level.

---

## 1.4 — Schema Naming Conventions

All tables are in the `public` schema in Phase 1. If schema separation becomes
necessary in later phases (e.g. separating core from intelligence tables), a
PostgreSQL schema migration is straightforward. For Phase 1, a single schema
with clear naming conventions is sufficient.

Table naming pattern: `snake_case`, plural nouns, domain-prefixed where
disambiguation is needed.

```
Core domain:
    users
    investor_profiles
    properties
    deals

Snapshot domain (prefix: snapshot_):
    snapshot_calculations
    snapshot_inputs
    snapshot_outputs
    snapshot_intermediates
    snapshot_risk_flags
    snapshot_validation_warnings

Configuration domain (prefix: config_):
    config_engine_versions
    config_sdlt_versions
    config_sdlt_bands
    config_corporation_tax_versions
    config_assumption_versions

Audit domain:
    audit_calculations

Intelligence domain (Phase 3+, prefix: intel_):
    intel_area_records
    intel_property_locations

AI domain (Phase 5+, prefix: ai_):
    ai_summaries
```

---

## 1.5 — UUID Primary Keys Throughout

All tables use UUID v4 primary keys, not auto-incrementing integers.

Rationale:
- UUIDs are safe to generate at the application layer before the database
  insert, enabling single-pass inserts without a round-trip to retrieve the ID.
- UUIDs do not reveal record count or insertion order to users, which matters
  for a trust-first platform where predictable IDs could be exploited.
- UUIDs are compatible with future distributed architectures without ID
  collision risk.
- UUIDs make snapshot references in exports and audit logs unambiguous across
  environments (staging vs production never share UUIDs).

---

## 1.6 — Timestamps

All timestamp columns store UTC datetimes. The database timezone is configured
to UTC. Application code never stores local time in the database.

Standard timestamp columns:
- `created_at` — set on INSERT, never updated (applies to all tables)
- `updated_at` — set on INSERT and UPDATE (applies to mutable tables only)

Immutable tables have `created_at` only. They have no `updated_at` column
because they are never updated.

---

---

# Part 2 — Append-Only Snapshot Strategy

---

## 2.1 — What "Append-Only" Means in Practice

A snapshot record, once written, is never changed. This constraint applies
to every table in the `snapshot_*` namespace:

- No UPDATE statements are permitted on any column of any snapshot table.
- No DELETE statements are permitted on any snapshot record.
- The application database user has INSERT privilege only on these tables.

The only partial exception is the `is_superseded` flag on `snapshot_calculations`
(detailed in Part 2.3). This flag represents a status transition, not a data
mutation.

---

## 2.2 — Why Recalculation Creates a New Snapshot

When a user recalculates a deal — whether with updated inputs or updated
configuration — the result is a new `snapshot_calculations` record with a new
UUID. The original snapshot record is not touched except for the `is_superseded`
flag update.

This behaviour is required by ADR-002 and TRUST_MODEL.md. A user who looks
at a historical snapshot six months later must see exactly what was calculated
at that time, using exactly the assumptions and configuration that were active.
Modifying the original snapshot would destroy that guarantee.

The deal record holds a `latest_snapshot_id` pointer for display convenience.
The full history of snapshots for a deal is always accessible by querying
`snapshot_calculations` by `deal_id`.

---

## 2.3 — The is_superseded Exception

`snapshot_calculations.is_superseded` is the only column on any snapshot table
that may be written after the initial INSERT. When a new snapshot is created
for a deal, the previous snapshot's `is_superseded` is set to `true` and
`superseded_at` is set to the current UTC timestamp.

This mutation is limited to these two columns only. No calculation data,
no input data, no output data, and no configuration reference is ever changed
after initial write.

This exception is implemented as:

1. A constraint at the application layer: the snapshot service exposes only
   an `is_superseded = true` transition — no other field update is permitted.
2. A database-layer partial permission: a targeted UPDATE privilege on only
   `is_superseded` and `superseded_at` columns of `snapshot_calculations`
   is granted, not a blanket UPDATE on the table.

---

## 2.4 — Snapshot Retention Policy

Snapshots are retained permanently. There is no automated deletion, no
archival after a period of inactivity, and no expiry date.

Rationale: A snapshot may be the only auditable record of a financial decision.
A user who purchased a property in 2025 based on a PropIQ analysis may need
to retrieve that analysis for tax purposes, dispute resolution, or audit in
2030. Retention must be permanent.

Storage cost of snapshot records is minimal — a typical snapshot with all
sub-tables is a few kilobytes of structured data. Permanent retention is
operationally trivial.

---

---

# Part 3 — Immutable Historical Calculation Storage

---

## 3.1 — The Snapshot Record Family

A single completed calculation produces records in five tables. Together these
constitute a complete, self-contained record of the calculation.

```
snapshot_calculations       — root record, version references, metadata
    │
    ├── snapshot_inputs     — every input value used (one-to-one)
    ├── snapshot_outputs    — every user-facing output metric (one-to-one)
    ├── snapshot_intermediates — every intermediate calculation value (one-to-one)
    ├── snapshot_risk_flags — one row per triggered risk flag (one-to-many)
    └── snapshot_validation_warnings — one row per validation warning (one-to-many)
```

All five are written in a single database transaction. Either all five exist
or none do. There is no partial snapshot state.

---

## 3.2 — What Each Table Stores

**snapshot_calculations** (root)

The root record anchors the snapshot to a deal, a user, and a set of
configuration version references. It is the record that `deals.latest_snapshot_id`
points to.

Key fields:
- `id` — UUID primary key
- `deal_id` — FK to deals
- `user_id` — FK to users (denormalised for audit — captures who triggered it)
- `engine_version` — the semantic version string of the engine that produced
  this result (e.g. "1.0.0"). Not a FK — stored as a plain string that
  matches a record in `config_engine_versions` for cross-reference.
- `assumption_config_version_id` — FK to config_assumption_versions
- `sdlt_config_version_id` — FK to config_sdlt_versions
- `corporation_tax_config_version_id` — FK to config_corporation_tax_versions
- `calculated_at` — UTC timestamp assigned at insert time
- `is_superseded` — Boolean, default false
- `superseded_at` — nullable UTC timestamp
- `calculation_duration_ms` — integer, operational diagnostic
- `created_at`

**snapshot_inputs** (one-to-one with snapshot_calculations)

Every input value used in this specific calculation, with source provenance
tracking. The source provenance is the persistence expression of ADR-013
(user overrides always take precedence) and ADR-009 (assumption provenance).

For each optional input, two columns are stored:
- The value actually used (e.g. `void_rate_percent`)
- The source of that value (e.g. `void_rate_percent_source`)

Source values: `USER_OVERRIDE` or `CONFIG_DEFAULT`

Key structural fields:
- `id` — UUID primary key
- `snapshot_id` — FK to snapshot_calculations (unique constraint enforces 1:1)
- All required input fields
- All optional input fields, each paired with a `_source` column
- `created_at`

**snapshot_outputs** (one-to-one with snapshot_calculations)

Every user-facing output metric. Field names match the `EngineOutputs` contract
in ENGINE_CONTRACTS.md Part 3.1 exactly, ensuring the persistence schema and
the engine contract are always aligned.

Key structural fields:
- `id` — UUID primary key
- `snapshot_id` — FK to snapshot_calculations (unique constraint enforces 1:1)
- All output fields with Decimal precision
- `created_at`

**snapshot_intermediates** (one-to-one with snapshot_calculations)

Every intermediate value produced during the calculation pipeline. This table
exists primarily for auditability, explainability, and reproducibility
verification. It is not loaded in routine display operations — it is loaded
on demand for audit views, explainability features, and debugging.

Key structural fields:
- `id` — UUID primary key
- `snapshot_id` — FK to snapshot_calculations (unique constraint enforces 1:1)
- All intermediate fields from `EngineIntermediates` in ENGINE_CONTRACTS.md
- `sdlt_band_breakdown` — JSONB (ordered list of band calculations; see Part 3.3)
- `created_at`

**snapshot_risk_flags** (one-to-many with snapshot_calculations)

One row per triggered risk flag. Risk flags are stored as rows, not as a JSON
array, to support querying flags across snapshots and deals.

Key structural fields:
- `id` — UUID primary key
- `snapshot_id` — FK to snapshot_calculations
- `flag_code` — the code string (e.g. "NEGATIVE_CASHFLOW")
- `severity` — HIGH, MEDIUM, or INFO
- `triggered_by_field` — the output/intermediate field that caused the flag
- `triggered_by_value` — the value at trigger time (stored as text)
- `message` — the user-facing message at the time of calculation (stored to
  preserve what the user was told even if message wording changes later)
- `created_at`

**snapshot_validation_warnings** (one-to-many with snapshot_calculations)

One row per validation warning (WARN-severity rules that did not block
calculation). Structured the same way as risk flags for consistency.

Key structural fields:
- `id` — UUID primary key
- `snapshot_id` — FK to snapshot_calculations
- `rule_code` — e.g. "V-08"
- `field` — the input field that triggered the warning
- `message` — the user-facing warning message at time of calculation
- `created_at`

---

## 3.3 — SDLT Band Breakdown as JSONB

The SDLT band breakdown is stored as JSONB in `snapshot_intermediates` rather
than as a separate normalised table. The reasoning is documented in
SCHEMA_ARCHITECTURE.md: the breakdown is a fixed-length ordered list at
calculation time, not a variable-length relational entity that requires
independent querying.

The JSONB structure per band:
```json
{
  "band_lower": "0.00",
  "band_upper": "125000.00",
  "rate": "0.00",
  "taxable_in_band": "125000.00",
  "tax_in_band": "0.00"
}
```

All numeric values are stored as strings within the JSONB to prevent
floating-point loss. The full breakdown is stored as an ordered array of these
objects.

If future analytics requirements need to query individual SDLT band data
(e.g. aggregate platform-wide SDLT at each band), a materialised view or a
separate normalised table can be added without altering the snapshot schema.

---

---

# Part 4 — Configuration Versioning Model

---

## 4.1 — Append-Only Configuration Tables

All configuration tables are append-only. Records are inserted but never
updated or deleted. This implements ADR-005.

Each configuration table follows the same structural pattern:

```
config_[name]_versions
    id                  UUID primary key
    effective_from      DATE (not timestamp — rates change on calendar dates)
    [configuration values for this version]
    notes               TEXT (human-readable rationale for this version)
    source_attribution  TEXT (regulatory reference, e.g. "Finance Act 2024")
    created_at          UTC timestamp
    created_by_user_id  UUID FK to users (the admin who inserted this version)
```

The `effective_from` column is a DATE, not a DATETIME. Tax rate changes are
effective from a calendar date, not an hour. Using DATE prevents ambiguity
about timezone-sensitive edge cases at midnight.

---

## 4.2 — Active Configuration Resolution

The active configuration version for a given calculation date is the record
with the most recent `effective_from` date that is on or before the calculation
date.

```
SELECT * FROM config_[name]_versions
WHERE effective_from <= :calculation_date
ORDER BY effective_from DESC
LIMIT 1
```

This query is run once per configuration table per calculation. The resulting
record IDs are stored in the snapshot, not the `effective_from` date. Storing
IDs is more reliable for reproducibility: if an `effective_from` date is ever
corrected (an admin error), the snapshot still references the exact record that
was used.

---

## 4.3 — SDLT Configuration Tables

SDLT configuration requires two related tables because the band structure
is a child entity of the configuration version.

**config_sdlt_versions** — one record per effective SDLT rate change

```
id
effective_from
property_country    ENUM (ENGLAND — extensible to SCOTLAND/WALES in future)
additional_dwelling_surcharge_rate  DECIMAL
notes
source_attribution
created_at
created_by_user_id
```

**config_sdlt_bands** — one row per band per version

```
id
sdlt_version_id     FK to config_sdlt_versions
band_order          INTEGER (for display ordering)
band_lower          DECIMAL
band_upper          DECIMAL (nullable for top band)
rate                DECIMAL
created_at
```

The `property_country` field on `config_sdlt_versions` is included in Phase 1
for England only, but is designed for future Scotland (LBTT) and Wales (LTT)
expansion without schema changes.

---

## 4.4 — Corporation Tax Configuration Table

**config_corporation_tax_versions**

```
id
effective_from
small_profits_rate                  DECIMAL
small_profits_upper_threshold       DECIMAL
main_rate                           DECIMAL
main_rate_lower_threshold           DECIMAL
marginal_relief_numerator           INTEGER
marginal_relief_denominator         INTEGER
notes
source_attribution
created_at
created_by_user_id
```

All threshold and rate fields are stored explicitly rather than derived. If
the marginal relief fraction changes in a future Finance Act, a new record
is inserted with the updated numerator/denominator and the correct
`effective_from` date. Historical snapshots referencing the old version
continue to use the old fraction.

---

## 4.5 — Assumption Configuration Table

**config_assumption_versions**

```
id
effective_from
void_rate_percent_default               DECIMAL
letting_agent_fee_percent_default       DECIMAL
letting_agent_vat_rate_percent          DECIMAL
maintenance_reserve_percent_default     DECIMAL
landlord_insurance_annual_default       DECIMAL
purchase_legal_costs_default            DECIMAL
accountancy_cost_individual_default     DECIMAL
accountancy_cost_ltd_default            DECIMAL
stress_test_rate_percent                DECIMAL
icr_threshold_basic_rate_percent        DECIMAL
icr_threshold_higher_rate_percent       DECIMAL
notes
source_attribution
created_at
created_by_user_id
```

The assumption configuration is stored as one record per version, not as
individual rows per assumption. This is a deliberate design choice: when the
void rate default changes, a new complete record is inserted. Unchanged
assumptions are copied forward. This trade-off (some data duplication for
clarity) makes it trivially easy to see the complete state of all assumptions
at any point in time without complex aggregation queries.

---

## 4.6 — Engine Version Registry

**config_engine_versions**

```
version_string      TEXT primary key (the semantic version, e.g. "1.0.0")
released_at         UTC timestamp
change_summary      TEXT
is_breaking_change  BOOLEAN
specification_ref   TEXT (link or note to CALCULATION_SPEC.md version or commit)
created_at
```

The engine version is stored as its semantic version string, not a UUID.
This makes snapshot records human-readable: a snapshot with `engine_version = "1.0.0"`
is immediately interpretable without a join.

---

---

# Part 5 — Snapshot-to-Config Traceability

---

## 5.1 — Three Version References Per Snapshot

Every `snapshot_calculations` record stores three foreign keys to configuration
tables:

```
assumption_config_version_id    FK to config_assumption_versions
sdlt_config_version_id          FK to config_sdlt_versions
corporation_tax_config_version_id FK to config_corporation_tax_versions
```

These are independent references. A Budget announcement that changes SDLT rates
requires a new `config_sdlt_versions` record but does not require new records
in `config_assumption_versions` or `config_corporation_tax_versions`. Existing
snapshots retain their original SDLT version reference; new snapshots pick up
the new SDLT version.

---

## 5.2 — Reproducibility via Version References

Given a snapshot ID, historical reproducibility is achieved by:

1. Loading the snapshot's inputs from `snapshot_inputs`
2. Loading `config_assumption_versions` by `assumption_config_version_id`
3. Loading `config_sdlt_versions` and its child `config_sdlt_bands` by
   `sdlt_config_version_id`
4. Loading `config_corporation_tax_versions` by
   `corporation_tax_config_version_id`
5. Passing these to the engine as `EngineInput` and `EngineConfig`

The result must be identical to the stored `snapshot_outputs`. If it is not,
either the engine version changed (check `engine_version`) or there is a bug.

---

## 5.3 — Engine Version Traceability

The `engine_version` string in `snapshot_calculations` is stored alongside
the configuration version IDs. Together they provide complete provenance:
what formula logic ran (engine version) and what values that logic used
(configuration versions).

A MAJOR engine version change (formula change) combined with the same
configuration versions would produce different results. The `engine_version`
field captures this. Future tooling for "regulatory drift analysis" (ROADMAP.md)
will use this traceability.

---

## 5.4 — Assumption Provenance Per Input Field (ADR-009)

For each optional input in `snapshot_inputs`, a paired `_source` column records
whether the value came from:

- `USER_OVERRIDE` — the user provided this value explicitly
- `CONFIG_DEFAULT` — the value was drawn from the active assumption config

This is the persistence expression of ADR-009 (assumption provenance) and
ADR-013 (user overrides always take precedence). It answers the question:
"Was this assumption what the user intended, or what the platform assumed?"

Future phases may extend this to:

- `EXTERNAL_PROVIDER` — the value was sourced from an external data feed
- `INVESTOR_PROFILE_DEFAULT` — the value was drawn from the user's investor
  profile preferences (Phase 2+)

The `_source` column is defined as an ENUM-backed TEXT field. Adding new
source types is additive.

---

---

# Part 6 — Audit Log Persistence Structure

---

## 6.1 — The Calculation Audit Log

`audit_calculations` records every calculation attempt regardless of outcome.

```
id                  UUID primary key
user_id             FK to users
deal_id             FK to deals
snapshot_id         FK to snapshot_calculations (nullable — null for failures)
triggered_at        UTC timestamp
outcome             ENUM: SUCCESS, VALIDATION_FAILURE, ENGINE_ERROR
engine_version      TEXT (the engine version at time of attempt)
validation_errors   JSONB (nullable — structured list of {rule_code, field, message})
error_detail        TEXT (nullable — sanitised engine error description)
client_context      TEXT (nullable — e.g. "web", "api" — for future analytics)
created_at          UTC timestamp
```

---

## 6.2 — Audit Log Write Timing

```
Outcome             When written                Transaction
SUCCESS             Inside snapshot transaction  Same tx as snapshot
VALIDATION_FAILURE  After validation fails       Own transaction
ENGINE_ERROR        After engine error           Own transaction
```

For SUCCESS outcomes, the audit log entry and all snapshot sub-tables commit
atomically. For failure outcomes, the audit entry commits independently —
there is no snapshot to be atomic with.

---

## 6.3 — Audit Log Is Append-Only

The application database user has INSERT-only privilege on `audit_calculations`.
No UPDATE, no DELETE.

---

## 6.4 — Future Admin Audit Log (Phase 2+)

A separate `audit_config_changes` table will record configuration version
inserts (who created a new SDLT version, when, with what rationale). This
is distinct from the calculation audit log and is not required in Phase 1.

---

---

# Part 7 — Deal and Snapshot Relationship Design

---

## 7.1 — Deal as Mutable Workspace

A `deal` record is the mutable workspace. It holds the user's current working
inputs and a pointer to the latest snapshot. The deal record itself does not
contain calculation results — those live in snapshots.

The mutable fields of a deal are:
- Label (user-defined name)
- Status (DRAFT → ANALYSED → ARCHIVED — workflow state)
- Working input fields (the current state of inputs the user is editing)
- `latest_snapshot_id` (pointer updated on each new snapshot)
- `updated_at`

---

## 7.2 — Working Inputs in the Deal Record

The deal record stores the user's current working inputs as a flat set of
columns (not as JSONB). This is intentional: flat columns allow validation
at the database layer if needed, allow indexing on specific fields for future
search features, and make the deal input form state directly readable from
a single record without deserialisaton.

These working inputs are separate from the snapshot inputs. The snapshot
inputs are an immutable copy made at calculation time. The deal working inputs
may continue to change after a snapshot is created.

---

## 7.3 — latest_snapshot_id Pointer

`deals.latest_snapshot_id` is a nullable FK to `snapshot_calculations`. It is
null for DRAFT deals that have never been calculated.

This pointer is updated inside the snapshot creation transaction, atomically
with the snapshot write. It is the single permitted UPDATE on the `deals` table
during the snapshot creation flow.

If the pointer is ever inconsistent with the most recently created snapshot
(a bug scenario), the most recently created snapshot is authoritative. The
pointer is a performance convenience, not a source of truth.

---

## 7.4 — Scenario Classification (Phase 2+)

Phase 2 introduces named scenarios against a deal. The schema must accommodate
this without disrupting Phase 1 structure.

The approach is additive:

```
snapshot_calculations gains two nullable columns:
    scenario_label      TEXT (nullable — null for unclassified snapshots)
    scenario_type       ENUM (nullable — e.g. BASE_CASE, STRESS_CASE, REFINANCE)
```

In Phase 1 all snapshots have `scenario_label = null`. In Phase 2, users can
label snapshots as named scenarios. The immutability guarantees are unchanged
— labelling is a metadata addition, not a data mutation.

ADR-011 requires scenario analysis to produce immutable snapshots. The label
and type columns are set at INSERT time alongside other snapshot fields and
are never updated thereafter. They are included in the append-only constraint.

---

## 7.5 — Snapshot Comparison Persistence (Phase 2+)

Scenario comparison (comparing two snapshots side by side) does not require
a separate database table in most cases. Comparison can be performed by loading
two `snapshot_outputs` records and computing differences at the service layer.

However, if users need to save a named comparison (e.g. "personal vs Ltd Co
comparison saved on 2025-03-15"), a lightweight `snapshot_comparisons` table
is appropriate:

```
snapshot_comparisons (Phase 2+):
    id                  UUID primary key
    deal_id             FK to deals
    user_id             FK to users
    label               TEXT
    snapshot_a_id       FK to snapshot_calculations
    snapshot_b_id       FK to snapshot_calculations
    created_at          UTC timestamp
```

This table is read-only after creation. It does not store computed differences —
those are always derived at read time from the immutable snapshot records. This
preserves the guarantee that comparison outputs are always based on current
data, not cached differences that could become stale.

---

---

# Part 8 — Risk Flag Persistence Structure

---

## 8.1 — Flags as Rows, Not JSON

Risk flags are stored as individual rows in `snapshot_risk_flags`, not as a
JSONB array on the snapshot record. This design choice enables:

- Querying across deals by flag code (`SELECT ... WHERE flag_code = 'NEGATIVE_CASHFLOW'`)
- Counting flag frequency per user (portfolio risk overview, Phase 4)
- Filtering the flag list at the database layer rather than in application code
- Future analytics on flag distribution across the platform

A JSON approach would require application-side parsing for every query that
touches flags. Row-per-flag is marginally more verbose to write but
significantly more queryable.

---

## 8.2 — Message Stored With the Flag

The user-facing message is stored with the flag record, not derived at read
time from a static definition. This is an explicit choice:

If the message wording for `NEGATIVE_CASHFLOW` is updated in a future engine
version, snapshots generated before that update still show the message that
was displayed to the user at the time. This supports explainability (ADR-010):
a user reviewing a historical snapshot sees exactly what they were told.

The message is in addition to the `flag_code`. Future UI can always look up the
current message definition by code; the stored message is the historical record.

---

## 8.3 — triggered_by_value as TEXT

The `triggered_by_value` column stores the output value that caused the flag
as a text representation of the Decimal value (e.g. "132.86"). Storing as
text rather than a numeric type:

- Preserves the exact string that would be displayed to a user (avoids
  precision loss from numeric type coercion)
- Works for both numeric values (ICR percentage) and enum values (income_tax_band)
  without needing a variant type

---

---

# Part 9 — Validation Warning Persistence Structure

`snapshot_validation_warnings` mirrors the structure of `snapshot_risk_flags`
in design rationale. Warnings are also stored as rows, not as JSON.

The distinction between validation warnings and risk flags:

- Validation warnings (V-08, V-25, etc.) are raised by the validation pipeline
  before calculation, based on input values.
- Risk flags are raised after calculation, based on output values.

Both are stored in the snapshot family for the same reason: they are part of
what the user was told at the time of calculation and must be historically
retrievable.

---

---

# Part 10 — Schema Boundary Rules

These rules define where different concerns live in the schema. Violations
represent a design defect.

---

## Rule SB-01 — Engine Output Fields Live Only in Snapshot Tables

Calculated outputs (annual_cash_flow, gross_yield, icr_percent, etc.) must
not be stored in `deals`, `properties`, or any non-snapshot table. If a
calculated value is needed outside the snapshot context, it is read from the
snapshot record — not duplicated elsewhere.

Rationale: Duplicated calculated values create consistency problems. If the
engine is corrected and a new snapshot is created, the duplicated value in
the deal record would be stale.

---

## Rule SB-02 — Configuration Values Live Only in Config Tables

Tax rates, stress rates, void rate defaults, and other assumption defaults
must not be hardcoded in migration files, application constants, or seed data
outside the `config_*` tables. The config tables are the single source of
truth for these values.

---

## Rule SB-03 — Workflow State Lives Only in the Deal Record

Deal status, offer tracking, lender status, and other workflow state (Phase 2+)
live in the `deals` table or in future workflow extension tables. Workflow
state must not be mixed into snapshot tables.

---

## Rule SB-04 — AI Outputs Live in Separate Tables

AI-generated summaries and commentary (Phase 5+) live in `ai_*` tables and
reference snapshots by FK. They must not be stored as columns on snapshot
tables. AI outputs are advisory and ephemeral (DATA_BOUNDARIES.md); snapshot
records are authoritative and permanent. They must not coexist in the same
record.

---

## Rule SB-05 — External Intelligence Lives in Intel Tables

Area intelligence, EPC data, flood risk, Article 4 overlays, and other external
data (Phase 3+) live in `intel_*` tables. This data has its own freshness and
provenance metadata requirements (DATA_BOUNDARIES.md) that are incompatible
with the immutable snapshot schema. It must not be embedded in snapshot records.

The point of contact between intelligence data and snapshots is a reference
stored in `snapshot_inputs` (e.g. `area_intel_record_id` if an external
intelligence record influenced a user's assumption). This reference is recorded
at calculation time and is immutable thereafter.

---

## Rule SB-06 — Investor Profile Values Are Copied Into Snapshots

An investor profile is a convenience record. When a deal is calculated, the
relevant profile fields (ownership structure, income tax band) are copied into
`snapshot_inputs` as explicit values. The snapshot does not store an FK to
the investor profile — if the profile is later deleted or changed, the snapshot
remains self-contained.

This implements ADR-013 (user overrides always take precedence) at the
persistence layer: the snapshot stores what was actually used, not a reference
to something that might change.

---

---

# Part 11 — Transaction Boundaries

---

## 11.1 — Snapshot Creation Transaction

The snapshot creation transaction is the most important transaction boundary in
the application. It must be atomic.

```
BEGIN TRANSACTION

  INSERT INTO snapshot_calculations (...)     — root record
  INSERT INTO snapshot_inputs (...)           — all inputs + source flags
  INSERT INTO snapshot_outputs (...)          — all output metrics
  INSERT INTO snapshot_intermediates (...)    — all intermediate values
  INSERT INTO snapshot_risk_flags (...)       — one row per triggered flag
  INSERT INTO snapshot_validation_warnings (...) — one row per warning

  UPDATE deals
    SET latest_snapshot_id = :new_snapshot_id,
        updated_at = NOW()
    WHERE id = :deal_id

  INSERT INTO audit_calculations (...)        — SUCCESS audit entry

COMMIT
```

All seven write operations commit together or all roll back. A partial snapshot
must never exist in the database. If any write fails, the transaction rolls back
completely, and the audit log entry for the failure is written in a separate
transaction outside this boundary.

---

## 11.2 — Validation Failure Audit Transaction

When the engine returns a `ValidationResult` with `is_valid = false`:

```
BEGIN TRANSACTION
  INSERT INTO audit_calculations (outcome=VALIDATION_FAILURE, ...)
COMMIT
```

This is a single-record insert. No snapshot is created.

---

## 11.3 — Configuration Version Insert Transaction

When an admin inserts a new configuration version:

```
BEGIN TRANSACTION
  INSERT INTO config_[name]_versions (...)
  [IF SDLT: INSERT INTO config_sdlt_bands (...) for each band]
  INSERT INTO audit_config_changes (...) [Phase 2+]
COMMIT
```

SDLT version inserts are the only multi-row configuration transactions. All
band records for a new SDLT version must commit atomically with the version
record — a version record with no band records is invalid.

---

## 11.4 — Deal and Property Mutations

Deal and property updates are single-record operations and do not require
special transaction handling beyond the default single-statement transaction.

The exception is deal creation, which may involve creating both a property
record and a deal record in the same operation:

```
BEGIN TRANSACTION
  INSERT INTO properties (...)
  INSERT INTO deals (..., property_id = :new_property_id)
COMMIT
```

---

---

# Part 12 — Concurrency Expectations

---

## 12.1 — Snapshot Writes Are Append-Only and Non-Contending

The most frequent write operation — snapshot creation — is an INSERT-only
operation. INSERTs on different snapshot records never contend with each other.
PostgreSQL handles concurrent INSERTs without row-level locking conflicts.

The `deals` table UPDATE (updating `latest_snapshot_id`) is a single-row
update per deal. Two concurrent calculations on the same deal (which would
be an unusual client behaviour) would contend on this update. Last-write-wins
is acceptable here: whichever calculation commits last becomes the "latest"
snapshot. Both snapshots are preserved.

---

## 12.2 — Configuration Table Reads Are High-Frequency, Low-Contention

Configuration tables are read on every calculation. They are append-only, so
there are no UPDATE locks to contend with. Read operations are highly
concurrent and non-blocking.

---

## 12.3 — No Optimistic Locking Required in Phase 1

Optimistic locking (version columns for conflict detection) is not required
in Phase 1. The mutable tables (deals, properties, investor_profiles, users)
are user-owned and low-frequency. A user editing their own deal is the only
expected concurrent writer — multi-user collaborative editing is explicitly
out of scope in Phase 1 (ROADMAP.md Phase 2+).

---

## 12.4 — Future Concurrency Considerations

Phase 2 introduces team accounts (multiple users accessing the same deals).
This will require:

- Optimistic locking on deal working inputs to prevent concurrent overwrites
- `updated_at` column checks in UPDATE statements
- Conflict resolution strategy (last-write-wins vs. explicit conflict error)

This is designed for in Phase 2 when team access is scoped. Phase 1 schema
is compatible with this addition (all mutable tables already have `updated_at`).

---

---

# Part 13 — Indexing Strategy

---

## 13.1 — Indexing Principles

Indexes are created to support known query patterns, not speculatively. The
Phase 1 query patterns are simple and well-understood. The following indexes
are required from day one.

Primary key indexes are created automatically by PostgreSQL on all UUID
primary key columns.

---

## 13.2 — Required Phase 1 Indexes

**deals table**
```
INDEX ON deals (user_id)
  — primary query: "all deals for this user"

INDEX ON deals (property_id)
  — query: "all deals against this property"

INDEX ON deals (latest_snapshot_id)
  — query: FK join when loading deal with its latest snapshot
```

**snapshot_calculations table**
```
INDEX ON snapshot_calculations (deal_id)
  — primary query: "all snapshots for this deal" (history view)

INDEX ON snapshot_calculations (deal_id, is_superseded)
  — query: "current snapshot for this deal" (filtered)

INDEX ON snapshot_calculations (user_id)
  — query: "all calculations by this user" (audit and analytics)

INDEX ON snapshot_calculations (engine_version)
  — query: "all snapshots using engine version X" (version audit)
```

**snapshot_inputs table**
```
UNIQUE INDEX ON snapshot_inputs (snapshot_id)
  — enforces the one-to-one relationship
```

**snapshot_outputs table**
```
UNIQUE INDEX ON snapshot_outputs (snapshot_id)
  — enforces the one-to-one relationship
```

**snapshot_intermediates table**
```
UNIQUE INDEX ON snapshot_intermediates (snapshot_id)
  — enforces the one-to-one relationship
```

**snapshot_risk_flags table**
```
INDEX ON snapshot_risk_flags (snapshot_id)
  — primary query: "all flags for this snapshot"

INDEX ON snapshot_risk_flags (flag_code)
  — future query: "all deals with flag X" (Phase 4 analytics)
```

**snapshot_validation_warnings table**
```
INDEX ON snapshot_validation_warnings (snapshot_id)
  — primary query: "all warnings for this snapshot"
```

**config_sdlt_versions table**
```
INDEX ON config_sdlt_versions (effective_from DESC)
  — active config resolution query
```

**config_corporation_tax_versions table**
```
INDEX ON config_corporation_tax_versions (effective_from DESC)
  — active config resolution query
```

**config_assumption_versions table**
```
INDEX ON config_assumption_versions (effective_from DESC)
  — active config resolution query
```

**properties table**
```
INDEX ON properties (user_id)
  — primary query: "all properties for this user"

INDEX ON properties (postcode)
  — future: property lookup by postcode
```

---

## 13.3 — Phase 3+ Spatial Indexes

When `intel_property_locations` is introduced in Phase 3, a GiST spatial
index is required:

```
GIST INDEX ON intel_property_locations (location)
  — enables PostGIS spatial queries (ST_DWithin, ST_Intersects)
```

This index is not created in Phase 1. The PostGIS extension is enabled in Phase 1
(ADR-006) but spatial indexes are only created when spatial data is first
populated.

---

---

# Part 14 — Migration and Versioning Philosophy

---

## 14.1 — Migration Tool: Alembic

Alembic is the migration tool for this project. All schema changes are
expressed as versioned Alembic migration files. No manual DDL is applied
to any environment.

---

## 14.2 — Migration Principles

**One migration per schema change:** Each logically distinct schema change
has its own migration file. Combining unrelated changes into one migration
makes rollbacks difficult and history confusing.

**Migrations are irreversible for immutable tables:** Downgrade operations
for migrations that add immutable tables should be explicit no-ops with a
comment explaining why the downgrade is a no-op. Dropping a snapshot table
in a downgrade would destroy data — this must never happen automatically.

**Forward-only for production:** Production database migrations are applied
forward only. Rollback in production means applying a corrective migration,
not running a downgrade script.

**Staging mirrors production schema:** The staging environment always runs
the same migration version as production before any production deployment.

---

## 14.3 — Schema Evolution Strategy for Immutable Tables

Adding new columns to immutable tables (e.g. `snapshot_calculations` gaining
`scenario_label` in Phase 2) uses nullable columns with no default. Existing
records have null for the new column, which is the correct representation
(they predate the concept).

Adding new columns to `snapshot_inputs` for new input types follows the same
pattern: new columns are nullable, and existing snapshots have null for inputs
that did not exist when they were created.

This approach means schema evolution is additive and never breaks existing
snapshot immutability — old data remains as it was, new data populates new
columns.

---

## 14.4 — Configuration Data Migrations

Configuration data (initial SDLT bands, Corporation Tax rates, Assumption
defaults) is not seeded in migration files. It is inserted via a separate
seed script that runs after migrations in each environment. This separation
keeps migration files (schema) separate from data files (seed data).

The seed script for v1.0 configuration is version-controlled alongside the
migration files and is re-runnable (it checks for the existence of records
before inserting to prevent duplicates).

---

---

# Part 15 — Soft Delete vs Immutable Retention Decisions

---

## 15.1 — Snapshot Domain: No Deletion

Snapshot records are never deleted, not even as a "soft delete". There is no
`deleted_at` column on any snapshot table. Deletion of any kind is not
permitted.

If a user wants to "discard" a snapshot they consider incorrect, they create
a new one. The old snapshot is superseded but remains in the history.

---

## 15.2 — Configuration Domain: No Deletion

Configuration records are never deleted. A superseded SDLT rate table from
2020 remains in the database as long as any snapshot references it, which is
forever (snapshots are never deleted).

---

## 15.3 — Mutable Domain: Soft Archive, Not Hard Delete

Users, investor profiles, properties, and deals support a soft archive
pattern rather than hard deletion.

```
users:              status ENUM — ACTIVE, SUSPENDED, ARCHIVED
investor_profiles:  is_archived BOOLEAN, archived_at TIMESTAMP
properties:         is_archived BOOLEAN, archived_at TIMESTAMP
deals:              status ENUM — DRAFT, ANALYSED, ARCHIVED
```

Hard deletion is not permitted for these records because:
- Deals reference properties which reference users. Hard-deleting a user
  would cascade into orphaned deal records and snapshots.
- GDPR right-to-erasure requirements will be handled in Phase 2 via a
  deliberate data anonymisation process, not via cascade delete.

The GDPR approach (Phase 2) is to anonymise the user record (remove PII)
rather than cascade-delete snapshot data. The financial calculation history
(snapshot records) does not itself constitute PII and is not subject to
right-to-erasure under UK GDPR for legitimate business records.

---

---

# Part 16 — Historical Reproducibility Guarantees

---

## 16.1 — The Four Prerequisites

For any snapshot to be exactly reproducible, four things must be preserved
and accessible:

1. **Snapshot inputs** — every input value used, stored in `snapshot_inputs`
2. **Configuration versions** — the exact SDLT, CT, and Assumption records
   referenced by `snapshot_calculations` version FK columns
3. **Engine version** — the semantic version string in `snapshot_calculations.engine_version`
4. **Formula behaviour** — the code corresponding to the engine version

Items 1-3 are preserved in the database by this architecture. Item 4 is
preserved in source control — a tagged git commit corresponding to each
MAJOR engine version release.

---

## 16.2 — What "Reproducible" Means

Given a snapshot ID, the following must always be possible:

1. Load `snapshot_inputs` to reconstruct `EngineInput`
2. Load the three configuration version records to reconstruct `EngineConfig`
3. Pass `EngineInput` and `EngineConfig` to the engine at `engine_version`
4. Assert the result matches `snapshot_outputs` exactly

Step 3 requires access to the engine at the version specified. This is
maintained via tagged releases in git. The database alone cannot guarantee
formula behaviour — the git history must also be preserved.

---

## 16.3 — What Does Not Affect Reproducibility

The following changes do not affect the reproducibility of existing snapshots:

- Adding new configuration versions (existing snapshots reference old versions)
- Deploying a new engine MINOR or PATCH version (formula logic unchanged)
- Adding new columns to snapshot tables (existing records keep their values)
- Changing the assumption defaults (existing snapshots copied old defaults)
- Updating AI summaries (not part of the deterministic calculation)
- Updating deal labels or status (snapshot inputs are immutable copies)

---

## 16.4 — What Breaks Reproducibility (Must Not Happen)

- Updating any row in `snapshot_inputs` (this is prevented by DB privileges)
- Deleting a configuration version record referenced by a snapshot (prevented by FK constraints)
- Dropping a column from `snapshot_inputs` or `snapshot_outputs` (never done
  — columns may be deprecated but never dropped while referenced data exists)

---

---

# Part 17 — Mutable Workflow State vs Immutable Snapshots

---

## 17.1 — The Boundary Is Physical, Not Just Conceptual

The mutable/immutable distinction is enforced at the database privilege level,
not just documented. The application user's privileges enforce:

```
snapshot_* tables:  INSERT only
config_* tables:    INSERT only
audit_* tables:     INSERT only
deals:              INSERT, UPDATE (no DELETE)
properties:         INSERT, UPDATE (no DELETE)
users:              INSERT, UPDATE (no DELETE)
investor_profiles:  INSERT, UPDATE (no DELETE)
```

A bug that attempts `UPDATE snapshot_outputs SET annual_cash_flow_gbp = ...`
will fail at the database layer, not just produce incorrect application
behaviour.

---

## 17.2 — Workflow State Changes Do Not Touch Snapshots

USER_WORKFLOW_ARCHITECTURE.md defines a deal lifecycle from Lead to Exit.
Each workflow stage update (offer submitted, financing started, etc.) modifies
the `deals` record or future workflow extension tables. None of these
operations touch snapshot tables.

The workflow state and the calculation state are physically separated. A deal
can be in status ARCHIVED but its snapshots remain fully accessible. A deal
can move from OFFER_SUBMITTED back to UNDERWRITING (if the deal falls through)
without affecting any previously created snapshot.

---

## 17.3 — Snapshot Immutability Is Compatible With Workflow Evolution

ROADMAP.md (Phase 2) introduces workflow stage tracking, operational notes,
and lender tracking. These are stored in mutable workflow tables that
reference deals, not in snapshots. The snapshot schema is unaffected.

Future workflow tables follow the pattern:
```
deal_workflow_events (Phase 2+):
    id
    deal_id     FK to deals
    event_type  ENUM (OFFER_SUBMITTED, OFFER_ACCEPTED, ...)
    event_data  JSONB (flexible payload per event type)
    recorded_at
    created_at
```

This is an event log pattern (EVENT_ARCHITECTURE.md) — append-only, ordered,
and queryable. It does not interact with the snapshot schema.

---

---

# Part 18 — Persistence Implications of User Override Precedence

ADR-013 establishes a strict priority hierarchy:
1. User override
2. Snapshot-stored value
3. External verified provider
4. Platform default
5. AI-generated suggestion

The persistence implications:

**User overrides are recorded with the value AND the source flag.** Every
optional input in `snapshot_inputs` has a corresponding `_source` column.
A `USER_OVERRIDE` source on `void_rate_percent` means: "the user explicitly
chose this value". A `CONFIG_DEFAULT` source means: "this was the platform's
default at calculation time". The difference is auditable and user-visible.

**Platform defaults are never silently applied without recording.** If the
default void rate changes in a future configuration version, new calculations
pick up the new default. But the snapshot of an existing calculation still
shows the old default value and `CONFIG_DEFAULT` as the source — it does not
retroactively update to the new default.

**AI-suggested values must never appear as `USER_OVERRIDE` or `CONFIG_DEFAULT`**
in source columns. If a future phase allows AI to suggest assumption values,
the source enum must include an `AI_SUGGESTION` value, and the user must
explicitly confirm the value to promote it to `USER_OVERRIDE`. An AI-suggested
value that the user did not confirm must never be recorded as a user override.

**External intelligence values must use `EXTERNAL_PROVIDER` source** when that
capability is introduced in Phase 3. The persistence schema is extended
additive-ly with new enum values — no existing data is changed.

---

---

# Part 19 — Persistence Implications of Assumption Provenance

ADR-009 requires that every non-user-provided assumption be traceable to a
source, version, effective date, and verification timestamp.

In Phase 1, the `_source` column on each `snapshot_inputs` field and the
`assumption_config_version_id` FK on the snapshot root record together provide
this provenance.

In future phases, the assumption configuration table will be extended with:

```
config_assumption_versions additional fields (Phase 2+):
    source_provider_name    TEXT (e.g. "ARLA Propertymark 2024 Survey")
    source_url              TEXT (URL to source document or dataset)
    collection_date         DATE
    last_verified_date      DATE
    confidence_level        ENUM (HIGH, MEDIUM, LOW, UNVERIFIED)
```

This extension is additive. Existing configuration version records will have
null values for these new columns (they predate the provenance tracking feature).
New configuration version inserts will populate these fields.

The persistence design anticipates this without requiring it in Phase 1. The
assumption config table already stores `source_attribution` as a text field —
this is the Phase 1 approximation of the full provenance schema that Phase 2+
will formalise.

---

---

# Part 20 — Persistence Implications of Explainability Metadata

ADR-010 requires that every user-facing calculation eventually be explainable
through a breakdown of formulas, assumptions, inputs, configuration versions,
and triggered risk conditions.

The persistence design directly supports this:

**`snapshot_intermediates`** stores every step of the calculation pipeline,
not just final outputs. This is the raw material for a future "show me how
this was calculated" feature. The intermediate values do not need to be
recomputed — they are stored at calculation time.

**`snapshot_risk_flags.message`** stores the exact message the user was shown,
not just the code. A future "why did this flag trigger?" feature can display
the original message alongside the `triggered_by_value` to explain the trigger.

**`snapshot_inputs._source` columns** enable "which assumptions were platform
defaults vs your choices?" — a key explainability question.

**Configuration version FKs on the snapshot root** enable "which SDLT rules
were in effect when this was calculated?" and "was this calculated under the
old or new Corporation Tax rate?"

All of these explainability components are persistent from Phase 1. The
explainability UI layer is a Phase 2-3 concern, but the data it needs is
captured from day one.

---

---

# Part 21 — Persistence Implications of Future Regulatory and Spatial Intelligence

ADR-008 and ADR-012 establish that regulatory intelligence (Article 4, HMO
licensing, flood risk, EPC restrictions) and spatial intelligence belong outside
the deterministic underwriting engine. DATA_BOUNDARIES.md classifies this data
as "regulatory intelligence — no, mutable, refreshable, informational."

The persistence implications in Phase 1:

**No regulatory intelligence tables are created in Phase 1.** The `postcode`
field on `properties` and the PostGIS extension are the only concessions to
future spatial capability.

**The schema must accommodate intelligence references without disruption.**
Future intelligence data will be stored in `intel_*` tables (Part 1.4). When
a user's deal input was influenced by an intelligence record (e.g. an area
intelligence record suggested a rental estimate), the `snapshot_inputs` table
will reference that record by ID.

The Phase 1 `snapshot_inputs` schema includes nullable placeholder columns
for these future references:

```
snapshot_inputs future columns (Phase 3+, all nullable):
    area_intel_record_id    FK to intel_area_records (nullable)
    epc_record_id           FK to intel_epc_records (nullable)
    flood_risk_record_id    FK to intel_flood_risk_records (nullable)
```

These columns are added in Phase 3 migrations, not in Phase 1. They are noted
here so the Phase 1 design does not inadvertently foreclose them.

**Freshness metadata lives with the intelligence record, not the snapshot.**
If the flood risk data used to inform a decision was collected in 2023, that
staleness is recorded on the `intel_flood_risk_records` record (with
`collection_date`, `last_verified_date`, and `is_stale` flag). The snapshot
records the FK to that intelligence record at the time of calculation. Future
queries can always determine "was this intelligence fresh when the snapshot
was created?" by joining on the FK.

---

---

# Part 22 — Persistence Implications of API Versioning and Export Reproducibility

API_VERSIONING.md establishes that API contracts are long-lived and that
historical underwriting snapshots must remain reproducible even across API
version changes.

The persistence implications:

**Snapshot field names are stable.** The output fields in `snapshot_outputs`
match `EngineOutputs` field names from ENGINE_CONTRACTS.md exactly. These
field names also appear in API responses. If a field is renamed in a future
API version (e.g. a v2 API), the database column name does not change — the
v2 API maps from the stable database column name to the new API field name
in the response serialiser. The database schema is the stable layer beneath
the evolving API.

**Exports are generated from snapshots, not re-derived.** PDF and CSV exports
(future Phase, ROADMAP.md) read directly from immutable snapshot records.
An export generated today and the same export regenerated next year from the
same snapshot will be identical (assuming no export template changes). The
data is stable because the snapshot is immutable.

**API version is not stored in the snapshot.** The API version used to retrieve
a snapshot is not a property of the snapshot itself. The snapshot is a
calculation record, not an API response record. This separation ensures that
adding a new API version does not require re-creating or migrating snapshots.

---

---

# Part 23 — Phase 1 Persistence Boundaries (What Is Not Built Yet)

The following persistence concerns are explicitly out of scope for Phase 1
but designed for in this document.

| Concern | Phase | Notes |
|---------|-------|-------|
| Scenario labels on snapshots | 2 | Nullable columns, additive migration |
| Snapshot comparison records | 2 | New table, references existing snapshots |
| Workflow event log | 2 | Append-only event table on deals |
| Admin audit log for config changes | 2 | Separate audit table |
| Investor profile preferences/strategy | 2 | Extension columns on investor_profiles |
| GDPR anonymisation process | 2 | User record anonymisation, not cascade delete |
| Optimistic locking on deals | 2 | `updated_at` check on deal UPDATE |
| Area intelligence tables | 3 | New intel_* table namespace |
| Property location geometry | 3 | Intel_property_locations with PostGIS column |
| Assumption provenance fields | 3 | Extended config_assumption_versions columns |
| Snapshot → intelligence FK columns | 3 | Nullable FK additions to snapshot_inputs |
| Portfolio analytics tables | 4 | Aggregate views or separate tables |
| AI summary records | 5 | New ai_* table namespace |
| Full assumption provenance API | 5 | Builds on Phase 3 provenance schema |

None of these require changes to the Phase 1 core snapshot schema. They are
additive extensions to a foundation that is designed to accommodate them.

---

---

# Part 24 — Persistence Architecture Invariants

The following are architectural invariants. They may not be changed without
a documented entry in DECISIONS.md.

1. **The application database user has no UPDATE or DELETE on snapshot tables.**
   Database-level privilege enforcement, not just application convention.

2. **The application database user has no UPDATE or DELETE on configuration tables.**
   Same enforcement.

3. **Snapshot creation is atomic.** All six sub-table inserts plus the deal
   pointer update and audit log entry commit together or not at all.

4. **Configuration records reference effective dates, not overwrites.**
   No configuration column is ever updated. New values produce new records.

5. **Snapshot inputs store both value and source.** Every optional input
   has a paired `_source` column. This is never nullable or omitted.

6. **Risk flags and validation warnings are rows, not JSON.**
   These must remain queryable across snapshots.

7. **AI outputs are never stored in snapshot tables.** They live in separate
   tables and reference snapshots by FK. The FK direction is always
   AI → snapshot, never snapshot → AI.

8. **Calculated output values are never stored outside snapshot tables.**
   Deal records store working inputs only, not output metrics.

9. **UUID primary keys throughout.** No auto-increment integers on any table.

10. **All timestamps are UTC.** No local time stored anywhere in the database.
