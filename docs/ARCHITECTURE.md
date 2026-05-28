# PropIQ Platform — Architecture Overview

# Purpose

This document defines the high-level architecture direction for the platform.

It focuses on:

* system boundaries,
* responsibilities,
* data flow,
* and long-term maintainability.

This is not an implementation document.

---

# Core Architectural Principles

## Separation of Concerns

Business logic, persistence, APIs, and presentation layers must remain isolated.

---

## Deterministic Domain Logic

Underwriting calculations must remain:

* pure,
* testable,
* deterministic,
* and independent from AI systems.

---

## Immutable Historical Analysis

Historical deal analyses are immutable snapshots.

---

## Versioned Configuration

Tax rates and operational assumptions must be versioned and auditable.

---

# High-Level System Overview

Frontend
↓
API Layer
↓
Underwriting Engine
↓
Persistence Layer
↓
PostgreSQL

Future enrichment services:

* crime data
* EPC data
* flood risk
* area intelligence
* mapping overlays

remain separate from core underwriting logic.

---

# Frontend

## Stack

* Next.js
* TypeScript
* Tailwind CSS

## Responsibilities

* user interaction
* forms
* deal analysis UI
* dashboards
* visualisation
* snapshot comparison

Frontend does not own calculation logic.

---

# Backend API

## Stack

* FastAPI
* Python

## Responsibilities

* request validation
* orchestration
* authentication integration
* persistence
* snapshot lifecycle
* configuration management

---

# Underwriting Engine

## Responsibilities

* deterministic calculations
* stress testing
* yield calculations
* tax modelling
* risk flag generation

## Important Constraint

The underwriting engine:

* must not depend on AI,
* must remain independently testable,
* and must support versioning.

---

# Snapshot System

## Purpose

Persist immutable deal analyses.

Each snapshot stores:

* inputs
* assumptions
* outputs
* version IDs
* timestamps

Snapshots are append-only.

---

# Versioning System

The platform must support:

* engine versioning
* assumption versioning
* rate table versioning
* historical recalculation

Configuration data is never overwritten.

---

# Database

## Stack

* PostgreSQL
* PostGIS enabled early

## Responsibilities

* persistence
* snapshot storage
* versioned configuration
* future geo capabilities

---

# Future Spatial Intelligence

Future roadmap includes:

* crime overlays
* flood risk
* school proximity
* deprivation indices
* local authority intelligence

PostGIS support is enabled early to reduce future migration complexity.

---

# AI Boundary

AI systems may later assist with:

* summaries
* explanations
* educational guidance
* natural language interpretation

AI systems must never:

* generate authoritative calculations,
* mutate underwriting outputs,
* or override deterministic engine results.

---

# Infrastructure Direction

## Initial Hosting

* Railway
* Docker-based development
* PostgreSQL managed database

## Future Considerations

Potential future scaling areas:

* background workers
* async enrichment pipelines
* scheduled data imports
* caching layers
* event-driven processing

---

# Long-Term Architectural Direction

The platform is intended to evolve toward:

* investor intelligence tooling,
* portfolio analytics,
* area risk analysis,
* and operational underwriting infrastructure.

The underwriting engine remains the core trusted asset of the platform.
