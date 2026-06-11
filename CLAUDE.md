# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

---

## Commands

All commands are run from the repo root via `make` unless noted.

### Backend

```bash
make dev              # Start postgres + FastAPI together (foreground)
make dev-db           # Start postgres + pgAdmin in background only
make dev-backend      # Start FastAPI only (DB must already be running)
make test             # Full suite — unit + integration (starts test DB)
make test-unit        # Unit tests only — no database, no Docker required (~10s)
make test-int         # Integration + API tests — requires test DB
make lint             # ruff check (read-only)
make lint-fix         # ruff check --fix
make typecheck        # mypy strict
make format           # ruff format
make migrate          # alembic upgrade head
make seed             # Insert v1.0 config seed data (idempotent)
```

Run a single test file:
```bash
cd backend && poetry run pytest tests/unit/formulas/test_f01_gross_annual_rent.py -v
```

Run a single regression scenario:
```bash
cd backend && poetry run pytest tests/regression/test_e01_baseline_basic_rate.py -v
```

### Frontend

```bash
make dev-frontend          # Next.js dev server (localhost:3000)
cd frontend && npm run typecheck   # tsc --noEmit
cd frontend && npm run lint        # next lint (ESLint)
cd frontend && npm run build       # production build
```

---

## Architecture

### Repository layout

```
backend/    FastAPI + engine + services + repositories
frontend/   Next.js 15 app
docs/       Architecture documents (frozen at architecture-v1)
infrastructure/  railway.toml, docker/
Makefile    All dev commands
```

### Backend layers (strict — no layer skips)

```
API routes (app/api/v1/routes/)
    ↓ calls
Services (app/services/)
    ↓ calls
Repositories (app/repositories/)  +  Engine (app/engine/)
    ↓ calls
ORM models (app/models/)  ←→  PostgreSQL
```

**Engine is pure.** `app/engine/` has zero I/O dependencies. It takes `EngineInput + EngineConfig` dataclasses and returns `EngineResult | ValidationResult | EngineError`. The engine never touches the database, config files, or settings. `CalculationService` assembles inputs, calls the engine, and persists the snapshot.

**Services are the only callers of repositories.** Routes call services only — never repositories directly.

**Configuration is versioned in the database.** SDLT bands, corporation tax rates, and assumption defaults are rows in `config_*` tables, not constants in code. `ConfigurationService.resolve_defaults()` fetches the active version for a given calculation date.

### Engine internals

`app/engine/orchestrator.py` is the single public entry point. It runs a 13-step pipeline: validate → acquisition costs → financing → effective rent → operating costs → NOI → tax → cash flow → yields → stress test → risk flags → persist intermediates → return result.

Sub-modules (`calculations/`, `validation/`, `tax/`, `risk_flags/`) do not import each other. Only the orchestrator imports from all sub-modules.

Rounding rule: full `Decimal` precision throughout the pipeline. Round to 2dp `ROUND_HALF_UP` **only** when writing into `EngineOutputs` / `EngineIntermediates` at Step 13. Never earlier.

### Test layers

| Layer | Location | Needs DB |
|---|---|---|
| Unit (formulas, validation, risk flags, tax) | `tests/unit/` | No |
| Regression (E-01 – E-12 reference scenarios) | `tests/regression/` | No |
| Determinism | `tests/determinism/` | No |
| Integration (repositories, snapshots) | `tests/integration/` | Yes |
| API (routes end-to-end) | `tests/api/` | Yes |

The 12 E-XX regression scenarios in `tests/regression/` are the canonical correctness tests. Expected values are hardcoded from `ENGINE_CONTRACTS.md Part 11` — never recomputed. E-01 baseline: `-£27.66/month` cash flow.

Shared fixtures (all scenario inputs + `REFERENCE_CONFIG`) live in `backend/tests/conftest.py`. Integration test DB session fixture lives in `backend/tests/integration/repositories/conftest.py`.

### Frontend architecture

**No calculation logic in the frontend.** Components render values from API responses only. No derived metrics, no formula functions.

**API client pattern.** All HTTP calls go through `frontend/lib/api/*.ts`. No component calls `fetch` directly. Every API call attaches the Supabase JWT via `frontend/lib/api/client.ts`.

**Auth guard.** `frontend/app/(app)/layout.tsx` is a Server Component that checks the Supabase session. Unauthenticated requests are redirected to `/login` before any page renders.

**Snapshot-first rendering.** The analysis page (`/deals/[dealId]/analysis`) always loads from `GET /api/v1/snapshots/{id}/full` (not the summary endpoint). The full endpoint is required for `sdlt_band_breakdown` (in `SnapshotIntermediates`) which the summary endpoint omits.

**Loading strategy for the analysis page:** `GET /api/v1/deals/{dealId}` → `deal.latest_snapshot_id` → `GET /api/v1/snapshots/{id}/full`. The snapshot ID is not in the URL.

**`NEXT_PUBLIC_*` env vars are baked at build time.** Changing them requires a rebuild. Local values live in `frontend/.env.local` (gitignored). See `frontend/.env.example` for required variables.

Required variables (all three must be set before the Railway build runs):

| Variable | Purpose | Example |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | Backend base URL — prefixed to every `/api/v1/…` call | `https://propiq-backend.up.railway.app` |
| `NEXT_PUBLIC_SUPABASE_URL` | Supabase project URL | `https://<ref>.supabase.co` |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Supabase public anon key | `eyJ…` |

Missing `NEXT_PUBLIC_API_URL` causes all API calls to resolve to `/undefined/api/v1/…`.

### Key domain types

`CalculationSnapshot` is the central aggregate. It is append-only — once written, no field is ever updated. `deal.latest_snapshot_id` is a nullable FK updated by `CalculationService` on each successful calculation.

`DealWorkingInputs` on the `Deal` entity stores the user's current form state. These are the mutable inputs; the snapshot is the immutable output.

All monetary values in API responses are serialised as strings (`MoneyStr = str`) to avoid JSON float precision loss. The frontend reads them as strings throughout.

### Docs

Architecture is frozen at `architecture-v1`. The 20+ docs in `docs/` are the authority — do not introduce new bounded contexts, entities, or persistence models without an ADR in `docs/decisions/`. `IMPLEMENTATION_ROADMAP.md` defines the commit sequence; implementation follows it commit-by-commit. `docs/BUILD_LOG.md` is updated after each phase is verified and pushed.
