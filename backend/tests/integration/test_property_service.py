"""
PropertyService integration tests.

Roadmap-specified tests (IMPLEMENTATION_ROADMAP.md Commit 5.3):
  - Leasehold consistency: DomainError when LEASEHOLD + no lease_years_remaining
  - NotFoundError for non-owned property access

Architecture:
    APPLICATION_SERVICE_ARCHITECTURE.md Part 13.
    IMPLEMENTATION_ROADMAP.md Commit 5.3.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import PropertyType, Tenure
from app.domain.errors import DomainError, NotFoundError
from app.domain.value_objects.address import PropertyAddress
from app.repositories.property_repository import PropertyRepository
from app.repositories.user_repository import UserRepository
from app.services.property_service import PropertyService
from app.services.user_service import UserService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_service(session: AsyncSession) -> PropertyService:
    return PropertyService(PropertyRepository(session))


def _freehold_address() -> PropertyAddress:
    return PropertyAddress(
        address_line_1="14 Acacia Road",
        city="Nottingham",
        postcode="NG1 1AA",
    )


async def _create_user(session: AsyncSession) -> uuid.UUID:
    """Insert a user and return their id."""
    user_svc = UserService(UserRepository(session))
    user = await user_svc.get_or_create_user(
        supabase_auth_id=uuid.uuid4(),
        email=f"prop_test_{uuid.uuid4().hex[:8]}@example.com",
    )
    await session.commit()
    return user.id


# ---------------------------------------------------------------------------
# Tests: leasehold consistency validation
# IMPLEMENTATION_ROADMAP.md Commit 5.3 — PropertyService key behaviour
# APPLICATION_SERVICE_ARCHITECTURE.md Part 13.1 STEP 2
# ---------------------------------------------------------------------------


class TestLeaseholdConsistency:
    """Leasehold consistency is enforced before any persistence."""

    async def test_leasehold_without_lease_years_raises_domain_error(
        self, async_session: AsyncSession
    ) -> None:
        """
        LEASEHOLD tenure with no lease_years_remaining raises DomainError.
        IMPLEMENTATION_ROADMAP.md Commit 5.3 — PropertyService key behaviour.
        """
        svc = _make_service(async_session)
        user_id = await _create_user(async_session)

        with pytest.raises(DomainError):
            await svc.create_property(
                user_id=user_id,
                address=_freehold_address(),
                property_type=PropertyType.RESIDENTIAL_SINGLE_LET,
                tenure=Tenure.LEASEHOLD,
                lease_years_remaining=None,  # ← missing — must raise
                bedrooms=None,
                epc_rating=None,
            )

    async def test_freehold_with_lease_years_raises_domain_error(
        self, async_session: AsyncSession
    ) -> None:
        """FREEHOLD tenure must not supply lease_years_remaining."""
        svc = _make_service(async_session)
        user_id = await _create_user(async_session)

        with pytest.raises(DomainError):
            await svc.create_property(
                user_id=user_id,
                address=_freehold_address(),
                property_type=PropertyType.RESIDENTIAL_SINGLE_LET,
                tenure=Tenure.FREEHOLD,
                lease_years_remaining=85,  # ← invalid for FREEHOLD — must raise
                bedrooms=None,
                epc_rating=None,
            )

    async def test_leasehold_with_lease_years_succeeds(
        self, async_session: AsyncSession
    ) -> None:
        """LEASEHOLD + valid lease_years_remaining creates the property."""
        svc = _make_service(async_session)
        user_id = await _create_user(async_session)

        prop = await svc.create_property(
            user_id=user_id,
            address=PropertyAddress(
                address_line_1="Flat 3, Manor House",
                city="London",
                postcode="SW1A 1AA",
            ),
            property_type=PropertyType.RESIDENTIAL_SINGLE_LET,
            tenure=Tenure.LEASEHOLD,
            lease_years_remaining=85,
            bedrooms=2,
            epc_rating=None,
        )
        await async_session.commit()

        assert prop.tenure == Tenure.LEASEHOLD
        assert prop.lease_years_remaining == 85
        assert prop.user_id == user_id

    async def test_freehold_without_lease_years_succeeds(
        self, async_session: AsyncSession
    ) -> None:
        """FREEHOLD with no lease_years_remaining is valid."""
        svc = _make_service(async_session)
        user_id = await _create_user(async_session)

        prop = await svc.create_property(
            user_id=user_id,
            address=_freehold_address(),
            property_type=PropertyType.RESIDENTIAL_SINGLE_LET,
            tenure=Tenure.FREEHOLD,
            lease_years_remaining=None,
            bedrooms=3,
            epc_rating="C",
        )
        await async_session.commit()

        assert prop.tenure == Tenure.FREEHOLD
        assert prop.lease_years_remaining is None
        assert prop.bedrooms == 3
        assert prop.epc_rating == "C"


# ---------------------------------------------------------------------------
# Tests: NotFoundError for non-owned property access
# IMPLEMENTATION_ROADMAP.md Commit 5.3 — PropertyService key behaviour
# APPLICATION_SERVICE_ARCHITECTURE.md SI-13
# ---------------------------------------------------------------------------


class TestOwnershipProtection:
    """get_property_for_user raises NotFoundError for non-owned access."""

    async def test_raises_not_found_for_wrong_user(
        self, async_session: AsyncSession
    ) -> None:
        """
        Accessing another user's property raises NotFoundError.
        IMPLEMENTATION_ROADMAP.md Commit 5.3 — PropertyService key behaviour.
        SI-13: both "not found" and "wrong owner" produce the same error.
        """
        svc = _make_service(async_session)
        owner_id = await _create_user(async_session)
        other_user_id = await _create_user(async_session)

        # Create property owned by owner_id
        prop = await svc.create_property(
            user_id=owner_id,
            address=_freehold_address(),
            property_type=PropertyType.RESIDENTIAL_SINGLE_LET,
            tenure=Tenure.FREEHOLD,
            lease_years_remaining=None,
            bedrooms=None,
            epc_rating=None,
        )
        await async_session.commit()

        # other_user_id cannot access owner's property
        with pytest.raises(NotFoundError) as exc_info:
            await svc.get_property_for_user(prop.id, other_user_id)

        assert exc_info.value.entity == "property"
        assert exc_info.value.id == prop.id

    async def test_raises_not_found_for_nonexistent_property(
        self, async_session: AsyncSession
    ) -> None:
        """A completely unknown property ID also raises NotFoundError."""
        svc = _make_service(async_session)
        user_id = await _create_user(async_session)

        with pytest.raises(NotFoundError):
            await svc.get_property_for_user(uuid.uuid4(), user_id)

    async def test_owner_can_access_own_property(
        self, async_session: AsyncSession
    ) -> None:
        """The creating user can access their own property."""
        svc = _make_service(async_session)
        user_id = await _create_user(async_session)

        prop = await svc.create_property(
            user_id=user_id,
            address=_freehold_address(),
            property_type=PropertyType.RESIDENTIAL_SINGLE_LET,
            tenure=Tenure.FREEHOLD,
            lease_years_remaining=None,
            bedrooms=None,
            epc_rating=None,
        )
        await async_session.commit()

        retrieved = await svc.get_property_for_user(prop.id, user_id)
        assert retrieved.id == prop.id
        assert retrieved.user_id == user_id
