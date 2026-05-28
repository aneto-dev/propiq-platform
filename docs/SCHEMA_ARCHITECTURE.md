# PropIQ Platform — Conceptual Schema Architecture

## Purpose

This document defines the conceptual schema architecture for the PropIQ
platform. It describes domain entities, their responsibilities, relationships,
mutability boundaries, versioning strategy, and future extensibility
considerations.

This document is not an implementation specification. It contains no SQL, no
ORM definitions, and no migration instructions. It is the conceptual design
that SQL schema and ORM models will be derived from.

All terminology matches DOMAIN_GLOSSARY.md. All architectural constraints
reflect ARCHITECTURE.md, DECISIONS.md, and CALCULATION_SPEC.md.

---

## Governing Constraints

The following constraints from the project reference documents govern every
design decision in this schema.

**Immutability (ADR-002):** Saved calculations are immutable snapshots.
Nothing that has been calculated and saved may be altered. Recalculation
creates a new record; it never modifies an existing one.

**Versioned configuration (ADR-005):** Tax rates, SDLT bands, stress test
assumptions, and operational defaults are stored in append-only configuration
tables. Configuration records are never updated or deleted. Every calculation
snapshot references the exact configuration version used.

**Historical reproducibility (CALCULATION_SPEC.md):** Given a snapshot ID,
it must be possible to exactly reproduce the calculation that produced it
using only the data stored in that snapshot and its referenced configuration
versions.

**Determinism (ARCHITECTURE.md):** The same inputs plus the same configuration
version must always produce the same outputs.

**Separation of concerns (ARCHITECTURE.md):** Domain logic, persistence, API,
and presentation are separate. The schema reflects domain boundaries, not
API convenience.

**PostGIS early (ADR-006):** The database must support spatial data from the
start to avoid future migrations.

---

---

# Part 1 — Domain Entity Map

There are six domain groups. Each group owns a clearly bounded set of
responsibilities. Cross-group relationships are explicit foreign key references,
never implicit joins or denormalised copies.

```
┌─────────────────────────────────────────────────────────────────┐
│  GROUP 1: IDENTITY                                              │
│  Users · Investor Profiles                                      │
└──────────────────────┬──────────────────────────────────────────┘
                       │ owns
┌──────────────────────▼──────────────────────────────────────────┐
│  GROUP 2: DEALS                                                 │
│  Properties · Deals                                             │
└──────────────────────┬──────────────────────────────────────────┘
                       │ triggers
┌──────────────────────▼──────────────────────────────────────────┐
│  GROUP 3: SNAPSHOTS                                             │
│  Calculation Snapshots · Snapshot Inputs · Snapshot Outputs     │
│  Snapshot Intermediates · Snapshot Risk Flags                   │
└──────────────────────┬──────────────────────────────────────────┘
                       │ references
┌──────────────────────▼──────────────────────────────────────────┐
│  GROUP 4: VERSIONED CONFIGURATION                               │
│  Engine Versions · SDLT Config · Corporation Tax Config         │
│  Assumption Config                                              │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  GROUP 5: SPATIAL (Phase 3+)                                    │
│  Property Locations · Area Intelligence Records                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│  GROUP 6: AUDIT                                                 │
│  Calculation Audit Log                                          │
└─────────────────────────────────────────────────────────────────┘
```

---

---

# Part 2 — Entity Definitions

---

## GROUP 1 — Identity

---

### Entity: User

**Responsibility:**
Represents an authenticated platform user. Mirrors the identity record managed
by Supabase Auth. The platform's own user record is a thin extension of the
auth identity, not a replacement for it.

**Mutability: MUTABLE**
User profile information (display name, preferences, contact details) may
change over time. This is the only major mutable entity in the core domain.
Changes are not historically significant — the platform does not need to know
what a user's email was at the time of a calculation.

**Key attributes:**
- Unique identifier (mirrors Supabase Auth user ID — this is the join key)
- Display name
- Email (synced from auth provider, not authoritative here)
- Account status (active, suspended)
- Account created timestamp
- Default investor profile reference (optional — which profile to pre-populate
  on new deals)

**Relationships:**
- Has many Investor Profiles
- Has many Deals
- Has many Calculation Snapshots (via Deals)

**Notes:**
The User entity does not store passwords or authentication tokens. All
authentication is delegated to Supabase Auth. The platform's user record is
created on first successful login and linked by the Supabase Auth user UUID.

---

### Entity: Investor Profile

**Responsibility:**
Represents a named set of investor-level tax and ownership assumptions that
the user applies to deals. A user may have more than one profile — for example,
one for personal ownership and one for a limited company. Profiles are
reusable across deals.

