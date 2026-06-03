"""initial schema — all Phase 1 tables

Revision ID: 0001
Revises: —
Create Date: 2026-06-03

Creates all Phase 1 PostgreSQL enum types, the PostGIS extension, all
tables, all CHECK constraints, all FK constraints (ON DELETE RESTRICT),
all UNIQUE constraints, and all indexes defined in
DATABASE_SCHEMA_DESIGN.md Sections 1–8.

Creation order follows FK dependency graph. The circular reference between
deals.latest_snapshot_id → snapshot_calculations and
snapshot_calculations.deal_id → deals is resolved by creating
deals.latest_snapshot_id as a bare nullable column first, then adding the
FK constraint after snapshot_calculations exists.

Downgrade: no-op with explanation.
Per PERSISTENCE_ARCHITECTURE.md Part 14.2 — migrations that create
immutable tables (snapshot_*, config_*, audit_calculations) are
irreversible. Dropping snapshot tables would permanently destroy
calculation history. Forward-only in production; in development, recreate
with a fresh database rather than running downgrade.

Architecture:
  DATABASE_SCHEMA_DESIGN.md  — authoritative schema definition
  PERSISTENCE_ARCHITECTURE.md Part 14 — migration philosophy
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Step 1 — PostgreSQL extensions
    # ------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # ------------------------------------------------------------------
    # Step 2 — PostgreSQL enum types
    # All enums use UPPER_SNAKE_CASE values per DATABASE_SCHEMA_DESIGN.md
    # Section 1. create_type=False on ORM models; the type is created here
    # once and reused across tables.
    # ------------------------------------------------------------------
    op.execute(
        "CREATE TYPE ownership_structure_enum AS ENUM "
        "('INDIVIDUAL', 'LIMITED_COMPANY')"
    )
    op.execute(
        "CREATE TYPE income_tax_band_enum AS ENUM "
        "('BASIC_RATE', 'HIGHER_RATE', 'ADDITIONAL_RATE')"
    )
    op.execute(
        "CREATE TYPE mortgage_type_enum AS ENUM "
        "('INTEREST_ONLY', 'REPAYMENT')"
    )
    op.execute(
        "CREATE TYPE property_type_enum AS ENUM "
        "('RESIDENTIAL_SINGLE_LET')"
    )
    op.execute(
        "CREATE TYPE tenure_enum AS ENUM "
        "('FREEHOLD', 'LEASEHOLD')"
    )
    op.execute(
        "CREATE TYPE property_country_enum AS ENUM "
        "('ENGLAND')"
    )
    op.execute(
        "CREATE TYPE deal_status_enum AS ENUM "
        "('DRAFT', 'ANALYSED', 'ARCHIVED')"
    )
    op.execute(
        "CREATE TYPE user_status_enum AS ENUM "
        "('ACTIVE', 'SUSPENDED', 'ARCHIVED')"
    )
    op.execute(
        "CREATE TYPE calculation_outcome_enum AS ENUM "
        "('SUCCESS', 'VALIDATION_FAILURE', 'ENGINE_ERROR')"
    )
    op.execute(
        "CREATE TYPE input_source_enum AS ENUM "
        "('USER_OVERRIDE', 'CONFIG_DEFAULT')"
    )
    op.execute(
        "CREATE TYPE flag_severity_enum AS ENUM "
        "('HIGH', 'MEDIUM', 'INFO')"
    )

    # ------------------------------------------------------------------
    # Step 3 — users
    # No FK dependencies.
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("supabase_auth_id", UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(name="user_status_enum", create_type=False),
            nullable=False,
            server_default="ACTIVE",
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("supabase_auth_id", name="uq_users_supabase_auth_id"),
        sa.CheckConstraint(
            r"email ~* '^[^@]+@[^@]+\.[^@]+$'",
            name="users_email_format",
        ),
    )
    op.create_index("ix_users_email", "users", ["email"])

    # ------------------------------------------------------------------
    # Step 4 — investor_profiles
    # FK → users
    # ------------------------------------------------------------------
    op.create_table(
        "investor_profiles",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column(
            "ownership_structure",
            sa.Enum(name="ownership_structure_enum", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "income_tax_band",
            sa.Enum(name="income_tax_band_enum", create_type=False),
            nullable=True,
        ),
        sa.Column(
            "is_default",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("archived_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_investor_profiles_users",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "(ownership_structure = 'INDIVIDUAL' AND income_tax_band IS NOT NULL)"
            " OR (ownership_structure = 'LIMITED_COMPANY' AND income_tax_band IS NULL)",
            name="investor_profiles_tax_band_consistency",
        ),
    )
    op.create_index("ix_investor_profiles_user_id", "investor_profiles", ["user_id"])

    # ------------------------------------------------------------------
    # Step 5 — properties
    # FK → users
    # ------------------------------------------------------------------
    op.create_table(
        "properties",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("address_line_1", sa.Text(), nullable=False),
        sa.Column("address_line_2", sa.Text(), nullable=True),
        sa.Column("city", sa.Text(), nullable=False),
        sa.Column("postcode", sa.Text(), nullable=False),
        sa.Column(
            "property_type",
            sa.Enum(name="property_type_enum", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "tenure",
            sa.Enum(name="tenure_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("lease_years_remaining", sa.Integer(), nullable=True),
        sa.Column("bedrooms", sa.SmallInteger(), nullable=True),
        sa.Column("epc_rating", sa.String(1), nullable=True),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("archived_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_properties_users",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            r"postcode ~ '^[A-Z]{1,2}[0-9][0-9A-Z]?\s*[0-9][A-Z]{2}$'",
            name="properties_postcode_format",
        ),
        sa.CheckConstraint(
            "lease_years_remaining IS NULL OR lease_years_remaining > 0",
            name="properties_lease_years_positive",
        ),
        sa.CheckConstraint(
            "bedrooms IS NULL OR bedrooms > 0",
            name="properties_bedrooms_positive",
        ),
        sa.CheckConstraint(
            "epc_rating IS NULL OR epc_rating IN ('A','B','C','D','E','F','G')",
            name="properties_epc_valid",
        ),
        sa.CheckConstraint(
            "NOT (tenure = 'LEASEHOLD' AND lease_years_remaining IS NULL)",
            name="properties_leasehold_requires_lease_years",
        ),
    )
    op.create_index("ix_properties_user_id", "properties", ["user_id"])
    op.create_index("ix_properties_postcode", "properties", ["postcode"])

    # ------------------------------------------------------------------
    # Step 6 — deals
    # FK → users, properties.
    # latest_snapshot_id FK → snapshot_calculations added after Step 11
    # to resolve the circular reference.
    # ------------------------------------------------------------------
    op.create_table(
        "deals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("property_id", UUID(as_uuid=True), nullable=False),
        sa.Column("investor_profile_id", UUID(as_uuid=True), nullable=True),
        sa.Column("label", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum(name="deal_status_enum", create_type=False),
            nullable=False,
            server_default="DRAFT",
        ),
        # latest_snapshot_id — FK added after snapshot_calculations exists
        sa.Column("latest_snapshot_id", UUID(as_uuid=True), nullable=True),
        # Working input fields — nullable; populated as user enters values
        sa.Column("purchase_price", sa.Numeric(15, 6), nullable=True),
        sa.Column("monthly_rent", sa.Numeric(15, 6), nullable=True),
        sa.Column("deposit_amount", sa.Numeric(15, 6), nullable=True),
        sa.Column("mortgage_interest_rate", sa.Numeric(10, 6), nullable=True),
        sa.Column("mortgage_term_years", sa.SmallInteger(), nullable=True),
        sa.Column(
            "mortgage_type",
            sa.Enum(name="mortgage_type_enum", create_type=False),
            nullable=True,
        ),
        sa.Column(
            "ownership_structure",
            sa.Enum(name="ownership_structure_enum", create_type=False),
            nullable=True,
        ),
        sa.Column(
            "income_tax_band",
            sa.Enum(name="income_tax_band_enum", create_type=False),
            nullable=True,
        ),
        sa.Column("is_additional_dwelling", sa.Boolean(), nullable=True),
        sa.Column("void_rate_percent", sa.Numeric(10, 6), nullable=True),
        sa.Column("letting_agent_fee_percent", sa.Numeric(10, 6), nullable=True),
        sa.Column("maintenance_reserve_percent", sa.Numeric(10, 6), nullable=True),
        sa.Column("landlord_insurance_annual", sa.Numeric(15, 6), nullable=True),
        sa.Column("purchase_legal_costs", sa.Numeric(15, 6), nullable=True),
        sa.Column("refurbishment_cost", sa.Numeric(15, 6), nullable=True),
        sa.Column("annual_service_charge", sa.Numeric(15, 6), nullable=True),
        sa.Column("annual_ground_rent", sa.Numeric(15, 6), nullable=True),
        sa.Column("annual_accountancy_cost", sa.Numeric(15, 6), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_deals_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["property_id"], ["properties.id"],
            name="fk_deals_properties",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["investor_profile_id"], ["investor_profiles.id"],
            name="fk_deals_investor_profiles",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "purchase_price IS NULL OR purchase_price > 0",
            name="deals_purchase_price_positive",
        ),
        sa.CheckConstraint(
            "monthly_rent IS NULL OR monthly_rent > 0",
            name="deals_monthly_rent_positive",
        ),
        sa.CheckConstraint(
            "deposit_amount IS NULL OR deposit_amount > 0",
            name="deals_deposit_positive",
        ),
        sa.CheckConstraint(
            "mortgage_interest_rate IS NULL OR mortgage_interest_rate >= 0",
            name="deals_rate_non_negative",
        ),
        sa.CheckConstraint(
            "mortgage_term_years IS NULL"
            " OR (mortgage_term_years >= 5 AND mortgage_term_years <= 35)",
            name="deals_term_range",
        ),
        sa.CheckConstraint(
            "refurbishment_cost IS NULL OR refurbishment_cost >= 0",
            name="deals_refurb_non_negative",
        ),
        sa.CheckConstraint(
            "annual_service_charge IS NULL OR annual_service_charge >= 0",
            name="deals_service_charge_non_negative",
        ),
        sa.CheckConstraint(
            "annual_ground_rent IS NULL OR annual_ground_rent >= 0",
            name="deals_ground_rent_non_negative",
        ),
    )
    op.create_index("ix_deals_user_id", "deals", ["user_id"])
    op.create_index("ix_deals_property_id", "deals", ["property_id"])
    op.create_index("ix_deals_latest_snapshot_id", "deals", ["latest_snapshot_id"])

    # ------------------------------------------------------------------
    # Step 7 — config_engine_versions
    # No FK dependencies. Uses version string as PK (TEXT, not UUID).
    # ------------------------------------------------------------------
    op.create_table(
        "config_engine_versions",
        sa.Column("version_string", sa.Text(), primary_key=True),
        sa.Column("released_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("change_summary", sa.Text(), nullable=False),
        sa.Column("is_breaking_change", sa.Boolean(), nullable=False),
        sa.Column("specification_ref", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ------------------------------------------------------------------
    # Step 8 — config_sdlt_versions + config_sdlt_bands
    # config_sdlt_versions FK → users (nullable created_by_user_id)
    # config_sdlt_bands FK → config_sdlt_versions
    # ------------------------------------------------------------------
    op.create_table(
        "config_sdlt_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column(
            "property_country",
            sa.Enum(name="property_country_enum", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "additional_dwelling_surcharge_rate",
            sa.Numeric(10, 6),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_attribution", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by_user_id", UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"],
            name="fk_config_sdlt_versions_users",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "effective_from", "property_country",
            name="uq_config_sdlt_versions_effective_country",
        ),
        sa.CheckConstraint(
            "additional_dwelling_surcharge_rate >= 0"
            " AND additional_dwelling_surcharge_rate <= 1",
            name="config_sdlt_versions_surcharge_rate_range",
        ),
    )
    op.create_index(
        "ix_config_sdlt_versions_effective_from",
        "config_sdlt_versions",
        [sa.text("effective_from DESC")],
    )
    op.create_index(
        "ix_config_sdlt_versions_country_effective_from",
        "config_sdlt_versions",
        ["property_country", sa.text("effective_from DESC")],
    )

    op.create_table(
        "config_sdlt_bands",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("sdlt_version_id", UUID(as_uuid=True), nullable=False),
        sa.Column("band_order", sa.SmallInteger(), nullable=False),
        sa.Column("band_lower", sa.Numeric(15, 6), nullable=False),
        sa.Column("band_upper", sa.Numeric(15, 6), nullable=True),
        sa.Column("rate", sa.Numeric(10, 6), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["sdlt_version_id"], ["config_sdlt_versions.id"],
            name="fk_config_sdlt_bands_sdlt_versions",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "sdlt_version_id", "band_order",
            name="uq_config_sdlt_bands_version_order",
        ),
        sa.CheckConstraint(
            "band_lower >= 0",
            name="config_sdlt_bands_lower_non_negative",
        ),
        sa.CheckConstraint(
            "band_upper IS NULL OR band_upper > band_lower",
            name="config_sdlt_bands_upper_gt_lower",
        ),
        sa.CheckConstraint(
            "rate >= 0 AND rate <= 1",
            name="config_sdlt_bands_rate_range",
        ),
        sa.CheckConstraint(
            "band_order > 0",
            name="config_sdlt_bands_order_positive",
        ),
    )
    op.create_index(
        "ix_config_sdlt_bands_version_order",
        "config_sdlt_bands",
        ["sdlt_version_id", "band_order"],
    )

    # ------------------------------------------------------------------
    # Step 9 — config_corporation_tax_versions
    # FK → users (nullable created_by_user_id)
    # ------------------------------------------------------------------
    op.create_table(
        "config_corporation_tax_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("small_profits_rate", sa.Numeric(10, 6), nullable=False),
        sa.Column("small_profits_upper_threshold", sa.Numeric(15, 6), nullable=False),
        sa.Column("main_rate", sa.Numeric(10, 6), nullable=False),
        sa.Column("main_rate_lower_threshold", sa.Numeric(15, 6), nullable=False),
        sa.Column("marginal_relief_numerator", sa.SmallInteger(), nullable=False),
        sa.Column("marginal_relief_denominator", sa.SmallInteger(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_attribution", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by_user_id", UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"],
            name="fk_config_ct_versions_users",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "effective_from",
            name="uq_config_ct_versions_effective_from",
        ),
        sa.CheckConstraint(
            "small_profits_rate >= 0 AND small_profits_rate <= 1",
            name="config_ct_small_profits_rate_range",
        ),
        sa.CheckConstraint(
            "main_rate >= 0 AND main_rate <= 1",
            name="config_ct_main_rate_range",
        ),
        sa.CheckConstraint(
            "small_profits_upper_threshold < main_rate_lower_threshold",
            name="config_ct_threshold_ordering",
        ),
        sa.CheckConstraint(
            "marginal_relief_numerator > 0",
            name="config_ct_numerator_positive",
        ),
        sa.CheckConstraint(
            "marginal_relief_denominator > 0",
            name="config_ct_denominator_positive",
        ),
    )
    op.create_index(
        "ix_config_ct_versions_effective_from",
        "config_corporation_tax_versions",
        [sa.text("effective_from DESC")],
    )

    # ------------------------------------------------------------------
    # Step 10 — config_assumption_versions
    # FK → users (nullable created_by_user_id)
    # ------------------------------------------------------------------
    op.create_table(
        "config_assumption_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("void_rate_percent_default", sa.Numeric(10, 6), nullable=False),
        sa.Column(
            "letting_agent_fee_percent_default", sa.Numeric(10, 6), nullable=False
        ),
        sa.Column("letting_agent_vat_rate_percent", sa.Numeric(10, 6), nullable=False),
        sa.Column(
            "maintenance_reserve_percent_default", sa.Numeric(10, 6), nullable=False
        ),
        sa.Column(
            "landlord_insurance_annual_default", sa.Numeric(15, 6), nullable=False
        ),
        sa.Column("purchase_legal_costs_default", sa.Numeric(15, 6), nullable=False),
        sa.Column(
            "accountancy_cost_individual_default", sa.Numeric(15, 6), nullable=False
        ),
        sa.Column(
            "accountancy_cost_ltd_default", sa.Numeric(15, 6), nullable=False
        ),
        sa.Column("stress_test_rate_percent", sa.Numeric(10, 6), nullable=False),
        sa.Column(
            "icr_threshold_basic_rate_percent", sa.Numeric(10, 6), nullable=False
        ),
        sa.Column(
            "icr_threshold_higher_rate_percent", sa.Numeric(10, 6), nullable=False
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("source_attribution", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("created_by_user_id", UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"],
            name="fk_config_assumption_versions_users",
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint(
            "effective_from",
            name="uq_config_assumption_versions_effective_from",
        ),
        sa.CheckConstraint(
            "void_rate_percent_default >= 0 AND void_rate_percent_default <= 100",
            name="config_assumptions_void_rate_range",
        ),
        sa.CheckConstraint(
            "letting_agent_fee_percent_default >= 0",
            name="config_assumptions_letting_fee_non_negative",
        ),
        sa.CheckConstraint(
            "letting_agent_vat_rate_percent >= 0",
            name="config_assumptions_vat_rate_non_negative",
        ),
        sa.CheckConstraint(
            "maintenance_reserve_percent_default >= 0",
            name="config_assumptions_maintenance_non_negative",
        ),
        sa.CheckConstraint(
            "landlord_insurance_annual_default >= 0",
            name="config_assumptions_insurance_non_negative",
        ),
        sa.CheckConstraint(
            "purchase_legal_costs_default >= 0",
            name="config_assumptions_legal_costs_non_negative",
        ),
        sa.CheckConstraint(
            "accountancy_cost_individual_default >= 0",
            name="config_assumptions_accountancy_individual_non_negative",
        ),
        sa.CheckConstraint(
            "accountancy_cost_ltd_default >= 0",
            name="config_assumptions_accountancy_ltd_non_negative",
        ),
        sa.CheckConstraint(
            "stress_test_rate_percent > 0",
            name="config_assumptions_stress_rate_positive",
        ),
        sa.CheckConstraint(
            "icr_threshold_basic_rate_percent > 0",
            name="config_assumptions_icr_basic_positive",
        ),
        sa.CheckConstraint(
            "icr_threshold_higher_rate_percent >= icr_threshold_basic_rate_percent",
            name="config_assumptions_icr_higher_gte_basic",
        ),
    )
    op.create_index(
        "ix_config_assumption_versions_effective_from",
        "config_assumption_versions",
        [sa.text("effective_from DESC")],
    )

    # ------------------------------------------------------------------
    # Step 11 — snapshot_calculations
    # FK → deals, users, config_assumption_versions, config_sdlt_versions,
    #      config_corporation_tax_versions.
    # ------------------------------------------------------------------
    op.create_table(
        "snapshot_calculations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("deal_id", UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("engine_version", sa.Text(), nullable=False),
        sa.Column(
            "assumption_config_version_id", UUID(as_uuid=True), nullable=False
        ),
        sa.Column("sdlt_config_version_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "corporation_tax_config_version_id", UUID(as_uuid=True), nullable=False
        ),
        sa.Column("calculated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "is_superseded",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
        sa.Column("superseded_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("calculation_duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["deal_id"], ["deals.id"],
            name="fk_snapshot_calculations_deals",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_snapshot_calculations_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["assumption_config_version_id"], ["config_assumption_versions.id"],
            name="fk_snapshot_calculations_assumption_config",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["sdlt_config_version_id"], ["config_sdlt_versions.id"],
            name="fk_snapshot_calculations_sdlt_config",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["corporation_tax_config_version_id"],
            ["config_corporation_tax_versions.id"],
            name="fk_snapshot_calculations_ct_config",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "is_superseded = FALSE OR superseded_at IS NOT NULL",
            name="snapshot_superseded_timestamp_consistency",
        ),
        sa.CheckConstraint(
            "calculated_at IS NOT NULL",
            name="snapshot_calculated_at_required",
        ),
    )
    op.create_index(
        "ix_snapshot_calculations_deal_id",
        "snapshot_calculations",
        ["deal_id"],
    )
    op.create_index(
        "ix_snapshot_calculations_deal_id_is_superseded",
        "snapshot_calculations",
        ["deal_id", "is_superseded"],
    )
    op.create_index(
        "ix_snapshot_calculations_user_id",
        "snapshot_calculations",
        ["user_id"],
    )
    op.create_index(
        "ix_snapshot_calculations_engine_version",
        "snapshot_calculations",
        ["engine_version"],
    )

    # ------------------------------------------------------------------
    # Step 11b — resolve the circular FK:
    # deals.latest_snapshot_id → snapshot_calculations.id
    # ------------------------------------------------------------------
    op.create_foreign_key(
        "fk_deals_snapshot_calculations",
        "deals",
        "snapshot_calculations",
        ["latest_snapshot_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # ------------------------------------------------------------------
    # Step 12 — snapshot_inputs
    # FK → snapshot_calculations (UNIQUE enforces 1:1)
    # ------------------------------------------------------------------
    op.create_table(
        "snapshot_inputs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("snapshot_id", UUID(as_uuid=True), nullable=False),
        # Required inputs
        sa.Column("purchase_price", sa.Numeric(15, 6), nullable=False),
        sa.Column("monthly_rent", sa.Numeric(15, 6), nullable=False),
        sa.Column("deposit_amount", sa.Numeric(15, 6), nullable=False),
        sa.Column("mortgage_interest_rate", sa.Numeric(10, 6), nullable=False),
        sa.Column("mortgage_term_years", sa.SmallInteger(), nullable=False),
        sa.Column(
            "mortgage_type",
            sa.Enum(name="mortgage_type_enum", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "ownership_structure",
            sa.Enum(name="ownership_structure_enum", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "income_tax_band",
            sa.Enum(name="income_tax_band_enum", create_type=False),
            nullable=True,
        ),
        sa.Column("is_additional_dwelling", sa.Boolean(), nullable=False),
        sa.Column(
            "property_type",
            sa.Enum(name="property_type_enum", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "tenure",
            sa.Enum(name="tenure_enum", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "property_country",
            sa.Enum(name="property_country_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("postcode", sa.Text(), nullable=False),
        sa.Column("lease_years_remaining", sa.SmallInteger(), nullable=True),
        # Optional inputs with source provenance
        sa.Column("void_rate_percent", sa.Numeric(10, 6), nullable=False),
        sa.Column(
            "void_rate_percent_source",
            sa.Enum(name="input_source_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("letting_agent_fee_percent", sa.Numeric(10, 6), nullable=False),
        sa.Column(
            "letting_agent_fee_percent_source",
            sa.Enum(name="input_source_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("maintenance_reserve_percent", sa.Numeric(10, 6), nullable=False),
        sa.Column(
            "maintenance_reserve_percent_source",
            sa.Enum(name="input_source_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("landlord_insurance_annual", sa.Numeric(15, 6), nullable=False),
        sa.Column(
            "landlord_insurance_annual_source",
            sa.Enum(name="input_source_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("purchase_legal_costs", sa.Numeric(15, 6), nullable=False),
        sa.Column(
            "purchase_legal_costs_source",
            sa.Enum(name="input_source_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("refurbishment_cost", sa.Numeric(15, 6), nullable=False),
        sa.Column(
            "refurbishment_cost_source",
            sa.Enum(name="input_source_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("annual_service_charge", sa.Numeric(15, 6), nullable=False),
        sa.Column(
            "annual_service_charge_source",
            sa.Enum(name="input_source_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("annual_ground_rent", sa.Numeric(15, 6), nullable=False),
        sa.Column(
            "annual_ground_rent_source",
            sa.Enum(name="input_source_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("annual_accountancy_cost", sa.Numeric(15, 6), nullable=False),
        sa.Column(
            "annual_accountancy_cost_source",
            sa.Enum(name="input_source_enum", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["snapshot_calculations.id"],
            name="fk_snapshot_inputs_snapshot_calculations",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "purchase_price > 0",
            name="snapshot_inputs_purchase_price_positive",
        ),
        sa.CheckConstraint(
            "monthly_rent > 0",
            name="snapshot_inputs_monthly_rent_positive",
        ),
        sa.CheckConstraint(
            "deposit_amount > 0 AND deposit_amount < purchase_price",
            name="snapshot_inputs_deposit_valid",
        ),
        sa.CheckConstraint(
            "mortgage_interest_rate >= 0",
            name="snapshot_inputs_rate_non_negative",
        ),
        sa.CheckConstraint(
            "mortgage_term_years >= 5 AND mortgage_term_years <= 35",
            name="snapshot_inputs_term_range",
        ),
        sa.CheckConstraint(
            "void_rate_percent >= 0 AND void_rate_percent <= 100",
            name="snapshot_inputs_void_rate_range",
        ),
        sa.CheckConstraint(
            "refurbishment_cost >= 0",
            name="snapshot_inputs_refurb_non_negative",
        ),
        sa.CheckConstraint(
            "annual_service_charge >= 0",
            name="snapshot_inputs_service_charge_non_negative",
        ),
        sa.CheckConstraint(
            "annual_ground_rent >= 0",
            name="snapshot_inputs_ground_rent_non_negative",
        ),
        sa.CheckConstraint(
            "annual_accountancy_cost >= 0",
            name="snapshot_inputs_accountancy_non_negative",
        ),
        sa.CheckConstraint(
            "(ownership_structure = 'INDIVIDUAL' AND income_tax_band IS NOT NULL)"
            " OR (ownership_structure = 'LIMITED_COMPANY' AND income_tax_band IS NULL)",
            name="snapshot_inputs_tax_band_consistency",
        ),
    )
    op.create_index(
        "ix_snapshot_inputs_snapshot_id",
        "snapshot_inputs",
        ["snapshot_id"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # Step 13 — snapshot_outputs
    # FK → snapshot_calculations (UNIQUE enforces 1:1)
    # ------------------------------------------------------------------
    op.create_table(
        "snapshot_outputs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("snapshot_id", UUID(as_uuid=True), nullable=False),
        sa.Column("gross_annual_rent_gbp", sa.Numeric(15, 6), nullable=False),
        sa.Column("effective_annual_rent_gbp", sa.Numeric(15, 6), nullable=False),
        sa.Column(
            "total_operating_costs_annual_gbp", sa.Numeric(15, 6), nullable=False
        ),
        sa.Column("net_operating_income_gbp", sa.Numeric(15, 6), nullable=False),
        sa.Column("annual_mortgage_cost_gbp", sa.Numeric(15, 6), nullable=False),
        sa.Column("annual_tax_liability_gbp", sa.Numeric(15, 6), nullable=False),
        sa.Column("annual_cash_flow_gbp", sa.Numeric(15, 6), nullable=False),
        sa.Column("monthly_cash_flow_gbp", sa.Numeric(15, 6), nullable=False),
        sa.Column("gross_yield_percent", sa.Numeric(10, 6), nullable=False),
        sa.Column("net_yield_percent", sa.Numeric(10, 6), nullable=False),
        sa.Column("roce_percent", sa.Numeric(10, 6), nullable=False),
        sa.Column("cash_on_cash_return_percent", sa.Numeric(10, 6), nullable=False),
        sa.Column("ltv_percent", sa.Numeric(10, 6), nullable=False),
        sa.Column("icr_percent", sa.Numeric(10, 6), nullable=True),
        sa.Column("total_sdlt_gbp", sa.Numeric(15, 6), nullable=False),
        sa.Column("total_acquisition_cost_gbp", sa.Numeric(15, 6), nullable=False),
        sa.Column("total_cash_deployed_gbp", sa.Numeric(15, 6), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["snapshot_calculations.id"],
            name="fk_snapshot_outputs_snapshot_calculations",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "gross_annual_rent_gbp >= 0",
            name="snapshot_outputs_gross_rent_non_negative",
        ),
        sa.CheckConstraint(
            "effective_annual_rent_gbp >= 0",
            name="snapshot_outputs_effective_rent_non_negative",
        ),
        sa.CheckConstraint(
            "total_operating_costs_annual_gbp >= 0",
            name="snapshot_outputs_operating_costs_non_negative",
        ),
        sa.CheckConstraint(
            "annual_tax_liability_gbp >= 0",
            name="snapshot_outputs_tax_non_negative",
        ),
        sa.CheckConstraint(
            "total_sdlt_gbp >= 0",
            name="snapshot_outputs_sdlt_non_negative",
        ),
        sa.CheckConstraint(
            "total_acquisition_cost_gbp >= 0",
            name="snapshot_outputs_acquisition_cost_non_negative",
        ),
        sa.CheckConstraint(
            "total_cash_deployed_gbp >= 0",
            name="snapshot_outputs_cash_deployed_non_negative",
        ),
        sa.CheckConstraint(
            "ltv_percent >= 0 AND ltv_percent <= 100",
            name="snapshot_outputs_ltv_range",
        ),
        sa.CheckConstraint(
            "icr_percent IS NULL OR icr_percent >= 0",
            name="snapshot_outputs_icr_non_negative",
        ),
        sa.CheckConstraint(
            "gross_yield_percent >= 0",
            name="snapshot_outputs_gross_yield_non_negative",
        ),
    )
    op.create_index(
        "ix_snapshot_outputs_snapshot_id",
        "snapshot_outputs",
        ["snapshot_id"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # Step 14 — snapshot_intermediates
    # FK → snapshot_calculations (UNIQUE enforces 1:1)
    # ------------------------------------------------------------------
    op.create_table(
        "snapshot_intermediates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("snapshot_id", UUID(as_uuid=True), nullable=False),
        sa.Column(
            "void_rate_decimal_applied", sa.Numeric(15, 10), nullable=False
        ),
        sa.Column("gross_annual_rent_gbp", sa.Numeric(15, 6), nullable=False),
        sa.Column("effective_annual_rent_gbp", sa.Numeric(15, 6), nullable=False),
        sa.Column("loan_amount_gbp", sa.Numeric(15, 6), nullable=False),
        sa.Column("ltv_percent", sa.Numeric(10, 6), nullable=False),
        sa.Column("monthly_mortgage_payment_gbp", sa.Numeric(15, 6), nullable=False),
        sa.Column("annual_mortgage_cost_gbp", sa.Numeric(15, 6), nullable=False),
        sa.Column("annual_mortgage_interest_gbp", sa.Numeric(15, 6), nullable=False),
        sa.Column("letting_agent_annual_gbp", sa.Numeric(15, 6), nullable=False),
        sa.Column("letting_agent_vat_rate_applied", sa.Numeric(10, 6), nullable=False),
        sa.Column(
            "annual_maintenance_reserve_gbp", sa.Numeric(15, 6), nullable=False
        ),
        sa.Column(
            "total_operating_costs_annual_gbp", sa.Numeric(15, 6), nullable=False
        ),
        sa.Column("net_operating_income_gbp", sa.Numeric(15, 6), nullable=False),
        sa.Column("sdlt_band_breakdown", JSONB(), nullable=False),
        sa.Column("sdlt_base_gbp", sa.Numeric(15, 6), nullable=False),
        sa.Column("sdlt_surcharge_gbp", sa.Numeric(15, 6), nullable=False),
        sa.Column(
            "sdlt_surcharge_rate_applied", sa.Numeric(10, 6), nullable=False
        ),
        sa.Column("total_sdlt_gbp", sa.Numeric(15, 6), nullable=False),
        sa.Column("total_acquisition_cost_gbp", sa.Numeric(15, 6), nullable=False),
        sa.Column("total_cash_deployed_gbp", sa.Numeric(15, 6), nullable=False),
        sa.Column("stressed_annual_interest_gbp", sa.Numeric(15, 6), nullable=False),
        sa.Column(
            "stress_test_rate_applied_percent", sa.Numeric(10, 6), nullable=False
        ),
        sa.Column(
            "taxable_income_or_profit_gbp", sa.Numeric(15, 6), nullable=False
        ),
        sa.Column("income_tax_gross_gbp", sa.Numeric(15, 6), nullable=True),
        sa.Column(
            "mortgage_interest_tax_credit_gbp", sa.Numeric(15, 6), nullable=True
        ),
        sa.Column("corporation_tax_gross_gbp", sa.Numeric(15, 6), nullable=True),
        sa.Column("annual_tax_liability_gbp", sa.Numeric(15, 6), nullable=False),
        sa.Column("pre_tax_annual_cash_flow_gbp", sa.Numeric(15, 6), nullable=False),
        sa.Column("section_24_applies", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["snapshot_calculations.id"],
            name="fk_snapshot_intermediates_snapshot_calculations",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "void_rate_decimal_applied >= 0 AND void_rate_decimal_applied <= 1",
            name="snapshot_intermediates_void_rate_range",
        ),
        sa.CheckConstraint(
            "loan_amount_gbp >= 0",
            name="snapshot_intermediates_loan_non_negative",
        ),
        sa.CheckConstraint(
            "sdlt_base_gbp >= 0",
            name="snapshot_intermediates_sdlt_base_non_negative",
        ),
        sa.CheckConstraint(
            "sdlt_surcharge_gbp >= 0",
            name="snapshot_intermediates_sdlt_surcharge_non_negative",
        ),
        sa.CheckConstraint(
            "total_sdlt_gbp >= 0",
            name="snapshot_intermediates_total_sdlt_non_negative",
        ),
        sa.CheckConstraint(
            "annual_tax_liability_gbp >= 0",
            name="snapshot_intermediates_tax_non_negative",
        ),
        sa.CheckConstraint(
            "income_tax_gross_gbp IS NULL OR income_tax_gross_gbp >= 0",
            name="snapshot_intermediates_income_tax_non_negative",
        ),
        sa.CheckConstraint(
            "mortgage_interest_tax_credit_gbp IS NULL"
            " OR mortgage_interest_tax_credit_gbp >= 0",
            name="snapshot_intermediates_tax_credit_non_negative",
        ),
        sa.CheckConstraint(
            "corporation_tax_gross_gbp IS NULL OR corporation_tax_gross_gbp >= 0",
            name="snapshot_intermediates_corp_tax_non_negative",
        ),
    )
    op.create_index(
        "ix_snapshot_intermediates_snapshot_id",
        "snapshot_intermediates",
        ["snapshot_id"],
        unique=True,
    )

    # ------------------------------------------------------------------
    # Step 15 — snapshot_risk_flags
    # FK → snapshot_calculations (one-to-many)
    # ------------------------------------------------------------------
    op.create_table(
        "snapshot_risk_flags",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("snapshot_id", UUID(as_uuid=True), nullable=False),
        sa.Column("flag_code", sa.Text(), nullable=False),
        sa.Column(
            "severity",
            sa.Enum(name="flag_severity_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("triggered_by_field", sa.Text(), nullable=False),
        sa.Column("triggered_by_value", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["snapshot_calculations.id"],
            name="fk_snapshot_risk_flags_snapshot_calculations",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "flag_code <> ''",
            name="snapshot_risk_flags_code_non_empty",
        ),
        sa.CheckConstraint(
            "triggered_by_field <> ''",
            name="snapshot_risk_flags_field_non_empty",
        ),
        sa.CheckConstraint(
            "triggered_by_value <> ''",
            name="snapshot_risk_flags_value_non_empty",
        ),
        sa.CheckConstraint(
            "message <> ''",
            name="snapshot_risk_flags_message_non_empty",
        ),
    )
    op.create_index(
        "ix_snapshot_risk_flags_snapshot_id",
        "snapshot_risk_flags",
        ["snapshot_id"],
    )
    op.create_index(
        "ix_snapshot_risk_flags_flag_code",
        "snapshot_risk_flags",
        ["flag_code"],
    )

    # ------------------------------------------------------------------
    # Step 16 — snapshot_validation_warnings
    # FK → snapshot_calculations (one-to-many)
    # ------------------------------------------------------------------
    op.create_table(
        "snapshot_validation_warnings",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("snapshot_id", UUID(as_uuid=True), nullable=False),
        sa.Column("rule_code", sa.Text(), nullable=False),
        sa.Column("field", sa.Text(), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["snapshot_calculations.id"],
            name="fk_snapshot_validation_warnings_snapshot_calculations",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            r"rule_code ~ '^V-[0-9]+$'",
            name="snapshot_validation_warnings_rule_code_format",
        ),
        sa.CheckConstraint(
            "field <> ''",
            name="snapshot_validation_warnings_field_non_empty",
        ),
        sa.CheckConstraint(
            "message <> ''",
            name="snapshot_validation_warnings_message_non_empty",
        ),
    )
    op.create_index(
        "ix_snapshot_validation_warnings_snapshot_id",
        "snapshot_validation_warnings",
        ["snapshot_id"],
    )

    # ------------------------------------------------------------------
    # Step 17 — audit_calculations
    # FK → users, deals, snapshot_calculations (nullable)
    # ------------------------------------------------------------------
    op.create_table(
        "audit_calculations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("deal_id", UUID(as_uuid=True), nullable=False),
        sa.Column("snapshot_id", UUID(as_uuid=True), nullable=True),
        sa.Column("triggered_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column(
            "outcome",
            sa.Enum(name="calculation_outcome_enum", create_type=False),
            nullable=False,
        ),
        sa.Column("engine_version", sa.Text(), nullable=False),
        sa.Column("validation_errors", JSONB(), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("client_context", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"],
            name="fk_audit_calculations_users",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["deal_id"], ["deals.id"],
            name="fk_audit_calculations_deals",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["snapshot_calculations.id"],
            name="fk_audit_calculations_snapshot_calculations",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "outcome <> 'SUCCESS' OR snapshot_id IS NOT NULL",
            name="audit_calculations_success_requires_snapshot",
        ),
        sa.CheckConstraint(
            "outcome <> 'VALIDATION_FAILURE' OR validation_errors IS NOT NULL",
            name="audit_calculations_failure_requires_errors",
        ),
        sa.CheckConstraint(
            "triggered_at IS NOT NULL",
            name="audit_calculations_triggered_at_required",
        ),
    )
    op.create_index(
        "ix_audit_calculations_user_id_triggered_at",
        "audit_calculations",
        ["user_id", sa.text("triggered_at DESC")],
    )
    op.create_index(
        "ix_audit_calculations_deal_id_triggered_at",
        "audit_calculations",
        ["deal_id", sa.text("triggered_at DESC")],
    )
    op.create_index(
        "ix_audit_calculations_outcome",
        "audit_calculations",
        ["outcome"],
    )


def downgrade() -> None:
    # ------------------------------------------------------------------
    # No-op downgrade.
    #
    # This migration creates immutable tables (snapshot_*, config_*,
    # audit_calculations). Per PERSISTENCE_ARCHITECTURE.md Part 14.2,
    # downgrade operations for migrations that create immutable tables
    # must be explicit no-ops. Dropping snapshot tables would permanently
    # destroy calculation history and is not permitted.
    #
    # To reset a development database, drop and recreate it rather than
    # running alembic downgrade:
    #
    #   psql -c "DROP DATABASE propiq_dev;"
    #   psql -c "CREATE DATABASE propiq_dev;"
    #   alembic upgrade head
    # ------------------------------------------------------------------
    pass
