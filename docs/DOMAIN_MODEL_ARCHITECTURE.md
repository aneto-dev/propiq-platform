# PropIQ Platform — Domain Model Architecture

## Purpose

This document defines the domain model for the PropIQ platform. It establishes
the conceptual structure of the business domain: which entities exist, how they
relate, what responsibilities they carry, where their boundaries lie, and what
invariants govern their behaviour.

This document is pre-implementation. It contains no SQLAlchemy models, no ORM
code, no repository definitions, no FastAPI routes, and no database DDL. It
defines the domain in business terms, from which infrastructure implementations
are derived.

All terminology is sourced from DOMAIN_GLOSSARY.md.
All entity responsibilities align with SCHEMA_ARCHITECTURE.md.
All calculation boundaries enforce ENGINE_ARCHITECTURE.md invariants.
All mutation rules implement DATA_BOUNDARIES.md classifications.
All design decisions trace to DECISIONS.md ADRs.

---

## Document Status

Version: 1.0
Covers: Phase 1 domain with explicit Phase 2-5 extension design

---

---

# Part 1 — Domain Entity Philosophy

---

## 1.1 — The Domain Reflects the Business, Not the Database

The domain model describes the business reality of UK property investment
analysis. It is not a reflection of database tables, API shapes, or
implementation convenience. Database tables, API responses, and service
objects all derive from the domain model, not the other way around.

The key business question this domain answers: **"Is this property investment
viable for this investor under these assumptions?"** Every entity, every
relationship, and every invariant is justified by its role in answering
that question reliably, reproducibly, and honestly.

---

## 1.2 — Two Fundamentally Different Kinds of Data

The domain contains two categories of entity with fundamentally different
natures. Confusing these categories is the primary source of bugs in
financial software.

**Calculation records — immutable truth:**
Once a calculation is performed and saved, it is a permanent record of what
was analysed at that moment in time. It cannot be corrected, adjusted, or
improved. If the analysis was wrong, a new one is created. The old one
remains visible, superseded but intact. This mirrors the real-world reality:
an investor who made a purchasing decision based on an analysis cannot
retroactively change what that analysis said.

**Operational state — mutable workflow:**
A deal's current status, a user's profile preferences, a property's address
details — these change as the investor's situation evolves. They are not
records of historical events; they are current representations of ongoing
reality.

The domain model keeps these two categories physically and conceptually
separate. No entity belongs to both. No operation crosses the boundary from
operational state into calculation records.

---

## 1.3 — The Underwriting Engine Is Not a Domain Entity

The underwriting engine is a pure computation function. It accepts data,
applies formulas, and returns results. It has no identity, no state, no
lifecycle, and no persistence. It is not a domain entity — it is a service
that the domain uses.

This distinction matters because it determines where business rules live.
Business rules about what inputs are valid belong in the engine's validation
pipeline. Business rules about who may trigger a calculation, when recalculation
is appropriate, and how results are stored belong in domain services and the
domain model.

---

## 1.4 — Explainability Is a Domain Concern, Not a Display Concern

ADR-010 establishes that explainability is a product requirement. This means
the domain model must carry the data required to explain any calculation — not
just the final outputs, but the intermediate steps, the assumption sources,
the configuration versions, and the risk flag trigger values. These are domain
concepts, not display hints.

A snapshot that stores only outputs cannot explain itself. A snapshot that
stores inputs, intermediates, assumption provenance, and the full calculation
lineage can be explained to any user, auditor, or regulator at any future
point in time.

---

---

# Part 2 — Separation Between Domain Entities and Persistence Models

The domain model defines entities in business terms. Infrastructure
(persistence) models define how those entities are stored. These are
different things and must be kept separate.

---

## 2.1 — What Domain Entities Are

Domain entities are named conceptual objects that carry identity, behaviour,
and invariants. They exist in the business domain regardless of how they are
stored. A `Deal` is a deal whether it lives in PostgreSQL, in memory, or in
a file. Its identity, its rules about what makes it valid, and its allowed
state transitions are domain concerns.

---

## 2.2 — What Persistence Models Are Not

Persistence models (SQLAlchemy models in this codebase) are infrastructure.
They describe how domain entities map to database rows. A SQLAlchemy model for
`Deal` is not the domain `Deal` — it is a representation of the deal that
PostgreSQL can store and retrieve. The two can have the same shape in simple
cases, but they serve different purposes and should never be conflated.

The most dangerous conflation is when a persistence model carries domain
behaviour (methods that enforce business rules). When this happens, the
domain logic becomes tightly coupled to the database structure. Changing
the schema requires changing the business rule, and vice versa.

---

## 2.3 — The Layer Boundary

```
Domain entities        — pure Python dataclasses or named tuples
                         no inheritance from ORM base classes
                         no database-specific types
                         carry invariants and business behaviour

Repository interfaces  — define what persistence operations exist
                         (abstract: load_deal_by_id, save_snapshot, etc.)

Persistence models     — SQLAlchemy mapped classes
                         implement the repository interface
                         translate between domain objects and database rows
                         no business logic

Services               — operate on domain entities
                         call repository interfaces (not persistence models directly)
                         call the engine
                         enforce ownership and state transition rules
```

Domain entities are constructed from persistence models when data is loaded.
Persistence models are populated from domain entities when data is saved.
This translation happens in the repository layer, not in the service layer
and not in the domain layer.

---

## 2.4 — Engine Data Contracts Are Not Domain Entities

`EngineInput`, `EngineConfig`, and `EngineResult` are engine data contracts
(defined in ENGINE_CONTRACTS.md). They are not domain entities. They are
the input/output types of the engine function. They are assembled by the
service layer from domain entities and configuration, passed to the engine,
and then translated into snapshot domain entities for persistence.

```
Domain entity (Deal) → service assembles → EngineInput
EngineInput + EngineConfig → engine.run() → EngineResult
EngineResult → service translates → CalculationSnapshot (domain entity)
CalculationSnapshot → repository persists → database row
```

---

---

# Part 3 — Aggregate Boundaries

An aggregate is a cluster of domain objects that is treated as a unit for
data changes. The aggregate root controls access to all objects within the
aggregate. Outside observers interact only with the aggregate root, never
with internal objects directly.

PropIQ has four primary aggregates.

---

## 3.1 — The CalculationSnapshot Aggregate

**Aggregate root:** `CalculationSnapshot`

**Internal objects:** `SnapshotInputs`, `SnapshotOutputs`, `SnapshotIntermediates`,
`List[RiskFlag]`, `List[ValidationWarning]`

**Invariant:** Once created, the aggregate is immutable. No part of it may
change. New snapshots supersede old ones but never modify them.