**Mutability: MUTABLE WITH VERSIONING CONSIDERATION**
Profiles are mutable in that a user can update them. However, a snapshot does
not reference the investor profile directly — it stores a copy of the relevant
profile fields at the time of calculation. This means a profile update does not
silently alter historical snapshots.

**Key attributes:**
- Unique identifier
- User reference (owner)
- Profile label (user-defined name, e.g. "Personal" or "PropCo Ltd")
- Ownership structure (INDIVIDUAL / LIMITED_COMPANY)
- Income tax band (BASIC_RATE / HIGHER_RATE / ADDITIONAL_RATE) — for
  INDIVIDUAL only
- Is additional dwelling default (Boolean — can be overridden per deal)
- Created at timestamp
- Updated at timestamp

**Relationships:**
- Belongs to User
- Referenced by Deals (as a convenience default — not stored in snapshots
  by reference, only by copied values)

**Notes:**
The investor profile is a deal setup convenience, not an authoritative input
to calculations. When a deal is calculated, the relevant profile values are
copied into the snapshot inputs. The snapshot never references the investor
profile by ID — if the profile is later deleted or changed, the snapshot
remains self-contained.

---

## GROUP 2 — Deals

---

### Entity: Property

**Responsibility:**
Represents a specific real-world property that is the subject of a deal
analysis. A property record holds the stable identifying and descriptive
attributes of the physical asset, separate from any financial analysis of it.

**Mutability: MOSTLY MUTABLE**
Property details (address, type, tenure) are mutable. A user may refine their
understanding of a property. However, no calculation output depends on the
current state of the Property record — calculations depend on the snapshot
inputs, which are immutable. Changes to a Property record do not affect
historical snapshots.

**Key attributes:**
- Unique identifier
- User reference (owner)
- Address line 1
- Address line 2 (optional)
- City / town
- Postcode (validated UK format)
- Property type (RESIDENTIAL_SINGLE_LET — v1.0 only)
- Tenure (FREEHOLD / LEASEHOLD)
- Lease years remaining (optional — for leasehold)
- Number of bedrooms (optional)
- EPC rating (optional — for future Phase 3 intelligence)
- Created at timestamp
- Updated at timestamp

**Spatial attribute (PostGIS — see Part 6):**
- Location point (GEOMETRY POINT, SRID 4326)

**Relationships:**
- Belongs to User
- Has many Deals

**Notes:**
The property record exists to allow a user to have multiple deal analyses
against the same physical property (e.g. comparing a 25% deposit scenario
against a 40% deposit scenario, or modelling personal vs Ltd Co ownership).
It is also the anchor point for future area intelligence data (Phase 3).

---

### Entity: Deal

**Responsibility:**
Represents a user's active analysis of a property under a specific set of
financial assumptions. A Deal is the mutable workspace for a property analysis.
It holds the user's current working inputs and points to the latest calculated
snapshot.

**Mutability: MUTABLE**
A deal's inputs may be changed at any time. Changing inputs and recalculating
creates a new snapshot — it does not alter existing snapshots. The deal record
itself is mutable (it records what the user is currently working on) but it
is not the source of truth for any calculation. Snapshots are.

**Key attributes:**
- Unique identifier
- User reference (owner)
- Property reference
- Deal label (user-defined name, e.g. "25% deposit scenario")
- Status (DRAFT / ANALYSED / ARCHIVED)
- Latest snapshot reference (nullable — null until first calculation)
- Created at timestamp
- Updated at timestamp

**Relationships:**
- Belongs to User
- Belongs to Property
- Has many Calculation Snapshots
- References latest Calculation Snapshot (denormalised convenience pointer)

**Notes:**
The Deal entity is intentionally thin. It is a named container that groups
snapshots together and gives the user a workspace. All financially significant
data lives in Calculation Snapshots, not in the Deal record.

The `latest_snapshot_id` denormalisation is a read convenience. It must always
be updated atomically when a new snapshot is persisted. If there is ever a
discrepancy between `latest_snapshot_id` and the most recently created snapshot
for the deal, the most recently created snapshot is authoritative.

---

## GROUP 3 — Snapshots

The snapshot group is the most important group in the schema. It implements
ADR-002 (immutable snapshots) and the historical reproducibility requirement
from CALCULATION_SPEC.md.

All entities in this group are **strictly immutable** after creation. No
update or delete operations are permitted at any layer.

---

### Entity: Calculation Snapshot

**Responsibility:**
The root record of a single complete underwriting analysis. It is the
container that ties together inputs, outputs, intermediate values, risk flags,
and version references for one calculation event.

**Mutability: STRICTLY IMMUTABLE**

