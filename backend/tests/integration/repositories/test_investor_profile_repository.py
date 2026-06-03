"""
Integration tests for InvestorProfileRepository.

Requires a running test database. Run via:
    make test-int

Architecture: REPOSITORY_ARCHITECTURE.md Part 5.5.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.investor_profile import InvestorProfile
from app.domain.entities.user import User
from app.domain.enums import IncomeTaxBand, OwnershipStructure, UserStatus
from app.repositories.investor_profile_repository import InvestorProfileRepository
from app.repositories.user_repository import UserRepository


async def _create_user(session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        supabase_auth_id=uuid.uuid4(),
        email=f"profile_test_{uuid.uuid4().hex[:8]}@example.com",
        display_name="Profile Test User",
        status=UserStatus.ACTIVE,
    )
    repo = UserRepository(session)
    await repo.save(user)
    await session.commit()
    return user


def _make_profile(
    user_id: uuid.UUID,
    label: str = "Personal",
    ownership_structure: OwnershipStructure = OwnershipStructure.INDIVIDUAL,
    income_tax_band: IncomeTaxBand | None = IncomeTaxBand.BASIC_RATE,
    is_default: bool = False,
) -> InvestorProfile:
    return InvestorProfile(
        id=uuid.uuid4(),
        user_id=user_id,
        label=label,
        ownership_structure=ownership_structure,
        income_tax_band=income_tax_band,
        is_default=is_default,
    )


class TestInvestorProfileRepositorySave:
    async def test_save_then_find_by_id(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        repo = InvestorProfileRepository(async_session)
        profile = _make_profile(user.id)

        await repo.save(profile)
        await async_session.commit()

        found = await repo.find_by_id(profile.id)
        assert found is not None
        assert found.id == profile.id
        assert found.user_id == user.id
        assert found.label == "Personal"
        assert found.ownership_structure == OwnershipStructure.INDIVIDUAL
        assert found.income_tax_band == IncomeTaxBand.BASIC_RATE

    async def test_save_limited_company_profile_no_tax_band(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        repo = InvestorProfileRepository(async_session)
        profile = _make_profile(
            user.id,
            label="Ltd Co",
            ownership_structure=OwnershipStructure.LIMITED_COMPANY,
            income_tax_band=None,
        )

        await repo.save(profile)
        await async_session.commit()

        found = await repo.find_by_id(profile.id)
        assert found is not None
        assert found.income_tax_band is None
        assert found.ownership_structure == OwnershipStructure.LIMITED_COMPANY


class TestInvestorProfileRepositoryFind:
    async def test_find_by_id_returns_none_when_not_found(
        self, async_session: AsyncSession
    ) -> None:
        repo = InvestorProfileRepository(async_session)
        result = await repo.find_by_id(uuid.uuid4())
        assert result is None

    async def test_find_by_id_for_user_returns_profile_for_correct_user(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        repo = InvestorProfileRepository(async_session)
        profile = _make_profile(user.id)

        await repo.save(profile)
        await async_session.commit()

        found = await repo.find_by_id_for_user(profile.id, user.id)
        assert found is not None
        assert found.id == profile.id

    async def test_find_by_id_for_user_returns_none_for_wrong_user(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        other_user = await _create_user(async_session)
        repo = InvestorProfileRepository(async_session)
        profile = _make_profile(user.id)

        await repo.save(profile)
        await async_session.commit()

        found = await repo.find_by_id_for_user(profile.id, other_user.id)
        assert found is None

    async def test_find_by_id_for_user_returns_none_when_not_found(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        repo = InvestorProfileRepository(async_session)

        found = await repo.find_by_id_for_user(uuid.uuid4(), user.id)
        assert found is None

    async def test_find_default_for_user_returns_default_profile(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        repo = InvestorProfileRepository(async_session)
        default_profile = _make_profile(user.id, label="Default", is_default=True)
        other_profile = _make_profile(user.id, label="Other", is_default=False)

        await repo.save(default_profile)
        await repo.save(other_profile)
        await async_session.commit()

        found = await repo.find_default_for_user(user.id)
        assert found is not None
        assert found.id == default_profile.id
        assert found.is_default is True

    async def test_find_default_for_user_returns_none_when_no_default(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        repo = InvestorProfileRepository(async_session)
        profile = _make_profile(user.id, is_default=False)

        await repo.save(profile)
        await async_session.commit()

        found = await repo.find_default_for_user(user.id)
        assert found is None

    async def test_find_all_for_user_excludes_archived_by_default(
        self, async_session: AsyncSession
    ) -> None:
        from datetime import UTC, datetime

        user = await _create_user(async_session)
        repo = InvestorProfileRepository(async_session)
        active = _make_profile(user.id, label="Active")
        archived = _make_profile(user.id, label="Archived")
        archived.is_archived = True
        archived.archived_at = datetime.now(UTC)

        await repo.save(active)
        await repo.save(archived)
        await async_session.commit()

        results = await repo.find_all_for_user(user.id, include_archived=False)
        ids = [p.id for p in results]
        assert active.id in ids
        assert archived.id not in ids

    async def test_find_all_for_user_includes_archived_when_requested(
        self, async_session: AsyncSession
    ) -> None:
        from datetime import UTC, datetime

        user = await _create_user(async_session)
        repo = InvestorProfileRepository(async_session)
        active = _make_profile(user.id, label="Active")
        archived = _make_profile(user.id, label="Archived")
        archived.is_archived = True
        archived.archived_at = datetime.now(UTC)

        await repo.save(active)
        await repo.save(archived)
        await async_session.commit()

        results = await repo.find_all_for_user(user.id, include_archived=True)
        ids = [p.id for p in results]
        assert active.id in ids
        assert archived.id in ids


class TestInvestorProfileRepositoryUpdate:
    async def test_update_persists_label_change(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        repo = InvestorProfileRepository(async_session)
        profile = _make_profile(user.id, label="Original")

        await repo.save(profile)
        await async_session.commit()

        profile.label = "Updated"
        await repo.update(profile)
        await async_session.commit()

        found = await repo.find_by_id(profile.id)
        assert found is not None
        assert found.label == "Updated"

    async def test_update_does_not_change_user_id(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        repo = InvestorProfileRepository(async_session)
        profile = _make_profile(user.id)

        await repo.save(profile)
        await async_session.commit()

        original_user_id = profile.user_id
        profile.label = "Changed"
        await repo.update(profile)
        await async_session.commit()

        found = await repo.find_by_id(profile.id)
        assert found is not None
        assert found.user_id == original_user_id
