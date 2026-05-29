# PropIQ Platform — Application Service Architecture

## Purpose

This document defines the application service layer for the PropIQ platform.
It specifies the responsibilities, boundaries, interaction rules, flow
sequences, error handling strategy, and extension points for every application
service.

This document is architecture only. It contains no ORM code, no SQLAlchemy
definitions, no FastAPI routes, no DTO implementations, no migration files,
and no repository implementation.

All terminology matches DOMAIN_GLOSSARY.md.
All domain entities and aggregates are sourced from DOMAIN_MODEL_ARCHITECTURE.md.
All repository interfaces are sourced from REPOSITORY_ARCHITECTURE.md.
All persistence principles are sourced from PERSISTENCE_ARCHITECTURE.md.
All engine boundaries are sourced from ENGINE_ARCHITECTURE.md and ENGINE_CONTRACTS.md.
All governing architectural decisions trace to DECISIONS.md (ADR-001 through ADR-014).

---

## Document Status

Version: 1.0
Phase coverage: Phase 1 complete with Phase 2–5 extension design

---

---

# Part 1 — Application Service Philosophy

---

## 1.1 — Services Orchestrate; They Do Not Compute

The service layer is the orchestration layer of the application. It coordinates
domain entities, repositories, and the engine. It does not perform financial
calculations, does not contain formula logic, and does not make business
decisions that belong to the domain model.

The single most important statement about the service layer: **a service that
contains a yield formula is wrong**. Calculation belongs in the engine.
Persistence belongs in repositories. Business invariants belong in domain
entities. The service layer connects these components in the correct sequence
for a given operation.

---

## 1.2 — Services Are the Transaction Boundary

Transaction scope belongs to the service layer. Repositories perform individual
database operations; services define which operations must be atomic.

The service layer opens a database session at the start of each operation,
passes it to repositories as a dependency, and either commits or rolls back
at the end of the operation. Repositories do not commit or roll back — they
participate in transactions opened by services.

---

## 1.3 — Services Enforce Ownership; Repositories Do Not

Every service operation that accepts a user-provided resource identifier (a
deal ID, property ID, snapshot ID) verifies ownership before proceeding. A
resource belonging to a different user produces `NotFoundError` — not
`ForbiddenError`. Existence is never disclosed to non-owners.

This ownership check is a service responsibility, not a repository
responsibility, and not an API layer responsibility. Repositories expose
ownership-filtered query variants (`find_by_id_for_user`) but the decision
to call them is a service concern.

---

## 1.4 — Services Are Stateless

Services hold no mutable state between requests. Each service method
receives everything it needs through its parameters and dependencies.
No shared caches, no cross-request state, no singleton computation state.

The database session is the only stateful resource associated with a request,
and it is scoped to the request lifetime via dependency injection.

---

## 1.5 — The Trust-First Imperative

Every service operation that touches calculation data must honour the
trust-first principle (TRUST_MODEL.md, ADR-007). This means:
- Calculation inputs and outputs are never silently altered or inferred
- Snapshot creation is atomic — no partial results exist
- Audit trails are written on every calculation attempt, including failures
- User overrides always prevail over platform defaults (ADR-013)
- Calculation outputs are never generated or modified by AI (ADR-001)

---

---

# Part 2 — Service Catalogue

Seven application services are defined for Phase 1. Each has a single clearly
named responsibility. Services are injected by FastAPI's dependency injection
system.

```
CalculationService
    The most critical service. Orchestrates the end-to-end calculation
    pipeline from input receipt to snapshot persistence.

ConfigurationService
    Resolves active configuration versions and translates them into the
    EngineConfig and ConfigVersionRefs needed by the calculation pipeline.

SnapshotService
    Persists completed calculation results as immutable snapshots.
    Provides snapshot reading operations for display and history.

DealService
    Manages the mutable deal workspace: creation, input updates, status
    transitions, and deal listing.

PropertyService
    Manages property records: creation, updates, and listing.

UserService
    Manages platform user records and investor profiles.

AuditService
    Writes calculation audit events. Called on every calculation attempt
    regardless of outcome.
```

---

---

# Part 3 — Service Boundaries

---

## 3.1 — What Each Service Owns

```
CalculationService owns:
    The calculation pipeline (ownership check → config → defaults → engine → snapshot)
    EngineInput assembly
    EngineConfig assembly (via ConfigurationService)
    Input default resolution (via ConfigurationService)
    Calculation outcome routing (success / validation failure / engine error)

ConfigurationService owns:
    Active configuration version resolution
    Configuration domain-to-engine-contract translation
    Input default resolution logic (which optional inputs get which defaults)
    Version-specific configuration loading (for reproducibility)

SnapshotService owns:
    Snapshot aggregate persistence (atomic write of all sub-tables)
    Snapshot read operations (summary, display, full, history)
    Supersession marking (is_superseded transition)
    Snapshot-level access: reading and providing snapshot data to other services

DealService owns:
    Deal creation
    Deal working input updates
    Deal status transitions (via DealStatusTransitionService)
    Deal listing and retrieval
    Deal archival

PropertyService owns:
    Property creation
    Property updates
    Property listing and retrieval
    Property archival

UserService owns:
    User platform record creation and updates
    Investor profile management (create, update, list, archive, set default)
    User status transitions

AuditService owns:
    Writing calculation audit events
    Reading calculation audit history (for display and reporting)
```

---

## 3.2 — What Each Service Does Not Own

```
CalculationService does NOT own:
    Formula logic (that is the engine)
    Snapshot reading (that is SnapshotService)
    Configuration storage (that is ConfigurationService)
    Audit entry structure (that is AuditService)

ConfigurationService does NOT own:
    Configuration table writes (admin operations handled separately)
    Default resolution for required inputs (those have no default)
    Engine formula behaviour

SnapshotService does NOT own:
    Engine result production (it receives EngineResult, does not produce it)
    Deal working input state (that is DealService)
    Configuration version selection (that is ConfigurationService)

DealService does NOT own:
    Calculations (it provides inputs to CalculationService)
    Snapshot content (it references snapshots by ID, does not load them)
    Property data (it references properties by ID)

AuditService does NOT own:
    Calculation logic
    Audit entry reads for user-facing deal history (that is SnapshotService
    and DealService which provide combined views)
```

---

## 3.3 — Service Dependency Rules

Services may call other services. The permitted calling relationships are:

```
CalculationService → ConfigurationService (for config loading)
CalculationService → SnapshotService (for snapshot creation on success)
CalculationService → AuditService (for all calculation audit events)
CalculationService → DealService (for ownership check and deal loading)

SnapshotService → (no other services — only repositories)

DealService → (no other services — only repositories and DealStatusTransitionService)

PropertyService → (no other services — only repositories)

UserService → (no other services — only repositories)

AuditService → (no other services — only AuditRepository)
```

**SnapshotService does not call CalculationService.** There is no circular
dependency. The flow is: CalculationService calls engine, then calls
SnapshotService to persist the result.

**DealService does not call CalculationService.** A user editing deal inputs
and a user triggering a calculation are two separate operations. DealService
does not trigger recalculation when working inputs change — that is an
explicit user action routed through CalculationService.

---

## 3.4 — Services Never Call the Engine Directly Except CalculationService

The engine is called in exactly one place in the entire application:
`CalculationService`. No other service, no repository, and no API route handler
may call `engine.run()` directly.

This is an architectural invariant enforced by module structure. If any service
other than `CalculationService` imports `engine.run`, that is a critical
defect.

---

---

# Part 4 — Request Lifecycle

Every service method follows the same structural lifecycle:

```
1. AUTHORISE
   Verify the authenticated user has permission for this operation.
   For user-owned resources: call the ownership-filtered repository variant.
   Return NotFoundError (not ForbiddenError) if the resource does not exist
   or belongs to a different user.

2. VALIDATE (domain-level, not engine-level)
   Apply any domain invariant checks that belong to the service layer.
   Examples: status transition validity, field immutability checks.
   These are not engine validation rules — they are domain operation guards.

3. LOAD DEPENDENCIES
   Load any other domain entities required for this operation.
   Always use the ownership-filtered variants for user-owned resources.

4. EXECUTE OPERATION
   Perform the core business operation: call engine, mutate domain entity,
   or read data.

5. PERSIST
   Call the appropriate repository methods to persist the result.
   Open a transaction if the operation requires atomicity across multiple writes.

6. WRITE AUDIT (if applicable)
   Write any audit log entries required by this operation.

7. RETURN RESULT
   Return a service result type to the API layer.
   Never return domain entities directly to the API layer.
   Always return a service-layer result type (DTO or structured result).
```

---

---

# Part 5 — CalculationService

The most important service in the application. Every design decision here
must preserve the trust-first principle, the engine boundary, and the
immutable snapshot guarantee.

---

## 5.1 — Primary Method: run_calculation

```
CalculationService.run_calculation(
    user_id: UUID,
    deal_id: UUID,
    raw_inputs: RawCalculationInputs,
    calculation_date: date,
    client_context: str | None
) → CalculationResult
```

`RawCalculationInputs` is the service layer's representation of inputs from
the API layer — a plain dictionary or typed struct of user-provided values,
with each optional field either present (user value) or absent (to be
defaulted). It is the bridge between the API layer's request DTO and the
engine's `EngineInput`.

`CalculationResult` is a discriminated union:

```
CalculationResult = CalculationSuccess | CalculationValidationFailure | CalculationError

CalculationSuccess:
    snapshot_id: UUID
    snapshot_summary: SnapshotSummary     (loaded from SnapshotService after save)
    deal_status_after: DealStatus

CalculationValidationFailure:
    hard_errors: List[ValidationError]
    warnings: List[ValidationWarning]

CalculationError:
    message: str                          (sanitised; no stack trace)
```

---

## 5.2 — Calculation Orchestration Flow (Complete)

```
CalculationService.run_calculation(user_id, deal_id, raw_inputs, calculation_date, client_context)

STEP 1 — Ownership verification
    deal = DealRepository.find_by_id_for_user(deal_id, user_id)
    if deal is None:
        raise NotFoundError(entity="deal", id=deal_id)

STEP 2 — Domain precondition check
    if deal.status == DealStatus.ARCHIVED:
        raise DomainError("Cannot calculate on an archived deal")

STEP 3 — Load active configuration
    config_bundle = ConfigurationService.load_for_calculation(calculation_date)
    # config_bundle.engine_config  → passed to engine
    # config_bundle.version_refs   → stored in snapshot; never passed to engine

STEP 4 — Resolve input defaults (ADR-013 — user override always prevails)
    resolved_inputs, input_sources = ConfigurationService.resolve_defaults(
        raw_inputs=raw_inputs,
        assumption_config=config_bundle.assumption_config_domain,
        ownership_structure=raw_inputs.ownership_structure
    )
    # resolved_inputs: all optional fields populated (user value or config default)
    # input_sources: InputSource per optional field (USER_OVERRIDE or CONFIG_DEFAULT)

STEP 5 — Assemble EngineInput
    engine_input = assemble_engine_input(resolved_inputs)
    # engine_input is fully populated — no nulls for optional fields
    # engine_input contains no UUIDs, no database references, no metadata

STEP 6 — Call the engine
    engine_result = engine.run(engine_input, config_bundle.engine_config)

STEP 7 — Route on engine result type

    --- PATH A: ValidationResult (is_valid = False) ---
    if isinstance(engine_result, ValidationResult) and not engine_result.is_valid:
        audit_event = CalculationAuditEvent(
            user_id=user_id,
            deal_id=deal_id,
            snapshot_id=None,
            triggered_at=utcnow(),
            outcome=CalculationOutcome.VALIDATION_FAILURE,
            engine_version=ENGINE_VERSION,
            validation_errors=engine_result.hard_errors,
            client_context=client_context
        )
        AuditService.write_failure(audit_event)
        # AuditService uses a fresh session — independent of any transaction
        return CalculationValidationFailure(
            hard_errors=engine_result.hard_errors,
            warnings=engine_result.warnings
        )

    --- PATH B: EngineError ---
    if isinstance(engine_result, EngineError):
        audit_event = CalculationAuditEvent(
            user_id=user_id,
            deal_id=deal_id,
            snapshot_id=None,
            triggered_at=utcnow(),
            outcome=CalculationOutcome.ENGINE_ERROR,
            engine_version=ENGINE_VERSION,
            error_detail=engine_result.detail,
            client_context=client_context
        )
        AuditService.write_failure(audit_event)
        return CalculationError(message="Calculation could not be completed.")

    --- PATH C: EngineResult (success) ---
    snapshot_id = generate_uuid()
    calculated_at = utcnow()
    audit_event = CalculationAuditEvent(
        user_id=user_id,
        deal_id=deal_id,
        snapshot_id=snapshot_id,
        triggered_at=calculated_at,
        outcome=CalculationOutcome.SUCCESS,
        engine_version=ENGINE_VERSION,
        client_context=client_context
    )
    snapshot = build_snapshot_from_engine_result(
        snapshot_id=snapshot_id,
        deal_id=deal_id,
        user_id=user_id,
        engine_result=engine_result,
        engine_input=engine_input,
        input_sources=input_sources,
        config_version_refs=config_bundle.version_refs,
        calculated_at=calculated_at
    )

STEP 8 — Persist (atomic)
    SnapshotService.save_snapshot_and_update_deal(
        snapshot=snapshot,
        deal=deal,
        audit_event=audit_event
    )
    # SnapshotService orchestrates the atomic transaction:
    # INSERT snapshot_calculations
    # INSERT snapshot_inputs
    # INSERT snapshot_outputs
    # INSERT snapshot_intermediates
    # INSERT snapshot_risk_flags (one per flag)
    # INSERT snapshot_validation_warnings (one per warning)
    # UPDATE deals.latest_snapshot_id = snapshot_id
    # INSERT audit_calculations
    # COMMIT

STEP 9 — Load summary for response
    snapshot_summary = SnapshotService.get_display_summary(snapshot_id)

STEP 10 — Return result
    return CalculationSuccess(
        snapshot_id=snapshot_id,
        snapshot_summary=snapshot_summary,
        deal_status_after=DealStatus.ANALYSED
    )
```