**Creation rule:** The aggregate is created as a complete unit. It is never
created partially. All internal objects come into existence simultaneously
in a single atomic operation.

**Access rule:** External code reads snapshot data through the root only.
`snapshot.outputs.annual_cash_flow_gbp` not `snapshot_outputs_repository.get_by_snapshot_id(...)`.

**Why this is an aggregate:** The snapshot's internal objects (inputs, outputs,
intermediates, flags) have no independent existence or identity outside the
snapshot. A `SnapshotOutput` record has no meaning without its parent snapshot.
They are created together, read together, and conceptually are one thing.

---

## 3.2 — The Deal Aggregate

**Aggregate root:** `Deal`

**Internal objects:** Working input fields (treated as a value object embedded
in the deal), `DealStatus` (enum value object)

**Does NOT include:** Snapshots. A deal references its latest snapshot by ID
but does not own the snapshot. The snapshot aggregate is independent.

**Invariant:** A deal always belongs to exactly one user and one property.
A deal's status transitions follow the defined state machine (Part 5.2).
Working inputs are mutable; the deal's identity and ownership are not.

**Why snapshots are external to the deal aggregate:** Snapshots are immutable
and permanent. A deal is mutable and can be archived. If snapshots were inside
the deal aggregate, the "archive a deal" operation would have to decide what
to do with immutable historical records. By keeping them separate, archiving
a deal simply changes its status — snapshots remain unaffected.

---

## 3.3 — The Property Aggregate

**Aggregate root:** `Property`

**Internal objects:** `PropertyAddress` (value object), `LeaseDetails`
(optional value object for leasehold)

**Does NOT include:** Deals. A property has many deals but does not own them.
Deals reference properties.

**Invariant:** A property always belongs to exactly one user. A property's
tenure cannot change after creation (this would affect any existing snapshot
that recorded the tenure at calculation time). Address and other mutable fields
may be updated.

**Note on tenure immutability:** Tenure (freehold/leasehold) is a fundamental
physical characteristic. If a user entered tenure incorrectly, the correct
action is to create a new property record or to archive the incorrect one
and create a replacement. The historical snapshots that referenced the
incorrect tenure remain as they were — they are a record of what was analysed
at the time.

---

## 3.4 — The VersionedConfiguration Aggregate

**Aggregate root:** One of `SDLTConfiguration`, `CorporationTaxConfiguration`,
or `AssumptionConfiguration`

**Internal objects:** `List[SDLTBand]` (for SDLT only)

**Invariant:** Configuration aggregates are append-only. A new version is a
new aggregate instance. Existing aggregate instances are never modified.

**Why configuration is an aggregate:** A set of SDLT bands is not meaningful
in isolation — band 2 without band 1 and band 3 is not a valid SDLT configuration.
The bands form a coherent unit that must be loaded and applied as a whole.
The version root record ensures consistency of the band set.

---

---

# Part 4 — Entity Lifecycle Rules

---

## 4.1 — User Lifecycle

```
CREATED (on first authenticated login)
    ↓ authenticate repeatedly
ACTIVE
    ↓ admin action or account closure
SUSPENDED (access denied; data retained)
    ↓ reactivation
ACTIVE
    ↓ GDPR erasure request (Phase 2)
ARCHIVED (PII removed; financial records retained)
```

A User is created once. It cannot be deleted. ARCHIVED status means PII fields
are anonymised, not that the record is removed. Historical snapshot references
to `user_id` remain intact and are not cascade-deleted.

**Phase 1 rule:** Only ACTIVE → SUSPENDED and SUSPENDED → ACTIVE transitions
are supported in Phase 1. ARCHIVED transition requires the GDPR anonymisation
process defined in Phase 2.

---

## 4.2 — InvestorProfile Lifecycle

```
CREATED (user creates a profile)
    ↓ user edits preferences
ACTIVE
    ↓ user creates a replacement profile
ARCHIVED (is_archived = true)
```

A profile is archived when superseded, not deleted. The `is_default` flag
may be moved from one profile to another. A user may have multiple active
profiles. An archived profile may still be the `investor_profile_id` on
historic deals — this is informational only since deal snapshots do not
reference profiles by ID.

---

## 4.3 — Property Lifecycle

```
CREATED
    ↓ user refines address / details
ACTIVE
    ↓ user no longer wishes to track this property
ARCHIVED (is_archived = true)
```

Properties are never deleted. An archived property's historical deals and
snapshots remain fully accessible. The property address and details may be
updated while ACTIVE — updates do not affect historical snapshots because
snapshots store the postcode and property type at calculation time.

---

## 4.4 — Deal Lifecycle

```
DRAFT (created; no snapshot yet; working inputs may be incomplete)
    ↓ user runs first calculation
ANALYSED (latest_snapshot_id is set; working inputs are complete)
    ↓ user continues to edit inputs and recalculate
ANALYSED (each recalculation creates a new snapshot; deal remains ANALYSED)
    ↓ user archives the deal
ARCHIVED
```

Status transitions are one-way. An ARCHIVED deal cannot be moved back to
ANALYSED. A user who wants to resume analysis on an archived deal creates
a new deal against the same property.

**Phase 1 rule:** Deals support DRAFT, ANALYSED, and ARCHIVED only. Future
workflow stages (OFFER_SUBMITTED, FINANCING, etc.) are Phase 2+ additions.

---

## 4.5 — CalculationSnapshot Lifecycle

```
CREATED (calculation succeeds; snapshot is written atomically)
    ↓ new calculation is run for the same deal
SUPERSEDED (is_superseded = true; superseded_at is set)
```

This is the entire lifecycle. A snapshot is created once and superseded when
a newer one exists. There is no further state transition. Superseded snapshots
remain permanently accessible and are never deleted.

**The is_superseded transition is the only permitted mutation on any snapshot entity.**

---

## 4.6 — VersionedConfiguration Lifecycle

```
CREATED (admin inserts a new version with an effective_from date)
    [remains permanently accessible; referenced by historical snapshots]
```

No lifecycle transitions. Configuration versions are created and read.
They have no status, no archival, no supersession flag. A newer version
with a later `effective_from` date becomes the active version for new
calculations; older versions remain active for historical snapshot
reproduction.

---

---

# Part 5 — Value Object Candidates

Value objects are domain concepts that are defined by their content rather
than by an identity. Two value objects with identical content are
interchangeable. They are immutable by definition.

---

## 5.1 — PropertyAddress

```
PropertyAddress:
    address_line_1: str  (required)
    address_line_2: str  (optional)
    city: str            (required)
    postcode: str        (required, validated UK format)
    country: PropertyCountry  (ENGLAND in Phase 1)
```

**Why a value object:** An address has no independent identity — two
properties at the same address are not the same property. The address is
a description of the location, not an entity in its own right.