**Key attributes:**
- Unique identifier (UUID)
- Deal reference
- User reference (denormalised for audit — the user who triggered this
  calculation)
- Engine version string (semantic version of the underwriting engine, e.g.
  "1.0.0")
- Assumption config version reference (FK to Assumption Config)
- SDLT config version reference (FK to SDLT Config)
- Corporation tax config version reference (FK to Corporation Tax Config)
- Calculation triggered at (UTC timestamp)
- Is superseded (Boolean — true when a newer snapshot exists for the same
  deal; set by the persistence layer when a new snapshot is created, this is
  the only permitted mutation on a snapshot record and is discussed further
  below)
- Superseded at (nullable UTC timestamp)
- Calculation duration milliseconds (operational diagnostic)

**Relationships:**
- Belongs to Deal
- Has one Snapshot Inputs record
- Has one Snapshot Outputs record
- Has one Snapshot Intermediates record
- Has many Snapshot Risk Flags
- References Assumption Config version
- References SDLT Config version
- References Corporation Tax Config version

**Note on `is_superseded`:**
Strict immutability means no calculation data may ever be altered. However,
the platform needs to distinguish the current snapshot from historical ones
without querying by recency each time. The `is_superseded` flag is the single
permitted exception: when a new snapshot is created for a deal, the previous
snapshot's `is_superseded` is set to true. This is a status transition, not a
data mutation. The calculation data itself remains unchanged. This approach
is preferable to ordering by timestamp because it is explicit and queryable
without sorting.

---

### Entity: Snapshot Inputs

**Responsibility:**
Stores every input value — user-provided and default — used in a calculation.
This is the complete input record for the snapshot. No input used in the
calculation may be absent from this record.

**Mutability: STRICTLY IMMUTABLE**

**Key attributes — user-provided inputs:**
- Snapshot reference
- Purchase price
- Monthly rent
- Deposit amount
- Mortgage interest rate
- Mortgage term years
- Mortgage type (INTEREST_ONLY / REPAYMENT)
- Ownership structure (INDIVIDUAL / LIMITED_COMPANY)
- Income tax band (nullable — INDIVIDUAL only)
- Is additional dwelling
- Property type
- Tenure
- Lease years remaining (nullable)
- Property country

**Key attributes — optional inputs (user-provided or defaulted):**
For each optional input, two values are stored: the value actually used in the
calculation, and the source of that value (USER_OVERRIDE or CONFIG_DEFAULT).

- Void rate percent (value used)
- Void rate source (USER_OVERRIDE / CONFIG_DEFAULT)
- Letting agent fee percent (value used)
- Letting agent fee source
- Maintenance reserve percent (value used)
- Maintenance reserve source
- Landlord insurance annual (value used)
- Landlord insurance source
- Purchase legal costs (value used)
- Purchase legal costs source
- Refurbishment cost (value used)
- Refurbishment cost source
- Annual service charge (value used)
- Annual service charge source
- Annual ground rent (value used)
- Annual ground rent source
- Annual accountancy cost (value used)
- Annual accountancy cost source

**Relationships:**
- Belongs to Calculation Snapshot (one-to-one)

**Notes:**
Storing both the value used and whether it came from a user override or a
config default serves two purposes. First, it makes the audit trail complete:
an auditor can see not just what assumptions were used but whether the user
customised them. Second, it enables the UI to present a clear diff between
user-customised and default assumptions on a snapshot comparison view.

---

### Entity: Snapshot Outputs

**Responsibility:**
Stores every user-facing output metric produced by the calculation. These are
the values displayed on the deal summary page.

**Mutability: STRICTLY IMMUTABLE**

**Key attributes:**
- Snapshot reference
- gross_annual_rent_gbp
- effective_annual_rent_gbp
- total_operating_costs_annual_gbp
- net_operating_income_gbp
- annual_mortgage_cost_gbp
- annual_tax_liability_gbp
- annual_cash_flow_gbp
- monthly_cash_flow_gbp
- gross_yield_percent
- net_yield_percent
- roce_percent
- cash_on_cash_return_percent
- ltv_percent
- icr_percent
- total_sdlt_gbp
- total_acquisition_cost_gbp
- total_cash_deployed_gbp

**Relationships:**
- Belongs to Calculation Snapshot (one-to-one)

**Notes:**
Field names match api_field names defined in DOMAIN_GLOSSARY.md exactly.
This is intentional — the output record maps directly to the glossary, which
maps directly to the API response schema.

---

### Entity: Snapshot Intermediates

**Responsibility:**
Stores every intermediate calculated value produced during the calculation
pipeline. These values are not primary user-facing outputs but are required
for full reproducibility, auditability, and future debugging.

**Mutability: STRICTLY IMMUTABLE**

