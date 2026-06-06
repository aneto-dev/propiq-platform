"""
Schema integrity tests — verify migration output against DATABASE_SCHEMA_DESIGN.md.

Verifies:
  - All 16 Phase 1 tables exist after migration
  - Key columns have the correct nullable / NOT NULL constraint
  - UNIQUE indexes on snapshot sub-tables enforcing 1:1 relationships
  - FK constraints from snapshot_calculations to all three config tables
  - FK deals.latest_snapshot_id → snapshot_calculations (deferred FK)
  - All 5 configuration seed records are present and queryable
  - PostGIS extension is enabled
  - Config age_days query works (sanity check on date column type and data)

Requires a running test database. Run via:
    make test-int

These tests are not collected by make test-unit (no DB dependency).

Architecture:
    DATABASE_SCHEMA_DESIGN.md — authoritative schema definition
    IMPLEMENTATION_ROADMAP.md Commit 3.5
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import get_settings

# ---------------------------------------------------------------------------
# Expected schema constants — DATABASE_SCHEMA_DESIGN.md
# ---------------------------------------------------------------------------

EXPECTED_TABLES: list[str] = [
    "users",
    "investor_profiles",
    "properties",
    "deals",
    "config_engine_versions",
    "config_sdlt_versions",
    "config_sdlt_bands",
    "config_corporation_tax_versions",
    "config_assumption_versions",
    "snapshot_calculations",
    "snapshot_inputs",
    "snapshot_outputs",
    "snapshot_intermediates",
    "snapshot_risk_flags",
    "snapshot_validation_warnings",
    "audit_calculations",
]

# Snapshot sub-tables with 1:1 constraint on snapshot_id (Section 3 + Section 8)
SNAPSHOT_ONE_TO_ONE_TABLES: list[str] = [
    "snapshot_inputs",
    "snapshot_outputs",
    "snapshot_intermediates",
]

# FK pairs: snapshot_calculations → config tables (Section 6)
SNAPSHOT_CONFIG_FKS: list[tuple[str, str]] = [
    ("snapshot_calculations", "config_assumption_versions"),
    ("snapshot_calculations", "config_sdlt_versions"),
    ("snapshot_calculations", "config_corporation_tax_versions"),
]

# Nullable columns — spot-check from DATABASE_SCHEMA_DESIGN.md Section 2–5
NULLABLE_COLUMNS: list[tuple[str, str]] = [
    ("users", "display_name"),
    ("investor_profiles", "income_tax_band"),
    ("investor_profiles", "archived_at"),
    ("properties", "address_line_2"),
    ("properties", "lease_years_remaining"),
    ("properties", "bedrooms"),
    ("properties", "epc_rating"),
    ("properties", "archived_at"),
    ("deals", "investor_profile_id"),
    ("deals", "latest_snapshot_id"),
    ("deals", "purchase_price"),
    ("deals", "mortgage_type"),
    ("snapshot_calculations", "superseded_at"),
    ("snapshot_calculations", "calculation_duration_ms"),
    ("snapshot_inputs", "income_tax_band"),
    ("snapshot_inputs", "lease_years_remaining"),
    ("snapshot_outputs", "icr_percent"),
    ("snapshot_intermediates", "income_tax_gross_gbp"),
    ("snapshot_intermediates", "mortgage_interest_tax_credit_gbp"),
    ("snapshot_intermediates", "corporation_tax_gross_gbp"),
    ("audit_calculations", "snapshot_id"),
    ("audit_calculations", "validation_errors"),
    ("audit_calculations", "error_detail"),
    ("audit_calculations", "client_context"),
    ("config_sdlt_versions", "created_by_user_id"),
    ("config_corporation_tax_versions", "created_by_user_id"),
    ("config_assumption_versions", "created_by_user_id"),
]

# NOT NULL columns — spot-check
NOT_NULL_COLUMNS: list[tuple[str, str]] = [
    ("users", "email"),
    ("users", "status"),
    ("users", "created_at"),
    ("investor_profiles", "user_id"),
    ("investor_profiles", "label"),
    ("investor_profiles", "ownership_structure"),
    ("properties", "user_id"),
    ("properties", "address_line_1"),
    ("properties", "city"),
    ("properties", "postcode"),
    ("properties", "property_type"),
    ("properties", "tenure"),
    ("deals", "user_id"),
    ("deals", "property_id"),
    ("deals", "label"),
    ("deals", "status"),
    ("snapshot_calculations", "deal_id"),
    ("snapshot_calculations", "user_id"),
    ("snapshot_calculations", "engine_version"),
    ("snapshot_calculations", "assumption_config_version_id"),
    ("snapshot_calculations", "sdlt_config_version_id"),
    ("snapshot_calculations", "corporation_tax_config_version_id"),
    ("snapshot_calculations", "calculated_at"),
    ("snapshot_inputs", "snapshot_id"),
    ("snapshot_inputs", "purchase_price"),
    ("snapshot_inputs", "mortgage_type"),
    ("snapshot_inputs", "ownership_structure"),
    ("snapshot_inputs", "property_country"),
    ("snapshot_outputs", "snapshot_id"),
    ("snapshot_outputs", "gross_annual_rent_gbp"),
    ("snapshot_intermediates", "snapshot_id"),
    ("snapshot_intermediates", "void_rate_decimal_applied"),
    ("snapshot_intermediates", "sdlt_band_breakdown"),
    ("snapshot_risk_flags", "snapshot_id"),
    ("snapshot_risk_flags", "flag_code"),
    ("snapshot_risk_flags", "severity"),
    ("snapshot_validation_warnings", "snapshot_id"),
    ("snapshot_validation_warnings", "rule_code"),
    ("audit_calculations", "user_id"),
    ("audit_calculations", "deal_id"),
    ("audit_calculations", "outcome"),
    ("audit_calculations", "triggered_at"),
    ("config_engine_versions", "change_summary"),
    ("config_engine_versions", "is_breaking_change"),
    ("config_sdlt_versions", "effective_from"),
    ("config_sdlt_versions", "property_country"),
    ("config_sdlt_bands", "sdlt_version_id"),
    ("config_sdlt_bands", "band_lower"),
    ("config_sdlt_bands", "rate"),
    ("config_corporation_tax_versions", "effective_from"),
    ("config_corporation_tax_versions", "small_profits_rate"),
    ("config_assumption_versions", "effective_from"),
    ("config_assumption_versions", "void_rate_percent_default"),
]




def _test_url() -> str:
    return get_settings().test_database_url

# ---------------------------------------------------------------------------
# Query helper
# ---------------------------------------------------------------------------

async def _query(sql: str, params: dict | None = None) -> list:
    engine = create_async_engine(_test_url())
    async with engine.connect() as conn:
        result = await conn.execute(text(sql), params or {})
        rows = result.fetchall()
    await engine.dispose()
    return rows


# ---------------------------------------------------------------------------
# Tests: tables
# ---------------------------------------------------------------------------

class TestAllTablesExist:
    """All 16 Phase 1 tables must be present after migration."""

    @pytest.mark.parametrize("table_name", EXPECTED_TABLES)
    async def test_table_exists(self, table_name: str) -> None:
        rows = await _query(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' "
            "AND table_type = 'BASE TABLE' "
            "AND table_name = :t",
            {"t": table_name},
        )
        assert len(rows) == 1, f"Table '{table_name}' not found in public schema"

    async def test_exactly_expected_tables(self) -> None:
        """No extra or missing tables — exactly the 16 Phase 1 tables."""
        rows = await _query(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' AND table_type = 'BASE TABLE' "
            "AND table_name NOT IN ('alembic_version', 'spatial_ref_sys')"
        )
        actual = {row[0] for row in rows}
        expected = set(EXPECTED_TABLES)
        assert actual == expected, (
            f"Table mismatch.\n"
            f"  Extra:   {sorted(actual - expected)}\n"
            f"  Missing: {sorted(expected - actual)}"
        )


# ---------------------------------------------------------------------------
# Tests: column nullability
# ---------------------------------------------------------------------------

class TestColumnNullability:
    """Key columns must have the correct nullable / NOT NULL constraint."""

    @pytest.mark.parametrize("table_name,column_name", NULLABLE_COLUMNS)
    async def test_column_is_nullable(
        self, table_name: str, column_name: str
    ) -> None:
        rows = await _query(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_schema = 'public' "
            "AND table_name = :t AND column_name = :c",
            {"t": table_name, "c": column_name},
        )
        assert len(rows) == 1, (
            f"Column '{table_name}.{column_name}' not found"
        )
        assert rows[0][0] == "YES", (
            f"'{table_name}.{column_name}' should be nullable but is NOT NULL"
        )

    @pytest.mark.parametrize("table_name,column_name", NOT_NULL_COLUMNS)
    async def test_column_is_not_null(
        self, table_name: str, column_name: str
    ) -> None:
        rows = await _query(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_schema = 'public' "
            "AND table_name = :t AND column_name = :c",
            {"t": table_name, "c": column_name},
        )
        assert len(rows) == 1, (
            f"Column '{table_name}.{column_name}' not found"
        )
        assert rows[0][0] == "NO", (
            f"'{table_name}.{column_name}' should be NOT NULL but is nullable"
        )


# ---------------------------------------------------------------------------
# Tests: UNIQUE constraints on snapshot sub-tables
# ---------------------------------------------------------------------------

class TestUniqueConstraints:
    """
    snapshot_inputs, snapshot_outputs, snapshot_intermediates must each have
    a UNIQUE index on snapshot_id — enforcing the 1:1 relationship.
    DATABASE_SCHEMA_DESIGN.md Section 3 (column spec) and Section 8 (indexes).
    """

    @pytest.mark.parametrize("table_name", SNAPSHOT_ONE_TO_ONE_TABLES)
    async def test_snapshot_id_unique_index(self, table_name: str) -> None:
        rows = await _query(
            "SELECT indexname FROM pg_indexes "
            "WHERE schemaname = 'public' "
            "AND tablename = :t "
            "AND indexdef ILIKE '%unique%' "
            "AND indexdef ILIKE '%snapshot_id%'",
            {"t": table_name},
        )
        assert len(rows) >= 1, (
            f"No UNIQUE index on '{table_name}.snapshot_id'"
        )


# ---------------------------------------------------------------------------
# Tests: FK relationships
# ---------------------------------------------------------------------------

_FK_QUERY = """
SELECT kcu.column_name
FROM information_schema.table_constraints tc
JOIN information_schema.key_column_usage kcu
  ON tc.constraint_name = kcu.constraint_name
  AND tc.table_schema   = kcu.table_schema
