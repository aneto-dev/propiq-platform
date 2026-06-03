"""
AuditRepository — SQLAlchemy implementation of IAuditRepository.

Append-only: save() is the only write operation. No update or delete
methods exist — audit records are immutable after creation (RI-05).

Two write paths (REPOSITORY_ARCHITECTURE.md Part 16.1):
  Path A — called inside the snapshot creation transaction (SUCCESS).
  Path B — called with a fresh session after a failed transaction
            (VALIDATION_FAILURE, ENGINE_ERROR).

Architecture:
    REPOSITORY_ARCHITECTURE.md Part 2.7, 5.7, 16.
    DATABASE_SCHEMA_DESIGN.md Section 5 — audit_calculations table.
"""

from __future__ import annotations

import uuid

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit import AuditCalculation
from app.domain.enums import CalculationOutcome
from app.repositories.interfaces.i_audit import CalculationAuditEvent
from app.repositories.pagination import Page, PageRequest


class AuditRepository:
    """
    SQLAlchemy implementation of IAuditRepository.

    Receives AsyncSession as a constructor dependency.
    Does not commit — the caller manages session lifecycle.

    Architecture: REPOSITORY_ARCHITECTURE.md Part 13.1–13.3.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, event: CalculationAuditEvent) -> None:
        """
        Insert one audit event record.

        The only write operation on this repository. Never updates or
        deletes (RI-05). For failure outcomes (Path B), the caller
        provides a fresh session independent of any failed transaction.
        """
        row = AuditCalculation(
            id=event.id,
            user_id=event.user_id,
            deal_id=event.deal_id,
            snapshot_id=event.snapshot_id,
            triggered_at=event.triggered_at,
            outcome=event.outcome,
            engine_version=event.engine_version,
            validation_errors=event.validation_errors,
            error_detail=event.error_detail,
            client_context=event.client_context,
        )
        self._session.add(row)

    async def find_history_for_deal(
        self,
        deal_id: uuid.UUID,
        page: PageRequest,
    ) -> Page[CalculationAuditEvent]:
        """
        Paginated calculation history for a deal, ordered by triggered_at DESC.
        """
        return await self._paginated_query(
            predicate=AuditCalculation.deal_id == deal_id,
            page=page,
        )

    async def find_history_for_user(
        self,
        user_id: uuid.UUID,
        page: PageRequest,
    ) -> Page[CalculationAuditEvent]:
        """
        Paginated calculation history for a user (all deals), triggered_at DESC.
        """
        return await self._paginated_query(
            predicate=AuditCalculation.user_id == user_id,
            page=page,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _paginated_query(
        self,
        predicate: ColumnElement[bool],
        page: PageRequest,
    ) -> Page[CalculationAuditEvent]:
        """
        Shared keyset-paginated query for deal and user history.
        Ordered by triggered_at DESC, id DESC.
        Cursor encoded as (triggered_at, id) using Page.encode_cursor.
        """
        # count
        count_stmt = (
            select(func.count())
            .select_from(AuditCalculation)
            .where(predicate)
        )
        total_count = (await self._session.execute(count_stmt)).scalar_one()

        # list
        stmt = select(AuditCalculation).where(predicate)

        cursor = page.decode_cursor()
        if cursor is not None:
            cursor_ts, cursor_id = cursor
            stmt = stmt.where(
                (AuditCalculation.triggered_at < cursor_ts)
                | (
                    (AuditCalculation.triggered_at == cursor_ts)
                    & (AuditCalculation.id < cursor_id)
                )
            )

        stmt = stmt.order_by(
            AuditCalculation.triggered_at.desc(),
            AuditCalculation.id.desc(),
        ).limit(page.limit + 1)

        rows = (await self._session.execute(stmt)).scalars().all()

        has_next = len(rows) > page.limit
        if has_next:
            rows = list(rows[: page.limit])

        items = [self._to_domain(row) for row in rows]

        next_cursor: str | None = None
        if has_next and rows:
            last = rows[-1]
            next_cursor = Page.encode_cursor(last.triggered_at, last.id)

        return Page(items=items, next_cursor=next_cursor, total_count=total_count)

    @staticmethod
    def _to_domain(row: AuditCalculation) -> CalculationAuditEvent:
        """Convert AuditCalculation ORM row → CalculationAuditEvent."""
        outcome = (
            row.outcome
            if isinstance(row.outcome, CalculationOutcome)
            else CalculationOutcome(row.outcome)
        )
        return CalculationAuditEvent(
            id=row.id,
            user_id=row.user_id,
            deal_id=row.deal_id,
            snapshot_id=row.snapshot_id,
            triggered_at=row.triggered_at,
            outcome=outcome,
            engine_version=row.engine_version,
            validation_errors=row.validation_errors,
            error_detail=row.error_detail,
            client_context=row.client_context,
            created_at=row.created_at,
        )
