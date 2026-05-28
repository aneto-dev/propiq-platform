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