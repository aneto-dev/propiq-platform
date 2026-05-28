# PropIQ Platform — Repository Architecture

## Purpose

This document defines the repository layer for the PropIQ platform. It
specifies how domain entities are loaded from and saved to the database,
the contracts each repository exposes, the rules governing mapping between
domain and persistence models, transaction boundaries, query patterns, and
extension points for future phases.

This document is architecture only. It contains no SQLAlchemy code, no ORM
class definitions, no Alembic migrations, no FastAPI routes, and no
implementation code of any kind.

All terminology matches DOMAIN_GLOSSARY.md.
All domain entities and aggregates are sourced from DOMAIN_MODEL_ARCHITECTURE.md.
All table names and column definitions are sourced from DATABASE_SCHEMA_DESIGN.md.
All persistence principles are sourced from PERSISTENCE_ARCHITECTURE.md.
All service boundaries are sourced from SERVICE_ARCHITECTURE.md.
All trust and mutability rules are sourced from TRUST_MODEL.md and DATA_BOUNDARIES.md.
All architectural decisions trace to DECISIONS.md.

---

## Document Status

Version: 1.0
Phase coverage: Phase 1 complete with Phase 2–5 extension design

---

---

# Part 1 — Repository Philosophy

---

## 1.1 — Repositories Are Infrastructure, Not Domain

Repositories exist at the infrastructure layer. They translate between domain
entities (pure Python objects) and persistence models (database rows). They
answer the question: "given a domain operation, what database operations are
needed, and in what order?"

Repositories do not contain business rules. A repository does not know whether
a user is allowed to see a deal — that is a service-layer concern. A repository
does not know whether a calculation result is correct — that is an engine
concern. A repository knows one thing: how to faithfully persist and reconstitute
domain entities.

---

## 1.2 — Repositories Protect Aggregate Boundaries

The repository is the only place where the boundary between domain and
persistence is crossed. Service layer code calls repository methods and
receives domain entities. Service layer code never constructs domain entities
from raw database rows. Service layer code never calls ORM models directly.

This single crossing point means that changes to the database schema require
changes only in the repository layer — not in the service layer, not in the
domain, and not in the API layer.

---

## 1.3 — The Read–Write Asymmetry

Most repositories in this platform have a fundamental asymmetry: reads are
flexible (different views, different levels of detail, different filters),
but writes are tightly constrained (only certain entities can be written,
only in certain ways, only with certain guarantees).

The most extreme case is the `SnapshotRepository`: it has a single write
operation (`save`) and several read operations of varying scope. The write
is atomic and irreversible. The reads are composable and never modify state.
This asymmetry reflects DATA_BOUNDARIES.md — snapshot data is immutable; reading
it in different ways does not change what it is.

---

## 1.4 — No Repositories for Sub-Aggregate Objects

The aggregate access rule from DOMAIN_MODEL_ARCHITECTURE.md Part 3.1 states
that external code interacts with aggregates only through their root. This has
a direct repository consequence: there are no repositories for sub-aggregate
objects.

There is no `SnapshotInputsRepository`, no `SnapshotOutputsRepository`, no
`RiskFlagRepository`. There is a `SnapshotRepository` whose operations load
and save the complete `CalculationSnapshot` aggregate.

Sub-aggregate objects (`SnapshotInputs`, `SnapshotOutputs`, `SnapshotIntermediates`,
`RiskFlag` list, `ValidationWarning` list) are always loaded and saved as part
of their parent aggregate operation — never independently.

---

## 1.5 — Repositories Are Not CRUD Classes

Repositories are not generic create/read/update/delete wrappers. Each
repository method is named for the domain operation it supports, not the
database operation it performs. `snapshot_repository.save(snapshot)` rather
than `snapshot_repository.insert_all_sub_tables(...)`. `deal_repository.find_by_id_for_user(...)` rather than `deal_repository.select_where_id_equals(...)`.

Named methods make the intent clear. They make the service layer readable
as business logic, not as database orchestration.

---

---

# Part 2 — Repository Responsibilities

One repository per aggregate root. Supporting repositories for standalone
entities that are not aggregate sub-objects.

---

## 2.1 — SnapshotRepository

**Aggregate served:** `CalculationSnapshot`

**Responsibility:** The single point of persistence for the calculation snapshot
aggregate. Saves complete snapshots atomically. Loads snapshots at varying
levels of detail for different use cases.

**Operations:**
- `save(snapshot: CalculationSnapshot) → None`
  Persists the complete aggregate. Atomic. No partial saves.

- `find_by_id(snapshot_id: UUID) → CalculationSnapshot | None`
  Loads full aggregate including inputs, outputs, intermediates, flags, warnings.

- `find_by_id_outputs_only(snapshot_id: UUID) → SnapshotSummary | None`
  Loads only the snapshot root and outputs. Used for deal summary display.
  Does not load intermediates (expensive and not needed for display).

- `find_history_for_deal(deal_id: UUID) → List[SnapshotHistoryEntry]`
  Loads root records only (no sub-entities) ordered by `calculated_at DESC`.
  Used for the snapshot history list view. Never loads intermediates in bulk.

- `mark_superseded(snapshot_id: UUID, superseded_at: datetime) → None`
  Applies the `is_superseded = true` status transition. The only update
  permitted on a snapshot entity.

**What SnapshotRepository does NOT do:**
- Modify any field other than `is_superseded` / `superseded_at`
- Delete any snapshot record
- Load snapshots belonging to a different user (ownership filter applied in
  the service layer before calling the repository)
- Partially construct a snapshot

---

## 2.2 — DealRepository

**Aggregate served:** `Deal`

**Responsibility:** Persists and loads `Deal` aggregates. Manages deal working
inputs and status.

**Operations:**
- `save(deal: Deal) → None`
  Persists a new deal (INSERT). For an existing deal, this is an error —
  updates use dedicated mutation methods.

- `update(deal: Deal) → None`
  Persists mutations to an existing deal (UPDATE working inputs, label,
  status, latest_snapshot_id, investor_profile_id).

- `find_by_id(deal_id: UUID) → Deal | None`
  Loads a single deal with full working inputs.

- `find_by_id_for_user(deal_id: UUID, user_id: UUID) → Deal | None`
  Loads a deal only if it belongs to the specified user. Returns `None`
  if the deal does not exist OR belongs to a different user. This is the
  ownership-aware variant used by all service operations.

- `find_all_for_user(user_id: UUID, status_filter: DealStatus | None, page: PageRequest) → Page[DealSummary]`
  Paginated list of deals for a user. Returns summary projection (no working
  input detail). Optionally filtered by status.

- `find_all_for_property(property_id: UUID, user_id: UUID) → List[DealSummary]`
  All deals against a specific property, ownership-filtered. Not paginated
  (a property is unlikely to have hundreds of deals in Phase 1).

- `count_for_user(user_id: UUID) → int`
  Count of non-archived deals for a user. Used for dashboard summary.

