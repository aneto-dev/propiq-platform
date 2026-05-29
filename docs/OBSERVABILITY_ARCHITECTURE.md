# PropIQ Platform — Observability Architecture

## Purpose

This document defines the observability architecture for the PropIQ platform.
It specifies the logging strategy, structured log schema, correlation ID
design, metrics architecture, audit event observability, error and security
event observability, alerting philosophy, and production troubleshooting
workflows.

This document is architecture only. It contains no FastAPI code, no
SQLAlchemy models, no Alembic migrations, no DTO definitions, no API routes,
no OpenTelemetry configuration, no Grafana dashboards, no Prometheus
configuration, and no implementation code of any kind.

All terminology matches DOMAIN_GLOSSARY.md.
All layer boundaries align with APPLICATION_SERVICE_ARCHITECTURE.md.
All trust requirements align with TRUST_MODEL.md.
All engine boundaries align with ENGINE_ARCHITECTURE.md and ENGINE_CONTRACTS.md.
All security requirements align with AUTHORIZATION_MODEL.md.
All persistence constraints align with PERSISTENCE_ARCHITECTURE.md.
All architectural decisions trace to DECISIONS.md.

---

## Document Status

Version: 1.0
Phase coverage: Phase 1 complete with Phase 2–5 extension design

---

---

# Part 1 — Observability Philosophy

---

## 1.1 — Observability Is a Trust Requirement, Not a DevOps Nice-to-Have

PropIQ is a trust-first platform (TRUST_MODEL.md, ADR-007). Every calculation
must be traceable. Every snapshot must be attributable. Every audit event must
be permanent. These are not operational preferences — they are product
requirements that observability infrastructure must support.

A platform where a user cannot answer "why did my analysis produce this number
on that date?" has failed its trust obligation regardless of feature richness.
Observability is the operational expression of the same transparency that
immutable snapshots provide at the data layer.

---

## 1.2 — Three Observability Purposes, Clearly Separated

The platform generates observability data for three distinct purposes. Each
has different retention requirements, different audiences, and different
privacy implications. They must not be conflated.

**Operational observability:** Understanding the system's health and
performance in real time. Audience: engineers. Retention: short (30 days).
Content: latencies, error rates, queue depths, resource usage. Contains no
PII, no user data, no financial figures.

**Business observability:** Understanding how users interact with the platform.
Audience: product and engineering. Retention: medium (90 days). Content:
calculation counts, validation failure rates, risk flag distributions, deal
creation patterns. Aggregated — no individual user data in business metrics.

**Audit observability:** The permanent record of what happened for compliance,
reproducibility, and trust. Audience: platform operators, users (via their
own audit access), and potentially regulators. Retention: permanent for
calculation audit events; configurable for operational logs. Content: every
calculation attempt with its outcome, every configuration version change,
every admin action. The audit event data in `audit_calculations` is the
primary store; operational logs supplement it.

---

## 1.3 — The Engine Is Transparent by Design

The underwriting engine produces deterministic outputs from explicit inputs.
This means engine observability is primarily about measuring performance and
detecting anomalies, not about understanding what happened. What happened
is recorded completely in the snapshot (all inputs, all intermediates, all
outputs, all risk flags). Engine logs supplement the snapshot for operational
diagnosis; they are not the primary audit record.

---

## 1.4 — Structured Logging Is Mandatory

All log output is structured JSON. Free-text log lines are not acceptable
in production. Structured logs enable:
- Log filtering and search without regex parsing
- Aggregation across log entries with shared fields
- Correlation across layers via shared `correlation_id`
- Alerting on specific field values (e.g. `outcome = ENGINE_ERROR`)
- Future log ingestion into analytics pipelines

No log line may contain unstructured free-text where structured fields
would serve the purpose.

---

## 1.5 — PII and Financial Data Are Not in Logs

Logs must not contain:
- User email addresses
- User display names
- Property addresses
- Purchase prices, rent figures, or any financial calculation inputs or outputs
- Postcode at full precision (sector only: e.g. "NG1" not "NG1 1AA")
- Investor profile details (income tax band, ownership structure)

Logs contain identifiers (UUIDs) that can be correlated to actual data in
the database for authorised investigation. This separation means log storage
can be retained at lower security classification than the database.

---

---

# Part 2 — Logging Architecture

---

## 2.1 — Log Levels

```
DEBUG:  Verbose diagnostic information. Not emitted in production except under
        explicit diagnostic mode. Used during development and targeted production
        debugging with flag-based activation.

INFO:   Normal operational events. Request received, operation succeeded,
        configuration loaded. These are the baseline operational signals.

WARNING: Recoverable unexpected conditions. Audit write failure (handled),
         configuration version not found for a historical date (data integrity
         concern), unexpected validation warning patterns.

ERROR:  Operation failed. Engine error, persistence failure, unexpected
        exception caught at service boundary. Always requires investigation.

CRITICAL: Platform-level failures. Database unreachable, configuration tables
          empty, authentication service unreachable. Requires immediate
          operator response.
```

---

## 2.2 — Log Output Target

Phase 1 (Railway deployment): structured JSON to stdout/stderr. Railway
aggregates container output and provides basic log search. This is sufficient
for Phase 1 operational needs.

Phase 2+: structured JSON to a dedicated log aggregation service (e.g.
Datadog, Axiom, or Loki). The log output format does not change — the
destination changes. No application code changes are needed to migrate
between log destinations.

---

## 2.3 — Log Contexts by Layer

Each application layer has defined log context responsibilities:

```
API LAYER logs:
    - Request received (method, path, correlation_id, user_id)
    - Response sent (status_code, duration_ms, correlation_id)
    - Authentication failure (no user_id — just the failure type)
    - Admin route access (user_id, route, correlation_id)

SERVICE LAYER logs:
    - Operation started (service name, method, user_id, resource identifiers)
    - Operation succeeded (service name, method, duration_ms)
    - Domain error raised (error_type, entity, user_id)
    - Engine called (engine_version, deal_id, correlation_id)
    - Engine result received (outcome, duration_ms, flag count if success)
    - Audit write failure (severity=WARNING — swallowed but must be logged)

REPOSITORY LAYER logs:
    - Query executed (table, operation type, duration_ms)
    - Integrity error detected (table, violation type — no field values)
    - Configuration version loaded (config_type, version_id, effective_from)

ENGINE logs:
    - (Engine does not log. It returns structured results.)
    - Engine duration is measured by the CalculationService and logged there.

DATABASE / INFRASTRUCTURE:
    - Connection pool events
    - Slow query detection (queries > 500ms)
    - Connection errors
```

The engine itself never logs. It is a pure function that returns structured
results. The calling service layer measures engine execution duration and
logs it as part of the calculation event.

---

## 2.4 — Log Retention Policy