---

## 5.3 — Recalculation: Current Assumptions

```
CalculationService.recalculate_with_current_assumptions(
    user_id: UUID,
    deal_id: UUID,
    calculation_date: date,
    client_context: str | None
) → CalculationResult
```

This method uses the deal's current working inputs (from the deal record) and
the latest active configuration. It follows the identical flow to `run_calculation`
except that `raw_inputs` is constructed from `deal.working_inputs` rather than
from an API request body.

The previous snapshot's `is_superseded` flag is NOT updated in this flow —
the `SnapshotService.save_snapshot_and_update_deal` call updates
`latest_snapshot_id` on the deal, and the previous snapshot is independently
marked superseded.

```
ADDITIONAL STEP — After successful snapshot save:
    if previous_snapshot_id is not None:
        SnapshotService.mark_superseded(
            snapshot_id=previous_snapshot_id,
            superseded_at=calculated_at
        )
```

This step is performed after the main transaction commits, not inside it.
The supersession mark is a status flag, not a data mutation. If it fails,
the new snapshot still exists and is accessible. The deal's `latest_snapshot_id`
is the authoritative "current" pointer.

---

## 5.4 — Recalculation: Reproduce Original

```
CalculationService.reproduce_original(
    user_id: UUID,
    source_snapshot_id: UUID,
    calculation_date: date,
    client_context: str | None
) → CalculationResult
```

**Purpose:** Run the engine with the exact same inputs and configuration as
a historical snapshot to verify the result is reproducible. Used for audit
and trust verification.

**Flow:**
```
STEP 1 — Load original snapshot (inputs only, for reconstruction)
    original = SnapshotService.get_snapshot_inputs_only(
        snapshot_id=source_snapshot_id,
        user_id=user_id
    )
    if original is None:
        raise NotFoundError(entity="snapshot", id=source_snapshot_id)

STEP 2 — Load the specific configuration versions from the original snapshot
    config_bundle = ConfigurationService.load_specific_versions(
        version_refs=original.config_version_refs
    )
    # This guarantees EngineConfig matches what was used at original calculation time

STEP 3 — Reconstruct EngineInput from original snapshot inputs
    engine_input = reconstruct_engine_input_from_snapshot(original.inputs)
    # input_sources are the same as recorded in original.inputs._source fields

STEP 4 — Run engine
    engine_result = engine.run(engine_input, config_bundle.engine_config)

STEP 5 — Compare with original outputs
    is_reproducible = compare_outputs(
        engine_result.outputs, original.snapshot_id
    )
    # Logs a discrepancy if outputs differ — should never happen
    # A discrepancy indicates an engine version change that was not properly versioned

STEP 6 — Save new reproduction snapshot
    [follows standard snapshot save flow]
    [new snapshot is NOT marked as superseding the original — Variant B]
    [deal.latest_snapshot_id is NOT updated]

STEP 7 — Return
    return CalculationSuccess with reproduction flag and is_reproducible result
```

**Important:** In Variant B (reproduce original), `deals.latest_snapshot_id`
is NOT updated. The original analysis remains the "current" one. The
reproduction is saved as a new immutable record tagged for audit purposes
but does not change which analysis the user sees by default.

---

---

# Part 6 — Snapshot Creation Flow (SnapshotService)

---

## 6.1 — Primary Method: save_snapshot_and_update_deal

```
SnapshotService.save_snapshot_and_update_deal(
    snapshot: CalculationSnapshot,
    deal: Deal,
    audit_event: CalculationAuditEvent
) → None
```

This is the atomic transaction that defines Phase 1's most important data
integrity guarantee.

```
BEGIN TRANSACTION (using injected async session)

    1. SnapshotRepository.save(snapshot)
       This repository method internally executes:
         INSERT snapshot_calculations
         INSERT snapshot_inputs         (with all _source fields)
         INSERT snapshot_outputs
         INSERT snapshot_intermediates  (including JSONB sdlt_band_breakdown)
         INSERT snapshot_risk_flags     (one row per flag)
         INSERT snapshot_validation_warnings  (one row per warning)
         UPDATE deals SET latest_snapshot_id = :snapshot_id,
                          status = 'ANALYSED',
                          updated_at = NOW()
                          WHERE id = :deal_id

    2. AuditRepository.save(audit_event)
         INSERT audit_calculations

COMMIT

If any step raises: ROLLBACK entire transaction
```

**Why the audit event is inside the snapshot transaction:**
If the snapshot persists but the audit event fails, there is a success on
record (the snapshot) but no audit trail for it. This would be a trust
violation — an analysis exists with no record of when it was created or
who triggered it. By including the audit INSERT in the snapshot transaction,
either both exist or neither does.

---

## 6.2 — Read Methods

