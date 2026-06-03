"""
IAuditRepository — abstract interface for calculation audit event persistence.

Also defines CalculationAuditEvent, the domain representation of an audit record.

Architecture: REPOSITORY_ARCHITECTURE.md Part 2.7, 5.7, 16.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable

from app.domain.enums import CalculationOutcome
from app.repositories.pagination import Page, PageRequest

# ---------------------------------------------------------------------------
# CalculationAuditEvent — domain entity for one audit record.
# Architecture: REPOSITORY_ARCHITECTURE.md Part 2.7, 16.
# DATABASE_SCHEMA_DESIGN.md Section 5 — audit_calculations table.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CalculationAuditEvent:
    """
    Immutable record of one calculation attempt — success or failure.

    Written on every calculation attempt regardless of outcome (RI-05).
    For SUCCESS: snapshot_id is populated and validation_errors is None.
    For VALIDATION_FAILURE: snapshot_id is None, validation_errors is a
        list of {rule_code, field, message} dicts.
    For ENGINE_ERROR: snapshot_id is None, error_detail is a sanitised
        description (no stack traces — user-facing safety).

    Architecture: REPOSITORY_ARCHITECTURE.md Part 16.1.
    DATABASE_SCHEMA_DESIGN.md Section 5 — audit_calculations.
    """

    id: uuid.UUID
    user_id: uuid.UUID
    deal_id: uuid.UUID
    snapshot_id: uuid.UUID | None       # None for failure outcomes
    triggered_at: datetime
    outcome: CalculationOutcome
    engine_version: str
    validation_errors: list[dict[str, Any]] | None   # For VALIDATION_FAILURE
    error_detail: str | None                          # For ENGINE_ERROR
    client_context: str | None                        # e.g. "web", "api"
    created_at: datetime


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------


@runtime_checkable
class IAuditRepository(Protocol):
    """
    Append-only write and scoped read of calculation audit events.

    save() is the only write operation. All audit records are immutable
    after creation (RI-05).

    Two critical audit paths (REPOSITORY_ARCHITECTURE.md Part 16.1):

    Path A — Calculation success:
        save() is called inside the snapshot creation transaction.
        Both the snapshot and the audit event commit or roll back together.
        outcome=SUCCESS, snapshot_id=<new_id>.

    Path B — Validation failure or engine error:
        save() is called with a fresh session after the failed transaction.
        The audit write must succeed even if the main transaction failed (RI-10).
        outcome=VALIDATION_FAILURE or ENGINE_ERROR, snapshot_id=None.

    Architecture: REPOSITORY_ARCHITECTURE.md Part 2.7, 5.7, 16.
    """

    async def save(self, event: CalculationAuditEvent) -> None:
        """
        Insert one audit event record.

        The only write operation. Never updates or deletes (RI-05).
        For failure outcomes (Path B), this is called with a fresh session
        independent of any failed transaction (RI-10).
        """
        ...

    async def find_history_for_deal(
        self,
        deal_id: uuid.UUID,
        page: PageRequest,
    ) -> Page[CalculationAuditEvent]:
        """
        Paginated calculation history for a specific deal.
        Ordered by triggered_at DESC.
        """
        ...

    async def find_history_for_user(
        self,
        user_id: uuid.UUID,
        page: PageRequest,
    ) -> Page[CalculationAuditEvent]:
        """
        Paginated calculation history for a user (all their deals).
        Ordered by triggered_at DESC.
        """
        ...
