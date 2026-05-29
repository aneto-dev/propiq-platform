# PropIQ Platform — Implementation Roadmap

## Purpose

This document is the execution plan for building the PropIQ platform.
It translates every architecture document into a concrete sequence of commits,
organised into phases. Each commit is small, purposeful, and traceable to
an architecture decision.

This is not an architecture document. No new bounded contexts, entities,
aggregates, repositories, services, permissions, or persistence models are
introduced. Everything defined here already exists in the architecture documents.

---

## Governing Constraints

- Python 3.13, FastAPI, SQLAlchemy 2.0 async, Alembic, Pydantic v2, pytest
- Next.js 15, TypeScript 5, Tailwind CSS 4
- PostgreSQL 16 + PostGIS 3
- Docker Compose for local development
- Railway for hosting
- Supabase Auth for authentication
- Solo developer; production-grade standards throughout
- No commit ships without passing tests
- The engine is written and fully tested before any API or persistence code

---

## The Vertical Slice Target

The first working end-to-end path is:

```
Create Property → Create Deal → Update Inputs → Run Calculation
  → Create Snapshot → Retrieve Snapshot
```

Everything else is built toward this slice. No frontend polish, no admin UI,
no configuration management UI, and no portfolio features until this slice
works end-to-end and is deployed to staging.

---

---

# Repository Structure

```
propiq/                               ← monorepo root
│
├── backend/                          ← FastAPI application
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                   ← FastAPI app factory
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py             ← Settings (Pydantic BaseSettings)
│   │   │   └── logging.py            ← Structured JSON log setup
│   │   │
│   │   ├── domain/                   ← Pure domain entities and value objects
│   │   │   ├── __init__.py
│   │   │   ├── enums.py              ← All enums: OwnershipStructure, DealStatus, etc.
│   │   │   ├── errors.py             ← NotFoundError, DomainError, etc.
│   │   │   ├── entities/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── user.py
│   │   │   │   ├── investor_profile.py
│   │   │   │   ├── property.py
│   │   │   │   ├── deal.py
│   │   │   │   └── snapshot.py       ← CalculationSnapshot aggregate
│   │   │   └── value_objects/
│   │   │       ├── __init__.py
│   │   │       ├── money.py
│   │   │       ├── rate.py
│   │   │       ├── address.py
│   │   │       └── input_source.py
│   │   │
│   │   ├── engine/                   ← Pure underwriting engine — zero I/O
│   │   │   ├── __init__.py
│   │   │   ├── contracts.py          ← EngineInput, EngineConfig, EngineResult
│   │   │   ├── version.py            ← ENGINE_VERSION = "1.0.0"
│   │   │   ├── orchestrator.py       ← engine.run() — single entry point
│   │   │   ├── validation/
│   │   │   │   ├── __init__.py
│   │   │   │   └── rules.py          ← V-01 through V-25 as declarative data
│   │   │   ├── calculations/
│   │   │   │   ├── __init__.py
│   │   │   │   └── formulas.py       ← F-01 through F-22 as pure functions
│   │   │   ├── tax/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── individual.py     ← Tax pathway A: Section 24
│   │   │   │   └── limited_company.py← Tax pathway B: Corporation Tax
│   │   │   └── risk_flags/
│   │   │       ├── __init__.py
│   │   │       └── definitions.py    ← Risk flag conditions as declarative data
│   │   │
│   │   ├── db/                       ← Database infrastructure
│   │   │   ├── __init__.py
│   │   │   ├── session.py            ← AsyncSession factory, engine setup
│   │   │   ├── base.py               ← DeclarativeBase for all ORM models
│   │   │   └── models/               ← SQLAlchemy ORM mapped classes
│   │   │       ├── __init__.py
│   │   │       ├── user.py
│   │   │       ├── investor_profile.py
│   │   │       ├── property.py
│   │   │       ├── deal.py
│   │   │       ├── snapshot.py       ← All snapshot_* table models
│   │   │       ├── configuration.py  ← All config_* table models
│   │   │       └── audit.py
│   │   │
│   │   ├── repositories/             ← Data access — implements interfaces
│   │   │   ├── __init__.py
│   │   │   ├── interfaces/           ← Abstract repository interfaces
│   │   │   │   ├── __init__.py
│   │   │   │   ├── i_user.py
│   │   │   │   ├── i_property.py
│   │   │   │   ├── i_deal.py
│   │   │   │   ├── i_snapshot.py
│   │   │   │   ├── i_configuration.py
│   │   │   │   └── i_audit.py
│   │   │   ├── user_repository.py
│   │   │   ├── investor_profile_repository.py
│   │   │   ├── property_repository.py
│   │   │   ├── deal_repository.py
│   │   │   ├── snapshot_repository.py
│   │   │   ├── configuration_repository.py
│   │   │   └── audit_repository.py
│   │   │
│   │   ├── services/                 ← Application services — orchestration
│   │   │   ├── __init__.py
│   │   │   ├── calculation_service.py
│   │   │   ├── configuration_service.py
│   │   │   ├── snapshot_service.py
│   │   │   ├── deal_service.py
│   │   │   ├── property_service.py
│   │   │   ├── user_service.py
│   │   │   └── audit_service.py
│   │   │
│   │   └── api/                      ← HTTP boundary — no business logic
│   │       ├── __init__.py
│   │       ├── dependencies.py       ← Auth verification, user resolution
│   │       ├── error_handlers.py     ← Global exception → HTTP mapping
│   │       └── v1/
│   │           ├── __init__.py
│   │           ├── router.py         ← Aggregates all v1 routers
│   │           ├── routes/
│   │           │   ├── __init__.py
│   │           │   ├── health.py
│   │           │   ├── auth.py
│   │           │   ├── properties.py
│   │           │   ├── deals.py
│   │           │   ├── calculations.py
│   │           │   └── snapshots.py
│   │           └── schemas/          ← Pydantic request/response DTOs
│   │               ├── __init__.py
│   │               ├── common.py     ← Shared types (PageRequest, etc.)
│   │               ├── property.py
│   │               ├── deal.py
│   │               ├── calculation.py
│   │               └── snapshot.py
│   │
│   ├── alembic/
│   │   ├── env.py
│   │   ├── script.py.mako
│   │   └── versions/
│   │       └── (migration files)
│   │
│   ├── tests/
│   │   ├── conftest.py               ← Shared fixtures: REFERENCE_CONFIG, scenarios
│   │   ├── unit/
│   │   │   ├── formulas/             ← Layer 1: F-01 through F-22
│   │   │   ├── tax/                  ← Tax pathways A and B
│   │   │   ├── validation/           ← V-01 through V-25
│   │   │   ├── risk_flags/           ← All flag definitions
│   │   │   └── precision/            ← Decimal arithmetic tests
│   │   ├── regression/               ← Layer 4: E-01 through E-12
│   │   │   ├── conftest.py
│   │   │   └── (scenario test files)
│   │   ├── determinism/              ← Layer 5: reproducibility guarantees
│   │   ├── integration/
│   │   │   ├── repositories/         ← Repository integration tests (test DB)
│   │   │   └── snapshots/            ← Snapshot payload tests
│   │   └── api/                      ← FastAPI TestClient tests
│   │
│   ├── scripts/
│   │   └── seed_configuration.py     ← Inserts v1.0 config seed data
│   │
│   ├── pyproject.toml
│   ├── alembic.ini
│   └── Dockerfile
│
├── frontend/                         ← Next.js application
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx                  ← Root (redirect to dashboard or login)
│   │   ├── (auth)/
│   │   │   └── login/
│   │   │       └── page.tsx
│   │   └── (app)/
│   │       ├── layout.tsx            ← App shell with auth guard
│   │       ├── dashboard/
│   │       │   └── page.tsx
│   │       └── properties/
│   │           └── [propertyId]/
│   │               └── deals/
│   │                   ├── page.tsx  ← Deal list for property
│   │                   └── [dealId]/
│   │                       ├── page.tsx        ← Deal workspace
│   │                       └── analysis/
│   │                           └── page.tsx    ← Snapshot summary
│   ├── components/
│   │   ├── ui/                       ← Shared primitive components
│   │   ├── deal/
│   │   │   ├── DealInputForm.tsx
│   │   │   └── DealStatusBadge.tsx
│   │   └── analysis/
│   │       ├── SnapshotSummary.tsx
│   │       ├── CashFlowWaterfall.tsx
│   │       ├── AcquisitionCostBreakdown.tsx
│   │       ├── SDLTBreakdown.tsx
│   │       ├── YieldMetrics.tsx
│   │       └── RiskFlagList.tsx
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.ts             ← Base HTTP client with JWT attachment
│   │   │   ├── properties.ts
│   │   │   ├── deals.ts
│   │   │   ├── calculations.ts
│   │   │   └── snapshots.ts
│   │   ├── types/                    ← TypeScript types mirroring API contracts
│   │   │   ├── property.ts
│   │   │   ├── deal.ts
│   │   │   ├── snapshot.ts
│   │   │   └── calculation.ts
│   │   └── supabase/
│   │       ├── client.ts             ← Browser Supabase client
│   │       └── server.ts             ← Server-side Supabase client
│   ├── hooks/
│   │   ├── useAuth.ts
│   │   ├── useDeals.ts
│   │   └── useSnapshot.ts
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── next.config.ts
│
├── infrastructure/
│   ├── docker-compose.yml            ← Local dev: postgres, pgadmin
│   ├── docker-compose.test.yml       ← Test DB only
│   ├── railway.toml                  ← Railway deployment config
│   └── nginx/                        ← Phase 2+ (not needed for Railway)
│
├── scripts/
│   ├── setup_dev.sh                  ← One-command dev environment setup
│   └── run_tests.sh                  ← Full test suite runner
│
├── docs/                             ← Architecture documents (the 20 files)
│
├── .env.example
├── .gitignore
├── README.md
└── Makefile                          ← make dev, make test, make migrate, etc.
```

