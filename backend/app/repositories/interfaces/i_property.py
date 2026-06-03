"""
IPropertyRepository — abstract interface for property persistence.

Architecture: REPOSITORY_ARCHITECTURE.md Part 2.3, 5.3.
"""

from __future__ import annotations

import uuid
from typing import Protocol, runtime_checkable

from app.domain.entities.property import Property
from app.repositories.pagination import Page, PageRequest


@runtime_checkable
class IPropertyRepository(Protocol):
    """
    Persists and loads Property aggregates.

    Properties are OPERATIONALLY MUTABLE (address refinements, archival).
    Tenure is immutable after creation — changing tenure would invalidate
    historical snapshots.

    Architecture: REPOSITORY_ARCHITECTURE.md Part 2.3, 5.3.
    """

    async def save(self, property: Property) -> None:
        """Persist a new property (INSERT)."""
        ...

    async def update(self, property: Property) -> None:
        """
        Persist mutable field updates: address, property_type, bedrooms,
        epc_rating, is_archived, archived_at.

        Never updates user_id, tenure, or created_at.
        """
        ...

    async def find_by_id(self, property_id: uuid.UUID) -> Property | None:
        """Return the property with this id, or None if not found."""
        ...

    async def find_by_id_for_user(
        self, property_id: uuid.UUID, user_id: uuid.UUID
    ) -> Property | None:
        """
        Ownership-aware load.
        Returns None if not found OR if the property belongs to a different user.
        Never distinguishes between the two cases (RI-06).
        """
        ...

    async def find_all_for_user(
        self,
        user_id: uuid.UUID,
        include_archived: bool,
        page: PageRequest,
    ) -> Page[Property]:
        """
        Paginated list of properties for a user.

        include_archived=False (default) excludes archived properties.
        Ordered by created_at DESC (newest first).

        Architecture: REPOSITORY_ARCHITECTURE.md Part 15.2.
        """
        ...
