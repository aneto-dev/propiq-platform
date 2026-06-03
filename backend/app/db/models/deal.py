"""
ORM model: deals table.

Source: DATABASE_SCHEMA_DESIGN.md Section 2 — Table: deals.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    SmallInteger,
    String,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums import DealStatus, IncomeTaxBand, MortgageType, OwnershipStructure


class Deal(Base):
    __tablename__ = "deals"

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
    property_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("properties.id", ondelete="RESTRICT"),
        nullable=False,
    )
    investor_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("investor_profiles.id", ondelete="RESTRICT"),
        nullable=True,
    )
    label: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[DealStatus] = mapped_column(
        SAEnum(DealStatus, name="deal_status_enum", create_type=False),
        nullable=False,
        server_default="DRAFT",
    )
    latest_snapshot_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("snapshot_calculations.id", ondelete="RESTRICT"),
        nullable=True,
    )

    # Working input fields (nullable — populated as user enters values)
    purchase_price: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=15, scale=6), nullable=True,
    )
    monthly_rent: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=15, scale=6), nullable=True,
    )
    deposit_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=15, scale=6), nullable=True,
    )
    mortgage_interest_rate: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=10, scale=6), nullable=True,
    )
    mortgage_term_years: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True,
    )
    mortgage_type: Mapped[MortgageType | None] = mapped_column(
        SAEnum(MortgageType, name="mortgage_type_enum", create_type=False),
        nullable=True,
    )
    ownership_structure: Mapped[OwnershipStructure | None] = mapped_column(
        SAEnum(OwnershipStructure, name="ownership_structure_enum", create_type=False),
        nullable=True,
    )
    income_tax_band: Mapped[IncomeTaxBand | None] = mapped_column(
        SAEnum(IncomeTaxBand, name="income_tax_band_enum", create_type=False),
        nullable=True,
    )
    is_additional_dwelling: Mapped[bool | None] = mapped_column(
        Boolean, nullable=True,
    )
    void_rate_percent: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=10, scale=6), nullable=True,
    )
    letting_agent_fee_percent: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=10, scale=6), nullable=True,
    )
    maintenance_reserve_percent: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=10, scale=6), nullable=True,
    )
    landlord_insurance_annual: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=15, scale=6), nullable=True,
    )
    purchase_legal_costs: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=15, scale=6), nullable=True,
    )
    refurbishment_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=15, scale=6), nullable=True,
    )
    annual_service_charge: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=15, scale=6), nullable=True,
    )
    annual_ground_rent: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=15, scale=6), nullable=True,
    )
    annual_accountancy_cost: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=15, scale=6), nullable=True,
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
            "purchase_price IS NULL OR purchase_price > 0",
            name="deals_purchase_price_positive",
        ),
        CheckConstraint(
            "monthly_rent IS NULL OR monthly_rent > 0",
            name="deals_monthly_rent_positive",
        ),
        CheckConstraint(
            "deposit_amount IS NULL OR deposit_amount > 0",
            name="deals_deposit_positive",
        ),
        CheckConstraint(
            "mortgage_interest_rate IS NULL OR mortgage_interest_rate >= 0",
            name="deals_rate_non_negative",
        ),
        CheckConstraint(
            "mortgage_term_years IS NULL"
            " OR (mortgage_term_years >= 5 AND mortgage_term_years <= 35)",
            name="deals_term_range",
        ),
        CheckConstraint(
            "refurbishment_cost IS NULL OR refurbishment_cost >= 0",
            name="deals_refurb_non_negative",
        ),
        CheckConstraint(
            "annual_service_charge IS NULL OR annual_service_charge >= 0",
            name="deals_service_charge_non_negative",
        ),
        CheckConstraint(
            "annual_ground_rent IS NULL OR annual_ground_rent >= 0",
            name="deals_ground_rent_non_negative",
        ),
    )