**Validation rule:** `postcode` must match the UK postcode format. Validation
occurs at construction time. A `PropertyAddress` with an invalid postcode
cannot be constructed.

---

## 5.2 — DealStatus

```
DealStatus (enum value object):
    DRAFT
    ANALYSED
    ARCHIVED
```

**Why a value object:** Status is a named constant with defined transition
rules. It carries no identity. Transition rules:

```
DRAFT → ANALYSED  (allowed: first snapshot created)
ANALYSED → ANALYSED  (allowed: recalculation creates new snapshot)
ANALYSED → ARCHIVED  (allowed: user archives)
DRAFT → ARCHIVED  (allowed: user abandons a draft deal)
ARCHIVED → any  (NOT allowed)
DRAFT → DRAFT  (allowed: user edits working inputs without calculating)
```

---

## 5.3 — InputSource

```
InputSource (enum value object):
    USER_OVERRIDE    — user explicitly provided this value
    CONFIG_DEFAULT   — value was drawn from active assumption configuration
```

Extended in Phase 3+ with `EXTERNAL_PROVIDER` and Phase 5+ with `AI_SUGGESTION`.

**Why a value object:** Source provenance is a property of the input value
pair, not a standalone entity. It always accompanies a specific optional
input value in the context of a snapshot.

---

## 5.4 — FlagSeverity

```
FlagSeverity (enum value object):
    HIGH    — materially affects deal viability
    MEDIUM  — warrants review
    INFO    — contextual disclosure
```

---

## 5.5 — OwnershipStructure

```
OwnershipStructure (enum value object):
    INDIVIDUAL
    LIMITED_COMPANY
```

**Significance:** This is not merely a label — it determines which tax
pathway the engine uses (Section 24 vs Corporation Tax), which default
accountancy cost applies, and which ICR threshold is relevant. It is a
fundamental characteristic of the deal, not just a preference.

---

## 5.6 — IncomeTaxBand

```
IncomeTaxBand (enum value object):
    BASIC_RATE       (effective rate: 20%)
    HIGHER_RATE      (effective rate: 40%)
    ADDITIONAL_RATE  (effective rate: 45%)
```

**Constraint:** Only meaningful when `ownership_structure = INDIVIDUAL`. The
combination `(INDIVIDUAL, null income_tax_band)` is invalid. The combination
`(LIMITED_COMPANY, any income_tax_band)` is also invalid.

---

## 5.7 — MortgageType

```
MortgageType (enum value object):
    INTEREST_ONLY
    REPAYMENT
```

**Significance:** Determines two separate formula pathways — the monthly
payment formula (F-06) and the annual interest calculation (F-08). The
two pathways produce materially different tax implications for repayment
mortgages because only the interest component is relevant to Section 24
and corporation tax deductions.

---

## 5.8 — Money

```
Money:
    amount: Decimal  (non-negative unless explicitly a cash flow value)
    currency: str    (GBP always in Phase 1; field exists for future multi-currency)
```

**Why a value object:** A monetary amount without a currency is ambiguous.
Phase 1 is GBP-only, but encoding the currency in the value object prevents
the class of bug where GBP and USD amounts are accidentally compared or added.

**Note on negative money:** Cash flow values (`annual_cash_flow_gbp`,
`monthly_cash_flow_gbp`) may be negative and are valid negative `Money`
values. A negative cash flow is a real business outcome, not a data error.

---

## 5.9 — Rate

```
Rate:
    value: Decimal  (stored as a percentage, e.g. Decimal("5.5") for 5.5%)
```

**Why a value object:** Rate values have a specific representation convention
in this platform — percentages are stored as their percentage value (5.5),
not as a decimal fraction (0.055). A `Rate` value object enforces this
convention and makes unit confusion impossible at the domain level.

---

## 5.10 — LeaseDetails

```
LeaseDetails:
    lease_years_remaining: int  (required for LEASEHOLD; not permitted for FREEHOLD)
```

**Why a value object:** Lease details are always in the context of a leasehold
tenure. They have no independent identity. Their validity depends on the
accompanying tenure value.

**Invariant:** `LeaseDetails` cannot exist without `tenure = LEASEHOLD`.
Attempting to construct a `Property` with `tenure = FREEHOLD` and a
`LeaseDetails` value object is a domain invariant violation.

---

## 5.11 — ConfigVersionRefs

```
ConfigVersionRefs:
    assumption_config_version_id: UUID
    sdlt_config_version_id: UUID
    corporation_tax_config_version_id: UUID
```

**Why a value object:** The three version IDs are always carried together
as a set. They represent "the complete configuration context for one
calculation." Separating them would create the risk of inconsistent
configuration references.

**Important:** This value object is held by the service layer, not by the
engine. The engine never sees UUIDs. The service uses `ConfigVersionRefs`
to populate the snapshot root record after the engine completes.

---

---

# Part 6 — Domain Service Boundaries

Domain services perform operations that don't naturally belong to a single
entity. They are stateless and named for their purpose.

---

## 6.1 — CalculationOrchestrationService

**Responsibility:** The single point of orchestration for a calculation
request. Assembles the `EngineInput` and `EngineConfig` from domain entities
and configuration, calls the engine, and delegates snapshot creation.

**Inputs:** authenticated user identity, deal ID, user-provided input values

**Outputs:** `CalculationResult` (either a `SnapshotSummary` on success,
a `ValidationFailure` on invalid input, or a `CalculationError` on failure)

**Key rule:** This service never contains formula logic. It is the coordinator,
not the calculator.

---

## 6.2 — ConfigurationResolutionService

**Responsibility:** Resolves the active configuration versions for a given
calculation date and converts them into `EngineConfig` for the engine and
`ConfigVersionRefs` for the snapshot.

**Inputs:** calculation date

**Outputs:** `ConfigBundle` (containing `EngineConfig` and `ConfigVersionRefs`)

**Key rule:** This service reads configuration domain entities and translates
them into engine-compatible data contracts. It is the bridge between the
configuration domain and the engine boundary.

---

## 6.3 — InputDefaultResolutionService

**Responsibility:** Resolves optional inputs. For each optional input, if the
user provided a value it is used with source `USER_OVERRIDE`; if not, the
active assumption configuration default is used with source `CONFIG_DEFAULT`.

**Outputs:** Fully-populated optional inputs with their `InputSource` tags

**Key rule:** This service enforces ADR-013 (user override precedence). It is
the point where the authority hierarchy (user > config default) is implemented
as code. The engine never participates in default resolution — by the time
`EngineInput` is assembled, all defaults are resolved.

---

## 6.4 — OwnershipVerificationService

**Responsibility:** Verifies that an authenticated user owns a deal, property,
or investor profile before any mutation or read is permitted.