**Key attributes:**
- Snapshot reference
- void_rate_decimal_applied
- gross_annual_rent_gbp (repeated from outputs for self-containment)
- effective_annual_rent_gbp
- letting_agent_annual_gbp (including VAT uplift)
- letting_agent_vat_rate_applied (the VAT rate used — configurable in future)
- annual_maintenance_reserve_gbp
- loan_amount_gbp
- monthly_mortgage_payment_gbp
- annual_mortgage_interest_gbp (interest component only — for tax)
- taxable_income_or_profit_gbp (rental income for INDIVIDUAL; company profit
  for LIMITED_COMPANY)
- income_tax_gross_gbp (before mortgage interest tax credit — INDIVIDUAL only)
- mortgage_interest_tax_credit_gbp (INDIVIDUAL only)
- corporation_tax_gross_gbp (LIMITED_COMPANY only)
- stressed_annual_interest_gbp
- stress_test_rate_applied_percent
- sdlt_band_breakdown (structured JSON — each band: lower, upper, rate,
  taxable amount, tax computed)
- sdlt_base_gbp
- sdlt_surcharge_gbp
- sdlt_surcharge_rate_applied_percent
- section_24_applies (Boolean — derived from ownership and tax band)

**Relationships:**
- Belongs to Calculation Snapshot (one-to-one)

**Notes on sdlt_band_breakdown:**
The SDLT band breakdown is stored as structured JSON rather than as child rows.
This is a deliberate choice for v1.0. The band structure is a fixed-length
ordered list at calculation time — it is not a variable-length relational
entity that needs to be queried independently. Storing it as JSON within the
intermediates record keeps the SDLT calculation auditable without adding a
separate table. If future requirements demand querying across SDLT band data
(e.g. analytics on how much SDLT users are paying at each band), a separate
normalised structure would be preferable. This is noted as a future
extensibility consideration.

---

### Entity: Snapshot Risk Flags

**Responsibility:**
Stores every risk flag generated for a calculation. Each flag is a separate
row, not a JSON blob. This allows querying, counting, and filtering flags
across snapshots without parsing unstructured data.

**Mutability: STRICTLY IMMUTABLE**

**Key attributes (one row per flag):**
- Unique identifier
- Snapshot reference
- Flag code (e.g. NEGATIVE_CASHFLOW, LOW_ICR, SECTION_24_IMPACT)
- Severity (HIGH / MEDIUM / INFO)
- Triggered by field (the output or intermediate value that caused the flag,
  for traceability)
- Triggered by value (the actual value at trigger time, stored as a string
  representation for auditability)
- User-facing message (the message shown to the user at the time of
  calculation — stored so it is auditable even if the message wording changes
  in future engine versions)

**Relationships:**
- Belongs to Calculation Snapshot
- One snapshot has zero or many risk flags

**Notes:**
Storing flags as individual rows rather than a JSON array enables:
- Querying deals by flag code (e.g. "show me all deals with NEGATIVE_CASHFLOW")
- Counting flag frequency across a user's portfolio (Phase 4)
- Future analytics on risk flag distributions across the platform

The user-facing message is stored with the flag rather than derived at read
time. This ensures that if the message wording is updated in a future engine
version, the original snapshot still shows what the user was told at the time.

---

## GROUP 4 — Versioned Configuration

All entities in this group are **strictly append-only**. Records are inserted
but never updated or deleted. Each table uses an `effective_from` date to
determine which record was active at any point in time.

The engine always selects the configuration record where `effective_from` is
the most recent date on or before the calculation date. This ensures that a
snapshot can always be reproduced by re-running with the same date.

---

### Entity: Engine Version Registry

**Responsibility:**
Records every deployed version of the underwriting engine. Provides a
reference point for understanding what calculation logic was in use at any
point in time.

**Mutability: APPEND-ONLY**

**Key attributes:**
- Version string (semantic version, e.g. "1.0.0") — primary key
- Released at timestamp
- Change summary (human-readable description of what changed)
- Is breaking change (Boolean — true for MAJOR version increments)
- Specification reference (link or note referencing the CALCULATION_SPEC
  version or commit this engine version implements)

**Notes:**
This is a registry, not a runtime entity. It is populated when a new engine
version is deployed. Snapshots reference this by version string, not by a
surrogate key, so the version is human-readable in the snapshot record.

---

### Entity: SDLT Configuration

**Responsibility:**
Stores versioned SDLT rate bands and surcharge rates for England. One
configuration version = one complete set of SDLT rules applicable from a
given date.

**Mutability: APPEND-ONLY**

