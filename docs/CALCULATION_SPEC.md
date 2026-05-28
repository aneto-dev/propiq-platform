# PropIQ Platform — Calculation Specification

## Purpose

This document defines the underwriting engine behaviour for the platform.

The engine must be:

* deterministic,
* explainable,
* versioned,
* testable,
* and historically reproducible.

AI models must never generate authoritative calculations.

---

# Calculation Principles

## Deterministic Outputs

The same inputs and assumptions must always produce the same outputs.

---

## Explicit Assumptions

All assumptions must:

* be visible,
* configurable,
* and versioned.

---

## Immutable Historical Analysis

Saved calculations are snapshots and must never silently change.

---

# High-Level Calculation Flow

## Step 1 — Validate Inputs

Validate:

* required fields,
* numeric ranges,
* enums,
* financing constraints,
* tax assumptions.

---

## Step 2 — Calculate Acquisition Costs

Includes:

* SDLT
* legal fees
* survey
* refurbishment
* setup costs

Outputs:

* total acquisition cost
* total cash deployed

---

## Step 3 — Calculate Financing

Includes:

* loan amount
* deposit
* mortgage payment
* stressed interest
* LTV

---

## Step 4 — Calculate Effective Rent

Apply:

* void allowance
* effective annual rent

---

## Step 5 — Calculate Operating Costs

Includes:

* management fees
* maintenance reserve
* insurance
* service charges
* ground rent
* HMO licensing

---

## Step 6 — Calculate NOI

Formula:
noi = effective_annual_rent - operating_costs

---

## Step 7 — Calculate Tax

Includes:

* Section 24 handling
* corporation tax handling
* investor type rules

---

## Step 8 — Calculate Cash Flow

Includes:

* mortgage costs
* estimated tax
* annual cash flow
* monthly cash flow

---

## Step 9 — Calculate Yields & Returns

Includes:

* gross yield
* net yield
* cash-on-cash return
* ROCE

---

## Step 10 — Calculate Stress Testing

Includes:

* stressed interest
* ICR
* affordability checks

---

## Step 11 — Generate Risk Flags

Potential flags:

* NEGATIVE_CASHFLOW
* LOW_ICR
* HIGH_LEVERAGE
* LOW_MARGIN_SAFETY
* HIGH_REFURB_RATIO

---

## Step 12 — Persist Snapshot

Snapshot must store:

* all inputs
* assumptions
* version IDs
* engine version
* outputs
* timestamp

Snapshots are immutable.

---

# Versioned Assumptions

The following must remain versioned:

* SDLT tables
* corporation tax rates
* stress test assumptions
* default void rates
* maintenance assumptions
* insurance assumptions

Configuration data is never overwritten.

---

# Recalculation Rules

## Original Analysis

Users must always be able to view the original snapshot.

---

## Recalculate With Latest Rates

Recalculation:

* uses latest assumptions,
* creates new snapshot,
* preserves historical version.

---

# Important Constraints

The platform:

* is not financial advice,
* does not predict future performance,
* does not guarantee profitability,
* and models deals under stated assumptions only.

Outputs are:

* estimates,
* projections,
* and scenario-based calculations.