```
Operational logs (INFO and below):  30 days
Warning and error logs:             90 days
Critical logs:                      1 year
Audit calculation events:           Permanent (stored in database, not log files)
```

The permanent audit record lives in `audit_calculations`, not in log files.
Log files support operational diagnosis; the database is the authoritative
audit store.

---

---

# Part 3 — Structured Log Schema

Every log entry is a JSON object with a base set of fields plus event-specific
fields. The base fields are present on every log line. Event-specific fields
are defined per event type.

---

## 3.1 — Base Fields (every log entry)

```json
{
  "timestamp": "2025-06-01T14:23:07.412Z",
  "level": "INFO",
  "service": "propiq-backend",
  "environment": "production",
  "version": "1.0.0",
  "correlation_id": "req_7f3a9b2c-...",
  "event": "calculation.started",
  "message": "Calculation pipeline initiated"
}
```

| Field | Type | Content |
|---|---|---|
| `timestamp` | ISO8601 UTC | Log entry creation time |
| `level` | string | DEBUG / INFO / WARNING / ERROR / CRITICAL |
| `service` | string | "propiq-backend" or "propiq-worker" (Phase 3+) |
| `environment` | string | "production" / "staging" / "development" |
| `version` | string | Application deployment version |
| `correlation_id` | string | Trace-scoped correlation ID (see Part 4) |
| `event` | string | Dot-separated event identifier (see Part 3.2) |
| `message` | string | Human-readable description (no PII, no financial data) |

---

## 3.2 — Event Name Taxonomy

Event names follow a dot-separated hierarchical taxonomy:

```
<domain>.<entity>.<action>

Examples:
  api.request.received
  api.request.completed
  api.auth.failed
  calculation.pipeline.started
  calculation.engine.called
  calculation.engine.completed
  calculation.validation.failed
  calculation.engine_error.occurred
  calculation.snapshot.persisted
  calculation.audit.written
  calculation.audit.write_failed
  config.version.loaded
  config.version.inserted
  deal.created
  deal.updated
  deal.archived
  property.created
  snapshot.loaded
  snapshot.superseded
  repository.query.slow
  repository.integrity.error
  security.auth.token_invalid
  security.auth.token_expired
  security.admin.access
  security.ownership.denied
```

---

## 3.3 — Calculation Event Log Schema

The most important structured log events. These supplement the database
audit record.

**calculation.pipeline.started**
```json
{
  "event": "calculation.pipeline.started",
  "correlation_id": "req_...",
  "user_id": "usr_...",
  "deal_id": "deal_...",
  "engine_version": "1.0.0",
  "sdlt_config_version_id": "cfg_...",
  "corporation_tax_config_version_id": "cfg_...",
  "assumption_config_version_id": "cfg_...",
  "input_override_count": 3
}
```

`input_override_count` is the number of optional inputs the user provided
(as opposed to accepting defaults). No actual input values are logged.

**calculation.engine.completed** (success path)
```json
{
  "event": "calculation.engine.completed",
  "correlation_id": "req_...",
  "deal_id": "deal_...",
  "engine_version": "1.0.0",
  "outcome": "SUCCESS",
  "engine_duration_ms": 4,
  "risk_flag_count_high": 1,
  "risk_flag_count_medium": 0,
  "risk_flag_count_info": 2,
  "validation_warning_count": 1,
  "ownership_structure": "INDIVIDUAL",
  "tax_pathway": "SECTION_24"
}
```

Note: `tax_pathway` is structural (which code branch ran), not financial
data. `ownership_structure` is structural context, not PII.

**calculation.validation.failed**
```json
{
  "event": "calculation.validation.failed",
  "correlation_id": "req_...",
  "user_id": "usr_...",
  "deal_id": "deal_...",
  "engine_version": "1.0.0",
  "hard_error_count": 2,
  "warning_count": 1,
  "hard_error_codes": ["V-07", "V-15"]
}
```

Rule codes are logged (they are structural identifiers), not field values
or user-supplied data.

**calculation.engine_error.occurred**
```json
{
  "event": "calculation.engine_error.occurred",
  "level": "ERROR",
  "correlation_id": "req_...",
  "user_id": "usr_...",
  "deal_id": "deal_...",
  "engine_version": "1.0.0",
  "error_code": "DIVIDE_BY_ZERO",
  "stack_trace": "..."
}
```

Stack trace goes to server logs only. It is never included in audit records
or API responses.

**calculation.snapshot.persisted**
```json
{
  "event": "calculation.snapshot.persisted",
  "correlation_id": "req_...",
  "snapshot_id": "snap_...",
  "deal_id": "deal_...",
  "user_id": "usr_...",
  "engine_version": "1.0.0",
  "persistence_duration_ms": 47,
  "risk_flag_codes": ["NEGATIVE_CASHFLOW", "RENT_UNVERIFIED"]
}
```

---

## 3.4 — Security Event Log Schema

**security.auth.token_invalid**
```json
{
  "event": "security.auth.token_invalid",
  "level": "WARNING",
  "correlation_id": "req_...",
  "reason": "SIGNATURE_INVALID",
  "remote_ip": "82.x.x.x"
}
```

No user_id (identity not established). Remote IP is retained for security
analysis but is not considered PII for log retention purposes under UK GDPR
given the security context (legitimate interest).

**security.admin.access**
```json
{
  "event": "security.admin.access",
  "level": "INFO",
  "correlation_id": "req_...",
  "user_id": "usr_...",
  "route": "/api/v1/admin/config/sdlt",
  "operation": "INSERT_SDLT_VERSION"
}
```

Every admin route access is logged regardless of outcome.

**security.ownership.denied**
```json
{
  "event": "security.ownership.denied",
  "level": "WARNING",
  "correlation_id": "req_...",
  "user_id": "usr_...",
  "resource_type": "deal",
  "resource_id": "deal_..."
}
```

This fires when `find_by_id_for_user` returns None for an existing resource
(meaning the resource exists but belongs to another user). It is a WARNING
not an ERROR because it is not necessarily malicious — it may be a user
bookmarking a URL. Repeated patterns from the same user_id may indicate
probing and should be caught by alerting (see Part 20).

---

---

# Part 4 — Correlation ID Strategy

---

## 4.1 — What a Correlation ID Is

A correlation ID is a unique identifier assigned at the start of a request
that is carried through every log entry produced during that request's
lifecycle — across the API layer, service layer, repository layer, and
audit event.

