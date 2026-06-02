# PropIQ Platform — Roadmap

---

## Platform Identity

PropIQ is an **Investor Operating System** for UK property investors.

Underwriting is the first capability — the foundation that earns trust —
but it is not the final destination. PropIQ begins with underwriting and
evolves into the system where investors manage their entire deal and portfolio
lifecycle: from initial analysis through acquisition, hold, refinance, and exit.

**Underwriting is the first shipped capability, not the product's identity.**

The underwriting engine establishes trust. The operating system builds retention.
Every feature added after launch deepens the investor's operational usefulness
within the platform.

---

## Strategic Layers

The platform is built in layers. Each layer preserves the trust boundaries
established by all previous layers.

```
Layer 1 — Deterministic Financial Truth
    The underwriting engine: authoritative calculations,
    immutable snapshots, explicit assumptions, transparent risk flags.
    This is what earns the right to charge.

Layer 2 — Deal Operating System
    The deal lifecycle: from analysis through acquisition, hold,
    and exit. Operational tracking, mortgage expiry, actual vs
    projected performance. This is what earns the right to retain.

Layer 3 — Intelligence and Explainability
    Scenario analysis, sensitivity testing, regulatory intelligence,
    explainability tooling. This is what earns the right to grow.

Layer 4 — Portfolio Intelligence
    Portfolio analytics, refinance modelling, portfolio stress testing,
    debt management. This is what earns enterprise pricing.

Layer 5 — Platform and Ecosystem
    AI-assisted insights, team collaboration, broker/accountant tooling,
    lender integrations. This is what earns platform value.
```

Each layer must preserve the deterministic trust boundaries established in
earlier layers.

---

## Phase 1 — Underwriting Foundation (first shipped capability)

### Goal

Ship the most trusted underwriting tool available to UK property investors,
framed as the foundation of an investor operating system.

The first user experience is: **add a deal to your pipeline, analyse it.**
The analysis is a step within the deal — not the end of the journey.

### Features

- Deal creation and pipeline management (DRAFT status)
- Purchase analysis with full breakdown
- SDLT calculation — banded, line-by-line, verifiable
- Mortgage modelling (interest-only and repayment)
- Yield calculations (gross and net)
- Cash flow analysis (pre-tax and post-tax)
- Section 24 handling — step-by-step display
- Ltd Co vs personal comparison (two scenarios, same deal)
- ICR stress testing
- Calculation snapshots — immutable, attributed, versioned
- Assumption versioning and provenance
- Risk flags with explanations
- Subscription gate (free tier: 3 deals, paid tier: unlimited)

### Not in Phase 1

- Maps
- Area intelligence
- AI insights
- Workflow tracking beyond DRAFT/ANALYSED
- Portfolio analytics
- Mortgage expiry tracking
- Actual vs projected performance

### Phase 1 Exit Criteria

- Investors can add a deal, analyse it, and trust the result
- The analysis output is explainable line by line
- A paying subscriber can save and return to their deals
- The product is positioned and described as an investor operating system
  where underwriting is the first capability, not the whole product

---

## Phase 2 — Retention Foundation (first reason to stay subscribed)

### Goal

Give subscribers a reason to return between deals and a reason not to cancel
after purchasing a property.

Without Phase 2, subscribers who purchase a property have no ongoing reason
to be subscribed. Phase 2 fixes this.

### Features

**Deal lifecycle expansion**

- Deal status tracking: Analysing → Offer Submitted → Purchased → Held → Exited
- Status transitions visible in the UI from the deal page
- Portfolio view: all deals by status

**Mortgage expiry tracking**

- Mortgage product end date field on purchased deals
- 90-day and 30-day email reminders before expiry
- Refinance modelling triggered from the expiry reminder

**Actual vs projected performance**

- Monthly actual rent field on held deals
- Monthly actual costs field (optional, aggregated)
- Variance display: actual vs original snapshot projection
- Simple chart: projected cash flow vs actual over time

**Portfolio summary**

- Dashboard: number of properties held, aggregate projected vs actual cash flow
- Total capital deployed across portfolio
- Upcoming mortgage expiries

### Retention anchors added by Phase 2

These features give subscribers ongoing operational reasons to stay subscribed:

1. **Mortgage expiry dates** — time-sensitive information tracked in one place;
   users with upcoming expiries have an active reason to engage
2. **Actual performance history** — accumulated month by month; the historical
   record grows more valuable over time and is directly exportable for
   accountancy and tax purposes
3. **Deal pipeline** — the full lifecycle of active deals in one view; this
   becomes the operational record of an investor's property business

Users own all of their data. Export is supported. Retention comes from the
accumulated value, operational convenience, and workflow integration that
the platform provides — not from restricting access to user-owned records.

### Phase 2 Exit Criteria

- A subscriber who purchased a property 6 months ago returns monthly to
  update their actual rent
- A subscriber receives an email 90 days before their mortgage expires
- The dashboard shows a meaningful portfolio summary for a 3-property investor

---

## Phase 3 — Depth (first reason to prefer PropIQ over alternatives)

### Goal

Add capabilities that competitors cannot easily replicate and that serve the
analytical investor's deeper needs.

### Features

**Underwriting depth**

- HMO analysis (per-room income modelling)
- BRRR scenario modelling (purchase → refurb → refinance → hold)
- Sensitivity analysis (what if rate rises 1%? what if void doubles?)
- Scenario comparison (saved side-by-side)

**Explainability layer**

- Step-by-step calculation breakdown (why did this number come from?)
- Assumption impact analysis (which input affects the result most?)
- Section 24 visual explainer
- PDF export (lender-ready, accountant-ready)

**Area intelligence (first pass)**

- Flood risk warning (Environment Agency — free API)
- EPC rating lookup
- Article 4 direction warnings by postcode

