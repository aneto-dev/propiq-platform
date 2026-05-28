# PropIQ Platform — Service Layer and API Architecture

## Purpose

This document defines the application architecture surrounding the underwriting
engine: the API boundary, service layer responsibilities, request lifecycles,
authentication boundaries, error propagation, async considerations, and future
extensibility constraints.

This document is not an implementation specification. It contains no FastAPI
routes, no DTO schemas, no repository implementations, and no ORM definitions.
It defines how the application is structured as a set of collaborating layers
so that implementation can proceed from a stable design.

All terminology matches DOMAIN_GLOSSARY.md. All constraints reflect
ARCHITECTURE.md, ENGINE_ARCHITECTURE.md, SCHEMA_ARCHITECTURE.md, and
DECISIONS.md.

---

## Governing Constraints

**Engine independence:** The underwriting engine remains a pure computation
module. No service layer concern — authentication, persistence, request
parsing, error formatting — may leak into the engine. The engine boundary
defined in ENGINE_ARCHITECTURE.md is an architectural invariant.

**No business logic in the API layer:** Route handlers receive requests,
delegate to services, and return responses. They do not calculate, validate
domain inputs, or make persistence decisions. Business logic lives in the
service layer; calculation logic lives in the engine.

**Atomic snapshot creation:** The snapshot creation transaction defined in
ENGINE_ARCHITECTURE.md Part 9 must remain atomic. No partial snapshot state
may exist in the database. This is enforced at the service layer, not at the
API layer.

**Historical reproducibility:** Every design decision in the service layer
must preserve the guarantee that any snapshot can be exactly reproduced from
its stored inputs and configuration version references.

**Phase 1 operational simplicity:** The architecture must be deployable and
maintainable by a small team. Premature abstractions, unnecessary services,
and speculative infrastructure are explicitly avoided. The design supports
future scaling without requiring it now.

**API versioning from day one:** API contracts must be versioned from the
first release. Adding a version prefix to all routes costs nothing early and
avoids a painful migration later.

---

---

# Part 1 — Full Stack Layer Map

This is the authoritative picture of all layers and their relationships. Every
component is described in detail in subsequent parts.

```
┌─────────────────────────────────────────────────────────────────────┐
│  FRONTEND  (Next.js / TypeScript / Tailwind)                        │
│                                                                     │
│  Deal form · Deal summary · Snapshot comparison · Dashboard         │
│  No calculation logic. Renders what the API returns.                │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTPS / JSON
                             │ JWT in Authorization header
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  API LAYER  (FastAPI)                                               │
│                                                                     │
│  Route handlers · Request parsing · Auth token verification         │
│  Response serialisation · HTTP error mapping                        │
│                                                                     │
│  /api/v1/deals          /api/v1/snapshots                           │
│  /api/v1/properties     /api/v1/calculations                        │
│  /api/v1/config (admin) /api/v1/health                              │
│                                                                     │
│  No business logic. No calculations. No direct DB access.           │
└────────────────────────────┬────────────────────────────────────────┘
                             │ calls
                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│  SERVICE LAYER                                                      │
│                                                                     │
│  CalculationService   ConfigurationService   SnapshotService        │
│  DealService          PropertyService        AuditService           │
│  UserService                                                        │
│                                                                     │
│  Orchestrates domain operations. Owns transaction boundaries.       │
│  Owns default resolution. Owns audit log writes.                    │
└──────────┬──────────────────────────────────┬───────────────────────┘
           │ calls                            │ reads/writes
           ▼                                  ▼
┌──────────────────────┐         ┌────────────────────────────────────┐
│  ENGINE              │         │  REPOSITORY LAYER                  │
│  (Pure Python)       │         │                                    │
│                      │         │  DealRepository                    │
│  engine.run(         │         │  PropertyRepository                │
│    EngineInput,      │         │  SnapshotRepository                │
│    EngineConfig      │         │  ConfigurationRepository           │
│  ) → EngineResult    │         │  AuditRepository                   │
│                      │         │                                    │
│  No I/O.             │         │  No business logic.                │
│  No DB.              │         │  No calculations.                  │
│  No framework.       │         │  Translates domain objects         │
└──────────────────────┘         │  to/from database records.        │
                                 └──────────────┬─────────────────────┘
                                                │
                                                ▼
                                 ┌──────────────────────────────────┐
                                 │  PostgreSQL + PostGIS             │
                                 │                                  │
                                 │  Deals · Properties · Snapshots  │
                                 │  Configuration · Audit Log       │
                                 └──────────────────────────────────┘
```

---

---

# Part 2 — API Layer Responsibilities

The API layer is the HTTP boundary of the backend. Its responsibilities are
narrow and must remain narrow.

---

## What the API layer does

**Request parsing:** Deserialise the incoming JSON body into a typed request
object. Reject structurally malformed requests (missing required keys, wrong
types) at this layer before they reach the service layer.

