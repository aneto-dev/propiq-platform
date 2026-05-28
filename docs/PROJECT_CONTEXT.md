# PropIQ Platform — Project Context

## Project Vision

PropIQ is a production-grade UK property investment analysis platform designed to help investors evaluate deals using realistic underwriting, transparent assumptions, and operationally trustworthy calculations.

The platform is not intended to provide financial advice or speculative predictions.

Its purpose is to:

* model property deals accurately under stated assumptions,
* surface hidden risks,
* improve investor decision-making,
* and provide reproducible analysis over time.

The platform prioritises:

* correctness,
* transparency,
* auditability,
* maintainability,
* and long-term trust.

---

# Core Product Philosophy

Most property investment calculators:

* oversimplify,
* hide assumptions,
* overstate yields,
* ignore realistic costs,
* or silently change outputs over time.

PropIQ intentionally takes the opposite approach.

Every calculation must:

* be deterministic,
* be explainable,
* disclose assumptions,
* and remain historically reproducible.

Saved deal analyses must never silently change when:

* regulations change,
* tax rules change,
* assumptions change,
* or engine logic changes.

Historical analyses are immutable snapshots.

---

# Engineering Principles

## Trust First

Trust is the platform's primary asset.

A fast feature that produces misleading outputs is worse than no feature.

---

## Explicit Over Implicit

The system should avoid hidden logic and ambiguous terminology.

Calculations, assumptions, and outputs should be understandable by:

* developers,
* investors,
* and auditors.

---

## Deterministic Calculations

Core underwriting calculations must:

* never rely on AI,
* never produce non-deterministic outputs,
* and always be testable.

AI may assist with:

* summaries,
* explanations,
* natural language interpretation,
* and future insight generation.

AI must never generate authoritative financial outputs.

---

## Incremental Development

The platform should evolve in controlled phases.

Each phase must:

* be deployable,
* maintainable,
* and production-safe.

Avoid large unbounded feature releases.

---

## Versioned Assumptions

All assumptions that may change over time must be versioned.

Examples:

* SDLT rates,
* corporation tax rates,
* stress test assumptions,
* default void rates,
* default maintenance assumptions.

Configuration data is never overwritten.

---

# Technical Stack

## Frontend

* Next.js
* TypeScript
* Tailwind CSS

## Backend

* FastAPI
* Python

## Database

* PostgreSQL
* PostGIS enabled from early phases

## Authentication

* Supabase Auth

## Infrastructure

* Railway initially
* Docker-based local development

## Mapping

* Mapbox (future phases)

---

# Architectural Direction

The underwriting engine is the core intellectual property of the platform.

The architecture should strongly separate:

* domain logic,
* infrastructure,
* persistence,
* API contracts,
* and presentation layers.

The system should support:

* future mobile apps,
* background jobs,
* event-driven processing,
* versioned calculations,
* and future enrichment datasets.

---

# Phase Strategy

## Phase 1

Core underwriting engine.

Focus:

* deal analysis,
* yield calculations,
* cash flow,
* stress testing,
* tax handling,
* snapshots,
* reproducibility.

No advanced maps or intelligence yet.

---

## Phase 2

Deal persistence and portfolio tracking.

---

## Phase 3

Area intelligence:

* crime,
* EPC,
* flood risk,
* schools,
* council/licensing data.

---

## Phase 4

Portfolio analytics and monitoring.

---

## Phase 5

AI-assisted summaries and insight generation.

AI remains non-authoritative.

---

# Important Constraints

The platform:

* is not a mortgage recommendation engine,
* is not regulated financial advice,
* does not guarantee investment outcomes,
* and should avoid misleading certainty language.

Avoid terms like:

* "safe investment"
* "guaranteed return"
* "best area"
* "high confidence prediction"

Use:

* estimated,
* projected,
* modelled,
* based on assumptions,
* historical reference,
* indicative only.

---

# Current Development Focus

Current focus:

* stabilising domain language,
* underwriting terminology,
* versioning strategy,
* schema architecture,
* and calculation specifications.

Implementation begins only after:

* terminology,
* assumptions,
* and architecture are stable.
