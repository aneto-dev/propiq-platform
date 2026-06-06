"""
AuditService integration and unit tests.

Three roadmap-specified tests (IMPLEMENTATION_ROADMAP.md Commit 5.2):
  1. write_failure() does not raise even if DB is unavailable (mocked)
  2. write_failure() increments the failure counter in structured log
  3. write_success() audit record has correct outcome=SUCCESS

Tests 1 and 2 use a mock repository — no live DB needed.
Test 3 uses the live test database via the async_session fixture.

Architecture:
    APPLICATION_SERVICE_ARCHITECTURE.md Part 11, SI-07, SI-08.
    IMPLEMENTATION_ROADMAP.md Commit 5.2.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.enums import CalculationOutcome
from app.repositories.interfaces.i_audit import CalculationAuditEvent
from app.services.audit_service import AuditService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(
    outcome: CalculationOutcome = CalculationOutcome.VALIDATION_FAILURE,
    snapshot_id: uuid.UUID | None = None,
) -> CalculationAuditEvent:
    """Build a minimal CalculationAuditEvent for testing."""
    return CalculationAuditEvent(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        deal_id=uuid.uuid4(),
        snapshot_id=snapshot_id,
        triggered_at=datetime.now(UTC),
        outcome=outcome,
        engine_version="1.0.0",
        validation_errors=None,
        error_detail=None,
        client_context="test",
        created_at=datetime.now(UTC),
    )


def _make_service_with_mock_factory(mock_session: AsyncMock) -> AuditService:
    """
    Build an AuditService whose session_factory returns the given mock session.
    The mock session supports async context manager usage.
    """
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return AuditService(session_factory=mock_factory)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Test 1 — write_failure() does not raise even if DB is unavailable
# IMPLEMENTATION_ROADMAP.md Commit 5.2 test 1
# SI-08: write_failure never propagates exceptions to its caller.
# ---------------------------------------------------------------------------


class TestWriteFailureDoesNotRaise:
    """write_failure() swallows all exceptions — SI-08."""

    async def test_does_not_raise_when_save_raises(self) -> None:
        """
        If the repository save() raises (e.g. DB unavailable), write_failure()
        must return normally without propagating the exception.
        """
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock(side_effect=Exception("DB unavailable"))
        svc = _make_service_with_mock_factory(mock_session)

        event = _make_event()

        # Must not raise — this is the core SI-08 guarantee
        await svc.write_failure(event)

    async def test_does_not_raise_when_connection_error(self) -> None:
        """Any exception type is swallowed — connection errors, timeouts, etc."""
        mock_factory = MagicMock()
        mock_factory.return_value.__aenter__ = AsyncMock(
            side_effect=ConnectionRefusedError("cannot connect")
        )
        mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
        svc = AuditService(session_factory=mock_factory)  # type: ignore[arg-type]

        event = _make_event()

        # Must not raise
        await svc.write_failure(event)


# ---------------------------------------------------------------------------
# Test 2 — write_failure() logs on failure
# IMPLEMENTATION_ROADMAP.md Commit 5.2 test 2
# ---------------------------------------------------------------------------


class TestWriteFailureLogs:
    """write_failure() logs a structured entry when the write fails."""

    async def test_logs_exception_on_failure(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """
        When the DB write fails, write_failure() logs at ERROR level via
        logger.exception() — which produces a structured log entry with
        the event metadata attached.
        """
        mock_session = AsyncMock()
        mock_session.commit = AsyncMock(side_effect=RuntimeError("simulated failure"))
        svc = _make_service_with_mock_factory(mock_session)

        event = _make_event()

        with caplog.at_level(logging.ERROR, logger="app.services.audit_service"):
            await svc.write_failure(event)

        assert len(caplog.records) == 1
        record = caplog.records[0]
        assert record.levelno == logging.ERROR
        assert "audit_write_failure_failed" in record.getMessage()


# ---------------------------------------------------------------------------
# Test 3 — write_success() persists outcome=SUCCESS
# IMPLEMENTATION_ROADMAP.md Commit 5.2 test 3
# ---------------------------------------------------------------------------


class TestWriteSuccess:
    """write_success() persists a SUCCESS audit event via the caller's repo."""

    async def test_audit_record_has_correct_outcome_success(
        self, async_session: AsyncSession
    ) -> None:
        """
        write_success() saves the event using the provided repository.
        The persisted record has outcome=SUCCESS and is queryable.
        IMPLEMENTATION_ROADMAP.md Commit 5.2 test 3.
        """
        from app.repositories.audit_repository import AuditRepository

        # Build a snapshot_calculations stub row to satisfy the FK
        # (audit_calculations.snapshot_id → snapshot_calculations.id)
        r1 = await async_session.execute(
            text("SELECT id FROM config_assumption_versions LIMIT 1")
        )
        r2 = await async_session.execute(
            text("SELECT id FROM config_sdlt_versions LIMIT 1")
        )
        r3 = await async_session.execute(
            text("SELECT id FROM config_corporation_tax_versions LIMIT 1")
        )
        row1, row2, row3 = r1.fetchone(), r2.fetchone(), r3.fetchone()
        assert row1 and row2 and row3, "Config seed data missing"

        user_id = uuid.uuid4()
        deal_id = uuid.uuid4()
        snapshot_id = uuid.uuid4()

        # Insert prerequisite user row
        await async_session.execute(
            text(
                "INSERT INTO users (id, supabase_auth_id, email, status) "
                "VALUES (:id, :auth_id, :email, 'ACTIVE')"
            ),
            {
                "id": user_id,
                "auth_id": uuid.uuid4(),
                "email": f"audit_svc_{uuid.uuid4().hex[:8]}@test.com",
            },
        )
        await async_session.commit()

        # Insert prerequisite property + deal rows
        property_id = uuid.uuid4()
        await async_session.execute(
            text(
                "INSERT INTO properties "
                "(id, user_id, address_line_1, city, postcode, property_type, tenure) "
                "VALUES (:id, :uid, '1 Test St', 'London', 'EC1A 1BB', "
                "'RESIDENTIAL_SINGLE_LET', 'FREEHOLD')"
            ),
            {"id": property_id, "uid": user_id},
        )
        await async_session.execute(
            text(
                "INSERT INTO deals (id, user_id, property_id, label, status) "
                "VALUES (:id, :uid, :pid, 'Test Deal', 'DRAFT')"
            ),
            {"id": deal_id, "uid": user_id, "pid": property_id},
        )
        await async_session.execute(
            text(
                "INSERT INTO snapshot_calculations "
                "(id, deal_id, user_id, engine_version, "
                "assumption_config_version_id, sdlt_config_version_id, "
                "corporation_tax_config_version_id, calculated_at) "
                "VALUES (:id, :did, :uid, '1.0.0', :acv, :scv, :ctv, NOW())"
            ),
            {
                "id": snapshot_id,
                "did": deal_id,
                "uid": user_id,
                "acv": row1[0],
                "scv": row2[0],
                "ctv": row3[0],
            },
        )
        await async_session.commit()

        # Build a SUCCESS event
        event = CalculationAuditEvent(
            id=uuid.uuid4(),
            user_id=user_id,
            deal_id=deal_id,
            snapshot_id=snapshot_id,
            triggered_at=datetime.now(UTC),
            outcome=CalculationOutcome.SUCCESS,
            engine_version="1.0.0",
            validation_errors=None,
            error_detail=None,
            client_context="test",
            created_at=datetime.now(UTC),
        )

        # Use a mock session_factory (write_success doesn't use it)
        mock_factory = MagicMock()
        svc = AuditService(session_factory=mock_factory)  # type: ignore[arg-type]
        repo = AuditRepository(async_session)

        await svc.write_success(event, repo)
        await async_session.commit()

        # Verify the record is persisted with outcome=SUCCESS
        result = await async_session.execute(
            text(
                "SELECT outcome FROM audit_calculations WHERE id = :id"
            ),
            {"id": event.id},
        )
        row = result.fetchone()
        assert row is not None, "Audit record not found"
        assert row[0] == "SUCCESS"
