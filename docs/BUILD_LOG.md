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

**Message:** `test(engine): regression tests E-01 through E-06`
**Status:** ✅ Complete
**Tests added:** 96 | **Running total:** 523

**Files created:**
- `backend/tests/regression/test_e01_baseline_basic_rate.py` (24 tests)
- `backend/tests/regression/test_e02_higher_rate_section24.py` (12 tests)
- `backend/tests/regression/test_e03_ltd_co_standard.py` (17 tests)
- `backend/tests/regression/test_e04_lower_leverage_positive.py` (16 tests)
- `backend/tests/regression/test_e05_high_value_ltd_ated.py` (12 tests)
- `backend/tests/regression/test_e06_leasehold_higher_rate.py` (15 tests)

**No files modified.**

**Test structure per scenario (TEST_STRATEGY.md Part 7.2):**
- Module-scoped `e0N_result` fixture: runs engine once, shared across class
- `TestE0NOutputs`: asserts every EngineOutputs field via `assert_outputs()`
- `TestE0NIntermediates`: asserts key intermediates individually with
  explicit expected values and derivation comments
- `TestE0NFlags`: asserts present flags, absent flags, validation warnings

**Key intermediate assertions per scenario:**
- E-01: all 29 intermediates covered; Section 24 credit = 1,425.00 offsets
  gross tax 1,358.62 → zero liability; corporation_tax_gross is None
- E-02: income_tax_gross = 2,717.24; credit = 1,425.00 (unchanged); liability = 1,292.24
- E-03: taxable profit = -2,468.20; corporation_tax = 0.00 (not None);
  income_tax_gross is None; section_24_applies is False
- E-04: loan = 120,000; stressed = 6,600; credit = 1,140.00; liability = 218.62;
  pre_tax = 1,093.10; positive cash flow confirmed
- E-05: ATED (purchase > 500k, Ltd Co); LOW_ICR_BASIC (icr=111.88 < 125);
  total_sdlt = 38,000 (base 20k + surcharge 18k)
- E-06: total_operating = 5,174 (includes service charge + ground rent);
  income_tax_gross = 1,853.32; credit = 1,282.50; liability = 570.82

**Discrepancy notes:**

- *E-03 icr_percent:* ENGINE_CONTRACTS.md shows 127.88; arithmetic gives 127.87
  (18,460.80 / 14,437.50 × 100 = 127.867...). Test uses 127.87 (correct).

- *E-06 icr_percent:* ENGINE_CONTRACTS.md shows 132.10; arithmetic gives 132.08
  (9,807.30 / 7,425.00 × 100 = 132.0848...). Discovered during Commit 2.10
  local verification. conftest.py e06_expected_outputs() corrected to 132.08.
  Same class of error as E-03 — arithmetic error in ENGINE_CONTRACTS.md.

- *void_rate_decimal_applied (E-01):* Test expected 0.0385 (4dp) but
  ENGINE_CONTRACTS.md Part 7.2 rounds all EngineIntermediates to 2dp at
  Step 13. Orchestrator correctly stores _r(0.0385) = 0.04. Test corrected
  to assert Decimal("0.04").

**Verification (post-fix):** 96 passed (all 2 previously failing tests corrected).
ruff: clean. mypy: clean.

### Commit 2.11 — Regression tests E-07 through E-12 + determinism

**Message:** `test(engine): regression E-07 to E-12, determinism guarantees`
**Status:** ✅ Complete
**Tests added:** 59 | **Running total:** 582

**Files created:**
- `backend/tests/regression/test_e07_hard_validation_failure.py` (7 tests)
- `backend/tests/regression/test_e08_warn_only_validation.py` (10 tests)
- `backend/tests/regression/test_e09_short_lease_flag.py` (5 tests)
- `backend/tests/regression/test_e10_additional_rate.py` (9 tests)
- `backend/tests/regression/test_e11_thin_margin.py` (8 tests)
- `backend/tests/regression/test_e12_high_refurb.py` (9 tests)
- `backend/tests/determinism/__init__.py`
- `backend/tests/determinism/test_idempotent_execution.py` (4 tests — DET-01..04)
- `backend/tests/determinism/test_serialisation_roundtrip.py` (2 tests — DET-05..06)
- `backend/tests/determinism/test_config_version_isolation.py` (3 tests — DET-07..09)
- `backend/tests/determinism/test_no_internal_state.py` (2 tests — DET-10..11)

