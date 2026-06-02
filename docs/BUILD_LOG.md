# PropIQ Platform — Build Log

Implementation progress log. Updated after each commit is verified and pushed.
Branch: `implementation-v1`

---

## Phase 0 — Foundation

| Commit | Message | Status | Notes |
|---|---|---|---|
| 0.1 | `chore: initialise monorepo structure` | ✅ Complete | .gitignore, README, Makefile, top-level dirs |
| 0.2 | `infra: add docker-compose for local postgres with PostGIS` | ✅ Complete | PostGIS 3.4 verified: `USE_GEOS=1 USE_PROJ=1 USE_STATS=1` |
| 0.3 | `chore: python 3.13 project with pyproject.toml` | ✅ Complete | Poetry install verified, pytest runs (0 tests) |
| 0.4 | `feat: fastapi application factory with health endpoint` | ✅ Complete | `GET /api/v1/health → {"status":"ok"}` verified |
| 0.5 | `chore: initialise alembic with async engine` | ✅ Complete | `alembic current` works, async NullPool config correct |
| 0.6 | `chore: makefile targets for dev workflow` | ✅ Complete | All targets verified: dev, test, migrate, seed, lint, typecheck, shell |

**Phase 0 exit criteria:** All met. `make dev` starts postgres and uvicorn. Health endpoint responds.

---

## Phase 1 — Domain Entities and Enums

| Commit | Message | Status | Tests added | Running total |
|---|---|---|---|---|
| 1.1 | `feat(domain): define all domain enums` | ✅ Complete | 0 | 0 |
| 1.2 | `feat(domain): define typed domain errors` | ✅ Complete | 0 | 0 |
| 1.3 | `feat(domain): define value objects` | ✅ Complete | 0 | 0 |
| 1.4 | `feat(domain): define User, InvestorProfile, Property, Deal entities` | ✅ Complete | 0 | 0 |
| 1.5 | `feat(domain): define CalculationSnapshot aggregate entity` | ✅ Complete | 0 | 0 |
| 1.6 | `test(domain): unit tests for entity invariants and value objects` | ✅ Complete | 46 | 46 |

**Architecture correction applied during Phase 1:**
- `fix(domain): allow negative rate values` — `Rate` value object incorrectly
  rejected negative values. DOMAIN_MODEL_ARCHITECTURE.md Part 8.3 and
  ENGINE_CONTRACTS.md E-03 require negative `cash_on_cash_return_percent`.
  Constraint removed. Regression test `test_negative_rate_accepted` added.

**Phase 1 exit criteria:** All met. 46 tests pass. Zero mypy/ruff errors.

---

## Phase 2 — Underwriting Engine

### Commit 2.1 — Engine contracts

**Message:** `feat(engine): EngineInput, EngineConfig, EngineResult contracts`
**Status:** ✅ Complete
**Tests added:** 0 | **Running total:** 46

**Files created:**
- `backend/app/engine/__init__.py`
- `backend/app/engine/version.py` — `ENGINE_VERSION = "1.0.0"`
- `backend/app/engine/contracts.py` — 15 frozen dataclass types

**Types defined:** `SDLTBand`, `SDLTConfig`, `CorporationTaxConfig`,
`AssumptionConfig`, `EngineConfig`, `EngineInput`, `SDLTBandResult`,
`EngineOutputs`, `EngineIntermediates`, `RiskFlag`, `ValidationWarning`,
`EngineResult`, `ValidationError`, `ValidationResult`, `EngineError`

**Files modified:**
- `backend/app/domain/errors.py` — `CalculationValidationFailure` tightened
  from `list[Any]` to `list[ValidationError]` / `list[ValidationWarning]`

---

### Commit 2.2 — Formulas F-01 through F-08

**Message:** `feat(engine): income and financing formulas F-01 through F-08`
**Status:** ✅ Complete
**Tests added:** 47 | **Running total:** 93

**Files created:**
- `backend/app/engine/calculations/__init__.py`
- `backend/app/engine/calculations/formulas.py`
- `backend/tests/unit/formulas/__init__.py`
- `backend/tests/unit/formulas/test_f01_gross_annual_rent.py`
- `backend/tests/unit/formulas/test_f02_void_rate_conversion.py`
- `backend/tests/unit/formulas/test_f03_effective_annual_rent.py`
- `backend/tests/unit/formulas/test_f04_loan_amount.py`
- `backend/tests/unit/formulas/test_f05_ltv.py`
- `backend/tests/unit/formulas/test_f06_monthly_mortgage_payment.py`
- `backend/tests/unit/formulas/test_f07_annual_mortgage_cost.py`
- `backend/tests/unit/formulas/test_f08_annual_mortgage_interest.py`