**Rule:** A resource belonging to a different user returns `NotFound`, not
`Forbidden`. Existence is not disclosed to unauthorised users (SERVICE_ARCHITECTURE.md).

---

## 6.5 — DealStatusTransitionService

**Responsibility:** Validates and applies deal status transitions. Enforces
the state machine in Part 5.2. Rejects invalid transitions with a domain error.

**Phase 1 transitions supported:**
- `DRAFT → ANALYSED` (triggered by snapshot creation)
- `ANALYSED → ARCHIVED` (triggered by user action)
- `DRAFT → ARCHIVED` (triggered by user action)

---

---

# Part 7 — Calculation Engine Boundaries

The engine boundary is the most important architectural boundary in the
system. Its rules are invariants (not guidelines).

---

## 7.1 — What Crosses the Engine Boundary (inward)

Only `EngineInput` and `EngineConfig` cross into the engine. Both are plain
data objects — no database sessions, no service references, no repository
calls, no infrastructure dependencies of any kind.

`EngineInput` contains resolved values only. By the time it reaches the
engine, every optional field has a value. No null optional fields. No
default-resolution logic inside the engine.

`EngineConfig` contains plain numeric and structured values. No UUID
references. No `effective_from` dates. No metadata. Just the numbers the
formulas need.

---

## 7.2 — What Crosses the Engine Boundary (outward)

`EngineResult` (on success), `ValidationResult` (on validation failure),
or `EngineError` (on unexpected failure). All are plain data objects.

`EngineResult` contains no timestamps, no snapshot IDs, no database
references, no version IDs. These are assigned by the persistence layer.

---

## 7.3 — What Never Crosses the Engine Boundary

```
NEVER enters the engine:
    Database sessions or connections
    Repository objects or interfaces
    Service objects
    Configuration version IDs or UUIDs
    Timestamps or system clock values
    User IDs or deal IDs
    HTTP request context
    Global state of any kind

NEVER leaves the engine:
    Side effects
    Database writes
    Log entries (only structured results)
    Exceptions that propagate unhandled
```

---

## 7.4 — The Engine Has No Knowledge of Snapshots

The engine does not know what a snapshot is. It receives data and returns
data. The service layer decides what to do with the result — persist it,
discard it, or return an error. The engine's job is to compute, not to
decide.

---

---

# Part 8 — CalculationSnapshot Aggregate Design

The `CalculationSnapshot` is the platform's most important domain entity.
Its design is the direct expression of ADR-002 (immutable snapshots) and
TRUST_MODEL.md.

---

## 8.1 — Aggregate Root: CalculationSnapshot

```
CalculationSnapshot:
    id: UUID                                     [IMMUTABLE, set at creation]
    deal_id: UUID                                [IMMUTABLE, set at creation]
    user_id: UUID                                [IMMUTABLE, set at creation]
    engine_version: str                          [IMMUTABLE, set at creation]
    config_version_refs: ConfigVersionRefs       [IMMUTABLE, set at creation]
    calculated_at: datetime (UTC)                [IMMUTABLE, set at creation]
    inputs: SnapshotInputs                       [IMMUTABLE, set at creation]
    outputs: SnapshotOutputs                     [IMMUTABLE, set at creation]
    intermediates: SnapshotIntermediates         [IMMUTABLE, set at creation]
    risk_flags: List[RiskFlag]                   [IMMUTABLE, set at creation]
    validation_warnings: List[ValidationWarning] [IMMUTABLE, set at creation]
    is_superseded: bool                          MUTABLE (only permitted mutation)
    superseded_at: datetime | None               MUTABLE (paired with is_superseded)
    calculation_duration_ms: int | None          [IMMUTABLE, set at creation]
```

**Aggregate invariant:** All fields except `is_superseded` and `superseded_at`
are set at creation time and never changed. The aggregate root enforces this
by having no setter methods for any field except the supersession pair.

**Factory method:** `CalculationSnapshot` is only created via a factory function
(not a constructor called with individual arguments). The factory accepts
`EngineResult`, `ConfigVersionRefs`, `deal_id`, `user_id`, and `calculated_at`.
It constructs the aggregate completely. Partial construction is not permitted.

---

## 8.2 — SnapshotInputs (internal aggregate object)

Contains every input value used in the calculation, with source provenance
for every optional field.

```
SnapshotInputs:
    Required inputs (all from EngineInput):
        purchase_price: Money
        monthly_rent: Money
        deposit_amount: Money
        mortgage_interest_rate: Rate
        mortgage_term_years: int
        mortgage_type: MortgageType
        ownership_structure: OwnershipStructure
        income_tax_band: IncomeTaxBand | None
        is_additional_dwelling: bool
        property_type: PropertyType
        tenure: Tenure
        property_country: PropertyCountry
        postcode: str
        lease_years_remaining: int | None

    Optional inputs with provenance (each is a pair):
        void_rate_percent: Rate
        void_rate_percent_source: InputSource
        letting_agent_fee_percent: Rate
        letting_agent_fee_percent_source: InputSource
        maintenance_reserve_percent: Rate
        maintenance_reserve_percent_source: InputSource
        landlord_insurance_annual: Money
        landlord_insurance_annual_source: InputSource
        purchase_legal_costs: Money
        purchase_legal_costs_source: InputSource
        refurbishment_cost: Money
        refurbishment_cost_source: InputSource
        annual_service_charge: Money
        annual_service_charge_source: InputSource
        annual_ground_rent: Money
        annual_ground_rent_source: InputSource
        annual_accountancy_cost: Money
        annual_accountancy_cost_source: InputSource
```

**Design note — provenance is non-nullable:** Every optional input pair
is always both value and source together. There is no state where a value
exists but its provenance is unknown. This enforces ADR-009 (assumption
provenance) and ADR-013 (user override precedence) at the domain level.

---

## 8.3 — SnapshotOutputs (internal aggregate object)

The user-facing calculation results. Field names match DOMAIN_GLOSSARY.md
API field names and ENGINE_CONTRACTS.md EngineOutputs exactly.

```
SnapshotOutputs:
    gross_annual_rent_gbp: Money
    effective_annual_rent_gbp: Money
    total_operating_costs_annual_gbp: Money
    net_operating_income_gbp: Money
    annual_mortgage_cost_gbp: Money
    annual_tax_liability_gbp: Money
    annual_cash_flow_gbp: Money          (may be negative)
    monthly_cash_flow_gbp: Money         (may be negative)
    gross_yield_percent: Rate
    net_yield_percent: Rate
    roce_percent: Rate
    cash_on_cash_return_percent: Rate    (may be negative)
    ltv_percent: Rate
    icr_percent: Rate | None             (None for cash purchase)
    total_sdlt_gbp: Money
    total_acquisition_cost_gbp: Money
    total_cash_deployed_gbp: Money
```

