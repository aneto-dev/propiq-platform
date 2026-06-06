"""
UserService integration tests.

Roadmap-specified tests (IMPLEMENTATION_ROADMAP.md Commit 5.3):
  - get_or_create_user() is idempotent
  - Second call with same supabase_auth_id returns existing user

Architecture:
    APPLICATION_SERVICE_ARCHITECTURE.md Part 14.1.
    IMPLEMENTATION_ROADMAP.md Commit 5.3.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user_repository import UserRepository
from app.services.user_service import UserService


def _make_service(session: AsyncSession) -> UserService:
    return UserService(UserRepository(session))


class TestGetOrCreateUser:
    """get_or_create_user() is idempotent — IMPLEMENTATION_ROADMAP.md Commit 5.3."""

    async def test_creates_user_on_first_call(
        self, async_session: AsyncSession
    ) -> None:
        """First call with a new supabase_auth_id creates and returns a User."""
        svc = _make_service(async_session)
        auth_id = uuid.uuid4()
        email = f"new_{uuid.uuid4().hex[:8]}@example.com"

        user = await svc.get_or_create_user(auth_id, email)
        await async_session.commit()

        assert user.supabase_auth_id == auth_id
        assert user.email == email
        assert user.id is not None

    async def test_idempotent_returns_existing_user(
        self, async_session: AsyncSession
    ) -> None:
        """
        Second call with same supabase_auth_id returns the existing user.
        No duplicate record is created.
        IMPLEMENTATION_ROADMAP.md Commit 5.3 — UserService key behaviour.
        """
        svc = _make_service(async_session)
        auth_id = uuid.uuid4()
        email = f"idem_{uuid.uuid4().hex[:8]}@example.com"

        first = await svc.get_or_create_user(auth_id, email)
        await async_session.commit()

        second = await svc.get_or_create_user(auth_id, email)

        # Same identity — not a new record
        assert second.id == first.id
        assert second.supabase_auth_id == auth_id

    async def test_second_call_does_not_create_duplicate(
        self, async_session: AsyncSession
    ) -> None:
        """
        Only one record exists in the DB after two calls with the same auth_id.
        IMPLEMENTATION_ROADMAP.md Commit 5.3 — UserService key behaviour.
        """
        from sqlalchemy import text

        svc = _make_service(async_session)
        auth_id = uuid.uuid4()
        email = f"nodup_{uuid.uuid4().hex[:8]}@example.com"

        await svc.get_or_create_user(auth_id, email)
        await async_session.commit()
        await svc.get_or_create_user(auth_id, email)
        await async_session.commit()

        result = await async_session.execute(
            text(
                "SELECT COUNT(*) FROM users WHERE supabase_auth_id = :auth_id"
            ),
            {"auth_id": auth_id},
        )
        count = result.scalar_one()
        assert count == 1
