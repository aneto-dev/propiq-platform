# Trust Model

# Purpose

This document defines how the PropIQ platform establishes, preserves, and communicates trust.

Property investment decisions involve significant financial risk.

Users must be able to trust:

* calculations
* assumptions
* historical outputs
* configuration behaviour
* explanations
* audit history
* data provenance

Trust is treated as a first-class architectural concern.

---

# Core Principle

The platform prioritises:

* reproducibility
* explainability
* transparency
* auditability
* deterministic behaviour

over:

* hidden optimisation
* opaque scoring
* black-box intelligence
* non-repeatable calculations

---

# Trust Foundations

## Deterministic Calculations

The underwriting engine is deterministic.

Given identical:

* inputs
* assumptions
* configuration versions

the engine must always produce identical outputs.

---

## Immutable Snapshots

Historical underwriting snapshots are append-only and immutable.

Snapshots preserve:

* user inputs
* assumptions
* configuration versions
* outputs
* risk flags
* engine version

Historical records must never silently change.

---

## Explainability

Users should eventually understand:

* how outputs were derived
* which assumptions affected results
* why risk flags triggered
* which tax pathways applied
* which configuration versions were used

Explainability is a product requirement, not a UI enhancement.

---

## Assumption Provenance

Platform-generated assumptions must eventually support provenance tracking.

Examples:

* source provider
* collection date
* verification date
* confidence level
* stale data warnings

Users must understand where platform intelligence originates.

---

## AI Boundary

AI-generated outputs are advisory only.

AI may:

* explain
* summarise
* compare
* educate
* suggest scenarios

AI must never generate authoritative financial calculations.

The deterministic underwriting engine remains the financial system of record.

---

## User Override Authority

Explicit user-provided assumptions always take precedence over:

* AI suggestions
* platform defaults
* external intelligence providers

The platform must never silently override user intent.

---

## Historical Reproducibility

Users must always be able to reproduce historical calculations.

This requires preserving:

* configuration versions
* formula behaviour
* engine version
* assumptions
* risk evaluation logic

Recalculation creates new snapshots rather than mutating old ones.

---

# Trust Threats

The platform explicitly avoids:

* silent assumption changes
* hidden scoring logic
* opaque AI outputs
* non-versioned configuration
* mutable historical calculations
* undisclosed optimisation logic
* untraceable intelligence sources

---

# Long-Term Direction

Future platform trust features may include:

* audit exports
* calculation lineage
* formula traceability
* assumption impact analysis
* scenario comparison explanations
* portfolio drift analysis
* regulatory drift alerts

The platform direction remains:

* trust-first
* underwriting-first
* explainability-first
* operationally transparent
