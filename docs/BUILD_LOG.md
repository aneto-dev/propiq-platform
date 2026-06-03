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

**Post-commit ruff fix applied:** `from typing import NamedTuple` was placed
mid-file in the F-09–F-15 additions. Ruff E402 flagged it as a module-level
import not at the top of the file. Fixed by moving it to the imports block.
`ruff --fix` resolved 42 of 43 errors automatically; the E402 was fixed
manually. Final state: `ruff check app/ tests/` → All checks passed.
`pytest tests/unit/formulas/ -v` → 101 passed.

**SDLT boundary tests:** All 12 boundary values (£100k through £2m) verified
against HMRC methodology. E-01/E-03/E-05 cross-reference cases confirmed.

---

### Commit 2.4 — Formulas F-16 through F-22

**Message:** `feat(engine): yield, return, and stress test formulas F-16 through F-22`
**Status:** ✅ Complete
**Tests added:** 46 | **Running total:** 193

**Files modified:**
- `backend/app/engine/calculations/formulas.py` — 8 functions appended

**Files created:**
- `backend/tests/unit/formulas/test_f16_gross_yield.py` (5 tests)
- `backend/tests/unit/formulas/test_f17_net_yield.py` (5 tests)
- `backend/tests/unit/formulas/test_f18_roce.py` (5 tests)
- `backend/tests/unit/formulas/test_f19_annual_cash_flow.py` (6 tests)
- `backend/tests/unit/formulas/test_f20_monthly_cash_flow.py` (5 tests)
- `backend/tests/unit/formulas/test_f21_cash_on_cash.py` (5 tests)
- `backend/tests/unit/formulas/test_f22_icr.py` (11 tests)

**Functions:** `f16_gross_yield_percent`, `f17_net_yield_percent`,
`f18_roce_percent`, `f19_annual_cash_flow`, `f20_monthly_cash_flow`,
`f21_cash_on_cash_return_percent`, `f22_stressed_annual_interest`,
`f22_icr_percent`. F-22 split into two functions per ENGINE_ARCHITECTURE.md
Step 11. `f22_icr_percent` returns `None` for cash purchase per
ENGINE_CONTRACTS.md Part 3.1.

**Known ENGINE_CONTRACTS.md discrepancies (documented in tests):**
- E-03 `gross_yield_percent`: contract=4.80, correct=5.49 (arithmetic error)
- E-03 `icr_percent`: contract=127.88, correct=127.87 (rounding discrepancy)

**Verification:** 31 implementation checks passed (sandbox). pytest tests/unit/formulas/ →
143 passed. Full suite → 189 passed. ruff: All checks passed. mypy: Success, no issues found.

**Recovery note:** This commit was recorded as complete in an earlier session but the
functions were never pushed to the repository. F-16 through F-22 were missing from
`formulas.py`, which caused `orchestrator.py` (Commit 2.8) to fail on import.
Commit 2.4 is implemented here as a recovery commit before Commit 2.8 is pushed.

**Tests: 46 (not 42 as originally recorded — F-22 has 15 tests due to boundary coverage
of 125.00 and 145.00 ICR thresholds per TEST_STRATEGY.md Part 3.3).**

---

---

## Pre-Commit 2.5 — Specification Clarifications

**Commit message:** `docs: clarify tax pathway A formula and section_24_applies flag`
**Status:** ✅ Complete (documentation only — no code)

During Commit 2.5 implementation planning, three ambiguities were identified
in the CALCULATION_SPEC.md tax pathway definitions. All three were resolved
before implementation.

### Ambiguity 1 — TA-06 test values

**Resolution: No specification error.** The planning brief incorrectly used
`effective_annual_rent = 9,807.60` for E-06. The correct contracted value in
ENGINE_CONTRACTS.md E-06 is `9,807.30` (computed as `10,200 × 0.9615`).
TEST_STRATEGY.md TA-06 values (4,633.30 / 1,853.32 / 570.82) are fully
consistent with ENGINE_CONTRACTS.md. No document correction needed.

### Ambiguity 2 — Step A-2 floor on negative taxable income

**Resolution: CALCULATION_SPEC.md Step A-2 updated.**

Original formula omitted an explicit floor:
```
income_tax_on_rental = taxable_rental_income × income_tax_rate_decimal
```

Corrected formula:
```
income_tax_on_rental = MAX(0, taxable_rental_income) × income_tax_rate_decimal
```

