"""
IUserRepository — abstract interface for user persistence.

The service layer depends on this Protocol. The SQLAlchemy implementation
(Commit 4.4) satisfies it structurally without inheritance.

Architecture: REPOSITORY_ARCHITECTURE.md Part 2.4, 5.4.
"""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from app.domain.entities.user import User


@runtime_checkable
class IUserRepository(Protocol):
    """
    Manages User platform records.

    Thin layer — most user identity is managed by Supabase Auth. This
    repository handles the platform-level record created on first login.

    RI-06: find_by_*_for_user variants return None for both "not found"
    and "found but wrong user" — they never distinguish between the two.
    (UserRepository has no _for_user methods; users are not sub-owned.)

    Architecture: REPOSITORY_ARCHITECTURE.md Part 2.4, 5.4.
    """

    async def save(self, user: User) -> None:
        """
        Create a new user platform record.

        Idempotent: if a record with the same supabase_auth_id already
        exists, returns without error and without creating a duplicate.
        Called on first authenticated login.
        """
        ...

    async def update(self, user: User) -> None:
        """
        Persist mutable field updates: display_name, status.

        Never updates id, supabase_auth_id, or created_at.
        """
        ...

    async def find_by_id(self, user_id: uuid.UUID) -> User | None:
        """Return the user with this id, or None if not found."""
        ...

    async def find_by_supabase_auth_id(
        self, supabase_auth_id: uuid.UUID
    ) -> User | None:
        """
        Primary lookup used on every authenticated request.
        Returns None if no platform record exists for this auth identity.
        """
        ...

    async def find_by_email(self, email: str) -> User | None:
        """
        Lookup by email address.
        Used for admin operations. Not exposed in standard user flows.
        Returns None if not found.
        """
        ...
