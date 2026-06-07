"""
DealService integration tests.

Roadmap-specified tests (IMPLEMENTATION_ROADMAP.md Commit 5.4):
  1. Create deal against owned property: succeeds
  2. Create deal against non-owned property: raises NotFoundError
  3. Update working_inputs on ARCHIVED deal: raises DomainError
  4. archive() on ARCHIVED deal: raises DomainError
  5. DRAFT → ANALYSED transition on first snapshot creation

Architecture:
    APPLICATION_SERVICE_ARCHITECTURE.md Part 12.
    IMPLEMENTATION_ROADMAP.md Commit 5.4.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import DealStatus, PropertyType, Tenure
from app.domain.errors import DomainError, NotFoundError
from app.domain.value_objects.address import PropertyAddress
from app.repositories.deal_repository import DealRepository
from app.repositories.investor_profile_repository import InvestorProfileRepository
from app.repositories.property_repository import PropertyRepository
from app.repositories.user_repository import UserRepository
from app.services.deal_service import DealInputUpdate, DealService
from app.services.property_service import PropertyService
from app.services.user_service import UserService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_deal_service(session: AsyncSession) -> DealService:
    return DealService(
        deal_repo=DealRepository(session),
        property_repo=PropertyRepository(session),
        profile_repo=InvestorProfileRepository(session),
    )


async def _create_user(session: AsyncSession) -> uuid.UUID:
    svc = UserService(UserRepository(session))
    user = await svc.get_or_create_user(
        supabase_auth_id=uuid.uuid4(),
        email=f"deal_test_{uuid.uuid4().hex[:8]}@example.com",
    )
    await session.commit()
    return user.id


async def _create_property(session: AsyncSession, user_id: uuid.UUID) -> uuid.UUID:
    svc = PropertyService(PropertyRepository(session))
    prop = await svc.create_property(
        user_id=user_id,
        address=PropertyAddress(
            address_line_1="14 Acacia Road",
            city="Nottingham",
            postcode="NG1 1AA",
        ),
        property_type=PropertyType.RESIDENTIAL_SINGLE_LET,
        tenure=Tenure.FREEHOLD,
        lease_years_remaining=None,
        bedrooms=None,
        epc_rating=None,
    )
    await session.commit()
    return prop.id


# ---------------------------------------------------------------------------
# Test 1 — Create deal against owned property: succeeds
# IMPLEMENTATION_ROADMAP.md Commit 5.4 test 1
# ---------------------------------------------------------------------------


class TestCreateDeal:
    """create_deal() against an owned property succeeds and returns a DRAFT deal."""

    async def test_create_deal_against_owned_property_succeeds(
        self, async_session: AsyncSession
    ) -> None:
        """
        Create deal against owned property returns a DRAFT Deal.
        IMPLEMENTATION_ROADMAP.md Commit 5.4 test 1.
        """
        user_id = await _create_user(async_session)
        property_id = await _create_property(async_session, user_id)

        svc = _make_deal_service(async_session)
        deal = await svc.create_deal(
            user_id=user_id,
            property_id=property_id,
            label="Test Deal",
        )
        await async_session.commit()

        assert deal.id is not None
        assert deal.user_id == user_id
        assert deal.property_id == property_id
        assert deal.status == DealStatus.DRAFT
        assert deal.label == "Test Deal"

    async def test_create_deal_against_non_owned_property_raises(
        self, async_session: AsyncSession
    ) -> None:
        """
        Create deal against a property owned by another user raises NotFoundError.
        IMPLEMENTATION_ROADMAP.md Commit 5.4 test 2.
        """
        owner_id = await _create_user(async_session)
        attacker_id = await _create_user(async_session)
        property_id = await _create_property(async_session, owner_id)

        svc = _make_deal_service(async_session)

        with pytest.raises(NotFoundError) as exc_info:
            await svc.create_deal(
                user_id=attacker_id,
                property_id=property_id,
                label="Should Fail",
            )

        assert exc_info.value.entity == "property"


# ---------------------------------------------------------------------------
# Test 3 — Update working_inputs on ARCHIVED deal: raises DomainError
# IMPLEMENTATION_ROADMAP.md Commit 5.4 test 3
# ---------------------------------------------------------------------------


class TestUpdateWorkingInputs:
    """update_working_inputs() raises DomainError on ARCHIVED deals."""

    async def test_update_archived_deal_raises_domain_error(
        self, async_session: AsyncSession
    ) -> None:
        """
        Updating working inputs on an ARCHIVED deal raises DomainError.
        IMPLEMENTATION_ROADMAP.md Commit 5.4 test 3.
        """
        user_id = await _create_user(async_session)
        property_id = await _create_property(async_session, user_id)

        svc = _make_deal_service(async_session)

        deal = await svc.create_deal(
            user_id=user_id,
            property_id=property_id,
            label="Will Be Archived",
        )
        await async_session.commit()

        # Archive the deal
        await svc.archive_deal(user_id=user_id, deal_id=deal.id)
        await async_session.commit()

        # Attempt to update inputs on archived deal
        with pytest.raises(DomainError):
            await svc.update_working_inputs(
                user_id=user_id,
                deal_id=deal.id,
                input_updates=DealInputUpdate(purchase_price=Decimal("300000")),
            )

    async def test_update_draft_deal_persists_changes(
        self, async_session: AsyncSession
    ) -> None:
        """update_working_inputs() on a DRAFT deal merges and persists the change."""
        user_id = await _create_user(async_session)
        property_id = await _create_property(async_session, user_id)

        svc = _make_deal_service(async_session)

        deal = await svc.create_deal(
            user_id=user_id,
            property_id=property_id,
            label="Input Test",
        )
        await async_session.commit()

        updated = await svc.update_working_inputs(
            user_id=user_id,
            deal_id=deal.id,
            input_updates=DealInputUpdate(
                purchase_price=Decimal("250000"),
                monthly_rent=Decimal("1100"),
            ),
        )
        await async_session.commit()

        assert updated.working_inputs.purchase_price == Decimal("250000")
        assert updated.working_inputs.monthly_rent == Decimal("1100")
        # Fields not in the update are unchanged
        assert updated.working_inputs.deposit_amount is None


# ---------------------------------------------------------------------------
# Test 4 — archive() on ARCHIVED deal: raises DomainError
# IMPLEMENTATION_ROADMAP.md Commit 5.4 test 4
# ---------------------------------------------------------------------------


class TestArchiveDeal:
    """archive_deal() raises DomainError when deal is already ARCHIVED."""

    async def test_archive_already_archived_deal_raises_domain_error(
        self, async_session: AsyncSession
    ) -> None:
        """
        Calling archive_deal() on an already ARCHIVED deal raises DomainError.
        IMPLEMENTATION_ROADMAP.md Commit 5.4 test 4.
        """
        user_id = await _create_user(async_session)
        property_id = await _create_property(async_session, user_id)

        svc = _make_deal_service(async_session)

        deal = await svc.create_deal(
            user_id=user_id,
            property_id=property_id,
            label="Archive Test",
        )
        await async_session.commit()

        # First archive succeeds
        await svc.archive_deal(user_id=user_id, deal_id=deal.id)
        await async_session.commit()

        # Second archive raises
        with pytest.raises(DomainError):
            await svc.archive_deal(user_id=user_id, deal_id=deal.id)

    async def test_archive_sets_status_to_archived(
        self, async_session: AsyncSession
    ) -> None:
        """archive_deal() sets deal status to ARCHIVED."""
        user_id = await _create_user(async_session)
        property_id = await _create_property(async_session, user_id)

        svc = _make_deal_service(async_session)

        deal = await svc.create_deal(
            user_id=user_id,
            property_id=property_id,
            label="Status Test",
        )
        await async_session.commit()

        archived = await svc.archive_deal(user_id=user_id, deal_id=deal.id)
        await async_session.commit()

        assert archived.status == DealStatus.ARCHIVED


# ---------------------------------------------------------------------------
# Test 5 — DRAFT → ANALYSED transition on first snapshot creation
# IMPLEMENTATION_ROADMAP.md Commit 5.4 test 5
# ---------------------------------------------------------------------------


class TestDraftToAnalysedTransition:
    """
    DRAFT → ANALYSED transition is triggered by Deal.apply_snapshot_created().

    DealService does not own this transition — CalculationService calls it
    after a successful snapshot persist. The test verifies the domain entity
    behaviour directly, confirming it works as expected before CalculationService
    is implemented.

    IMPLEMENTATION_ROADMAP.md Commit 5.4 test 5.
    """

    async def test_draft_to_analysed_on_first_snapshot_creation(
        self, async_session: AsyncSession
    ) -> None:
        """
        Deal.apply_snapshot_created() transitions DRAFT → ANALYSED.
        IMPLEMENTATION_ROADMAP.md Commit 5.4 test 5.
        """
        import uuid as _uuid

        user_id = await _create_user(async_session)
        property_id = await _create_property(async_session, user_id)

        svc = _make_deal_service(async_session)

        deal = await svc.create_deal(
            user_id=user_id,
            property_id=property_id,
            label="Transition Test",
        )
        await async_session.commit()

        assert deal.status == DealStatus.DRAFT

        # Simulate what CalculationService does after snapshot creation
        snapshot_id = _uuid.uuid4()
        deal.apply_snapshot_created(snapshot_id)

        assert deal.status == DealStatus.ANALYSED
        assert deal.latest_snapshot_id == snapshot_id

    async def test_subsequent_snapshot_does_not_change_analysed_status(
        self, async_session: AsyncSession
    ) -> None:
        """ANALYSED → ANALYSED on recalculation (no status change)."""
        import uuid as _uuid

        user_id = await _create_user(async_session)
        property_id = await _create_property(async_session, user_id)

        svc = _make_deal_service(async_session)

        deal = await svc.create_deal(
            user_id=user_id,
            property_id=property_id,
            label="Recalc Test",
        )
        await async_session.commit()

        # First snapshot: DRAFT → ANALYSED
        deal.apply_snapshot_created(_uuid.uuid4())
        assert deal.status == DealStatus.ANALYSED

        # Second snapshot: ANALYSED → ANALYSED (no change)
        second_snapshot_id = _uuid.uuid4()
        deal.apply_snapshot_created(second_snapshot_id)
        assert deal.status == DealStatus.ANALYSED
        assert deal.latest_snapshot_id == second_snapshot_id


# ---------------------------------------------------------------------------
# Tests: get_deal and list_deals
# Bridge commit before Commit 6.3 — fills roadmap gap per SERVICE_ARCHITECTURE.md
# ---------------------------------------------------------------------------


class TestGetDeal:
    """get_deal() returns an owned deal; raises NotFoundError otherwise."""

    async def test_returns_owned_deal(
        self, async_session: AsyncSession
    ) -> None:
        user_id = await _create_user(async_session)
        property_id = await _create_property(async_session, user_id)

        svc = _make_deal_service(async_session)
        deal = await svc.create_deal(
            user_id=user_id, property_id=property_id, label="Test"
        )
        await async_session.commit()

        retrieved = await svc.get_deal(user_id, deal.id)
        assert retrieved.id == deal.id
        assert retrieved.user_id == user_id

    async def test_raises_not_found_for_wrong_user(
        self, async_session: AsyncSession
    ) -> None:
        owner_id = await _create_user(async_session)
        attacker_id = await _create_user(async_session)
        property_id = await _create_property(async_session, owner_id)

        svc = _make_deal_service(async_session)
        deal = await svc.create_deal(
            user_id=owner_id, property_id=property_id, label="Test"
        )
        await async_session.commit()

        with pytest.raises(NotFoundError) as exc_info:
            await svc.get_deal(attacker_id, deal.id)
        assert exc_info.value.entity == "deal"

    async def test_raises_not_found_for_unknown_id(
        self, async_session: AsyncSession
    ) -> None:
        user_id = await _create_user(async_session)
        svc = _make_deal_service(async_session)

        with pytest.raises(NotFoundError):
            await svc.get_deal(user_id, uuid.uuid4())


class TestListDeals:
    """list_deals() returns paginated, user-scoped deal summaries."""

    async def test_returns_owned_deals(
        self, async_session: AsyncSession
    ) -> None:
        user_id = await _create_user(async_session)
        property_id = await _create_property(async_session, user_id)

        svc = _make_deal_service(async_session)
        d1 = await svc.create_deal(
            user_id=user_id, property_id=property_id, label="Deal A"
        )
        d2 = await svc.create_deal(
            user_id=user_id, property_id=property_id, label="Deal B"
        )
        await async_session.commit()

        page = await svc.list_deals(user_id)
        ids = [s.id for s in page.items]
        assert d1.id in ids
        assert d2.id in ids

    async def test_excludes_other_users_deals(
        self, async_session: AsyncSession
    ) -> None:
        owner_id = await _create_user(async_session)
        other_id = await _create_user(async_session)
        property_id = await _create_property(async_session, owner_id)

        svc = _make_deal_service(async_session)
        await svc.create_deal(
            user_id=owner_id, property_id=property_id, label="Owner Deal"
        )
        await async_session.commit()

        page = await svc.list_deals(other_id)
        assert page.items == []

    async def test_status_filter_returns_only_matching_deals(
        self, async_session: AsyncSession
    ) -> None:
        user_id = await _create_user(async_session)
        property_id = await _create_property(async_session, user_id)

        svc = _make_deal_service(async_session)
        draft_deal = await svc.create_deal(
            user_id=user_id, property_id=property_id, label="Draft"
        )
        archived_deal = await svc.create_deal(
            user_id=user_id, property_id=property_id, label="To Archive"
        )
        await async_session.commit()

        await svc.archive_deal(user_id=user_id, deal_id=archived_deal.id)
        await async_session.commit()

        draft_page = await svc.list_deals(user_id, status_filter=DealStatus.DRAFT)
        draft_ids = [s.id for s in draft_page.items]
        assert draft_deal.id in draft_ids
        assert archived_deal.id not in draft_ids