---

---

# Implementation Phases

---

## PHASE 0 — Foundation
**Goal:** Working local development environment, project skeleton, CI foundation.
**Duration:** 1–2 days
**Exit criteria:** `make dev` starts postgres and the backend healthcheck responds.
Pytest can be run and finds (zero) tests. Git history is clean.

---

### Commit 0.1 — Monorepo skeleton

**Message:** `chore: initialise monorepo structure`

**Purpose:** Create the root directory layout, .gitignore, README stub,
Makefile with placeholder targets, and the top-level structure.

**Files created:**
```
.gitignore
.env.example
README.md
Makefile
propiq/              (empty dirs with .gitkeep)
backend/
frontend/
infrastructure/
scripts/
docs/
```

**Why:** Every subsequent commit has a home. No code yet — just structure.

**Dependencies:** None.

---

### Commit 0.2 — Docker Compose local environment

**Message:** `infra: add docker-compose for local postgres with PostGIS`

**Purpose:** Define the local development database with PostGIS enabled.

**Files created:**
```
infrastructure/docker-compose.yml
infrastructure/docker-compose.test.yml
```

**docker-compose.yml services:**
- `postgres`: postgres:16-alpine with postgis extension, port 5432
- `pgadmin`: dpage/pgadmin4, port 5050 (local admin UI)

**docker-compose.test.yml services:**
- `postgres_test`: identical postgres config on port 5433

**Why:** PostGIS must be enabled from the first database instance (ADR-006).
Separate test DB avoids contaminating dev data.

**Dependencies:** Commit 0.1

---

### Commit 0.3 — Python project skeleton

**Message:** `chore: python 3.13 project with pyproject.toml`

**Purpose:** Set up the Python project with all required dependencies
declared but no application code yet.

**Files created:**
```
backend/pyproject.toml
backend/.python-version      (3.13)
```

**pyproject.toml dependencies:**
```
[project]
python = "^3.13"

[tool.poetry.dependencies]
fastapi = "^0.115"
uvicorn = {extras = ["standard"], version = "^0.32"}
sqlalchemy = {extras = ["asyncio"], version = "^2.0"}
alembic = "^1.14"
asyncpg = "^0.30"
pydantic = "^2.10"
pydantic-settings = "^2.6"
python-jose = {extras = ["cryptography"], version = "^3.3"}
httpx = "^0.28"          # for Supabase auth verification
structlog = "^24.4"      # structured logging

[tool.poetry.dev-dependencies]
pytest = "^8.3"
pytest-asyncio = "^0.24"
pytest-cov = "^6.0"
anyio = {extras = ["trio"], version = "^4.6"}

[tool.pytest.ini_options]
asyncio_mode = "auto"
```

**Why:** Pinning versions explicitly prevents dependency drift. asyncpg is
the async PostgreSQL driver required by SQLAlchemy 2.0 async mode.

**Dependencies:** Commit 0.1

---

### Commit 0.4 — Backend application skeleton

**Message:** `feat: fastapi application factory with health endpoint`

**Purpose:** The minimum FastAPI application that starts, responds to `/api/v1/health`,
and has structured logging initialised.

**Files created:**
```
backend/app/__init__.py
backend/app/main.py
backend/app/core/__init__.py
backend/app/core/config.py
backend/app/core/logging.py
backend/app/api/__init__.py
backend/app/api/v1/__init__.py
backend/app/api/v1/router.py
backend/app/api/v1/routes/__init__.py
backend/app/api/v1/routes/health.py
```

