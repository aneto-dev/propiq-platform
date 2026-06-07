# PropIQ Platform — Intelligence Architecture

## Purpose

This document defines the intelligence layer of the PropIQ platform.

The intelligence layer enriches investor decision-making through external data,
monitoring, enrichment, and operational awareness.

The intelligence layer is explicitly separated from the deterministic
underwriting engine.

Intelligence may become stale, incomplete, unavailable, or refreshed.

Underwriting calculations must remain reproducible and authoritative even if
all intelligence services are unavailable.

---

## Core Principle

The underwriting engine produces financial truth.

The intelligence layer produces context.

Context may influence investor decisions.

Context must never modify historical underwriting outputs.

---

## Intelligence Categories

### Property Intelligence

External property-related information:

* EPC ratings
* EPC history
* Property characteristics
* Property age
* Floorplans
* Property images
* UPRN data
* Address enrichment

### Listing Intelligence

Monitoring of third-party property listings.

Examples:

* Listing first seen
* Price reductions
* Price increases
* Sold STC status
* Under offer status
* Listing removal
* Listing reactivation
* New floorplans
* New photos

Purpose:

Track properties already under consideration.

Not to become a property portal.

### Planning Intelligence

Planning and regulatory information:

* Article 4 directions
* Planning applications
* Conservation areas
* Listed buildings
* Development constraints

### Area Intelligence

Location-based context:

* Crime statistics
* Flood risk
* Schools
* Demographics
* Population trends
* Employment indicators

### Market Intelligence

Market-level information:

* Comparable sales
* Rental comparables
* Yield trends
* Local market trends
* Supply and demand indicators

## Data Sources

Potential intelligence sources may include:

- EPC Register
- Planning Data England
- Land Registry
- ONS
- Police UK
- Environment Agency
- Property listing portals
- Commercial data providers

Source availability must not affect underwriting calculations.

---

## Architectural Boundary

The intelligence layer:

* may use APIs
* may use refresh jobs
* may use event-driven processing
* may use caching
* may use AI summarisation

The underwriting engine:

* must not depend on intelligence availability
* must remain deterministic
* must remain reproducible
* must remain independently testable

---

## Data Classification

Intelligence data is advisory.

It is not authoritative financial truth.

Intelligence records may be:

* refreshed
* updated
* replaced
* re-fetched

Historical snapshots remain immutable and independent of intelligence updates.

---

## Intelligence Events

Examples:

* ListingFirstSeen
* ListingPriceChanged
* ListingRemoved
* ListingStatusChanged
* ListingReactivated
* FloorplanDiscovered
* EPCDataUpdated
* PlanningDataUpdated
* FloodRiskUpdated
* RegulatoryDataRefreshed

---

## Future AI Usage

AI may interpret intelligence.

Examples:

* Explain planning risk
* Summarise market conditions
* Interpret floorplans
* Highlight unusual listing changes

AI outputs are advisory only.

AI outputs never become authoritative underwriting outputs.

---

## Long-Term Direction

The intelligence layer evolves into the investor awareness system for PropIQ.

The underwriting engine answers:

"Is this deal financially viable?"

The intelligence layer answers:

"What should the investor know about this property, location, and opportunity?"