**What DealRepository does NOT do:**
- Trigger calculations
- Load snapshot data (that is SnapshotRepository's job)
- Perform status validation (that is DealStatusTransitionService's job)

---

## 2.3 — PropertyRepository

**Aggregate served:** `Property`

**Responsibility:** Persists and loads `Property` aggregates.

**Operations:**
- `save(property: Property) → None`
  Persists a new property (INSERT).

- `update(property: Property) → None`
  Persists mutable field updates (address, epc_rating, bedrooms,
  is_archived / archived_at).

- `find_by_id(property_id: UUID) → Property | None`
  Loads a single property.

- `find_by_id_for_user(property_id: UUID, user_id: UUID) → Property | None`
  Ownership-aware load. Returns `None` if not found or not owned.

- `find_all_for_user(user_id: UUID, include_archived: bool, page: PageRequest) → Page[Property]`
  Paginated list. Optionally includes archived properties.

**What PropertyRepository does NOT do:**
- Load deals for the property (that is DealRepository's job)
- Validate postcode format (that is the domain entity's job)
- Allow tenure mutation (schema constraint prevents this; the repository
  should not expose a field-level update that the schema cannot enforce)

---

## 2.4 — UserRepository

**Aggregate served:** `User`

**Responsibility:** Manages user platform records. Thin layer — most user
identity is managed by Supabase Auth.

**Operations:**
- `save(user: User) → None`
  Creates a new user platform record on first login.

- `update(user: User) → None`
  Persists mutable updates (display_name, status).

- `find_by_id(user_id: UUID) → User | None`

- `find_by_supabase_auth_id(supabase_auth_id: UUID) → User | None`
  Primary lookup used on every authenticated request.

- `find_by_email(email: str) → User | None`
  Used for admin operations. Not exposed in standard user flows.

**What UserRepository does NOT do:**
- Manage passwords or tokens (Supabase Auth handles that)
- Load deals, properties, or snapshots

---

## 2.5 — InvestorProfileRepository

**Entity served:** `InvestorProfile` (standalone entity, not a sub-aggregate)

**Responsibility:** Persists and loads investor profiles for a user.

**Operations:**
- `save(profile: InvestorProfile) → None`
  Creates a new investor profile.

- `update(profile: InvestorProfile) → None`
  Persists mutable updates (label, ownership_structure, income_tax_band,
  is_default, is_archived / archived_at).

- `find_by_id(profile_id: UUID) → InvestorProfile | None`

- `find_by_id_for_user(profile_id: UUID, user_id: UUID) → InvestorProfile | None`
  Ownership-aware load.

- `find_all_for_user(user_id: UUID, include_archived: bool) → List[InvestorProfile]`
  Not paginated. A user is unlikely to have more than a small number of profiles.

- `find_default_for_user(user_id: UUID) → InvestorProfile | None`
  Returns the profile with `is_default = true` for the user, if one exists.

---

## 2.6 — ConfigurationRepository

**Aggregates served:** `SDLTConfiguration`, `CorporationTaxConfiguration`,
`AssumptionConfiguration`, `EngineVersionRecord`

**Responsibility:** The read-focused interface to versioned configuration. All
reads. Admin-only writes for new configuration versions.

**Operations — reads (used on every calculation):**
- `find_active_sdlt_config(as_of_date: date) → SDLTConfiguration`
  Returns the most recent `SDLTConfiguration` with `effective_from <= as_of_date`.
  Raises `ConfigurationNotFoundError` if no configuration exists for the date.

- `find_active_corporation_tax_config(as_of_date: date) → CorporationTaxConfiguration`

- `find_active_assumption_config(as_of_date: date) → AssumptionConfiguration`

**Operations — reads by specific version ID (used for snapshot reproduction):**
- `find_sdlt_config_by_id(version_id: UUID) → SDLTConfiguration`
- `find_corporation_tax_config_by_id(version_id: UUID) → CorporationTaxConfiguration`
- `find_assumption_config_by_id(version_id: UUID) → AssumptionConfiguration`

These three operations are the foundation of historical reproducibility. Given
the version IDs stored in a snapshot, the exact configuration can be retrieved.

**Operations — admin writes (INSERT only, append-only):**
- `save_sdlt_config(config: SDLTConfiguration) → None`
  Inserts root record and all band records atomically.
- `save_corporation_tax_config(config: CorporationTaxConfiguration) → None`
- `save_assumption_config(config: AssumptionConfiguration) → None`
- `save_engine_version(version: EngineVersionRecord) → None`

**Operations — version listing (admin and transparency views):**
- `find_all_sdlt_config_versions() → List[SDLTConfigurationSummary]`
- `find_all_corporation_tax_config_versions() → List[CorporationTaxConfigSummary]`
- `find_all_assumption_config_versions() → List[AssumptionConfigSummary]`
- `find_all_engine_versions() → List[EngineVersionRecord]`

**What ConfigurationRepository does NOT do:**
- Update any configuration record
- Delete any configuration record
- Interpolate between versions (the service layer selects the correct version
  using `as_of_date`; the repository returns exactly what the database holds)

---

## 2.7 — AuditRepository

**Entity served:** `CalculationAuditEvent`

**Responsibility:** Append-only write of calculation audit events. Read
access for audit review.

**Operations:**
- `save(event: CalculationAuditEvent) → None`
  Inserts one audit event. The only write operation.

- `find_history_for_deal(deal_id: UUID, page: PageRequest) → Page[CalculationAuditEvent]`
  Paginated calculation history for a deal, ordered `triggered_at DESC`.

- `find_history_for_user(user_id: UUID, page: PageRequest) → Page[CalculationAuditEvent]`
  Paginated calculation history for a user (all deals), ordered `triggered_at DESC`.

**What AuditRepository does NOT do:**
- Update or delete any audit event
- Return audit events for a different user without explicit user scope

---

---

# Part 3 — Repository Boundaries

---

## 3.1 — Services Call Repositories; Repositories Do Not Call Services

```
Service layer
    ↓ calls
Repository interfaces
    ↓ calls
Persistence models (SQLAlchemy)
    ↓ calls
PostgreSQL
```

This is strictly one-directional. No repository calls a service. No
repository calls the engine. No repository generates UUIDs or timestamps
for domain entities — those come from the service layer.

---

## 3.2 — Repositories Do Not Call Each Other

`DealRepository` does not call `SnapshotRepository`. If a service needs
both a deal and a snapshot, it calls both repositories independently and
assembles the result. Repositories that depend on each other create hidden
coupling and make the persistence layer difficult to test.

The one exception is within the `SnapshotRepository.save()` operation, which
internally orchestrates writes to multiple database tables (snapshot_calculations,
snapshot_inputs, snapshot_outputs, snapshot_intermediates, snapshot_risk_flags,
snapshot_validation_warnings, and the deal pointer update). This orchestration
is explicitly part of the snapshot save contract — not inter-repository coupling.

---

## 3.3 — Repositories Receive and Return Domain Entities

Repository method signatures use domain types:

```
Correct:
  find_by_id(deal_id: UUID) → Deal | None
  save(snapshot: CalculationSnapshot) → None

Incorrect:
  find_by_id(deal_id: UUID) → DealORM          ← ORM model leaked
  save(snapshot_data: dict) → None              ← untyped
  save(snapshot_row: SnapshotRow) → None        ← persistence model leaked
```

The domain entity is the unit of exchange between the service layer and
the repository layer. ORM models are an internal implementation detail of
the repository, never visible to the service layer.

---

## 3.4 — Repositories Do Not Perform Ownership Checks

Ownership verification (ensuring a user can only access their own data)
is a domain service responsibility, not a repository responsibility. However,
all repository operations that load single entities by ID have an
ownership-aware variant (e.g. `find_by_id_for_user`) that filters by
`user_id` as part of the query. This is a query filter, not a business rule.

The difference:
- `find_by_id(deal_id)` — pure data lookup; may return a deal belonging to
  any user; used internally within transactions where ownership is already
  verified by context
- `find_by_id_for_user(deal_id, user_id)` — query-level ownership filter;
  used in service operations that receive external input

Service layer uses the `_for_user` variants. Internal operations (e.g. the
snapshot service updating `latest_snapshot_id` during a known-user-owned
transaction) may use the non-ownership-filtered variant when ownership is
already established.

---

---

# Part 4 — Domain Entity ↔ Persistence Model Mapping Rules

---

## 4.1 — Mapping Is Bidirectional and Explicit

Every repository that reads from the database performs an explicit mapping
from persistence model (SQLAlchemy row) to domain entity. Every write
performs an explicit mapping from domain entity to persistence model.

These mappings are defined as private methods (or static functions) within
the repository implementation class. They are named consistently:

```
_to_domain(row: ORM_Model) → DomainEntity
_to_persistence(entity: DomainEntity) → dict  (values for INSERT/UPDATE)
```

---

## 4.2 — Value Objects Are Constructed During Mapping

When a persistence model is mapped to a domain entity, value objects are
constructed at that point. The mapper constructs `PropertyAddress` from
address columns, `DealWorkingInputs` from working input columns, `Money`
from numeric columns, `Rate` from percentage columns.

Primitive types (strings, integers, booleans) do not exist in service layer
code as raw database values — they are wrapped in their domain value objects
during the mapping.

---

## 4.3 — Decimal Precision Is Preserved in Mapping

All `NUMERIC(15,6)` and `NUMERIC(10,6)` database values are mapped to
Python `Decimal` objects, never to `float`. The mapping layer is responsible
for ensuring that Decimal precision is not silently downgraded to float
during the persistence-to-domain translation.

SQLAlchemy returns `Decimal` objects for `NUMERIC` columns when configured
correctly. The mapping layer must verify this configuration is active and
never accept `float` from the ORM.

---

## 4.4 — Enum Mapping

Database enum values (stored as PostgreSQL custom enum types) are mapped to
Python enum members during domain entity construction. The mapping is by
exact string value. If a database value does not match any Python enum member,
the mapping raises a `PersistenceIntegrityError` — not a Python `ValueError`
propagated to the API layer.

New enum values added in future phases require:
1. A database migration to extend the PostgreSQL enum type
2. A Python enum extension
3. A mapping update
None of these require changes to the service layer or domain layer.

---

## 4.5 — UUID Handling

Database UUID columns map to Python `uuid.UUID` objects. String representations
of UUIDs are never used as identifiers in domain entity code. The mapping layer
performs the string-to-UUID or UUID-to-string conversion at the boundary.

---

## 4.6 — Snapshot Aggregate Mapping

The `CalculationSnapshot` aggregate spans six database tables. Its mapping
is more complex than single-table entities. The mapping rules:

**Loading (database → domain):**
1. Load `snapshot_calculations` root row
2. Load `snapshot_inputs` row (JOIN or separate query; see Part 7)
3. Load `snapshot_outputs` row
4. Load `snapshot_intermediates` row (only for full aggregate load)
5. Load all `snapshot_risk_flags` rows for the snapshot
6. Load all `snapshot_validation_warnings` rows for the snapshot
7. Reconstruct the JSONB `sdlt_band_breakdown` from the intermediates row
   into `List[SDLTBandResult]`
8. Construct `ConfigVersionRefs` from the three version ID columns on the root
9. Assemble the `CalculationSnapshot` aggregate from all sub-objects

**Saving (domain → database):**
1. Extract all fields from the `CalculationSnapshot` root
2. Insert `snapshot_calculations` row
3. Extract all fields from `SnapshotInputs`, including all `_source` values
4. Insert `snapshot_inputs` row
5. Insert `snapshot_outputs` row
6. Serialise `sdlt_band_breakdown` list to JSONB; insert `snapshot_intermediates` row
7. Insert one `snapshot_risk_flags` row per `RiskFlag`
8. Insert one `snapshot_validation_warnings` row per `ValidationWarning`
9. UPDATE `deals.latest_snapshot_id`
10. Insert `audit_calculations` row
All ten operations are within a single database transaction (see Part 10).

---

---

# Part 5 — Repository Interfaces

Repository interfaces define the contract that service-layer code depends on.
Implementation classes satisfy this contract using SQLAlchemy. Alternative
implementations (e.g. in-memory for testing) also satisfy this contract.

This is the explicit interface design that separates domain logic from
persistence infrastructure.

---

## 5.1 — ISnapshotRepository

```
interface ISnapshotRepository:

    save(snapshot: CalculationSnapshot) → None
        Atomically persists the complete snapshot aggregate plus the deal
        pointer update and audit event.
        Raises: SnapshotPersistenceError on failure.
        Guarantee: Either all sub-tables are written or none are.

    find_by_id(snapshot_id: UUID) → CalculationSnapshot | None
        Loads full aggregate including intermediates.
        Returns None if not found.

    find_by_id_outputs_only(snapshot_id: UUID) → SnapshotSummary | None
        Loads root + outputs only. No intermediates.
        Returns None if not found.

    find_history_for_deal(deal_id: UUID) → List[SnapshotHistoryEntry]
        Loads root records only, ordered by calculated_at DESC.
        Never paginates (deal snapshot history is bounded in practice).

    mark_superseded(snapshot_id: UUID, superseded_at: datetime) → None
        Sets is_superseded = true and superseded_at on the specified record.
        Raises: SnapshotNotFoundError if snapshot_id does not exist.
```

**SnapshotSummary (projection type, not a full domain entity):**
```
SnapshotSummary:
    id: UUID
    deal_id: UUID
    engine_version: str
    calculated_at: datetime
    is_superseded: bool
    outputs: SnapshotOutputs
    risk_flags: List[RiskFlag]
    validation_warnings: List[ValidationWarning]
    config_version_refs: ConfigVersionRefs
```

Note: `SnapshotSummary` is a read projection for display purposes. It does
not include intermediates or inputs. It is not the full `CalculationSnapshot`
aggregate.

**SnapshotHistoryEntry (minimal projection for list view):**
```
SnapshotHistoryEntry:
    id: UUID
    deal_id: UUID
    engine_version: str
    calculated_at: datetime
    is_superseded: bool
    risk_flag_count_high: int
    risk_flag_count_medium: int
    risk_flag_count_info: int
    annual_cash_flow_gbp: Decimal   (from outputs — key metric for list display)
    gross_yield_percent: Decimal
```

---

## 5.2 — IDealRepository

```
interface IDealRepository:

    save(deal: Deal) → None
        Inserts a new deal. Raises: DealAlreadyExistsError if id already present.

    update(deal: Deal) → None
        Updates mutable fields of an existing deal.
        Raises: DealNotFoundError if id not present.
        Never updates user_id, property_id, or created_at.

    find_by_id(deal_id: UUID) → Deal | None

    find_by_id_for_user(deal_id: UUID, user_id: UUID) → Deal | None
        Returns None if deal does not exist OR belongs to a different user.

    find_all_for_user(
        user_id: UUID,
        status_filter: DealStatus | None,
        page: PageRequest
    ) → Page[DealSummary]

    find_all_for_property(property_id: UUID, user_id: UUID) → List[DealSummary]

    count_for_user(user_id: UUID) → int
```

**DealSummary (projection type):**
```
DealSummary:
    id: UUID
    label: str
    status: DealStatus
    property_id: UUID
    latest_snapshot_id: UUID | None
    created_at: datetime
    updated_at: datetime
    latest_snapshot_cash_flow_gbp: Decimal | None    (joined from snapshot_outputs if present)
    latest_snapshot_gross_yield: Decimal | None
    latest_snapshot_calculated_at: datetime | None
    latest_snapshot_risk_flag_count_high: int | None
```

The `latest_snapshot_*` fields in `DealSummary` are populated via a JOIN
to `snapshot_outputs` using `deals.latest_snapshot_id`. They are nullable
because a DRAFT deal has no snapshot yet. This JOIN is efficient because
`deals.latest_snapshot_id` is indexed.

---

## 5.3 — IPropertyRepository

```
interface IPropertyRepository:

    save(property: Property) → None

    update(property: Property) → None
        Never updates user_id, tenure, or created_at.

    find_by_id(property_id: UUID) → Property | None

    find_by_id_for_user(property_id: UUID, user_id: UUID) → Property | None

    find_all_for_user(
        user_id: UUID,
        include_archived: bool,
        page: PageRequest
    ) → Page[Property]
```

---

## 5.4 — IUserRepository

```
interface IUserRepository:

    save(user: User) → None
        Idempotent: if a user with the same supabase_auth_id already exists,
        returns without error rather than creating a duplicate.

    update(user: User) → None

    find_by_id(user_id: UUID) → User | None

    find_by_supabase_auth_id(supabase_auth_id: UUID) → User | None

    find_by_email(email: str) → User | None
```

---

## 5.5 — IInvestorProfileRepository

```
interface IInvestorProfileRepository:

    save(profile: InvestorProfile) → None

    update(profile: InvestorProfile) → None

    find_by_id(profile_id: UUID) → InvestorProfile | None

    find_by_id_for_user(profile_id: UUID, user_id: UUID) → InvestorProfile | None

    find_all_for_user(user_id: UUID, include_archived: bool) → List[InvestorProfile]

    find_default_for_user(user_id: UUID) → InvestorProfile | None
```

---

## 5.6 — IConfigurationRepository

```
interface IConfigurationRepository:

    # Active version reads (used on every calculation)
    find_active_sdlt_config(as_of_date: date) → SDLTConfiguration
    find_active_corporation_tax_config(as_of_date: date) → CorporationTaxConfiguration
    find_active_assumption_config(as_of_date: date) → AssumptionConfiguration

    # Specific version reads (used for snapshot reproduction)
    find_sdlt_config_by_id(version_id: UUID) → SDLTConfiguration
    find_corporation_tax_config_by_id(version_id: UUID) → CorporationTaxConfiguration
    find_assumption_config_by_id(version_id: UUID) → AssumptionConfiguration

    # Admin writes (append-only)
    save_sdlt_config(config: SDLTConfiguration) → None
    save_corporation_tax_config(config: CorporationTaxConfiguration) → None
    save_assumption_config(config: AssumptionConfiguration) → None
    save_engine_version(version: EngineVersionRecord) → None

    # Version listing
    find_all_sdlt_config_versions() → List[SDLTConfigurationSummary]
    find_all_corporation_tax_config_versions() → List[CorporationTaxConfigSummary]
    find_all_assumption_config_versions() → List[AssumptionConfigSummary]
    find_all_engine_versions() → List[EngineVersionRecord]
```

---

## 5.7 — IAuditRepository

```
interface IAuditRepository:

    save(event: CalculationAuditEvent) → None

    find_history_for_deal(
        deal_id: UUID,
        page: PageRequest
    ) → Page[CalculationAuditEvent]

    find_history_for_user(
        user_id: UUID,
        page: PageRequest
    ) → Page[CalculationAuditEvent]
```

---

---

# Part 6 — Aggregate Loading Rules

Different service operations require different levels of detail from an
aggregate. Loading unnecessary data wastes resources; under-loading loses
information. The repository exposes different load strategies for different
contexts.

---

## 6.1 — Loading Levels Defined

```
SUMMARY       — root record only, plus key scalar fields from sub-tables via JOIN
                Used for: list views, dashboard counts
                Tables joined: snapshot_calculations + snapshot_outputs (key fields)

DISPLAY       — root + outputs + risk_flags + validation_warnings
                Does NOT include intermediates
                Used for: deal summary display, snapshot detail page
                Tables loaded: 4 of 6 snapshot tables

FULL          — all sub-entities including intermediates
                Used for: reproducibility verification, audit display, future explainability
                Tables loaded: all 6 snapshot tables

INPUTS_ONLY   — root + inputs only
                Used for: recalculation (reconstructing EngineInput from a historical snapshot)
                Tables loaded: 2 of 6 snapshot tables
```

---

## 6.2 — Loading Level vs Method Name Mapping

```
ISnapshotRepository.find_history_for_deal       → SUMMARY loading
ISnapshotRepository.find_by_id_outputs_only     → DISPLAY loading
ISnapshotRepository.find_by_id                  → FULL loading
```

There is no implicit "lazy loading". Each method loads exactly what its name
implies. Service code that needs intermediates explicitly calls `find_by_id`.
Service code that needs only outputs for display calls `find_by_id_outputs_only`.

This design avoids the N+1 query problem and ensures that service code is
explicit about how much data it needs — preventing accidental loading of
expensive data in high-frequency paths.

---

## 6.3 — Aggregate Loading Is Always Consistent

When a `CalculationSnapshot` is loaded, all its sub-entities must be from
the same database row set — not a mix of cached and fresh data. No partial
loading of an aggregate is permitted. If a load operation starts but cannot
complete (e.g. `snapshot_inputs` row is missing for a snapshot that should
have one), this is a data integrity error to be raised, not silently returned
as a partial object.

An integrity violation in snapshot sub-tables indicates a failed transaction
that should never have happened given the atomic write guarantee. It must be
raised as a `SnapshotIntegrityError`, not ignored.

---

---

# Part 7 — Snapshot Loading Strategy

---

## 7.1 — Sub-Table Loading Approach: Separate Queries, Not JOINs

For full aggregate loading, the snapshot repository loads sub-tables in
separate queries rather than a single massive JOIN. The reasons:

**Clarity:** A JOIN across six tables produces a wide, repetitive result set.
The repetition of the root columns for every risk_flag row is wasteful and
complicates mapping.

**Predictability:** Separate queries produce predictable row counts. A JOIN
can produce unexpected row multiplication if cardinality is not carefully
managed.

**Risk flags and warnings are lists:** The risk_flags and validation_warnings
sub-tables are one-to-many. Joining them with one-to-one tables produces
Cartesian complexity. Separate queries load each list cleanly.

The loading sequence for a full `CalculationSnapshot`:

```
1. SELECT * FROM snapshot_calculations WHERE id = :snapshot_id
2. SELECT * FROM snapshot_inputs WHERE snapshot_id = :snapshot_id
3. SELECT * FROM snapshot_outputs WHERE snapshot_id = :snapshot_id
4. SELECT * FROM snapshot_intermediates WHERE snapshot_id = :snapshot_id
5. SELECT * FROM snapshot_risk_flags WHERE snapshot_id = :snapshot_id ORDER BY severity, flag_code
6. SELECT * FROM snapshot_validation_warnings WHERE snapshot_id = :snapshot_id ORDER BY rule_code
```

Six queries. All use the indexed `snapshot_id` column. All fast.

---

## 7.2 — DISPLAY Loading Uses a JOIN for Efficiency

For the display-level load (root + outputs + flags + warnings), a different
strategy applies. Outputs are one-to-one with the root, so a JOIN is efficient:

```
SELECT sc.*, so.*
FROM snapshot_calculations sc
JOIN snapshot_outputs so ON so.snapshot_id = sc.id
WHERE sc.id = :snapshot_id
```

Then two additional queries for flags and warnings (one-to-many, loaded
separately as in full loading).

For `find_by_id_outputs_only`, this is three queries total.

---

## 7.3 — List Loading Uses a Single Aggregating Query

For `find_history_for_deal`, the repository loads root records only and
computes risk flag counts via a subquery or GROUP BY:

```
SELECT
    sc.id,
    sc.engine_version,
    sc.calculated_at,
    sc.is_superseded,
    so.annual_cash_flow_gbp,
    so.gross_yield_percent,
    COUNT(CASE WHEN srf.severity = 'HIGH' THEN 1 END) AS risk_flag_count_high,
    COUNT(CASE WHEN srf.severity = 'MEDIUM' THEN 1 END) AS risk_flag_count_medium,
    COUNT(CASE WHEN srf.severity = 'INFO' THEN 1 END) AS risk_flag_count_info
FROM snapshot_calculations sc
LEFT JOIN snapshot_outputs so ON so.snapshot_id = sc.id
LEFT JOIN snapshot_risk_flags srf ON srf.snapshot_id = sc.id
WHERE sc.deal_id = :deal_id
GROUP BY sc.id, so.annual_cash_flow_gbp, so.gross_yield_percent
ORDER BY sc.calculated_at DESC
```

One query, not N+1.

---

## 7.4 — Intermediates Are Never Loaded in Bulk Operations

`snapshot_intermediates` is never loaded in list queries, summary projections,
or display-level loads. It is loaded only when explicitly requested via
`find_by_id` (full aggregate loading). This is a deliberate performance
decision: intermediates are the largest sub-table (many columns) and are
only needed for audit, reproducibility verification, and future explainability
features. Loading them on every snapshot display would be wasteful.

---

---

# Part 8 — Configuration Loading Strategy

---

## 8.1 — Active Version Resolution

The active configuration version for a given date is resolved using the
pattern:

```
SELECT * FROM config_[name]_versions
WHERE effective_from <= :as_of_date
ORDER BY effective_from DESC
LIMIT 1
```

This query runs three times per calculation (once per configuration table).
The result is small (one row per query). The `effective_from DESC` index on
each configuration table makes this fast regardless of how many historical
versions exist.

---

## 8.2 — SDLT Bands Are Loaded With Their Parent Version

When a `SDLTConfiguration` is loaded, its bands are always loaded in the
same operation:

```
SELECT * FROM config_sdlt_versions WHERE id = :version_id
SELECT * FROM config_sdlt_bands WHERE sdlt_version_id = :version_id ORDER BY band_order
```

Two queries, always together. An `SDLTConfiguration` without bands is an
invalid domain entity. The repository raises `ConfigurationIntegrityError`
if a version record exists with no associated band records.

---

## 8.3 — Configuration Versions Are Immutable After Loading

Once a configuration version is loaded and translated to a domain entity,
it is treated as immutable in memory for the duration of the request. There
is no re-loading mechanism within a request. The `ConfigurationResolutionService`
calls the repository once per calculation, assembles the `ConfigBundle`, and
passes it to the calculation orchestration service. The repository is not
called again for the same configuration within that request.

---

## 8.4 — No Configuration Caching in Phase 1

Per-request memory holding is acceptable and required (load once per request,
use multiple times). Cross-request process-level caching of configuration
is not implemented in Phase 1.

Rationale: Configuration tables are append-only and rarely change. However,
when a new configuration version is inserted (a Budget change), calculations
must immediately pick up the new version. A process-level cache would need
an invalidation mechanism that adds complexity. In Phase 1, the simplicity of
always reading from the database on each request is correct.

Phase 2 may introduce a short-lived cache (e.g. 60-second TTL) if configuration
loading becomes measurably significant in load testing. This is a performance
optimisation that can be added to the repository implementation without changing
the interface.

---

## 8.5 — Configuration Writes Are Admin-Only

`IConfigurationRepository.save_*` methods are called exclusively from the
admin service layer. They must not be accessible through any user-facing
code path. The implementation enforces this via the service layer's admin
authentication check (SERVICE_ARCHITECTURE.md Part 6), not at the repository
level — repositories do not perform authentication.

---

---

# Part 9 — Ownership Verification Strategy

---

## 9.1 — Two-Method Pattern

Every repository for user-owned entities exposes two load variants:

```
find_by_id(entity_id: UUID) → Entity | None
find_by_id_for_user(entity_id: UUID, user_id: UUID) → Entity | None
```

`find_by_id` — no ownership filter. Used in internal operations within the
service layer where ownership has already been established by context (e.g.
the snapshot service updating `latest_snapshot_id` during a transaction that
was initiated after ownership was verified on the deal).

`find_by_id_for_user` — adds `AND user_id = :user_id` to the WHERE clause.
Returns `None` if the entity does not exist OR belongs to a different user.
Used in any service operation that accepts external user input.

**Critical rule:** The `find_by_id_for_user` variant must return `None` in
both cases (not found, and found-but-wrong-user). It must not return different
errors for "does not exist" vs "exists but not yours." The calling service
layer converts `None` to `NotFoundError` — not `ForbiddenError`. This
prevents existence disclosure to unauthorised callers.

---

## 9.2 — Snapshot Ownership Is Indirect

`CalculationSnapshot` records do not have a direct user-ownership filter in
most loading paths. Snapshot access is always mediated through the deal:
a user who can access a deal can access that deal's snapshots.

The one exception is `snapshot_calculations.user_id`, which is stored
for audit purposes. Cross-user snapshot queries in the audit domain
are admin-only and not exposed through the user-facing API.

---

## 9.3 — Configuration Is Not User-Owned

Configuration entities are not user-owned. They are platform-level resources
accessible by all authenticated users (for reading) and by admin users only
(for writing). Configuration loading methods have no ownership parameter.

---

---

# Part 10 — Transaction Boundaries

---

## 10.1 — Transaction Scope Belongs to the Service Layer

The repository layer performs database operations. The service layer defines
which operations must be atomic. Transaction boundaries are therefore a
service-layer concern, with the repository layer participating.

The mechanism: the service layer opens a database session (unit of work),
passes it to repository operations, and commits or rolls back at the service
level. Repositories receive the session as a dependency; they do not open
their own sessions.

This means a service that calls two repositories within the same transaction
can guarantee atomicity across both.

---

## 10.2 — The Snapshot Creation Transaction

The most critical transaction in the system. This transaction is defined in
SERVICE_ARCHITECTURE.md Part 4 and PERSISTENCE_ARCHITECTURE.md Part 11.1.
The repository layer implements it as described here.

```
Within a single database session / transaction:

1. SnapshotRepository.save(snapshot)
   — Inserts: snapshot_calculations
   — Inserts: snapshot_inputs
   — Inserts: snapshot_outputs
   — Inserts: snapshot_intermediates
   — Inserts: all snapshot_risk_flags rows
   — Inserts: all snapshot_validation_warnings rows
   — Updates: deals.latest_snapshot_id

2. AuditRepository.save(audit_event)
   — Inserts: audit_calculations (SUCCESS outcome)

COMMIT (all or nothing)
```

If any step fails, the entire transaction rolls back. No partial snapshot
state exists in the database.

**Important:** The `DealRepository.update()` call to set `latest_snapshot_id`
is embedded within the `SnapshotRepository.save()` operation for the snapshot
creation case. It is NOT a separate service-layer call that happens to be in
the same transaction. This is an intentional design: the snapshot save and
the deal pointer update are inseparable — the repository encapsulates both
as part of the snapshot save contract.

---

## 10.3 — Validation Failure Audit Transaction

When the engine returns a `ValidationResult` with `is_valid = false`:

```
Within a single database session / transaction:
1. AuditRepository.save(audit_event with outcome=VALIDATION_FAILURE)
COMMIT
```

This is independent of any snapshot transaction. No snapshot exists for a
validation failure.

---

## 10.4 — Configuration Insert Transaction (SDLT only)

SDLT configuration inserts must be atomic across the root version record
and all band records:

```
Within a single database session / transaction:
1. ConfigurationRepository.save_sdlt_config(config)
   — Inserts: config_sdlt_versions (root)
   — Inserts: all config_sdlt_bands rows for this version
COMMIT
```

Other configuration tables (Corporation Tax, Assumptions) are single-table
inserts and do not require multi-table transaction management.

---

## 10.5 — Property + Deal Creation Transaction

When a new property and deal are created together:

```
Within a single database session / transaction:
1. PropertyRepository.save(property)
2. DealRepository.save(deal)  — references property.id
COMMIT
```

If the deal save fails, the property save rolls back. A property without
at least one deal is technically allowed by the schema but the UX creates
both together.

---

## 10.6 — Standalone Mutations

Mutations to individual mutable entities (updating deal working inputs,
archiving a deal, updating a property address, updating a user's display
name) are single-table UPDATE operations. They do not require explicit
transaction management beyond the implicit single-statement transaction
that PostgreSQL applies.

---

---

# Part 11 — Concurrency Expectations

---

## 11.1 — Snapshot Writes: Non-Contending

Snapshot inserts are pure INSERTs on append-only tables. Multiple concurrent
calculations by different users produce no contention. Multiple concurrent
calculations by the same user on different deals produce no contention.
Multiple concurrent calculations by the same user on the same deal will
contend only on the `deals.latest_snapshot_id` UPDATE — last write wins,
which is acceptable (both snapshots are preserved).

---

## 11.2 — Configuration Reads: Non-Contending

Configuration tables are append-only. SELECT operations never contend with
other SELECTs or with the rare configuration INSERT. No locking is needed
for configuration reads.

---

## 11.3 — Deal Working Input Updates: Single-User in Phase 1

In Phase 1, deals are user-owned with no multi-user collaboration. A user
editing their own deal working inputs is the only expected concurrent writer.
No locking strategy is needed for Phase 1 deal updates.

Phase 2 introduces team accounts, which may have multiple users editing the
same deal. At that point, optimistic locking on `deals.updated_at` is the
appropriate strategy (see Part 12).

---

---

# Part 12 — Optimistic vs Pessimistic Locking Decisions

---

## 12.1 — Phase 1: No Explicit Locking

Phase 1 applies no explicit row-level locking anywhere. The rationale:
- Snapshot tables are append-only. No update conflicts possible.
- Configuration tables are append-only. No update conflicts possible.
- Deals, properties, and profiles are user-owned. Single user per resource
  in Phase 1. No concurrent edit conflict is expected.

Last-write-wins on the rare case of concurrent deal updates (e.g. two browser
tabs editing the same deal) is acceptable. The deal working inputs are a
scratchpad — losing one update in a concurrent edit race is annoying but not
a financial integrity concern.

---

## 12.2 — Phase 2+: Optimistic Locking for Collaborative Deals

When team accounts are introduced (Phase 2), multiple users may edit the same
deal concurrently. At that point:

**Mechanism:** `deals.updated_at` is used as the optimistic lock token.

**Protocol:**
1. Client loads deal, receives current `updated_at` timestamp.
2. Client submits update including the `updated_at` value they received.
3. Repository executes: `UPDATE deals SET ... WHERE id = :id AND updated_at = :client_updated_at`
4. If `rowcount = 0`: another writer has modified the deal since the client
   loaded it. Return `DealConcurrencyConflictError`.
5. If `rowcount = 1`: update succeeded.

**What this does NOT protect:** Snapshot creation atomicity. Snapshot writes
are INSERT-only and do not conflict with deal working input updates.

---

## 12.3 — No Pessimistic Locking

Pessimistic locking (`SELECT FOR UPDATE`) is not used anywhere in Phase 1
or Phase 2. The reasoning:
- Snapshot writes are non-contending INSERTs.
- Configuration writes are rare admin operations.
- Optimistic locking is sufficient for deal working input updates in Phase 2.
- Pessimistic locking in a web application creates lock-holding under network
  latency, which is a deadlock risk.

---

---

# Part 13 — Unit of Work Rules

---

## 13.1 — One Session Per Request

The database session is opened at the start of each HTTP request and closed
(committed or rolled back) at the end. The session is injected into the service
layer via FastAPI's dependency injection. Services pass the session to
repositories as a parameter.

One request = one session. No session sharing across requests. No long-lived
sessions.

---

## 13.2 — Session Lifetime Is Not the Repository's Concern

The repository does not open or close sessions. It receives a session as a
dependency and uses it for its operations. The service layer (via the request
lifecycle) is responsible for session management.

This means the repository does not call `session.commit()` or `session.rollback()`
for standalone operations. The service layer decides when to commit. For
complex transactions (snapshot creation), the service layer's transaction
context wraps the repository calls.

The exception: the `AuditRepository.save()` for failure outcomes (VALIDATION_FAILURE,
ENGINE_ERROR) may be called after a transaction has already failed or been
rolled back. In this case, the audit write uses a fresh session rather than
the failed session. The repository interface accepts an optional parameter
indicating whether to use the current session or a new one.

---

## 13.3 — Async Sessions

FastAPI is an async framework. Repository implementations use `AsyncSession`
(SQLAlchemy async). All repository methods are `async def`. All queries
use `await session.execute(...)`.

The use of async sessions means:
- No blocking database calls in the request path
- Concurrent requests use cooperative multitasking during I/O waits
- The session isolation described in Part 13.1 applies per async task

---

---

# Part 14 — Repository Query Rules

---

## 14.1 — Queries Are Named for Their Domain Intent

Repository queries are named for what they retrieve, not how they retrieve it.
`find_active_sdlt_config` not `select_config_where_effective_from_lte`.

---

## 14.2 — No Raw SQL in Repository Methods

Repository implementations use SQLAlchemy ORM query construction or Core
expressions. Raw SQL strings are not used in any repository method except
in specifically justified cases (e.g. a PostGIS spatial query in Phase 3
that cannot be expressed with standard ORM). Any raw SQL must be parameterised —
never formatted with string interpolation.

---

## 14.3 — No Unbounded Queries

Every query that returns a list of records is either bounded by a foreign key
(e.g. all flags for a snapshot — bounded by snapshot existence), paginated
(e.g. all deals for a user), or explicitly documented as small-bounded (e.g.
all investor profiles for a user — typically fewer than five).

A query that could return an unbounded number of records without pagination
is a reliability risk and must not exist in the repository layer.

---

## 14.4 — Sorted Results Are Always Explicitly Ordered

Queries that return ordered results always include an `ORDER BY` clause. No
repository method relies on "natural" database ordering, which is undefined
in PostgreSQL and changes with physical table organisation.

Standard orderings:
- Snapshot history: `ORDER BY calculated_at DESC`
- Deal list: `ORDER BY updated_at DESC`
- Property list: `ORDER BY created_at DESC`
- Configuration versions: `ORDER BY effective_from DESC`
- Risk flags within a snapshot: `ORDER BY severity, flag_code`
  (HIGH before MEDIUM before INFO; alphabetical within severity)
- Validation warnings within a snapshot: `ORDER BY rule_code`
  (e.g. V-08 before V-25)

---

## 14.5 — Projection Queries Use Column Selection, Not SELECT *

Projection queries (Summary, HistoryEntry types) select only the columns
they need. `SELECT *` is not used in projection queries. This prevents
accidental loading of large columns (e.g. `sdlt_band_breakdown` JSONB)
in queries that do not need them.

Full aggregate loads may use `SELECT *` per table, since all columns are
needed.

---

---

# Part 15 — Pagination Strategy

---

## 15.1 — Cursor-Based Pagination for Lists

All paginated repository methods accept a `PageRequest` value object and
return a `Page[T]` result.

**PageRequest:**
```
PageRequest:
    limit: int        (max records per page; 1 to 100; default 20)
    cursor: str | None  (opaque cursor from previous page response; None for first page)
```

**Page[T]:**
```
Page[T]:
    items: List[T]
    next_cursor: str | None   (None if this is the last page)
    total_count: int          (total matching records, for display)
```

**Cursor encoding:** The cursor encodes the `(created_at, id)` tuple of the
last record on the previous page, base64-encoded. This provides stable
pagination even as records are inserted or updated between page requests.

**Why cursor-based rather than offset-based:** Offset pagination (`LIMIT n
OFFSET m`) is unreliable when new records are inserted between page requests
— records shift in position and users may see duplicates or skip records.
Cursor-based pagination is stable regardless of concurrent inserts.

---

## 15.2 — Paginated Queries Use Keyset Pagination

The WHERE clause for cursor-based pagination:

```
WHERE (created_at, id) < (:cursor_created_at, :cursor_id)
ORDER BY created_at DESC, id DESC
LIMIT :limit
```

Using `(created_at, id)` as a composite cursor handles the edge case where
multiple records have the same `created_at` timestamp (e.g. bulk imports).
The `id` UUID provides a stable tiebreaker.

---

## 15.3 — Non-Paginated Results Are Explicitly Documented

Repository methods that return `List[T]` without pagination are explicitly
documented with a reason and an expected maximum bound. Any list method
without pagination documentation is a review defect.

Currently non-paginated (with justification):
- `find_all_for_property` — a property is expected to have < 50 deals; bounded
- `find_all_for_user` on `InvestorProfileRepository` — expected < 10 profiles per user
- `find_history_for_deal` on `SnapshotRepository` — expected < 100 snapshots per deal;
  bounded by recalculation frequency

---

---

# Part 16 — Audit Repository Design

---

## 16.1 — Audit Writes Are Decoupled From Business Transaction Outcomes

The audit repository must write even when the main business operation fails.
The two-path audit pattern:

**Path A — Calculation Success:**
The audit event write is included inside the snapshot creation transaction.
Both succeed together or both roll back together. The audit event has
`outcome = SUCCESS` and `snapshot_id = <new_snapshot_id>`.

**Path B — Validation Failure or Engine Error:**
The main calculation transaction either did not start (no snapshot exists)
or was rolled back. The audit event write uses a fresh database session,
independent of any failed transaction. If the audit write itself fails
(extremely rare), this is logged operationally but does not propagate as
an error to the user — the business outcome (validation failure message)
is unaffected.

---

## 16.2 — Audit Records Are Append-Only At the Repository Level

The `IAuditRepository` interface exposes only `save()`. There is no `update()`
or `delete()`. The repository implementation uses INSERT only. No audit record
may be modified after creation.

---

## 16.3 — Audit Reads Are Scoped

`find_history_for_deal` always filters by `deal_id` and returns paginated
results. `find_history_for_user` always filters by `user_id`. No bulk audit
read (all audit events, no scope) is exposed through the user-facing repository
interface.

Admin-level audit queries (e.g. "all engine errors in the last 24 hours")
are out of scope for Phase 1 but the table design accommodates them via the
`outcome` index defined in DATABASE_SCHEMA_DESIGN.md.

---

---

# Part 17 — Future Workflow Repository Extension Points

These extension points are designed now to ensure Phase 1 implementation
does not create structural obstacles to Phase 2 workflow features.

---

## 17.1 — DealWorkflowEventRepository (Phase 2+)

```
interface IDealWorkflowEventRepository:

    save(event: DealWorkflowEvent) → None
        Append-only insert. No updates.

    find_history_for_deal(
        deal_id: UUID,
        event_type_filter: WorkflowEventType | None,
        page: PageRequest
    ) → Page[DealWorkflowEvent]
```

This repository is entirely independent of `IDealRepository`. It uses a
different table (`deal_workflow_events`) and a different domain entity
(`DealWorkflowEvent`). No changes to `IDealRepository` are required.

---

## 17.2 — SnapshotComparisonRepository (Phase 2+)

```
interface ISnapshotComparisonRepository:

    save(comparison: SnapshotComparison) → None
        Insert-only. Comparisons are read-only after creation.

    find_by_id_for_user(comparison_id: UUID, user_id: UUID) → SnapshotComparison | None

    find_all_for_deal(deal_id: UUID) → List[SnapshotComparison]
```

`SnapshotComparison` stores only the two snapshot IDs and metadata. It does
not cache computed differences — those are always derived at read time by
loading the two snapshots from `ISnapshotRepository`.

---

## 17.3 — IDealRepository Extensions (Phase 2+)

Phase 2 deal status vocabulary expands (OFFER_SUBMITTED, FINANCING, etc.).
The `IDealRepository.update()` method handles these without interface changes
— the `Deal` domain entity carries the new status values, and the mapping
layer handles the persistence.

The `find_all_for_user` status filter already accepts `DealStatus | None`,
so new status values are immediately filterable without interface changes.

---

---

# Part 18 — Future Intelligence Repository Extension Points

---

## 18.1 — IPropertyLocationRepository (Phase 3+)

```
interface IPropertyLocationRepository:

    save(location: PropertyLocation) → None

    find_by_property_id(property_id: UUID) → PropertyLocation | None

    find_properties_within_radius(
        centre: GeoPoint,
        radius_metres: int,
        user_id: UUID
    ) → List[PropertyLocationSummary]
```

This is a new repository for Phase 3. It uses PostGIS spatial queries. It
has no overlap with `IPropertyRepository` (which handles address and
descriptive data). The two repositories are independently called by the
service layer.

---

## 18.2 — IAreaIntelligenceRepository (Phase 3+)

```
interface IAreaIntelligenceRepository:

    find_latest_for_postcode(
        postcode: str,
        data_type: IntelligenceDataType
    ) → AreaIntelligenceRecord | None

    find_freshness_status(
        postcode: str,
        data_type: IntelligenceDataType
    ) → IntelligenceFreshness
```

Area intelligence records are read-only from the user-facing perspective. They
are populated by background import processes (Phase 3+) that write to the
`intel_area_records` table. The repository exposes only read operations for
the user-facing service layer.

---

## 18.3 — ISnapshotRepository Intelligence Extension (Phase 3+)

When `snapshot_inputs` gains nullable intelligence FK columns (Phase 3), the
`SnapshotRepository` save and load operations are extended to handle these
new fields. The interface additions are additive — existing methods are not
changed. The `SnapshotInputs` domain entity gains optional intelligence
reference fields; the repository mapper handles them.

---

## 18.4 — IAISummaryRepository (Phase 5+)

```
interface IAISummaryRepository:

    save(summary: AISummary) → None

    find_latest_for_snapshot(snapshot_id: UUID) → AISummary | None

    find_all_for_snapshot(snapshot_id: UUID) → List[AISummary]
```

The FK direction is AI → snapshot. `ISnapshotRepository` has no knowledge of
`IAISummaryRepository`. AI summaries are a separate concern loaded and
displayed independently of the snapshot data.

---

---

# Part 19 — Performance Expectations

---

## 19.1 — Expected Query Performance Targets (Phase 1)

All targets apply at expected Phase 1 scale (< 10,000 users, < 100,000 deals,
< 500,000 snapshots).

| Operation | Expected Latency | Justification |
|---|---|---|
| `find_by_id_outputs_only` (snapshot display) | < 10ms | 3 indexed queries, small row count |
| `find_by_id` (full aggregate) | < 30ms | 6 indexed queries, small row count |
| `find_history_for_deal` (snapshot list) | < 20ms | 1 aggregating query, indexed by deal_id |
| `find_all_for_user` (deal list, page 1) | < 15ms | Indexed by user_id, keyset pagination |
| `find_active_*_config` (per-calculation × 3) | < 5ms each | Single row query, indexed |
| `SnapshotRepository.save` (full write) | < 50ms | 6 INSERTs + 1 UPDATE, no contention |
| `AuditRepository.save` | < 5ms | Single row INSERT |

---

## 19.2 — The Configuration Read Hotpath

The three `find_active_*_config` calls run on every calculation. At high
request volume, these are the most frequent reads in the system. They are
protected by:
- Small result sets (one row per query)
- `effective_from DESC` indexes on all three configuration tables
- Append-only tables (no UPDATE lock contention)

If load testing reveals these queries to be a measurable bottleneck, the
first mitigation is a short-lived per-process cache in
`ConfigurationResolutionService`. The repository interface does not change.

---

## 19.3 — Intermediates Are Not a Hotpath

`snapshot_intermediates` is the widest table in the schema (many columns,
full precision values). It is only loaded via `find_by_id` (full aggregate).
This is not called in any list view, any display view, or any calculation path.
It is a low-frequency read (audit, reproducibility verification, future
explainability). Its performance is not a primary concern.

---

## 19.4 — Risk Flag Queries Scale With Portfolio Size (Phase 4+)

Phase 4 introduces portfolio analytics queries such as "all deals with
NEGATIVE_CASHFLOW flag." These cross-snapshot queries use the `flag_code`
index on `snapshot_risk_flags`. At Phase 4 scale, this index may need tuning
or the query may need a materialised view. This is a Phase 4 concern — the
index is in place from Phase 1, and further optimisation deferred.

---

---

# Part 20 — Repository Invariants

These invariants are enforced by the repository layer. Any implementation
that violates them is incorrect.

---

```
RI-01 — Snapshot repositories only expose INSERT for snapshot sub-tables.
        No UPDATE method, no DELETE method, no UPSERT method exists for
        snapshot_inputs, snapshot_outputs, snapshot_intermediates,
        snapshot_risk_flags, or snapshot_validation_warnings.

RI-02 — SnapshotRepository.save() is atomic.
        Either all sub-table writes succeed or none do.
        A partial snapshot must never exist in the database.

RI-03 — mark_superseded() is the only update operation on snapshot_calculations.
        No other field on a snapshot record may be modified via any repository
        operation.

RI-04 — Configuration repositories only expose INSERT for new versions.
        No UPDATE method, no DELETE method exists for any config_* table.
        find_active_* always returns the most recent version for the given date,
        never an interpolated or synthesised value.

RI-05 — AuditRepository only exposes INSERT.
        No UPDATE, no DELETE.

RI-06 — All _for_user query variants return None for both "not found" and
        "found but wrong user" cases.
        They never distinguish between the two cases in their return value.

RI-07 — No repository method returns a persistence model (ORM row).
        All return types are domain entities or domain projection types.

RI-08 — No repository method accepts a persistence model as input.
        All input types are domain entities or primitive identifiers (UUID, date).

RI-09 — No unbounded list query without explicit justification.
        Any method returning List[T] without pagination must document the
        expected upper bound.

RI-10 — The AuditRepository.save() for failure outcomes must succeed even
        if the main business transaction has failed or been rolled back.
        It uses a fresh session, independent of the failed transaction.

RI-11 — SnapshotRepository.save() updates deals.latest_snapshot_id as part
        of the same transaction. This update is not a separate repository call.
        It is encapsulated within the snapshot save operation.

RI-12 — Configuration reads never return stale data within a request.
        The configuration loaded at the start of a request is used throughout
        that request. No re-reading mid-request.

RI-13 — All numeric values flowing through the repository are Decimal.
        Float is never accepted or returned. The repository mapping layer
        must enforce this and raise PersistenceIntegrityError if float is
        returned by the ORM.

RI-14 — Repositories do not call services.
        Repositories do not call the engine.
        Repositories do not call other repositories.
        The one exception: SnapshotRepository.save() orchestrates multiple
        table writes as a unit — this is internal to the repository, not
        inter-repository calling.

RI-15 — Snapshot sub-aggregate objects (SnapshotInputs, SnapshotOutputs,
        SnapshotIntermediates, RiskFlag, ValidationWarning) are never loaded
        independently of their parent CalculationSnapshot.
        There are no repository methods for these types as standalone objects.
```