**backend/app/core/config.py:** Pydantic BaseSettings reading from environment:
- `DATABASE_URL` (async postgresql+asyncpg://...)
- `TEST_DATABASE_URL`
- `SUPABASE_URL`
- `SUPABASE_ANON_KEY`
- `SUPABASE_JWT_SECRET`
- `ENVIRONMENT` (development/staging/production)
- `LOG_LEVEL`

**backend/app/core/logging.py:** structlog configuration producing JSON output
in production, pretty console output in development. Base fields: timestamp,
level, service, environment, version, event, message.

**backend/app/main.py:**
```python
# Application factory pattern
def create_app() -> FastAPI:
    app = FastAPI(title="PropIQ API", version="1.0.0")
    app.include_router(v1_router, prefix="/api/v1")
    # error handlers registered here (stubs for now)
    return app

app = create_app()
```

**backend/app/api/v1/routes/health.py:**
```python
# GET /api/v1/health → {"status": "ok", "environment": "..."}
```

**Why:** The application factory pattern allows the app to be created
differently in test vs production. Health endpoint confirms the server starts.

**Dependencies:** Commit 0.3

---

### Commit 0.5 — Alembic initialisation

**Message:** `chore: initialise alembic with async engine`

**Purpose:** Set up Alembic pointing at the development database.

**Files created:**
```
backend/alembic.ini
backend/alembic/env.py
backend/alembic/script.py.mako
backend/alembic/versions/  (empty)
backend/app/db/__init__.py
backend/app/db/base.py
backend/app/db/session.py
```

**backend/app/db/base.py:** SQLAlchemy `DeclarativeBase`. No models yet.

**backend/app/db/session.py:** Async engine creation from `DATABASE_URL`,
`AsyncSessionLocal` factory, `get_db()` FastAPI dependency.

**backend/alembic/env.py:** Configured for async engine with target_metadata
pointing to `Base.metadata`.

**Why:** Alembic must be configured before any models exist so migrations are
managed from the first model. Async engine configuration is non-trivial and
must be correct from the start.

**Dependencies:** Commit 0.4

---

### Commit 0.6 — Makefile targets and setup script

**Message:** `chore: makefile targets for dev workflow`

**Purpose:** Make developer workflow frictionless.

**Files created/modified:**
```
Makefile
scripts/setup_dev.sh
```

**Makefile targets:**
```
make dev          # docker-compose up postgres + uvicorn --reload
make test         # pytest with test DB
make migrate      # alembic upgrade head
make seed         # python scripts/seed_configuration.py
make lint         # ruff check + mypy
make typecheck    # mypy app/
make shell        # ipython with app context
```

**Why:** A solo developer runs these commands dozens of times per day.
Friction here multiplies. Also documents the workflow for future contributors.

**Dependencies:** Commits 0.4, 0.5

---

**Phase 0 Exit Criteria:**
- [ ] `make dev` starts postgres and FastAPI on port 8000
- [ ] `GET http://localhost:8000/api/v1/health` returns 200
- [ ] `make test` runs (zero tests, all pass)
- [ ] `make migrate` runs without error (zero migrations applied)
- [ ] Git log is clean: 6 focused commits

---

---

## PHASE 1 — Domain Entities and Enums
**Goal:** All domain enums, value objects, and entity dataclasses defined.
No database yet. No engine yet. Pure Python domain layer.
**Duration:** 1 day
**Exit criteria:** All domain types importable. Domain invariants enforced
at construction time. Zero test failures.

---

### Commit 1.1 — All enums

**Message:** `feat(domain): define all domain enums`

**Purpose:** Every enum used by the domain, engine, and persistence layers.

**Files created:**
```
backend/app/domain/__init__.py
backend/app/domain/enums.py
```

**Enums defined (from DATABASE_SCHEMA_DESIGN.md Section 1):**
```python
class OwnershipStructure(str, Enum):
    INDIVIDUAL = "INDIVIDUAL"
    LIMITED_COMPANY = "LIMITED_COMPANY"

class IncomeTaxBand(str, Enum):
    BASIC_RATE = "BASIC_RATE"
    HIGHER_RATE = "HIGHER_RATE"
    ADDITIONAL_RATE = "ADDITIONAL_RATE"

class MortgageType(str, Enum):
    INTEREST_ONLY = "INTEREST_ONLY"
    REPAYMENT = "REPAYMENT"

class PropertyType(str, Enum):
    RESIDENTIAL_SINGLE_LET = "RESIDENTIAL_SINGLE_LET"

class Tenure(str, Enum):
    FREEHOLD = "FREEHOLD"
    LEASEHOLD = "LEASEHOLD"

class PropertyCountry(str, Enum):
    ENGLAND = "ENGLAND"

class DealStatus(str, Enum):
    DRAFT = "DRAFT"
    ANALYSED = "ANALYSED"
    ARCHIVED = "ARCHIVED"

class UserStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    ARCHIVED = "ARCHIVED"

class CalculationOutcome(str, Enum):
    SUCCESS = "SUCCESS"
    VALIDATION_FAILURE = "VALIDATION_FAILURE"
    ENGINE_ERROR = "ENGINE_ERROR"

class InputSource(str, Enum):
    USER_OVERRIDE = "USER_OVERRIDE"
    CONFIG_DEFAULT = "CONFIG_DEFAULT"

class FlagSeverity(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    INFO = "INFO"
```

**Why:** Enums as `str, Enum` subclasses serialise directly to their string
value in JSON without extra configuration. They are importable by all other
layers. Defining them first removes forward-reference issues.

**Dependencies:** Commit 0.4

---

### Commit 1.2 — Domain errors

**Message:** `feat(domain): define typed domain errors`

**Purpose:** Typed exceptions for the service layer. The API layer maps these
to HTTP status codes.

**Files created:**
```
backend/app/domain/errors.py
```

**Error types:**
```python
class NotFoundError(Exception):
    def __init__(self, entity: str, id: uuid.UUID): ...

class DomainError(Exception):
    def __init__(self, message: str): ...

class CalculationValidationFailure(Exception):
    def __init__(self, hard_errors: list, warnings: list): ...

class CalculationError(Exception):
    def __init__(self, message: str): ...

class ConfigurationNotFoundError(Exception):
    def __init__(self, config_type: str, version_id=None): ...

class PersistenceIntegrityError(Exception):
    def __init__(self, detail: str): ...

class UnauthorisedAdminError(Exception): ...
```

**Why:** Typed errors allow the API layer's exception handlers to produce
the correct HTTP response code without inspecting exception messages.

**Dependencies:** Commit 1.1

---

### Commit 1.3 — Value objects

**Message:** `feat(domain): define value objects (Money, Rate, Address, InputSource pair)`

**Purpose:** Immutable value objects from DOMAIN_MODEL_ARCHITECTURE.md Part 5.

**Files created:**
```
backend/app/domain/value_objects/__init__.py
backend/app/domain/value_objects/money.py
backend/app/domain/value_objects/rate.py
backend/app/domain/value_objects/address.py
```

**money.py:**
```python
@dataclass(frozen=True)
class Money:
    amount: Decimal
    currency: str = "GBP"

    def __post_init__(self):
        if not isinstance(self.amount, Decimal):
            object.__setattr__(self, 'amount', Decimal(str(self.amount)))
```

**rate.py:**
```python
@dataclass(frozen=True)
class Rate:
    """Rate stored as percentage value (5.5 means 5.5%, not 0.055)"""
    value: Decimal

    def __post_init__(self):
        if not isinstance(self.value, Decimal):
            object.__setattr__(self, 'value', Decimal(str(self.value)))
    
    def as_decimal_fraction(self) -> Decimal:
        return self.value / Decimal("100")
```

**address.py:**
```python
import re

UK_POSTCODE_RE = re.compile(
    r'^[A-Z]{1,2}[0-9][0-9A-Z]?\s*[0-9][A-Z]{2}$', re.IGNORECASE
)

@dataclass(frozen=True)
class PropertyAddress:
    address_line_1: str
    city: str
    postcode: str
    address_line_2: str | None = None
    country: PropertyCountry = PropertyCountry.ENGLAND

    def __post_init__(self):
        normalised = self.postcode.strip().upper()
        if not UK_POSTCODE_RE.match(normalised):
            raise DomainError(f"Invalid UK postcode format: {self.postcode}")
        object.__setattr__(self, 'postcode', normalised)
```

**Why:** `frozen=True` dataclasses are value objects by construction —
they cannot be mutated after creation. The `__post_init__` methods enforce
the domain invariants described in DOMAIN_MODEL_ARCHITECTURE.md.

**Dependencies:** Commit 1.2

---

### Commit 1.4 — Domain entity dataclasses

**Message:** `feat(domain): define User, InvestorProfile, Property, Deal entities`

**Purpose:** Pure Python dataclasses for the four core mutable entities.
No ORM. No database types. Plain data with behaviour.

**Files created:**
```
backend/app/domain/entities/__init__.py
backend/app/domain/entities/user.py
backend/app/domain/entities/investor_profile.py
backend/app/domain/entities/property.py
backend/app/domain/entities/deal.py
```

**deal.py key structure:**
```python
@dataclass
class DealWorkingInputs:
    purchase_price: Decimal | None = None
    monthly_rent: Decimal | None = None
    deposit_amount: Decimal | None = None
    # ... all working input fields nullable
    
@dataclass
class Deal:
    id: uuid.UUID
    user_id: uuid.UUID
    property_id: uuid.UUID
    label: str
    status: DealStatus
    working_inputs: DealWorkingInputs
    latest_snapshot_id: uuid.UUID | None = None
    investor_profile_id: uuid.UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def apply_snapshot_created(self, snapshot_id: uuid.UUID) -> None:
        self.latest_snapshot_id = snapshot_id
        if self.status == DealStatus.DRAFT:
            self.status = DealStatus.ANALYSED
        self.updated_at = datetime.now(UTC)

    def archive(self) -> None:
        if self.status == DealStatus.ARCHIVED:
            raise DomainError("Deal is already archived")
        self.status = DealStatus.ARCHIVED
        self.updated_at = datetime.now(UTC)
```

**Why:** Domain entities are plain dataclasses. They carry the behaviour
methods described in DOMAIN_MODEL_ARCHITECTURE.md Parts 9.3 and 4.4.
The methods enforce state transition rules directly on the entity.

**Dependencies:** Commits 1.1, 1.2, 1.3

---

### Commit 1.5 — Snapshot domain entity

**Message:** `feat(domain): define CalculationSnapshot aggregate entity`

**Purpose:** The CalculationSnapshot aggregate root and all its sub-entities
as pure Python dataclasses. Immutable after construction.

**Files created:**
```
backend/app/domain/entities/snapshot.py
```

**Key types:**
```python
@dataclass(frozen=True)
class SnapshotInputs: ...        # all required + optional inputs with sources

@dataclass(frozen=True)
class SnapshotOutputs: ...       # all output fields

@dataclass(frozen=True)
class SnapshotIntermediates: ... # all intermediate values

@dataclass(frozen=True)
class SDLTBandResult: ...        # per-band SDLT breakdown

@dataclass(frozen=True)
class RiskFlag:
    code: str
    severity: FlagSeverity
    triggered_by_field: str
    triggered_by_value: str
    message: str

@dataclass(frozen=True)
class ValidationWarning:
    rule_code: str
    field: str
    message: str

@dataclass(frozen=True)
class ConfigVersionRefs:
    assumption_config_version_id: uuid.UUID
    sdlt_config_version_id: uuid.UUID
    corporation_tax_config_version_id: uuid.UUID

@dataclass
class CalculationSnapshot:
    id: uuid.UUID
    deal_id: uuid.UUID
    user_id: uuid.UUID
    engine_version: str
    config_version_refs: ConfigVersionRefs
    calculated_at: datetime
    inputs: SnapshotInputs
    outputs: SnapshotOutputs
    intermediates: SnapshotIntermediates
    risk_flags: list[RiskFlag]
    validation_warnings: list[ValidationWarning]
    is_superseded: bool = False
    superseded_at: datetime | None = None
    calculation_duration_ms: int | None = None
```

**Why:** `SnapshotInputs`, `SnapshotOutputs`, `SnapshotIntermediates`, and
`RiskFlag` are `frozen=True` (immutable). The `CalculationSnapshot` root
is mutable only for `is_superseded` and `superseded_at`, matching the
architecture invariant.

**Dependencies:** Commit 1.4

---

### Commit 1.6 — Domain entity unit tests

**Message:** `test(domain): unit tests for entity invariants and value objects`

**Purpose:** Verify domain invariants are enforced at construction time.

**Files created:**
```
backend/tests/conftest.py         (empty for now)
backend/tests/unit/__init__.py
backend/tests/unit/test_domain_entities.py
backend/tests/unit/test_value_objects.py
```

**Tests:**
- `PropertyAddress` with invalid UK postcode raises `DomainError`
- `PropertyAddress` with valid postcode normalises to uppercase
- `Deal.archive()` on an already-archived deal raises `DomainError`
- `Deal.apply_snapshot_created()` transitions DRAFT → ANALYSED
- `Deal.apply_snapshot_created()` keeps ANALYSED → ANALYSED (no change)
- `Rate.as_decimal_fraction()` returns 0.055 for Rate(5.5)
- `Money` with integer input coerces to `Decimal`
- `frozen=True` entities raise on mutation attempt

**Why:** Domain invariants must be tested at this layer independently of
any infrastructure. If the `DomainError` on invalid postcode ever breaks,
this test catches it before it reaches production.

**Dependencies:** Commit 1.5

---

**Phase 1 Exit Criteria:**
- [ ] All domain enums, errors, value objects, and entities importable
- [ ] Domain invariants enforced (tested)
- [ ] `make test` passes
- [ ] Zero TODO items in domain layer

---

---

## PHASE 2 — Underwriting Engine (Core IP)
**Goal:** The complete underwriting engine, fully tested against all 12
reference scenarios from ENGINE_CONTRACTS.md. No database, no API, no
services. Pure computation.
**Duration:** 4–6 days
**Risks:** Section 24 tax arithmetic, SDLT band boundaries, Decimal precision.
All formulas must match ENGINE_CONTRACTS.md exactly.
**Exit criteria:** E-01 through E-12 all pass. All determinism tests pass.
Zero engine errors possible from valid inputs.

---

### Commit 2.1 — Engine contracts

**Message:** `feat(engine): EngineInput, EngineConfig, EngineResult contracts`

**Purpose:** The plain data contract types that define the engine's
input/output boundary. No calculation logic.

**Files created:**
```
backend/app/engine/__init__.py
backend/app/engine/contracts.py
backend/app/engine/version.py
```

**version.py:**
```python
ENGINE_VERSION: str = "1.0.0"
```

**contracts.py** defines as frozen dataclasses:
- `SDLTBand`, `SDLTConfig`
- `CorporationTaxConfig`
- `AssumptionConfig`
- `EngineConfig` (contains the three config types)
- `EngineInput` (all required + optional fields, all typed with `Decimal`)
- `EngineOutputs`, `EngineIntermediates`, `SDLTBandResult`
- `EngineResult` (outputs + intermediates + risk_flags + validation_warnings)
- `ValidationError`, `ValidationWarning`, `ValidationResult`
- `RiskFlag`
- `EngineError`

All monetary values typed as `Decimal`. No `float` anywhere.

**Why:** The contracts must be defined before any calculation code so that
every formula function signature is constrained to accept and return the
correct types. Importing `contracts.py` from the engine module should have
zero side effects.

**Dependencies:** Commit 1.5

---

### Commit 2.2 — Formula functions F-01 through F-08

**Message:** `feat(engine): income and financing formulas F-01 through F-08`

**Purpose:** Pure formula functions for gross rent, void adjustment, loan
amount, LTV, mortgage payment (both pathways), and mortgage interest.

**Files created:**
```
backend/app/engine/calculations/__init__.py
backend/app/engine/calculations/formulas.py
```

**Key implementation notes:**
- All inputs and outputs typed as `Decimal`
- `ROUND_HALF_UP` rounding applied only when storing to `EngineOutputs`/
  `EngineIntermediates`, never during intermediate steps
- Repayment formula uses `Decimal` arithmetic throughout — no `float`
  intermediate values
- Zero interest rate: returns `Decimal("0")` for monthly payment, sets
  cash_purchase flag in orchestrator (not handled in formula itself)

**Files created:**
```
backend/tests/unit/formulas/test_f01_gross_annual_rent.py
backend/tests/unit/formulas/test_f02_void_rate_conversion.py
backend/tests/unit/formulas/test_f03_effective_annual_rent.py
backend/tests/unit/formulas/test_f04_loan_amount.py
backend/tests/unit/formulas/test_f05_ltv.py
backend/tests/unit/formulas/test_f06_monthly_mortgage_payment.py
backend/tests/unit/formulas/test_f07_annual_mortgage_cost.py
backend/tests/unit/formulas/test_f08_annual_mortgage_interest.py
```

Each test file tests happy path + the specific edge cases from
TEST_STRATEGY.md Section 3.3.

**Dependencies:** Commit 2.1

---

### Commit 2.3 — Formula functions F-09 through F-15

**Message:** `feat(engine): operating cost and acquisition formulas F-09 through F-15`

**Purpose:** Letting agent cost (with VAT), maintenance reserve, total
operating costs, NOI, and SDLT calculation.

**Files created:**
```
(additions to formulas.py)
backend/tests/unit/formulas/test_f09_letting_agent.py
backend/tests/unit/formulas/test_f10_maintenance_reserve.py
backend/tests/unit/formulas/test_f11_total_operating_costs.py
backend/tests/unit/formulas/test_f12_noi.py
backend/tests/unit/formulas/test_f13_sdlt.py
backend/tests/unit/formulas/test_f14_total_acquisition_cost.py
backend/tests/unit/formulas/test_f15_total_cash_deployed.py
```

**SDLT test coverage (from TEST_STRATEGY.md Section 3.3):**
All 12 boundary values from £100,000 to £1,500,001+ with and without
surcharge. Each test states the manual calculation in its docstring.

**Dependencies:** Commit 2.2

---

### Commit 2.4 — Formula functions F-16 through F-22

**Message:** `feat(engine): yield, return, and stress test formulas F-16 through F-22`

**Purpose:** Gross yield, net yield, ROCE, cash flow, cash-on-cash return,
and ICR stress test.

**Files created:**
```
(additions to formulas.py)
backend/tests/unit/formulas/test_f16_gross_yield.py
backend/tests/unit/formulas/test_f17_net_yield.py
backend/tests/unit/formulas/test_f18_roce.py
backend/tests/unit/formulas/test_f19_annual_cash_flow.py
backend/tests/unit/formulas/test_f20_monthly_cash_flow.py
backend/tests/unit/formulas/test_f21_cash_on_cash.py
backend/tests/unit/formulas/test_f22_icr.py
```

**ICR edge cases:** cash purchase (icr=None), exactly 125.00 (no flag),
exactly 124.99 (flag fires).

**Dependencies:** Commit 2.3

---

### Commit 2.5 — Tax pathways

**Message:** `feat(engine): Section 24 individual and corporation tax pathways`

**Purpose:** Tax Pathway A (Individual / Section 24) and Tax Pathway B
(Limited Company / Corporation Tax) as pure functions.

**Files created:**
```
backend/app/engine/tax/__init__.py
backend/app/engine/tax/individual.py
backend/app/engine/tax/limited_company.py
backend/tests/unit/tax/test_pathway_a_individual.py
backend/tests/unit/tax/test_pathway_b_limited_company.py
backend/tests/unit/tax/test_tax_pathway_routing.py
```

**Test scenarios (from TEST_STRATEGY.md Section 4.2-4.3):**
- TA-01 through TA-06 (individual, all tax bands, with/without leasehold)
- TB-01 through TB-07 (Ltd Co, positive/zero/negative profit, rate boundaries)

**Critical test:** Section 24 basic-rate result matches E-01 expected
`annual_tax_liability = 0.00` exactly. The credit (£1,425.00) exceeds
the gross tax (£1,358.62). `MAX(0, -66.38) = 0.00`.

**Dependencies:** Commit 2.4

---

### Commit 2.6 — Validation pipeline

**Message:** `feat(engine): validation pipeline V-01 through V-25`

**Purpose:** All 25 validation rules as declarative data, the validation
pipeline runner, and the `ValidationResult` builder.

**Files created:**
```
backend/app/engine/validation/__init__.py
backend/app/engine/validation/rules.py
backend/tests/unit/validation/test_hard_rules.py
backend/tests/unit/validation/test_warn_rules.py
backend/tests/unit/validation/test_validation_pipeline.py
```

**Rules structure:**
```python
@dataclass(frozen=True)
class ValidationRule:
    code: str
    field: str
    severity: Literal["HARD", "WARN"]
    condition: Callable[[EngineInput], bool]
    message: str

VALIDATION_RULES: list[ValidationRule] = [
    ValidationRule(
        code="V-01",
        field="purchase_price",
        severity="HARD",
        condition=lambda i: i.purchase_price <= Decimal("0"),
        message="Purchase price must be greater than zero."
    ),
    # ... V-02 through V-25
]
```

The pipeline runner iterates all rules, collects HARD and WARN results,
and returns `ValidationResult(is_valid, hard_errors, warnings)`.

**Dependencies:** Commit 2.5

---

### Commit 2.7 — Risk flag definitions

**Message:** `feat(engine): risk flag evaluator with all 16 flag definitions`

**Purpose:** All 16 risk flags as declarative condition data. The evaluator
iterates all definitions against the completed calculation context.

**Files created:**
```
backend/app/engine/risk_flags/__init__.py
backend/app/engine/risk_flags/definitions.py
backend/tests/unit/risk_flags/  (16 individual flag test files)
backend/tests/unit/risk_flags/test_flag_evaluation_pipeline.py
```

**Flag structure:**
```python
@dataclass(frozen=True)
class RiskFlagDefinition:
    code: str
    severity: FlagSeverity
    triggered_by_field: str
    message: str
    condition: Callable[[EvaluationContext], bool]
```

**Dependencies:** Commit 2.6

---

### Commit 2.8 — Engine orchestrator

**Message:** `feat(engine): orchestrator — engine.run() entry point`

**Purpose:** The single entry point that executes the 13-step calculation
sequence defined in ENGINE_ARCHITECTURE.md Part 6.

**Files created:**
```
backend/app/engine/orchestrator.py
backend/tests/unit/precision/test_decimal_types.py
backend/tests/unit/precision/test_rounding_point.py
backend/tests/unit/precision/test_rounding_mode.py
backend/tests/unit/precision/test_no_float_arithmetic.py
```

**orchestrator.py structure:**
```python
from decimal import getcontext, ROUND_HALF_UP

getcontext().prec = 10  # ENGINE_CONTRACTS.md Part 7.1

def run(engine_input: EngineInput, engine_config: EngineConfig
        ) -> EngineResult | ValidationResult | EngineError:
    # Step 0: Validation
    # Steps 1-13: Orchestration sequence
    # Returns EngineResult, ValidationResult, or EngineError
    ...
```

The orchestrator passes explicit values to each step — never the full
`EngineInput` object to formula functions directly (ENGINE_ARCHITECTURE.md).

**Dependencies:** Commits 2.5, 2.6, 2.7

---

### Commit 2.9 — Test fixtures for reference scenarios

**Message:** `test(engine): reference scenario fixtures E-01 through E-12`

**Purpose:** The static fixture data for all 12 canonical reference scenarios
from ENGINE_CONTRACTS.md Part 11. These are the authoritative expected values.

**Files created:**
```
backend/tests/conftest.py         (REFERENCE_CONFIG, all scenario input fixtures)
backend/tests/regression/conftest.py
```

All expected output values are hardcoded from ENGINE_CONTRACTS.md — not
derived from any formula.

**Dependencies:** Commit 2.8

---

### Commit 2.10 — Regression tests E-01 through E-06

**Message:** `test(engine): regression tests E-01 through E-06`

**Purpose:** Full engine runs for the first six canonical scenarios.

**Files created:**
```
backend/tests/regression/test_e01_baseline_basic_rate.py
backend/tests/regression/test_e02_higher_rate_section24.py
backend/tests/regression/test_e03_ltd_co_standard.py
backend/tests/regression/test_e04_lower_leverage_positive.py
backend/tests/regression/test_e05_high_value_ltd_ated.py
backend/tests/regression/test_e06_leasehold_higher_rate.py
```

Each test asserts every output field, every intermediate, and the exact set
of risk flags against ENGINE_CONTRACTS.md values.

**Dependencies:** Commit 2.9

---

### Commit 2.11 — Regression tests E-07 through E-12 and determinism tests

**Message:** `test(engine): regression E-07 to E-12, determinism guarantees`

**Purpose:** Remaining scenarios (validation failures, warnings, edge cases)
and all determinism/reproducibility tests from TEST_STRATEGY.md Part 8.

**Files created:**
```
backend/tests/regression/test_e07_hard_validation_failure.py
backend/tests/regression/test_e08_warn_only_validation.py
backend/tests/regression/test_e09_short_lease_flag.py
backend/tests/regression/test_e10_additional_rate.py
backend/tests/regression/test_e11_thin_margin.py
backend/tests/regression/test_e12_high_refurb.py
backend/tests/regression/test_cross_scenario_consistency.py
backend/tests/determinism/test_idempotent_execution.py
backend/tests/determinism/test_serialisation_roundtrip.py
backend/tests/determinism/test_config_version_isolation.py
backend/tests/determinism/test_no_internal_state.py
```

**Dependencies:** Commit 2.10

---

**Phase 2 Exit Criteria:**
- [ ] All 12 regression scenarios pass
- [ ] All 5 determinism tests pass
- [ ] All formula boundary tests pass (SDLT bands, ICR thresholds, etc.)
- [ ] Section 24 E-01/E-02/E-10 monotonicity tests pass
- [ ] Zero `float` type found in any EngineResult (PREC-06 test passes)
- [ ] `make test` runs the full engine test suite in under 10 seconds
- [ ] Engine module imports zero application infrastructure

---

---

## PHASE 3 — Database Schema and Migrations
**Goal:** All Phase 1 database tables created via Alembic migrations.
Configuration seed data insertable. No application code yet.
**Duration:** 1–2 days
**Risks:** NUMERIC column precision, PostgreSQL enum type creation,
ON DELETE RESTRICT on all FKs.
**Exit criteria:** `make migrate` creates all tables. `make seed` inserts
v1.0 configuration data. All schema invariants verified.

---

### Commit 3.1 — ORM base models (no relationships)

**Message:** `feat(db): SQLAlchemy ORM models for all Phase 1 tables`

**Purpose:** SQLAlchemy 2.0 mapped classes for every table in
DATABASE_SCHEMA_DESIGN.md. No relationships between models yet — just
column definitions matching the schema exactly.

**Files created:**
```
backend/app/db/models/__init__.py
backend/app/db/models/user.py
backend/app/db/models/investor_profile.py
backend/app/db/models/property.py
backend/app/db/models/deal.py
backend/app/db/models/snapshot.py
backend/app/db/models/configuration.py
backend/app/db/models/audit.py
```

**Column type mapping:**
- UUID primary keys: `Uuid(as_uuid=True)` with `server_default=func.gen_random_uuid()`
- `NUMERIC(15,6)`: `Numeric(precision=15, scale=6)`
- `NUMERIC(10,6)`: `Numeric(precision=10, scale=6)`
- `NUMERIC(15,10)`: `Numeric(precision=15, scale=10)` (intermediates only)
- Enums: `ARRAY` of string or `Enum` type
- JSONB: `JSONB`
- Timestamps: `DateTime(timezone=True)` with `server_default=func.now()`

**Immutable columns:** columns on snapshot and config tables have
`default=None, server_default=None` (no update default) to make accidental
updates visible.

**Why:** ORM models must be defined before Alembic can auto-generate
migrations. Defining all models in one commit ensures the first migration
is complete and self-consistent.

**Dependencies:** Commit 0.5

---

### Commit 3.2 — Alembic migration: initial schema

**Message:** `migration: initial schema — all Phase 1 tables`

**Purpose:** The first Alembic migration that creates all tables, all
PostgreSQL enum types, all indexes, and all FK constraints.

**Files created:**
```
backend/alembic/versions/0001_initial_schema.py
```

**Migration creates (in dependency order):**
1. PostgreSQL enum types (CREATE TYPE ... AS ENUM)
2. PostGIS extension: `CREATE EXTENSION IF NOT EXISTS postgis`
3. `users` table
4. `investor_profiles` table
5. `properties` table
6. `deals` table
7. `config_engine_versions` table
8. `config_sdlt_versions` + `config_sdlt_bands`
9. `config_corporation_tax_versions`
10. `config_assumption_versions`
11. `snapshot_calculations` table
12. `snapshot_inputs` table
13. `snapshot_outputs` table
14. `snapshot_intermediates` table
15. `snapshot_risk_flags` table
16. `snapshot_validation_warnings` table
17. `audit_calculations` table
18. All indexes from DATABASE_SCHEMA_DESIGN.md Section 8

**ON DELETE RESTRICT** on all foreign keys, verified.
**UNIQUE constraints** on snapshot sub-tables (enforcing 1:1).

**Dependencies:** Commit 3.1

---

### Commit 3.3 — Database role privileges migration

**Message:** `migration: application database role privileges`

**Purpose:** Alembic migration that creates the `propiq_app` role and applies
the privilege model from DATABASE_SCHEMA_DESIGN.md Section 7.

**Files created:**
```
backend/alembic/versions/0002_database_roles.py
```

**Privilege grants:**
```sql
-- INSERT only on snapshot and config tables
GRANT SELECT, INSERT ON snapshot_calculations TO propiq_app;
-- etc. for all snapshot_* tables

-- Column-level UPDATE grant for is_superseded only
GRANT UPDATE (is_superseded, superseded_at) 
  ON snapshot_calculations TO propiq_app;

-- INSERT, UPDATE (no DELETE) on mutable tables
GRANT SELECT, INSERT, UPDATE ON deals TO propiq_app;
-- etc. for users, properties, investor_profiles

-- INSERT only on audit
GRANT SELECT, INSERT ON audit_calculations TO propiq_app;

-- SELECT only on config tables (admin inserts via separate admin_app role)
GRANT SELECT ON config_sdlt_versions TO propiq_app;
-- etc.
```

**Why:** Database-level privilege enforcement is a production-grade trust
requirement (PERSISTENCE_ARCHITECTURE.md Part 1.3). It cannot be deferred
to Phase 2. It is not enforced in local development (where we use a superuser)
but is applied in staging and production.

**Dependencies:** Commit 3.2

---

### Commit 3.4 — Configuration seed script

**Message:** `feat(scripts): seed v1.0 configuration data`

**Purpose:** Idempotent script that inserts the initial configuration versions
from DATABASE_SCHEMA_DESIGN.md Section 9.

**Files created:**
```
backend/scripts/seed_configuration.py
```

**Inserts:**
1. `config_engine_versions`: version "1.0.0"
2. `config_sdlt_versions`: England, effective 2025-04-01
3. `config_sdlt_bands`: 5 bands
4. `config_corporation_tax_versions`: 2023-04-01 rates
5. `config_assumption_versions`: v1.0 defaults

Idempotency: checks `WHERE effective_from = :date AND property_country = 'ENGLAND'`
before inserting SDLT config. Uses `INSERT ... ON CONFLICT DO NOTHING` where
unique constraints exist.

**Why:** The application cannot run without configuration seed data.
`ConfigurationService.load_for_calculation()` will raise
`ConfigurationNotFoundError` if these records are absent.

**Dependencies:** Commit 3.2

---

### Commit 3.5 — Migration integration tests

**Message:** `test(db): schema integrity tests against test database`

**Purpose:** Verify that migrations run cleanly and the schema matches
the design specification.

**Files created:**
```
backend/tests/integration/__init__.py
backend/tests/integration/test_schema_integrity.py
```

**Tests:**
- All expected tables exist
- All expected columns exist with correct nullable/not-null
- UNIQUE constraints on snapshot sub-tables present
- FK relationships from snapshot to config tables intact
- `propiq.config.version.age_days` query works (sanity check on config data)

Uses a pytest fixture that runs migrations against the test DB before
the test session.

**Dependencies:** Commits 3.2, 3.4

---

**Phase 3 Exit Criteria:**
- [ ] `make migrate` completes cleanly against fresh PostgreSQL
- [ ] `make seed` inserts all 5 seed records without error
- [ ] Re-running `make seed` is idempotent
- [ ] Schema integrity tests pass
- [ ] PostGIS extension enabled (verified via `SELECT PostGIS_Version()`)

---

---

## PHASE 4 — Repository Layer
**Goal:** All repository interfaces and implementations. Domain entity
↔ ORM model mapping. Tested against the test database.
**Duration:** 3–4 days
**Risks:** Decimal precision in ORM → domain mapping, async session management,
snapshot atomic write.
**Exit criteria:** All repository integration tests pass. Snapshot atomic
write either succeeds completely or rolls back completely.

---

### Commit 4.1 — Repository interfaces

**Message:** `feat(repositories): abstract repository interfaces`

**Purpose:** The abstract interface definitions from REPOSITORY_ARCHITECTURE.md
Part 5. These are what the service layer depends on.

**Files created:**
```
backend/app/repositories/interfaces/__init__.py
backend/app/repositories/interfaces/i_user.py
backend/app/repositories/interfaces/i_property.py
backend/app/repositories/interfaces/i_deal.py
backend/app/repositories/interfaces/i_snapshot.py
backend/app/repositories/interfaces/i_configuration.py
backend/app/repositories/interfaces/i_investor_profile.py
backend/app/repositories/interfaces/i_audit.py
```

All interfaces use `Protocol` (typing.Protocol) so implementations are
verified structurally without inheritance. Each interface method is async.

**Dependencies:** Commits 1.5, 2.1

---

### Commit 4.2 — Pagination types

**Message:** `feat(repositories): PageRequest and Page types`

**Purpose:** The cursor-based pagination types used across all list operations.

**Files created:**
```
backend/app/repositories/pagination.py
```

```python
@dataclass(frozen=True)
class PageRequest:
    limit: int = 20
    cursor: str | None = None
    
    def __post_init__(self):
        if not (1 <= self.limit <= 100):
            raise ValueError("limit must be between 1 and 100")

@dataclass(frozen=True)
class Page(Generic[T]):
    items: list[T]
    next_cursor: str | None
    total_count: int
```

**Cursor encoding:** base64 of JSON `{"created_at": "<iso>", "id": "<uuid>"}`.

**Dependencies:** Commit 4.1

---

### Commit 4.3 — Configuration repository

**Message:** `feat(repositories): configuration repository implementation`

**Purpose:** The configuration repository is implemented first because all
other services depend on it and it is read-only (simpler to test).

**Files created:**
```
backend/app/repositories/configuration_repository.py
backend/tests/integration/repositories/__init__.py
backend/tests/integration/repositories/conftest.py
backend/tests/integration/repositories/test_configuration_repository.py
```

**Mapping:** `ConfigurationRepository._to_sdlt_domain()` converts
`SDLTVersionORM + [SDLTBandORM]` → `SDLTConfiguration` domain entity.
All `Decimal` columns are received as `Decimal` from asyncpg (verified).

**Tests:**
- `find_active_sdlt_config(date(2025, 6, 1))` returns the 2025-04-01 seed record
- `find_active_sdlt_config(date(2024, 12, 31))` raises `ConfigurationNotFoundError`
  (no config before 2025-04-01)
- `find_sdlt_config_by_id(known_uuid)` returns correct record
- `find_sdlt_config_by_id(unknown_uuid)` raises `ConfigurationNotFoundError`
- `find_active_assumption_config` returns values matching seed data exactly

**Dependencies:** Commits 3.4, 4.1

---

### Commit 4.4 — User and InvestorProfile repositories

**Message:** `feat(repositories): user and investor profile repositories`

**Files created:**
```
backend/app/repositories/user_repository.py
backend/app/repositories/investor_profile_repository.py
backend/tests/integration/repositories/test_user_repository.py
backend/tests/integration/repositories/test_investor_profile_repository.py
```

**Tests:**
- `save()` then `find_by_supabase_auth_id()` returns the saved user
- `save()` twice with same supabase_auth_id: idempotent (second save is no-op)
- `find_by_id_for_user()` returns None for wrong user_id
- `find_default_for_user()` returns profile with `is_default = True`

**Dependencies:** Commit 4.1

---

### Commit 4.5 — Property repository

**Message:** `feat(repositories): property repository implementation`

**Files created:**
```
backend/app/repositories/property_repository.py
backend/tests/integration/repositories/test_property_repository.py
```

**Tests:**
- Ownership filtering: `find_by_id_for_user` returns None for correct ID
  but wrong user
- Tenure immutability: update() does not modify tenure column
- Archived property still returned by `find_by_id_for_user`

**Dependencies:** Commit 4.4

---

### Commit 4.6 — Deal repository

**Message:** `feat(repositories): deal repository implementation`

**Files created:**
```
backend/app/repositories/deal_repository.py
backend/tests/integration/repositories/test_deal_repository.py
```

**Tests:**
- `find_by_id_for_user` returns None for both "not found" and "wrong user"
- `find_all_for_user` pagination with cursor
- `update()` persists working_inputs changes
- `update()` does not modify user_id or property_id

**Dependencies:** Commit 4.5

---

### Commit 4.7 — Audit repository

**Message:** `feat(repositories): audit repository — append-only implementation`

**Files created:**
```
backend/app/repositories/audit_repository.py
backend/tests/integration/repositories/test_audit_repository.py
```

**Tests:**
- `save()` inserts audit event
- No update or delete methods exist on the interface
- `find_history_for_deal` returns in triggered_at DESC order

**Dependencies:** Commit 4.1

---

### Commit 4.8 — Snapshot repository

**Message:** `feat(repositories): snapshot repository with atomic save`

**Purpose:** The most important repository. The `save()` method orchestrates
6 INSERTs + 1 UPDATE atomically. The mapping from `EngineResult` +
`EngineInput` → all snapshot sub-table rows is the most complex mapping
in the codebase.

**Files created:**
```
backend/app/repositories/snapshot_repository.py
backend/tests/integration/repositories/test_snapshot_repository.py
backend/tests/integration/snapshots/__init__.py
backend/tests/integration/snapshots/test_snapshot_completeness.py
backend/tests/integration/snapshots/test_snapshot_immutability_structure.py
backend/tests/integration/snapshots/test_snapshot_comparison.py
```

**Repository implementation key points:**
- `save()` uses `async with session.begin()` to wrap all 6 INSERTs
- SDLT band breakdown serialised to JSONB as `[{"band_lower": "0.00", ...}]`
  (all numbers as strings — see DATABASE_SCHEMA_DESIGN.md Part 3.3)
- `find_by_id()` runs 6 separate SELECT queries (not JOINs) per
  REPOSITORY_ARCHITECTURE.md Part 7.1
- `find_by_id_outputs_only()` runs 3 queries (root + outputs + flags/warnings)
- `mark_superseded()` uses the column-level UPDATE grant only

**Tests:**
- Atomic save: if any sub-table INSERT fails, no records are written
- Full roundtrip: save an E-01 snapshot, load it, assert all fields match
- `find_by_id_outputs_only` does NOT load intermediates
- `mark_superseded()` sets both `is_superseded` and `superseded_at`
- No update methods exist for any field other than supersession

**Dependencies:** Commits 4.6, 4.7

---

**Phase 4 Exit Criteria:**
- [ ] All repository integration tests pass against test DB
- [ ] Snapshot atomic write verified (partial write test)
- [ ] Decimal values pass through ORM without precision loss
- [ ] `find_by_id_for_user` verified to return None for both failure modes
- [ ] Configuration repository loads seed data correctly

---

---

## PHASE 5 — Application Services
**Goal:** All application services implemented. The calculation pipeline
works end-to-end in Python (no HTTP yet). ConfigurationService loads from DB,
CalculationService runs engine and persists snapshot.
**Duration:** 3–4 days
**Risks:** Default resolution logic, atomic transaction coordination,
audit write isolation on failure path.
**Exit criteria:** End-to-end calculation pipeline test passes using
real DB and real engine.

---

### Commit 5.1 — ConfigurationService

**Message:** `feat(services): configuration service — load and translate config`

**Purpose:** Loads active configuration from the database and translates it
into `EngineConfig` + `ConfigVersionRefs`.

**Files created:**
```
backend/app/services/__init__.py
backend/app/services/configuration_service.py
backend/tests/integration/test_configuration_service.py
```

**Key methods:**
- `load_for_calculation(calculation_date)` → `ConfigBundle`
- `load_specific_versions(version_refs)` → `ConfigBundle`
- `resolve_defaults(raw_inputs, assumption_config, ownership_structure)` →
  `(ResolvedInputs, InputSourceMap)`

**Tests:**
- `load_for_calculation(today)` returns all three configs from seed data
- `EngineConfig` has no UUIDs or metadata fields
- `ConfigVersionRefs` has all three version IDs
- `resolve_defaults` with all inputs present → all USER_OVERRIDE
- `resolve_defaults` with no optionals → all CONFIG_DEFAULT

**Dependencies:** Commits 4.3, 2.1

---

### Commit 5.2 — AuditService

**Message:** `feat(services): audit service with two write paths`

**Purpose:** `write_success()` (inside snapshot transaction) and
`write_failure()` (fresh session, exception-swallowing).

**Files created:**
```
backend/app/services/audit_service.py
backend/tests/integration/test_audit_service.py
```

**Tests:**
- `write_failure()` does not raise even if DB is unavailable (mocked)
- `write_failure()` increments the failure counter in structured log
- `write_success()` audit record has correct outcome=SUCCESS

**Dependencies:** Commit 4.7

---

### Commit 5.3 — UserService and PropertyService

**Message:** `feat(services): user service and property service`

**Files created:**
```
backend/app/services/user_service.py
backend/app/services/property_service.py
backend/tests/integration/test_user_service.py
backend/tests/integration/test_property_service.py
```

**UserService key behaviour:**
- `get_or_create_user()` is idempotent
- Second call with same supabase_auth_id returns existing user

**PropertyService key behaviour:**
- Validates leasehold consistency (lease_details required for LEASEHOLD)
- Raises `NotFoundError` for non-owned property access

**Dependencies:** Commits 4.4, 4.5, 1.2

---

### Commit 5.4 — DealService

**Message:** `feat(services): deal service with status transitions`

**Files created:**
```
backend/app/services/deal_service.py
backend/tests/integration/test_deal_service.py
```

**Tests:**
- Create deal against owned property: succeeds
- Create deal against non-owned property: raises NotFoundError
- Update working_inputs on ARCHIVED deal: raises DomainError
- `archive()` on ARCHIVED deal: raises DomainError
- DRAFT → ANALYSED transition on first snapshot creation

**Dependencies:** Commits 4.6, 5.3

---

### Commit 5.5 — SnapshotService

**Message:** `feat(services): snapshot service — persist and read snapshots`

**Files created:**
```
backend/app/services/snapshot_service.py
backend/tests/integration/test_snapshot_service.py
```

**Key method:** `save_snapshot_and_update_deal()` — calls
`SnapshotRepository.save()` and `AuditRepository.save(audit_event)` in the
same transaction. Deal status transitions to ANALYSED. Returns void.

**Tests:**
- Full save + retrieve roundtrip for an E-01 snapshot
- Snapshot access via non-owner deal: raises NotFoundError

**Dependencies:** Commits 4.8, 5.2

---

### Commit 5.6 — CalculationService

**Message:** `feat(services): calculation service — end-to-end calculation pipeline`

**Purpose:** The most important service. Assembles all prior components
into the full calculation flow.

**Files created:**
```
backend/app/services/calculation_service.py
backend/tests/integration/test_calculation_service.py
```

**Integration test — the first true end-to-end test:**
```python
async def test_full_calculation_pipeline(db_session, seed_data):
    # 1. Create user
    user = await user_service.get_or_create_user(...)
    # 2. Create property
    property = await property_service.create_property(user.id, ...)
    # 3. Create deal
    deal = await deal_service.create_deal(user.id, property.id, ...)
    # 4. Run calculation (E-01 inputs)
    result = await calculation_service.run_calculation(
        user_id=user.id, deal_id=deal.id, raw_inputs=E01_INPUTS, ...
    )
    # 5. Assert success
    assert isinstance(result, CalculationSuccess)
    # 6. Assert snapshot persisted
    snapshot = await snapshot_service.get_display_summary(result.snapshot_id)
    assert snapshot.outputs.annual_cash_flow_gbp == Decimal("-331.90")
    # 7. Assert deal status updated
    updated_deal = await deal_service.get_deal(user.id, deal.id)
    assert updated_deal.status == DealStatus.ANALYSED
```

**Tests:**
- Successful calculation matches E-01 outputs exactly
- Validation failure: returns `CalculationValidationFailure` with error codes
- Ownership failure: raises `NotFoundError`
- Calculation on ARCHIVED deal: raises `DomainError`

**Dependencies:** Commits 5.1, 5.5, 2.8

---

**Phase 5 Exit Criteria:**
- [ ] End-to-end calculation pipeline integration test passes
- [ ] E-01 outputs correct through the full service → engine → DB stack
- [ ] Validation failure path writes audit record and returns structured errors
- [ ] Audit write failure is swallowed and logged (not propagated)
- [ ] `make test` runs all tests (unit + integration) in under 60 seconds

---

---

## PHASE 6 — FastAPI HTTP Layer
**Goal:** All Phase 1 API routes implemented and tested. Supabase JWT
authentication. The vertical slice is accessible via HTTP.
**Duration:** 2–3 days
**Risks:** Async session dependency injection, Supabase JWT verification,
Pydantic v2 DTO mapping.
**Exit criteria:** Full HTTP integration tests pass. `/api/v1/calculations/`
returns a snapshot summary.

---

### Commit 6.1 — Authentication dependency

**Message:** `feat(api): Supabase JWT verification dependency`

**Purpose:** FastAPI dependency that verifies the JWT and resolves the
platform user.

**Files created:**
```
backend/app/api/dependencies.py
backend/tests/api/conftest.py        (TestClient fixtures, mock auth)
backend/tests/api/test_auth.py
```

**Dependencies.py key function:**
```python
async def get_current_user(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
    user_service: UserService = Depends(get_user_service)
) -> User:
    # Verify JWT using python-jose + Supabase JWKS
    # Extract sub claim → supabase_auth_id
    # UserService.get_or_create_user(supabase_auth_id, email)
    # Return platform User entity
```

**Test auth fixture:** A pytest fixture that returns a mock `User` entity,
bypassing real JWT verification. All API tests use this fixture.

**Dependencies:** Commit 5.3

---

### Commit 6.2 — Global error handlers and DTO schemas

**Message:** `feat(api): global error handlers and Pydantic v2 DTO schemas`

**Purpose:** Map domain errors to HTTP responses. Define all request/response
Pydantic models.

**Files created:**
```
backend/app/api/error_handlers.py
backend/app/api/v1/schemas/__init__.py
backend/app/api/v1/schemas/common.py
backend/app/api/v1/schemas/property.py
backend/app/api/v1/schemas/deal.py
backend/app/api/v1/schemas/calculation.py
backend/app/api/v1/schemas/snapshot.py
```

**Error handler mappings:**
```python
NotFoundError → 404
DomainError → 422
CalculationValidationFailure → 422 with field_errors list
CalculationError → 500
UnauthorisedAdminError → 403
ConfigurationNotFoundError → 500
Exception (catch-all) → 500 with generic message
```

**Pydantic DTO structure (example — SnapshotSummaryResponse):**
All monetary fields serialised as strings in decimal format to avoid
JSON float precision loss. e.g. `"annual_cash_flow_gbp": "-331.90"`.

**Dependencies:** Commit 1.2

---

### Commit 6.3 — Property and Deal routes

**Message:** `feat(api): property and deal CRUD routes`

**Files created:**
```
backend/app/api/v1/routes/properties.py
backend/app/api/v1/routes/deals.py
backend/tests/api/test_properties.py
backend/tests/api/test_deals.py
```

**Routes:**
```
POST   /api/v1/properties/              → 201 PropertyResponse
GET    /api/v1/properties/              → 200 Page[PropertyResponse]
GET    /api/v1/properties/{id}/         → 200 PropertyResponse
PATCH  /api/v1/properties/{id}/         → 200 PropertyResponse
DELETE /api/v1/properties/{id}/archive  → 200 PropertyResponse

POST   /api/v1/deals/                   → 201 DealResponse
GET    /api/v1/deals/                   → 200 Page[DealSummaryResponse]
GET    /api/v1/deals/{id}/              → 200 DealResponse
PATCH  /api/v1/deals/{id}/inputs        → 200 DealResponse
POST   /api/v1/deals/{id}/archive       → 200 DealResponse
```

**Tests:** TestClient tests with mocked auth. Verify 404 for non-owned
resources (not 403). Verify 422 for invalid state transitions.

**Dependencies:** Commits 6.1, 6.2

---

### Commit 6.4 — Calculation routes

**Message:** `feat(api): calculation routes — the core product endpoint`

**Files created:**
```
backend/app/api/v1/routes/calculations.py
backend/tests/api/test_calculations.py
```

**Routes:**
```
POST /api/v1/calculations/                     → 201 CalculationSuccessResponse
POST /api/v1/calculations/recalculate          → 201 CalculationSuccessResponse
POST /api/v1/calculations/reproduce-original   → 201 CalculationSuccessResponse
```

**CalculationSuccessResponse:**
```json
{
  "snapshot_id": "uuid",
  "deal_status": "ANALYSED",
  "outputs": { ... },
  "risk_flags": [ ... ],
  "validation_warnings": [ ... ]
}
```

**Tests:**
- E-01 inputs through HTTP returns correct `annual_cash_flow_gbp: "-331.90"`
- Validation failure returns 422 with structured `field_errors`
- Calculation on non-owned deal returns 404

**Dependencies:** Commits 5.6, 6.2

---

### Commit 6.5 — Snapshot routes

**Message:** `feat(api): snapshot read routes`

**Files created:**
```
backend/app/api/v1/routes/snapshots.py
backend/tests/api/test_snapshots.py
```

**Routes:**
```
GET /api/v1/snapshots/{snapshot_id}/          → 200 SnapshotDisplayResponse
GET /api/v1/snapshots/{snapshot_id}/full/     → 200 SnapshotFullResponse
GET /api/v1/snapshots/?deal_id={id}           → 200 List[SnapshotHistoryEntry]
```

**SnapshotDisplayResponse** includes outputs + risk_flags + validation_warnings.
Does not include intermediates.

**SnapshotFullResponse** includes intermediates (for audit/explainability).

**Tests:**
- Snapshot for non-owned deal returns 404
- Full snapshot includes sdlt_band_breakdown as ordered array
- History list ordered by calculated_at DESC

**Dependencies:** Commits 6.3, 6.4

---

### Commit 6.6 — Correlation ID middleware

**Message:** `feat(api): correlation ID middleware and structured request logging`

**Purpose:** Request-scoped correlation IDs per OBSERVABILITY_ARCHITECTURE.md
Part 4. Every log entry within a request carries the correlation_id.

**Files created:**
```
backend/app/api/middleware.py
```

**Middleware:**
- Generates `req_<uuid4>` on each request (or uses `X-Correlation-ID` header)
- Stores in `contextvars.ContextVar`
- Adds `X-Correlation-ID` to response headers
- Logs `api.request.received` and `api.request.completed` events

**Dependencies:** Commit 6.5

---

**Phase 6 Exit Criteria:**
- [ ] Full HTTP roundtrip: POST /calculations/ → GET /snapshots/{id} works
- [ ] E-01 inputs through HTTP return `-331.90` cash flow
- [ ] Non-owned resource access returns 404 (not 403)
- [ ] `X-Correlation-ID` header present on all responses
- [ ] All API tests pass with mocked auth
- [ ] `make test` completes in under 90 seconds

---

---

## PHASE 7 — Frontend Vertical Slice
**Goal:** Minimal working frontend: login → create property → create deal →
enter inputs → run calculation → view snapshot. No polish. Working flow only.
**Duration:** 3–5 days
**Risks:** Next.js App Router server/client component boundary, Supabase Auth
client integration, TypeScript API client typing.
**Exit criteria:** Full user journey works in a browser. Snapshot summary
displays correct numbers from Phase 2 engine.

---

### Commit 7.1 — Next.js project initialisation

**Message:** `feat(frontend): Next.js 15 project with TypeScript and Tailwind`

**Files created:**
```
frontend/package.json
frontend/tsconfig.json
frontend/tailwind.config.ts
frontend/next.config.ts
frontend/app/layout.tsx
frontend/app/page.tsx
```

**Key packages:**
```json
{
  "@supabase/supabase-js": "^2.46",
  "@supabase/ssr": "^0.5",
  "next": "^15.0",
  "react": "^19.0",
  "typescript": "^5.6",
  "tailwindcss": "^4.0"
}
```

**Why:** Next.js 15 with App Router is the architecture standard. `@supabase/ssr`
handles server-side auth correctly with the App Router.

**Dependencies:** Commit 0.1

---

### Commit 7.2 — Supabase Auth and API client foundation

**Message:** `feat(frontend): Supabase auth client and typed API client base`

**Files created:**
```
frontend/lib/supabase/client.ts
frontend/lib/supabase/server.ts
frontend/lib/api/client.ts
frontend/lib/types/snapshot.ts
frontend/lib/types/deal.ts
frontend/lib/types/property.ts
frontend/lib/types/calculation.ts
```

**client.ts API client:**
```typescript
// Base fetch wrapper with JWT injection
async function apiRequest<T>(
  path: string,
  options?: RequestInit
): Promise<T> {
  const session = await supabase.auth.getSession();
  const token = session.data.session?.access_token;
  
  const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}${path}`, {
    ...options,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...options?.headers,
    },
  });
  
  if (!response.ok) {
    throw new ApiError(response.status, await response.json());
  }
  return response.json();
}
```

**Dependencies:** Commit 7.1

---

### Commit 7.3 — Auth flow: login page and auth guard

**Message:** `feat(frontend): login page and authenticated app shell`

**Files created:**
```
frontend/app/(auth)/login/page.tsx
frontend/app/(app)/layout.tsx         ← auth guard: redirect to login if no session
frontend/app/(app)/dashboard/page.tsx  ← stub: "Welcome to PropIQ"
frontend/components/ui/Button.tsx
frontend/components/ui/Input.tsx
```

**Auth guard logic:** Server component reads session via `@supabase/ssr`.
If no valid session, redirects to `/login`.

**Dependencies:** Commit 7.2

---

### Commit 7.4 — Property creation flow

**Message:** `feat(frontend): property creation form and list`

**Files created:**
```
frontend/lib/api/properties.ts
frontend/app/(app)/properties/page.tsx          ← property list
frontend/app/(app)/properties/new/page.tsx      ← create property form
frontend/components/ui/FormField.tsx
frontend/components/ui/Select.tsx
```

**Simple property form:** address line 1, city, postcode, property type,
tenure (and lease years if leasehold). Submits to `POST /api/v1/properties/`.
On success, redirects to the deals page for the new property.

**Dependencies:** Commit 7.3

---

### Commit 7.5 — Deal workspace and input form

**Message:** `feat(frontend): deal creation and input form`

**Files created:**
```
frontend/lib/api/deals.ts
frontend/app/(app)/properties/[propertyId]/deals/page.tsx
frontend/app/(app)/properties/[propertyId]/deals/new/page.tsx
frontend/app/(app)/properties/[propertyId]/deals/[dealId]/page.tsx
frontend/components/deal/DealInputForm.tsx
frontend/components/deal/DealStatusBadge.tsx
```

**DealInputForm:** All required and optional calculation inputs. DRAFT deal
auto-saves working inputs on blur (PATCH /api/v1/deals/{id}/inputs).
"Analyse Deal" button calls POST /api/v1/calculations/.

**Dependencies:** Commit 7.4

---

### Commit 7.6 — Snapshot summary display

**Message:** `feat(frontend): snapshot summary — the first analysis output`

**Purpose:** The most important UI component. Renders the calculation result.

**Files created:**
```
frontend/lib/api/snapshots.ts
frontend/lib/api/calculations.ts
frontend/app/(app)/properties/[propertyId]/deals/[dealId]/analysis/page.tsx
frontend/components/analysis/SnapshotSummary.tsx
frontend/components/analysis/CashFlowWaterfall.tsx
frontend/components/analysis/AcquisitionCostBreakdown.tsx
frontend/components/analysis/SDLTBreakdown.tsx
frontend/components/analysis/YieldMetrics.tsx
frontend/components/analysis/RiskFlagList.tsx
```

**CashFlowWaterfall** renders the line-by-line annual cash flow breakdown
exactly as defined in CALCULATION_SPEC.md Section 7.3.

**RiskFlagList** displays flags sorted HIGH → MEDIUM → INFO, each with
severity colour coding and the stored message text.

**Why render from snapshot:** The page always loads from `GET /api/v1/snapshots/{id}`.
It never derives numbers from working inputs. Snapshot-first rendering is the
trust architecture (SERVICE_ARCHITECTURE.md Part 10).

**Dependencies:** Commits 7.5

---

**Phase 7 Exit Criteria:**
- [ ] Complete user journey works in Chrome/Firefox
- [ ] E-01 inputs display correct `-£27.66/month` cash flow
- [ ] SDLT breakdown shows correct band-by-band calculation
- [ ] Risk flags displayed with correct severity and message
- [ ] Login/logout works
- [ ] TypeScript compiles with zero errors
- [ ] No calculation logic in any frontend component

---

---

## PHASE 8 — First Deployment to Staging
**Goal:** The vertical slice is deployed to Railway staging with a
real PostgreSQL database. A second person (or you from a different device)
can run the full journey.
**Duration:** 1–2 days
**Risks:** Railway environment variables, production asyncpg connection pooling,
CORS configuration.
**Exit criteria:** Staging URL accessible. E-01 calculation produces correct
result in production environment.

---

### Commit 8.1 — Docker configuration for backend

**Message:** `infra: backend Dockerfile for Railway deployment`

**Files created:**
```
backend/Dockerfile
```

```dockerfile
FROM python:3.13-slim

