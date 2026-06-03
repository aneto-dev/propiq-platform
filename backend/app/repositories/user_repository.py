"""
UserRepository — SQLAlchemy implementation of IUserRepository.

Thin layer: most user identity is managed by Supabase Auth. This repository
manages only the platform-level record created on first authenticated login.

Architecture:
    REPOSITORY_ARCHITECTURE.md Part 2.4, 5.4.
    DATABASE_SCHEMA_DESIGN.md Section 2 — users table.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User as UserORM
from app.domain.entities.user import User
from app.domain.enums import UserStatus


class UserRepository:
    """
    SQLAlchemy implementation of IUserRepository.

    Receives AsyncSession as a constructor dependency.
    Does not commit — the caller manages session lifecycle.

    Architecture: REPOSITORY_ARCHITECTURE.md Part 13.1–13.3.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, user: User) -> None:
        """
        Insert a new user platform record.

        Idempotent: if a record with the same supabase_auth_id already exists,
        this is a no-op (ON CONFLICT DO NOTHING on the UNIQUE index).
        Called on first authenticated login.

        Architecture: REPOSITORY_ARCHITECTURE.md Part 5.4.
        """
        stmt = (
            pg_insert(UserORM)
            .values(
                id=user.id,
                supabase_auth_id=user.supabase_auth_id,
                email=user.email,
                display_name=user.display_name,
                status=user.status,
            )
            .on_conflict_do_nothing(index_elements=["supabase_auth_id"])
        )
        await self._session.execute(stmt)

    async def update(self, user: User) -> None:
        """
        Persist mutable field updates: email, display_name, status.
        Never updates id, supabase_auth_id, or created_at.
        """
        stmt = (
            update(UserORM)
            .where(UserORM.id == user.id)
            .values(
                email=user.email,
                display_name=user.display_name,
                status=user.status,
                updated_at=datetime.now(UTC),
            )
        )
        await self._session.execute(stmt)

    async def find_by_id(self, user_id: uuid.UUID) -> User | None:
        """Return the user with this id, or None if not found."""
        stmt = select(UserORM).where(UserORM.id == user_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row is not None else None

    async def find_by_supabase_auth_id(
        self, supabase_auth_id: uuid.UUID
    ) -> User | None:
        """
        Primary lookup used on every authenticated request.
        Returns None if no platform record exists for this auth identity.
        """
        stmt = select(UserORM).where(
            UserORM.supabase_auth_id == supabase_auth_id
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row is not None else None

    async def find_by_email(self, email: str) -> User | None:
        """
        Lookup by email address.
        Used for admin operations. Not exposed in standard user flows.
        """
        stmt = select(UserORM).where(UserORM.email == email)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row is not None else None

    # ------------------------------------------------------------------
    # Private mapping helpers (Part 4.1)
    # ------------------------------------------------------------------

    def _to_domain(self, row: UserORM) -> User:
        """
        Convert UserORM row → User domain entity.

        status: SAEnum with create_type=False returns a UserStatus member or
        its string value depending on asyncpg version; coerce defensively.
        """
        status = (
            row.status
            if isinstance(row.status, UserStatus)
            else UserStatus(row.status)
        )
        return User(
            id=row.id,
            supabase_auth_id=row.supabase_auth_id,
            email=row.email,
            display_name=row.display_name,
            status=status,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
