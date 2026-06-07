"""
API test fixtures — TestClient and mock authentication.

Provides:

  client — TestClient fixture that overrides get_current_user with a mock
           returning a pre-built User entity. All API tests use this fixture
           to bypass real JWT verification (Supabase JWKS is not available
           in the test environment).

  mock_user — the User entity injected by the mock auth dependency.

The override mechanism uses FastAPI's dependency_overrides dict, which
is the standard approach for replacing dependencies in tests without
modifying application code.

Architecture:
    AUTHORIZATION_MODEL.md §9.2 — auth as FastAPI dependency.
    IMPLEMENTATION_ROADMAP.md Commit 6.1 — test auth fixture.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_current_user
from app.domain.entities.user import User
from app.domain.enums import UserStatus
from app.main import create_app


@pytest.fixture(scope="session")
def mock_user() -> User:
    """
    A pre-built platform User entity returned by all mock-authenticated requests.

    The id and supabase_auth_id are stable across the session so that
    multiple test requests are treated as the same user.
    """
    return User(
        id=uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"),
        supabase_auth_id=uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
        email="test@propiq.test",
        display_name="Test User",
        status=UserStatus.ACTIVE,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )


@pytest.fixture
def client(mock_user: User) -> TestClient:
    """
    FastAPI TestClient with authentication overridden.

    get_current_user is replaced with a lambda that returns mock_user
    immediately, bypassing JWT verification and the database user lookup.
    All API tests that require an authenticated user use this fixture.

    Architecture: IMPLEMENTATION_ROADMAP.md Commit 6.1 — mock auth fixture.
    """
    app = create_app()
    app.dependency_overrides[get_current_user] = lambda: mock_user
    with TestClient(app) as test_client:
        yield test_client