**Key attributes (per configuration version):**
- Unique identifier
- Effective from date
- Country (ENGLAND — for future LBTT/LTT expansion)
- Additional dwelling surcharge rate (percent)
- Notes (e.g. "Post-April 2025 threshold reversion")
- Created at timestamp
- Created by (admin user reference)
- Source attribution (e.g. "HMRC SDLT guidance, Finance Act 2024")

**Associated entity: SDLT Rate Bands**
Each SDLT configuration version has a child set of rate band records:
- Configuration version reference
- Band order (integer — for display ordering)
- Band lower threshold (GBP)
- Band upper threshold (GBP, nullable for the top band)
- Standard rate percent
- Notes (optional)

**Relationships:**
- One SDLT configuration version has many SDLT rate band records
- Referenced by Calculation Snapshot

**Notes:**
The rate bands are stored as child records rather than embedded JSON because
they are the subject of meaningful independent queries: "what was the rate on
amount X under configuration version Y" is a calculation-critical query, not
just a display query.

---

### Entity: Corporation Tax Configuration

**Responsibility:**
Stores versioned corporation tax rates and thresholds applicable to UK
limited companies.

**Mutability: APPEND-ONLY**

**Key attributes (per configuration version):**
- Unique identifier
- Effective from date
- Small profits rate percent (applicable below lower threshold)
- Small profits upper threshold (GBP)
- Main rate percent (applicable above upper threshold)
- Main rate lower threshold (GBP)
- Marginal relief fraction numerator (for the marginal relief formula)
- Marginal relief fraction denominator
- Notes
- Created at timestamp
- Source attribution (e.g. "Finance Act 2023")

**Relationships:**
- Referenced by Calculation Snapshot

**Notes:**
The marginal relief fraction (currently 3/200) is stored explicitly rather
than derived. If this fraction changes in a future Finance Act, the existing
configuration version remains correct and a new version is inserted. Snapshots
referencing the old version will continue to reproduce correctly.

---

### Entity: Assumption Configuration

**Responsibility:**
Stores the versioned set of operational assumption defaults: void rates,
letting agent fees, maintenance reserves, insurance estimates, purchase cost
estimates, accountancy cost estimates, stress test rate, and ICR thresholds.

These are the defaults applied when a user does not override an optional input.

**Mutability: APPEND-ONLY**

**Key attributes (per configuration version):**
- Unique identifier
- Effective from date
- void_rate_percent_default
- letting_agent_fee_percent_default
- maintenance_reserve_percent_default
- landlord_insurance_annual_default_gbp
- purchase_legal_costs_default_gbp
- accountancy_cost_individual_default_gbp
- accountancy_cost_ltd_default_gbp
- stress_test_rate_percent
- icr_threshold_basic_rate_percent
- icr_threshold_higher_rate_percent
- letting_agent_vat_rate_percent (currently 20% — stored explicitly in case
  VAT rate changes)
- Notes
- Created at timestamp
- Source attribution

**Relationships:**
- Referenced by Calculation Snapshot

**Notes:**
All assumption defaults for a given calculation are captured in a single
configuration version record. This means a snapshot holds one foreign key to
this table rather than many. If only one default changes (e.g. the void rate
default is updated following new ARLA data), a new configuration version is
inserted with all values — the unchanged ones are copied forward. This is
intentionally simple and auditable. It trades some data duplication for
clarity.

---

## GROUP 5 — Spatial (Phase 3+)

These entities are scoped to Phase 3 and beyond. They are defined here
conceptually to ensure the Phase 1 schema does not preclude them. No
implementation is required in Phase 1 beyond enabling PostGIS on the database.

---

### Entity: Property Location (extension of Property)

**Responsibility:**
Holds the precise geospatial coordinates of a property, enabling spatial
queries in Phase 3.

**Mutability: MUTABLE**

**Key attributes:**
- Property reference
- Location (PostGIS GEOMETRY POINT, SRID 4326 — WGS84 longitude/latitude)
- Geocoded at timestamp
- Geocode source (e.g. OS Places API, user-entered)
- Geocode confidence (optional — for future quality scoring)

**Notes:**
The location geometry is kept separate from the core Property entity. This
separation allows the geocoding concern (which involves external APIs and may
be asynchronous) to be managed independently from the property record itself.
In Phase 3, spatial queries will join Property to Property Location by property
ID.

---

### Entity: Area Intelligence Record (Phase 3)

**Responsibility:**
Stores enrichment data about the area surrounding a property: crime indices,
flood risk bands, EPC data, school proximity scores, deprivation indices.

These records are sourced from external datasets (ONS, Environment Agency,
Ofsted, Land Registry). They are reference data attached to a geographic area,
not to a specific property.

**Mutability: APPEND-ONLY (per data source and effective date)**

