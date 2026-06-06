"""
Integration test fixtures — shared across all tests/integration sub-packages.

Provides:
  async_engine      — function-scoped AsyncEngine with NullPool. A fresh engine
                      is created and disposed for every test. NullPool ensures
                      no cross-test connection sharing, which prevents asyncpg
                      cross-event-loop errors under pytest-asyncio 0.24.
  async_session     — function-scoped AsyncSession derived from async_engine.
                      Tests may call session.commit() freely; isolation is
                      achieved through unique UUIDs/emails per test.
  sdlt_version_id   — function-scoped UUID of the seeded SDLT version record.
                      Read from the live test DB on each test that requests it.

Design note — NullPool:
  SQLAlchemy's NullPool disables connection pooling entirely. Each engine.connect()
  call creates a new asyncpg connection; closing it destroys it. This removes all
  pool state that would otherwise survive across event loop boundaries and trigger
  "Future attached to a different loop" errors when pytest-asyncio creates a new
  event loop per test function.

Architecture:
    REPOSITORY_ARCHITECTURE.md RI-07, RI-08 — repositories receive an
    AsyncSession; they do not open or close sessions.
    IMPLEMENTATION_ROADMAP.md Commit 4.3.
"""

from __future__ import annotations

import uuid

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

import app.db.models.audit  # noqa: F401
import app.db.models.configuration  # noqa: F401
import app.db.models.deal  # noqa: F401
import app.db.models.investor_profile  # noqa: F401
import app.db.models.property  # noqa: F401
import app.db.models.snapshot  # noqa: F401
import app.db.models.user  # noqa: F401
from app.core.config import get_settings


@pytest_asyncio.fixture
async def async_engine():
    engine = create_async_engine(
        get_settings().test_database_url,
        echo=False,
        poolclass=NullPool,
    )
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def async_session(async_engine) -> AsyncSession:
    factory = async_sessionmaker(async_engine, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def sdlt_version_id(async_session: AsyncSession) -> uuid.UUID:
    result = await async_session.execute(
        text("SELECT id FROM config_sdlt_versions LIMIT 1")
    )
    row = result.fetchone()
    assert row is not None, "SDLT version seed data missing — run seed_configuration.py"
    return uuid.UUID(str(row[0]))
