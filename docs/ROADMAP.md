# PropIQ Platform — Roadmap

# Phase 1 — Underwriting Engine Foundation

## Goals

Build the core trusted underwriting engine.

## Features

* purchase analysis
* SDLT calculation
* mortgage modelling
* yield calculations
* cash flow analysis
* stress testing
* Section 24 handling
* calculation snapshots
* assumption versioning
* risk flags

## Non-Goals

* maps
* AI insights
* property sourcing
* nationwide search
* automated valuation

---

# Phase 2 — Persistence & User Platform

## Features

* authentication
* saved deals
* deal history
* portfolio management
* analysis comparison
* recalculation workflows

---

# Phase 3 — Area Intelligence

## Features

* crime data
* EPC integration
* flood risk
* school ratings
* deprivation indices
* licensing overlays
* local authority enrichment

---

# Phase 4 — Portfolio Analytics

## Features

* portfolio cash flow
* refinance tracking
* debt exposure
* risk concentration
* portfolio stress testing

---

# Phase 5 — AI-Assisted Insights

## Features

* deal summaries
* risk explanations
* assumption interpretation
* portfolio commentary
* investor education

AI remains:

* non-authoritative,
* explainable,
* and secondary to deterministic calculations.

---

# Long-Term Direction

Potential future areas:

* lender integrations
* broker workflows
* refinancing alerts
* planning intelligence
* market trend analysis
* professional investor tooling
* mobile companion app

The platform remains:

* underwriting-first,
* trust-first,
* and transparency-first.

## Article 4 Direction Checks

Future area intelligence must support Article 4 planning restriction checks.

Article 4 is not part of the deterministic underwriting engine. It belongs to the future regulatory and spatial intelligence layer.

The platform should eventually support:
- Article 4 direction lookup by address/postcode
- local authority source attribution
- planning restriction warnings
- HMO conversion feasibility checks
- manual verification status
- date last checked
- source URL

Article 4 results may influence deal risk flags or feasibility warnings, but must not be embedded inside core financial calculation formulas.

## Future Capability — Assumption Provenance and Source Attribution

The platform should eventually support detailed provenance tracking for all non-user-provided assumptions.

Future functionality may include:

* source provider tracking
* source URLs
* collection timestamps
* last verified timestamps
* confidence scoring
* stale data warnings
* assumption override tracking
* user-visible source attribution
* assumption change history

This capability is important for:

* trust
* auditability
* enterprise reporting
* lender confidence
* historical reproducibility

---

## Future Capability — Explainability Layer

Future platform versions should support explainable underwriting outputs.

Users should eventually be able to understand:

* why a risk flag triggered
* why a metric changed
* which assumptions affected the result
* which tax pathway applied
* which configuration versions were used
* how outputs were derived

Potential future features include:

* calculation breakdown trees
* assumption impact summaries
* comparison explanations
* audit exports
* investor-ready reporting
* lender-ready explanations

AI-generated commentary must remain visually and architecturally separate from authoritative calculation outputs.

---

## Future Capability — Scenario and Sensitivity Analysis

The platform should eventually support scenario-based underwriting and sensitivity analysis.

Potential scenario types include:

* base case
* optimistic case
* pessimistic case
* high-rate stress case
* refinance case
* BRRR case
* HMO conversion case
* exit/sale case

Scenario analysis should support comparison across:

* rent assumptions
* interest rates
* void periods
* refurbishment costs
* refinancing assumptions
* operating costs
* tax changes

Each scenario should generate its own immutable snapshot record.

---

## Future Capability — Regulatory and Spatial Intelligence

Future area intelligence should eventually support:

* Article 4 restrictions
* HMO licensing
* selective licensing
* additional licensing
* conservation areas
* flood risk overlays
* EPC restriction warnings
* local authority planning overlays
* planning feasibility warnings
* postcode intelligence
* geospatial deal analysis

This intelligence belongs to a future regulatory and spatial intelligence layer rather than the deterministic underwriting engine.

Future implementations may eventually use:

* PostGIS
* spatial indexing
* local authority datasets
* external regulatory APIs
* cached area intelligence pipelines