**Key attributes:**
- Unique identifier
- Geographic area reference (postcode sector, LSOA, or geometry polygon —
  depending on data source)
- Data source identifier (e.g. ONS_CRIME_2024, EA_FLOOD_RISK_2024)
- Data type (CRIME / FLOOD_RISK / EPC / SCHOOL_PROXIMITY / DEPRIVATION)
- Effective from date
- Data payload (JSON — structure varies by data type)
- Imported at timestamp

**Notes:**
Area intelligence data is not underwriting data. It is enrichment data that
supports investor judgement but does not feed into deterministic calculations.
It must remain clearly separated from the underwriting engine domain.

---

## GROUP 6 — Audit

---

### Entity: Calculation Audit Log

**Responsibility:**
Records every calculation event: who triggered it, when, what snapshot was
produced, and whether it succeeded or failed. Supplements the snapshot itself
with operational context.

**Mutability: APPEND-ONLY**

**Key attributes:**
- Unique identifier
- User reference
- Deal reference
- Snapshot reference (nullable — null if the calculation failed before a
  snapshot was persisted)
- Triggered at timestamp
- Outcome (SUCCESS / VALIDATION_FAILURE / ENGINE_ERROR)
- Validation errors JSON (if VALIDATION_FAILURE — structured list of
  validation rule codes and messages)
- Error detail (if ENGINE_ERROR — sanitised error description, no stack traces)
- Engine version at time of attempt
- Client context (optional — e.g. web, mobile, API — for future analytics)

**Relationships:**
- References User
- References Deal
- References Calculation Snapshot (nullable)

**Notes:**
This entity records attempts, including failures. A validation failure does
not produce a snapshot, but the attempt is still recorded. This is useful
for understanding user behaviour, identifying common validation errors, and
auditing any claims about calculation history.

---

---

# Part 3 — Entity Relationships Summary

```
User ──────────────────────┬── has many ──► Investor Profiles
                           ├── has many ──► Deals
                           └── has many ──► Calculation Audit Log entries

Property ──────────────────┬── belongs to ──► User
                           └── has many ──► Deals

Deal ───────────────────────┬── belongs to ──► User
                            ├── belongs to ──► Property
                            ├── has many ──► Calculation Snapshots
                            └── references one ──► latest Calculation Snapshot

Calculation Snapshot ───────┬── belongs to ──► Deal
                            ├── has one ──► Snapshot Inputs
                            ├── has one ──► Snapshot Outputs
                            ├── has one ──► Snapshot Intermediates
                            ├── has many ──► Snapshot Risk Flags
                            ├── references ──► Assumption Config version
                            ├── references ──► SDLT Config version
                            └── references ──► Corporation Tax Config version

SDLT Config ───────────────── has many ──► SDLT Rate Bands

Calculation Audit Log ──────┬── references ──► User
                            ├── references ──► Deal
                            └── references (nullable) ──► Calculation Snapshot
```

---

---

# Part 4 — Immutable vs Mutable Boundary

This is one of the most important design decisions in the schema. The boundary
is intentional and must be enforced at both the application layer and the
database layer.

```
MUTABLE ENTITIES                   IMMUTABLE / APPEND-ONLY ENTITIES
────────────────────────────────   ──────────────────────────────────────────
User                               Calculation Snapshot
Investor Profile                   Snapshot Inputs
Property                           Snapshot Outputs
Deal                               Snapshot Intermediates
  (Deal.latest_snapshot_id         Snapshot Risk Flags
   is the only FK that updates     SDLT Configuration
   when snapshots are created)     SDLT Rate Bands
                                   Corporation Tax Configuration
                                   Assumption Configuration
                                   Engine Version Registry
                                   Calculation Audit Log
```

**Application-layer enforcement:**
- The snapshot persistence service must expose only an insert operation.
  No update or delete method is defined for snapshot entities.
- Configuration management must expose only an insert operation for new
  configuration versions. Editing existing versions is not supported.

**Database-layer enforcement:**
- The application database user must not have UPDATE or DELETE privileges
  on snapshot tables or configuration tables.
- This is the last line of defence. Application-layer protection is
  necessary but not sufficient.

**The only permitted mutation on a snapshot record:**
The `is_superseded` flag on Calculation Snapshot may be set to true when a
newer snapshot is created for the same deal. This is a status transition, not
a data mutation. The calculation data remains unchanged. All other fields on
a snapshot record are written once on creation and never changed.

---

---

# Part 5 — Versioned Configuration Strategy

## The append-only versioning pattern

All configuration tables follow the same pattern:

```
Configuration Record
  ├── id (unique)
  ├── effective_from (date)
  ├── [all configuration values for this version]
  ├── notes (human-readable rationale)
  ├── source_attribution (regulatory or data source reference)
  └── created_at (insert timestamp)
```