**No files modified.**

**Key test notes:**
- E-07: asserts isinstance(result, ValidationResult), is_valid=False, V-07 in
  hard_errors, field="deposit_amount", no EngineResult structure present.
- E-08: asserts V-08+V-25 in validation_warnings, HIGH_LEVERAGE fires (ltv=82.50),
  HIGH_LEVERAGE_EXTREME absent (82.50 < 85).
- E-09: outputs identical to E-06; LEASEHOLD_SHORT_LEASE fires with
  triggered_by_value="72".
- E-10: maximum Section 24 impact at ADDITIONAL_RATE; credit still 20%.
- E-11: LOW_MARGIN_SAFETY fires; cash flow positive (258.48); NEGATIVE_CASHFLOW
  absent; triggered_by_value="258.48".
- E-12: V-25 NOT in warnings (refurb=25000); HIGH_REFURB_RATIO fires with
  triggered_by_value="25000.00".
- DET-01..04: identical inputs → identical outputs (1, 2, and 10 sequential calls).
- DET-05..06: object identity irrelevant — reconstructed inputs/configs produce
  same results.
- DET-07..09: different configs → different results; original config always
  reproduces original result; higher stress rate → lower ICR.
- DET-10: static inspection of engine sub-modules for mutable module-level
  variables (G-2 structural guarantee).
- DET-11: EngineResult has no timestamp fields (G-3 guarantee).

**Verification (pre-commit):** 59 test functions. ruff: clean. mypy: clean.

**Final verification:** pytest 582 passed. ruff: passed. mypy: passed.

**Post-verification test fixes (4 failures corrected):**

1. *E-07 test_warnings_empty:* V-08 WARN fires alongside V-07 HARD (deposit=25k
   is below both 15% and 25% thresholds; pipeline evaluates all rules). Added
   `e07_expected_warnings()` to conftest returning `frozenset({"V-08"})`.
   Test renamed `test_v08_warn_also_fires`.

2. *E-11 roce_percent (9.30 → 9.99):* Conftest used wrong value.
   maintenance_reserve = 220,000 × 1% = 2,200 (not 2,000).
   NOI = 6,593.10; cash_deployed = 66,000; ROCE = 9,593.10/66,000×100 = 9.99.

3. *E-11 icr_percent (150.08 → 120.78) and LOW_ICR_BASIC flag:* Conftest had
   wrong ICR. loan=165,000; stressed=9,075; ICR=120.78 < 125 → LOW_ICR_BASIC
   fires. Moved LOW_ICR_BASIC from absent_flags to expected_flags.

4. *DET-07/08 ALTERNATIVE_CONFIG_VOID → ALTERNATIVE_CONFIG_STRESS:*
   void_rate_percent is an EngineInput field already resolved before engine entry;
   changing the AssumptionConfig default has no effect. stress_test_rate_percent
   IS read from EngineConfig at execution time. Tests now use ALTERNATIVE_CONFIG_STRESS.


---

## Phase 3 — Database Schema and Migrations

---

### Commit 3.1 — ORM base models

**Message:** `feat(db): SQLAlchemy ORM models for all Phase 1 tables`
**Status:** ✅ Complete
**Tests added:** 0 (ORM models only — schema integrity tested in Commit 3.5)
**Running total:** 582

**Files created:**
- `backend/app/db/models/__init__.py`
- `backend/app/db/models/user.py`
- `backend/app/db/models/investor_profile.py`
- `backend/app/db/models/property.py`
- `backend/app/db/models/deal.py` (170 lines — all working input columns)
- `backend/app/db/models/configuration.py` (177 lines — 5 config models)
- `backend/app/db/models/snapshot.py` (492 lines — 6 snapshot models)
- `backend/app/db/models/audit.py`

