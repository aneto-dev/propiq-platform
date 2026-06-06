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

from app.domain.entities.property import Property
from app.domain.enums import PropertyType, Tenure
from app.domain.errors import DomainError, NotFoundError
from app.domain.value_objects.address import PropertyAddress
from app.repositories.interfaces.i_property import IPropertyRepository


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