The engine selects the active configuration record using:

```
SELECT * FROM [config_table]
WHERE effective_from <= [calculation_date]
ORDER BY effective_from DESC
LIMIT 1
```

This query is used for each configuration table independently. A snapshot
stores the ID of the selected record from each table.

## What triggers a new configuration version

| Configuration Table    | Trigger for New Version                              |
|------------------------|------------------------------------------------------|
| SDLT Configuration     | Any government change to SDLT bands or rates         |
| Corporation Tax Config | Any Finance Act change to CT rates or thresholds     |
| Assumption Config      | Any admin decision to revise a default assumption    |
| Engine Version Registry| Any deployment of a new engine version               |

## Who can create new configuration versions

Configuration versions are created by platform administrators only. This is
not a user-facing capability. The admin interface for configuration management
is a Phase 2 concern; in Phase 1, new configuration versions may be inserted
directly by developers following a documented process.

## Multiple active configuration tables per snapshot

A snapshot references three configuration tables independently (SDLT, CT,
Assumptions). This matters when, for example, a Budget announcement changes
SDLT rates but not corporation tax rates. In that case, a new SDLT
configuration version is inserted, and new snapshots will reference the new
SDLT version. Existing snapshots continue to reference the old SDLT version.
The CT and Assumptions references for existing snapshots are unaffected.

This per-table versioning is more granular than a single "config bundle"
version. It is more accurate and avoids forcing unnecessary version increments
on unchanged configuration tables.

---

---

# Part 6 — PostGIS Compatibility

PostGIS is enabled on the PostgreSQL database from Phase 1. No spatial queries
are required in Phase 1, but the schema must not prevent them in Phase 3.

## What Phase 1 must do

- Enable the PostGIS extension on the database at provisioning time.
- Include the `postcode` field on Property (text, validated format).
- Define the Property Location entity conceptually (it will not be populated
  in Phase 1 but the design is established).

## What Phase 1 must not do

- Store coordinates as text fields (latitude_text, longitude_text). These are
  not compatible with PostGIS queries and would require a migration to convert.
- Use a custom coordinate representation that would conflict with PostGIS types.

## Phase 3 spatial additions (no Phase 1 action required)

When Phase 3 arrives, the following additions will be made without requiring
changes to existing Phase 1 tables:

- Property Location table (as defined in Group 5) is created.
- The `location` column uses PostGIS `GEOMETRY(POINT, 4326)`.
- Area Intelligence Records use PostGIS `GEOMETRY(POLYGON, 4326)` or
  `GEOMETRY(MULTIPOLYGON, 4326)` for area boundaries.
- Spatial indexes are created on location columns.
- Proximity queries (e.g. "properties within 500m of a flood zone") use
  PostGIS `ST_DWithin` with geography casting.

## Coordinate reference system

All spatial data uses SRID 4326 (WGS84 longitude/latitude). This is the
standard for web mapping (Mapbox) and is compatible with most UK geospatial
data sources (OS Places, Environment Agency, ONS).

If high-precision distance calculations are needed in future (e.g. distances
in metres rather than degrees), geography type casting (`::geography`) will
be used at query time rather than storing data in a projected CRS. This is
the standard PostGIS approach and requires no schema changes.

---

---

# Part 7 — Module and Database Boundary Recommendations

## Recommended module structure (backend)

The backend code organisation should mirror the schema domain groups. This
makes the separation between mutable and immutable data visible in code
structure, not just in the database.

```
backend/
├── domain/
│   ├── identity/         # User, InvestorProfile
│   ├── deals/            # Property, Deal
│   ├── snapshots/        # All snapshot entities — read-only after creation
│   ├── configuration/    # All versioned config entities — append-only
│   └── audit/            # Calculation audit log
│
├── engine/               # Underwriting engine — no database dependencies
│   ├── calculations/     # Pure functions: F-01 through F-22
│   ├── tax/              # Tax pathway A and B
│   ├── validation/       # Validation rules V-01 through V-25
│   └── risk_flags/       # Risk flag rule definitions and evaluation
│
└── services/
    ├── calculation_service/   # Orchestrates engine + snapshot persistence
    ├── configuration_service/ # Reads active configuration versions
    └── snapshot_service/      # Snapshot read operations and comparisons
```

The `engine/` module has no database dependency. It takes inputs and
configuration values as arguments and returns outputs. This is what makes it
independently testable and deterministic. The `calculation_service` is
responsible for fetching the correct configuration versions and invoking
the engine.

## Single database, logical separation

In Phase 1, all entities live in a single PostgreSQL database. Logical
separation is achieved through clear naming conventions and module boundaries
in code, not through separate databases or schemas.