**No behaviour on this object:** `SnapshotOutputs` is a pure data container.
No derived properties, no computed methods, no formatting logic. The service
layer reads these values and the API layer serialises them.

---

## 8.4 — SnapshotIntermediates (internal aggregate object)

All intermediate calculation values from the engine pipeline. Exists for
auditability, reproducibility verification, and the future explainability
layer (Phase 3+). Not displayed in routine operation.

```
SnapshotIntermediates:
    void_rate_decimal_applied: Decimal
    gross_annual_rent_gbp: Money
    effective_annual_rent_gbp: Money
    loan_amount_gbp: Money
    ltv_percent: Rate
    monthly_mortgage_payment_gbp: Money
    annual_mortgage_cost_gbp: Money
    annual_mortgage_interest_gbp: Money
    letting_agent_annual_gbp: Money
    letting_agent_vat_rate_applied: Rate
    annual_maintenance_reserve_gbp: Money
    total_operating_costs_annual_gbp: Money
    net_operating_income_gbp: Money
    sdlt_band_breakdown: List[SDLTBandResult]
    sdlt_base_gbp: Money
    sdlt_surcharge_gbp: Money
    sdlt_surcharge_rate_applied: Rate
    total_sdlt_gbp: Money
    total_acquisition_cost_gbp: Money
    total_cash_deployed_gbp: Money
    stressed_annual_interest_gbp: Money
    stress_test_rate_applied_percent: Rate
    taxable_income_or_profit_gbp: Money     (may be negative)
    income_tax_gross_gbp: Money | None       (INDIVIDUAL pathway only)
    mortgage_interest_tax_credit_gbp: Money | None  (INDIVIDUAL pathway only)
    corporation_tax_gross_gbp: Money | None  (LIMITED_COMPANY pathway only)
    annual_tax_liability_gbp: Money
    pre_tax_annual_cash_flow_gbp: Money      (may be negative)
    section_24_applies: bool
```

**SDLTBandResult:**
```
SDLTBandResult:
    band_lower: Money
    band_upper: Money | None      (None for the top band)
    rate: Rate
    taxable_in_band: Money
    tax_in_band: Money
```

---

---

# Part 9 — Deal Aggregate Design

The `Deal` is the mutable workspace where an investor analyses a property.
It is the point of interaction for most user actions.

---

## 9.1 — Aggregate Root: Deal

```
Deal:
    id: UUID
    user_id: UUID                                [IMMUTABLE after creation]
    property_id: UUID                            [IMMUTABLE after creation]
    investor_profile_id: UUID | None             MUTABLE (convenience reference only)
    label: str                                   MUTABLE
    status: DealStatus                           MUTABLE (via defined transitions only)
    latest_snapshot_id: UUID | None              MUTABLE (updated by snapshot creation)
    working_inputs: DealWorkingInputs            MUTABLE
    created_at: datetime                         [IMMUTABLE]
    updated_at: datetime                         MUTABLE
```

---

## 9.2 — DealWorkingInputs (embedded value object)

The user's current editable input state. These are working values that may
be incomplete (for a DRAFT deal). They are NOT the values used in calculations
— those are copied into `SnapshotInputs` at calculation time.

```
DealWorkingInputs:
    purchase_price: Money | None
    monthly_rent: Money | None
    deposit_amount: Money | None
    mortgage_interest_rate: Rate | None
    mortgage_term_years: int | None
    mortgage_type: MortgageType | None
    ownership_structure: OwnershipStructure | None
    income_tax_band: IncomeTaxBand | None
    is_additional_dwelling: bool | None
    void_rate_percent: Rate | None         (None = use config default)
    letting_agent_fee_percent: Rate | None
    maintenance_reserve_percent: Rate | None
    landlord_insurance_annual: Money | None
    purchase_legal_costs: Money | None
    refurbishment_cost: Money | None
    annual_service_charge: Money | None
    annual_ground_rent: Money | None
    annual_accountancy_cost: Money | None
```

**Why nullable:** Working inputs reflect a deal under construction. Null means
"not yet entered". The engine's validation pipeline — not the domain model —
enforces that required inputs are present at calculation time.

**Separation principle:** A null `void_rate_percent` in working inputs means
"use the config default when calculating." The service layer resolves this
before passing to the engine. The deal record never needs to know what the
current default void rate is.

---

## 9.3 — Deal Behaviour

The deal aggregate root exposes a small set of operations that enforce its
invariants.

**`update_working_inputs(inputs: DealWorkingInputs)`**
Replaces the working input state. Valid only when `status != ARCHIVED`.
Updates `updated_at`.

**`apply_snapshot_created(snapshot_id: UUID)`**
Sets `latest_snapshot_id` to the new snapshot ID. Transitions status from
`DRAFT` to `ANALYSED` if currently `DRAFT`. Updates `updated_at`. This is
the only operation that advances the status from DRAFT to ANALYSED.

**`archive()`**
Transitions status to `ARCHIVED`. Valid from `DRAFT` or `ANALYSED` only.
Once archived, no further operations are permitted except reading.