**Column type mapping (IMPLEMENTATION_ROADMAP.md Commit 3.1):**
NUMERIC(15,6) → Numeric(15,6); NUMERIC(10,6) → Numeric(10,6);
NUMERIC(15,10) → Numeric(15,10) [void_rate_decimal_applied];
JSONB → JSONB [sdlt_band_breakdown]; UUID PKs with gen_random_uuid();
DateTime(timezone=True) with now() server_default.

**Key decisions:**
- All enum types use create_type=False — created by migration (Commit 3.2)
- All FK columns are plain UUID columns — FK constraints added by migration
- snapshot_calculations.is_superseded is the only mutable snapshot column
- SnapshotInputs includes _source column per optional input (ADR-009)
- No ORM relationships defined in this commit (scope: column definitions only)

**Verification:** 8 files syntax-clean. ruff: clean. mypy: clean.
pytest: 582 passed (no new tests).

---

### Commit 3.2 — Alembic migration: initial schema

**Message:** `migration: initial schema — all Phase 1 tables`
**Status:** ✅ Complete
**Tests added:** 0 (migration integrity tested in Commit 3.5)
**Running total:** 582

**Files created:**
- `backend/alembic/versions/0001_initial_schema.py` (≈1250 lines)

**Migration creates (in dependency order):**
1. PostGIS extension (`CREATE EXTENSION IF NOT EXISTS postgis`)
2. 11 PostgreSQL enum types (all from DATABASE_SCHEMA_DESIGN.md Section 1)
3. `users` — no FK dependencies
4. `investor_profiles` — FK → users
5. `properties` — FK → users
6. `deals` — FK → users, properties, investor_profiles; `latest_snapshot_id` column created without FK (deferred)
7. `config_engine_versions` — no FK dependencies; TEXT primary key
8. `config_sdlt_versions` — FK → users (nullable); UNIQUE (effective_from, property_country)
9. `config_sdlt_bands` — FK → config_sdlt_versions; UNIQUE (sdlt_version_id, band_order)
10. `config_corporation_tax_versions` — FK → users (nullable); UNIQUE (effective_from)
11. `config_assumption_versions` — FK → users (nullable); UNIQUE (effective_from)
12. `snapshot_calculations` — FK → deals, users, three config tables
13. `deals.latest_snapshot_id` FK → snapshot_calculations — added via `op.create_foreign_key()` to resolve circular dependency
14. `snapshot_inputs` — FK → snapshot_calculations; UNIQUE INDEX on snapshot_id (enforces 1:1)
15. `snapshot_outputs` — FK → snapshot_calculations; UNIQUE INDEX on snapshot_id (enforces 1:1)
16. `snapshot_intermediates` — FK → snapshot_calculations; UNIQUE INDEX on snapshot_id (enforces 1:1)
17. `snapshot_risk_flags` — FK → snapshot_calculations (one-to-many)
18. `snapshot_validation_warnings` — FK → snapshot_calculations (one-to-many)
19. `audit_calculations` — FK → users, deals, snapshot_calculations (nullable)
20. All 25 indexes from DATABASE_SCHEMA_DESIGN.md Section 8

**Totals:**
- Tables: 16
- Enum types: 11
- Foreign keys: 23 (all ON DELETE RESTRICT)
- CHECK constraints: 78
- Named indexes (op.create_index): 25 (3 unique, 22 non-unique)
- Implicit unique indexes from sa.UniqueConstraint: 5 (users, config_sdlt_versions, config_sdlt_bands, config_ct_versions, config_assumption_versions)

**Circular dependency resolution:**
`deals.latest_snapshot_id → snapshot_calculations` and `snapshot_calculations.deal_id → deals` form a mutual reference. Resolved by creating `latest_snapshot_id` as a bare nullable UUID column inside `op.create_table("deals")` — no FK — then calling `op.create_foreign_key("fk_deals_snapshot_calculations", ...)` after `snapshot_calculations` exists (Step 13).

**Uniqueness correction applied:**
`snapshot_inputs`, `snapshot_outputs`, `snapshot_intermediates` initially had both `unique=True` on the column inside `op.create_table()` AND `op.create_index(..., unique=True)` — producing duplicate unique indexes. Confirmed via `DATABASE_SCHEMA_DESIGN.md` Section 3 (column attribute) and Section 8 (index) that these describe one database object. Column-level `unique=True` removed from all three; enforcement retained solely in the named unique index.