WORKDIR /app
COPY pyproject.toml poetry.lock ./
RUN pip install poetry && poetry install --no-dev

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY scripts/ ./scripts/

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**Dependencies:** Commit 6.6

---

### Commit 8.2 — Railway configuration

**Message:** `infra: railway.toml for staging deployment`

**Files created:**
```
infrastructure/railway.toml
```

**Defines:**
- Build: `docker` builder using `backend/Dockerfile`
- Start command: `alembic upgrade head && python scripts/seed_configuration.py && uvicorn app.main:app`
- Environment variable references (DATABASE_URL from Railway PostgreSQL service)
- Health check endpoint: `/api/v1/health`

**Dependencies:** Commit 8.1

---

### Commit 8.3 — CORS and production settings

**Message:** `feat(api): CORS configuration for production`

**Files modified:**
```
backend/app/main.py
backend/app/core/config.py
```

**Adds:**
- `ALLOWED_ORIGINS` setting (comma-separated list)
- `CORSMiddleware` in `main.py` using `ALLOWED_ORIGINS`
- `ENVIRONMENT` guard: stricter CORS in production

**Dependencies:** Commit 8.1

---

### Commit 8.4 — Frontend environment and production build

**Message:** `feat(frontend): production environment configuration`

**Files created/modified:**
```
frontend/.env.example
frontend/.env.local           (gitignored — local only)
```