```
SnapshotService.get_display_summary(snapshot_id: UUID) → SnapshotSummary | None
    Loads: root + outputs + risk_flags + warnings (no intermediates)
    Used for: deal summary display, API response after calculation

SnapshotService.get_full_snapshot(
    snapshot_id: UUID,
    user_id: UUID
) → CalculationSnapshot | None
    Loads: full aggregate including intermediates
    Used for: audit display, reproducibility verification
    Ownership verified via deal ownership

SnapshotService.get_snapshot_inputs_only(
    snapshot_id: UUID,
    user_id: UUID
) → SnapshotInputsView | None
    Loads: root + inputs only
    Used for: recalculation input reconstruction
    Returns a view type, not the full aggregate

SnapshotService.get_history_for_deal(
    deal_id: UUID,
    user_id: UUID
) → List[SnapshotHistoryEntry]
    Loads: aggregated root + key output metrics + flag counts
    Returns history list ordered by calculated_at DESC
    Ownership verified via deal ownership

SnapshotService.mark_superseded(snapshot_id: UUID, superseded_at: datetime) → None
    Applies is_superseded = true status transition
    Called by CalculationService after a new snapshot is created
```

---

---

# Part 7 — Validation Failure Flow

When the engine returns `ValidationResult` with `is_valid = false`:

```
STEP 1 — CalculationService receives ValidationResult from engine.run()

STEP 2 — Assemble audit event
    audit_event = CalculationAuditEvent(
        outcome=VALIDATION_FAILURE,
        validation_errors=validation_result.hard_errors,
        snapshot_id=None,
        ...
    )

STEP 3 — Write audit event
    AuditService.write_failure(audit_event)
    # Uses a FRESH database session, independent of any transaction
    # The main calculation flow has no open transaction at this point
    # The audit write is its own atomic commit

STEP 4 — Return structured failure to API layer
    return CalculationValidationFailure(
        hard_errors=validation_result.hard_errors,
        warnings=validation_result.warnings
    )

API layer maps this to HTTP 422 with structured field errors.
No snapshot is created. No deal state changes.
```

**Key principle:** The validation failure path is entirely outside any
database transaction. No data was written before the failure (configuration
was loaded read-only; no snapshot was started). The audit event write is
the only write, and it uses its own connection.

---

---

# Part 8 — Engine Error Flow

When the engine returns `EngineError` (an unexpected internal failure that
validation did not catch):

```
STEP 1 — CalculationService receives EngineError from engine.run()

STEP 2 — Log the error details server-side
    # EngineError contains error_code and detail string
    # These are logged internally (structured application logging)
    # They are NEVER included in the API response or audit event detail
    # that is returned to the user
    server_log.error(
        event="engine_error",
        error_code=engine_error.error_code,
        engine_version=engine_error.engine_version,
        deal_id=deal_id,
        user_id=user_id
    )

STEP 3 — Assemble sanitised audit event
    audit_event = CalculationAuditEvent(
        outcome=ENGINE_ERROR,
        error_detail="Engine computation failed. See server logs for detail.",
        snapshot_id=None,
        ...
    )
    # error_detail is a generic string — no internal error codes in the audit record
    # that would be returned to users. Server-side logs hold the real detail.

STEP 4 — Write audit event (fresh session)
    AuditService.write_failure(audit_event)

STEP 5 — Return sanitised error to API layer
    return CalculationError(message="Calculation could not be completed.")

API layer maps this to HTTP 500 with generic message.
```

**The two-log approach:** Engine errors produce two records: a server-side
structured log entry with full technical detail (for developers), and an
audit event with sanitised detail (for operational audit). Users see only
the generic API response message.

---

---

# Part 9 — Configuration Resolution Flow (ConfigurationService)

---

## 9.1 — Standard Resolution (for new calculations)

```
ConfigurationService.load_for_calculation(calculation_date: date) → ConfigBundle
```

```
STEP 1 — Load active SDLT configuration
    sdlt_config = ConfigurationRepository.find_active_sdlt_config(calculation_date)
    # Returns SDLTConfiguration with all bands loaded

STEP 2 — Load active Corporation Tax configuration
    ct_config = ConfigurationRepository.find_active_corporation_tax_config(calculation_date)

STEP 3 — Load active Assumption configuration
    assumption_config = ConfigurationRepository.find_active_assumption_config(calculation_date)

STEP 4 — Translate to EngineConfig (plain values only; no UUIDs)
    engine_config = EngineConfig(
        sdlt_config=SDLTConfig(
            bands=[SDLTBand(band_lower=b.band_lower, band_upper=b.band_upper, rate=b.rate)
                   for b in sdlt_config.bands],
            additional_dwelling_surcharge_rate=sdlt_config.additional_dwelling_surcharge_rate
        ),
        corporation_tax_config=CorporationTaxConfig(
            small_profits_rate=ct_config.small_profits_rate,
            small_profits_upper_threshold=ct_config.small_profits_upper_threshold,
            main_rate=ct_config.main_rate,
            main_rate_lower_threshold=ct_config.main_rate_lower_threshold,
            marginal_relief_numerator=ct_config.marginal_relief_numerator,
            marginal_relief_denominator=ct_config.marginal_relief_denominator
        ),
        assumption_config=AssumptionConfig(
            void_rate_percent_default=assumption_config.void_rate_percent_default,
            letting_agent_fee_percent_default=assumption_config.letting_agent_fee_percent_default,
            letting_agent_vat_rate_percent=assumption_config.letting_agent_vat_rate_percent,
            maintenance_reserve_percent_default=assumption_config.maintenance_reserve_percent_default,
            landlord_insurance_annual_default=assumption_config.landlord_insurance_annual_default,
            purchase_legal_costs_default=assumption_config.purchase_legal_costs_default,
            accountancy_cost_individual_default=assumption_config.accountancy_cost_individual_default,
            accountancy_cost_ltd_default=assumption_config.accountancy_cost_ltd_default,
            stress_test_rate_percent=assumption_config.stress_test_rate_percent,
            icr_threshold_basic_rate_percent=assumption_config.icr_threshold_basic_rate_percent,
            icr_threshold_higher_rate_percent=assumption_config.icr_threshold_higher_rate_percent
        )
    )

STEP 5 — Collect version IDs (for snapshot persistence; NOT for engine)
    version_refs = ConfigVersionRefs(
        sdlt_config_version_id=sdlt_config.id,
        corporation_tax_config_version_id=ct_config.id,
        assumption_config_version_id=assumption_config.id
    )

STEP 6 — Return ConfigBundle
    return ConfigBundle(
        engine_config=engine_config,
        version_refs=version_refs,
        assumption_config_domain=assumption_config   # retained for default resolution
    )
```

