"""
AuditService — two write paths for calculation audit events.

Write paths (APPLICATION_SERVICE_ARCHITECTURE.md Part 11.1):

  write_success(event, repo)
      Called INSIDE the snapshot creation transaction.
      Uses the caller-provided repository (bound to the snapshot session).
      Commits atomically with the snapshot — caller controls the transaction.

  write_failure(event)
      Called OUTSIDE any transaction, after a failed calculation.
      Opens a fresh AsyncSession from the injected session factory.
      Commits independently.
      Wraps the entire write in try/except — NEVER raises to the caller.
      On failure: logs server-side, returns silently (SI-08).

Architecture:
    APPLICATION_SERVICE_ARCHITECTURE.md Part 11, SI-07, SI-08.
    REPOSITORY_ARCHITECTURE.md Part 16.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.repositories.audit_repository import AuditRepository
from app.repositories.interfaces.i_audit import (
    CalculationAuditEvent,
    IAuditRepository,
)

logger = logging.getLogger(__name__)


class AuditService:
    """
    Write-only audit service for calculation events.

    Constructor arguments:
      session_factory — async_sessionmaker used by write_failure() to open
                        a fresh session independent of any failed transaction.

    Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 11.
    """

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    # ------------------------------------------------------------------
    # Path A — success (inside snapshot transaction)
    # APPLICATION_SERVICE_ARCHITECTURE.md Part 11.1
    # ------------------------------------------------------------------

    async def write_success(
        self,
        event: CalculationAuditEvent,
        repo: IAuditRepository,
    ) -> None:
        """
        Persist a SUCCESS audit event using the caller's open repository.

        The caller (CalculationService) is responsible for the session and
        transaction. This method does not commit — it only appends the
        audit row to the session. The caller's transaction commits all
        snapshot sub-tables and this record atomically (SI-06).

        Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 11.1.
        """
        await repo.save(event)

    # ------------------------------------------------------------------
    # Path B — failure (fresh session, exception-swallowing)
    # APPLICATION_SERVICE_ARCHITECTURE.md Part 11.1, SI-07, SI-08
    # ------------------------------------------------------------------

    async def write_failure(
        self,
        event: CalculationAuditEvent,
    ) -> None:
        """
        Persist a VALIDATION_FAILURE or ENGINE_ERROR audit event.

        Opens a fresh AsyncSession independent of any failed transaction
        (SI-07). Commits independently. If the write fails for any reason,
        logs the failure and returns silently — NEVER raises (SI-08).

        Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 11.1.
        """
        try:
            async with self._session_factory() as session:
                repo = AuditRepository(session)
                await repo.save(event)
                await session.commit()
        except Exception:
            logger.exception(
                "audit_write_failure_failed",
                extra={
                    "event_id": str(event.id),
                    "user_id": str(event.user_id),
                    "deal_id": str(event.deal_id),
                    "outcome": event.outcome.value,
                },
            )
