# ============================================================
# PropIQ — Makefile
# ============================================================

.PHONY: help \
        dev dev-db dev-db-test dev-db-down dev-backend dev-frontend \
        test test-unit test-int \
        migrate migrate-down migrate-history migrate-status \
        seed \
        lint lint-fix typecheck format \
        shell \
        clean

# ---- Help ---------------------------------------------------
help:
	@echo ""
	@echo "PropIQ development targets"
	@echo "=========================="
	@echo ""
	@echo "  make dev             Start postgres + FastAPI (foreground)"
	@echo "  make dev-db          Start PostgreSQL + pgAdmin (background)"
	@echo "  make dev-backend     Start FastAPI with auto-reload"
	@echo "  make dev-frontend    Start Next.js dev server"
	@echo ""
	@echo "  make test            Full suite (unit + integration)"
	@echo "  make test-unit       Unit tests — no database required"
	@echo "  make test-int        Integration tests — requires test DB"
	@echo ""
	@echo "  make migrate         Run all pending Alembic migrations"
	@echo "  make migrate-down    Roll back one migration"
	@echo "  make migrate-history Show full migration history"
	@echo "  make migrate-status  Show current migration state"
	@echo "  make seed            Insert v1.0 configuration seed data"
	@echo ""
	@echo "  make lint            ruff check (read-only)"
	@echo "  make lint-fix        ruff check --fix (auto-fix)"
	@echo "  make typecheck       mypy strict type check"
	@echo "  make format          ruff format"
	@echo ""
	@echo "  make shell           Python shell with app context"
	@echo "  make clean           Remove cache and build artefacts"
	@echo ""

# ============================================================
# Development servers
# ============================================================

# Start postgres, wait for healthy, then start FastAPI in foreground.
# Phase 0 exit criterion: make dev starts postgres and uvicorn together.
dev:
	@echo "Starting PostgreSQL..."
	docker compose up -d postgres
	@echo "Waiting for PostgreSQL..."
	@until docker exec propiq_postgres pg_isready -U propiq -d propiq >/dev/null 2>&1; do \
		printf '.'; sleep 1; \
	done
	@echo " ready."
	@echo "Starting FastAPI on http://localhost:8000 ..."
	cd backend && poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start database services in the background only.
dev-db:
	docker compose up -d postgres pgadmin
	@echo "PostgreSQL : localhost:5432"
	@echo "pgAdmin    : http://localhost:5050  (admin@propiq.local / propiq)"

# Start the isolated test database.
dev-db-test:
	docker compose -f docker-compose.test.yml up -d postgres_test

# Stop all database containers.
dev-db-down:
	docker compose down
	docker compose -f docker-compose.test.yml down

# Start FastAPI only (database must already be running).
dev-backend:
	cd backend && poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Start Next.js dev server (Phase 7+).
dev-frontend:
	cd frontend && npm run dev

# ============================================================
# Testing
# ============================================================

# Full suite: all five test layers. TEST_STRATEGY.md Part 1.
test: dev-db-test
	cd backend && \
		TEST_DATABASE_URL="postgresql+asyncpg://propiq:propiq@localhost:5433/propiq_test" \
		poetry run pytest tests/ -v --tb=short

# Unit tests only — no database, no Docker required.
# Engine formulas, validation rules, risk flags, precision tests.
# Should complete in under 10 seconds.
test-unit:
	cd backend && poetry run pytest \
		tests/unit/ \
		tests/regression/ \
		tests/determinism/ \
		-v --tb=short

# Integration tests — requires test database.
test-int: dev-db-test
	cd backend && \
		TEST_DATABASE_URL="postgresql+asyncpg://propiq:propiq@localhost:5433/propiq_test" \
		poetry run pytest tests/integration/ tests/api/ -v --tb=short

# ============================================================
# Database management
# ============================================================

# Apply all pending migrations.
migrate:
	cd backend && poetry run alembic upgrade head

# Roll back one migration (development only).
migrate-down:
	cd backend && poetry run alembic downgrade -1

# Show full migration history.
migrate-history:
	cd backend && poetry run alembic history --verbose

# Show current database migration state.
migrate-status:
	cd backend && poetry run alembic current

# Insert v1.0 configuration seed data. Idempotent.
seed:
	cd backend && poetry run python scripts/seed_configuration.py

# ============================================================
# Code quality — all must pass before every commit
# ============================================================

lint:
	cd backend && poetry run ruff check app/ tests/

lint-fix:
	cd backend && poetry run ruff check --fix app/ tests/

typecheck:
	cd backend && poetry run mypy app/

format:
	cd backend && poetry run ruff format app/ tests/

# ============================================================
# Utilities
# ============================================================

# Python shell with app context loaded.
# Requires ipython: poetry add --group dev ipython
shell:
	cd backend && poetry run python -c "\
from app.core.config import get_settings; \
from app.core.logging import configure_logging; \
configure_logging(); \
s = get_settings(); \
print(f'PropIQ shell — {s.environment} / {s.app_version}'); \
import IPython; IPython.start_ipython(argv=[])"

# ============================================================
# Clean
# ============================================================

clean:
	@echo "Removing cache artefacts..."
	find backend -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; true
	find backend -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null; true
	find backend -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null; true
	find backend -type d -name ".ruff_cache"  -exec rm -rf {} + 2>/dev/null; true
	find backend -name "*.pyc"                -delete       2>/dev/null; true
	@echo "Done."