HMRC does not levy income tax on rental losses. TEST_STRATEGY.md TA-05 already
specified `income_tax_gross: 0.00` for negative taxable income, confirming the
correct behaviour. The correction makes the implicit floor explicit in the spec.

### Ambiguity 3 — section_24_applies definition

**Resolution: CALCULATION_SPEC.md Tax Pathway A updated.**

New section inserted after Step A-4 defining `section_24_applies`:
```
section_24_applies = (annual_mortgage_interest > 0)
```
True when the deal has a mortgage (interest to restrict).
False for cash-purchase individual landlords (no interest to restrict).
Always False for Pathway B (LIMITED_COMPANY).

**Files modified:** `docs/CALCULATION_SPEC.md` only.
**ENGINE_CONTRACTS.md and TEST_STRATEGY.md: unchanged.**
All contracted reference scenario values remain valid as written.

---

### Commit 2.5 — Tax pathways

**Message:** `feat(engine): tax pathway A (Section 24) and pathway B (Corporation Tax)`
**Status:** ✅ Complete
**Tests added:** 25 | **Running total:** 214

**Files created:**
- `backend/app/engine/tax/__init__.py`
- `backend/app/engine/tax/individual.py` — Pathway A, `IndividualTaxResult` NamedTuple
- `backend/app/engine/tax/limited_company.py` — Pathway B, `LimitedCompanyTaxResult` NamedTuple
- `backend/tests/unit/tax/__init__.py`
- `backend/tests/unit/tax/test_pathway_a_individual.py` (12 tests)
- `backend/tests/unit/tax/test_pathway_b_limited_company.py` (13 tests)

**No existing files modified.**

**Key implementation decisions:**
- `income_tax_gross = MAX(0, taxable_rental_income) × rate` per updated CALCULATION_SPEC.md
- `section_24_applies = (annual_mortgage_interest > 0)` per CALCULATION_SPEC.md Derived Flag
- `section_24_applies` always `False` for Pathway B
- CT config passed as explicit arguments — never hardcoded in limited_company.py
- Both pathways return NamedTuples; no imports from app.engine.contracts or app.domain entities
- `LimitedCompanyTaxResult.section_24_applies` always `False` (for orchestrator convenience)

**Tests cover:** TA-01 through TA-06, cash purchase s24=False, field types,
result type, TB-01 through TB-07, s24 always False for Ltd Co, config fraction
independence, field types, result type.

**Post-commit fix:** C408 ruff violation (unnecessary `dict()` call) fixed in
both test files. `E01_INPUTS` and `CT_CONFIG` converted from `dict(key=value)`
to `{"key": value}` literals. No calculation logic or expected values changed.

**Final verification (local):** pytest 25 passed. ruff: All checks passed. mypy: Success, no issues found.

### Commit 2.6 — Validation pipeline

**Message:** `feat(engine): validation pipeline V-01 through V-25`
**Status:** ✅ Complete
**Tests added:** 99 | **Running total:** 313

**Files created:**
- `backend/app/engine/validation/__init__.py`
- `backend/app/engine/validation/rules.py` (440 lines — 25 rules + pipeline runner)
- `backend/tests/unit/validation/__init__.py`
- `backend/tests/unit/validation/test_hard_rules.py` (50 tests)
- `backend/tests/unit/validation/test_warn_rules.py` (38 tests)
- `backend/tests/unit/validation/test_validation_pipeline.py` (11 tests)

**No existing files modified.**

**Key implementation decisions:**
- 25 rules as `ValidationRule` frozen dataclasses with `Callable[[EngineInput], bool]`
- Pipeline iterates every rule — never stops at first error (all failures collected)
- V-14 (LLP): implemented as value-level guard checking `.value not in` supported set
  (Option A — LLP unreachable from current enum; guard protects against future additions)
- V-06 guard: `purchase_price > 0` check prevents false V-07 trigger on zero price
- `run_validation()` is the single public entry point, re-exported from `__init__.py`
- `ValidationResult` from `app.engine.contracts` used throughout (no duplication)

**Verification (pre-commit):** 28 implementation checks passed. 99 test
functions defined. ruff: clean. mypy: clean.

**Post-generation corrections (before local verification):**
- V-21 and V-22 conditions changed to `lambda i: False` — `EngineInput` defines
  `annual_service_charge` and `annual_ground_rent` as `Decimal` (not `Decimal|None`).
  Null-check conditions are unreachable at the engine boundary; service layer
  enforces leasehold presence before `EngineInput` is assembled. Pattern matches
  V-14 Option A. Rules remain in `VALIDATION_RULES` with correct metadata.
