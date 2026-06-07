"""
PropertyService — property creation and ownership-protected access.

Responsibilities (APPLICATION_SERVICE_ARCHITECTURE.md Part 13):
  - create_property: validates leasehold consistency, persists, returns entity
  - get_property_for_user: ownership-protected read; raises NotFoundError

Leasehold consistency rules (Part 13.1 STEP 2):
  - LEASEHOLD + no lease_years_remaining → DomainError
  - FREEHOLD + lease_years_remaining provided → DomainError

Note on LeaseDetails: DOMAIN_MODEL_ARCHITECTURE.md §5.10 defines LeaseDetails
as a single-field value object (lease_years_remaining: int). It was not
implemented in the domain entity layer (Commit 1.4), which uses
lease_years_remaining: int | None directly on Property. This service uses
the same approach — no LeaseDetails wrapper — consistent with the existing
domain entity, repository, and ORM model.

Architecture:
    APPLICATION_SERVICE_ARCHITECTURE.md Part 13.
    DOMAIN_MODEL_ARCHITECTURE.md §5.10 (LeaseDetails invariant).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from app.domain.entities.property import Property
from app.domain.enums import PropertyType, Tenure
from app.domain.errors import DomainError, NotFoundError
from app.domain.value_objects.address import PropertyAddress
from app.repositories.interfaces.i_property import IPropertyRepository
from app.repositories.pagination import Page, PageRequest


class PropertyService:
    """
    Manages investment property records.

    Depends on IPropertyRepository (injected). Does not manage session lifecycle.

    Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 13.
    """

    def __init__(self, property_repo: IPropertyRepository) -> None:
        self._property_repo = property_repo

    async def create_property(
        self,
        user_id: uuid.UUID,
        address: PropertyAddress,
        property_type: PropertyType,
        tenure: Tenure,
        lease_years_remaining: int | None,
        bedrooms: int | None,
        epc_rating: str | None,
    ) -> Property:
        """
        Create and persist a new property.

        Validates leasehold consistency before construction:
          - LEASEHOLD requires lease_years_remaining.
          - FREEHOLD must not provide lease_years_remaining.

        Returns the persisted Property entity.

        Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 13.1.
        """
        if tenure == Tenure.LEASEHOLD and lease_years_remaining is None:
            raise DomainError(
                "Lease details required for leasehold properties"
            )
        if tenure == Tenure.FREEHOLD and lease_years_remaining is not None:
            raise DomainError(
                "Lease details cannot be provided for freehold properties"
            )

        prop = Property(
            id=uuid.uuid4(),
            user_id=user_id,
            address=address,
            property_type=property_type,
            tenure=tenure,
            lease_years_remaining=lease_years_remaining,
            bedrooms=bedrooms,
            epc_rating=epc_rating,
            is_archived=False,
        )
        await self._property_repo.save(prop)
        return prop

    async def get_property_for_user(
        self,
        property_id: uuid.UUID,
        user_id: uuid.UUID,
    ) -> Property:
        """
        Return a property owned by the given user.

        Raises NotFoundError if the property does not exist or belongs to
        a different user — both cases produce the same error per SI-13
        (non-disclosure of existence).

        Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 13, SI-13.
        """
        prop = await self._property_repo.find_by_id_for_user(property_id, user_id)
        if prop is None:
            raise NotFoundError(entity="property", id=property_id)
        return prop

    async def list_properties(
        self,
        user_id: uuid.UUID,
        include_archived: bool = False,
        page: PageRequest | None = None,
    ) -> Page[Property]:
        """
        Return a paginated list of properties owned by the given user.

        include_archived=False (default) excludes archived properties.
        The query is already scoped to user_id — no additional ownership
        check is required.

        Architecture: SERVICE_ARCHITECTURE.md — API layer calls services,
        not repositories directly.
        """
        return await self._property_repo.find_all_for_user(
            user_id,
            include_archived=include_archived,
            page=page or PageRequest(),
        )

    async def update_property(
        self,
        user_id: uuid.UUID,
        property_id: uuid.UUID,
        address: PropertyAddress | None = None,
        property_type: PropertyType | None = None,
        bedrooms: int | None = None,
        epc_rating: str | None = None,
    ) -> Property:
        """
        Apply mutable field updates to a user-owned property and persist.

        Tenure is immutable after creation and cannot be changed via this
        method (domain invariant — changing tenure would invalidate historical
        snapshots that recorded it at calculation time).

        Raises NotFoundError if the property does not exist or belongs to
        a different user.

        Architecture: SERVICE_ARCHITECTURE.md — API layer calls services.
        DOMAIN_MODEL_ARCHITECTURE.md Part 16 — tenure immutability.
        """
        prop = await self._property_repo.find_by_id_for_user(property_id, user_id)
        if prop is None:
            raise NotFoundError(entity="property", id=property_id)

        if address is not None:
            prop.address = address
        if property_type is not None:
            prop.property_type = property_type
        if bedrooms is not None:
            prop.bedrooms = bedrooms
        if epc_rating is not None:
            prop.epc_rating = epc_rating

        await self._property_repo.update(prop)
        return prop

    async def archive_property(
        self,
        user_id: uuid.UUID,
        property_id: uuid.UUID,
    ) -> Property:
        """
        Archive a property. Archived properties are excluded from list views
        by default but remain accessible for historical snapshot reproduction.

        Raises NotFoundError if the property does not exist or belongs to
        a different user.

        Architecture: SERVICE_ARCHITECTURE.md — API layer calls services.
        """
        prop = await self._property_repo.find_by_id_for_user(property_id, user_id)
        if prop is None:
            raise NotFoundError(entity="property", id=property_id)

        prop.is_archived = True
        prop.archived_at = datetime.now(UTC)
        await self._property_repo.update(prop)
        return prop