Its purpose: given a user report of unexpected behaviour ("my calculation
on Tuesday produced a strange result"), an engineer can search all logs
for the relevant `correlation_id` and see the complete execution trace
of that request, from receipt to snapshot persistence.

---

## 4.2 — Correlation ID Generation and Propagation

```
GENERATION
  The API layer generates a UUID v4 correlation ID at the point of request
  receipt, before any other processing. This is the first action taken on
  any incoming request.
  Format: "req_" + UUID v4 (e.g. "req_7f3a9b2c-4e1d-4f89-b2d3-c9a8e4f2b1d0")
  The "req_" prefix distinguishes correlation IDs from other UUIDs in log search.

CLIENT-PROVIDED CORRELATION ID
  If the client provides an X-Correlation-ID header, this value is used instead
  of a generated UUID, after validating format (must be a valid UUID or
  "req_" prefixed UUID string). This supports client-side tracing for API
  integrations (Phase 3+).

PROPAGATION RULES
  The correlation_id is included in:
    — Every log entry produced during the request
    — The audit_calculations record (stored as a dedicated column)
    — The API response header: X-Correlation-ID: <correlation_id>
      (returned to the client for their own tracing)

  The correlation_id is NOT included in:
    — Snapshot records (snapshots have their own stable IDs)
    — Error responses returned to users (security: avoid leaking internal
      trace IDs to potential attackers scanning for patterns)
    — Database query parameters (it is a logging concern, not a DB concern)

  Within a single request, the correlation_id is available via a
  context variable (Python contextvars) — not via function parameters.
  Services and repositories read it from context when logging. They do not
  accept it as a method parameter. This keeps the domain/service API clean.
```

---

## 4.3 — Correlation ID in the Audit Record

The `audit_calculations` table gains a `correlation_id` column (TEXT, nullable
for backward compatibility with records written before this field was added):

```
audit_calculations.correlation_id: TEXT NULLABLE
```

This creates a permanent, queryable link between the server-side log trace
and the immutable audit record. An engineer investigating an anomaly can:

1. Find the audit record by `deal_id` and `triggered_at`
2. Extract the `correlation_id`
3. Search the log aggregation system for all entries with that `correlation_id`
4. See the complete request trace including engine timing and intermediate
   state that is not stored in the database

This is the bridge between ephemeral operational logs and permanent audit
records.

---

## 4.4 — Calculation-Scoped Trace Context

A calculation request may produce multiple units of work: configuration
loading, engine execution, snapshot persistence, and audit writing. These
all share the same `correlation_id`. The log stream for a single calculation
request will therefore contain entries from:

```
api.request.received         — correlation_id set
config.version.loaded (×3)  — same correlation_id
calculation.pipeline.started — same correlation_id
calculation.engine.called    — same correlation_id
calculation.engine.completed — same correlation_id
calculation.snapshot.persisted — same correlation_id
calculation.audit.written    — same correlation_id
api.request.completed        — same correlation_id
```

Filtering logs by a single `correlation_id` yields a complete trace of
one calculation event in temporal order.

---

---

# Part 5 — Request Tracing Strategy

---

## 5.1 — Phase 1: Correlation ID Is Sufficient

Phase 1 uses correlation IDs as the tracing mechanism. Full distributed
tracing (OpenTelemetry spans, Jaeger, Zipkin) is not implemented in Phase 1.

Rationale: Phase 1 is a single-service backend with synchronous request
handling and no distributed calls (no microservices, no message queues).
The added complexity of distributed tracing infrastructure is not justified
at this scale. Correlation IDs through structured logs provide the tracing
capability actually needed.

---

## 5.2 — Phase 3+ Tracing Extension

When Phase 3 introduces background jobs (area intelligence enrichment,
EPC lookups) and potentially external API calls, the tracing requirements
change. A background job triggered by a property creation cannot carry the
same HTTP correlation ID as the triggering request.

At that point, OpenTelemetry instrumentation is the recommended approach.
The design foundation is already in place: structured log fields and
correlation IDs are compatible with OpenTelemetry's trace/span model. The
`correlation_id` field maps to `trace_id`. Adding OpenTelemetry exporters
and SDK instrumentation is an additive change that does not require log
schema changes.

---

## 5.3 — External Service Calls

Phase 1 has no external API calls in the synchronous request path. When
Phase 3 introduces external data provider calls (Environment Agency, ONS,
Land Registry APIs), each external call must log:

```json
{
  "event": "external.api.called",
  "correlation_id": "req_...",
  "provider": "environment_agency_flood_risk",
  "endpoint": "flood_risk_v1",
  "duration_ms": 340,
  "status_code": 200,
  "cache_hit": false
}
```

External provider errors must log at WARNING or ERROR depending on whether
the failure is handled gracefully (WARN) or causes the operation to fail
(ERROR). The URL is logged but query parameters that might contain
postcode data are omitted from logs.

---

---

# Part 6 — Audit Event Architecture

---

## 6.1 — The Two-Layer Audit Model

PropIQ uses two complementary audit mechanisms:

**Layer 1 — Database audit events (`audit_calculations` table):**
Permanent, immutable, queryable, user-accessible. Records every calculation
attempt with its outcome. This is the authoritative audit record. Defined in
DATABASE_SCHEMA_DESIGN.md Section 5. Written by `AuditService`.

**Layer 2 — Structured log events:**
Operational, temporary (30–90 days), not user-accessible directly. Records
rich operational context that does not belong in the database: stack traces,
engine timing, query counts, correlation IDs. Supplements Layer 1 for
engineering diagnosis.

The two layers are linked via the `correlation_id` which appears in both the
`audit_calculations.correlation_id` column and in every associated log entry.

---

## 6.2 — What the Audit Record Covers

Every `audit_calculations` record covers one calculation attempt. One request
to `CalculationService.run_calculation` produces exactly one audit record,
regardless of outcome.

```
SUCCESS outcome:
    — snapshot_id is set
    — validation_errors is null
    — error_detail is null
    — correlation_id is set
    — engine_version is set

VALIDATION_FAILURE outcome:
    — snapshot_id is null
    — validation_errors contains structured list of {rule_code, field, message}
    — error_detail is null
    — correlation_id is set
    — engine_version is set

ENGINE_ERROR outcome:
    — snapshot_id is null
    — validation_errors is null
    — error_detail contains sanitised error description
    — correlation_id is set
    — engine_version is set
    — Full stack trace is in structured logs only (not in audit record)
```

---

## 6.3 — Audit Events for Configuration Changes (Phase 2+)

Phase 1 logs configuration inserts at the server INFO level. Phase 2
introduces `audit_config_changes` to provide a permanent database record
of every configuration version insertion:

```
audit_config_changes (Phase 2+):
    id
    config_table_name     ("config_sdlt_versions", etc.)
    config_version_id     (the inserted record's ID)
    admin_user_id         (who inserted it)
    notes                 (rationale for the change)
    correlation_id        (the admin request that triggered it)
    created_at
```

In Phase 1, the `config.version.inserted` log event serves this purpose.

---

## 6.4 — Audit Events for Snapshot Supersession

Snapshot supersession (`mark_superseded`) is not a new audit record — the
supersession status is visible on the `snapshot_calculations` record itself.
But the supersession event IS logged:

```json
{
  "event": "snapshot.superseded",
  "correlation_id": "req_...",
  "snapshot_id": "snap_...",
  "deal_id": "deal_...",
  "superseded_at": "2025-06-01T14:23:08.412Z",
  "new_snapshot_id": "snap_..."
}
```

This creates an operational record of the supersession event even though
the database state only shows the final result.

---

---

# Part 7 — Metrics Architecture

---

## 7.1 — Metrics Categories

The platform defines four categories of metrics. Each category has different
consumers, different retention, and different alert purposes.

```
SYSTEM METRICS
  Infrastructure: CPU, memory, disk I/O, network throughput
  Database: connection pool usage, query rates, transaction rates
  Source: database and hosting platform (Railway/Postgres metrics)
  Consumer: engineering
  Alert on: resource exhaustion, connection pool saturation

APPLICATION METRICS
  Request rates, latency distributions, error rates per route
  Engine execution duration
  Database query duration per operation type
  Source: application code (counters and histograms)
  Consumer: engineering
  Alert on: latency degradation, elevated error rates

BUSINESS METRICS
  Calculation counts by outcome (success/failure/error)
  Validation failure rates by rule code
  Risk flag distribution across calculations
  Deal and property creation rates
  Source: application code (event counters)
  Consumer: product and engineering
  Alert on: unusual pattern changes

TRUST METRICS
  Configuration version age (days since last update — alert if stale)
  Snapshot reproduction success rate (if Variant B is run)
  Audit write failure rate (should always be zero)
  Source: application code + scheduled checks
  Consumer: platform operators
  Alert on: any non-zero value for certain trust metrics
```

---

## 7.2 — Metric Naming Convention

All metrics use dot-separated hierarchical names:

```
propiq.<layer>.<entity>.<measurement>

Examples:
  propiq.api.request.duration_ms
  propiq.api.request.count
  propiq.calculation.engine.duration_ms
  propiq.calculation.outcome.count            (label: outcome=success/failure/error)
  propiq.calculation.validation.failure_count (label: rule_code=V-07/V-15/...)
  propiq.calculation.risk_flag.count          (label: flag_code, severity)
  propiq.repository.query.duration_ms         (label: table, operation)
  propiq.snapshot.persistence.duration_ms
  propiq.config.version.age_days              (label: config_type)
  propiq.audit.write_failure.count
```

---

---

# Part 8 — Domain Metrics

Domain metrics measure business-level behaviour. They answer questions like
"is the platform being used as expected?" and "are calculations succeeding?"

---

## 8.1 — Calculation Outcome Metrics

```
propiq.calculation.outcome.count
  Labels: outcome (SUCCESS, VALIDATION_FAILURE, ENGINE_ERROR),
          ownership_structure (INDIVIDUAL, LIMITED_COMPANY),
          tax_pathway (SECTION_24, CORPORATION_TAX)
  Type: Counter
  Purpose: Track calculation volume and success rate

propiq.calculation.engine.duration_ms
  Labels: ownership_structure, tax_pathway
  Type: Histogram (buckets: 1, 5, 10, 25, 50, 100, 250ms)
  Purpose: Track engine execution time; detect performance regressions

propiq.calculation.pipeline.duration_ms
  Labels: outcome
  Type: Histogram
  Purpose: Total calculation request time including DB I/O
```

---

## 8.2 — Validation Failure Metrics

```
propiq.calculation.validation.failure_count
  Labels: rule_code (V-07, V-15, etc.)
  Type: Counter
  Purpose: Identify which validation rules trigger most frequently.
           High rate on a specific rule may indicate a UX issue (users
           repeatedly submitting invalid inputs) or a data quality problem.
           High rate on V-16 (country not England) may indicate users from
           unsupported regions — a product signal.

propiq.calculation.validation.warning_count
  Labels: rule_code
  Type: Counter
  Purpose: Track warning patterns, particularly V-25 (no refurb cost)
           and V-08 (deposit below 25%). Informs default tuning.
```

---

## 8.3 — Risk Flag Metrics

```
propiq.calculation.risk_flag.trigger_count
  Labels: flag_code, severity (HIGH, MEDIUM, INFO)
  Type: Counter
  Purpose: Platform-wide distribution of risk flags.
           High NEGATIVE_CASHFLOW rate may indicate market conditions
           or user base characteristics.
           HIGH rate on SECTION_24_IMPACT informs product messaging.

propiq.calculation.risk_flag_count_per_calculation
  Labels: severity
  Type: Histogram (buckets: 0, 1, 2, 3, 4, 5, 6+)
  Purpose: Understand typical flag density per calculation.
```

---

## 8.4 — Deal and Property Lifecycle Metrics

```
propiq.deal.created.count
propiq.deal.archived.count
propiq.property.created.count
propiq.user.registered.count    (first login)

All type: Counter
Purpose: Growth and engagement signals. Not user-identifying in aggregate.
```

---

---

# Part 9 — Engine Metrics

The engine is a pure function with no I/O. Its metrics are measured by
the service layer wrapper around `engine.run()`.

---

## 9.1 — Engine Execution Duration

```
propiq.calculation.engine.duration_ms
  Measured: time from engine.run() call to return
  Labels: outcome (SUCCESS, VALIDATION_FAILURE, ENGINE_ERROR),
          tax_pathway (SECTION_24, CORPORATION_TAX),
          mortgage_type (INTEREST_ONLY, REPAYMENT)
  Type: Histogram
  Expected range: 1–20ms (pure in-memory computation)
  Alert threshold: P99 > 100ms (indicates unexpected blocking)
```

---

## 9.2 — Engine Error Tracking

```
propiq.calculation.engine_error.count
  Labels: error_code (DIVIDE_BY_ZERO, UNEXPECTED_NONE, etc.)
  Type: Counter
  Expected value: 0 in production
  Alert: immediately on any increment (engine errors should not occur in production)
```

---

## 9.3 — Validation Pipeline Metrics

```
propiq.calculation.validation.duration_ms
  Type: Histogram
  Expected range: < 1ms (pure data validation, no I/O)
  Alert threshold: P99 > 10ms (indicates unexpected complexity)

propiq.calculation.validation.hard_error_count_per_request
  Type: Histogram (buckets: 1, 2, 3, 4, 5+)
  Purpose: Understand how many errors occur simultaneously.
           Most requests with validation failures have 1 error.
           Multiple simultaneous errors may indicate bulk API misuse.
```

---

---

# Part 10 — Repository Metrics

---

## 10.1 — Query Duration by Table and Operation

```
propiq.repository.query.duration_ms
  Labels: table (snapshot_calculations, deals, config_sdlt_versions, etc.),
          operation (SELECT, INSERT, UPDATE),
          query_name (find_by_id_for_user, find_active_config, save_snapshot, etc.)
  Type: Histogram
  Purpose: Identify slow queries per table and operation.
           Slow config reads indicate need for caching.
           Slow snapshot inserts indicate transaction overhead.
```

---

## 10.2 — Snapshot Persistence Duration

```
propiq.snapshot.persistence.duration_ms
  Type: Histogram
  Measured: full duration of save_snapshot_and_update_deal transaction
  Buckets: 10, 25, 50, 100, 200, 500ms
  Alert threshold: P95 > 500ms (the 6-table atomic write should be fast)
```

---

## 10.3 — Configuration Load Duration

```
propiq.config.load.duration_ms
  Labels: config_type (sdlt, corporation_tax, assumption, combined)
  Type: Histogram
  Measured: time to load and translate one configuration type
  Expected: < 5ms per config type (single indexed row query)
  Alert threshold: P95 > 50ms
```

---

## 10.4 — Database Connection Pool Metrics

```
propiq.db.pool.active_connections
propiq.db.pool.waiting_requests
propiq.db.pool.overflow_connections
  Type: Gauge
  Alert on: waiting_requests > 0 for sustained period (pool exhaustion)
```

---

---

# Part 11 — Service Metrics

---

## 11.1 — Calculation Service Metrics

```
propiq.service.calculation.run_calculation.duration_ms
  Type: Histogram
  Includes: ownership check + config load + default resolution +
            engine + snapshot persistence + summary load
  This is the end-to-end service method duration (not HTTP duration)

propiq.service.calculation.config_load.duration_ms
  Type: Histogram
  Measured: time for ConfigurationService.load_for_calculation
  (Three separate DB reads, should be < 20ms total)
```

---

## 11.2 — Audit Service Metrics

```
propiq.service.audit.write_failure.count
  Type: Counter
  Expected value: 0 in production
  Alert: immediately on any increment
  Reason: AuditService.write_failure() swallows exceptions but logs and
          increments this counter. Any audit write failure is a trust event.
```

---

---

# Part 12 — API Metrics

---

## 12.1 — HTTP Request Metrics

```
propiq.api.request.duration_ms
  Labels: method (GET, POST), route_pattern (/api/v1/calculations, etc.),
          status_code (200, 201, 400, 401, 403, 404, 422, 500)
  Type: Histogram
  Purpose: Request latency and error rates per route

propiq.api.request.count
  Labels: method, route_pattern, status_code
  Type: Counter
  Purpose: Volume per route and outcome distribution

propiq.api.request.in_flight
  Type: Gauge
  Purpose: Concurrent request count (scale signal)
```

---

## 12.2 — Authentication Metrics

```
propiq.api.auth.failure_count
  Labels: reason (TOKEN_EXPIRED, TOKEN_INVALID, TOKEN_MISSING)
  Type: Counter
  Alert on: spike in TOKEN_INVALID (may indicate brute-force or token theft)
  Note: TOKEN_EXPIRED is normal client behaviour; TOKEN_INVALID is more concerning

propiq.api.auth.success_count
  Type: Counter
  Purpose: Baseline authentication volume
```

---

---

# Part 13 — Error Observability

---

## 13.1 — Error Classification Hierarchy

All errors are classified into five categories. Classification determines
alert severity and investigation priority.

```
CATEGORY 1 — TRUST ERRORS (immediate investigation required)
  Description: Errors that affect the platform's core trust guarantees.
  Examples:
    - Snapshot sub-table missing for a snapshot that should have one
      (PersistenceIntegrityError)
    - Configuration version not found for a version_id referenced by a snapshot
      (ConfigurationNotFoundError on version-specific load)
    - Audit write failure (write_failure returning without writing)
    - Engine producing different output for the same inputs (reproducibility violation)
  Logging: ERROR level with full context
  Alert: Immediate PagerDuty (or equivalent) alert
  Action required: Investigate within 15 minutes

CATEGORY 2 — ENGINE ERRORS (urgent investigation)
  Description: Unexpected failures inside the engine that validation did not catch.
  Examples:
    - EngineError returned by engine.run()
  Logging: ERROR level with stack trace
  Alert: Immediate alert; escalate if repeated
  Action required: Investigate within 1 hour

CATEGORY 3 — OPERATIONAL ERRORS (same-day investigation)
  Description: Infrastructure failures that affect availability but not data integrity.
  Examples:
    - Database connection failures
    - Repository query timeouts
  Logging: ERROR level
  Alert: Non-critical alert; investigate within business hours
  Action required: Monitor and investigate

CATEGORY 4 — DOMAIN ERRORS (monitoring only)
  Description: Business rule violations that are expected in normal operation.
  Examples:
    - NotFoundError (user accessing non-existent or non-owned resource)
    - DomainError (invalid state transition)
    - CalculationValidationFailure
  Logging: INFO level (not an error in the system — expected user behaviour)
  Alert: No individual alert; monitor aggregate rates for anomalies
  Action required: Alert only if rate is abnormally high

CATEGORY 5 — EXPECTED TRANSIENT ERRORS (no action)
  Description: Client-side errors with no server-side intervention needed.
  Examples:
    - 401 (expired token — client refreshes)
    - Rate limiting (Phase 3+)
  Logging: INFO level
  Alert: None unless rate is anomalous
```

---

## 13.2 — Error Context Requirements

Every ERROR or CRITICAL log entry must include:

```json
{
  "level": "ERROR",
  "event": "...",
  "correlation_id": "req_...",
  "user_id": "usr_...",
  "deal_id": "deal_...",
  "service": "propiq-backend",
  "operation": "CalculationService.run_calculation",
  "error_type": "PersistenceIntegrityError",
  "error_message": "Snapshot sub-table missing: snapshot_inputs",
  "stack_trace": "..."
}
```

`user_id` and `deal_id` are included so the investigation can locate the
exact data in the database. The `stack_trace` goes to server logs only —
never to users or external systems.

---

---

# Part 14 — Validation Failure Observability

Validation failures are domain events, not system errors. They require
separate observability design because they carry useful product intelligence.

---

## 14.1 — Validation Failure Logging

Every validation failure produces an INFO-level log entry (not ERROR). The
entry records the rule codes that triggered but does not record the values
that triggered them (those would be user financial data).

```json
{
  "level": "INFO",
  "event": "calculation.validation.failed",
  "correlation_id": "req_...",
  "user_id": "usr_...",
  "deal_id": "deal_...",
  "engine_version": "1.0.0",
  "hard_error_count": 1,
  "hard_error_codes": ["V-07"],
  "warning_count": 1,
  "warning_codes": ["V-25"]
}
```

---

## 14.2 — Validation Failure Intelligence

Aggregate validation failure metrics (counts by rule code over time) provide
product intelligence without any individual user data:

- High V-07 rate (deposit below 15%) may indicate users misunderstanding
  deposit requirements or entering purchase price incorrectly.
- High V-16 rate (country not England) is a market signal — users in Scotland
  and Wales are being blocked; this is a roadmap consideration.
- High V-15 rate (property type not RESIDENTIAL_SINGLE_LET) indicates demand
  for HMO and commercial analysis features.

These aggregate patterns are derived from metrics, not from accessing
individual user data.

---

---

# Part 15 — Security Event Observability

---

## 15.1 — Security Events That Must Always Be Logged

The following events are mandatory log entries regardless of log level
configuration:

```
security.auth.token_invalid     — all invalid JWT presentations
security.auth.token_expired     — all expired JWT presentations
security.admin.access           — all admin route accesses (success and failure)
security.ownership.denied       — all ownership check failures
security.admin.config.insert    — all configuration version insertions
```

Security events are never suppressed. They are logged at WARNING or INFO level
but their logging is unconditional — debug mode cannot suppress them.

---

## 15.2 — Ownership Denial Pattern Detection

Repeated `security.ownership.denied` events from the same `user_id` in a
short window may indicate resource enumeration (a user probing random UUIDs
to find valid resource IDs belonging to others).

The metric `propiq.api.auth.failure_count` and the log stream of
`security.ownership.denied` events with timestamps enable detection of
this pattern.

Alert rule (Phase 2+): if `security.ownership.denied` events from the same
`user_id` exceed 10 in 60 seconds, trigger a security review alert.

---

## 15.3 — Admin Action Audit Trail

Every admin action (configuration insert, user suspension, any admin route
access) must be logged at INFO level with:

```json
{
  "event": "security.admin.access",
  "user_id": "usr_...",
  "route": "/api/v1/admin/config/sdlt",
  "operation": "INSERT_SDLT_VERSION",
  "config_version_id": "cfg_...",
  "correlation_id": "req_..."
}
```

In Phase 1, this log serves as the admin audit record. Phase 2 introduces
a formal `audit_config_changes` database table as a permanent record.

---

---

# Part 16 — Snapshot Creation Observability

Snapshot creation is the most important operation in the platform. Its
observability requires dedicated attention.

---

## 16.1 — Snapshot Creation Metrics

```
propiq.snapshot.persistence.duration_ms
  Measures: full atomic transaction duration
  Expectation: < 100ms P95
  Alert: > 500ms P95

propiq.snapshot.persistence.success_count
  Counter incremented on successful snapshot commit

propiq.snapshot.persistence.failure_count
  Counter incremented on transaction rollback
  Alert: any non-zero increment in a 5-minute window
```

---

## 16.2 — Snapshot Creation Log Events

```
calculation.snapshot.persisted (INFO) — on success:
{
  "snapshot_id": "snap_...",
  "deal_id": "deal_...",
  "user_id": "usr_...",
  "engine_version": "1.0.0",
  "persistence_duration_ms": 47,
  "risk_flag_codes": ["NEGATIVE_CASHFLOW", "RENT_UNVERIFIED"],
  "assumption_overrides": 2
}

calculation.snapshot.persistence_failed (ERROR) — on rollback:
{
  "deal_id": "deal_...",
  "user_id": "usr_...",
  "failure_stage": "snapshot_inputs_insert",
  "error_type": "DatabaseError",
  "correlation_id": "req_..."
}
```

---

## 16.3 — Snapshot Integrity Verification

A scheduled operational check runs daily (Phase 2+) to verify snapshot
integrity:

```
Check: For every snapshot_calculations record created in the last 24 hours,
       verify that corresponding records exist in:
       - snapshot_inputs (exactly one, unique snapshot_id)
       - snapshot_outputs (exactly one, unique snapshot_id)
       - snapshot_intermediates (exactly one, unique snapshot_id)

If any orphaned snapshot root record is found (missing sub-tables):
   Log at CRITICAL: "trust.snapshot.integrity_violation"
   Alert immediately
```

An orphaned snapshot indicates a failed atomic transaction that partially
committed — a scenario that should be prevented by the database transaction
design, but which must be detected if it somehow occurs.

---

---

# Part 17 — Configuration Version Observability

---

## 17.1 — Configuration Staleness Monitoring

Tax rates and assumption defaults should be reviewed at regular intervals.
A configuration version that has not been updated in an unusually long time
may indicate the platform is running on outdated assumptions.

```
propiq.config.version.age_days
  Labels: config_type (sdlt, corporation_tax, assumption)
  Type: Gauge
  Computed: days since most recent effective_from date for each config type
  Alert thresholds:
    sdlt_version_age_days > 400:   WARNING (SDLT rates typically change
                                    annually at Budget)
    assumption_version_age_days > 365: INFO (assumptions should be
                                    reviewed annually)
    corporation_tax_age_days > 730: INFO (CT rates less frequent)
```

---

## 17.2 — Configuration Insert Observability

Every configuration insert is logged immediately:

```json
{
  "event": "config.version.inserted",
  "level": "INFO",
  "config_type": "sdlt",
  "new_version_id": "cfg_...",
  "effective_from": "2025-04-01",
  "admin_user_id": "usr_...",
  "correlation_id": "req_..."
}
```

This log entry is the Phase 1 record of configuration changes. Phase 2
moves this to the permanent `audit_config_changes` database table.

---

## 17.3 — Configuration Load Failure

A missing active configuration is a CRITICAL platform failure:

```json
{
  "event": "config.load.not_found",
  "level": "CRITICAL",
  "config_type": "sdlt",
  "as_of_date": "2025-06-01",
  "correlation_id": "req_..."
}
```

This means the configuration seed data was not run, the most recent
`effective_from` date is in the future, or the database is in an unexpected
state. All calculations will fail until this is resolved. Alert immediately.

---

---

# Part 18 — Performance Monitoring

---

## 18.1 — Performance Budget per Operation

```
Operation                           P50      P95     P99     Alert at
──────────────────────────────────  ───────  ──────  ──────  ────────────────────
run_calculation (full pipeline)     120ms    250ms   400ms   P99 > 1000ms
get_display_summary (snapshot)       25ms     50ms    80ms   P99 > 300ms
get_full_snapshot (with intermediates) 40ms  80ms   150ms   P99 > 500ms
update_working_inputs                20ms     40ms    80ms   P99 > 300ms
create_deal                          25ms     50ms   100ms   P99 > 300ms
load_for_calculation (config, ×3)    15ms     30ms    50ms   P99 > 200ms
engine.run() alone                    3ms      8ms    15ms   P99 > 50ms
snapshot persistence transaction     40ms    100ms   200ms   P99 > 500ms
```

---

## 18.2 — Slow Query Detection

Any database query exceeding 500ms is logged as a WARNING with:

```json
{
  "event": "repository.query.slow",
  "level": "WARNING",
  "table": "snapshot_calculations",
  "operation": "SELECT",
  "query_name": "find_history_for_deal",
  "duration_ms": 720,
  "correlation_id": "req_..."
}
```

Repeated slow query warnings for the same `query_name` indicate a missing
index or a query design issue requiring investigation.

---

## 18.3 — Performance Regression Detection

Performance regressions are detected by comparing rolling percentile metrics
against a baseline. The baseline is established during load testing before
each deployment. A deployment that causes P95 latency on `run_calculation`
to increase by more than 50% should trigger a review.

---

---

# Part 19 — Operational Dashboards

Dashboards are not implemented in Phase 1 with tooling; they are defined
here as requirements so the metric naming and log structure support them.

---

## 19.1 — Calculation Health Dashboard

**Purpose:** Real-time view of calculation pipeline health.

**Panels:**
1. Calculation outcome rate (success / validation failure / engine error) — last 1 hour
2. Engine execution duration histogram — last 1 hour
3. Full pipeline duration histogram — last 1 hour
4. Validation failure rate by rule code — last 24 hours
5. Risk flag trigger rate by flag code and severity — last 24 hours
6. Active user count triggering calculations — last 1 hour

---

## 19.2 — Snapshot and Audit Integrity Dashboard

**Purpose:** Trust and data integrity monitoring.

**Panels:**
1. Snapshot persistence success/failure rate — last 24 hours
2. Audit write failure rate — last 24 hours (should always be zero)
3. Snapshot integrity check results — last 24 hours
4. Engine errors — last 7 days (should always be zero in production)
5. Configuration version age by type — current

---

## 19.3 — Security Dashboard

**Purpose:** Authentication and access pattern monitoring.

**Panels:**
1. Authentication failure rate by reason — last 1 hour
2. Admin route accesses — last 24 hours
3. Ownership denial events by rate — last 1 hour
4. New user registrations — last 24 hours

---

## 19.4 — API Performance Dashboard

**Purpose:** Request latency and error rate monitoring.

**Panels:**
1. P50/P95/P99 latency by route — last 1 hour
2. Request rate by route — last 1 hour
3. HTTP error rate by status code — last 1 hour
4. Database connection pool usage — live

---

---

# Part 20 — Alerting Philosophy

---

## 20.1 — Alert Principles

**Alert on exceptions, not on norms.** An alert that fires when things are
normal trains operators to ignore it. Every alert must represent a condition
that requires human attention and that cannot resolve itself automatically.

**Trust alerts are higher priority than performance alerts.** A 500ms
increase in P95 latency is a performance concern. An audit write failure
or a snapshot integrity violation is a trust violation. The alert
prioritisation reflects the platform's values.

**Alerts are actionable.** Every alert has a defined investigation procedure.
An alert without a runbook is incomplete. Phase 1 defines runbooks as
documented investigation steps in an operational wiki, not as automated
remediation.

---

## 20.2 — Alert Severity Tiers

```
TIER 1 — CRITICAL (wake someone up immediately)
  Condition examples:
    - Any engine error in production
    - Any snapshot integrity violation
    - Any audit write failure
    - Configuration not found for current date
    - Database unreachable
  Response: Investigate within 15 minutes

TIER 2 — HIGH (investigate within 1 business hour)
  Condition examples:
    - Snapshot persistence failure rate > 0
    - API error rate (5xx) > 1% over 5 minutes
    - Database connection pool saturation
    - P99 calculation latency > 1000ms for 5 minutes
  Response: Investigate within 1 hour

TIER 3 — MEDIUM (investigate same business day)
  Condition examples:
    - Configuration version age exceeding threshold
    - Ownership denial rate spike (potential enumeration)
    - Elevated validation failure rate on specific rule codes
    - Slow query warnings for same query > 3 times in an hour
  Response: Investigate within business hours

TIER 4 — LOW (review weekly)
  Condition examples:
    - AUTH token invalid rate elevation (not spike, just elevation)
    - Business metric anomalies (unusual deal creation rate)
  Response: Review in weekly operational review
```

---

## 20.3 — Alert Silence Policy

Alerts must not be silenced without a documented reason and an expiry time.
An indefinitely silenced alert is an unmonitored failure mode. Any alert
that fires so frequently it requires regular silencing is an alert that
needs redesigning, not silencing.

---

---

# Part 21 — Future AI Explainability Observability Requirements

When Phase 5 introduces AI-assisted summaries and explanations, the
observability model must extend to cover the AI layer without compromising
the deterministic calculation observability.

---

## 21.1 — AI Service Metrics (Phase 5+)

```
propiq.ai.summary.generation.duration_ms
  Labels: summary_type, model_version
  Type: Histogram
  Purpose: AI API call latency tracking

propiq.ai.summary.generation.count
  Labels: summary_type, outcome (success/error)
  Type: Counter

propiq.ai.api.cost.tokens
  Labels: model_version, summary_type
  Type: Counter
  Purpose: AI API cost tracking
```

---

## 21.2 — AI Boundary Enforcement Observability

The AI boundary (ADR-001, ADR-014) must be verifiable in production:

```
Metric: propiq.ai.snapshot.write_attempt.count
  Purpose: This counter should ALWAYS be zero.
           It increments if any AI service method attempts to write to
           a snapshot table (caught by the database privilege constraint).
  Alert tier: TIER 1 — any non-zero value indicates an architectural
              boundary violation that requires immediate investigation.
```

This metric is the operational equivalent of the AZ-14 authorization
invariant. The database will reject the write; this metric records that
the attempt occurred.

---

## 21.3 — AI Explainability Log Requirements

AI-generated explanations that reference specific calculation intermediates
must log the mapping between the explanation and the snapshot:

```json
{
  "event": "ai.summary.generated",
  "snapshot_id": "snap_...",
  "summary_type": "RISK_FLAG_EXPLANATION",
  "flag_code": "SECTION_24_IMPACT",
  "model_version": "claude-sonnet-4-6",
  "prompt_version": "risk_flag_v1.2",
  "generation_duration_ms": 1840,
  "token_count": 320
}
```

No financial values appear in AI observability logs. The `snapshot_id`
reference is sufficient for correlation.

---

---

# Part 22 — Production Troubleshooting Workflow

---

## 22.1 — Scenario: User Reports Unexpected Calculation Result

```
1. Ask user for the deal ID and approximate time of the calculation.

2. Query audit_calculations:
   SELECT * FROM audit_calculations
   WHERE deal_id = '<deal_id>'
   ORDER BY triggered_at DESC;
   → Find the relevant record; extract snapshot_id and correlation_id.

3. If snapshot_id is null: the calculation failed.
   Look at outcome (VALIDATION_FAILURE / ENGINE_ERROR).
   For VALIDATION_FAILURE: review validation_errors JSON for rule codes.
   For ENGINE_ERROR: search logs by correlation_id.

4. If snapshot_id is present: the calculation succeeded.
   Query snapshot_outputs and snapshot_intermediates for the snapshot_id.
   → This is the authoritative record of what was calculated and why.

5. To understand the engine configuration used:
   From snapshot_calculations, extract the three config version IDs.
   Query config_sdlt_versions, config_corporation_tax_versions,
   config_assumption_versions for those specific IDs.
   → You now have the complete calculation environment.

6. To verify reproducibility:
   Use CalculationService.reproduce_original(snapshot_id) in a staging
   environment. The result should be identical to snapshot_outputs.
   If not: TIER 1 alert — investigate immediately.

7. For further detail on execution context:
   Search log aggregation system for correlation_id.
   → Retrieve the full request trace with timing and intermediate events.
```

---

## 22.2 — Scenario: Engine Error in Production

```
1. TIER 1 alert fires on propiq.calculation.engine_error.count increment.

2. Check audit_calculations for ENGINE_ERROR outcomes in the last 15 minutes:
   SELECT * FROM audit_calculations
   WHERE outcome = 'ENGINE_ERROR'
   AND triggered_at > NOW() - INTERVAL '15 minutes';
   → Get deal_id, user_id, correlation_id.

3. Search logs for error_code from the engine and the correlation_id.
   → Stack trace is in the log entry for calculation.engine_error.occurred.

4. Check if the error is repeatable:
   Try triggering a calculation on the same deal in staging.
   If repeatable: fix required before production calculation can proceed.
   If not repeatable: transient error; verify it does not recur.

5. Notify the affected user:
   The user received a generic "Calculation could not be completed" response.
   If the deal is important, contact user to retry.
   Their data is fully intact — no snapshot was created.
```

---

## 22.3 — Scenario: Configuration Version Staleness Alert

```
1. TIER 3 alert fires on propiq.config.version.age_days > threshold.

2. Identify which configuration type is stale:
   SELECT config_type, effective_from
   FROM (
     SELECT 'sdlt' as config_type, MAX(effective_from) as effective_from
     FROM config_sdlt_versions
     UNION
     SELECT 'corporation_tax', MAX(effective_from) FROM config_corporation_tax_versions
     UNION
     SELECT 'assumption', MAX(effective_from) FROM config_assumption_versions
   ) t;

3. Assess whether the configuration is genuinely outdated:
   - Check HMRC for recent SDLT changes
   - Check Finance Acts for CT rate changes
   - Review ARLA/market data for assumption updates

4. If an update is needed:
   Insert a new configuration version via /api/v1/admin/config/
   with the correct effective_from date.
   Verify that new calculations pick up the new version.
   Old snapshots retain references to their original versions unchanged.
```

---

## 22.4 — Scenario: Snapshot Integrity Violation

```
1. TIER 1 alert fires on trust.snapshot.integrity_violation log event.

2. Identify the affected snapshot:
   The log entry contains the snapshot_id and the missing sub-table name.

3. Immediate investigation:
   This should never happen given the atomic transaction design.
   If it has happened, it indicates either:
     a) A bug in the transaction management that allowed a partial commit
     b) A direct database manipulation that bypassed the application

4. Assess the scope:
   SELECT COUNT(*) FROM snapshot_calculations sc
   LEFT JOIN snapshot_inputs si ON si.snapshot_id = sc.id
   WHERE si.snapshot_id IS NULL;
   → How many snapshots are affected?

5. Do not attempt to repair the data without a documented change process.
   An orphaned snapshot root record is a data integrity issue.
   The decision to repair or retire it must be documented and logged.

6. Post-incident:
   Review whether the transaction boundary in SnapshotService was violated.
   Review database access logs for any direct manipulation.
   Review the privilege model — the application user should not be able
   to INSERT snapshot_calculations without the accompanying sub-tables
   via the application code path.
```

---

---

# Part 23 — Observability Invariants

```
OI-01  Every log entry is structured JSON. No free-text log lines in
       production. The structured fields defined in Part 3.1 are present
       on every log entry.

OI-02  Every log entry carries a correlation_id when it is produced within
       the context of an HTTP request or background task.
       Logs without a correlation_id are only acceptable for startup,
       shutdown, and health check events.

OI-03  No log entry contains PII (email addresses, display names, property
       addresses) or financial data (purchase prices, rent figures, any
       calculation input or output values).
       Log entries identify resources by UUID only.

OI-04  Security events (auth failures, ownership denials, admin accesses)
       are logged unconditionally. No log level configuration may suppress
       security event logging.

OI-05  Every calculation attempt produces exactly one structured log event
       at the "calculation pipeline" level, regardless of outcome.
       This pairs with the invariant that every calculation attempt produces
       exactly one audit_calculations database record.

OI-06  The correlation_id used in server logs and the correlation_id stored
       in audit_calculations.correlation_id are identical.
       This creates a permanent link between operational logs and the
       immutable audit record.

OI-07  Engine errors are logged at ERROR level with full stack trace.
       The stack trace goes to server logs only.
       It is never included in audit_calculations.error_detail,
       API responses, or any user-accessible record.

OI-08  Audit write failures are logged at WARNING level and increment
       the propiq.service.audit.write_failure.count metric.
       They are never silently discarded. Even if the audit write cannot
       complete, the attempt and failure must be recorded in operational logs.

OI-09  propiq.calculation.engine_error.count must be zero in production.
       Any non-zero value triggers a TIER 1 alert.
       Any non-zero value requires an incident investigation.

OI-10  propiq.service.audit.write_failure.count must be zero in production.
       Any non-zero value triggers a TIER 1 alert.
       An audit write failure is a trust event — it means a calculation
       occurred without a permanent record.

OI-11  The snapshot integrity check (Part 16.3) must find zero orphaned
       snapshot records. Any violation triggers a TIER 1 alert and an
       immediate incident investigation.

OI-12  Observability data for calculation events must be sufficient to
       reconstruct the complete execution context of any historical calculation
       by combining the snapshot record (permanent, in database) with the
       structured logs (operational, time-bounded) using correlation_id.

OI-13  Performance metrics are collected at all five layers: API, service,
       engine, repository, and database. No layer is a black box for
       performance diagnosis.

OI-14  Configuration version age metrics are computed and exported.
       A TIER 3 alert fires when configuration age exceeds defined thresholds.
       Platform operators must be notified before configuration becomes
       materially stale.

OI-15  AI service metrics (Phase 5+) must include a write_attempt counter
       on snapshot tables. This counter must always be zero. Any non-zero
       value is a TIER 1 trust boundary violation.
```