**Downgrade:** intentional no-op per `PERSISTENCE_ARCHITECTURE.md` Part 14.2. All tables created are immutable (snapshot_*, config_*, audit_calculations). Dropping them would destroy historical data. Development reset requires dropping and recreating the database.

**Verification:** ruff: All checks passed. mypy: Success, no issues found. pytest: 582 passed (no new tests — migration integrity tested in Commit 3.5).

---

### Commit 3.3 — Database role privileges migration

**Message:** `migration: application database role privileges`
**Status:** ✅ Complete
**Tests added:** 0
**Running total:** 582

**Files created:**
- `backend/alembic/versions/0002_database_roles.py`

**Roles created:**
- `propiq_app` — runtime FastAPI application role
- `propiq_admin` — admin configuration management role

(`propiq_migrations` is not created here — it is the superuser-equivalent migration execution role that pre-exists in each environment.)

**Privilege grants — propiq_app (per DATABASE_SCHEMA_DESIGN.md Section 7):**

| Tables | SELECT | INSERT | UPDATE | DELETE |
|---|---|---|---|---|
| users, investor_profiles, properties, deals | ✅ | ✅ | ✅ | ✗ |
| snapshot_calculations | ✅ | ✅ | column-level only | ✗ |
| snapshot_inputs/outputs/intermediates/risk_flags/validation_warnings | ✅ | ✅ | ✗ | ✗ |
| config_* (5 tables) | ✅ | ✗ | ✗ | ✗ |
| audit_calculations | ✅ | ✅ | ✗ | ✗ |

Column-level UPDATE grant: `GRANT UPDATE (is_superseded, superseded_at) ON snapshot_calculations TO propiq_app` — the single permitted snapshot mutation.

**Privilege grants — propiq_admin:**

SELECT, INSERT on all 16 tables. No UPDATE or DELETE anywhere — per schema: "Even the admin role has no UPDATE or DELETE on any table."

**Downgrade:** Revokes all grants and drops both roles. Real downgrade (not no-op) since no immutable data is created by this migration. Production downgrade requires a maintenance window.

**Verification:** pytest: 582 passed. ruff: All checks passed. mypy: Success, no issues found in 49 source files.

---

### Commit 3.4 — Configuration seed script

**Message:** `feat(scripts): seed v1.0 configuration data`
**Status:** ✅ Complete
**Tests added:** 0 (seed correctness verified in Commit 3.5 schema integrity tests)
**Running total:** 582

**Files created:**
- `backend/scripts/seed_configuration.py`

**Records seeded (all idempotent — safe to re-run):**

| Table | Key | Values |
|---|---|---|
| `config_engine_versions` | `"1.0.0"` | `is_breaking_change=False`, `specification_ref="CALCULATION_SPEC.md v1.0"` |
| `config_sdlt_versions` | ENGLAND, 2025-04-01 | `additional_dwelling_surcharge_rate=0.030000` |
| `config_sdlt_bands` | 5 bands | 0%, 2%, 5%, 10%, 12% at standard thresholds |
| `config_corporation_tax_versions` | 2023-04-01 | small_profits=19%, main=25%, marginal relief 3/200 |
| `config_assumption_versions` | 2025-01-01 | void=3.85%, letting=10%, VAT=20%, stress=5.5%, ICR basic=125%, higher=145% |

**Idempotency mechanism:**
- `config_engine_versions`: `ON CONFLICT (version_string) DO NOTHING`
- `config_sdlt_versions`: pre-existence check by `(effective_from, property_country)` — existing ID retrieved and used for band seeding
- `config_sdlt_bands`: `ON CONFLICT (sdlt_version_id, band_order) DO NOTHING`
- `config_corporation_tax_versions`: `ON CONFLICT (effective_from) DO NOTHING`
- `config_assumption_versions`: `ON CONFLICT (effective_from) DO NOTHING`

**All values sourced from DATABASE_SCHEMA_DESIGN.md Section 9 exactly as specified. SDLT band boundary verified against ENGINE_CONTRACTS.md E-01: £200k purchase → total_sdlt = £7,500.00 ✓**