**Authentication token verification:** Extract the JWT from the Authorization
header. Verify signature and expiry against Supabase Auth. Extract the
authenticated user identity. Reject unauthenticated requests with 401.

**Authorisation pre-check:** Verify that the authenticated user has the right
to perform the requested operation at the route level. Detailed ownership
checks (e.g. "does this user own this deal?") happen in the service layer,
but coarse role checks (e.g. "only admin users may call this config route")
happen at the API layer.

**Delegation to service layer:** Pass the parsed request and authenticated
user identity to the appropriate service. Do not make business decisions.

**Response serialisation:** Convert the service layer's return value into the
appropriate HTTP response: status code, JSON body, headers.

**HTTP error mapping:** Convert service layer exceptions and error values into
appropriate HTTP responses. A domain validation error becomes 422. An entity
not found becomes 404. An unexpected engine error becomes 500. The mapping
table is defined in Part 11.

---

## What the API layer must not do

- Perform domain validation (that is the engine's validation pipeline)
- Make persistence calls directly (that is the repository layer's job)
- Know about the underwriting engine or its contracts
- Know about snapshot creation or configuration version resolution
- Contain conditional business logic

---

## API versioning strategy

All routes are prefixed with `/api/v1/`. This is mandatory from day one.

The version prefix is the only mechanism for introducing breaking API changes
without disrupting existing clients. When a breaking change is needed (changed
response shape, removed field, changed semantics), a `/api/v2/` namespace is
introduced alongside v1. v1 is maintained for a defined deprecation period.

Non-breaking additions (new optional response fields, new optional request
fields) may be made within an existing version without a version increment.

---

## Route groups (Phase 1)

```
/api/v1/auth/
    Thin wrapper around Supabase Auth callbacks.
    Profile creation on first login.

/api/v1/properties/
    CRUD for Property records.
    Owned by the authenticated user.

/api/v1/deals/
    CRUD for Deal records.
    Deals belong to properties which belong to the user.

/api/v1/calculations/
    POST to trigger a new calculation for a deal.
    POST to trigger a recalculation.
    These are the highest-value routes in the system.

/api/v1/snapshots/
    GET snapshot by ID.
    GET snapshot list for a deal.
    No write operations — snapshots are created only via /calculations/.

/api/v1/config/ (admin-only)
    GET active configuration versions.
    POST to insert a new configuration version.
    Requires admin role.

/api/v1/health/
    Liveness and readiness checks.
    No authentication required.
```

---

---

# Part 3 — Service Layer Responsibilities

The service layer contains all domain logic that is not pure calculation. It
orchestrates the engine, manages transactions, resolves configuration, and
enforces business rules about ownership, state transitions, and audit trails.

Services are the only layer that may call other services. The API layer calls
services. Services call repositories and the engine. The engine calls nothing.

---

## CalculationService

The most important service in the application. It is the only service that
calls the engine.

**Responsibilities:**
- Receive a calculation request containing deal inputs and user identity
- Verify the user owns the deal
- Load active configuration versions via ConfigurationService
- Resolve optional input defaults (user value or config default)
- Track input source (USER_OVERRIDE / CONFIG_DEFAULT) per optional input
- Assemble EngineInput and EngineConfig
- Call `engine.run(engine_input, engine_config)`
- If validation failure: write audit log entry, return structured errors
- If engine error: write audit log entry, return sanitised error
- If success: delegate to SnapshotService to persist the result
- Return the created snapshot ID and summary to the API layer

**What CalculationService does not do:**
- Contain any formula logic
- Make direct database calls (delegates to repositories)
- Format HTTP responses

---

## ConfigurationService

Responsible for loading versioned configuration from the database and
providing it to CalculationService in the form the engine expects.

**Responsibilities:**
- Load the active SDLT configuration for a given calculation date
- Load the active Corporation Tax configuration for a given calculation date
- Load the active Assumption configuration for a given calculation date
- Return both the configuration values (for EngineConfig) and the version IDs
  (for snapshot version references) as a paired structure
- Resolve optional input defaults from the active Assumption configuration

**Configuration loading pattern:**

```
For each configuration table:
    active_record = most recent record where effective_from <= calculation_date

Return:
    ConfigBundle {
        engine_config: EngineConfig (plain values only)
        version_refs: ConfigVersionRefs (IDs only, not passed to engine)
    }
```

**Caching behaviour:**
Configuration records are append-only and do not change within a request.
ConfigurationService may hold a per-request cache of loaded configuration.
Process-level or cross-request caching is not implemented in Phase 1.

---

## SnapshotService

Responsible for persisting a completed EngineResult as an immutable snapshot,
and for reading snapshot data for display.

**Write responsibilities (called only by CalculationService):**
- Open a database transaction
- Write the Snapshot root record, Snapshot Inputs, Snapshot Outputs,
  Snapshot Intermediates, and Snapshot Risk Flag rows
- Update Deal.latest_snapshot_id
- Write the audit log entry for the successful calculation
- Commit atomically — all writes succeed or none do

**Read responsibilities:**
- Load a snapshot by ID for display (assembles the sub-entity records)
- Load the snapshot list for a deal (summary view — does not load intermediates)
- Load two snapshots for comparison (for the comparison view, Phase 2)

**What SnapshotService does not do:**
- Modify existing snapshots
- Delete snapshots
- Call the engine
- Contain business logic about when recalculation is appropriate

---

## DealService

Responsible for deal lifecycle management — the mutable workspace layer.

**Responsibilities:**
- Create a deal for an authenticated user against a property
- Update deal inputs (label, status, working input fields)
- Verify user ownership before any operation
- Archive a deal (status transition only — no data deletion)
- Return deal summaries including the latest snapshot reference

**What DealService does not do:**
- Trigger calculations (that is CalculationService's job)
- Know about snapshots except to pass the latest snapshot ID for display

---

## PropertyService

Responsible for property record management.

**Responsibilities:**
- Create a property record for an authenticated user
- Update property details (address, tenure, type)
- Verify user ownership
- Return properties with their associated deal count

**Notes:**
The Property record is mutable and does not affect historical snapshots.
Changes to a property record after a snapshot is created do not alter the
snapshot, because snapshots are self-contained.

---

## UserService

Responsible for the platform's own user record, which extends Supabase Auth.

**Responsibilities:**
- Create a platform user record on first login (triggered by Supabase Auth
  webhook or on first authenticated request)
- Update display name and preferences
- Manage investor profiles (create, update, list, set default)

**What UserService does not do:**
- Manage authentication tokens (Supabase Auth owns that)
- Store passwords

---

## AuditService

Responsible for writing audit log entries. Called by CalculationService after
every calculation attempt, regardless of outcome.

**Responsibilities:**
- Write a calculation audit log entry with outcome, snapshot reference,
  validation errors, or engine error details
- Ensure audit entries are written even when calculation fails

**Design note:**
AuditService writes to the audit log inside the same transaction as the
snapshot creation (for SUCCESS outcomes). For VALIDATION_FAILURE and
ENGINE_ERROR outcomes, no snapshot transaction exists, so the audit entry
is written in its own transaction. This ensures audit entries are always
written, even when the main operation fails.

---

---

# Part 4 — Calculation Request Lifecycle

This is the end-to-end flow for a new calculation request. It connects the
frontend action to the persisted snapshot.

```
FRONTEND
  User completes deal input form and clicks "Analyse Deal"
  POST /api/v1/calculations/  { deal_id, inputs }
  Authorization: Bearer <JWT>
        │
        ▼
API LAYER
  1. Parse and validate request structure (required fields present, types correct)
  2. Verify JWT with Supabase Auth → extract user_id
  3. Delegate to CalculationService.run_calculation(user_id, deal_id, raw_inputs)
        │
        ▼
CALCULATION SERVICE
  4.  Verify user_id owns deal_id → if not: raise NotFoundError
  5.  Load active configuration:
        ConfigurationService.load_for_calculation(calculation_date=now())
        Returns: ConfigBundle { engine_config, version_refs }
  6.  Resolve optional input defaults:
        For each optional input:
          user_value present → use it, source = USER_OVERRIDE
          user_value absent  → use config default, source = CONFIG_DEFAULT
  7.  Assemble EngineInput (fully populated, no nulls)
  8.  Call engine.run(engine_input, config_bundle.engine_config)
        │
        ├── ValidationFailure?
        │     AuditService.write(outcome=VALIDATION_FAILURE, errors=...)
        │     Return ValidationErrorResult to API layer
        │
        ├── EngineError?
        │     AuditService.write(outcome=ENGINE_ERROR, detail=...)
        │     Return EngineErrorResult to API layer
        │
        └── EngineResult (success)
              │
              ▼
SNAPSHOT SERVICE (called by CalculationService)
  9.  Begin transaction
  10. Write Snapshot root record (UUID, deal_id, user_id, engine_version,
        version_refs, calculated_at=now())
  11. Write Snapshot Inputs (all inputs + source flags)
  12. Write Snapshot Outputs (all output fields from EngineResult)
  13. Write Snapshot Intermediates (all intermediate fields)
  14. Write Snapshot Risk Flags (one row per flag)
  15. UPDATE Deal.latest_snapshot_id = new snapshot_id
  16. AuditService.write(outcome=SUCCESS, snapshot_id=...)
  17. Commit transaction
        │
        ▼
CALCULATION SERVICE
  18. Return { snapshot_id, summary_outputs, risk_flags } to API layer
        │
        ▼
API LAYER
  19. Serialise response → 201 Created { snapshot_id, outputs, risk_flags }
        │
        ▼
FRONTEND
  20. Navigate to deal summary page, render snapshot outputs
```

---

---

# Part 5 — Recalculation Workflow

Recalculation is triggered explicitly by the user. It is not automatic.
Two variants exist as defined in ENGINE_ARCHITECTURE.md Part 10.

```
VARIANT A — Recalculate with current rates
  User clicks "Recalculate with current assumptions"
  POST /api/v1/calculations/recalculate
    { deal_id, mode: "CURRENT_ASSUMPTIONS" }

  CalculationService:
    1. Load LATEST active configuration (standard loading sequence)
    2. Use deal's current working inputs
    3. Run engine → new EngineResult
    4. Create new snapshot (full snapshot creation flow)
    5. Previous snapshot is_superseded = true
    6. Deal.latest_snapshot_id updated
    7. Return new snapshot_id

VARIANT B — Reproduce original result
  User clicks "Verify original calculation"
  POST /api/v1/calculations/recalculate
    { deal_id, mode: "REPRODUCE_ORIGINAL", source_snapshot_id }

  CalculationService:
    1. Load ORIGINAL snapshot's configuration version IDs
    2. Load those SPECIFIC configuration records (not latest)
    3. Use ORIGINAL snapshot's inputs as EngineInput
    4. Run engine → should produce identical EngineResult
    5. Create new snapshot (marked as a reproduction)
    6. Return new snapshot_id and comparison result
```

**Important:** In both variants, the original snapshot is never modified.
All previous snapshots remain accessible. The Deal.latest_snapshot_id pointer
is updated only in Variant A — a reproduction (Variant B) does not change
which snapshot is considered current.

---

---

# Part 6 — Authentication and Authorisation Boundaries

---

## Authentication

Authentication is fully delegated to Supabase Auth. The platform does not
implement token issuance, password management, or session handling.

**Flow:**
1. Frontend authenticates via Supabase Auth (email/password, magic link, or
   OAuth in future phases)
2. Supabase issues a signed JWT
3. Frontend includes the JWT in `Authorization: Bearer <token>` on every API
   request
4. API layer verifies the JWT signature using Supabase's public key
5. Verified user identity (user UUID from JWT sub claim) is passed to services

**What the platform does with the JWT:**
- Extract user UUID
- Verify token expiry
- Reject expired or invalid tokens with 401

**What the platform does not do:**
- Re-implement token verification logic (uses Supabase's SDK)
- Store session state server-side (JWTs are stateless)

---

## Authorisation model (Phase 1)

Phase 1 uses a simple ownership model. There are no role-based permissions
except for the admin configuration routes.

**Ownership rules:**
- A user may only read and write their own Properties and Deals
- A user may only read Snapshots that belong to their Deals
- A user may only trigger calculations on their own Deals

**Enforcement:**
- Ownership is verified at the service layer, not at the API layer
- Every DealService and PropertyService method that retrieves or modifies a
  record verifies that `record.user_id == authenticated_user_id`
- A record belonging to a different user returns NotFound (not Forbidden) —
  existence must not be disclosed to unauthorised users

**Admin routes:**
- Configuration management routes (`/api/v1/config/`) require an admin flag
  on the User record
- Admin status is checked at the API layer before delegating to the service
- Admin users are provisioned manually in Phase 1; self-service admin
  assignment is out of scope

---

## Future authorisation considerations (not Phase 1)

Phase 2 will introduce team/advisor accounts, which will require a more
formal permission model. The current ownership-only model does not need to
change for Phase 1 to work correctly, and the simple model is easier to
reason about and audit.

---

---

# Part 7 — Configuration Service Responsibilities

The ConfigurationService is the sole point of contact between the application
and the versioned configuration tables. No other service queries configuration
tables directly.

---

## Loading strategy

```
ConfigurationService.load_for_calculation(calculation_date: date) → ConfigBundle

ConfigBundle:
  engine_config: EngineConfig      ← passed to engine.run()
  version_refs: ConfigVersionRefs  ← stored in snapshot, NOT passed to engine

ConfigVersionRefs:
  sdlt_config_id
  corporation_tax_config_id
  assumption_config_id
```

The engine receives `engine_config` only. It never sees `version_refs`.
The calculation service holds `version_refs` and passes them to
SnapshotService for persistence.

---

## Loading for recalculation (reproduce original)

```
ConfigurationService.load_specific_versions(
    sdlt_config_id,
    corporation_tax_config_id,
    assumption_config_id
) → ConfigBundle
```

This loads the exact configuration records referenced by the original snapshot.
The returned `engine_config` contains the same values that were active at the
time of the original calculation, guaranteeing reproducibility.

---

## Default resolution

The ConfigurationService also resolves optional input defaults when called
by the CalculationService:

```
ConfigurationService.resolve_defaults(
    raw_user_inputs: dict,
    assumption_config: AssumptionConfig,
    ownership_structure: OwnershipStructure
) → (resolved_inputs: dict, input_sources: dict)
```

Where `input_sources` maps each optional field to USER_OVERRIDE or
CONFIG_DEFAULT. This is returned alongside the resolved inputs and written
to the Snapshot Inputs record.

---

## What ConfigurationService does not do

- Modify configuration records
- Validate whether a configuration version is "correct"
- Cache across requests in Phase 1

---

---

# Part 8 — Audit Logging Architecture

Every calculation attempt is recorded in the Calculation Audit Log, regardless
of outcome. This is an architectural invariant, not a nice-to-have.

---

## Audit entry timing

```
Outcome             When written            Transaction
─────────────────   ─────────────────────   ──────────────────────────────
SUCCESS             Inside snapshot tx      Same transaction as snapshot
VALIDATION_FAILURE  After validation fails  Own transaction (no snapshot)
ENGINE_ERROR        After engine fails      Own transaction (no snapshot)
```

For SUCCESS outcomes, the audit entry and the snapshot are written atomically.
Either both exist or neither does. This prevents the audit log from recording
a success for a snapshot that failed to persist.

---

## What each audit entry contains

```
Calculation Audit Entry:
  id                  — unique identifier
  user_id             — who triggered the calculation
  deal_id             — which deal
  snapshot_id         — nullable (null for failures)
  triggered_at        — UTC timestamp
  outcome             — SUCCESS / VALIDATION_FAILURE / ENGINE_ERROR
  engine_version      — version of engine at time of attempt
  validation_errors   — JSON array of {rule_code, field, message} (failures only)
  error_detail        — sanitised string (engine errors only)
  client_context      — web / API (for future analytics)
```

---

## Audit log is append-only

Audit entries are never updated or deleted. This is enforced at the database
layer (no UPDATE/DELETE privileges for the application user on the audit log
table) and at the application layer (AuditService exposes only a write method).

---

## Future audit extensions (not Phase 1)

Phase 2 will add an Admin Audit Log for configuration version inserts
(who created a new SDLT configuration version, when, with what rationale).
This is a separate log from the Calculation Audit Log. The structure is
similar but the subject is configuration events rather than calculation events.

---

---

# Part 9 — Async and Background Job Considerations

Phase 1 calculations are synchronous. The calculation pipeline — validation,
engine, snapshot creation — completes within a single HTTP request cycle.
This is intentional and correct for Phase 1 workloads.

---

## Why synchronous is correct for Phase 1

A calculation on a single deal takes milliseconds. The engine is pure in-memory
computation. The snapshot write is a small set of INSERT statements. There is
no I/O within the engine itself. A synchronous request cycle is entirely
appropriate at this scale.

---

## Where async becomes relevant in later phases

**Phase 3 — Area intelligence enrichment:**
When a property is saved or a deal is created, the platform will want to enrich
it with crime data, flood risk, EPC ratings, and school proximity. These
require external API calls that may be slow or unreliable. This is the first
natural use case for a background job queue.

The current architecture accommodates this by keeping the Property and Deal
creation flows independent from any enrichment. A Phase 3 background worker
would receive a property ID, call external APIs, and write Area Intelligence
Records. The core calculation flow is unaffected.

**Phase 4 — Portfolio analytics:**
Aggregating metrics across all of a user's deals (total portfolio cash flow,
aggregate risk exposure) may involve querying many snapshots. At scale this
is better handled as a pre-computed background job than an on-demand query.

**Phase 5 — AI summaries:**
Generating a plain-language summary of a deal involves an AI API call with
variable latency. This must be asynchronous. The AI summary must reference
the snapshot and display alongside it, but must never block the snapshot
creation or display of calculated outputs.

---

## Async infrastructure recommendation

When background jobs become necessary (Phase 3 at the earliest), the
recommended approach is a simple task queue using Redis and a worker process
(e.g. ARQ or Celery). This fits the Railway deployment model and does not
require separate infrastructure until task volume warrants it.

The Phase 1 architecture does not preclude this. No synchronous logic needs
to be restructured to introduce a task queue in a future phase.

---

---

# Part 10 — Frontend and Backend Interaction Flow

The frontend is a consumer of the API. It does not own any calculation logic,
business rules, or data transformation logic beyond presentation.

---

## Interaction principles

**API client pattern:** The frontend maintains a typed API client layer
(`/lib/api/`) that wraps all HTTP calls. No component makes raw fetch calls.
The API client handles JWT attachment, error response normalisation, and
TypeScript type mapping.

**No calculation in the frontend:** The frontend never computes yields,
cash flows, SDLT, or any other underwriting output. It renders what the API
returns. Displaying a pre-computed value from the snapshot is the only
permitted pattern.

**Optimistic UI is not used for calculations:** A calculation is a
write-then-read pattern. The frontend submits inputs, waits for the API
response, then renders the returned outputs. There is no speculative rendering
of calculation results before the server confirms them. This is correct for a
trust-first platform — showing the user a number that might change is the
exact antipattern the platform is designed to avoid.

**Snapshot-first rendering:** The deal summary page always renders from a
snapshot. It never derives display values from the deal's working inputs.
If no snapshot exists yet (DRAFT status), the user sees an empty state that
prompts them to run the analysis.

---

## Key frontend flows

```
DEAL CREATION
  User enters property address and deal label
  POST /api/v1/properties/ → property_id
  POST /api/v1/deals/ → deal_id (status: DRAFT, no snapshot yet)
  Frontend redirects to deal input form

DEAL INPUT AND ANALYSIS
  User completes all required inputs
  User clicks "Analyse Deal"
  POST /api/v1/calculations/ → { snapshot_id, outputs, risk_flags }
  Frontend navigates to deal summary, renders snapshot outputs

DEAL SUMMARY DISPLAY
  GET /api/v1/snapshots/{snapshot_id} → full snapshot outputs and intermediates
  Frontend renders:
    — acquisition cost breakdown
    — annual cash flow waterfall
    — SDLT band breakdown
    — yield and return metrics
    — risk flags (sorted by severity)
    — disclosed limitations

SNAPSHOT HISTORY
  GET /api/v1/snapshots/?deal_id={deal_id} → list of snapshots for deal
  Frontend renders snapshot list with timestamps and superseded status

RECALCULATION
  User clicks "Recalculate with current assumptions"
  POST /api/v1/calculations/recalculate → { new_snapshot_id, ... }
  Frontend navigates to updated deal summary
```

---

## Error display conventions

Validation failures from the engine return structured field-level errors.
The API layer maps these to the response body. The frontend maps error codes
to form field highlighting and user-facing messages.

Engine errors return a generic message. The frontend shows a non-technical
error state and does not display internal error detail to users.

---

---

# Part 11 — Error Propagation Strategy

Errors originate in three places: the API layer (malformed requests), the
service layer (domain rule violations), and the engine (validation failures
or engine errors). Each must propagate to the frontend clearly and consistently.

---

## Error origin to HTTP status mapping

```
Origin                        HTTP Status   Response body
────────────────────────────  ───────────   ──────────────────────────────────
Malformed request body        400           { error: "INVALID_REQUEST",
                                             detail: "field X missing" }

Auth token missing/invalid    401           { error: "UNAUTHENTICATED" }

Insufficient permissions      403           { error: "FORBIDDEN" }

Resource not found or         404           { error: "NOT_FOUND" }
  belongs to another user

Engine HARD validation        422           { error: "VALIDATION_FAILURE",
  failure                                    field_errors: [
                                               { rule_code, field, message }
                                             ],
                                             warnings: [...] }

Engine unexpected failure     500           { error: "CALCULATION_ERROR",
                                             message: "Calculation could not
                                             be completed. Please try again." }

Unexpected server error       500           { error: "INTERNAL_ERROR" }
```

---

## Error propagation rules

**No stack traces in API responses.** Internal error detail (exception types,
stack traces, database query text) must never appear in API responses. Error
detail is logged server-side and surfaced via audit log entries where
appropriate.

**Structured validation errors, not free text.** Every validation failure
returns a structured list of `{ rule_code, field, message }` objects. The
frontend can map these to specific form fields for inline error display.

**Distinguishing 404 from 403.** Resources belonging to other users return
404, not 403. Returning 403 would confirm the resource exists. Returning 404
reveals nothing about whether the resource exists at all.

**Engine warnings are not errors.** WARN-level validation outcomes from the
engine (V-08, V-10, V-11 etc.) do not produce HTTP error responses. They are
included in the successful response body alongside the outputs, so the
frontend can display them as contextual information.

---

---

# Part 12 — Idempotency Considerations

---

## Calculation requests are not idempotent by design

Each call to `POST /api/v1/calculations/` creates a new snapshot. This is
correct and intentional. Snapshots are immutable records of a point-in-time
analysis. Two identical requests create two identical snapshots with different
UUIDs and timestamps. This is not a bug.

---

## Where idempotency matters

**Property and deal creation:** Creating the same property twice (same address,
same user) should ideally be idempotent or at least detectable. In Phase 1,
the platform does not enforce address uniqueness — the user may have legitimate
reasons to analyse the same address under different assumptions. Duplicate
detection is a Phase 2 UX concern, not a Phase 1 constraint.

**Configuration version inserts:** Inserting a new SDLT configuration version
is a low-frequency admin operation. It does not need to be idempotent. If an
admin accidentally inserts the same version twice, the effective_from date
deduplication in the query (`ORDER BY effective_from DESC LIMIT 1`) means the
second insert does not affect calculations unless it has a different
effective_from date.

---

## Client-side duplication prevention

The frontend should disable the "Analyse Deal" button during the in-flight
request and re-enable it only after the response is received. This prevents
accidental double-submission at the UX layer. It does not eliminate the
possibility of duplicate requests (network retries, tab duplication) but
reduces it to edge cases. Duplicate snapshots are benign — they are visible
in the snapshot history and the user can disregard them.

---

---

# Part 13 — Future AI Integration Boundaries

Phase 5 introduces AI-assisted summaries and insight generation.
The integration boundary is defined here so that Phase 1 through Phase 4
architecture decisions do not inadvertently create dependencies that would
make the AI integration harder or riskier.

---

## What AI may do (Phase 5)

- Generate a plain-language summary of a completed snapshot
- Explain what a specific risk flag means in the context of the deal
- Answer natural language questions about assumptions ("why is the void rate
  set to 3.85%?")
- Provide educational context about Section 24, SDLT, ICR thresholds
- Summarise changes between two snapshots

---

## What AI must never do (ADR-001)

- Generate or modify any output in the EngineResult
- Access the underwriting engine directly
- Interpret user inputs as calculation instructions
- Override, correct, or second-guess deterministic calculation outputs
- Produce numbers that appear alongside or as substitutes for calculated metrics

---

## Architectural enforcement of the AI boundary

```
AI Service (Phase 5)
    │
    │ reads snapshot outputs and metadata
    ▼
SnapshotService.get_snapshot_for_ai_summary(snapshot_id)
    │
    │ returns read-only snapshot data
    │ (outputs + risk flags + input summary)
    │ does NOT return intermediates
    ▼
AI API call (external — Anthropic API)
    │
    ▼
AI Summary Record (stored in database, references snapshot_id)
    │
    │ surfaced to frontend separately from calculation outputs
    ▼
Frontend renders AI summary in a visually distinct section
  with disclosure: "AI-generated summary — not a financial calculation"
```

The AI service is a read-only consumer of snapshot data. It has no write
access to snapshot records. The AI summary is stored as a separate entity
(AI Summary Record from SCHEMA_ARCHITECTURE.md Part 9) that references a
snapshot but does not modify it.

The frontend must render AI summaries in a visually and semantically distinct
area from calculation outputs. The two must never be mixed in a way that could
cause a user to mistake an AI-generated sentence for a deterministic calculated
value.

---

---

# Part 14 — Package and Module Boundaries

This defines the backend code organisation. It mirrors the domain group
structure from SCHEMA_ARCHITECTURE.md and makes the layer boundaries visible
in the file system.

---

## Backend package structure

```
backend/
│
├── api/                          # API layer only — no business logic
│   ├── v1/
│   │   ├── routes/
│   │   │   ├── calculations.py   # POST /calculations/, /recalculate
│   │   │   ├── deals.py
│   │   │   ├── properties.py
│   │   │   ├── snapshots.py
│   │   │   ├── config.py         # Admin only
│   │   │   └── health.py
│   │   └── dependencies.py       # Auth token verification, user extraction
│   └── error_handlers.py         # Global HTTP error mapping
│
├── services/                     # Service layer — business orchestration
│   ├── calculation_service.py
│   ├── configuration_service.py
│   ├── snapshot_service.py
│   ├── deal_service.py
│   ├── property_service.py
│   ├── user_service.py
│   └── audit_service.py
│
├── engine/                       # Pure underwriting engine — no I/O
│   ├── orchestrator.py           # engine.run() entry point
│   ├── validation/
│   │   └── rules.py              # V-01 through V-25 as data
│   ├── calculations/
│   │   └── formulas.py           # F-01 through F-22 as pure functions
│   ├── tax/
│   │   ├── individual.py         # Tax pathway A — Section 24
│   │   └── limited_company.py    # Tax pathway B — Corporation Tax
│   ├── risk_flags/
│   │   └── definitions.py        # Risk flag conditions as data
│   └── contracts.py              # EngineInput, EngineConfig, EngineResult
│
├── repositories/                 # Data access — no business logic
│   ├── deal_repository.py
│   ├── property_repository.py
│   ├── snapshot_repository.py
│   ├── configuration_repository.py
│   └── audit_repository.py
│
├── domain/                       # Domain value types and enums
│   ├── enums.py                  # OwnershipStructure, MortgageType, etc.
│   └── errors.py                 # Domain error types (not HTTP errors)
│
├── db/                           # Database connection and session management
│   ├── session.py
│   └── base.py
│
└── core/                         # Application config, startup, settings
    ├── config.py                 # Environment variables, settings
    └── startup.py                # App initialisation
```

---

## Dependency rules between packages

```
api/           → services/       (delegates to)
api/           → domain/         (uses enums, error types)

services/      → engine/         (calls engine.run())
services/      → repositories/   (reads and writes data)
services/      → domain/         (uses domain types)

engine/        → (nothing outside engine/)
               The engine package has zero imports from any other
               package in this application.

repositories/  → db/             (uses database session)
repositories/  → domain/         (uses domain types)

domain/        → (nothing — leaf package)
```

**The engine import rule is absolute.** If a linter or import check reveals
that `engine/` imports from `services/`, `repositories/`, `api/`, or `db/`,
that is a critical defect to be resolved before the code is merged.

---

## Frontend package structure

```
frontend/
│
├── app/                          # Next.js App Router
│   ├── (auth)/
│   │   └── login/
│   ├── dashboard/
│   ├── properties/
│   │   └── [id]/
│   │       └── deals/
│   │           └── [dealId]/
│   └── deals/
│       └── [id]/
│           └── analysis/
│
├── components/
│   ├── deal/
│   │   ├── DealInputForm.tsx
│   │   ├── DealSummary.tsx
│   │   └── SnapshotHistory.tsx
│   ├── analysis/
│   │   ├── CashFlowWaterfall.tsx
│   │   ├── AcquisitionCostBreakdown.tsx
│   │   ├── SDLTBreakdown.tsx
│   │   ├── YieldMetrics.tsx
│   │   └── RiskFlagList.tsx
│   └── ui/                       # Shared UI primitives
│
├── lib/
│   ├── api/                      # Typed API client — all HTTP calls
│   │   ├── calculations.ts
│   │   ├── deals.ts
│   │   ├── snapshots.ts
│   │   └── client.ts             # Base client with JWT attachment
│   └── types/                    # TypeScript types mirroring API contracts
│
└── hooks/                        # Data fetching hooks
```

---

---

# Part 15 — Scaling Considerations

Phase 1 is intentionally simple. The architecture is designed to scale
gracefully without requiring structural changes to accommodate growth.

---

## What scales without architecture changes

**Calculation throughput:** The underwriting engine is pure in-memory
computation with no I/O. Horizontal scaling of the FastAPI process (multiple
Railway instances behind a load balancer) increases calculation throughput
linearly. No shared mutable state exists between processes.

**Snapshot read throughput:** Snapshots are immutable after creation. A read
replica of PostgreSQL can serve all snapshot read traffic without any
application code changes. Read replicas are a database infrastructure concern,
not an application concern.

**Configuration loading:** Configuration records are append-only and rarely
change. They are safe to cache at the process level in later phases. A simple
in-process cache (with invalidation on configuration insert) reduces database
load significantly.

---

## What requires architecture changes at scale

**Background enrichment (Phase 3):** Area intelligence requires async external
API calls. This requires introducing a task queue (Redis + ARQ or similar).
The application code changes are additive — new worker processes and new
task definitions. Existing synchronous flows are unaffected.

**Portfolio analytics queries (Phase 4):** Aggregating across many snapshots
for portfolio-level metrics may require read replicas or a separate analytics
pipeline. The snapshot schema is designed to support this (standardised output
field names, queryable risk flag rows) without schema changes.

**Concurrent writes at high user volume:** PostgreSQL row-level locking handles
concurrent snapshot writes correctly. The append-only snapshot model means
there are no update contention patterns. The only update is
`Deal.latest_snapshot_id`, which is a single-row update per deal and does not
cause contention between deals.

---

## The Railway-to-production migration path

Phase 1 deploys on Railway with a single FastAPI process and a managed
PostgreSQL instance. The migration path to a more robust production
infrastructure (AWS, GCP, or similar) requires no application code changes:

- FastAPI process → containerised deployment (already Docker-based)
- PostgreSQL → managed RDS or Cloud SQL (connection string change only)
- Static assets → CDN (Next.js is already CDN-compatible)
- Background workers → separate container running the same codebase with a
  worker entrypoint

The architecture avoids any vendor-specific SDKs or infrastructure assumptions
in the application code, making this migration straightforward.

---

---

# Part 16 — What This Document Establishes as Invariants

The following are architectural invariants. They may not be changed without
a documented decision in DECISIONS.md.

1. **The engine package imports nothing from the application.** Zero tolerance.

2. **Calculations are never performed in the API layer.** Route handlers
   delegate to CalculationService.

3. **Snapshot creation is atomic.** All snapshot sub-records, the deal pointer
   update, and the audit log entry commit together or not at all.

4. **Snapshots are never updated or deleted.** The application database user
   has no UPDATE or DELETE privilege on snapshot tables.

5. **Configuration data is never overwritten.** All configuration changes
   produce new records with effective_from dates.

6. **AI systems read snapshot outputs; they never write to them.** The AI
   integration is a read-only consumer of calculated results.

7. **API routes are versioned from the first deployment.** /api/v1/ is the
   minimum prefix. No unversioned routes are exposed except /health.

8. **Ownership is verified in the service layer before any domain operation.**
   Not in the API layer, not in the repository layer.