Using PostgreSQL schemas (namespaces) is an option but adds deployment
complexity for limited benefit at this stage. The recommendation is a single
`public` schema with well-named tables in Phase 1, with the option to migrate
to separate PostgreSQL schemas in a later phase if isolation becomes important.

## Future database boundary considerations

The current single-database design is appropriate for Phase 1 through Phase 3.
The following future conditions would warrant revisiting this:

- Area intelligence data (Phase 3) grows to a size that creates performance
  pressure on the core transaction tables. If this occurs, the Area
  Intelligence Records could be moved to a separate read-optimised database
  or a dedicated geospatial data store.

- Portfolio analytics (Phase 4) requires aggregation queries over large
  snapshot datasets. A read replica or OLAP-style secondary database may be
  appropriate to avoid analytics queries competing with transactional writes.

Neither of these is a Phase 1 concern. The schema is designed to support this
evolution without requiring changes to the core deal and snapshot tables.

---

---

# Part 8 — Design Decisions and Rationale

The following decisions are recorded here for context. Significant decisions
should be promoted to DECISIONS.md.

---

## Why snapshot sub-entities rather than one large snapshot table

Inputs, outputs, and intermediates are stored as separate one-to-one related
entities rather than as a single wide snapshot table. Reasons:

- Separation of concerns: inputs, outputs, and intermediates are logically
  distinct. Combining them into one table blurs the calculation pipeline.
- The intermediates table is primarily for auditability and debugging. It does
  not need to be queried in most read paths. Separating it avoids loading
  irrelevant data in typical read operations.
- Future extensibility: adding new intermediate values (e.g. when a new
  calculation step is introduced) requires changing only the intermediates
  table, not a monolithic snapshot table.
- Risk flags are stored separately because they are queryable and filterable
  across snapshots, which a JSON blob would not support efficiently.

The trade-off is more joins for full snapshot reads. This is acceptable because
full snapshot reads are not high-frequency operations (a user reads a specific
analysis, not hundreds simultaneously), and the clarity benefit outweighs the
join cost.

---

## Why Snapshot Inputs stores both the value and the source

Every optional input stores whether it came from user override or config
default. This supports two use cases that would otherwise require re-derivation:

1. The UI can visually distinguish "you changed this from the default" without
   re-fetching configuration.
2. Auditors can see whether a user customised assumptions without querying
   historical configuration tables.

---

## Why SDLT bands are child records but CT marginal relief is not

SDLT band data is queried independently (each band's contribution to the total
is displayed to users line by line). Storing bands as relational records is
appropriate.

Corporation tax marginal relief is a formula applied to a single profit figure.
It does not produce line-by-line outputs that users see. Storing it as fields
on the Corporation Tax Configuration record is sufficient.

---

## Why Investor Profile is not referenced by Snapshot

The investor profile is a user convenience, not an authoritative calculation
input. If the profile is updated, historical snapshots must not be affected.
The solution is to copy the relevant profile values into Snapshot Inputs at
calculation time. The snapshot is self-contained. The profile reference is
not stored in the snapshot.

---

## Why Deal.latest_snapshot_id is a denormalised pointer

Finding the current snapshot for a deal using `ORDER BY created_at DESC LIMIT 1`
is functionally correct but requires a sort on every read. For a table that will
grow with every recalculation across all users, this becomes progressively
more expensive. The denormalised pointer on Deal is a read optimisation that is
justified from the start because it is simple, low-risk, and avoids an
increasingly expensive query pattern. The authoritative source remains the
snapshot table itself — if the pointer is ever inconsistent, the most recently
created snapshot is authoritative.

---

---

# Part 9 — Entities Not in Scope for Phase 1

The following entities are anticipated in later phases. They are noted here
to ensure Phase 1 decisions do not foreclose them.

| Entity                        | Phase | Dependency on Phase 1 Schema              |
|-------------------------------|-------|-------------------------------------------|
| Portfolio                     | 2     | Groups Deals; requires Deal entity        |
| Portfolio Snapshot            | 4     | Aggregates Calculation Snapshots          |
| Refinance Event               | 4     | Extends Deal with refinance tracking      |
| AI Summary Record             | 5     | References Calculation Snapshot           |
| Area Intelligence Record      | 3     | References Property via postcode/location |
| Property Location             | 3     | Extends Property with PostGIS point       |
| Scenario Comparison           | 2     | Groups two or more Snapshots for a Deal   |
| User Subscription / Plan      | 2     | Extends User entity                       |
| Admin Audit Log               | 2     | Records configuration version inserts     |

None of these require changes to Phase 1 entities. They are additive.
