"""initial schema from models

Revision ID: 1d56deba40c1
Revises:
Create Date: 2026-06-06 00:26:29.399432+00:00

Generated via `alembic revision --autogenerate` then reordered to resolve
the circular FK dependency between deals ↔ snapshot_calculations.

deals.latest_snapshot_id → snapshot_calculations is deferred: deals is
created without that FK, snapshot_calculations is created (deals now
exists), then op.create_foreign_key adds the deferred FK.

Downgrade: intentional no-op per PERSISTENCE_ARCHITECTURE.md Part 14.2.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "1d56deba40c1"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Extensions
    # ------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    # ------------------------------------------------------------------
    # Step 1 — config_engine_versions (no FK deps)
    # ------------------------------------------------------------------
    op.create_table(
        "config_engine_versions",
        sa.Column("version_string", sa.String(), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("change_summary", sa.String(), nullable=False),
        sa.Column("is_breaking_change", sa.Boolean(), nullable=False),
        sa.Column("specification_ref", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("version_string"),
    )

    # ------------------------------------------------------------------
    # Step 2 — users (no FK deps)
    # ------------------------------------------------------------------
    op.create_table(
        "users",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("supabase_auth_id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("display_name", sa.String(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "SUSPENDED", "ARCHIVED", name="user_status_enum"),
            server_default="ACTIVE",
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            r"email ~* '^[^@]+@[^@]+\.[^@]+$'", name="users_email_format"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("supabase_auth_id"),
    )

    # ------------------------------------------------------------------
    # Step 3 — investor_profiles (FK → users)
    # ------------------------------------------------------------------
    op.create_table(
        "investor_profiles",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column(
            "ownership_structure",
            sa.Enum(
                "INDIVIDUAL", "LIMITED_COMPANY", name="ownership_structure_enum"
            ),
            nullable=False,
        ),
        sa.Column(
            "income_tax_band",
            sa.Enum(
                "BASIC_RATE", "HIGHER_RATE", "ADDITIONAL_RATE",
                name="income_tax_band_enum",
            ),
            nullable=True,
        ),
        sa.Column(
            "is_default",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(ownership_structure = 'INDIVIDUAL' AND income_tax_band IS NOT NULL)"
            " OR (ownership_structure = 'LIMITED_COMPANY' AND income_tax_band IS NULL)",
            name="investor_profiles_tax_band_consistency",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # Step 4 — properties (FK → users)
    # ------------------------------------------------------------------
    op.create_table(
        "properties",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("address_line_1", sa.String(), nullable=False),
        sa.Column("address_line_2", sa.String(), nullable=True),
        sa.Column("city", sa.String(), nullable=False),
        sa.Column("postcode", sa.String(), nullable=False),
        sa.Column(
            "property_type",
            sa.Enum("RESIDENTIAL_SINGLE_LET", name="property_type_enum"),
            nullable=False,
        ),
        sa.Column(
            "tenure",
            sa.Enum("FREEHOLD", "LEASEHOLD", name="tenure_enum"),
            nullable=False,
        ),
        sa.Column("lease_years_remaining", sa.Integer(), nullable=True),
        sa.Column("bedrooms", sa.SmallInteger(), nullable=True),
        sa.Column("epc_rating", sa.String(length=1), nullable=True),
        sa.Column(
            "is_archived",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "NOT (tenure = 'LEASEHOLD' AND lease_years_remaining IS NULL)",
            name="properties_leasehold_requires_lease_years",
        ),
        sa.CheckConstraint(
            "epc_rating IS NULL OR epc_rating IN ('A','B','C','D','E','F','G')",
            name="properties_epc_valid",
        ),
        sa.CheckConstraint(
            r"postcode ~ '^[A-Z]{1,2}[0-9][0-9A-Z]?\s*[0-9][A-Z]{2}$'",
            name="properties_postcode_format",
        ),
        sa.CheckConstraint(
            "bedrooms IS NULL OR bedrooms > 0", name="properties_bedrooms_positive"
        ),
        sa.CheckConstraint(
            "lease_years_remaining IS NULL OR lease_years_remaining > 0",
            name="properties_lease_years_positive",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # Step 5 — config_sdlt_versions (FK → users nullable)
    # ------------------------------------------------------------------
    op.create_table(
        "config_sdlt_versions",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column(
            "property_country",
            sa.Enum("ENGLAND", name="property_country_enum"),
            nullable=False,
        ),
        sa.Column(
            "additional_dwelling_surcharge_rate",
            sa.Numeric(precision=10, scale=6),
            nullable=False,
        ),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("source_attribution", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "additional_dwelling_surcharge_rate >= 0"
            " AND additional_dwelling_surcharge_rate <= 1",
            name="config_sdlt_versions_surcharge_rate_range",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # Step 6 — config_corporation_tax_versions (FK → users nullable)
    # ------------------------------------------------------------------
    op.create_table(
        "config_corporation_tax_versions",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column(
            "small_profits_rate", sa.Numeric(precision=10, scale=6), nullable=False
        ),
        sa.Column(
            "small_profits_upper_threshold",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column("main_rate", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column(
            "main_rate_lower_threshold",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column("marginal_relief_numerator", sa.SmallInteger(), nullable=False),
        sa.Column("marginal_relief_denominator", sa.SmallInteger(), nullable=False),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("source_attribution", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "main_rate >= 0 AND main_rate <= 1", name="config_ct_main_rate_range"
        ),
        sa.CheckConstraint(
            "marginal_relief_denominator > 0", name="config_ct_denominator_positive"
        ),
        sa.CheckConstraint(
            "marginal_relief_numerator > 0", name="config_ct_numerator_positive"
        ),
        sa.CheckConstraint(
            "small_profits_rate >= 0 AND small_profits_rate <= 1",
            name="config_ct_small_profits_rate_range",
        ),
        sa.CheckConstraint(
            "small_profits_upper_threshold < main_rate_lower_threshold",
            name="config_ct_threshold_ordering",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("effective_from"),
    )

    # ------------------------------------------------------------------
    # Step 7 — config_assumption_versions (FK → users nullable)
    # ------------------------------------------------------------------
    op.create_table(
        "config_assumption_versions",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column(
            "void_rate_percent_default", sa.Numeric(precision=10, scale=6), nullable=False
        ),
        sa.Column(
            "letting_agent_fee_percent_default",
            sa.Numeric(precision=10, scale=6),
            nullable=False,
        ),
        sa.Column(
            "letting_agent_vat_rate_percent",
            sa.Numeric(precision=10, scale=6),
            nullable=False,
        ),
        sa.Column(
            "maintenance_reserve_percent_default",
            sa.Numeric(precision=10, scale=6),
            nullable=False,
        ),
        sa.Column(
            "landlord_insurance_annual_default",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column(
            "purchase_legal_costs_default",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column(
            "accountancy_cost_individual_default",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column(
            "accountancy_cost_ltd_default",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column(
            "stress_test_rate_percent", sa.Numeric(precision=10, scale=6), nullable=False
        ),
        sa.Column(
            "icr_threshold_basic_rate_percent",
            sa.Numeric(precision=10, scale=6),
            nullable=False,
        ),
        sa.Column(
            "icr_threshold_higher_rate_percent",
            sa.Numeric(precision=10, scale=6),
            nullable=False,
        ),
        sa.Column("notes", sa.String(), nullable=True),
        sa.Column("source_attribution", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by_user_id", sa.UUID(), nullable=True),
        sa.CheckConstraint(
            "accountancy_cost_individual_default >= 0",
            name="config_assumptions_accountancy_individual_non_negative",
        ),
        sa.CheckConstraint(
            "accountancy_cost_ltd_default >= 0",
            name="config_assumptions_accountancy_ltd_non_negative",
        ),
        sa.CheckConstraint(
            "icr_threshold_basic_rate_percent > 0",
            name="config_assumptions_icr_basic_positive",
        ),
        sa.CheckConstraint(
            "icr_threshold_higher_rate_percent >= icr_threshold_basic_rate_percent",
            name="config_assumptions_icr_higher_gte_basic",
        ),
        sa.CheckConstraint(
            "landlord_insurance_annual_default >= 0",
            name="config_assumptions_insurance_non_negative",
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
            "purchase_legal_costs_default >= 0",
            name="config_assumptions_legal_costs_non_negative",
        ),
        sa.CheckConstraint(
            "stress_test_rate_percent > 0",
            name="config_assumptions_stress_rate_positive",
        ),
        sa.CheckConstraint(
            "void_rate_percent_default >= 0 AND void_rate_percent_default <= 100",
            name="config_assumptions_void_rate_range",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("effective_from"),
    )

    # ------------------------------------------------------------------
    # Step 8 — deals (FK → users, investor_profiles, properties)
    # latest_snapshot_id FK is DEFERRED — added after snapshot_calculations
    # ------------------------------------------------------------------
    op.create_table(
        "deals",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("property_id", sa.UUID(), nullable=False),
        sa.Column("investor_profile_id", sa.UUID(), nullable=True),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("DRAFT", "ANALYSED", "ARCHIVED", name="deal_status_enum"),
            server_default="DRAFT",
            nullable=False,
        ),
        # latest_snapshot_id stored without FK here; FK added below
        sa.Column("latest_snapshot_id", sa.UUID(), nullable=True),
        sa.Column("purchase_price", sa.Numeric(precision=15, scale=6), nullable=True),
        sa.Column("monthly_rent", sa.Numeric(precision=15, scale=6), nullable=True),
        sa.Column("deposit_amount", sa.Numeric(precision=15, scale=6), nullable=True),
        sa.Column(
            "mortgage_interest_rate", sa.Numeric(precision=10, scale=6), nullable=True
        ),
        sa.Column("mortgage_term_years", sa.SmallInteger(), nullable=True),
        sa.Column(
            "mortgage_type",
            sa.Enum("INTEREST_ONLY", "REPAYMENT", name="mortgage_type_enum"),
            nullable=True,
        ),
        sa.Column(
            "ownership_structure",
            sa.Enum(
                "INDIVIDUAL", "LIMITED_COMPANY", name="ownership_structure_enum"
            ),
            nullable=True,
        ),
        sa.Column(
            "income_tax_band",
            sa.Enum(
                "BASIC_RATE", "HIGHER_RATE", "ADDITIONAL_RATE",
                name="income_tax_band_enum",
            ),
            nullable=True,
        ),
        sa.Column("is_additional_dwelling", sa.Boolean(), nullable=True),
        sa.Column(
            "void_rate_percent", sa.Numeric(precision=10, scale=6), nullable=True
        ),
        sa.Column(
            "letting_agent_fee_percent",
            sa.Numeric(precision=10, scale=6),
            nullable=True,
        ),
        sa.Column(
            "maintenance_reserve_percent",
            sa.Numeric(precision=10, scale=6),
            nullable=True,
        ),
        sa.Column(
            "landlord_insurance_annual",
            sa.Numeric(precision=15, scale=6),
            nullable=True,
        ),
        sa.Column(
            "purchase_legal_costs", sa.Numeric(precision=15, scale=6), nullable=True
        ),
        sa.Column(
            "refurbishment_cost", sa.Numeric(precision=15, scale=6), nullable=True
        ),
        sa.Column(
            "annual_service_charge",
            sa.Numeric(precision=15, scale=6),
            nullable=True,
        ),
        sa.Column(
            "annual_ground_rent", sa.Numeric(precision=15, scale=6), nullable=True
        ),
        sa.Column(
            "annual_accountancy_cost",
            sa.Numeric(precision=15, scale=6),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "annual_ground_rent IS NULL OR annual_ground_rent >= 0",
            name="deals_ground_rent_non_negative",
        ),
        sa.CheckConstraint(
            "annual_service_charge IS NULL OR annual_service_charge >= 0",
            name="deals_service_charge_non_negative",
        ),
        sa.CheckConstraint(
            "deposit_amount IS NULL OR deposit_amount > 0",
            name="deals_deposit_positive",
        ),
        sa.CheckConstraint(
            "monthly_rent IS NULL OR monthly_rent > 0",
            name="deals_monthly_rent_positive",
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
            "purchase_price IS NULL OR purchase_price > 0",
            name="deals_purchase_price_positive",
        ),
        sa.CheckConstraint(
            "refurbishment_cost IS NULL OR refurbishment_cost >= 0",
            name="deals_refurb_non_negative",
        ),
        sa.ForeignKeyConstraint(
            ["investor_profile_id"], ["investor_profiles.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["property_id"], ["properties.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # Step 9 — snapshot_calculations (FK → deals, users, config tables)
    # ------------------------------------------------------------------
    op.create_table(
        "snapshot_calculations",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("deal_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("engine_version", sa.String(), nullable=False),
        sa.Column("assumption_config_version_id", sa.UUID(), nullable=False),
        sa.Column("sdlt_config_version_id", sa.UUID(), nullable=False),
        sa.Column("corporation_tax_config_version_id", sa.UUID(), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "is_superseded",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("calculation_duration_ms", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "calculated_at IS NOT NULL", name="snapshot_calculated_at_required"
        ),
        sa.CheckConstraint(
            "is_superseded = FALSE OR superseded_at IS NOT NULL",
            name="snapshot_superseded_timestamp_consistency",
        ),
        sa.ForeignKeyConstraint(
            ["assumption_config_version_id"],
            ["config_assumption_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["corporation_tax_config_version_id"],
            ["config_corporation_tax_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["deal_id"], ["deals.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["sdlt_config_version_id"],
            ["config_sdlt_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # Step 9b — resolve circular FK: deals.latest_snapshot_id → snapshot_calculations
    # ------------------------------------------------------------------
    op.create_foreign_key(
        "fk_deals_latest_snapshot_id",
        "deals",
        "snapshot_calculations",
        ["latest_snapshot_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    # ------------------------------------------------------------------
    # Step 10 — snapshot_inputs (FK → snapshot_calculations, 1:1)
    # ------------------------------------------------------------------
    op.create_table(
        "snapshot_inputs",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("snapshot_id", sa.UUID(), nullable=False),
        sa.Column("purchase_price", sa.Numeric(precision=15, scale=6), nullable=False),
        sa.Column("monthly_rent", sa.Numeric(precision=15, scale=6), nullable=False),
        sa.Column("deposit_amount", sa.Numeric(precision=15, scale=6), nullable=False),
        sa.Column(
            "mortgage_interest_rate", sa.Numeric(precision=10, scale=6), nullable=False
        ),
        sa.Column("mortgage_term_years", sa.SmallInteger(), nullable=False),
        sa.Column(
            "mortgage_type",
            sa.Enum("INTEREST_ONLY", "REPAYMENT", name="mortgage_type_enum"),
            nullable=False,
        ),
        sa.Column(
            "ownership_structure",
            sa.Enum(
                "INDIVIDUAL", "LIMITED_COMPANY", name="ownership_structure_enum"
            ),
            nullable=False,
        ),
        sa.Column(
            "income_tax_band",
            sa.Enum(
                "BASIC_RATE", "HIGHER_RATE", "ADDITIONAL_RATE",
                name="income_tax_band_enum",
            ),
            nullable=True,
        ),
        sa.Column("is_additional_dwelling", sa.Boolean(), nullable=False),
        sa.Column(
            "property_type",
            sa.Enum("RESIDENTIAL_SINGLE_LET", name="property_type_enum"),
            nullable=False,
        ),
        sa.Column(
            "tenure",
            sa.Enum("FREEHOLD", "LEASEHOLD", name="tenure_enum"),
            nullable=False,
        ),
        sa.Column(
            "property_country",
            sa.Enum("ENGLAND", name="property_country_enum"),
            nullable=False,
        ),
        sa.Column("postcode", sa.String(), nullable=False),
        sa.Column("lease_years_remaining", sa.SmallInteger(), nullable=True),
        sa.Column(
            "void_rate_percent", sa.Numeric(precision=10, scale=6), nullable=False
        ),
        sa.Column(
            "void_rate_percent_source",
            sa.Enum("USER_OVERRIDE", "CONFIG_DEFAULT", name="input_source_enum"),
            nullable=False,
        ),
        sa.Column(
            "letting_agent_fee_percent",
            sa.Numeric(precision=10, scale=6),
            nullable=False,
        ),
        sa.Column(
            "letting_agent_fee_percent_source",
            sa.Enum("USER_OVERRIDE", "CONFIG_DEFAULT", name="input_source_enum"),
            nullable=False,
        ),
        sa.Column(
            "maintenance_reserve_percent",
            sa.Numeric(precision=10, scale=6),
            nullable=False,
        ),
        sa.Column(
            "maintenance_reserve_percent_source",
            sa.Enum("USER_OVERRIDE", "CONFIG_DEFAULT", name="input_source_enum"),
            nullable=False,
        ),
        sa.Column(
            "landlord_insurance_annual",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column(
            "landlord_insurance_annual_source",
            sa.Enum("USER_OVERRIDE", "CONFIG_DEFAULT", name="input_source_enum"),
            nullable=False,
        ),
        sa.Column(
            "purchase_legal_costs", sa.Numeric(precision=15, scale=6), nullable=False
        ),
        sa.Column(
            "purchase_legal_costs_source",
            sa.Enum("USER_OVERRIDE", "CONFIG_DEFAULT", name="input_source_enum"),
            nullable=False,
        ),
        sa.Column(
            "refurbishment_cost", sa.Numeric(precision=15, scale=6), nullable=False
        ),
        sa.Column(
            "refurbishment_cost_source",
            sa.Enum("USER_OVERRIDE", "CONFIG_DEFAULT", name="input_source_enum"),
            nullable=False,
        ),
        sa.Column(
            "annual_service_charge", sa.Numeric(precision=15, scale=6), nullable=False
        ),
        sa.Column(
            "annual_service_charge_source",
            sa.Enum("USER_OVERRIDE", "CONFIG_DEFAULT", name="input_source_enum"),
            nullable=False,
        ),
        sa.Column(
            "annual_ground_rent", sa.Numeric(precision=15, scale=6), nullable=False
        ),
        sa.Column(
            "annual_ground_rent_source",
            sa.Enum("USER_OVERRIDE", "CONFIG_DEFAULT", name="input_source_enum"),
            nullable=False,
        ),
        sa.Column(
            "annual_accountancy_cost",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column(
            "annual_accountancy_cost_source",
            sa.Enum("USER_OVERRIDE", "CONFIG_DEFAULT", name="input_source_enum"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(ownership_structure = 'INDIVIDUAL' AND income_tax_band IS NOT NULL)"
            " OR (ownership_structure = 'LIMITED_COMPANY' AND income_tax_band IS NULL)",
            name="snapshot_inputs_tax_band_consistency",
        ),
        sa.CheckConstraint(
            "annual_accountancy_cost >= 0",
            name="snapshot_inputs_accountancy_non_negative",
        ),
        sa.CheckConstraint(
            "annual_ground_rent >= 0",
            name="snapshot_inputs_ground_rent_non_negative",
        ),
        sa.CheckConstraint(
            "annual_service_charge >= 0",
            name="snapshot_inputs_service_charge_non_negative",
        ),
        sa.CheckConstraint(
            "deposit_amount > 0 AND deposit_amount < purchase_price",
            name="snapshot_inputs_deposit_valid",
        ),
        sa.CheckConstraint(
            "monthly_rent > 0", name="snapshot_inputs_monthly_rent_positive"
        ),
        sa.CheckConstraint(
            "mortgage_interest_rate >= 0", name="snapshot_inputs_rate_non_negative"
        ),
        sa.CheckConstraint(
            "mortgage_term_years >= 5 AND mortgage_term_years <= 35",
            name="snapshot_inputs_term_range",
        ),
        sa.CheckConstraint(
            "purchase_price > 0", name="snapshot_inputs_purchase_price_positive"
        ),
        sa.CheckConstraint(
            "refurbishment_cost >= 0", name="snapshot_inputs_refurb_non_negative"
        ),
        sa.CheckConstraint(
            "void_rate_percent >= 0 AND void_rate_percent <= 100",
            name="snapshot_inputs_void_rate_range",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["snapshot_calculations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id"),
    )

    # ------------------------------------------------------------------
    # Step 11 — snapshot_outputs (FK → snapshot_calculations, 1:1)
    # ------------------------------------------------------------------
    op.create_table(
        "snapshot_outputs",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("snapshot_id", sa.UUID(), nullable=False),
        sa.Column(
            "gross_annual_rent_gbp", sa.Numeric(precision=15, scale=6), nullable=False
        ),
        sa.Column(
            "effective_annual_rent_gbp",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column(
            "total_operating_costs_annual_gbp",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column(
            "net_operating_income_gbp",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column(
            "annual_mortgage_cost_gbp",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column(
            "annual_tax_liability_gbp",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column(
            "annual_cash_flow_gbp", sa.Numeric(precision=15, scale=6), nullable=False
        ),
        sa.Column(
            "monthly_cash_flow_gbp", sa.Numeric(precision=15, scale=6), nullable=False
        ),
        sa.Column(
            "gross_yield_percent", sa.Numeric(precision=10, scale=6), nullable=False
        ),
        sa.Column(
            "net_yield_percent", sa.Numeric(precision=10, scale=6), nullable=False
        ),
        sa.Column("roce_percent", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column(
            "cash_on_cash_return_percent",
            sa.Numeric(precision=10, scale=6),
            nullable=False,
        ),
        sa.Column("ltv_percent", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column("icr_percent", sa.Numeric(precision=10, scale=6), nullable=True),
        sa.Column("total_sdlt_gbp", sa.Numeric(precision=15, scale=6), nullable=False),
        sa.Column(
            "total_acquisition_cost_gbp",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column(
            "total_cash_deployed_gbp",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "annual_tax_liability_gbp >= 0",
            name="snapshot_outputs_tax_non_negative",
        ),
        sa.CheckConstraint(
            "effective_annual_rent_gbp >= 0",
            name="snapshot_outputs_effective_rent_non_negative",
        ),
        sa.CheckConstraint(
            "gross_annual_rent_gbp >= 0",
            name="snapshot_outputs_gross_rent_non_negative",
        ),
        sa.CheckConstraint(
            "gross_yield_percent >= 0",
            name="snapshot_outputs_gross_yield_non_negative",
        ),
        sa.CheckConstraint(
            "icr_percent IS NULL OR icr_percent >= 0",
            name="snapshot_outputs_icr_non_negative",
        ),
        sa.CheckConstraint(
            "ltv_percent >= 0 AND ltv_percent <= 100",
            name="snapshot_outputs_ltv_range",
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
            "total_operating_costs_annual_gbp >= 0",
            name="snapshot_outputs_operating_costs_non_negative",
        ),
        sa.CheckConstraint(
            "total_sdlt_gbp >= 0", name="snapshot_outputs_sdlt_non_negative"
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["snapshot_calculations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id"),
    )

    # ------------------------------------------------------------------
    # Step 12 — snapshot_intermediates (FK → snapshot_calculations, 1:1)
    # ------------------------------------------------------------------
    op.create_table(
        "snapshot_intermediates",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("snapshot_id", sa.UUID(), nullable=False),
        sa.Column(
            "void_rate_decimal_applied",
            sa.Numeric(precision=15, scale=10),
            nullable=False,
        ),
        sa.Column(
            "gross_annual_rent_gbp", sa.Numeric(precision=15, scale=6), nullable=False
        ),
        sa.Column(
            "effective_annual_rent_gbp",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column(
            "loan_amount_gbp", sa.Numeric(precision=15, scale=6), nullable=False
        ),
        sa.Column("ltv_percent", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column(
            "monthly_mortgage_payment_gbp",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column(
            "annual_mortgage_cost_gbp",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column(
            "annual_mortgage_interest_gbp",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column(
            "letting_agent_annual_gbp",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column(
            "letting_agent_vat_rate_applied",
            sa.Numeric(precision=10, scale=6),
            nullable=False,
        ),
        sa.Column(
            "annual_maintenance_reserve_gbp",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column(
            "total_operating_costs_annual_gbp",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column(
            "net_operating_income_gbp",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column(
            "sdlt_band_breakdown",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column("sdlt_base_gbp", sa.Numeric(precision=15, scale=6), nullable=False),
        sa.Column(
            "sdlt_surcharge_gbp", sa.Numeric(precision=15, scale=6), nullable=False
        ),
        sa.Column(
            "sdlt_surcharge_rate_applied",
            sa.Numeric(precision=10, scale=6),
            nullable=False,
        ),
        sa.Column("total_sdlt_gbp", sa.Numeric(precision=15, scale=6), nullable=False),
        sa.Column(
            "total_acquisition_cost_gbp",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column(
            "total_cash_deployed_gbp",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column(
            "stressed_annual_interest_gbp",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column(
            "stress_test_rate_applied_percent",
            sa.Numeric(precision=10, scale=6),
            nullable=False,
        ),
        sa.Column(
            "taxable_income_or_profit_gbp",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column(
            "income_tax_gross_gbp", sa.Numeric(precision=15, scale=6), nullable=True
        ),
        sa.Column(
            "mortgage_interest_tax_credit_gbp",
            sa.Numeric(precision=15, scale=6),
            nullable=True,
        ),
        sa.Column(
            "corporation_tax_gross_gbp",
            sa.Numeric(precision=15, scale=6),
            nullable=True,
        ),
        sa.Column(
            "annual_tax_liability_gbp",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column(
            "pre_tax_annual_cash_flow_gbp",
            sa.Numeric(precision=15, scale=6),
            nullable=False,
        ),
        sa.Column("section_24_applies", sa.Boolean(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "annual_tax_liability_gbp >= 0",
            name="snapshot_intermediates_tax_non_negative",
        ),
        sa.CheckConstraint(
            "corporation_tax_gross_gbp IS NULL OR corporation_tax_gross_gbp >= 0",
            name="snapshot_intermediates_corp_tax_non_negative",
        ),
        sa.CheckConstraint(
            "income_tax_gross_gbp IS NULL OR income_tax_gross_gbp >= 0",
            name="snapshot_intermediates_income_tax_non_negative",
        ),
        sa.CheckConstraint(
            "loan_amount_gbp >= 0", name="snapshot_intermediates_loan_non_negative"
        ),
        sa.CheckConstraint(
            "mortgage_interest_tax_credit_gbp IS NULL"
            " OR mortgage_interest_tax_credit_gbp >= 0",
            name="snapshot_intermediates_tax_credit_non_negative",
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
            "void_rate_decimal_applied >= 0 AND void_rate_decimal_applied <= 1",
            name="snapshot_intermediates_void_rate_range",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["snapshot_calculations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("snapshot_id"),
    )

    # ------------------------------------------------------------------
    # Step 13 — snapshot_risk_flags (FK → snapshot_calculations, 1:many)
    # ------------------------------------------------------------------
    op.create_table(
        "snapshot_risk_flags",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("snapshot_id", sa.UUID(), nullable=False),
        sa.Column("flag_code", sa.String(), nullable=False),
        sa.Column(
            "severity",
            sa.Enum("HIGH", "MEDIUM", "INFO", name="flag_severity_enum"),
            nullable=False,
        ),
        sa.Column("triggered_by_field", sa.String(), nullable=False),
        sa.Column("triggered_by_value", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("flag_code <> ''", name="snapshot_risk_flags_code_non_empty"),
        sa.CheckConstraint(
            "message <> ''", name="snapshot_risk_flags_message_non_empty"
        ),
        sa.CheckConstraint(
            "triggered_by_field <> ''",
            name="snapshot_risk_flags_field_non_empty",
        ),
        sa.CheckConstraint(
            "triggered_by_value <> ''",
            name="snapshot_risk_flags_value_non_empty",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["snapshot_calculations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # Step 14 — snapshot_validation_warnings (FK → snapshot_calculations, 1:many)
    # ------------------------------------------------------------------
    op.create_table(
        "snapshot_validation_warnings",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("snapshot_id", sa.UUID(), nullable=False),
        sa.Column("rule_code", sa.String(), nullable=False),
        sa.Column("field", sa.String(), nullable=False),
        sa.Column("message", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "field <> ''", name="snapshot_validation_warnings_field_non_empty"
        ),
        sa.CheckConstraint(
            "message <> ''", name="snapshot_validation_warnings_message_non_empty"
        ),
        sa.CheckConstraint(
            r"rule_code ~ '^V-[0-9]+$'",
            name="snapshot_validation_warnings_rule_code_format",
        ),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["snapshot_calculations.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # Step 15 — audit_calculations (FK → users, deals, snapshot_calculations)
    # ------------------------------------------------------------------
    op.create_table(
        "audit_calculations",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("deal_id", sa.UUID(), nullable=False),
        sa.Column("snapshot_id", sa.UUID(), nullable=True),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "outcome",
            sa.Enum(
                "SUCCESS",
                "VALIDATION_FAILURE",
                "ENGINE_ERROR",
                name="calculation_outcome_enum",
            ),
            nullable=False,
        ),
        sa.Column("engine_version", sa.String(), nullable=False),
        sa.Column(
            "validation_errors",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("error_detail", sa.String(), nullable=True),
        sa.Column("client_context", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
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
        sa.ForeignKeyConstraint(["deal_id"], ["deals.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["snapshot_id"], ["snapshot_calculations.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # Step 16 — config_sdlt_bands (FK → config_sdlt_versions)
    # ------------------------------------------------------------------
    op.create_table(
        "config_sdlt_bands",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("sdlt_version_id", sa.UUID(), nullable=False),
        sa.Column("band_order", sa.SmallInteger(), nullable=False),
        sa.Column("band_lower", sa.Numeric(precision=15, scale=6), nullable=False),
        sa.Column("band_upper", sa.Numeric(precision=15, scale=6), nullable=True),
        sa.Column("rate", sa.Numeric(precision=10, scale=6), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "band_lower >= 0", name="config_sdlt_bands_lower_non_negative"
        ),
        sa.CheckConstraint(
            "band_order > 0", name="config_sdlt_bands_order_positive"
        ),
        sa.CheckConstraint(
            "band_upper IS NULL OR band_upper > band_lower",
            name="config_sdlt_bands_upper_gt_lower",
        ),
        sa.CheckConstraint(
            "rate >= 0 AND rate <= 1", name="config_sdlt_bands_rate_range"
        ),
        sa.ForeignKeyConstraint(
            ["sdlt_version_id"],
            ["config_sdlt_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    # PERSISTENCE_ARCHITECTURE.md Part 14.2 — intentional no-op.
    # This migration creates immutable tables (snapshot_*, config_*, audit_calculations).
    # Dropping them would destroy historical data permanently.
    # To reset a development database, drop and recreate the database entirely.
    pass