**ConfigBundle carries `assumption_config_domain`** — the domain entity form
of the assumption config — because `resolve_defaults` (Step 9.2 below) needs
the default values as domain entities, not just as the EngineConfig representation.
The engine never sees this; it is used before `engine.run()` is called.

---

## 9.2 — Input Default Resolution (enforcing ADR-013)

```
ConfigurationService.resolve_defaults(
    raw_inputs: RawCalculationInputs,
    assumption_config: AssumptionConfiguration,
    ownership_structure: OwnershipStructure
) → (resolved_inputs: ResolvedInputs, input_sources: InputSourceMap)
```

For each optional input field, the resolution rule is:

```
if raw_inputs.<field> is not None:
    resolved_inputs.<field> = raw_inputs.<field>
    input_sources.<field> = InputSource.USER_OVERRIDE

else:
    resolved_inputs.<field> = assumption_config.<field>_default
    input_sources.<field> = InputSource.CONFIG_DEFAULT
```

Special case — accountancy cost:
```
if raw_inputs.annual_accountancy_cost is not None:
    resolved_inputs.annual_accountancy_cost = raw_inputs.annual_accountancy_cost
    input_sources.annual_accountancy_cost = InputSource.USER_OVERRIDE
else if ownership_structure == INDIVIDUAL:
    resolved_inputs.annual_accountancy_cost = assumption_config.accountancy_cost_individual_default
    input_sources.annual_accountancy_cost = InputSource.CONFIG_DEFAULT
else:  # LIMITED_COMPANY
    resolved_inputs.annual_accountancy_cost = assumption_config.accountancy_cost_ltd_default
    input_sources.annual_accountancy_cost = InputSource.CONFIG_DEFAULT
```

Required inputs (`purchase_price`, `monthly_rent`, `deposit_amount`, etc.)
are never defaulted. They are validated by the engine's validation pipeline.
If they are absent from `raw_inputs`, the engine's validation will return
a HARD failure. `resolve_defaults` only processes optional inputs.

---

## 9.3 — Version-Specific Resolution (for reproducibility)

```
ConfigurationService.load_specific_versions(
    version_refs: ConfigVersionRefs
) → ConfigBundle
```

```
STEP 1 — Load each configuration by its specific UUID
    sdlt_config = ConfigurationRepository.find_sdlt_config_by_id(
        version_refs.sdlt_config_version_id
    )
    ct_config = ConfigurationRepository.find_corporation_tax_config_by_id(
        version_refs.corporation_tax_config_version_id
    )
    assumption_config = ConfigurationRepository.find_assumption_config_by_id(
        version_refs.assumption_config_version_id
    )

    if any are None: raise ConfigurationNotFoundError
    # A missing specific version means either data corruption or the version
    # IDs in the snapshot are wrong — both are critical integrity violations

STEP 2 — Translate to EngineConfig (same as standard resolution)
    [identical to Steps 4-6 in standard resolution]
```

The engine receives identical `EngineConfig` whether loading by date or
by specific version ID. The engine is unaware of which loading path was used.

---

---

# Part 10 — Ownership Verification Flow

Ownership verification is applied at the start of every service operation
that accepts a user-provided resource identifier.

---

## 10.1 — Standard Pattern

```
def get_deal_or_raise(deal_id: UUID, user_id: UUID, repository: IDealRepository) → Deal:
    deal = repository.find_by_id_for_user(deal_id, user_id)
    if deal is None:
        raise NotFoundError(entity="deal", id=deal_id)
    return deal
```

This pattern is repeated for every resource type. The `_for_user` repository
variant returns `None` for both "not found" and "found but wrong user".
The service raises `NotFoundError` in both cases.

**Never:**
```
deal = repository.find_by_id(deal_id)
if deal.user_id != user_id:
    raise ForbiddenError()
```

This pattern would disclose existence. A 403 confirms the resource exists.

---

## 10.2 — Snapshot Ownership Is Mediated Through Deals

Snapshots do not have direct user ownership checks. Snapshot access is always
mediated through the parent deal:

```
def get_snapshot_for_user(
    snapshot_id: UUID,
    user_id: UUID,
    snapshot_repo: ISnapshotRepository,
    deal_repo: IDealRepository
) → SnapshotSummary:
    snapshot = snapshot_repo.find_by_id_outputs_only(snapshot_id)
    if snapshot is None:
        raise NotFoundError(entity="snapshot", id=snapshot_id)
    # Verify the snapshot's deal belongs to this user
    deal = deal_repo.find_by_id_for_user(snapshot.deal_id, user_id)
    if deal is None:
        raise NotFoundError(entity="snapshot", id=snapshot_id)
    return snapshot
```

The user sees a 404 whether the snapshot doesn't exist, its deal doesn't exist,
or its deal belongs to a different user.

---

---

# Part 11 — Audit Orchestration (AuditService)

---

## 11.1 — Two Write Paths

```
AuditService.write_success(event: CalculationAuditEvent) → None
    Called INSIDE the snapshot creation transaction.
    Uses the same session as the snapshot writes.
    Commits atomically with the snapshot.

AuditService.write_failure(event: CalculationAuditEvent) → None
    Called OUTSIDE any transaction.
    Opens a FRESH database session.
    Commits independently.
    If this write fails, the failure is logged server-side but does NOT
    propagate as an error to the caller. The business outcome is unaffected.
```

**Why `write_success` and `write_failure` are separate methods:**
The session handling is different. `write_success` participates in an open
transaction; `write_failure` must be independent of any failed transaction.
Conflating these into one method would require complex session management
logic. Two methods with clear contracts are simpler and safer.

---

## 11.2 — AuditService Has No Read Methods for User-Facing Paths

`AuditService` is write-only in Phase 1. Audit history read operations
(the calculation history shown to a user) are provided by `SnapshotService`
and `DealService`, which present a more useful combined view of deal history.

The raw `audit_calculations` table is accessed directly only by admin
operations, which are out of scope for Phase 1 user-facing flows.

---

---

# Part 12 — DealService

---

## 12.1 — Create Deal

```
DealService.create_deal(
    user_id: UUID,
    property_id: UUID,
    label: str,
    investor_profile_id: UUID | None
) → Deal
```

