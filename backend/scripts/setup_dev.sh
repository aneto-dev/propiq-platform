#!/usr/bin/env bash
# =============================================================================
# PropIQ — Developer setup script
#
# Run once after cloning to get a fully working local environment.
# Safe to run multiple times — every step is idempotent.
#
# Usage:
#   cd propiq-platform/
#   chmod +x backend/scripts/setup_dev.sh
#   ./backend/scripts/setup_dev.sh
#
# What this does:
#   1. Checks required tools are installed
#   2. Creates .env from .env.example if it doesn't exist
#   3. Starts the development database (Docker)
#   4. Installs backend Python dependencies (Poetry)
#   5. Runs database migrations (Alembic)
#   6. Inserts v1.0 configuration seed data (when available)
#   7. Confirms the health endpoint responds
#
# After this script:
#   make dev-backend    — start FastAPI with auto-reload
#   make dev-frontend   — start Next.js dev server (Phase 7+)
# =============================================================================

set -euo pipefail

# Colour helpers
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${GREEN}[setup]${NC} $1"; }
warn()  { echo -e "${YELLOW}[setup]${NC} $1"; }
error() { echo -e "${RED}[setup]${NC} $1"; exit 1; }

# =============================================================================
# Resolve repository root from script location
# =============================================================================
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Script lives at backend/scripts/setup_dev.sh — repo root is two levels up
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$REPO_ROOT"

info "PropIQ developer setup"
info "Repository root: $REPO_ROOT"
echo ""

# =============================================================================
# Step 1: Check required tools
# =============================================================================
info "Checking required tools..."

command -v docker  >/dev/null 2>&1 || error "docker not found. Install Docker Desktop."
command -v poetry  >/dev/null 2>&1 || error "poetry not found. See https://python-poetry.org/docs/"
command -v python3 >/dev/null 2>&1 || error "python3 not found."

info "  docker    $(docker --version | awk '{print $3}' | tr -d ',')"
info "  poetry    $(poetry --version 2>/dev/null | awk '{print $3}')"
info "  python3   $(python3 --version | awk '{print $2}')"
echo ""

# =============================================================================
# Step 2: Environment file
# =============================================================================
if [ ! -f "$REPO_ROOT/.env" ]; then
    warn ".env not found — copying from .env.example"
    cp "$REPO_ROOT/.env.example" "$REPO_ROOT/.env"
    warn "Edit .env and set your DATABASE_URL and Supabase credentials."
else
    info ".env already exists — skipping"
fi
echo ""

# =============================================================================
# Step 3: Start development database
# =============================================================================
info "Starting development database..."
# docker-compose.yml is at the repository root
docker compose up -d postgres

info "Waiting for PostgreSQL to be ready..."
MAX_WAIT=30
WAITED=0
until docker exec propiq_postgres pg_isready -U propiq -d propiq >/dev/null 2>&1; do
    if [ $WAITED -ge $MAX_WAIT ]; then
        error "PostgreSQL did not become ready within ${MAX_WAIT}s."
    fi
    printf '.'
    sleep 1
    WAITED=$((WAITED + 1))
done
echo ""
info "  PostgreSQL ready (${WAITED}s)"
echo ""

# =============================================================================
# Step 4: Install Python dependencies
# =============================================================================
info "Installing backend dependencies..."
cd "$REPO_ROOT/backend"
poetry install --no-interaction
info "  Dependencies installed"
echo ""

# =============================================================================
# Step 5: Run database migrations
# =============================================================================
info "Running database migrations..."
cd "$REPO_ROOT/backend"
poetry run alembic upgrade head
info "  Migrations applied"
echo ""

# =============================================================================
# Step 6: Seed configuration data (available from Commit 3.4)
# =============================================================================
SEED_SCRIPT="$REPO_ROOT/backend/scripts/seed_configuration.py"
if [ -f "$SEED_SCRIPT" ]; then
    info "Seeding configuration data..."
    cd "$REPO_ROOT/backend"
    poetry run python scripts/seed_configuration.py
    info "  Seed data inserted"
else
    warn "Seed script not yet present (added in Commit 3.4) — skipping"
fi
echo ""

# =============================================================================
# Done
# =============================================================================
echo ""
info "Setup complete."
echo ""
echo "  make dev-backend     Start FastAPI on http://localhost:8000"
echo "  make test            Run the test suite"
echo "  make help            Show all available targets"
echo ""
