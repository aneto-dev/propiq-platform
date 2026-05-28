# PropIQ Platform

Production-grade UK property investment underwriting SaaS platform.

---

# Vision

PropIQ is a deterministic underwriting and investment analysis platform designed for UK property investors.

The platform prioritises:

* deterministic calculations,
* immutable historical analysis,
* explainable financial outputs,
* versioned configuration,
* auditability,
* and long-term architectural stability.

The underwriting engine is intentionally designed to remain independent from persistence, APIs, frontend frameworks, and AI systems.

---

# Why PropIQ Exists

Most property investment tools:

* oversimplify underwriting,
* hide assumptions,
* overstate profitability,
* ignore regulatory risk,
* lack historical reproducibility,
* or behave like spreadsheets with UI layers.

PropIQ is designed differently.

The platform aims to become a trust-first investor operating system combining:

* deterministic underwriting,
* explainable financial analysis,
* immutable historical snapshots,
* regulatory intelligence,
* portfolio analytics,
* and operational workflow tooling.

The goal is not only to calculate deals.

The goal is to help investors make better long-term decisions using transparent and reproducible intelligence.


# Core Principles

## Deterministic Calculations

The same inputs and configuration versions must always produce the same outputs.

## Immutable Historical Analysis

Snapshots are append-only and never modified after creation.

## Versioned Configuration

Tax rules, assumptions, and platform configuration are versioned independently.

## Explainability

Every calculated output must be traceable to:

* formulas,
* assumptions,
* configuration versions,
* and risk evaluation rules.

## AI Boundary Enforcement

AI systems may consume underwriting outputs for commentary and insights.

AI systems must never generate authoritative calculations.

---

# Current Architecture Status

The platform is currently in the architecture and executable specification phase.

The underwriting engine design, persistence philosophy, testing strategy, and service boundaries are being stabilised before implementation begins.

---

# Documentation Map

| Document                | Purpose                                            |
| ----------------------- | -------------------------------------------------- |
| ARCHITECTURE.md         | High-level platform architecture                   |
| CALCULATION_SPEC.md     | Formal underwriting formulas and calculation rules |
| DOMAIN_GLOSSARY.md      | Canonical domain terminology                       |
| SCHEMA_ARCHITECTURE.md  | Conceptual domain schema design                    |
| ENGINE_ARCHITECTURE.md  | Underwriting engine architecture                   |
| SERVICE_ARCHITECTURE.md | Service layer and API architecture                 |
| ENGINE_CONTRACTS.md     | Executable engine contracts                        |
| TEST_STRATEGY.md        | Engine testing strategy                            |
| DECISIONS.md            | Architectural decisions and invariants             |
| ROADMAP.md              | Platform roadmap                                   |
| PROJECT_CONTEXT.md      | Platform goals and constraints                     |

---

# Planned Phases

1. Architecture & Specifications
2. Executable Contracts
3. Persistence Design
4. Underwriting Engine Implementation
5. Service Layer & Persistence Wiring
6. API Layer
7. Frontend Platform
8. Production Hardening
9. AI & Intelligence Layer
10. Scaling & Advanced Analytics

---

# Technology Direction

## Backend

* Python
* FastAPI
* PostgreSQL
* SQLAlchemy
* Alembic

## Frontend

* Next.js
* TypeScript

## Infrastructure

* Docker
* Railway (Phase 1)
* Future cloud portability

---

# Engineering Philosophy

* Design for operability, not just correctness
* Preserve historical reproducibility
* Treat calculations as trust-critical infrastructure
* Prefer explicit contracts over implicit behaviour
* Avoid premature optimisation
* Keep architecture evolvable

---

# Project Status

Architecture phase in active development.