```
STEP 1 — Verify property ownership
    property = PropertyRepository.find_by_id_for_user(property_id, user_id)
    if property is None: raise NotFoundError

STEP 2 — Optionally load investor profile for pre-population
    if investor_profile_id is not None:
        profile = InvestorProfileRepository.find_by_id_for_user(investor_profile_id, user_id)
        if profile is None: raise NotFoundError
    else:
        profile = InvestorProfileRepository.find_default_for_user(user_id)

STEP 3 — Construct deal
    deal = Deal(
        id=generate_uuid(),
        user_id=user_id,
        property_id=property_id,
        label=label,
        status=DealStatus.DRAFT,
        latest_snapshot_id=None,
        investor_profile_id=investor_profile_id,
        working_inputs=pre_populate_from_profile(profile)  # may be mostly null
    )

STEP 4 — Persist
    DealRepository.save(deal)

STEP 5 — Return
    return deal
```

---

## 12.2 — Update Working Inputs

```
DealService.update_working_inputs(
    user_id: UUID,
    deal_id: UUID,
    input_updates: DealInputUpdate
) → Deal
```

```
STEP 1 — Load and verify ownership
    deal = DealRepository.find_by_id_for_user(deal_id, user_id)
    if deal is None: raise NotFoundError

STEP 2 — Domain precondition check
    if deal.status == DealStatus.ARCHIVED:
        raise DomainError("Cannot update inputs on an archived deal")

STEP 3 — Apply updates to working inputs
    deal.working_inputs = merge_input_update(deal.working_inputs, input_updates)
    deal.updated_at = utcnow()

STEP 4 — Persist
    DealRepository.update(deal)

STEP 5 — Return updated deal
    return deal
```

**What this does NOT do:** Trigger recalculation. Input updates are saved
to the working inputs only. The user must explicitly trigger a calculation
via `CalculationService`. This is deliberate — calculations are explicit
user actions that produce permanent immutable records, not background
responses to every keystroke.

---

## 12.3 — Archive Deal

```
DealService.archive_deal(user_id: UUID, deal_id: UUID) → Deal
```

```
STEP 1 — Load and verify ownership
    deal = DealRepository.find_by_id_for_user(deal_id, user_id)
    if deal is None: raise NotFoundError

STEP 2 — Apply status transition
    new_status = DealStatusTransitionService.apply_transition(
        current=deal.status,
        transition=DealStatusTransition.ARCHIVE
    )
    # Raises DomainError if transition is not permitted (e.g. already ARCHIVED)

STEP 3 — Persist
    deal.status = new_status
    deal.updated_at = utcnow()
    DealRepository.update(deal)

STEP 4 — Return
    return deal
```

**Snapshots are unaffected by archiving.** The deal's snapshots remain fully
accessible through `SnapshotService`. Archiving is a workflow status change
only.

---

---

# Part 13 — PropertyService

---

## 13.1 — Create Property

```
PropertyService.create_property(
    user_id: UUID,
    address: PropertyAddress,
    property_type: PropertyType,
    tenure: Tenure,
    lease_details: LeaseDetails | None,
    bedrooms: int | None,
    epc_rating: str | None
) → Property
```

```
STEP 1 — Validate address
    PropertyAddress construction validates postcode format.
    If invalid: construction raises DomainError (not returned to here).

STEP 2 — Validate leasehold consistency
    if tenure == LEASEHOLD and lease_details is None:
        raise DomainError("Lease details required for leasehold properties")
    if tenure == FREEHOLD and lease_details is not None:
        raise DomainError("Lease details cannot be provided for freehold properties")

STEP 3 — Construct property
    property = Property(
        id=generate_uuid(),
        user_id=user_id,
        address=address,
        property_type=property_type,
        tenure=tenure,
        lease_details=lease_details,
        bedrooms=bedrooms,
        epc_rating=epc_rating,
        is_archived=False
    )

STEP 4 — Persist
    PropertyRepository.save(property)

STEP 5 — Return
    return property
```

---

---

# Part 14 — UserService

---

## 14.1 — Create or Retrieve User on Login

```
UserService.get_or_create_user(supabase_auth_id: UUID, email: str) → User
```

This is the service called on every authenticated request when establishing
the user session. It is idempotent — if the user already exists, it returns
the existing record.

```
STEP 1 — Check for existing user
    user = UserRepository.find_by_supabase_auth_id(supabase_auth_id)
    if user is not None:
        return user

STEP 2 — Create new user record
    user = User(
        id=generate_uuid(),
        supabase_auth_id=supabase_auth_id,
        email=email,
        status=UserStatus.ACTIVE
    )
    UserRepository.save(user)
    return user
```

---

## 14.2 — Create Investor Profile

```
UserService.create_investor_profile(
    user_id: UUID,
    label: str,
    ownership_structure: OwnershipStructure,
    income_tax_band: IncomeTaxBand | None,
    set_as_default: bool
) → InvestorProfile
```

Domain invariant enforced: `income_tax_band` required for INDIVIDUAL, null
for LIMITED_COMPANY. This is checked at domain entity construction time
before the repository is called.

If `set_as_default = True`, the service clears `is_default = False` on all
other profiles for the user before saving the new one. This is a multi-row
update and requires a transaction.

---

---

# Part 15 — DTO Boundaries

Service methods receive and return structured types. These service-layer
types are distinct from API layer DTOs (request/response models) and from
domain entities.

---

## 15.1 — Service Result Types

Service result types are the outputs of service methods, passed to the
API layer for serialisation. They are pure data containers with no behaviour.

```
Service returns domain entities when:
    The caller needs to do further domain operations with the object.
    Example: DealService.create_deal → Deal
             (CalculationService needs to read working_inputs from it)

Service returns projection/summary types when:
    The caller only needs to display or return the data.
    Example: SnapshotService.get_display_summary → SnapshotSummary
             (API layer only needs to serialise this)
```

---

## 15.2 — DTO Boundary at the API Layer

The API layer converts between service result types and HTTP request/response
shapes. This conversion (DTO mapping) belongs entirely in the API layer.

```
Service layer produces:    Domain entities / service result types
                                 ↓
API layer converts to:     Response DTOs (Pydantic models for FastAPI)

API layer receives:        Request DTOs (parsed Pydantic models)
                                 ↓
API layer converts to:     Service input types
                                 ↓
Service layer receives:    Service input types (typed service parameters)
```

**Service methods never accept Pydantic request models as parameters.**
The API layer extracts the relevant fields and passes them as typed service
parameters. This decouples service behaviour from API schema decisions.

---

## 15.3 — Key Service Input Types

