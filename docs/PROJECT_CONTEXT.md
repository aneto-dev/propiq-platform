# PropIQ — Project Context

## Product Vision

PropIQ is an Investor Operating System for UK property investors.

Underwriting is the first shipped capability. The Deal is the primary
domain concept. The platform evolves from deal analysis into the operational
system where investors manage their entire investment lifecycle — from initial
analysis through acquisition, hold, refinance, and exit.

Retention is earned through workflow integration and accumulated operational
value, not through feature novelty or data restriction.

---

## Primary Domain Concept

The **Deal** is the central entity. Not the calculation, not the property,
not the snapshot.

A deal represents an investment opportunity at any stage of its lifecycle.
Analysis (underwriting) is a step within a deal. The result is stored on
the deal and retrievable at any time.

Users add deals to their pipeline and analyse them.
They do not "run calculations."

---

## Architectural Principles

**Trust-first.** Calculations are deterministic, explainable, and immutable
once saved. The underwriting engine is a pure function — no I/O, no AI,
no side effects. Every calculation is reproducible from its stored inputs
and configuration version.

**Engine independence.** The underwriting engine has zero dependency on any
application infrastructure. It is independently testable and separately
versioned.

**Immutable snapshots.** Saved calculations are permanent records. They are
never modified. Recalculation creates a new snapshot; the original is retained.

**Append-only configuration.** Tax rates, SDLT bands, and assumption defaults
are versioned records. Historical snapshots always reference the exact
configuration active at calculation time.

**Explicit assumptions.** Every assumption is versioned, attributed, and
visible to users. User overrides always take precedence over platform defaults.

**Data ownership.** Users own their data. Export is supported. Retention
comes from operational usefulness and accumulated value, not from restricting
access.

---

## Technology Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.13, FastAPI, SQLAlchemy 2.0 async |
| Database | PostgreSQL 16 + PostGIS |
| Migrations | Alembic |
| Validation | Pydantic v2 |
| Auth | Supabase Auth (JWT, RS256) |
| Frontend | Next.js 15, TypeScript 5, Tailwind CSS 4 |
| Hosting | Railway |
| Testing | pytest, pytest-asyncio |

---

## Authoritative Documents

All architecture is frozen at tag `architecture-v1`. The following documents
are the source of truth:

| Document | Covers |
|---|---|
| ARCHITECTURE.md | System overview |
| DOMAIN_MODEL_ARCHITECTURE.md | Entities, aggregates, value objects |
| ENGINE_CONTRACTS.md | Engine input/output contracts, reference scenarios |
| CALCULATION_SPEC.md | Formula definitions, tax pathways, validation rules |
| DATABASE_SCHEMA_DESIGN.md | All Phase 1 table definitions |
| PERSISTENCE_ARCHITECTURE.md | Immutability, versioning, transaction rules |
| REPOSITORY_ARCHITECTURE.md | Repository interfaces and patterns |
| APPLICATION_SERVICE_ARCHITECTURE.md | Service responsibilities and flow |
| AUTHORIZATION_MODEL.md | Authentication, ownership, permissions |
| OBSERVABILITY_ARCHITECTURE.md | Logging, metrics, alerting |
| IMPLEMENTATION_ROADMAP.md | Commit-by-commit execution plan |
| ROADMAP.md | Product phases and retention strategy |
| GROWTH_AND_PLATFORM_DIRECTION.md | Platform positioning and growth |
| CUSTOMER_VALUE_AND_RETENTION_CHALLENGE.md | Retention review framework |

No new architecture decisions are introduced during implementation.
Changes to behaviour require an ADR update in DECISIONS.md first.

---

## Long-term Product Vision

PropIQ is intended to become the operating system for UK property investors.

The initial implementation focuses on standard UK property underwriting because
this creates the core calculation, validation, risk, and snapshot infrastructure
that every future capability depends on.

Long term, PropIQ should support multiple property strategies and investor types,
including standard buy-to-let, BRRR, flips, HMO, serviced accommodation,
rent-to-rent, lease options, joint ventures, deal sourcing, social housing
leases, commercial conversion, and planning-led opportunities.

The platform should remain strategy-aware rather than hard-coded to one deal type.

The current underwriting engine must stay clean, deterministic, and focused.
Strategy expansion is introduced later through explicit roadmap phases, not
mixed into the current formula implementation.

---

## Strategic Priorities

**Phase 1 (current):** Ship the most trusted underwriting capability
available to UK BTL investors. Establish the Deal as the primary concept
from day one.

**Phase 2 (post-launch, within 60 days of first paying subscriber):**
Ship the three retention anchors:
1. Deal status tracking (Analysing → Purchased → Held → Exited)
2. Mortgage expiry tracking and email reminders
3. Actual vs projected rent performance tracking

**Phases 3–5:** Underwriting depth, portfolio intelligence, AI-assisted
insights. Sequenced by retention impact, not technical convenience.

---

## Current Implementation Status

Implementation began at tag `implementation-v1`.

| Roadmap Commit | Status | Notes |
|---|---|---|
| 0.1 — Monorepo skeleton | ✅ Complete | .gitignore, README, Makefile, dirs |
| 0.2 — Docker Compose | ✅ Complete | Verified: PostGIS 3.4 running |
| 0.3 — Python project | ✅ Complete | pyproject.toml, .python-version |
| 0.4 — FastAPI skeleton | ✅ Complete | main.py, config, logging, health endpoint |
| 0.5 — Alembic infrastructure | ✅ Complete | alembic.ini, env.py, base.py, session.py |
| 0.6 — Makefile and setup script | ⚠️ Partial | Makefile and setup_dev.sh exist but were produced out-of-sequence; user confirmed 0.6 as next target |

**Next commit:** 0.6 — `chore: makefile targets for dev workflow`

See the Alignment Report for full detail.

---

## Definition of Done (per commit)

1. `make test` passes
2. `make typecheck` passes (mypy, zero errors)
3. `make lint` passes (ruff, zero errors)
4. Commit message format: `type(scope): description`
5. No TODO comments
6. No test expected values derived from the formula being tested
7. No new architecture decisions without an ADR update
