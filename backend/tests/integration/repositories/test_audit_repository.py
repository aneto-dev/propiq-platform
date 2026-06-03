"""
Integration tests for AuditRepository.

Roadmap-specified tests (IMPLEMENTATION_ROADMAP.md Commit 4.7):
  - save() inserts audit event
  - No update or delete methods exist on the interface
  - find_history_for_deal returns in triggered_at DESC order

Requires a running test database. Run via:
    make test-int

Architecture: REPOSITORY_ARCHITECTURE.md Part 2.7, 5.7, 16.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.entities.deal import Deal, DealWorkingInputs
from app.domain.entities.property import Property
from app.domain.entities.user import User
from app.domain.enums import (
    CalculationOutcome,
    DealStatus,
    PropertyType,
    Tenure,
    UserStatus,
)
from app.domain.value_objects.address import PropertyAddress
from app.repositories.audit_repository import AuditRepository
from app.repositories.deal_repository import DealRepository
from app.repositories.interfaces.i_audit import CalculationAuditEvent
from app.repositories.pagination import PageRequest
from app.repositories.property_repository import PropertyRepository
from app.repositories.user_repository import UserRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_user(session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        supabase_auth_id=uuid.uuid4(),
        email=f"audit_test_{uuid.uuid4().hex[:8]}@example.com",
        display_name="Audit Test User",
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
            address_line_1="1 Audit Street",
            city="Nottingham",
            postcode="NG1 1AA",
        ),
        property_type=PropertyType.RESIDENTIAL_SINGLE_LET,
        tenure=Tenure.FREEHOLD,
    )
    await PropertyRepository(session).save(prop)
    await session.commit()
    return prop


async def _create_deal(
    session: AsyncSession, user_id: uuid.UUID, property_id: uuid.UUID
) -> Deal:
    deal = Deal(
        id=uuid.uuid4(),
        user_id=user_id,
        property_id=property_id,
        label="Audit Test Deal",
        status=DealStatus.DRAFT,
        working_inputs=DealWorkingInputs(),
    )
    await DealRepository(session).save(deal)
    await session.commit()
    return deal


def _make_success_event(
    user_id: uuid.UUID,
    deal_id: uuid.UUID,
    snapshot_id: uuid.UUID,
    triggered_at: datetime | None = None,
) -> CalculationAuditEvent:
    return CalculationAuditEvent(
        id=uuid.uuid4(),
        user_id=user_id,
        deal_id=deal_id,
        snapshot_id=snapshot_id,
        triggered_at=triggered_at or datetime.now(UTC),
        outcome=CalculationOutcome.SUCCESS,
        engine_version="1.0.0",
        validation_errors=None,
        error_detail=None,
        client_context="web",
        created_at=datetime.now(UTC),
    )


def _make_failure_event(
    user_id: uuid.UUID,
    deal_id: uuid.UUID,
    triggered_at: datetime | None = None,
) -> CalculationAuditEvent:
    return CalculationAuditEvent(
        id=uuid.uuid4(),
        user_id=user_id,
        deal_id=deal_id,
        snapshot_id=None,
        triggered_at=triggered_at or datetime.now(UTC),
        outcome=CalculationOutcome.VALIDATION_FAILURE,
        engine_version="1.0.0",
        validation_errors=[{"rule_code": "V-01", "field": "purchase_price",
                            "message": "Must be > 0"}],
        error_detail=None,
        client_context="web",
        created_at=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# save() inserts audit event (roadmap-specified)
# ---------------------------------------------------------------------------

class TestAuditRepositorySave:
    async def test_save_success_event_and_find(
        self, async_session: AsyncSession
    ) -> None:
        """save() inserts audit event."""
        user = await _create_user(async_session)
        prop = await _create_property(async_session, user.id)
        deal = await _create_deal(async_session, user.id, prop.id)
        repo = AuditRepository(async_session)

        # SUCCESS requires a snapshot_id (DB CHECK constraint)
        snapshot_id = uuid.uuid4()
        # Insert a stub snapshot_calculations row to satisfy the FK
        from sqlalchemy import text

        await async_session.execute(
            text(
                "INSERT INTO snapshot_calculations "
                "(id, deal_id, user_id, engine_version, "
                "assumption_config_version_id, sdlt_config_version_id, "
                "corporation_tax_config_version_id, calculated_at) "
                "VALUES (:id, :deal_id, :user_id, :ev, "
                ":acv, :scv, :ctv, now())"
            ),
            {
                "id": snapshot_id,
                "deal_id": deal.id,
                "user_id": user.id,
                "ev": "1.0.0",
                "acv": await _get_assumption_config_id(async_session),
                "scv": await _get_sdlt_config_id(async_session),
                "ctv": await _get_ct_config_id(async_session),
            },
        )
        await async_session.commit()

        event = _make_success_event(user.id, deal.id, snapshot_id)
        await repo.save(event)
        await async_session.commit()

        page = await repo.find_history_for_deal(deal.id, PageRequest())
        assert page.total_count >= 1
        found = next((e for e in page.items if e.id == event.id), None)
        assert found is not None
        assert found.outcome == CalculationOutcome.SUCCESS
        assert found.snapshot_id == snapshot_id
        assert found.engine_version == "1.0.0"
        assert found.client_context == "web"

    async def test_save_validation_failure_event(
        self, async_session: AsyncSession
    ) -> None:
        """save() inserts VALIDATION_FAILURE event with no snapshot_id."""
        user = await _create_user(async_session)
        prop = await _create_property(async_session, user.id)
        deal = await _create_deal(async_session, user.id, prop.id)
        repo = AuditRepository(async_session)

        event = _make_failure_event(user.id, deal.id)
        await repo.save(event)
        await async_session.commit()

        page = await repo.find_history_for_deal(deal.id, PageRequest())
        found = next((e for e in page.items if e.id == event.id), None)
        assert found is not None
        assert found.outcome == CalculationOutcome.VALIDATION_FAILURE
        assert found.snapshot_id is None
        assert found.validation_errors is not None
        assert found.validation_errors[0]["rule_code"] == "V-01"

    async def test_save_engine_error_event(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        prop = await _create_property(async_session, user.id)
        deal = await _create_deal(async_session, user.id, prop.id)
        repo = AuditRepository(async_session)

        event = CalculationAuditEvent(
            id=uuid.uuid4(),
            user_id=user.id,
            deal_id=deal.id,
            snapshot_id=None,
            triggered_at=datetime.now(UTC),
            outcome=CalculationOutcome.ENGINE_ERROR,
            engine_version="1.0.0",
            validation_errors=None,
            error_detail="Unexpected internal error",
            client_context=None,
            created_at=datetime.now(UTC),
        )
        await repo.save(event)
        await async_session.commit()

        page = await repo.find_history_for_deal(deal.id, PageRequest())
        found = next((e for e in page.items if e.id == event.id), None)
        assert found is not None
        assert found.outcome == CalculationOutcome.ENGINE_ERROR
        assert found.error_detail == "Unexpected internal error"
        assert found.client_context is None


# ---------------------------------------------------------------------------
# No update or delete methods (roadmap-specified)
# ---------------------------------------------------------------------------

class TestAuditRepositoryAppendOnly:
    def test_no_update_method_on_interface(self) -> None:
        """No update or delete methods exist on the interface (RI-05)."""
        from app.repositories.interfaces.i_audit import IAuditRepository

        assert not hasattr(IAuditRepository, "update"), (
            "IAuditRepository must not expose an update() method"
        )
        assert not hasattr(IAuditRepository, "delete"), (
            "IAuditRepository must not expose a delete() method"
        )

    def test_no_update_method_on_implementation(self) -> None:
        """AuditRepository implementation has no update() or delete()."""
        assert not hasattr(AuditRepository, "update"), (
            "AuditRepository must not expose an update() method"
        )
        assert not hasattr(AuditRepository, "delete"), (
            "AuditRepository must not expose a delete() method"
        )


# ---------------------------------------------------------------------------
# find_history_for_deal — triggered_at DESC order (roadmap-specified)
# ---------------------------------------------------------------------------

class TestAuditRepositoryFindHistory:
    async def test_find_history_for_deal_ordered_by_triggered_at_desc(
        self, async_session: AsyncSession
    ) -> None:
        """find_history_for_deal returns in triggered_at DESC order."""
        user = await _create_user(async_session)
        prop = await _create_property(async_session, user.id)
        deal = await _create_deal(async_session, user.id, prop.id)
        repo = AuditRepository(async_session)

        now = datetime.now(UTC)
        oldest = _make_failure_event(
            user.id, deal.id, triggered_at=now - timedelta(hours=2)
        )
        middle = _make_failure_event(
            user.id, deal.id, triggered_at=now - timedelta(hours=1)
        )
        newest = _make_failure_event(
            user.id, deal.id, triggered_at=now
        )

        # Insert in non-chronological order to confirm ordering is by column
        await repo.save(middle)
        await repo.save(oldest)
        await repo.save(newest)
        await async_session.commit()

        page = await repo.find_history_for_deal(deal.id, PageRequest())
        deal_events = [e for e in page.items
                       if e.id in {oldest.id, middle.id, newest.id}]

        assert len(deal_events) == 3
        # DESC order: newest first
        assert deal_events[0].id == newest.id
        assert deal_events[1].id == middle.id
        assert deal_events[2].id == oldest.id

    async def test_find_history_for_deal_returns_only_that_deals_events(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        prop = await _create_property(async_session, user.id)
        deal_a = await _create_deal(async_session, user.id, prop.id)
        deal_b = await _create_deal(async_session, user.id, prop.id)
        repo = AuditRepository(async_session)

        event_a = _make_failure_event(user.id, deal_a.id)
        event_b = _make_failure_event(user.id, deal_b.id)
        await repo.save(event_a)
        await repo.save(event_b)
        await async_session.commit()

        page = await repo.find_history_for_deal(deal_a.id, PageRequest())
        ids = {e.id for e in page.items}
        assert event_a.id in ids
        assert event_b.id not in ids

    async def test_find_history_for_deal_empty_when_no_events(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        prop = await _create_property(async_session, user.id)
        deal = await _create_deal(async_session, user.id, prop.id)
        repo = AuditRepository(async_session)

        page = await repo.find_history_for_deal(deal.id, PageRequest())
        assert page.total_count == 0
        assert page.items == []
        assert page.next_cursor is None

    async def test_find_history_for_user_returns_events_across_deals(
        self, async_session: AsyncSession
    ) -> None:
        user = await _create_user(async_session)
        other_user = await _create_user(async_session)
        prop = await _create_property(async_session, user.id)
        other_prop = await _create_property(async_session, other_user.id)
        deal_a = await _create_deal(async_session, user.id, prop.id)
        deal_b = await _create_deal(async_session, user.id, prop.id)
        other_deal = await _create_deal(async_session, other_user.id, other_prop.id)
        repo = AuditRepository(async_session)

        ev_a = _make_failure_event(user.id, deal_a.id)
        ev_b = _make_failure_event(user.id, deal_b.id)
        ev_other = _make_failure_event(other_user.id, other_deal.id)
        await repo.save(ev_a)
        await repo.save(ev_b)
        await repo.save(ev_other)
        await async_session.commit()

        page = await repo.find_history_for_user(user.id, PageRequest())
        ids = {e.id for e in page.items}
        assert ev_a.id in ids
        assert ev_b.id in ids
        assert ev_other.id not in ids


# ---------------------------------------------------------------------------
# FK helpers — fetch seeded config UUIDs for snapshot stub
# ---------------------------------------------------------------------------

async def _get_assumption_config_id(session: AsyncSession) -> uuid.UUID:
    from sqlalchemy import text

    result = await session.execute(
        text("SELECT id FROM config_assumption_versions LIMIT 1")
    )
    row = result.fetchone()
    assert row is not None, "No assumption config seed data found"
    return uuid.UUID(str(row[0]))


async def _get_sdlt_config_id(session: AsyncSession) -> uuid.UUID:
    from sqlalchemy import text

    result = await session.execute(
        text("SELECT id FROM config_sdlt_versions LIMIT 1")
    )
    row = result.fetchone()
    assert row is not None, "No SDLT config seed data found"
    return uuid.UUID(str(row[0]))


async def _get_ct_config_id(session: AsyncSession) -> uuid.UUID:
    from sqlalchemy import text

    result = await session.execute(
        text("SELECT id FROM config_corporation_tax_versions LIMIT 1")
    )
    row = result.fetchone()
    assert row is not None, "No corporation tax config seed data found"
    return uuid.UUID(str(row[0]))
