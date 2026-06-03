"""
Integration tests for DealRepository.

Roadmap-specified tests (IMPLEMENTATION_ROADMAP.md Commit 4.6):
  - find_by_id_for_user returns None for both "not found" and "wrong user"
  - find_all_for_user pagination with cursor
  - update() persists working_inputs changes
  - update() does not modify user_id or property_id

Requires a running test database. Run via:
    make test-int

Architecture: REPOSITORY_ARCHITECTURE.md Part 5.2.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.deal import Deal, DealWorkingInputs
from app.domain.entities.property import Property
from app.domain.entities.user import User
from app.domain.enums import (
    DealStatus,
    MortgageType,
    OwnershipStructure,
    PropertyType,
    Tenure,
    UserStatus,
)
from app.domain.value_objects.address import PropertyAddress
from app.repositories.deal_repository import DealRepository
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
        email=f"deal_test_{uuid.uuid4().hex[:8]}@example.com",
        display_name="Deal Test User",
        status=UserStatus.ACTIVE,
    )
    await UserRepository(session).save(user)
    await session.commit()
    return user


async def _create_property(session: AsyncSession, user_id: uuid.UUID) -> Property:
    prop = Property(
        id=uuid.uuid4(),
        user_id=user_id,
        address=PropertyAddress(
            address_line_1="1 Test Street",
            city="Nottingham",
            postcode="NG1 1AA",
        ),
        property_type=PropertyType.RESIDENTIAL_SINGLE_LET,
        tenure=Tenure.FREEHOLD,
    )
    await PropertyRepository(session).save(prop)
    await session.commit()
    return prop


def _make_deal(
    user_id: uuid.UUID,
    property_id: uuid.UUID,
    label: str = "Test Deal",
    status: DealStatus = DealStatus.DRAFT,
    working_inputs: DealWorkingInputs | None = None,
) -> Deal:
    return Deal(
        id=uuid.uuid4(),
        user_id=user_id,
        property_id=property_id,
        label=label,
        status=status,
        working_inputs=working_inputs or DealWorkingInputs(),
    )


def _standard_inputs() -> DealWorkingInputs:
    return DealWorkingInputs(
        purchase_price=Decimal("200000"),
        monthly_rent=Decimal("950"),
        deposit_amount=Decimal("50000"),
        mortgage_interest_rate=Decimal("4.5"),
        mortgage_term_years=25,
        mortgage_type=MortgageType.INTEREST_ONLY,
        ownership_structure=OwnershipStructure.INDIVIDUAL,
        is_additional_dwelling=True,
    )


# ---------------------------------------------------------------------------
# Save and basic retrieval
# ---------------------------------------------------------------------------

class TestDealRepositorySave:
    async def test_save_then_find_by_id(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        prop = await _create_property(async_session, user.id)
        repo = DealRepository(async_session)
        deal = _make_deal(user.id, prop.id)

        await repo.save(deal)
        await async_session.commit()

        found = await repo.find_by_id(deal.id)
        assert found is not None
        assert found.id == deal.id
        assert found.user_id == user.id
        assert found.property_id == prop.id
        assert found.label == "Test Deal"
        assert found.status == DealStatus.DRAFT

    async def test_save_with_working_inputs(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        prop = await _create_property(async_session, user.id)
        repo = DealRepository(async_session)
        deal = _make_deal(user.id, prop.id, working_inputs=_standard_inputs())

        await repo.save(deal)
        await async_session.commit()

        found = await repo.find_by_id(deal.id)
        assert found is not None
        wi = found.working_inputs
        assert wi.purchase_price == Decimal("200000")
        assert wi.monthly_rent == Decimal("950")
        assert wi.mortgage_type == MortgageType.INTEREST_ONLY
        assert wi.ownership_structure == OwnershipStructure.INDIVIDUAL

    async def test_find_by_id_returns_none_when_not_found(
        self, async_session: AsyncSession
    ) -> None:
        repo = DealRepository(async_session)
        result = await repo.find_by_id(uuid.uuid4())
        assert result is None


# ---------------------------------------------------------------------------
# Ownership filtering (roadmap-specified)
# ---------------------------------------------------------------------------

class TestDealOwnershipFiltering:
    async def test_find_by_id_for_user_returns_deal_for_correct_user(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        prop = await _create_property(async_session, user.id)
        repo = DealRepository(async_session)
        deal = _make_deal(user.id, prop.id)

        await repo.save(deal)
        await async_session.commit()

        found = await repo.find_by_id_for_user(deal.id, user.id)
        assert found is not None
        assert found.id == deal.id

    async def test_find_by_id_for_user_returns_none_for_wrong_user(
        self, async_session: AsyncSession
    ) -> None:
        """RI-06: correct ID, wrong user → None (not found vs wrong user indistinguishable)."""
        user = await _create_user(async_session)
        other_user = await _create_user(async_session)
        prop = await _create_property(async_session, user.id)
        repo = DealRepository(async_session)
        deal = _make_deal(user.id, prop.id)

        await repo.save(deal)
        await async_session.commit()

        found = await repo.find_by_id_for_user(deal.id, other_user.id)
        assert found is None

    async def test_find_by_id_for_user_returns_none_when_not_found(
        self, async_session: AsyncSession
    ) -> None:
        """RI-06: unknown id, correct user → None (same code path as wrong user)."""
        user = await _create_user(async_session)
        repo = DealRepository(async_session)

        found = await repo.find_by_id_for_user(uuid.uuid4(), user.id)
        assert found is None


# ---------------------------------------------------------------------------
# Update (roadmap-specified)
# ---------------------------------------------------------------------------

class TestDealRepositoryUpdate:
    async def test_update_persists_working_inputs_changes(
        self, async_session: AsyncSession
    ) -> None:
        """update() persists working_inputs changes."""
        user = await _create_user(async_session)
        prop = await _create_property(async_session, user.id)
        repo = DealRepository(async_session)
        deal = _make_deal(user.id, prop.id)

        await repo.save(deal)
        await async_session.commit()

        deal.working_inputs.purchase_price = Decimal("250000")
        deal.working_inputs.monthly_rent = Decimal("1100")
        deal.working_inputs.mortgage_type = MortgageType.REPAYMENT
        await repo.update(deal)
        await async_session.commit()

        found = await repo.find_by_id(deal.id)
        assert found is not None
        assert found.working_inputs.purchase_price == Decimal("250000")
        assert found.working_inputs.monthly_rent == Decimal("1100")
        assert found.working_inputs.mortgage_type == MortgageType.REPAYMENT

    async def test_update_does_not_modify_user_id(
        self, async_session: AsyncSession
    ) -> None:
        """update() does not modify user_id."""
        user = await _create_user(async_session)
        prop = await _create_property(async_session, user.id)
        repo = DealRepository(async_session)
        deal = _make_deal(user.id, prop.id)

        await repo.save(deal)
        await async_session.commit()
        original_user_id = deal.user_id

        deal.label = "Renamed Deal"
        await repo.update(deal)
        await async_session.commit()

        found = await repo.find_by_id(deal.id)
        assert found is not None
        assert found.user_id == original_user_id

    async def test_update_does_not_modify_property_id(
        self, async_session: AsyncSession
    ) -> None:
        """update() does not modify property_id."""
        user = await _create_user(async_session)
        prop = await _create_property(async_session, user.id)
        repo = DealRepository(async_session)
        deal = _make_deal(user.id, prop.id)

        await repo.save(deal)
        await async_session.commit()
        original_property_id = deal.property_id

        deal.label = "Renamed"
        await repo.update(deal)
        await async_session.commit()

        found = await repo.find_by_id(deal.id)
        assert found is not None
        assert found.property_id == original_property_id

    async def test_update_persists_status_change(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        prop = await _create_property(async_session, user.id)
        repo = DealRepository(async_session)
        deal = _make_deal(user.id, prop.id, status=DealStatus.DRAFT)

        await repo.save(deal)
        await async_session.commit()

        deal.status = DealStatus.ANALYSED
        await repo.update(deal)
        await async_session.commit()

        found = await repo.find_by_id(deal.id)
        assert found is not None
        assert found.status == DealStatus.ANALYSED

    async def test_update_clears_optional_working_inputs_to_none(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        prop = await _create_property(async_session, user.id)
        repo = DealRepository(async_session)
        deal = _make_deal(user.id, prop.id, working_inputs=_standard_inputs())

        await repo.save(deal)
        await async_session.commit()

        deal.working_inputs.void_rate_percent = None
        deal.working_inputs.refurbishment_cost = None
        await repo.update(deal)
        await async_session.commit()

        found = await repo.find_by_id(deal.id)
        assert found is not None
        assert found.working_inputs.void_rate_percent is None
        assert found.working_inputs.refurbishment_cost is None


# ---------------------------------------------------------------------------
# find_all_for_user pagination (roadmap-specified)
# ---------------------------------------------------------------------------

class TestDealPagination:
    async def test_find_all_for_user_returns_page(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        prop = await _create_property(async_session, user.id)
        repo = DealRepository(async_session)

        for i in range(3):
            deal = _make_deal(user.id, prop.id, label=f"Deal {i}")
            await repo.save(deal)
        await async_session.commit()

        page = await repo.find_all_for_user(
            user.id, status_filter=None, page=PageRequest(limit=2)
        )
        assert isinstance(page, Page)
        assert len(page.items) == 2
        assert page.total_count >= 3
        assert page.next_cursor is not None

    async def test_find_all_for_user_second_page_no_overlap(
        self, async_session: AsyncSession
    ) -> None:
        """find_all_for_user pagination with cursor — pages must not overlap."""
        user = await _create_user(async_session)
        prop = await _create_property(async_session, user.id)
        repo = DealRepository(async_session)

        for i in range(3):
            deal = _make_deal(user.id, prop.id, label=f"Cursor Deal {i}")
            await repo.save(deal)
        await async_session.commit()

        first = await repo.find_all_for_user(
            user.id, status_filter=None, page=PageRequest(limit=2)
        )
        assert first.next_cursor is not None

        second = await repo.find_all_for_user(
            user.id,
            status_filter=None,
            page=PageRequest(limit=2, cursor=first.next_cursor),
        )
        first_ids = {s.id for s in first.items}
        second_ids = {s.id for s in second.items}
        assert first_ids.isdisjoint(second_ids)

    async def test_find_all_for_user_status_filter(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        prop = await _create_property(async_session, user.id)
        repo = DealRepository(async_session)

        draft = _make_deal(user.id, prop.id, label="Draft", status=DealStatus.DRAFT)
        archived = _make_deal(
            user.id, prop.id, label="Archived", status=DealStatus.ARCHIVED
        )
        await repo.save(draft)
        await repo.save(archived)
        await async_session.commit()

        page = await repo.find_all_for_user(
            user.id, status_filter=DealStatus.DRAFT, page=PageRequest()
        )
        statuses = [s.status for s in page.items]
        assert all(s == DealStatus.DRAFT for s in statuses)
        assert DealStatus.ARCHIVED not in statuses

    async def test_find_all_for_user_draft_deal_has_null_snapshot_fields(
        self, async_session: AsyncSession
    ) -> None:
        """DRAFT deal has no snapshot — all latest_snapshot_* fields must be None."""
        user = await _create_user(async_session)
        prop = await _create_property(async_session, user.id)
        repo = DealRepository(async_session)
        deal = _make_deal(user.id, prop.id, status=DealStatus.DRAFT)

        await repo.save(deal)
        await async_session.commit()

        page = await repo.find_all_for_user(
            user.id, status_filter=DealStatus.DRAFT, page=PageRequest()
        )
        summaries = [s for s in page.items if s.id == deal.id]
        assert len(summaries) == 1
        summary = summaries[0]
        assert summary.latest_snapshot_id is None
        assert summary.latest_snapshot_cash_flow_gbp is None
        assert summary.latest_snapshot_gross_yield is None
        assert summary.latest_snapshot_calculated_at is None
        assert summary.latest_snapshot_risk_flag_count_high is None


# ---------------------------------------------------------------------------
# count_for_user
# ---------------------------------------------------------------------------

class TestDealCount:
    async def test_count_for_user_excludes_archived(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        prop = await _create_property(async_session, user.id)
        repo = DealRepository(async_session)

        draft = _make_deal(user.id, prop.id, status=DealStatus.DRAFT)
        archived = _make_deal(user.id, prop.id, status=DealStatus.ARCHIVED)
        await repo.save(draft)
        await repo.save(archived)
        await async_session.commit()

        count = await repo.count_for_user(user.id)
        assert count >= 1
        # Archived deal must not be counted
        count_archived_only = await repo.find_all_for_user(
            user.id,
            status_filter=DealStatus.ARCHIVED,
            page=PageRequest(),
        )
        # count_for_user excludes ARCHIVED — verify it is less than total
        total = await repo.find_all_for_user(
            user.id, status_filter=None, page=PageRequest()
        )
        assert count < total.total_count or (
            count == total.total_count - count_archived_only.total_count
        )
