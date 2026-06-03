"""
Integration tests for PropertyRepository.

Covers the three roadmap-specified test cases:
  - Ownership filtering: find_by_id_for_user returns None for correct ID but wrong user
  - Tenure immutability: update() does not modify tenure column
  - Archived property still returned by find_by_id_for_user

Requires a running test database. Run via:
    make test-int

Architecture: REPOSITORY_ARCHITECTURE.md Part 5.3.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.property import Property
from app.domain.entities.user import User
from app.domain.enums import PropertyType, Tenure, UserStatus
from app.domain.value_objects.address import PropertyAddress
from app.repositories.pagination import Page, PageRequest
from app.repositories.property_repository import PropertyRepository
from app.repositories.user_repository import UserRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_user(session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        supabase_auth_id=uuid.uuid4(),
        email=f"prop_test_{uuid.uuid4().hex[:8]}@example.com",
        display_name="Property Test User",
        status=UserStatus.ACTIVE,
    )
    await UserRepository(session).save(user)
    await session.commit()
    return user


def _make_address(postcode: str = "NG1 1AA") -> PropertyAddress:
    return PropertyAddress(
        address_line_1="14 Acacia Road",
        city="Nottingham",
        postcode=postcode,
    )


def _make_property(
    user_id: uuid.UUID,
    tenure: Tenure = Tenure.FREEHOLD,
    lease_years_remaining: int | None = None,
    is_archived: bool = False,
) -> Property:
    return Property(
        id=uuid.uuid4(),
        user_id=user_id,
        address=_make_address(),
        property_type=PropertyType.RESIDENTIAL_SINGLE_LET,
        tenure=tenure,
        lease_years_remaining=lease_years_remaining,
        bedrooms=2,
        epc_rating="C",
        is_archived=is_archived,
    )


# ---------------------------------------------------------------------------
# Save and basic retrieval
# ---------------------------------------------------------------------------

class TestPropertyRepositorySave:
    async def test_save_then_find_by_id(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        repo = PropertyRepository(async_session)
        prop = _make_property(user.id)

        await repo.save(prop)
        await async_session.commit()

        found = await repo.find_by_id(prop.id)
        assert found is not None
        assert found.id == prop.id
        assert found.user_id == user.id
        assert found.address.postcode == "NG1 1AA"
        assert found.property_type == PropertyType.RESIDENTIAL_SINGLE_LET
        assert found.tenure == Tenure.FREEHOLD
        assert found.bedrooms == 2
        assert found.epc_rating == "C"

    async def test_save_leasehold_property(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        repo = PropertyRepository(async_session)
        prop = _make_property(
            user.id,
            tenure=Tenure.LEASEHOLD,
            lease_years_remaining=85,
        )

        await repo.save(prop)
        await async_session.commit()

        found = await repo.find_by_id(prop.id)
        assert found is not None
        assert found.tenure == Tenure.LEASEHOLD
        assert found.lease_years_remaining == 85

    async def test_find_by_id_returns_none_when_not_found(
        self, async_session: AsyncSession
    ) -> None:
        repo = PropertyRepository(async_session)
        result = await repo.find_by_id(uuid.uuid4())
        assert result is None


# ---------------------------------------------------------------------------
# Ownership filtering (roadmap-specified test)
# ---------------------------------------------------------------------------

class TestPropertyOwnershipFiltering:
    async def test_find_by_id_for_user_returns_property_for_correct_user(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        repo = PropertyRepository(async_session)
        prop = _make_property(user.id)

        await repo.save(prop)
        await async_session.commit()

        found = await repo.find_by_id_for_user(prop.id, user.id)
        assert found is not None
        assert found.id == prop.id

    async def test_find_by_id_for_user_returns_none_for_wrong_user(
        self, async_session: AsyncSession
    ) -> None:
        """Ownership filtering: correct ID but wrong user → None (RI-06)."""
        user = await _create_user(async_session)
        other_user = await _create_user(async_session)
        repo = PropertyRepository(async_session)
        prop = _make_property(user.id)

        await repo.save(prop)
        await async_session.commit()

        found = await repo.find_by_id_for_user(prop.id, other_user.id)
        assert found is None

    async def test_find_by_id_for_user_returns_none_when_not_found(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        repo = PropertyRepository(async_session)

        found = await repo.find_by_id_for_user(uuid.uuid4(), user.id)
        assert found is None


# ---------------------------------------------------------------------------
# Tenure immutability (roadmap-specified test)
# ---------------------------------------------------------------------------

class TestTenureImmutability:
    async def test_update_does_not_modify_tenure(
        self, async_session: AsyncSession
    ) -> None:
        """Tenure immutability: update() does not modify tenure column."""
        user = await _create_user(async_session)
        repo = PropertyRepository(async_session)
        prop = _make_property(user.id, tenure=Tenure.FREEHOLD)

        await repo.save(prop)
        await async_session.commit()

        # Simulate caller attempting to change tenure (incorrect — should be ignored)
        prop.tenure = Tenure.LEASEHOLD  # type: ignore[misc]
        prop.address = PropertyAddress(
            address_line_1="15 New Road",
            city="Derby",
            postcode="DE1 1AA",
        )
        await repo.update(prop)
        await async_session.commit()

        # Address should change but tenure should remain FREEHOLD
        found = await repo.find_by_id(prop.id)
        assert found is not None
        assert found.tenure == Tenure.FREEHOLD
        assert found.address.address_line_1 == "15 New Road"
        assert found.address.city == "Derby"

    async def test_update_does_not_modify_user_id(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        repo = PropertyRepository(async_session)
        prop = _make_property(user.id)

        await repo.save(prop)
        await async_session.commit()
        original_user_id = prop.user_id

        prop.address = PropertyAddress(
            address_line_1="Updated",
            city="Nottingham",
            postcode="NG1 1AA",
        )
        await repo.update(prop)
        await async_session.commit()

        found = await repo.find_by_id(prop.id)
        assert found is not None
        assert found.user_id == original_user_id


# ---------------------------------------------------------------------------
# Archived property behaviour (roadmap-specified test)
# ---------------------------------------------------------------------------

class TestArchivedProperty:
    async def test_archived_property_returned_by_find_by_id_for_user(
        self, async_session: AsyncSession
    ) -> None:
        """Archived property still returned by find_by_id_for_user (RI-06)."""
        user = await _create_user(async_session)
        repo = PropertyRepository(async_session)
        prop = _make_property(user.id, is_archived=True)
        prop.archived_at = datetime.now(UTC)

        await repo.save(prop)
        await async_session.commit()

        found = await repo.find_by_id_for_user(prop.id, user.id)
        assert found is not None
        assert found.id == prop.id
        assert found.is_archived is True

    async def test_find_all_for_user_excludes_archived_by_default(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        repo = PropertyRepository(async_session)
        active = _make_property(user.id)
        archived = _make_property(user.id, is_archived=True)
        archived.archived_at = datetime.now(UTC)

        await repo.save(active)
        await repo.save(archived)
        await async_session.commit()

        page = await repo.find_all_for_user(
            user.id, include_archived=False, page=PageRequest()
        )
        ids = [p.id for p in page.items]
        assert active.id in ids
        assert archived.id not in ids

    async def test_find_all_for_user_includes_archived_when_requested(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        repo = PropertyRepository(async_session)
        active = _make_property(user.id)
        archived = _make_property(user.id, is_archived=True)
        archived.archived_at = datetime.now(UTC)

        await repo.save(active)
        await repo.save(archived)
        await async_session.commit()

        page = await repo.find_all_for_user(
            user.id, include_archived=True, page=PageRequest()
        )
        ids = [p.id for p in page.items]
        assert active.id in ids
        assert archived.id in ids


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------

class TestPropertyPagination:
    async def test_find_all_for_user_returns_page_with_total_count(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        repo = PropertyRepository(async_session)

        for i in range(3):
            prop = Property(
                id=uuid.uuid4(),
                user_id=user.id,
                address=PropertyAddress(
                    address_line_1=f"{i + 1} Test Street",
                    city="London",
                    postcode="SW1A 1AA",
                ),
                property_type=PropertyType.RESIDENTIAL_SINGLE_LET,
                tenure=Tenure.FREEHOLD,
            )
            await repo.save(prop)
        await async_session.commit()

        page = await repo.find_all_for_user(
            user.id, include_archived=False, page=PageRequest(limit=2)
        )
        assert isinstance(page, Page)
        assert len(page.items) == 2
        assert page.total_count >= 3
        assert page.next_cursor is not None

    async def test_find_all_for_user_second_page_via_cursor(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        repo = PropertyRepository(async_session)

        for i in range(3):
            prop = Property(
                id=uuid.uuid4(),
                user_id=user.id,
                address=PropertyAddress(
                    address_line_1=f"{i + 100} Cursor Street",
                    city="Birmingham",
                    postcode="B1 1AA",
                ),
                property_type=PropertyType.RESIDENTIAL_SINGLE_LET,
                tenure=Tenure.FREEHOLD,
            )
            await repo.save(prop)
        await async_session.commit()

        first_page = await repo.find_all_for_user(
            user.id, include_archived=False, page=PageRequest(limit=2)
        )
        assert first_page.next_cursor is not None

        second_page = await repo.find_all_for_user(
            user.id,
            include_archived=False,
            page=PageRequest(limit=2, cursor=first_page.next_cursor),
        )
        first_ids = {p.id for p in first_page.items}
        second_ids = {p.id for p in second_page.items}
        assert first_ids.isdisjoint(second_ids)
