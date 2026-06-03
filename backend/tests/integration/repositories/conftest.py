"""
Shared fixtures for repository integration tests.

Provides:
  repo_db_setup  — session-scoped: reset test DB, run migrations, seed config
  async_session  — function-scoped: AsyncSession per test
  sdlt_version_id — function-scoped: UUID of the seeded SDLT version

Requires a running test database. Run via:
    make test-int

Architecture: REPOSITORY_ARCHITECTURE.md Part 13.
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.config import get_settings

_BACKEND_DIR = Path(__file__).parents[3]


def _test_url() -> str:
    return get_settings().test_database_url


async def _reset_schema(url: str) -> None:
    """Drop and recreate the public schema for a clean test slate."""
    engine = create_async_engine(url, isolation_level="AUTOCOMMIT")
    async with engine.connect() as conn:
        await conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO CURRENT_USER"))
        await conn.execute(text("GRANT ALL ON SCHEMA public TO PUBLIC"))
    await engine.dispose()


def _run_alembic(url: str) -> None:
    """Run alembic upgrade head against the test database."""
    env = {**os.environ, "DATABASE_URL": url}
    result = subprocess.run(
        ["poetry", "run", "alembic", "upgrade", "head"],
        cwd=_BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"alembic upgrade head failed:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


def _run_seed(url: str) -> None:
    """Seed v1.0 configuration data."""
    env = {**os.environ, "DATABASE_URL": url}
    result = subprocess.run(
        ["poetry", "run", "python", "scripts/seed_configuration.py"],
        cwd=_BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Seed script failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )


@pytest.fixture(scope="session", autouse=True)
def repo_db_setup() -> None:
    """
    Reset test DB, run all migrations, and seed configuration data.

    Session-scoped and autouse — runs once before all repository tests.
    Requires the test database to be running (make dev-db-test).
    """
    url = _test_url()
    asyncio.run(_reset_schema(url))
    _run_alembic(url)
    _run_seed(url)


@pytest.fixture
async def async_session() -> AsyncSession:
    """
    Provide a fresh AsyncSession per test.

    Function-scoped. Does not commit — tests that write should either
    commit explicitly or use a transaction rollback strategy.
    Config repository tests are read-only; no cleanup needed.
    """
    engine = create_async_engine(_test_url())
    async with AsyncSession(engine, expire_on_commit=False) as session:
        yield session  # type: ignore[misc]
    await engine.dispose()


@pytest.fixture
async def sdlt_version_id(async_session: AsyncSession) -> uuid.UUID:
    """
    Return the UUID of the seeded SDLT version (ENGLAND, 2025-04-01).
    Used by tests that call find_sdlt_config_by_id().
    """
    result = await async_session.execute(
        text(
            "SELECT id FROM config_sdlt_versions "
            "WHERE effective_from = '2025-04-01' "
            "AND property_country = 'ENGLAND'"
        )
    )
    row = result.fetchone()
    assert row is not None, "Seeded SDLT version not found — check seed script ran"
    return uuid.UUID(str(row[0]))