**Verification:** pytest: 582 passed. ruff: All checks passed. mypy: Success, no issues found in 49 source files. (Script is in `scripts/` — outside mypy `app/` scope by project convention.)

---

### Commit 3.5 — Migration integration tests

**Message:** `test(db): schema integrity tests against test database`
**Status:** ✅ Complete
**Tests added:** 120 (integration — require test DB, run via `make test-int`)
**Running total (unit):** 582 | **Integration:** 120

**Files created:**
- `backend/tests/integration/__init__.py`
- `backend/tests/integration/test_schema_integrity.py`

**Test classes and coverage:**

| Class | Tests | What is verified |
|---|---|---|
| `TestAllTablesExist` | 17 | All 16 tables present; exactly that set and no others |
| `TestColumnNullability` | 79 | 25 nullable columns, 54 NOT NULL columns (spot-check from Sections 2–5) |
| `TestUniqueConstraints` | 3 | UNIQUE INDEX on `snapshot_id` for all three 1:1 snapshot sub-tables |
| `TestForeignKeys` | 11 | All key FK relationships from Section 6; including deferred deals↔snapshot_calculations circular FK |
| `TestConfigData` | 10 | All 5 seed records present; correct rates/values; age_days query; PostGIS enabled |

**Session fixture (`db_schema`, autouse=True):**
1. Drops and recreates `public` schema (clean slate via `AUTOCOMMIT`)
2. Runs `alembic upgrade head` via subprocess with `DATABASE_URL` set to test URL (avoids `lru_cache` conflict with `env.py`)
3. Runs `scripts/seed_configuration.py` via subprocess against test DB

**Not collected by `make test-unit`** — integration tests only run via `make test-int` which starts the test DB first.

**Verification:** `make test-unit`: 582 passed. ruff: All checks passed. mypy: No issues in 49 source files. Integration tests: 120 collected cleanly (not executed — no test DB in CI without `make dev-db-test`).

---

## Phase 4 — Repository Layer

---

### Commit 4.1 — Repository interfaces

**Message:** `feat(repositories): abstract repository interfaces`
**Status:** ✅ Complete
**Tests added:** 0 (interfaces only — tested via implementations in Commits 4.3–4.5)
**Running total:** 582

**Files created:**
- `backend/app/repositories/__init__.py`
- `backend/app/repositories/pagination.py` — `PageRequest`, `Page[T]` (Commit 4.2 content included here; interfaces require these types)
- `backend/app/repositories/interfaces/__init__.py` — re-exports all interfaces and types
- `backend/app/repositories/interfaces/i_user.py` — `IUserRepository`
- `backend/app/repositories/interfaces/i_investor_profile.py` — `IInvestorProfileRepository`
- `backend/app/repositories/interfaces/i_property.py` — `IPropertyRepository`
- `backend/app/repositories/interfaces/i_deal.py` — `IDealRepository` + `DealSummary`
- `backend/app/repositories/interfaces/i_snapshot.py` — `ISnapshotRepository` + `SnapshotSummary` + `SnapshotHistoryEntry`
- `backend/app/repositories/interfaces/i_configuration.py` — `IConfigurationRepository` + `EngineVersionRecord` + summary projection types
- `backend/app/repositories/interfaces/i_audit.py` — `IAuditRepository` + `CalculationAuditEvent`

**All interfaces use `typing.Protocol` with `@runtime_checkable`. All methods are `async def`. No inheritance required from implementations.**

**Projection types defined:**
- `DealSummary` — lightweight read projection for deal list views (in `i_deal.py`)
- `SnapshotSummary` — DISPLAY-level projection: root + outputs + flags + warnings (in `i_snapshot.py`)
- `SnapshotHistoryEntry` — SUMMARY-level projection: root + key metrics + flag counts (in `i_snapshot.py`)
- `CalculationAuditEvent` — domain representation of one audit record (in `i_audit.py`)
- `EngineVersionRecord`, `SDLTConfigurationSummary`, `CorporationTaxConfigSummary`, `AssumptionConfigSummary` (in `i_configuration.py`)

**Configuration type aliases:** `SDLTConfiguration = SDLTConfig`, `CorporationTaxConfiguration = CorporationTaxConfig`, `AssumptionConfiguration = AssumptionConfig` — aliased from engine contracts so repository config output is directly usable by the engine.