**What the deal aggregate does NOT do:**
- Trigger calculations
- Know what the calculation produced
- Know about snapshot contents
- Validate inputs against domain rules (that is the engine's job)

---

---

# Part 10 — Configuration Aggregate Design

Configuration aggregates are append-only. Each version is a complete,
independent entity.

---

## 10.1 — SDLTConfiguration Aggregate Root

```
SDLTConfiguration:
    id: UUID
    effective_from: date
    property_country: PropertyCountry
    additional_dwelling_surcharge_rate: Rate
    bands: List[SDLTBand]          (always loaded together with the root)
    notes: str | None
    source_attribution: str | None
    created_at: datetime
    created_by_user_id: UUID | None
```

**SDLTBand:**
```
SDLTBand:
    band_order: int
    band_lower: Money
    band_upper: Money | None
    rate: Rate
```

**Invariant:** A `SDLTConfiguration` is only valid with at least one band.
An empty band list is a construction error. The bands must be in ascending
order (enforced by `band_order`).

---

## 10.2 — CorporationTaxConfiguration Aggregate Root

```
CorporationTaxConfiguration:
    id: UUID
    effective_from: date
    small_profits_rate: Rate
    small_profits_upper_threshold: Money
    main_rate: Rate
    main_rate_lower_threshold: Money
    marginal_relief_numerator: int
    marginal_relief_denominator: int
    notes: str | None
    source_attribution: str | None
    created_at: datetime
    created_by_user_id: UUID | None
```

**Invariant:** `small_profits_upper_threshold` < `main_rate_lower_threshold`.
A configuration where the thresholds are equal or inverted is a construction
error.

---

## 10.3 — AssumptionConfiguration Aggregate Root

```
AssumptionConfiguration:
    id: UUID
    effective_from: date
    void_rate_percent_default: Rate
    letting_agent_fee_percent_default: Rate
    letting_agent_vat_rate_percent: Rate
    maintenance_reserve_percent_default: Rate
    landlord_insurance_annual_default: Money
    purchase_legal_costs_default: Money
    accountancy_cost_individual_default: Money
    accountancy_cost_ltd_default: Money
    stress_test_rate_percent: Rate
    icr_threshold_basic_rate_percent: Rate
    icr_threshold_higher_rate_percent: Rate
    notes: str | None
    source_attribution: str | None
    created_at: datetime
    created_by_user_id: UUID | None
```

**Invariant:** `icr_threshold_higher_rate_percent` >= `icr_threshold_basic_rate_percent`.

---

## 10.4 — EngineVersionRecord (not a full aggregate, but a domain entity)

```
EngineVersionRecord:
    version_string: str          (primary identity — e.g. "1.0.0")
    released_at: datetime
    change_summary: str
    is_breaking_change: bool
    specification_ref: str | None
    created_at: datetime
```

This is a registry entry, not a configuration that participates in calculations.
It exists for audit and traceability only.

---

---

# Part 11 — User and Investor Profile Relationships

---

## 11.1 — User Domain Entity

```
User:
    id: UUID
    supabase_auth_id: UUID         [IMMUTABLE — join key to auth provider]
    email: str                     MUTABLE (synced from auth; not authoritative)
    display_name: str | None       MUTABLE
    status: UserStatus             MUTABLE (via defined transitions)
    created_at: datetime           [IMMUTABLE]
    updated_at: datetime
```

**What the User entity does NOT own:** Deals, properties, and snapshots are
associated with a user by `user_id` reference but are not "inside" the user
aggregate. The user does not hold a list of deals. This avoids loading the
entire user aggregate every time a deal is loaded.

---

## 11.2 — InvestorProfile Domain Entity

```
InvestorProfile:
    id: UUID
    user_id: UUID                  [IMMUTABLE]
    label: str                     MUTABLE
    ownership_structure: OwnershipStructure  MUTABLE
    income_tax_band: IncomeTaxBand | None    MUTABLE
    is_default: bool               MUTABLE
    is_archived: bool              MUTABLE
    archived_at: datetime | None   MUTABLE
    created_at: datetime           [IMMUTABLE]
    updated_at: datetime
```

**Critical domain rule:** The investor profile is a convenience entity.
Profile values are copied into `SnapshotInputs.ownership_structure` and
`SnapshotInputs.income_tax_band` at calculation time. The snapshot never
stores a reference to the profile. If the profile is later changed or
archived, all historical snapshots remain self-contained and unaffected.

**This implements ADR-013 at the domain level:** The snapshot stores what
was actually used — explicit copied values — not a reference to something
mutable.

---

## 11.3 — Profile-to-Deal Relationship

A deal may optionally reference an investor profile (`investor_profile_id`).
This reference is informational only — it records which profile was used
to pre-populate the deal's working inputs when it was created.

The profile reference on the deal does NOT affect:
- What values are used in calculations (those come from `DealWorkingInputs`)
- What is stored in any snapshot
- Historical reproducibility

---

---

# Part 12 — Risk Flag Domain Representation

---

## 12.1 — RiskFlag Value Object

```
RiskFlag:
    code: str              (e.g. "NEGATIVE_CASHFLOW")
    severity: FlagSeverity
    triggered_by_field: str    (the output field that caused the flag)
    triggered_by_value: str    (the value at trigger time, as string)
    message: str               (user-facing message at calculation time)
```

**Why a value object:** A risk flag has no independent identity. It exists
only within the context of a `CalculationSnapshot`. Two flags with identical
code, severity, field, value, and message are equivalent.

**Why message is stored with the flag:** The message content may change in
future engine versions. The message stored in the snapshot is the exact text
shown to the user at the time of calculation. This supports ADR-010
(explainability): a user reviewing a historical snapshot sees exactly what
they were told.

**Why triggered_by_value is a string:** Both numeric values ("132.86" for
ICR) and non-numeric values ("HIGHER_RATE" for income_tax_band) can trigger
flags. A string representation is consistent regardless of the originating
type and is human-readable in the snapshot record.

---

## 12.2 — Risk Flags Are Not Blocking

Risk flags are informational. They do not prevent snapshot creation, deal
saving, or any user action. They are displayed prominently in the deal
summary to inform the investor's judgement.

**Domain invariant:** The presence or absence of risk flags never changes
the calculation outputs. The outputs are what the formulas produced. Flags
are an interpretation layer above the outputs.

---

---

# Part 13 — Validation Result Domain Representation

---

## 13.1 — ValidationResult

Returned by the engine when inputs fail validation. Not a domain entity in
the persistence sense — it is never stored directly. The validation errors
it contains are stored in `audit_calculations.validation_errors`.

```
ValidationResult:
    is_valid: bool
    hard_errors: List[ValidationError]
    warnings: List[ValidationWarning]
```

**ValidationError:**
```
ValidationError:
    rule_code: str    (e.g. "V-07")
    field: str        (the input field that triggered the rule)
    message: str      (user-facing message)
```

**ValidationWarning:**
```
ValidationWarning:
    rule_code: str
    field: str
    message: str
```

**Domain rule:** When `is_valid = false`, the engine returns a
`ValidationResult` and does not proceed to calculation. No `EngineResult`
exists. No snapshot is created. The `ValidationResult` is passed back to
the service layer, which records the errors in the audit log and returns
them to the API layer for user feedback.

When `is_valid = true`, warnings are carried forward into the final
`EngineResult.validation_warnings` and stored in the snapshot as
`List[ValidationWarning]`.

---

---

# Part 14 — Audit Event Representation

---

## 14.1 — CalculationAuditEvent

```
CalculationAuditEvent:
    id: UUID
    user_id: UUID
    deal_id: UUID
    snapshot_id: UUID | None       (None for failure outcomes)
    triggered_at: datetime (UTC)
    outcome: CalculationOutcome
    engine_version: str
    validation_errors: List[ValidationError] | None  (for VALIDATION_FAILURE)
    error_detail: str | None                         (for ENGINE_ERROR)
    client_context: str | None
    created_at: datetime
```

**CalculationOutcome:**
```
CalculationOutcome (enum value object):
    SUCCESS
    VALIDATION_FAILURE
    ENGINE_ERROR
```

**Domain rule:** Every calculation attempt produces exactly one
`CalculationAuditEvent`. No exceptions. A `SUCCESS` event always has a
`snapshot_id`. A `VALIDATION_FAILURE` always has `validation_errors`. An
`ENGINE_ERROR` always has `error_detail`.

**Audit events are append-only domain entities.** Once created, they are
never modified. They are not part of any mutable aggregate.

---

---

# Part 15 — Domain Invariants

These invariants are business truths that the domain model enforces.
Any code that violates them introduces a correctness defect.

---

## I-01 — Snapshots Are Immutable

Once a `CalculationSnapshot` is created, its inputs, outputs, intermediates,
risk flags, and validation warnings never change. The supersession flag is the
only permitted mutation and affects only the snapshot's status, not its content.

**Enforcement:** Read-only domain entity construction. Service layer has
INSERT privilege only on snapshot tables. No setter methods on snapshot
aggregate internals.

---

## I-02 — User Overrides Always Prevail

When assembling `SnapshotInputs`, a user-provided value always supersedes
a platform default, regardless of what the platform default says. This is
enforced in `InputDefaultResolutionService` and is visible in every `_source`
column: a `USER_OVERRIDE` source means the user's choice was used.

**Enforcement:** `InputDefaultResolutionService` checks user value first.
`InputSource` on every optional input makes the decision permanent and auditable.

---

## I-03 — A Snapshot Belongs to Exactly One Deal

`snapshot.deal_id` is set at creation time and never changes. A snapshot
cannot be moved between deals. A snapshot cannot belong to zero deals.

---

## I-04 — A Deal Belongs to Exactly One User and One Property

`deal.user_id` and `deal.property_id` are set at creation time and never
change. Ownership cannot be transferred.

---

## I-05 — Configuration Records Are Never Overwritten

When a new effective date for SDLT, Corporation Tax, or Assumptions comes
into effect, a new configuration entity is created. The old entity remains
unchanged and continues to be referenced by historical snapshots. No
`UPDATE` operation is ever performed on any configuration entity.

---

## I-06 — Income Tax Band Is Required for INDIVIDUAL, Forbidden for LIMITED_COMPANY

The combination `(ownership_structure=INDIVIDUAL, income_tax_band=null)`
is a domain invariant violation. The combination `(ownership_structure=LIMITED_COMPANY,
income_tax_band=any)` is also a domain invariant violation.

**Enforcement:** Check constraint on `SnapshotInputs` and `InvestorProfile`.
Engine validation rule V-17.

---

## I-07 — Leasehold Properties Require Lease Details

When `tenure = LEASEHOLD`, `lease_years_remaining` must be provided. A
leasehold property without a declared lease length is not fully described.

**Enforcement:** Check constraint on `properties` table. Validated by the
engine's validation pipeline when calculating.

---

## I-08 — Snapshot Creation Is Atomic

All components of the `CalculationSnapshot` aggregate (root record, inputs,
outputs, intermediates, risk flags, validation warnings) are created
simultaneously in a single database transaction. A partial snapshot is
a data integrity violation.

**Enforcement:** Service layer transaction management. Database FK constraints
ensure referential integrity.

---

## I-09 — The Engine Never Modifies Domain State

The engine receives plain data, returns plain data, and has no side effects.
It does not write to databases, emit events, update caches, or call external
services. This invariant is enforced by the engine module's import rules —
no infrastructure dependencies are permitted in the engine package.

---

## I-10 — AI Outputs Are Read-Only Consumers

AI summaries (Phase 5+) reference snapshots by ID but never modify snapshot
content. The FK direction is always AI → snapshot, never snapshot → AI.
Snapshot records have no knowledge of AI summaries.

---

---

# Part 16 — Mutation Rules

These rules define what may change, when, and under what conditions.

---

```
Entity                      Permitted Mutations
──────────────────────────────────────────────────────────────────────────────
User                        email (sync), display_name, status transition

InvestorProfile             label, ownership_structure, income_tax_band,
                            is_default, is_archived + archived_at

Property                    address fields, epc_rating, bedrooms,
                            is_archived + archived_at
                            IMMUTABLE: tenure, user_id

Deal                        label, status (via transition rules only),
                            latest_snapshot_id (on snapshot creation only),
                            investor_profile_id, all working_inputs fields
                            IMMUTABLE: user_id, property_id, created_at

CalculationSnapshot         is_superseded + superseded_at
                            ALL OTHER FIELDS IMMUTABLE

SnapshotInputs              IMMUTABLE ENTIRELY

SnapshotOutputs             IMMUTABLE ENTIRELY

SnapshotIntermediates       IMMUTABLE ENTIRELY

RiskFlag                    IMMUTABLE ENTIRELY

ValidationWarning           IMMUTABLE ENTIRELY

CalculationAuditEvent       IMMUTABLE ENTIRELY

Any ConfigurationVersion    IMMUTABLE ENTIRELY
```

---

---

# Part 17 — Entity Creation Rules

---

**User:**
Created on first authenticated login. `supabase_auth_id` is the join key.
If a record already exists for the `supabase_auth_id`, the existing record
is returned — creation is idempotent.

**InvestorProfile:**
Created by an authenticated user. The creating user's `user_id` is set at
creation. At most one profile per user may have `is_default = true`.

**Property:**
Created by an authenticated user. The postcode is validated at creation time.
Tenure is set at creation and is not subsequently mutable.

**Deal:**
Created by an authenticated user against an existing property owned by that
user. Created with `status = DRAFT`. Working inputs may be empty at creation.

**CalculationSnapshot:**
Created only by the calculation orchestration flow. Never created directly.
Always created with all sub-entities in the same atomic transaction. The
factory receives a complete `EngineResult` — partial construction is not
permitted.

**ConfigurationVersion:**
Created only by an admin user via the admin service. Always created with
`effective_from` set to the date the new rates/assumptions take effect.
SDLT configuration versions are always created with their complete band set.

**CalculationAuditEvent:**
Created only by the audit service. Created once per calculation attempt,
regardless of outcome.

---

---

# Part 18 — Entity Versioning Expectations

---

## 18.1 — Engine Versioning

The engine version is a semantic string embedded in the engine module as a
constant. When the engine's formula logic changes in a way that produces
different results for the same inputs (a MAJOR version increment), a new
version string is recorded. All subsequent snapshots carry the new version
string. Historical snapshots retain the version string under which they
were calculated.

**Domain implication:** The `engine_version` field on `CalculationSnapshot`
is not merely a string label — it is the key to reproductibility. Given this
version string and the three configuration version IDs, the exact calculation
can be reproduced.

---

## 18.2 — Configuration Versioning

Configuration entities are versioned by `effective_from` date. The active
version for a given calculation date is the most recent version with
`effective_from <= calculation_date`. There is no concept of "current" version
in the domain model — currency is always relative to a date.

---

## 18.3 — Snapshot Versioning

Snapshots are not versioned in the traditional sense — they are immutable
records. When a recalculation is needed, a new snapshot is created. The
previous snapshot is marked as superseded. The full history of snapshots
for a deal is always available.

This is the domain expression of "versioning by append": the history IS
the version history.

---

---

# Part 19 — Future Workflow Integration Boundaries

USER_WORKFLOW_ARCHITECTURE.md defines a 12-stage investment lifecycle.
Stages beyond DRAFT/ANALYSED/ARCHIVED are Phase 2+ additions. This section
defines where and how the domain model accommodates them.

---

## 19.1 — Workflow State Is Always Separate From Calculation State

Future workflow stages (OFFER_SUBMITTED, FINANCING, REFURBISHMENT, etc.)
are additions to the `Deal` aggregate's status vocabulary. They do not affect
any snapshot entity. A deal moving from ANALYSED to OFFER_SUBMITTED transitions
its mutable status — all snapshots remain exactly as they were.

**Implementation path:** `DealStatus` enum gains new values in Phase 2.
`DealStatusTransitionService` gains new permitted transitions. No snapshot
entity is touched.

---

## 19.2 — Workflow Events Are a Separate Entity Family

Phase 2 introduces `DealWorkflowEvent` as an append-only event entity:

```
DealWorkflowEvent (Phase 2+):
    id: UUID
    deal_id: UUID
    event_type: WorkflowEventType
    event_data: dict              (flexible payload per event type)
    recorded_by_user_id: UUID
    recorded_at: datetime
    created_at: datetime
```

This entity family is strictly separate from the snapshot family. Workflow
events are operational records; snapshots are calculation records. They
reference the same deal but neither owns the other.

---

## 19.3 — Refinance Scenarios Generate New Snapshots

When a user models a refinance (Phase 4+), the refinance analysis produces
a new immutable snapshot tagged with a scenario type. The snapshot
aggregate gains nullable `scenario_label` and `scenario_type` fields.
Historical snapshots without scenario labelling have null values for these
fields — the addition is non-breaking.

---

---

# Part 20 — Future Intelligence Integration Boundaries

---

## 20.1 — Intelligence Data Is Never Inside a Snapshot

Area intelligence, EPC data, flood risk, Article 4 overlays, and all external
regulatory data (Phase 3+) are stored in separate `intel_*` entity families.
They are never embedded in snapshot entities.

The point of contact is a nullable reference stored in `SnapshotInputs`
at calculation time:

```
SnapshotInputs (Phase 3+ additions):
    area_intel_record_id: UUID | None
    epc_record_id: UUID | None
    flood_risk_record_id: UUID | None
```

These references are immutable once set (they are part of the snapshot). The
intelligence records they reference are separately mutable and refreshable —
freshness is a property of the intelligence record, not the snapshot.

---

## 20.2 — Investor Profile Intelligence (Phase 2+)

INVESTOR_PROFILE_DIRECTION.md defines future investor strategy profiles with
preferences that influence risk flag interpretation. This affects only the
advisory layer — flag severity thresholds, scenario suggestions, and
workflow recommendations. It does not alter deterministic calculations.

**Domain boundary:** Investor profile preferences may only influence:
- Which risk flags are displayed prominently (presentation priority)
- Which workflow suggestions are surfaced
- Which scenarios are pre-configured for comparison

Investor profile preferences must never alter:
- Formula inputs or outputs
- Snapshot content
- Engine configuration values

The `InvestorProfile` entity is the owner of these future preferences.
They are additive fields — the Phase 1 `InvestorProfile` has no preference
fields, and Phase 2 adds them without requiring schema changes to any
snapshot or calculation entity.

---

## 20.3 — AI Summaries Are a Read-Only Advisory Layer

Phase 5 introduces `AISummary` as a domain entity that references
snapshots but has no authority over them.

```
AISummary (Phase 5+):
    id: UUID
    snapshot_id: UUID    (FK → CalculationSnapshot)
    generated_at: datetime
    model_version: str
    prompt_version: str
    summary_text: str
    summary_type: AISummaryType
    created_at: datetime
```

**Domain invariant:** `AISummary.snapshot_id` references the snapshot.
The snapshot has no knowledge of any `AISummary` that references it.
The FK direction enforces the read-only consumer boundary from ADR-001.

The `AISummary` entity exists in a separate bounded context from the
calculation domain. The two contexts share only the `snapshot_id` as a
reference. Domain services in the calculation context never load or reference
`AISummary` entities.

---

---

# Part 21 — Domain Model Dependency Map

The correct direction of dependency between domain components:

```
Configuration Domain
    ↓ provides EngineConfig to
Engine Contracts (EngineInput, EngineConfig, EngineResult)
    ↑ receives domain data from
Deal Domain (Deal, DealWorkingInputs)
    ↑ associated with
Property Domain (Property)
    ↑ owned by
User Domain (User, InvestorProfile)

Snapshot Domain (CalculationSnapshot and sub-entities)
    ← created from EngineResult by
Calculation Orchestration Service
    ← triggers
Audit Domain (CalculationAuditEvent)

Intelligence Domain (Phase 3+)  — reads → Snapshot Domain
AI Domain (Phase 5+)            — reads → Snapshot Domain
Workflow Domain (Phase 2+)      — annotates → Deal Domain
```

No reverse dependencies. Intelligence, AI, and workflow domains consume
from the core calculation domain. They never modify it.

---

---

# Part 22 — Domain Model Invariants Summary

The following invariants are the domain's non-negotiable rules. Any code
that violates them is incorrect, regardless of what test passes.

```
I-01  Snapshots are immutable after creation (except is_superseded)
I-02  User overrides always prevail over platform defaults
I-03  A snapshot belongs to exactly one deal
I-04  A deal belongs to exactly one user and one property
I-05  Configuration records are never overwritten
I-06  Income tax band is required for INDIVIDUAL, forbidden for LIMITED_COMPANY
I-07  Leasehold properties require lease details
I-08  Snapshot creation is atomic
I-09  The engine never modifies domain state
I-10  AI outputs are read-only consumers of snapshots

Additional:
I-11  Provenance is recorded for every optional input in every snapshot
I-12  Every calculation attempt produces exactly one audit event
I-13  A deal's user_id and property_id are immutable after creation
I-14  Property tenure is immutable after creation
I-15  Configuration effective_from uniqueness: one version per date per domain
I-16  SDLT configuration is only valid with at least one band
I-17  Corporation tax thresholds must be ordered: small < main
I-18  ICR higher-rate threshold >= ICR basic-rate threshold
I-19  Archived entities cannot transition to any other status
I-20  The engine package imports nothing from the application domain
```