**Environment variables:**
```
NEXT_PUBLIC_API_URL=https://propiq-staging.up.railway.app
NEXT_PUBLIC_SUPABASE_URL=...
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
```

**Dependencies:** Commit 7.6

---

**Phase 8 Exit Criteria:**
- [ ] `railway up` deploys both backend and frontend
- [ ] Staging URL loads the login page
- [ ] Full vertical slice works end-to-end in staging
- [ ] Database migrations run automatically on deployment
- [ ] Configuration seed data present in staging database
- [ ] CORS allows requests from the frontend domain
- [ ] Health endpoint returns 200

---

---

# Post-Phase 8 Roadmap

After the vertical slice is deployed to staging, subsequent work follows
the same commit-per-concern discipline. The next priorities in order:

**Immediate hardening (before any marketing or user onboarding):**
1. Rate limiting on calculation endpoints
2. Production error monitoring (Sentry or Axiom)
3. Database backups configured on Railway
4. HTTPS certificate (automatic on Railway)
5. Investor profile creation and management UI
6. Snapshot history list UI

**Phase 9 — Remaining Phase 1 features:**
- Admin configuration management routes and UI
- Recalculation with current assumptions
- Reproduce original calculation (Variant B)
- Deal archival UI
- Property archival UI
- Snapshot comparison view

