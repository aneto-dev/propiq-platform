# Event Architecture

# Purpose

This document defines the future event-driven architecture direction for the PropIQ platform.

The goal is to support:

* automation
* notifications
* background processing
* refresh workflows
* scalability
* operational intelligence

without coupling those concerns directly into the deterministic underwriting engine.

---

# Core Principle

The underwriting engine remains synchronous and deterministic.

Event-driven systems operate around the engine, not inside it.

The engine calculates.

The event layer orchestrates.

---

# Event Categories

## Domain Events

Examples:

* DealCreated
* SnapshotGenerated
* ScenarioCompared
* RefinanceRecorded
* PropertySold

---

## Intelligence Events

Examples:

* RegulatoryDataRefreshed
* EPCDataUpdated
* PlanningDataUpdated
* FloodRiskUpdated

---

## Risk Events

Examples:

* RiskFlagTriggered
* PortfolioStressThresholdExceeded
* LTVThresholdBreached

---

## Workflow Events

Examples:

* OfferSubmitted
* OfferAccepted
* FinancingStarted
* RefinanceCompleted

---

## System Events

Examples:

* ExportGenerated
* SnapshotArchived
* CacheExpired
* BackgroundJobFailed

---

# Event Immutability

Events should be append-only.

Historical events should remain queryable for:

* audit history
* debugging
* workflow replay
* operational analytics

---

# Background Processing

Future asynchronous infrastructure may include:

* Redis
* ARQ
* Celery
* message queues
* scheduled workers

These systems remain external to the underwriting engine.

---

# Failure Handling

Background failures must not corrupt deterministic underwriting outputs.

Examples:

* failed notification
* failed export
* failed AI summary
* failed refresh job

must never alter authoritative financial calculations.

---

# Observability

Future event infrastructure should support:

* structured logging
* event tracing
* retry visibility
* dead-letter queues
* monitoring dashboards
* audit replay

---

# Long-Term Direction

Future platform versions may evolve toward:

* distributed processing
* analytics pipelines
* streaming portfolio metrics
* automated intelligence refreshes
* collaborative workflows

The deterministic underwriting engine remains:

* isolated
* synchronous
* deterministic
* independently testable
