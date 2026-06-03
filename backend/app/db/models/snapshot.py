"""
ORM models: all snapshot tables.

snapshot_calculations (root), snapshot_inputs, snapshot_outputs,
snapshot_intermediates, snapshot_risk_flags, snapshot_validation_warnings.

All snapshot tables are strictly immutable except:
  snapshot_calculations.is_superseded and superseded_at (the single
  permitted mutation, column-level UPDATE grant only).

Source: DATABASE_SCHEMA_DESIGN.md Sections 3 and 5.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    SmallInteger,
    String,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.domain.enums import (
    FlagSeverity,
    IncomeTaxBand,
    InputSource,
    MortgageType,
    OwnershipStructure,
    PropertyCountry,
    PropertyType,
    Tenure,
)


class SnapshotCalculation(Base):
    """Root snapshot record. Immutable except is_superseded/superseded_at."""

    __tablename__ = "snapshot_calculations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    deal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("deals.id", ondelete="RESTRICT"),
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    engine_version: Mapped[str] = mapped_column(String, nullable=False)
    assumption_config_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("config_assumption_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    sdlt_config_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("config_sdlt_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    corporation_tax_config_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("config_corporation_tax_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
    )
    is_superseded: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false"),
    )
    superseded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True,
    )
    calculation_duration_ms: Mapped[int | None] = mapped_column(
        Integer, nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint(
            "is_superseded = FALSE OR superseded_at IS NOT NULL",
            name="snapshot_superseded_timestamp_consistency",
        ),
        CheckConstraint(
            "calculated_at IS NOT NULL",
            name="snapshot_calculated_at_required",
        ),
    )


class SnapshotInputs(Base):
    """Complete input record for one calculation. Strictly immutable."""

    __tablename__ = "snapshot_inputs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("snapshot_calculations.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )

    # Required inputs
    purchase_price: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    monthly_rent: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    deposit_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    mortgage_interest_rate: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False,
    )
    mortgage_term_years: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    mortgage_type: Mapped[MortgageType] = mapped_column(
        SAEnum(MortgageType, name="mortgage_type_enum", create_type=False),
        nullable=False,
    )
    ownership_structure: Mapped[OwnershipStructure] = mapped_column(
        SAEnum(OwnershipStructure, name="ownership_structure_enum", create_type=False),
        nullable=False,
    )
    income_tax_band: Mapped[IncomeTaxBand | None] = mapped_column(
        SAEnum(IncomeTaxBand, name="income_tax_band_enum", create_type=False),
        nullable=True,
    )
    is_additional_dwelling: Mapped[bool] = mapped_column(Boolean, nullable=False)
    property_type: Mapped[PropertyType] = mapped_column(
        SAEnum(PropertyType, name="property_type_enum", create_type=False),
        nullable=False,
    )
    tenure: Mapped[Tenure] = mapped_column(
        SAEnum(Tenure, name="tenure_enum", create_type=False),
        nullable=False,
    )
    property_country: Mapped[PropertyCountry] = mapped_column(
        SAEnum(PropertyCountry, name="property_country_enum", create_type=False),
        nullable=False,
    )
    postcode: Mapped[str] = mapped_column(String, nullable=False)
    lease_years_remaining: Mapped[int | None] = mapped_column(
        SmallInteger, nullable=True,
    )

    # Optional inputs with source provenance
    void_rate_percent: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False,
    )
    void_rate_percent_source: Mapped[InputSource] = mapped_column(
        SAEnum(InputSource, name="input_source_enum", create_type=False),
        nullable=False,
    )
    letting_agent_fee_percent: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False,
    )
    letting_agent_fee_percent_source: Mapped[InputSource] = mapped_column(
        SAEnum(InputSource, name="input_source_enum", create_type=False),
        nullable=False,
    )
    maintenance_reserve_percent: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False,
    )
    maintenance_reserve_percent_source: Mapped[InputSource] = mapped_column(
        SAEnum(InputSource, name="input_source_enum", create_type=False),
        nullable=False,
    )
    landlord_insurance_annual: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    landlord_insurance_annual_source: Mapped[InputSource] = mapped_column(
        SAEnum(InputSource, name="input_source_enum", create_type=False),
        nullable=False,
    )
    purchase_legal_costs: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    purchase_legal_costs_source: Mapped[InputSource] = mapped_column(
        SAEnum(InputSource, name="input_source_enum", create_type=False),
        nullable=False,
    )
    refurbishment_cost: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    refurbishment_cost_source: Mapped[InputSource] = mapped_column(
        SAEnum(InputSource, name="input_source_enum", create_type=False),
        nullable=False,
    )
    annual_service_charge: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    annual_service_charge_source: Mapped[InputSource] = mapped_column(
        SAEnum(InputSource, name="input_source_enum", create_type=False),
        nullable=False,
    )
    annual_ground_rent: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    annual_ground_rent_source: Mapped[InputSource] = mapped_column(
        SAEnum(InputSource, name="input_source_enum", create_type=False),
        nullable=False,
    )
    annual_accountancy_cost: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    annual_accountancy_cost_source: Mapped[InputSource] = mapped_column(
        SAEnum(InputSource, name="input_source_enum", create_type=False),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint(
            "purchase_price > 0",
            name="snapshot_inputs_purchase_price_positive",
        ),
        CheckConstraint(
            "monthly_rent > 0",
            name="snapshot_inputs_monthly_rent_positive",
        ),
        CheckConstraint(
            "deposit_amount > 0 AND deposit_amount < purchase_price",
            name="snapshot_inputs_deposit_valid",
        ),
        CheckConstraint(
            "mortgage_interest_rate >= 0",
            name="snapshot_inputs_rate_non_negative",
        ),
        CheckConstraint(
            "mortgage_term_years >= 5 AND mortgage_term_years <= 35",
            name="snapshot_inputs_term_range",
        ),
        CheckConstraint(
            "void_rate_percent >= 0 AND void_rate_percent <= 100",
            name="snapshot_inputs_void_rate_range",
        ),
        CheckConstraint(
            "refurbishment_cost >= 0",
            name="snapshot_inputs_refurb_non_negative",
        ),
        CheckConstraint(
            "annual_service_charge >= 0",
            name="snapshot_inputs_service_charge_non_negative",
        ),
        CheckConstraint(
            "annual_ground_rent >= 0",
            name="snapshot_inputs_ground_rent_non_negative",
        ),
        CheckConstraint(
            "annual_accountancy_cost >= 0",
            name="snapshot_inputs_accountancy_non_negative",
        ),
        CheckConstraint(
            "(ownership_structure = 'INDIVIDUAL' AND income_tax_band IS NOT NULL)"
            " OR (ownership_structure = 'LIMITED_COMPANY' AND income_tax_band IS NULL)",
            name="snapshot_inputs_tax_band_consistency",
        ),
    )


class SnapshotOutputs(Base):
    """All user-facing output metrics. Strictly immutable."""

    __tablename__ = "snapshot_outputs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("snapshot_calculations.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )

    gross_annual_rent_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    effective_annual_rent_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    total_operating_costs_annual_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    net_operating_income_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    annual_mortgage_cost_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    annual_tax_liability_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    annual_cash_flow_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    monthly_cash_flow_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    gross_yield_percent: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False,
    )
    net_yield_percent: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False,
    )
    roce_percent: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False,
    )
    cash_on_cash_return_percent: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False,
    )
    ltv_percent: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False,
    )
    icr_percent: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=10, scale=6), nullable=True,
    )
    total_sdlt_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    total_acquisition_cost_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    total_cash_deployed_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint(
            "gross_annual_rent_gbp >= 0",
            name="snapshot_outputs_gross_rent_non_negative",
        ),
        CheckConstraint(
            "effective_annual_rent_gbp >= 0",
            name="snapshot_outputs_effective_rent_non_negative",
        ),
        CheckConstraint(
            "total_operating_costs_annual_gbp >= 0",
            name="snapshot_outputs_operating_costs_non_negative",
        ),
        CheckConstraint(
            "annual_tax_liability_gbp >= 0",
            name="snapshot_outputs_tax_non_negative",
        ),
        CheckConstraint(
            "total_sdlt_gbp >= 0",
            name="snapshot_outputs_sdlt_non_negative",
        ),
        CheckConstraint(
            "total_acquisition_cost_gbp >= 0",
            name="snapshot_outputs_acquisition_cost_non_negative",
        ),
        CheckConstraint(
            "total_cash_deployed_gbp >= 0",
            name="snapshot_outputs_cash_deployed_non_negative",
        ),
        CheckConstraint(
            "ltv_percent >= 0 AND ltv_percent <= 100",
            name="snapshot_outputs_ltv_range",
        ),
        CheckConstraint(
            "icr_percent IS NULL OR icr_percent >= 0",
            name="snapshot_outputs_icr_non_negative",
        ),
        CheckConstraint(
            "gross_yield_percent >= 0",
            name="snapshot_outputs_gross_yield_non_negative",
        ),
    )


class SnapshotIntermediates(Base):
    """All intermediate engine values. Strictly immutable."""

    __tablename__ = "snapshot_intermediates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("snapshot_calculations.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )

    void_rate_decimal_applied: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=10), nullable=False,
    )
    gross_annual_rent_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    effective_annual_rent_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    loan_amount_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    ltv_percent: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False,
    )
    monthly_mortgage_payment_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    annual_mortgage_cost_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    annual_mortgage_interest_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    letting_agent_annual_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    letting_agent_vat_rate_applied: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False,
    )
    annual_maintenance_reserve_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    total_operating_costs_annual_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    net_operating_income_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    sdlt_band_breakdown: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    sdlt_base_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    sdlt_surcharge_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    sdlt_surcharge_rate_applied: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False,
    )
    total_sdlt_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    total_acquisition_cost_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    total_cash_deployed_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    stressed_annual_interest_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    stress_test_rate_applied_percent: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=6), nullable=False,
    )
    taxable_income_or_profit_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    income_tax_gross_gbp: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=15, scale=6), nullable=True,
    )
    mortgage_interest_tax_credit_gbp: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=15, scale=6), nullable=True,
    )
    corporation_tax_gross_gbp: Mapped[Decimal | None] = mapped_column(
        Numeric(precision=15, scale=6), nullable=True,
    )
    annual_tax_liability_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    pre_tax_annual_cash_flow_gbp: Mapped[Decimal] = mapped_column(
        Numeric(precision=15, scale=6), nullable=False,
    )
    section_24_applies: Mapped[bool] = mapped_column(Boolean, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint(
            "void_rate_decimal_applied >= 0 AND void_rate_decimal_applied <= 1",
            name="snapshot_intermediates_void_rate_range",
        ),
        CheckConstraint(
            "loan_amount_gbp >= 0",
            name="snapshot_intermediates_loan_non_negative",
        ),
        CheckConstraint(
            "sdlt_base_gbp >= 0",
            name="snapshot_intermediates_sdlt_base_non_negative",
        ),
        CheckConstraint(
            "sdlt_surcharge_gbp >= 0",
            name="snapshot_intermediates_sdlt_surcharge_non_negative",
        ),
        CheckConstraint(
            "total_sdlt_gbp >= 0",
            name="snapshot_intermediates_total_sdlt_non_negative",
        ),
        CheckConstraint(
            "annual_tax_liability_gbp >= 0",
            name="snapshot_intermediates_tax_non_negative",
        ),
        CheckConstraint(
            "income_tax_gross_gbp IS NULL OR income_tax_gross_gbp >= 0",
            name="snapshot_intermediates_income_tax_non_negative",
        ),
        CheckConstraint(
            "mortgage_interest_tax_credit_gbp IS NULL OR mortgage_interest_tax_credit_gbp >= 0",
            name="snapshot_intermediates_tax_credit_non_negative",
        ),
        CheckConstraint(
            "corporation_tax_gross_gbp IS NULL OR corporation_tax_gross_gbp >= 0",
            name="snapshot_intermediates_corp_tax_non_negative",
        ),
    )


class SnapshotRiskFlag(Base):
    """One row per triggered risk flag. Strictly immutable."""

    __tablename__ = "snapshot_risk_flags"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("snapshot_calculations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    flag_code: Mapped[str] = mapped_column(String, nullable=False)
    severity: Mapped[FlagSeverity] = mapped_column(
        SAEnum(FlagSeverity, name="flag_severity_enum", create_type=False),
        nullable=False,
    )
    triggered_by_field: Mapped[str] = mapped_column(String, nullable=False)
    triggered_by_value: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint("flag_code <> ''", name="snapshot_risk_flags_code_non_empty"),
        CheckConstraint("triggered_by_field <> ''", name="snapshot_risk_flags_field_non_empty"),
        CheckConstraint("triggered_by_value <> ''", name="snapshot_risk_flags_value_non_empty"),
        CheckConstraint("message <> ''", name="snapshot_risk_flags_message_non_empty"),
    )


class SnapshotValidationWarning(Base):
    """One row per validation warning. Strictly immutable."""

    __tablename__ = "snapshot_validation_warnings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=text("gen_random_uuid()"),
    )
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("snapshot_calculations.id", ondelete="RESTRICT"),
        nullable=False,
    )
    rule_code: Mapped[str] = mapped_column(String, nullable=False)
    field: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint(
            r"rule_code ~ '^V-[0-9]+$'",
            name="snapshot_validation_warnings_rule_code_format",
        ),
        CheckConstraint("field <> ''", name="snapshot_validation_warnings_field_non_empty"),
        CheckConstraint("message <> ''", name="snapshot_validation_warnings_message_non_empty"),
    )