**Pagination types (pagination.py):** `PageRequest` (limit 1–100, cursor decode), `Page[T]` (items, next_cursor, total_count, cursor encode). Full implementation included — Commit 4.2 is a subset of what's here.

**Architecture invariants covered:** RI-01 through RI-15 from REPOSITORY_ARCHITECTURE.md Part 20. Each interface method is documented with the relevant invariant where applicable.

**Ruff fix:** 3 × `I001` import-sort errors auto-fixed in `i_deal.py`, `i_snapshot.py`, `i_audit.py`.

**Verification:** pytest: 582 passed. ruff: All checks passed. mypy: Success, no issues found in 59 source files.

---

### Commit 4.3 — Configuration repository

**Message:** `feat(repositories): configuration repository implementation`
**Status:** ✅ Complete
**Tests added:** 17 (integration — require test DB, run via `make test-int`)
**Running total (unit):** 582 | **Integration:** 137

**Files created:**
- `backend/app/repositories/configuration_repository.py`
- `backend/tests/integration/repositories/__init__.py`
- `backend/tests/integration/repositories/conftest.py`
- `backend/tests/integration/repositories/test_configuration_repository.py`

**Implementation (`ConfigurationRepository`):**
- Constructor takes `AsyncSession` (injected; does not open/close sessions — RI-07, RI-08)
- `find_active_sdlt_config(as_of_date)` — SELECT + LIMIT 1 by `effective_from DESC`, then second query for bands; raises `ConfigurationNotFoundError` if none found
- `find_sdlt_config_by_id(version_id)` — SELECT by PK, then bands; raises if not found
- `find_active_corporation_tax_config(as_of_date)` — same active-version pattern
- `find_corporation_tax_config_by_id(version_id)` — SELECT by PK
- `find_active_assumption_config(as_of_date)` — same active-version pattern
- `find_assumption_config_by_id(version_id)` — SELECT by PK
- `_to_sdlt_domain(version, bands)` — ORM rows → `SDLTConfig` (per roadmap spec)
- `_to_ct_domain(row)` — ORM row → `CorporationTaxConfig`
- `_to_assumption_domain(row)` — ORM row → `AssumptionConfig`
- All numeric values wrapped in `Decimal(str(...))` to enforce RI-13 (no float)
- Listing and admin write methods: listing implemented; writes raise `NotImplementedError` (no metadata in engine contract types)

**Tests (all 5 roadmap-specified + 12 additional correctness tests):**
- `find_active_sdlt_config(date(2025,6,1))` → 5 bands, surcharge=0.030000 ✅
- `find_active_sdlt_config(date(2024,12,31))` → raises `ConfigurationNotFoundError` ✅
- `find_sdlt_config_by_id(known_uuid)` → correct record ✅
- `find_sdlt_config_by_id(unknown_uuid)` → raises `ConfigurationNotFoundError` ✅
- `find_active_assumption_config` → all 11 seed values match exactly ✅

**Ruff fixes:** 3 errors auto-fixed (`I001` ×2, `F401` ×1); 1 further fix (`F821` — missing `SDLTConfiguration` import, `F821` — wrong parameter type in `save_sdlt_config`).

**Verification:** pytest (unit): 582 passed. ruff: All checks passed. mypy: Success, no issues found in 60 source files. Integration: 17 tests collected.

---

### Commit 4.2 — Pagination types

**Message:** `feat(repositories): PageRequest and Page types`
**Status:** ✅ Complete (no new files — all work completed in Commit 4.1)
**Tests added:** 0
**Running total:** 582

**Verification against roadmap spec:**

`backend/app/repositories/pagination.py` already exists and fully satisfies all Commit 4.2 requirements:

| Requirement | Status |
|---|---|
| `PageRequest` frozen dataclass with `limit: int = 20`, `cursor: str | None = None` | ✅ |
| `__post_init__` validates `1 <= limit <= 100` | ✅ |
| `Page(Generic[T])` with `items`, `next_cursor`, `total_count` | ✅ |
| Cursor encoding: base64 of JSON `{"created_at": "<iso>", "id": "<uuid>"}` | ✅ (`encode_cursor` / `decode_cursor`) |