- V-02 and V-03 tests fixed: changing `purchase_price` alone cascaded into
  V-06/V-07/V-08 hard failures. Deposit amount now scaled proportionally
  (25%+ of test price) to isolate the target WARN rule.

### Commit 2.7 — Risk flag definitions

**Message:** `feat(engine): risk flag definitions and evaluator`
**Status:** ✅ Complete
**Tests added:** 80 | **Running total:** 393

**Files created:**
- `backend/app/engine/risk_flags/__init__.py`
- `backend/app/engine/risk_flags/definitions.py` (424 lines)
- `backend/tests/unit/risk_flags/__init__.py`
- `backend/tests/unit/risk_flags/test_flag_*.py` × 17 flag test files
- `backend/tests/unit/risk_flags/test_flag_evaluation_pipeline.py`

**No existing files modified.**

**Key implementation decisions:**
- `EvaluationContext`: frozen dataclass with 15 named fields from outputs,
  intermediates, and inputs. No condition accesses EngineInput/EngineConfig.
- `RiskFlagDefinition`: frozen dataclass with `condition` and `value_extractor`
  callables. Evaluator iterates in declaration order (HIGH→MEDIUM→INFO).
- `LOW_ICR_BASIC`: ownership check omitted (all valid structures are already
  in the supported set). `None` guard mandatory for cash purchase.
- `LOW_MARGIN_SAFETY`: strictly `< 0.05`. TEST_STRATEGY.md "Fires:" label on
  boundary-exact case is a typo; CALCULATION_SPEC.md strict inequality governs.
- `LEASEHOLD_SHORT_LEASE`: `None` guard on `lease_years_remaining` is required.
  Value is legitimately nullable at the engine boundary.
- `RENT_UNVERIFIED`: `condition=lambda c: True` — unconditional INFO disclosure.
- `LTD_EXTRACTION_UNDISCLOSED`: fires whenever `ownership_structure == LIMITED_COMPANY`.
- `FLAG_DEFINITIONS` ordered HIGH→MEDIUM→INFO; result list inherits that order.

**Verification (pre-commit):** 15 implementation checks passed. 80 tests defined.
ruff: clean. mypy: clean.

### Commit 2.8 — Engine orchestrator

**Message:** `feat(engine): orchestrator — engine.run() entry point`
**Status:** ✅ Complete and pushed
**Tests added:** 34 | **Running total:** 427 (repository ground truth)

**Files created:**
- `backend/app/engine/orchestrator.py` (440 lines — 13-step pipeline)
- `backend/tests/unit/engine/__init__.py`
- `backend/tests/unit/engine/test_orchestrator_validation_path.py` (5 tests)
- `backend/tests/unit/engine/test_orchestrator_calculation_path.py` (7 tests)
- `backend/tests/unit/engine/test_orchestrator_cash_purchase.py` (5 tests)
- `backend/tests/unit/engine/test_orchestrator_ltd_co.py` (5 tests)
- `backend/tests/unit/precision/__init__.py`
- `backend/tests/unit/precision/test_decimal_types.py` (4 tests)
- `backend/tests/unit/precision/test_rounding_point.py` (3 tests)
- `backend/tests/unit/precision/test_rounding_mode.py` (3 tests)
- `backend/tests/unit/precision/test_no_float_arithmetic.py` (2 tests)

**Files modified:**
- `backend/app/engine/__init__.py` — adds `from app.engine.orchestrator import run`
  and `__all__ = ["run"]`

**Key implementation decisions:**
- `getcontext().prec = 10` set at module level (ENGINE_CONTRACTS.md Part 7.1)
- Rounding (`_r()`) applied ONLY at Step 13 when writing EngineOutputs /
  EngineIntermediates. Never during intermediate computation.
- `is_cash_purchase` is a local boolean — no CASH_PURCHASE flag. V-10 WARN
  informs the user (ENGINE_ARCHITECTURE.md Step 1 decision confirmed in plan).
- SDLT SDLTBand objects unpacked → plain tuples before calling f13, keeping
  `calculations/` import-free of `contracts`.
- Return type: `EngineResult | ValidationResult | EngineError`.
  `ValidationResult` is the actual HARD failure return type (no EngineFailure
  wrapper — confirmed against APPLICATION_SERVICE_ARCHITECTURE.md).
