"""
ORM model: properties table.

Source: DATABASE_SCHEMA_DESIGN.md Section 2 — Table: properties.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums import PropertyType, Tenure


class Property(Base):
    __tablename__ = "properties"

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
    address_line_1: Mapped[str] = mapped_column(String, nullable=False)
    address_line_2: Mapped[str | None] = mapped_column(String, nullable=True)
    city: Mapped[str] = mapped_column(String, nullable=False)
    postcode: Mapped[str] = mapped_column(String, nullable=False)
    property_type: Mapped[PropertyType] = mapped_column(
        SAEnum(PropertyType, name="property_type_enum", create_type=False),
        nullable=False,
    )
    tenure: Mapped[Tenure] = mapped_column(
        SAEnum(Tenure, name="tenure_enum", create_type=False),
        nullable=False,
    )
    lease_years_remaining: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    bedrooms: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    epc_rating: Mapped[str | None] = mapped_column(String(1), nullable=True)
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
            r"postcode ~ '^[A-Z]{1,2}[0-9][0-9A-Z]?\s*[0-9][A-Z]{2}$'",
            name="properties_postcode_format",
        ),
        CheckConstraint(
            "lease_years_remaining IS NULL OR lease_years_remaining > 0",
            name="properties_lease_years_positive",
        ),
        CheckConstraint(
            "bedrooms IS NULL OR bedrooms > 0",
            name="properties_bedrooms_positive",
        ),
        CheckConstraint(
            "epc_rating IS NULL OR epc_rating IN ('A','B','C','D','E','F','G')",
            name="properties_epc_valid",
        ),
        CheckConstraint(
            "NOT (tenure = 'LEASEHOLD' AND lease_years_remaining IS NULL)",
            name="properties_leasehold_requires_lease_years",
        ),
    )