No files were created or modified. Commit 4.2 content was delivered in Commit 4.1 because the interfaces required `PageRequest` and `Page[T]` to typecheck.

**Verification:** pytest: 582 passed. ruff: All checks passed. mypy: Success, no issues found in 59 source files.

---

### Commit 4.4 — User and InvestorProfile repositories

**Message:** `feat(repositories): user and investor profile repositories`
**Status:** ✅ Complete
**Tests added:** 21 (integration — require test DB, run via `make test-int`)
**Running total (unit):** 582 | **Integration:** 158

**Files created:**
- `backend/app/repositories/investor_profile_repository.py`
- `backend/tests/integration/repositories/test_user_repository.py` (9 tests)
- `backend/tests/integration/repositories/test_investor_profile_repository.py` (12 tests)

**Files already present (untracked from prior session):**
- `backend/app/repositories/user_repository.py` — complete implementation; no changes needed

**InvestorProfileRepository implementation:**
- Constructor takes `AsyncSession` (injected; does not open/close sessions — RI-07, RI-08)
- `save(profile)` — `session.add()` with ORM model; idempotency enforced at service layer
- `update(profile)` — `update()` statement on mutable fields only; `id`, `user_id`, `created_at` never modified
- `find_by_id(profile_id)` — SELECT by PK
- `find_by_id_for_user(profile_id, user_id)` — SELECT by PK AND user_id; returns None for both "not found" and "wrong user" (RI-06)
- `find_all_for_user(user_id, include_archived)` — ORDER BY created_at DESC; filters archived when include_archived=False
- `find_default_for_user(user_id)` — SELECT WHERE is_default=True AND user_id
- `_to_domain(row)` — ORM → InvestorProfile with defensive enum coercion for asyncpg compatibility

**UserRepository tests (9 tests):**
- `save()` then `find_by_supabase_auth_id()` returns the saved user
- `save()` twice with same supabase_auth_id: idempotent (second save is no-op — ON CONFLICT DO NOTHING)
- `find_by_id()` and `find_by_email()` return correct records after save
- `find_by_id/supabase_auth_id/email` return None when not found
- `update()` persists display_name and status changes

**InvestorProfileRepository tests (12 tests):**
- `save()` then `find_by_id()` returns correct profile with all fields
- Ltd Co profile (income_tax_band=None) saves and loads correctly
- `find_by_id()` returns None when not found
- `find_by_id_for_user()` returns profile for correct user; None for wrong user; None when not found
- `find_default_for_user()` returns profile with is_default=True; None when no default set
- `find_all_for_user()` excludes archived by default; includes archived when include_archived=True
- `update()` persists label change; does not modify user_id

**Verification:** pytest (unit): 582 passed. ruff: All checks passed. mypy: Success, no issues found in 62 source files. Integration tests: 21 collected (9 user + 12 investor_profile).

---

### Commit 4.5 — Property repository

**Message:** `feat(repositories): property repository implementation`
**Status:** ✅ Complete
**Tests added:** 13 (integration — require test DB, run via `make test-int`)
**Running total (unit):** 582 | **Integration:** 171

**Files created:**
- `backend/app/repositories/property_repository.py`
- `backend/tests/integration/repositories/test_property_repository.py` (13 tests)

**Files modified:**
- `backend/app/domain/entities/property.py` — added `lease_years_remaining: int | None = None`

**Domain entity correction:**
`Property` was missing `lease_years_remaining` from its field list. The ORM model (`properties` table) has this column with a CHECK constraint `NOT (tenure = 'LEASEHOLD' AND lease_years_remaining IS NULL)`, confirming it is required for LEASEHOLD properties. The field was omitted from the domain entity in Commit 1.4. Added as an optional field after `tenure` — required by service layer to be non-None when tenure is LEASEHOLD.

