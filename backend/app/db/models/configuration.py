"""
ORM models: all configuration version tables.

config_engine_versions, config_sdlt_versions, config_sdlt_bands,
config_corporation_tax_versions, config_assumption_versions.

All configuration tables are append-only (no updated_at, no is_archived).
Source: DATABASE_SCHEMA_DESIGN.md Section 4.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
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
from app.domain.enums import PropertyCountry


class ConfigEngineVersion(Base):
    __tablename__ = "config_engine_versions"

    version_string: Mapped[str] = mapped_column(String, primary_key=True)
    released_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    change_summary: Mapped[str] = mapped_column(String, nullable=False)
    is_breaking_change: Mapped[bool] = mapped_column(Boolean, nullable=False)
    specification_ref: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class ConfigSdltVersion(Base):
    __tablename__ = "config_sdlt_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False)
    property_country: Mapped[PropertyCountry] = mapped_column(
        SAEnum(PropertyCountry, name="property_country_enum", create_type=False),
        nullable=False,
    )
    additional_dwelling_surcharge_rate: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    source_attribution: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "additional_dwelling_surcharge_rate >= 0"
            " AND additional_dwelling_surcharge_rate <= 1",
            name="config_sdlt_versions_surcharge_rate_range",
        ),
    )


class ConfigSdltBand(Base):
    __tablename__ = "config_sdlt_bands"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    sdlt_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("config_sdlt_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    band_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    band_lower: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    band_upper: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=15, scale=6), nullable=True,
    )
    rate: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint("band_lower >= 0", name="config_sdlt_bands_lower_non_negative"),
        CheckConstraint(
            "band_upper IS NULL OR band_upper > band_lower",
            name="config_sdlt_bands_upper_gt_lower",
        ),
        CheckConstraint("rate >= 0 AND rate <= 1", name="config_sdlt_bands_rate_range"),
        CheckConstraint("band_order > 0", name="config_sdlt_bands_order_positive"),
    )


class ConfigCorporationTaxVersion(Base):
    __tablename__ = "config_corporation_tax_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    small_profits_rate: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False,
    )
    small_profits_upper_threshold: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    main_rate: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False,
    )
    main_rate_lower_threshold: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    marginal_relief_numerator: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    marginal_relief_denominator: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    source_attribution: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "small_profits_rate >= 0 AND small_profits_rate <= 1",
            name="config_ct_small_profits_rate_range",
        ),
        CheckConstraint(
            "main_rate >= 0 AND main_rate <= 1",
            name="config_ct_main_rate_range",
        ),
        CheckConstraint(
            "small_profits_upper_threshold < main_rate_lower_threshold",
            name="config_ct_threshold_ordering",
        ),
        CheckConstraint(
            "marginal_relief_numerator > 0",
            name="config_ct_numerator_positive",
        ),
        CheckConstraint(
            "marginal_relief_denominator > 0",
            name="config_ct_denominator_positive",
        ),
    )


class ConfigAssumptionVersion(Base):
    __tablename__ = "config_assumption_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    effective_from: Mapped[date] = mapped_column(Date, nullable=False, unique=True)
    void_rate_percent_default: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False,
    )
    letting_agent_fee_percent_default: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False,
    )
    letting_agent_vat_rate_percent: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False,
    )
    maintenance_reserve_percent_default: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False,
    )
    landlord_insurance_annual_default: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    purchase_legal_costs_default: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    accountancy_cost_individual_default: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    accountancy_cost_ltd_default: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    stress_test_rate_percent: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False,
    )
    icr_threshold_basic_rate_percent: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False,
    )
    icr_threshold_higher_rate_percent: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False,
    )
    notes: Mapped[str | None] = mapped_column(String, nullable=True)
    source_attribution: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    created_by_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )

    __table_args__ = (
        CheckConstraint(
            "void_rate_percent_default >= 0 AND void_rate_percent_default <= 100",
            name="config_assumptions_void_rate_range",
        ),
        CheckConstraint(
            "letting_agent_fee_percent_default >= 0",
            name="config_assumptions_letting_fee_non_negative",
        ),
        CheckConstraint(
            "letting_agent_vat_rate_percent >= 0",
            name="config_assumptions_vat_rate_non_negative",
        ),
        CheckConstraint(
            "maintenance_reserve_percent_default >= 0",
            name="config_assumptions_maintenance_non_negative",
        ),
        CheckConstraint(
            "landlord_insurance_annual_default >= 0",
            name="config_assumptions_insurance_non_negative",
        ),
        CheckConstraint(
            "purchase_legal_costs_default >= 0",
            name="config_assumptions_legal_costs_non_negative",
        ),
        CheckConstraint(
            "accountancy_cost_individual_default >= 0",
            name="config_assumptions_accountancy_individual_non_negative",
        ),
        CheckConstraint(
            "accountancy_cost_ltd_default >= 0",
            name="config_assumptions_accountancy_ltd_non_negative",
        ),
        CheckConstraint(
            "stress_test_rate_percent > 0",
            name="config_assumptions_stress_rate_positive",
        ),
        CheckConstraint(
            "icr_threshold_basic_rate_percent > 0",
            name="config_assumptions_icr_basic_positive",
        ),
        CheckConstraint(
            "icr_threshold_higher_rate_percent >= icr_threshold_basic_rate_percent",
            name="config_assumptions_icr_higher_gte_basic",
        ),
    )