**Formulas implemented:**

| Formula | Function | Key notes |
|---|---|---|
| F-01 | `f01_gross_annual_rent` | `monthly_rent × 12` |
| F-02 | `f02_void_rate_decimal` | `void_pct / 100` |
| F-03 | `f03_effective_annual_rent` | `gross × (1 - void_decimal)` |
| F-04 | `f04_loan_amount` | `purchase_price - deposit` |
| F-05 | `f05_ltv_percent` | `(loan / price) × 100`; zero-safe |
| F-06 | `f06_monthly_mortgage_payment` | IO and repayment annuity; zero-rate → 0 |
| F-07 | `f07_annual_mortgage_cost` | `monthly × 12` |
| F-08 | `f08_annual_mortgage_interest` | IO exact; repayment uses 12-month amortisation loop |

**Verification:** F-06 repayment: £150k@4.75%/25yr → £855.18/month (confirmed).

---

### Commit 2.3 — Formulas F-09 through F-15

**Message:** `feat(engine): operating cost and acquisition formulas F-09 through F-15`
**Status:** ✅ Complete
**Tests added:** 54 | **Running total:** 147

**Files modified:**
- `backend/app/engine/calculations/formulas.py` — 7 functions + 2 NamedTuples appended

**Files created:**
- `backend/tests/unit/formulas/test_f09_letting_agent.py`
- `backend/tests/unit/formulas/test_f10_maintenance_reserve.py`
- `backend/tests/unit/formulas/test_f11_total_operating_costs.py`
- `backend/tests/unit/formulas/test_f12_noi.py`
- `backend/tests/unit/formulas/test_f13_sdlt.py`
- `backend/tests/unit/formulas/test_f14_total_acquisition_cost.py`
- `backend/tests/unit/formulas/test_f15_total_cash_deployed.py`

**Formulas implemented:**

| Formula | Function | Key notes |
|---|---|---|
| F-09 | `f09_letting_agent_annual` | `gross × (fee/100) × (1 + vat/100)`; applied to gross_annual_rent |
| F-10 | `f10_annual_maintenance_reserve` | `purchase_price × (pct/100)` |
| F-11 | `f11_total_operating_costs` | Sum of 6 components |
| F-12 | `f12_net_operating_income` | `effective_rent - total_ops`; may be negative |
| F-13 | `f13_sdlt` | Progressive banded + flat surcharge; returns `SDLTResult` NamedTuple |
| F-14 | `f14_total_acquisition_cost` | `price + sdlt + legal + refurb` |
| F-15 | `f15_total_cash_deployed` | `deposit + sdlt + legal + refurb`; loan excluded |

**New types defined in formulas.py:**
- `SDLTBandCalculation` — NamedTuple per-band result
- `SDLTResult` — NamedTuple: `sdlt_base`, `sdlt_surcharge`, `total_sdlt`, `band_breakdown`

**F-09 discrepancy documented:** ENGINE_CONTRACTS.md E-01 shows
`letting_agent_annual=1,384.62` (effective-rent-based). CALCULATION_SPEC.md
F-09 formula and all other scenarios (E-05, E-06) confirm fee applied to
`gross_annual_rent`. CALCULATION_SPEC.md governs. Implementation uses
gross_annual_rent. Documented in `test_applied_to_gross_not_effective`.

**SDLT boundary tests:** All 12 boundary values (£100k through £2m) verified
against HMRC methodology. E-01/E-03/E-05 cross-reference cases confirmed.

---

### Commit 2.4 — Formulas F-16 through F-22

**Status:** ⏳ Planned — implementation plan below

---

### Commit 2.5 — Tax pathways
**Status:** ⏳ Not started

### Commit 2.6 — Validation pipeline
**Status:** ⏳ Not started

### Commit 2.7 — Risk flag definitions
**Status:** ⏳ Not started

### Commit 2.8 — Engine orchestrator
**Status:** ⏳ Not started

### Commit 2.9 — Reference scenario fixtures
**Status:** ⏳ Not started

### Commit 2.10 — Regression tests E-01 through E-06
**Status:** ⏳ Not started

### Commit 2.11 — Regression tests E-07 through E-12 + determinism
**Status:** ⏳ Not started
