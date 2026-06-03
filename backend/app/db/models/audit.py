"""
ORM model: audit_calculations table.

Source: DATABASE_SCHEMA_DESIGN.md Section 5 — Table: audit_calculations.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums import CalculationOutcome


class AuditCalculation(Base):
    __tablename__ = "audit_calculations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    deal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("deals.id", ondelete="RESTRICT"),
        nullable=False,
    )
    snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("snapshot_calculations.id", ondelete="RESTRICT"),
        nullable=True,
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    outcome: Mapped[CalculationOutcome] = mapped_column(
        SAEnum(CalculationOutcome, name="calculation_outcome_enum", create_type=False),
        nullable=False,
    )
    engine_version: Mapped[str] = mapped_column(String, nullable=False)
    validation_errors: Mapped[list[Any] | None] = mapped_column(JSONB, nullable=True)
    error_detail: Mapped[str | None] = mapped_column(String, nullable=True)
    client_context: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint(
            "outcome <> 'SUCCESS' OR snapshot_id IS NOT NULL",
            name="audit_calculations_success_requires_snapshot",
        ),
        CheckConstraint(
            "outcome <> 'VALIDATION_FAILURE' OR validation_errors IS NOT NULL",
            name="audit_calculations_failure_requires_errors",
        ),
        CheckConstraint(
            "triggered_at IS NOT NULL",
            name="audit_calculations_triggered_at_required",
        ),
    )
