"""
Integration tests for UserRepository.

Requires a running test database. Run via:
    make test-int

Architecture: REPOSITORY_ARCHITECTURE.md Part 5.4.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.user import User
from app.domain.enums import UserStatus
from app.repositories.user_repository import UserRepository


def _make_user(
    supabase_auth_id: uuid.UUID | None = None,
    email: str = "test@example.com",
    display_name: str | None = "Test User",
) -> User:
    return User(
        id=uuid.uuid4(),
        supabase_auth_id=supabase_auth_id or uuid.uuid4(),
        email=email,
        display_name=display_name,
        status=UserStatus.ACTIVE,
    )


class TestUserRepositorySave:
    async def test_save_then_find_by_supabase_auth_id(
        self, async_session: AsyncSession
    ) -> None:
        repo = UserRepository(async_session)
        user = _make_user()

        await repo.save(user)
        await async_session.commit()

        found = await repo.find_by_supabase_auth_id(user.supabase_auth_id)
        assert found is not None
        assert found.id == user.id
        assert found.email == user.email
        assert found.supabase_auth_id == user.supabase_auth_id

    async def test_save_twice_same_supabase_auth_id_is_idempotent(
        self, async_session: AsyncSession
    ) -> None:
        repo = UserRepository(async_session)
        auth_id = uuid.uuid4()
        user1 = _make_user(supabase_auth_id=auth_id, email="first@example.com")
        user2 = _make_user(supabase_auth_id=auth_id, email="second@example.com")

        await repo.save(user1)
        await async_session.commit()
        await repo.save(user2)
        await async_session.commit()

        found = await repo.find_by_supabase_auth_id(auth_id)
        assert found is not None
        assert found.email == "first@example.com"

    async def test_save_then_find_by_id(
        self, async_session: AsyncSession
    ) -> None:
        repo = UserRepository(async_session)
        user = _make_user(email="byid@example.com")

        await repo.save(user)
        await async_session.commit()

        found = await repo.find_by_id(user.id)
        assert found is not None
        assert found.id == user.id

    async def test_save_then_find_by_email(
        self, async_session: AsyncSession
    ) -> None:
        repo = UserRepository(async_session)
        email = f"email_{uuid.uuid4().hex[:8]}@example.com"
        user = _make_user(email=email)

        await repo.save(user)
        await async_session.commit()

        found = await repo.find_by_email(email)
        assert found is not None
        assert found.id == user.id


class TestUserRepositoryFind:
    async def test_find_by_id_returns_none_when_not_found(
        self, async_session: AsyncSession
    ) -> None:
        repo = UserRepository(async_session)
        result = await repo.find_by_id(uuid.uuid4())
        assert result is None

    async def test_find_by_supabase_auth_id_returns_none_when_not_found(
        self, async_session: AsyncSession
    ) -> None:
        repo = UserRepository(async_session)
        result = await repo.find_by_supabase_auth_id(uuid.uuid4())
        assert result is None

    async def test_find_by_email_returns_none_when_not_found(
        self, async_session: AsyncSession
    ) -> None:
        repo = UserRepository(async_session)
        result = await repo.find_by_email("nonexistent@example.com")
        assert result is None


class TestUserRepositoryUpdate:
    async def test_update_persists_display_name_change(
        self, async_session: AsyncSession
    ) -> None:
        repo = UserRepository(async_session)
        user = _make_user(display_name="Original Name")

        await repo.save(user)
        await async_session.commit()

        user.display_name = "Updated Name"
        await repo.update(user)
        await async_session.commit()

        found = await repo.find_by_id(user.id)
        assert found is not None
        assert found.display_name == "Updated Name"

    async def test_update_persists_status_change(
        self, async_session: AsyncSession
    ) -> None:
        repo = UserRepository(async_session)
        user = _make_user()

        await repo.save(user)
        await async_session.commit()

        user.status = UserStatus.SUSPENDED
        await repo.update(user)
        await async_session.commit()

        found = await repo.find_by_id(user.id)
        assert found is not None
        assert found.status == UserStatus.SUSPENDED
