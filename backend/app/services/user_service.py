"""
UserService — user account management.

Responsibilities (APPLICATION_SERVICE_ARCHITECTURE.md Part 14):
  - get_or_create_user: idempotent user creation on authenticated login

Scope (IMPLEMENTATION_ROADMAP.md Commit 5.3):
  - get_or_create_user() only.
  - create_investor_profile() is out of scope for Commit 5.3.

Architecture:
    APPLICATION_SERVICE_ARCHITECTURE.md Part 14.
"""

from __future__ import annotations

import uuid

from app.domain.entities.user import User
from app.domain.enums import UserStatus
from app.repositories.interfaces.i_user import IUserRepository


class UserService:
    """
    Manages user account records.

    Depends on IUserRepository (injected). Does not manage session lifecycle.

    Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 14.
    """

    def __init__(self, user_repo: IUserRepository) -> None:
        self._user_repo = user_repo

    async def get_or_create_user(
        self,
        supabase_auth_id: uuid.UUID,
        email: str,
    ) -> User:
        """
        Return the existing platform user for this Supabase identity, or
        create a new one if this is the user's first login.

        Idempotent: calling twice with the same supabase_auth_id returns
        the same User record without creating a duplicate.

        Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 14.1.
        """
        existing = await self._user_repo.find_by_supabase_auth_id(supabase_auth_id)
        if existing is not None:
            return existing

        user = User(
            id=uuid.uuid4(),
            supabase_auth_id=supabase_auth_id,
            email=email,
            display_name=None,
            status=UserStatus.ACTIVE,
        )
        await self._user_repo.save(user)
        return user