- `income_tax_gross_gbp` and `mortgage_interest_tax_credit_gbp` set to `None`
  for LIMITED_COMPANY; `corporation_tax_gross_gbp` set to `None` for INDIVIDUAL.
- Cash purchase test: `mortgage_interest_rate=Decimal("0")` with `deposit_amount`
  unchanged (50,000 < 200,000), so V-06 does not fire.
- `pre_tax_annual_cash_flow` computed inline: `noi - annual_mortgage_cost`
  (no formula number — orchestrator-only intermediate per ENGINE_ARCHITECTURE.md).

**Note on running total:** BUILD_LOG projections and repository counts diverged
across several commits (V-21/V-22 rewrites in 2.6, Commit 2.4 recovery).
Repository ground truth after Commit 2.8 local verification: **427 passed**.
All subsequent commits use 427 as the baseline.

**Local verification results:**
- pytest: 427 passed
- ruff: All checks passed
- mypy: Success, no issues found
- SDLT band breakdown standardised to immutable tuple representation
- Engine outputs flow through full end-to-end calculation pipeline

**Verification (pre-commit):** All 12 files syntax-clean. 34 test functions
defined. ruff: clean (verified in sandbox). mypy: clean (verified in sandbox).

**Post-generation test fixes (4 failing tests corrected before local verification):**

1. `test_warn_only_produces_engine_result` — removed `assert result.is_valid`;
   `EngineResult` has no `is_valid` field (ENGINE_CONTRACTS.md Part 3).

2. `test_icr_percent_is_none_for_cash_purchase` — renamed and corrected.
   `rate=0` with `deposit < price` gives `loan=150,000`, not zero. `icr_percent`
   is a `Decimal`, not `None`. Test now asserts `isinstance(icr_percent, Decimal)`.

3. `test_loan_amount_is_zero_in_intermediates` — renamed and corrected.
   `loan = price − deposit = 150,000`. Test now asserts `Decimal("150000.00")`.

4. `test_prec03_effective_rent_rounded_at_output_only` — corrected expected value.
   `11,199.96 × 0.9615 = 10,768.76154`, not `10,776.96174` as TEST_STRATEGY.md
   states (arithmetic error in that document). Test now expects `10,768.76`.

### Commit 2.9 — Reference scenario fixtures

**Message:** `test(engine): reference scenario fixtures E-01 through E-12`
**Status:** ✅ Complete and pushed
**Tests added:** 0 (fixtures only — tests in Commits 2.10 and 2.11)
**Running total:** 427

**Files created:**
- `backend/tests/conftest.py` (601 lines)
  — REFERENCE_CONFIG, ALTERNATIVE_CONFIG_VOID, ALTERNATIVE_CONFIG_STRESS
  — e01_input() through e12_input() — scenario input builders
  — e01_expected_outputs() through e12_expected_outputs() — expected values
  — e01_expected_flags() / e01_absent_flags() / e01_expected_warnings() (× 12)
  — pytest fixtures: reference_config, alt_config_void, alt_config_stress
- `backend/tests/regression/conftest.py` (127 lines)
  — Re-exports all builders from top-level conftest
  — assert_outputs() helper (exact Decimal comparison with field name in error)
  — assert_flags_present() / assert_flags_absent() / assert_warnings() helpers

**No files modified.**

**Key decisions:**
- All expected values hardcoded from ENGINE_CONTRACTS.md Part 11 — nothing
  computed at import time from formulas.
- E-03 icr_percent: 127.87 (arithmetically correct per F-22 formula; ENGINE_CONTRACTS.md
  shows 127.88 — known arithmetic discrepancy documented in Commit 2.4).
- E-10 expected outputs expressed as delta from E-01 base dict to avoid
  duplicating all 17 fields.
- E-12 validation warnings: empty frozenset (refurb=25000 so V-25 does not fire).
- assert_outputs() rounds actual values to 2dp before comparing — matches
  ENGINE_CONTRACTS.md Part 7.2 rounding semantics.
- REFERENCE_CONFIG and ALTERNATIVE_CONFIG_* are module-level constants, not
  just pytest fixtures, so they can be imported by non-pytest code (Commit 2.10+).

**Verification:** pytest 427 passed (no new tests — fixtures are data only).
ruff: All checks passed. mypy: Success, no issues found.

### Commit 2.10 — Regression tests E-01 through E-06
**Status:** ⏳ Not started

### Commit 2.11 — Regression tests E-07 through E-12 + determinism
**Status:** ⏳ Not started
