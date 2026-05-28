# Data Ownership Boundaries

# Purpose

This document defines ownership, mutability, authority, and lifecycle boundaries for major data domains within the platform.

The goal is to preserve:

* trust
* auditability
* determinism
* operational clarity
* historical reproducibility

---

# Core Principle

Not all platform data behaves the same way.

Some data must be immutable forever.

Some data may refresh over time.

Some data is advisory only.

Some data is authoritative.

These distinctions must remain explicit.

---

# Data Domain Classification

| Domain                       | Authoritative | Mutable | Historical  | Notes                       |
| ---------------------------- | ------------- | ------- | ----------- | --------------------------- |
| Underwriting snapshots       | Yes           | No      | Permanent   | Core financial truth        |
| User assumptions             | Yes           | Yes     | Versioned   | User overrides always win   |
| Regulatory intelligence      | No            | Yes     | Refreshable | Informational               |
| AI summaries                 | No            | Yes     | Ephemeral   | Advisory only               |
| Portfolio operational state  | Yes           | Yes     | Partial     | Workflow state              |
| Engine configuration         | Yes           | No      | Versioned   | Never overwritten           |
| Risk flags                   | Derived       | No      | Permanent   | Snapshot-scoped             |
| External cached intelligence | No            | Yes     | Expirable   | Requires freshness metadata |

---

# Immutable Domains

## Underwriting Snapshots

Snapshots are immutable.

They represent:

* exact inputs
* exact assumptions
* exact configuration versions
* exact engine outputs

Snapshots must never be modified after creation.

Recalculation creates a new snapshot.

---

## Engine Configuration

Configuration records are append-only.

Examples:

* SDLT rules
* tax bands
* stress rates
* lender assumptions

Configuration is versioned rather than overwritten.

---

# Mutable Domains

## Portfolio Operational State

Portfolio workflow data changes over time.

Examples:

* deal status
* refurbishment progress
* tenant status
* lender stage
* refinance stage

This operational state is mutable.

---

## Regulatory Intelligence

Regulatory intelligence may refresh over time.

Examples:

* Article 4
* licensing rules
* EPC restrictions
* flood risk
* planning overlays

This data requires:

* timestamps
* source attribution
* freshness tracking

---

# Advisory Domains

## AI Outputs

AI-generated content is advisory only.

AI may provide:

* summaries
* explanations
* commentary
* educational guidance

AI must never generate authoritative financial outputs.

AI outputs may be regenerated or discarded.

---

# Authority Hierarchy

Priority order:

1. User override
2. Snapshot-stored value
3. External verified provider
4. Platform default
5. AI-generated suggestion

This hierarchy is absolute.

---

# Historical Reproducibility

Historical calculations must always remain reproducible.

This requires preserving:

* snapshot inputs
* engine version
* configuration versions
* formula behaviour
* risk evaluation logic

Future recalculations must never silently rewrite history.

---

# Freshness Requirements

External intelligence requires freshness metadata.

Future metadata may include:

* source URL
* collection timestamp
* last verified timestamp
* confidence score
* expiration timestamp

Users must understand when data may be stale.

---

# Architectural Boundary

The deterministic underwriting engine remains the authoritative financial system of record.

All other systems:

* workflow
* AI
* area intelligence
* integrations
* dashboards

consume engine outputs but do not redefine them.