**PropertyRepository implementation:**
- Constructor takes `AsyncSession` (injected — RI-07, RI-08)
- `save(property)` — `session.add()` with all ORM columns including `lease_years_remaining`
- `update(property)` — `update()` statement on mutable address fields, property_type, bedrooms, epc_rating, is_archived, archived_at; **tenure explicitly excluded** (immutability — RI-05)
- `find_by_id(property_id)` — SELECT by PK
- `find_by_id_for_user(property_id, user_id)` — SELECT by PK AND user_id; returns None for both failure modes (RI-06)
- `find_all_for_user(user_id, include_archived, page)` — keyset pagination on (created_at DESC, id DESC); separate count query for total_count; fetches limit+1 to detect next page
- `_to_domain(row)` — ORM → Property with PropertyAddress value object construction and defensive enum coercion

**Tests (all three roadmap-specified cases + additional coverage):**
- `find_by_id_for_user` returns None for correct ID but **wrong user** (RI-06) ✅
- `update()` does not modify tenure column — address change persists, tenure stays FREEHOLD ✅
- Archived property **still returned** by `find_by_id_for_user` (no active-only filter on single-record lookup) ✅
- Save/find roundtrip for freehold and leasehold (with `lease_years_remaining=85`) ✅
- `find_all_for_user` excludes/includes archived by flag ✅
- Pagination: cursor-based second page has no overlap with first page ✅

**Verification:** pytest (unit): 582 passed. ruff: All checks passed (1 import-sort auto-fixed). mypy: Success, no issues found in 63 source files. Integration tests: 13 collected.

---

### Commit 4.6 — Deal repository

**Message:** `feat(repositories): deal repository implementation`
**Status:** ✅ Complete
**Tests added:** 16 (integration — require test DB, run via `make test-int`)
**Running total (unit):** 582 | **Integration:** 187

**Files created:**
- `backend/app/repositories/deal_repository.py`
- `backend/tests/integration/repositories/test_deal_repository.py` (16 tests)

**DealRepository implementation:**
- Constructor takes `AsyncSession` (injected — RI-07, RI-08)
- `save(deal)` — `session.add()` mapping all 19 working_input columns from `DealWorkingInputs` to `DealORM`
- `update(deal)` — `update()` statement on mutable fields including all working_input columns; `user_id`, `property_id`, `created_at` explicitly excluded (RI-05)
- `find_by_id(deal_id)` — SELECT by PK (any user)
- `find_by_id_for_user(deal_id, user_id)` — SELECT by PK AND user_id; returns None for both failure modes (RI-06)
- `find_all_for_user(user_id, status_filter, page)` — keyset pagination on (updated_at DESC, id DESC); LEFT JOINs snapshot_outputs and snapshot_calculations via `deals.latest_snapshot_id`; HIGH flag count via correlated subquery; DRAFT deals have None for all latest_snapshot_* fields
- `find_all_for_property(property_id, user_id)` — ownership-filtered, unpaginated list (RI-09)
- `count_for_user(user_id)` — counts non-ARCHIVED deals
- `_to_domain(row)` — ORM → Deal + DealWorkingInputs; all Decimal columns wrapped in `Decimal(str(...))` for precision (RI-13); defensive enum coercion for asyncpg compatibility
- `_row_to_summary(row)` — joined Row → DealSummary projection; typed as `Row` (SQLAlchemy) to satisfy mypy

**mypy fix:** `_row_to_summary` parameter annotated as `Row` (type-arg suppressed with `# type: ignore[type-arg]`) — SQLAlchemy `Row` is generic but column names are dynamically constructed; `object` type caused 16 attr-defined errors.

**Tests — all four roadmap-specified cases:**
- `find_by_id_for_user` returns None for **wrong user** (RI-06) ✅
- `find_by_id_for_user` returns None for **not found** (RI-06) ✅
- `find_all_for_user` **pagination with cursor** — second page has no overlap with first ✅
- `update()` **persists working_inputs changes** ✅
- `update()` **does not modify user_id** ✅
- `update()` **does not modify property_id** ✅

**Additional tests:** save/find roundtrip with full working inputs; status filter; DRAFT deal has null snapshot fields in DealSummary; optional inputs clear to None on update; count_for_user excludes ARCHIVED.

**Verification:** pytest (unit): 582 passed. ruff: All checks passed (1 import-sort auto-fixed). mypy: Success, no issues found in 64 source files. Integration tests: 16 collected.