JOIN information_schema.referential_constraints rc
  ON tc.constraint_name = rc.constraint_name
JOIN information_schema.table_constraints tc2
  ON rc.unique_constraint_name = tc2.constraint_name
WHERE tc.constraint_type = 'FOREIGN KEY'
AND   tc.table_schema    = 'public'
AND   tc.table_name      = :source
AND   tc2.table_name     = :referent
"""


class TestForeignKeys:
    """FK constraints must exist as defined in DATABASE_SCHEMA_DESIGN.md Section 6."""

    @pytest.mark.parametrize("source,referent", SNAPSHOT_CONFIG_FKS)
    async def test_snapshot_calculations_config_fk(
        self, source: str, referent: str
    ) -> None:
        rows = await _query(_FK_QUERY, {"source": source, "referent": referent})
        assert len(rows) >= 1, (
            f"FK '{source}' → '{referent}' not found"
        )

    async def test_snapshot_inputs_fk(self) -> None:
        rows = await _query(
            _FK_QUERY,
            {"source": "snapshot_inputs", "referent": "snapshot_calculations"},
        )
        assert len(rows) >= 1, "FK snapshot_inputs → snapshot_calculations not found"

    async def test_snapshot_outputs_fk(self) -> None:
        rows = await _query(
            _FK_QUERY,
            {"source": "snapshot_outputs", "referent": "snapshot_calculations"},
        )
        assert len(rows) >= 1, "FK snapshot_outputs → snapshot_calculations not found"

    async def test_snapshot_intermediates_fk(self) -> None:
        rows = await _query(
            _FK_QUERY,
            {"source": "snapshot_intermediates", "referent": "snapshot_calculations"},
        )
        assert len(rows) >= 1

    async def test_snapshot_risk_flags_fk(self) -> None:
        rows = await _query(
            _FK_QUERY,
            {"source": "snapshot_risk_flags", "referent": "snapshot_calculations"},
        )
        assert len(rows) >= 1

    async def test_snapshot_validation_warnings_fk(self) -> None:
        rows = await _query(
            _FK_QUERY,
            {
                "source": "snapshot_validation_warnings",
                "referent": "snapshot_calculations",
            },
        )
        assert len(rows) >= 1

    async def test_deals_latest_snapshot_fk(self) -> None:
        """
        Deferred FK: deals.latest_snapshot_id → snapshot_calculations.
        Added via op.create_foreign_key() after snapshot_calculations exists.
        """
        rows = await _query(
            _FK_QUERY + " AND kcu.column_name = 'latest_snapshot_id'",
            {"source": "deals", "referent": "snapshot_calculations"},
        )
        assert len(rows) == 1, (
            "FK deals.latest_snapshot_id → snapshot_calculations not found"
        )

    async def test_deals_user_fk(self) -> None:
        rows = await _query(_FK_QUERY, {"source": "deals", "referent": "users"})
        assert len(rows) >= 1

    async def test_deals_property_fk(self) -> None:
        rows = await _query(
            _FK_QUERY, {"source": "deals", "referent": "properties"}
        )
        assert len(rows) >= 1

    async def test_audit_calculations_fks(self) -> None:
        """audit_calculations has FKs to users, deals, and snapshot_calculations."""
        for referent in ("users", "deals", "snapshot_calculations"):
            rows = await _query(
                _FK_QUERY,
                {"source": "audit_calculations", "referent": referent},
            )
            assert len(rows) >= 1, (
                f"FK audit_calculations → {referent} not found"
            )


# ---------------------------------------------------------------------------
# Tests: configuration seed data
# ---------------------------------------------------------------------------

class TestConfigData:
    """Seed records from DATABASE_SCHEMA_DESIGN.md Section 9 must be present."""

    async def test_engine_version_present(self) -> None:
        rows = await _query(
            "SELECT version_string, is_breaking_change "
            "FROM config_engine_versions WHERE version_string = '1.0.0'"
        )
        assert len(rows) == 1, "Engine version '1.0.0' not seeded"
        assert rows[0][1] is False, "is_breaking_change should be False for v1.0.0"

    async def test_sdlt_version_present(self) -> None:
        rows = await _query(
            "SELECT id FROM config_sdlt_versions "
            "WHERE effective_from = '2025-04-01' "
            "AND property_country = 'ENGLAND'"
        )
        assert len(rows) == 1, "SDLT version ENGLAND/2025-04-01 not seeded"

    async def test_sdlt_five_bands_present(self) -> None:
        rows = await _query(
            "SELECT COUNT(*) FROM config_sdlt_bands csb "
            "JOIN config_sdlt_versions csv ON csb.sdlt_version_id = csv.id "
            "WHERE csv.effective_from = '2025-04-01' "
            "AND csv.property_country = 'ENGLAND'"
        )
        assert rows[0][0] == 5, f"Expected 5 SDLT bands, found {rows[0][0]}"

    async def test_sdlt_top_band_has_null_upper(self) -> None:
        """Band 5 (rate=12%) must have NULL band_upper — no upper limit."""
        rows = await _query(
            "SELECT band_upper FROM config_sdlt_bands csb "
            "JOIN config_sdlt_versions csv ON csb.sdlt_version_id = csv.id "
            "WHERE csv.effective_from = '2025-04-01' "
            "AND csv.property_country = 'ENGLAND' "
            "AND csb.band_order = 5"
        )
        assert len(rows) == 1
        assert rows[0][0] is None, "Top SDLT band should have NULL band_upper"

    async def test_corporation_tax_rates(self) -> None:
        rows = await _query(
            "SELECT small_profits_rate, main_rate, "
            "marginal_relief_numerator, marginal_relief_denominator "
            "FROM config_corporation_tax_versions "
            "WHERE effective_from = '2023-04-01'"
        )
        assert len(rows) == 1, "CT version 2023-04-01 not seeded"
        assert float(rows[0][0]) == pytest.approx(0.19, abs=1e-6)
        assert float(rows[0][1]) == pytest.approx(0.25, abs=1e-6)
        assert rows[0][2] == 3
        assert rows[0][3] == 200

    async def test_assumption_defaults(self) -> None:
        rows = await _query(
            "SELECT void_rate_percent_default, stress_test_rate_percent, "
            "icr_threshold_basic_rate_percent, icr_threshold_higher_rate_percent "
            "FROM config_assumption_versions "
            "WHERE effective_from = '2025-01-01'"
        )
        assert len(rows) == 1, "Assumption version 2025-01-01 not seeded"
        assert float(rows[0][0]) == pytest.approx(3.85, abs=1e-4)
        assert float(rows[0][1]) == pytest.approx(5.50, abs=1e-4)
        assert float(rows[0][2]) == pytest.approx(125.0, abs=1e-4)
        assert float(rows[0][3]) == pytest.approx(145.0, abs=1e-4)

    async def test_config_age_days_query(self) -> None:
        """
        Sanity check: effective_from is a proper date column and the seed
        record is accessible. Computes days since effective_from.
        DATABASE_SCHEMA_DESIGN.md Section 9 — config data sanity check.
        """
        rows = await _query(
            "SELECT (CURRENT_DATE - effective_from)::INTEGER AS age_days "
            "FROM config_assumption_versions "
            "WHERE effective_from = '2025-01-01'"
        )
        assert len(rows) == 1, "Assumption version record not found for age_days check"
        age_days = rows[0][0]
        assert isinstance(age_days, int), (
            f"age_days should be INTEGER, got {type(age_days).__name__}"
        )
        assert age_days >= 0, f"age_days is negative: {age_days}"

    async def test_postgis_extension_enabled(self) -> None:
        """
        PostGIS must be enabled — installed in migration Step 1.
        DATABASE_SCHEMA_DESIGN.md Phase 3 Exit Criteria.
        """
        rows = await _query("SELECT PostGIS_Version()")
        assert len(rows) == 1
        assert rows[0][0] is not None, "PostGIS_Version() returned NULL"
