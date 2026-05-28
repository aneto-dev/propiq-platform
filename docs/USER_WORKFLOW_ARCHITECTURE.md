# User Workflow Architecture

# Purpose

This document defines the operational investor workflow lifecycle within the PropIQ platform.

The purpose is to ensure the platform evolves into a complete investor operating system rather than remaining a standalone underwriting calculator.

This document defines:

* lifecycle stages
* workflow state transitions
* operational boundaries
* mutable vs immutable records
* future workflow automation direction

---

# Core Principle

Underwriting is only one stage of the investment lifecycle.

The platform must eventually support the full operational journey of a property investment.

The deterministic underwriting engine remains the authoritative financial calculation system, but the broader platform manages investor workflow and operational state.

---

# High-Level Lifecycle

```text
Lead / Sourced Deal
    ↓
Initial Screening
    ↓
Underwriting
    ↓
Offer Submitted
    ↓
Offer Accepted
    ↓
Due Diligence
    ↓
Financing
    ↓
Refurbishment
    ↓
Letting / Stabilisation
    ↓
Refinance
    ↓
Portfolio Hold
    ↓
Exit / Sale
```

---

# Workflow Stages

## 1. Lead / Sourced Deal

Potential investment opportunity is created.

Possible future sources:

* Rightmove
* Zoopla
* auction feed
* manual entry
* sourcing agent
* spreadsheet import
* CRM integration

This stage is informational only.

No authoritative underwriting exists yet.

---

## 2. Initial Screening

Fast high-level feasibility assessment.

Potential checks:

* estimated yield
* estimated cash flow
* area suitability
* high-level risk indicators
* basic lending feasibility

Outputs are provisional.

Detailed underwriting has not yet occurred.

---

## 3. Underwriting

The deterministic underwriting engine is executed.

This stage generates:

* immutable calculation snapshots
* risk flags
* financing metrics
* tax calculations
* stress testing outputs
* scenario comparisons

Underwriting outputs become part of the permanent audit history.

---

## 4. Offer Submitted

User operationally records:

* offer amount
* offer date
* negotiation notes
* estate agent details
* vendor status

This stage does not alter underwriting snapshots.

---

## 5. Offer Accepted

Deal moves into acquisition workflow.

Potential future functionality:

* solicitor tracking
* broker tracking
* lender workflow
* valuation tracking
* document collection
* due diligence checklist

---

## 6. Due Diligence

Operational and regulatory verification stage.

Potential future checks:

* Article 4
* HMO licensing
* flood risk
* EPC restrictions
* planning constraints
* title issues
* tenant status
* leasehold review

These checks belong outside the deterministic underwriting engine.

---

## 7. Financing

Tracks lending progression.

Potential future functionality:

* lender comparison
* mortgage application tracking
* stress-rate comparison
* product expiry alerts
* refinance modelling
* bridging finance workflows

---

## 8. Refurbishment

Tracks refurbishment execution.

Potential future functionality:

* budget tracking
* contractor tracking
* timeline management
* cost variance analysis
* staged refinance modelling

---

## 9. Letting / Stabilisation

Tracks operational rental performance.

Potential future functionality:

* tenant onboarding
* rent tracking
* void tracking
* occupancy metrics
* operational cash flow variance

---

## 10. Refinance

Tracks refinance lifecycle.

Potential future functionality:

* updated valuations
* refinance proceeds
* capital recycling
* lender switching
* debt restructuring

Each refinance analysis generates new immutable snapshots.

---

## 11. Portfolio Hold

Long-term operational ownership stage.

Potential future analytics:

* portfolio yield
* DSCR monitoring
* debt maturity tracking
* concentration risk
* rolling cash flow analysis

---

## 12. Exit / Sale

Tracks disposal and realised returns.

Potential future functionality:

* capital gains estimation
* realised ROCE
* total lifecycle return
* disposal cost analysis

---

# Workflow State vs Snapshot State

## Important Boundary

Workflow state is mutable.

Calculation snapshots are immutable.

Examples:

* deal status may change
* lender status may change
* refurbishment stage may change

However:

* historical underwriting snapshots never change
* historical assumptions never change
* historical outputs never change

---

# Future Workflow Automation

Potential future automations:

* stale deal reminders
* refinance alerts
* lender expiry alerts
* planning review reminders
* portfolio stress alerts
* regulatory change alerts

These workflows operate outside the deterministic engine.

---

# Architectural Boundary

Workflow orchestration belongs to the application/service layer.

The underwriting engine remains:

* deterministic
* stateless
* geographically agnostic
* operationally isolated
* independently testable

Workflow systems consume underwriting outputs but do not modify engine behaviour.

---

# Future Direction

Future versions may eventually support:

* broker collaboration
* accountant access
* investor teams
* sourcing pipelines
* CRM integration
* lender integrations
* workflow automations
* task systems
* portfolio operations

The platform direction remains:

* underwriting-first
* trust-first
* workflow-aware
* operationally scalable