```
RawCalculationInputs:
    Required field values as typed parameters (purchase_price: Decimal, etc.)
    Optional field values as nullable (void_rate_percent: Decimal | None)
    This is NOT a Pydantic model — it is a service layer typed struct.

DealInputUpdate:
    Partial update to working inputs — any field may be None (meaning "no change")
    Distinct from RawCalculationInputs (which represents a full calculation request)

ConfigBundle (internal to ConfigurationService → CalculationService flow):
    engine_config: EngineConfig
    version_refs: ConfigVersionRefs
    assumption_config_domain: AssumptionConfiguration
```

---

---

# Part 16 — Error Handling Strategy

---

## 16.1 — Domain Error Types

Services raise typed domain errors, not generic Python exceptions. The API
layer catches these and maps them to HTTP responses.

```
NotFoundError(entity: str, id: UUID)
    → HTTP 404
    Used when: entity not found OR belongs to different user

DomainError(message: str)
    → HTTP 422 (business rule violation)
    Used when: invalid state transition, domain constraint violated
    NOT used for engine validation failures (those use CalculationValidationFailure)

CalculationValidationFailure(hard_errors, warnings)
    → HTTP 422 (engine validation failed)
    Distinct from DomainError — carries structured field-level errors

CalculationError(message: str)
    → HTTP 500 (unexpected engine failure)
    message is always sanitised — no internal detail

ConfigurationNotFoundError(config_type: str, version_id: UUID | None)
    → HTTP 500 (data integrity issue — should never reach user)
    A missing active configuration is a critical operational error

PersistenceIntegrityError(detail: str)
    → HTTP 500
    Raised by repository layer when data integrity constraints are violated
    (e.g. snapshot sub-table is missing for a snapshot that should have one)

UnauthorisedAdminError()
    → HTTP 403
    Only raised for admin-only routes where the user is authenticated
    but lacks admin status (the only case where 403 is appropriate)
```

---

## 16.2 — Error Propagation Rules

**Errors propagate upward through layers without transformation until the API layer.**
A `NotFoundError` raised in `DealRepository.find_by_id_for_user` propagates
through `DealService` to the API route handler, which converts it to HTTP 404.
The service layer does not catch and re-wrap errors from the repository unless
it needs to add business context.

**Internal errors are logged before propagating.**
Any unexpected exception (not a typed domain error) caught in the service layer
is logged with full context (user_id, deal_id, operation name) before being
re-raised as an `InternalError` for the API layer to map to HTTP 500.

**Stack traces never reach the API response.**
The API layer's exception handler serialises only the error type and sanitised
message. Exception details, stack frames, and database query text are logged
server-side only.

**Engine errors are sanitised before the audit record.**
The internal `EngineError.detail` is logged server-side. The audit event
stores only a generic error description. Users and audit readers never see
raw engine error detail.

---

## 16.3 — The Audit Write Must Not Raise

`AuditService.write_failure()` must not raise an exception that propagates
to the caller. If the audit write fails (a database connection issue, for
example), the failure is logged server-side and the original error (validation
failure or engine error) is returned to the caller as normal. The user
receives the correct error response. The missing audit entry is an operational
concern, not a user-facing concern.

**Implementation note:** `write_failure` wraps its database write in a
try/except. On failure, it logs and returns silently. This is the only place
in the service layer where swallowing an exception is intentional and
documented.

---

---

# Part 17 — Service-to-Repository Interaction Rules

---

## 17.1 — Services Use Interfaces, Not Concrete Implementations

Service methods declare their repository dependencies using the interface
types defined in REPOSITORY_ARCHITECTURE.md:

```
class CalculationService:
    def __init__(
        self,
        deal_repo: IDealRepository,
        config_repo: IConfigurationRepository,
        snapshot_repo: ISnapshotRepository,
        audit_repo: IAuditRepository,
        config_service: ConfigurationService
    ): ...
```

This makes services independently testable with in-memory repository
implementations without requiring a database.

---

## 17.2 — Services Inject the Database Session Into Repositories

The session is injected as a dependency. Services pass the session to
repositories; repositories do not open their own sessions.

```
async def run_calculation(self, ..., session: AsyncSession) → CalculationResult:
    deal = await self.deal_repo.find_by_id_for_user(deal_id, user_id, session=session)
    ...
    async with session.begin():
        await self.snapshot_repo.save(snapshot, session=session)
        await self.audit_repo.save(audit_event, session=session)
    ...
```

---

## 17.3 — Services Never Access Persistence Models

Services never import, instantiate, or reference SQLAlchemy model classes.
The repository interface is the only permitted abstraction. If a service
references `SnapshotCalculationRow` or any ORM class, that is a boundary
violation.

---

## 17.4 — Repository Results Are Treated as Trusted Domain Objects

When a repository returns a domain entity, the service layer treats it as
a correctly constructed domain object. The service does not re-validate
repository results against domain invariants.

The exception: when loading a snapshot for reproduction, `CalculationService`
verifies that the engine result matches the original outputs. This is not
domain validation — it is a reproducibility check.

---

---

# Part 18 — Service-to-Engine Interaction Rules

---

## 18.1 — One Call Point for the Engine

`engine.run()` is called in one place: `CalculationService`. This rule is
enforced by code organisation — the engine module is imported only in
`CalculationService`.

---

## 18.2 — EngineInput Is Assembled By CalculationService, Not the Engine

The assembly of `EngineInput` from `resolved_inputs` is a service
responsibility. The engine receives a fully formed `EngineInput` object.
It does not receive raw API inputs or partially formed data.

---

## 18.3 — EngineConfig Is Assembled By ConfigurationService

The service layer (specifically `ConfigurationService`) is responsible for
translating domain configuration entities into the plain-value `EngineConfig`
object. The engine never sees domain entity types or database UUIDs.

---

## 18.4 — The Engine Result Is Never Mutated

The `EngineResult` returned by `engine.run()` is never modified by the
service layer before being persisted. Intermediates, outputs, and flags are
stored exactly as the engine produced them. No service-layer "correction"
or "normalisation" of engine output is permitted.

---

## 18.5 — The Engine Version Constant Is the Authoritative Version Source

The `ENGINE_VERSION` constant from the engine module is used in all service
layer references to the current engine version. No service method hardcodes
a version string. The constant is the single source of truth.

---

---

# Part 19 — Future Workflow Service Extension Points

---

## 19.1 — WorkflowService (Phase 2+)

```
WorkflowService.record_workflow_event(
    user_id: UUID,
    deal_id: UUID,
    event_type: WorkflowEventType,
    event_data: dict
) → DealWorkflowEvent
```