**Phase 10 — Operational readiness:**
- Structured log shipping to Axiom/Datadog
- Alerting on TIER-1 metrics (engine errors, audit failures)
- Load testing against staging
- GDPR privacy policy and terms of service
- User account deletion flow

These phases use the same commit discipline defined in this document.
Each commit has a single clear purpose and leaves the codebase in a
deployable state.

---

---

# Risk Register

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Section 24 arithmetic wrong | Low (regression tested) | High | E-01/E-02/E-10 pass before any DB work |
| SDLT band boundary off-by-one | Low (boundary tested) | High | 12 boundary tests in Phase 2 |
| Decimal precision loss in ORM | Medium | High | PREC-06 test in Phase 2; verified in integration test Phase 4 |
| Snapshot partial write in production | Very Low (tested) | Critical | Atomic write test in Phase 4; DB privilege model in Phase 3 |
| Railway/Supabase integration issues | Medium | Medium | Phase 8 is explicitly for deployment; vertical slice simple |
| asyncpg connection pool exhaustion | Low at Phase 1 scale | Medium | Default pool size 5; monitored via metrics |
| Test DB state contamination | Low (separate DB) | Medium | docker-compose.test.yml uses port 5433 |

---

# Definition of Done (per commit)

A commit is complete when:

1. `make test` passes with the new code included
2. `make typecheck` passes (mypy zero errors)
3. `make lint` passes (ruff zero errors)
4. The commit message follows the format: `type(scope): description`
5. No TODO comments added (if a deferral is needed, create a documented issue)
6. No test expected values derived from the same formula being tested
7. The commit does not introduce any new architecture decisions
   (changes to behaviour require an ADR update first)