### Phase 3 Exit Criteria

- HMO investors use PropIQ for all deal analysis
- Investors share PDF reports with brokers and accountants
- Sensitivity analysis is used to model rate rise scenarios

---

## Phase 4 — Portfolio Intelligence

### Goal

Become the operational intelligence layer for investors with 5+ properties.

### Features

- Portfolio-level cash flow analysis
- Debt maturity calendar (all mortgage expiries in one view)
- Refinance pipeline tracking
- Debt exposure and concentration risk
- Portfolio stress testing (what happens to the portfolio if rates rise 2%?)
- Equity tracking across portfolio
- Capital recycling modelling (BRRR portfolio view)

### Phase 4 Exit Criteria

- Investors with 10+ properties rely on PropIQ for portfolio oversight
- Refinance decisions are modelled in PropIQ before engaging a broker
- Churn at month 12 is materially lower than month 6

---

## Phase 5 — AI and Platform

### Goal

Add AI-assisted insight and professional tooling without compromising the
deterministic trust model.

### Features

**AI-assisted (advisory only, never authoritative)**

- Deal summary in plain English
- Risk flag explanations in context
- "What does this mean for my situation?" — scenario interpretation
- Portfolio commentary

**Platform expansion**

- Team/advisor access (accountant reads portfolio, broker models deals)
- White-label investor report generation
- API access for professional users

AI remains:
- Non-authoritative
- Explicitly labelled as advisory
- Visually separate from deterministic calculation outputs

---

## Retention Ladder

Every new subscriber should be climbing this ladder. The further up the
ladder a subscriber is, the lower their probability of cancellation.

```
Rung 1 — ANALYSING      (Phase 1)
  Has used the analysis tool. Has seen the output. Trusts the numbers.
  Cancellation likelihood: Higher — operational value is still limited.

Rung 2 — PURCHASED      (Phase 2)
  Has marked a deal as Purchased. Has a real asset tracked in the system.
  Cancellation likelihood: Reduced. Beginning to build operational history.

Rung 3 — TRACKING       (Phase 2)
  Updating actual rent monthly. Has accumulated performance history.
  Cancellation likelihood: Materially lower. Accumulated data has real value.

Rung 4 — EXPIRY AWARE   (Phase 2)
  Has a mortgage expiry date in the system. Knows when to refinance.
  Cancellation likelihood: Low. Time-sensitive information creates active
  engagement before each expiry event.

Rung 5 — PORTFOLIO      (Phase 4)
  Has 3+ properties tracked. Portfolio analytics are meaningful.
  Cancellation likelihood: Low. High operational switching cost;
  portfolio history is exportable but not easily recreated in another tool.

Rung 6 — OPERATIONALLY INTEGRATED (Phase 4-5)
  Makes refinance decisions, portfolio decisions, and investor decisions
  from within PropIQ. Accounting exports, broker sharing, team access.
  Cancellation likelihood: Very low. Cancellation has meaningful operational
  cost and disrupts established business workflows.
```

---

## What This Roadmap Is Not

- It is not a feature wishlist
- It is not an analysis tool that adds operational features as an afterthought
- It is not a race to build every feature before charging

Every feature is evaluated against: **does this move subscribers up the
retention ladder, or does it only attract them onto it?**

Features that only attract (acquisition) are worth building after features
that retain. The exception is Phase 1, where acquisition is necessary
before retention is possible at all.

---

## Long-Term Direction

The platform remains:

- **Deal-first** — the Deal is the primary domain concept
- **Trust-first** — calculations are deterministic, explainable, immutable
- **Value-first** — every phase increases the operational usefulness of the subscription
- **Transparency-first** — assumptions are explicit, versioned, and disclosed

Future capabilities not yet scheduled:

- Lender integrations
- Broker collaboration workflows
- Auction deal workflows
- Regulatory change monitoring and alerts
- Mobile companion app
- Enterprise multi-portfolio management

---

## Future Phase — Strategy Expansion Engine

### Goal

Expand PropIQ from a standard BTL underwriting platform into a
**multi-strategy UK property investment operating system**.

The initial implementation establishes the core calculation, validation, risk,
and snapshot infrastructure around the standard buy-to-let strategy. That
infrastructure is intentionally designed to be strategy-aware rather than
hard-coded to one deal type.

This future phase extends the platform to support the full range of UK property
investment strategies used by serious investors.

### Strategies

**Residential Investment**

- Buy-to-Let (current)
- BRRR (Buy, Refurbish, Refinance, Rent)
- Property Flips
- HMO (Houses in Multiple Occupation)
- Serviced Accommodation

**Creative and Control-Based Strategies**

- Rent-to-Rent
- Lease Options
- Assisted Sale
- Vendor Finance

**Commercial and Development**

- Commercial Property
- Commercial Conversion
- Mixed-Use
- Planning Gain
- Land and Small Development

**Structured Arrangements**

- Joint Ventures
- Deal Sourcing
- Social Housing Leases

### What Each Strategy Requires

Each strategy eventually needs:

- Strategy-specific underwriting inputs
- Strategy-specific calculation model
- Strategy-specific risk flags
- Strategy-specific investor KPIs
- Scenario analysis
- Deal comparison
- Snapshot-based, versioned outputs

### Implementation Principles

This phase is future roadmap direction only. No strategy-specific code
is introduced during the current underwriting engine implementation.

The current engine must stay clean, deterministic, and focused on the
standard BTL pathway. Strategy expansion is introduced through explicit
roadmap phases, not mixed into the current formula implementation.

When strategy support is added, each strategy is implemented as a distinct
calculation module with its own contracts, formulas, and validation rules —
following the same trust-first, pure-function architecture established in
Phase 2.
