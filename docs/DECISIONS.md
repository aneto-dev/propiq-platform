# Architectural Decisions

This document records important architectural and product decisions.

The purpose is to:

* preserve reasoning,
* avoid repeated debates,
* improve consistency,
* and provide historical context.

---

# ADR-001 — AI Does Not Perform Financial Calculations

## Decision

AI models must not generate authoritative underwriting calculations.

## Reasoning

LLMs are probabilistic and non-deterministic.

Financial calculations require:

* reproducibility,
* auditability,
* deterministic outputs,
* and exact consistency.

The underwriting engine must remain:

* code-driven,
* testable,
* and versioned.

AI may later assist with:

* summaries,
* explanations,
* interpretation,
* and educational guidance.

---

# ADR-002 — Immutable Calculation Snapshots

## Decision

Saved analyses are immutable snapshots.

Recalculating a deal creates a new snapshot rather than modifying historical outputs.

## Reasoning

Tax rules, assumptions, and engine logic change over time.

Investors must be able to:

* review historical analyses,
* compare versions,
* and understand what assumptions were used at the time.

Historical reproducibility is a trust requirement.

---

# ADR-003 — ROI Terminology Is Avoided

## Decision

The platform does not expose a primary metric labelled "ROI".

## Reasoning

ROI has inconsistent meaning across property investment.

Different users interpret ROI as:

* cash-on-cash return,
* ROCE,
* total return,
* or appreciation-inclusive return.

Instead, the platform uses explicit metrics:

* net_yield_percent
* cash_on_cash_return_percent
* roce_percent

This reduces ambiguity.

---

# ADR-004 — Net Yield Is Financing-Neutral

## Decision

Net yield excludes financing costs and tax.

## Reasoning

This allows:

* fair comparison between deals,
* fair comparison between leveraged and cash purchases,
* and separation of asset performance from financing strategy.

Mortgage costs and tax are handled separately in cash flow calculations.

---

# ADR-005 — Versioned Configuration Tables

## Decision

Tax rates and assumptions are stored in versioned configuration tables.

Configuration data is never overwritten.

## Reasoning

Regulations and assumptions change over time.

Historical calculations must remain reproducible.

The platform must support:

* effective date ranges,
* source attribution,
* verification metadata,
* and recalculation using updated assumptions.

---

# ADR-006 — PostGIS Enabled Early

## Decision

PostGIS will be enabled from early phases even if advanced geo features are deferred.

## Reasoning

Future roadmap includes:

* crime overlays,
* flood risk,
* area intelligence,
* and spatial analysis.

Early enablement avoids painful future migrations.

---

# ADR-007 — Trust Over Feature Velocity

## Decision

The platform prioritises:

* correctness,
* transparency,
* and operational trust

over rapid feature delivery.

## Reasoning

Incorrect calculations destroy trust faster than missing features.

The underwriting engine is the core asset of the business.

# ADR-008 — Article 4 Belongs Outside the Underwriting Engine

Article 4 planning restrictions are regulatory/spatial feasibility concerns, not deterministic financial calculation rules.

The underwriting engine must remain geographically agnostic.

Article 4 checks belong to a future area intelligence layer using local authority data, source attribution, and possibly PostGIS spatial lookups.

Outputs from that layer may inform deal feasibility warnings, but must not alter historical financial calculations unless explicitly converted into user-visible assumptions.


# ADR-009 — Assumption Provenance Is Required

## Decision

Every non-user-provided assumption used in underwriting must be traceable to a source, version, effective date, and verification timestamp.

## Reasoning

Property underwriting depends heavily on assumptions such as:

* void rates
* stress rates
* insurance estimates
* maintenance reserves
* tax rates
* area intelligence
* planning constraints
* lending assumptions

Users must be able to understand:

* where an assumption came from
* when it was last verified
* whether it was platform-generated or user-provided
* whether it may be stale
* whether the value was manually overridden

This supports:

* trust
* auditability
* historical reproducibility
* explainability
* enterprise-grade reporting

---

# ADR-010 — Explainability Is a Product Requirement

## Decision

Every user-facing calculation should eventually be explainable through a breakdown of formulas, assumptions, inputs, configuration versions, and triggered risk conditions.

## Reasoning

PropIQ is not only a calculator. It is a trust-first underwriting platform.

Users should be able to understand:

* why a result changed
* why a risk flag triggered
* which assumptions affected the outcome
* which tax pathway applied
* which configuration version produced the result

Explainability must be designed into the platform architecture rather than added later as presentation-only logic.

---

# ADR-011 — Scenario Analysis Is a First-Class Capability

## Decision

The platform must eventually support scenario-based underwriting, including:

* base scenarios
* optimistic scenarios
* pessimistic scenarios
* stress-rate scenarios
* refinance scenarios
* exit/sale scenarios
* BRRR scenarios
* HMO conversion scenarios

## Reasoning

Professional property investors do not evaluate deals using one static result.

They compare sensitivity across:

* rent assumptions
* interest rates
* void periods
* refurbishment costs
* exit values
* refinance assumptions
* operating expenses

Scenario support must be implemented without weakening snapshot immutability or historical reproducibility guarantees.

---

# ADR-012 — Regulatory Intelligence Is Separate From Financial Calculations

## Decision

Planning rules, Article 4 restrictions, HMO licensing, selective licensing, EPC regulations, conservation areas, and local authority overlays belong outside the deterministic underwriting engine.

## Reasoning

These are regulatory and spatial feasibility concerns, not deterministic financial formulas.

They may create:

* warnings
* feasibility blockers
* due diligence tasks
* risk indicators

However, they must not directly alter historical financial calculations unless explicitly converted into user-visible assumptions.

The underwriting engine remains geographically agnostic and deterministic.

# ADR-013 — User Overrides Always Take Precedence

## Decision

User-provided assumptions always override platform defaults, AI suggestions, and external data providers.

## Reasoning

The platform must never silently replace explicit user decisions.

Priority order:

1. User override
2. Snapshot-stored value
3. External verified provider
4. Platform default
5. AI-generated suggestion

This hierarchy ensures:
- trust
- predictability
- reproducibility
- auditability

AI outputs are advisory only and never authoritative.


# ADR-014 — The Underwriting Engine Is the System of Record

## Decision

The deterministic underwriting engine is the authoritative source of financial truth within the platform.

## Reasoning

Frontend applications, AI summaries, dashboards, exports, and integrations may present or explain results, but they must not alter authoritative calculation outputs.

Only the deterministic engine may produce:

- official underwriting metrics
- tax calculations
- yield calculations
- risk evaluation outputs
- affordability calculations

This architectural boundary protects:

- trust
- reproducibility
- auditability
- historical consistency
- regulatory defensibility