`WorkflowService` is a new service that operates exclusively on
`deal_workflow_events`. It does not interact with `SnapshotService`,
`CalculationService`, or any configuration service. Workflow events are
orthogonal to calculations.

`DealService` gains a status vocabulary extension (new enum values) but its
existing methods are unchanged. The new status values participate in the
`DealStatusTransitionService` state machine, which gains new permitted
transitions.

---

## 19.2 — CalculationService Scenario Extensions (Phase 2+)

When scenario labelling is introduced (Phase 2), `run_calculation` gains
two optional parameters:

```
CalculationService.run_calculation(
    ...existing parameters...,
    scenario_label: str | None,    # Phase 2+
    scenario_type: str | None      # Phase 2+
) → CalculationResult
```

These are passed through to snapshot creation. The `SnapshotService.save_snapshot_and_update_deal`
method is extended to populate the nullable `scenario_label` and `scenario_type`
columns added to `snapshot_calculations` in Phase 2. No other changes are
required to any service.

---

## 19.3 — ScenarioComparisonService (Phase 2+)

```
ScenarioComparisonService.compare_snapshots(
    user_id: UUID,
    snapshot_a_id: UUID,
    snapshot_b_id: UUID,
    label: str | None
) → SnapshotComparison
```

This service loads two `SnapshotSummary` objects via `SnapshotService`,
computes the differences between their outputs at the service layer, and
optionally persists the comparison record. It is a pure addition — no
existing service is modified.

---

---

# Part 20 — Future Intelligence Service Extension Points

---

## 20.1 — AreaIntelligenceService (Phase 3+)

```
AreaIntelligenceService.get_area_intelligence_for_property(
    property_id: UUID,
    user_id: UUID
) → AreaIntelligenceSummary
```

This service is a read-only consumer of `intel_area_records`. It does not
interact with `CalculationService`, `SnapshotService`, or any configuration
service. Area intelligence is informational enrichment, not calculation input.

Phase 3 adds `AreaIntelligenceService` as a new service alongside existing
services. No existing service is modified.

---

## 20.2 — Intelligence Impact on Calculations (Phase 3+)

If future phases allow area intelligence data to inform calculation inputs
(e.g. platform-suggested rental estimate from area data), the flow is:

```
User reviews intelligence suggestion → explicitly accepts or overrides it
→ Value enters RawCalculationInputs as user_value with USER_OVERRIDE source
```

Area intelligence can suggest; it cannot inject values into calculations
without explicit user confirmation. `InputDefaultResolutionService` gains
a third source (`EXTERNAL_PROVIDER`) but the authority hierarchy (user >
config default > external provider) is enforced in the resolution logic.
The engine never changes.

---

## 20.3 — AISummaryService (Phase 5+)

```
AISummaryService.generate_summary_for_snapshot(
    snapshot_id: UUID,
    user_id: UUID,
    summary_type: AISummaryType
) → AISummary
```

`AISummaryService` is a new service. It:
1. Loads a `SnapshotSummary` via `SnapshotService` (read-only)
2. Calls the external AI API with snapshot output data
3. Persists the AI summary record via `IAISummaryRepository`
4. Returns the AI summary

It never calls `CalculationService`, never modifies any snapshot, and never
modifies any calculation output. The AI summary is stored and displayed
separately from all deterministic calculation data.

---

---

# Part 21 — Performance Expectations

All targets apply at expected Phase 1 scale (< 10,000 users, < 100,000 deals).

| Operation | Expected End-to-End Latency | Dominant Cost |
|---|---|---|
| `run_calculation` (full pipeline) | < 200ms P50 | Engine (~5ms) + DB writes (~50ms) |
| `get_display_summary` | < 50ms P50 | DB reads (3 queries) |
| `get_full_snapshot` | < 80ms P50 | DB reads (6 queries) |
| `update_working_inputs` | < 30ms P50 | Single DB write |
| `create_deal` | < 40ms P50 | 1-2 DB writes |
| `load_for_calculation` (config) | < 20ms P50 | 3 single-row indexed reads |

**The engine is not the bottleneck.** In-memory pure computation with no I/O
completes in single-digit milliseconds for a Phase 1 deal. Database I/O is
the dominant cost in all operations.

---

---

# Part 22 — Service Invariants

These invariants govern the service layer. Any implementation that violates
them introduces a correctness or trust defect.

```
SI-01  engine.run() is called only within CalculationService.
       No other service or API route may call the engine.

SI-02  EngineInput reaches the engine with all optional fields populated.
       No null optional fields in EngineInput when engine.run() is called.

SI-03  EngineConfig contains no UUIDs, no effective_from dates, no database
       identifiers. Configuration version IDs are held in ConfigVersionRefs,
       separate from EngineConfig.

SI-04  Every call to engine.run() is preceded by ownership verification.
       A calculation cannot be triggered on a deal the requesting user does
       not own.

SI-05  Every call to engine.run() produces exactly one audit event,
       regardless of outcome (success, validation failure, or engine error).

SI-06  The snapshot creation transaction is atomic.
       All snapshot sub-table writes, the deal pointer update, and the
       SUCCESS audit event commit together or none do.

SI-07  AuditService.write_failure() uses a fresh database session.
       It is independent of any failed or rolled-back transaction.

SI-08  AuditService.write_failure() does not propagate exceptions to its
       caller. Failure to write an audit event is an operational concern,
       not a user-facing error.

SI-09  EngineResult is never mutated by the service layer before persistence.
       Outputs, intermediates, and flags are stored exactly as the engine
       produced them.

SI-10  Services never return Pydantic request models to the API layer.
       Services return domain entities or typed service result types.
       DTO construction belongs to the API layer.

SI-11  Services never import SQLAlchemy ORM models.
       Repository interfaces are the only permitted abstraction.

SI-12  Services never call other repositories except through their declared
       dependencies. Cross-service repository access is not permitted.

SI-13  NotFoundError is raised for both "entity not found" and "entity belongs
       to a different user." ForbiddenError is never raised for user-owned
       resources. The only permitted use of ForbiddenError is for admin-only
       routes where the user is authenticated but lacks admin status.

SI-14  The engine version constant from the engine module is the authoritative
       source for the engine version string in all audit events and snapshots.
       No service hardcodes a version string.

SI-15  AI services are read-only consumers of snapshot data.
       No AI service modifies, corrects, or supplements any snapshot field.
       The AI service boundary from ADR-001 is enforced in service layer
       code by the absence of any write operation on snapshot entities from
       any AI service method.
```
