# ============================================================
# PropIQ — Makefile
#
# All targets defined here. Some are stubs that will be
# implemented in later commits.
# ============================================================

.PHONY: help dev-db dev-backend dev-frontend dev \
        test test-unit test-int \
        migrate seed \
        lint typecheck \
        clean

# ---- Help ---------------------------------------------------
help:
	@echo ""
	@echo "PropIQ development targets:"
	@echo ""
	@echo "  make dev-db          Start PostgreSQL (Docker)"
	@echo "  make dev-backend     Start FastAPI with auto-reload"
	@echo "  make dev-frontend    Start Next.js dev server"
	@echo ""
	@echo "  make test            Run full test suite"
	@echo "  make test-unit       Run unit tests only (no DB)"
	@echo "  make test-int        Run integration tests (requires test DB)"
	@echo ""
	@echo "  make migrate         Run Alembic migrations"
	@echo "  make seed            Insert v1.0 configuration seed data"
	@echo ""
	@echo "  make lint            ruff check backend/"
	@echo "  make typecheck       mypy backend/"
	@echo ""
	@echo "  make clean           Remove build artifacts"
	@echo ""

# ---- Database -----------------------------------------------
dev-db:
	docker compose -f infrastructure/docker-compose.yml up -d postgres pgadmin

dev-db-test:
	docker compose -f infrastructure/docker-compose.test.yml up -d postgres_test

dev-db-down:
	docker compose -f infrastructure/docker-compose.yml down
	docker compose -f infrastructure/docker-compose.test.yml down

# ---- Backend ------------------------------------------------
dev-backend:
	cd backend && poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# ---- Frontend -----------------------------------------------
dev-frontend:
	cd frontend && npm run dev

# ---- Convenience: start everything --------------------------
dev: dev-db
	@echo "Database started. Run 'make dev-backend' and 'make dev-frontend' in separate terminals."

# ---- Tests --------------------------------------------------
test: dev-db-test
	cd backend && poetry run pytest tests/ -v --tb=short

test-unit:
	cd backend && poetry run pytest tests/unit/ tests/regression/ tests/determinism/ -v --tb=short

test-int: dev-db-test
	cd backend && poetry run pytest tests/integration/ tests/api/ -v --tb=short

# ---- Database management ------------------------------------
migrate:
	cd backend && poetry run alembic upgrade head

migrate-down:
	cd backend && poetry run alembic downgrade -1

migrate-history:
	cd backend && poetry run alembic history

seed:
	cd backend && poetry run python scripts/seed_configuration.py

# ---- Code quality -------------------------------------------
lint:
	cd backend && poetry run ruff check app/ tests/

lint-fix:
	cd backend && poetry run ruff check --fix app/ tests/

typecheck:
	cd backend && poetry run mypy app/

format:
	cd backend && poetry run ruff format app/ tests/

# ---- Clean --------------------------------------------------
clean:
	find backend -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null; true
	find backend -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null; true
	find backend -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null; true
	find backend -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null; true
	find backend -name "*.pyc" -delete 2>/dev/null; true
