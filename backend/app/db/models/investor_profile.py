"""
ORM model: investor_profiles table.

Source: DATABASE_SCHEMA_DESIGN.md Section 2 — Table: investor_profiles.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, text
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums import IncomeTaxBand, OwnershipStructure


class InvestorProfile(Base):
    __tablename__ = "investor_profiles"

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
    label: Mapped[str] = mapped_column(String, nullable=False)
    ownership_structure: Mapped[OwnershipStructure] = mapped_column(
        SAEnum(OwnershipStructure, name="ownership_structure_enum", create_type=False),
        nullable=False,
    )
    income_tax_band: Mapped[IncomeTaxBand | None] = mapped_column(
        SAEnum(IncomeTaxBand, name="income_tax_band_enum", create_type=False),
        nullable=True,
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"),
    )
    is_archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"),
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint(
            "(ownership_structure = 'INDIVIDUAL'"
            " AND income_tax_band IS NOT NULL)"
            " OR "
            "(ownership_structure = 'LIMITED_COMPANY'"
            " AND income_tax_band IS NULL)",
            name="investor_profiles_tax_band_consistency",
        ),
    )
