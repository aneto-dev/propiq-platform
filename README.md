# PropIQ

Production-grade UK property investment analysis platform.

PropIQ helps investors evaluate deals using realistic underwriting,
transparent assumptions, and historically reproducible calculations.

---

## Architecture

Architecture documents are in `docs/`. The architecture is tagged
`architecture-v1` and is frozen. Implementation follows
`docs/IMPLEMENTATION_ROADMAP.md` commit-by-commit.

Key design principles:
- **Trust first.** Calculations are deterministic, explainable, and
  immutable once saved.
- **Engine is core IP.** The underwriting engine is pure Python with
  no I/O dependencies. It is independently testable.
- **Explicit over implicit.** Every assumption is versioned and disclosed.

---

## Technology

| Layer       | Technology                        |
|-------------|-----------------------------------|
| Backend     | Python 3.12, FastAPI, SQLAlchemy 2 |
| Database    | PostgreSQL 16 + PostGIS            |
| Auth        | Supabase Auth                      |
| Frontend    | Next.js 15, TypeScript, Tailwind   |
| Hosting     | Railway                            |

---

## Local Development

### Prerequisites

- Docker and Docker Compose
- Python 3.12
- Node.js 20+

### Setup

```bash
# 1. Clone and enter the repository
git clone <repo>
cd propiq

# 2. Copy environment file
cp .env.example .env
# Fill in Supabase values in .env

# 3. Start the database
make dev-db

# 4. Install backend dependencies
cd backend && pip install poetry && poetry install

# 5. Run migrations
make migrate

# 6. Seed configuration data
make seed

# 7. Start the backend
make dev-backend

# 8. In another terminal, start the frontend
make dev-frontend
```

### Running Tests

```bash
make test
```

---

## Development Workflow

Every commit follows the rules in `docs/IMPLEMENTATION_ROADMAP.md`:

1. `make test` must pass
2. `make typecheck` must pass (mypy zero errors)
3. `make lint` must pass (ruff zero errors)
4. Commit message format: `type(scope): description`
5. No new architecture decisions without an ADR update

---

## Repository Structure

```
propiq/
├── backend/       FastAPI application, engine, repositories, services
├── frontend/      Next.js application
├── infrastructure/ Docker Compose, Railway config
├── scripts/       Seed scripts and utilities
└── docs/          Frozen architecture documents
```
