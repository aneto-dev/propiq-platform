"""
IInvestorProfileRepository — abstract interface for investor profile persistence.

Architecture: REPOSITORY_ARCHITECTURE.md Part 2.5, 5.5.
"""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from app.domain.entities.investor_profile import InvestorProfile


@runtime_checkable
class IInvestorProfileRepository(Protocol):
    """
    Persists and loads InvestorProfile entities.

    Profiles are a deal-creation convenience, not an authoritative
    calculation input. Historical snapshots store copied values, not FK
    references to profiles.

    Not paginated: find_all_for_user returns a plain list because a user
    is expected to have fewer than 10 profiles. (RI-09 justification.)

    Architecture: REPOSITORY_ARCHITECTURE.md Part 2.5, 5.5.
    """

    async def save(self, profile: InvestorProfile) -> None:
        """Create a new investor profile."""
        ...

    async def update(self, profile: InvestorProfile) -> None:
        """
        Persist mutable updates: label, ownership_structure, income_tax_band,
        is_default, is_archived, archived_at.

        Never updates id, user_id, or created_at.
        """
        ...

    async def find_by_id(self, profile_id: uuid.UUID) -> InvestorProfile | None:
        """Return the profile with this id, or None if not found."""
        ...

    async def find_by_id_for_user(
        self, profile_id: uuid.UUID, user_id: uuid.UUID
    ) -> InvestorProfile | None:
        """
        Ownership-aware load.
        Returns None if not found OR if the profile belongs to a different user.
        Never distinguishes between the two cases (RI-06).
        """
        ...

    async def find_all_for_user(
        self, user_id: uuid.UUID, include_archived: bool
    ) -> list[InvestorProfile]:
        """
        All profiles for a user.

        Not paginated: expected upper bound < 10 profiles per user.
        include_archived=False (default) filters out archived profiles.
        Returns newest first (ORDER BY created_at DESC).

        Architecture: REPOSITORY_ARCHITECTURE.md Part 15.3.
        """
        ...

    async def find_default_for_user(
        self, user_id: uuid.UUID
    ) -> InvestorProfile | None:
        """
        Return the profile with is_default=True for this user.
        Returns None if the user has no default profile set.
        At most one profile per user may have is_default=True (enforced at
        service layer, not repository layer).
        """
        ...
