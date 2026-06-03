"""application database role privileges

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-03

Creates the propiq_app and propiq_admin database roles and applies the
full privilege model defined in DATABASE_SCHEMA_DESIGN.md Section 7.

Role summary
────────────
propiq_app   — runtime FastAPI application role.
               SELECT, INSERT, UPDATE on mutable tables (no DELETE).
               SELECT, INSERT on snapshot and audit tables (no UPDATE, no DELETE).
               SELECT only on config tables.
               Column-level UPDATE grant on snapshot_calculations.is_superseded
               and snapshot_calculations.superseded_at only — the single permitted
               snapshot mutation (PERSISTENCE_ARCHITECTURE.md Part 2.3).

propiq_admin — admin configuration management role.
               SELECT, INSERT on all tables (no UPDATE, no DELETE anywhere).
               Superset of propiq_app on config tables; INSERT permitted where
               propiq_app has SELECT only.
               Note: admin role has NO UPDATE even on mutable tables — admin
               operations are append-only configuration inserts.

propiq_migrations is not created here. It is the role that executes migrations
(superuser-equivalent DDL). It pre-exists in each environment and is not managed
by application migrations.

Why here
────────
Database-level privilege enforcement is a production-grade trust requirement
(PERSISTENCE_ARCHITECTURE.md Part 1.3). Application-layer guards are necessary
but not sufficient — a bug or direct database connection must be blocked at the
privilege layer. This migration does nothing harmful in local development
(the connection role is a superuser, so grants have no practical effect) but is
applied in staging and production where roles are separated.

Architecture references
───────────────────────
DATABASE_SCHEMA_DESIGN.md Section 7 — Application Database Role Permissions
PERSISTENCE_ARCHITECTURE.md Part 1.3 — Database-Level Enforcement of Immutability

Downgrade
─────────
Revokes all grants and drops both roles. Safe in development. In production,
downgrade is a destructive operation that would break the running application —
do not run in production without a maintenance window and role re-creation plan.
"""

from __future__ import annotations

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Create roles
    # IF NOT EXISTS prevents failure on re-run (idempotent role creation).
    # ------------------------------------------------------------------
    op.execute("CREATE ROLE IF NOT EXISTS propiq_app")
    op.execute("CREATE ROLE IF NOT EXISTS propiq_admin")

    # ==================================================================
    # propiq_app — runtime application role
    # ==================================================================

    # ------------------------------------------------------------------
    # Mutable tables: SELECT, INSERT, UPDATE (no DELETE)
    # users, investor_profiles, properties, deals
    # ------------------------------------------------------------------
    for table in ("users", "investor_profiles", "properties", "deals"):
        op.execute(
            f"GRANT SELECT, INSERT, UPDATE ON {table} TO propiq_app"
        )

    # ------------------------------------------------------------------
    # snapshot_calculations: SELECT, INSERT only.
    # Column-level UPDATE on is_superseded and superseded_at — the single
    # permitted mutation on any snapshot table.
    # DATABASE_SCHEMA_DESIGN.md Section 7 / PERSISTENCE_ARCHITECTURE.md 2.3.
    # ------------------------------------------------------------------
    op.execute(
        "GRANT SELECT, INSERT ON snapshot_calculations TO propiq_app"
    )
    op.execute(
        "GRANT UPDATE (is_superseded, superseded_at)"
        " ON snapshot_calculations TO propiq_app"
    )

    # ------------------------------------------------------------------
    # Remaining snapshot tables: SELECT, INSERT only (no UPDATE, no DELETE)
    # ------------------------------------------------------------------
    for table in (
        "snapshot_inputs",
        "snapshot_outputs",
        "snapshot_intermediates",
        "snapshot_risk_flags",
        "snapshot_validation_warnings",
    ):
        op.execute(
            f"GRANT SELECT, INSERT ON {table} TO propiq_app"
        )

    # ------------------------------------------------------------------
    # Config tables: SELECT only
    # Admin inserts via propiq_admin role; runtime app never writes config.
    # ------------------------------------------------------------------
    for table in (
        "config_engine_versions",
        "config_sdlt_versions",
        "config_sdlt_bands",
        "config_corporation_tax_versions",
        "config_assumption_versions",
    ):
        op.execute(
            f"GRANT SELECT ON {table} TO propiq_app"
        )

    # ------------------------------------------------------------------
    # Audit table: SELECT, INSERT only (append-only)
    # ------------------------------------------------------------------
    op.execute(
        "GRANT SELECT, INSERT ON audit_calculations TO propiq_app"
    )

    # ==================================================================
    # propiq_admin — admin configuration management role
    # SELECT, INSERT on all tables. No UPDATE or DELETE anywhere.
    # "Even the admin role has no UPDATE or DELETE on any table."
    # — DATABASE_SCHEMA_DESIGN.md Section 7
    # ==================================================================

    # ------------------------------------------------------------------
    # Mutable tables: SELECT, INSERT (no UPDATE — admin is insert-only)
    # ------------------------------------------------------------------
    for table in ("users", "investor_profiles", "properties", "deals"):
        op.execute(
            f"GRANT SELECT, INSERT ON {table} TO propiq_admin"
        )

    # ------------------------------------------------------------------
    # Snapshot tables: SELECT, INSERT (same as propiq_app — no UPDATE)
    # ------------------------------------------------------------------
    for table in (
        "snapshot_calculations",
        "snapshot_inputs",
        "snapshot_outputs",
        "snapshot_intermediates",
        "snapshot_risk_flags",
        "snapshot_validation_warnings",
    ):
        op.execute(
            f"GRANT SELECT, INSERT ON {table} TO propiq_admin"
        )

    # ------------------------------------------------------------------
    # Config tables: SELECT, INSERT
    # Admin role can insert new configuration versions.
    # This is the key difference from propiq_app (which has SELECT only).
    # ------------------------------------------------------------------
    for table in (
        "config_engine_versions",
        "config_sdlt_versions",
        "config_sdlt_bands",
        "config_corporation_tax_versions",
        "config_assumption_versions",
    ):
        op.execute(
            f"GRANT SELECT, INSERT ON {table} TO propiq_admin"
        )

    # ------------------------------------------------------------------
    # Audit table: SELECT, INSERT
    # ------------------------------------------------------------------
    op.execute(
        "GRANT SELECT, INSERT ON audit_calculations TO propiq_admin"
    )


def downgrade() -> None:
    # ------------------------------------------------------------------
    # Revoke all grants and drop roles.
    #
    # Safe in development for schema rollback. In production, running
    # downgrade will break the application immediately — any connection
    # using propiq_app will lose all privileges. Only run in production
    # during a planned maintenance window with a re-creation plan in place.
    # ------------------------------------------------------------------

    # Revoke propiq_admin grants
    for table in (
        "users", "investor_profiles", "properties", "deals",
        "snapshot_calculations", "snapshot_inputs", "snapshot_outputs",
        "snapshot_intermediates", "snapshot_risk_flags",
        "snapshot_validation_warnings",
        "config_engine_versions", "config_sdlt_versions", "config_sdlt_bands",
        "config_corporation_tax_versions", "config_assumption_versions",
        "audit_calculations",
    ):
        op.execute(
            f"REVOKE ALL PRIVILEGES ON {table} FROM propiq_admin"
        )

    # Revoke propiq_app grants (including column-level grant)
    op.execute(
        "REVOKE ALL PRIVILEGES ON snapshot_calculations FROM propiq_app"
    )
    for table in (
        "users", "investor_profiles", "properties", "deals",
        "snapshot_inputs", "snapshot_outputs", "snapshot_intermediates",
        "snapshot_risk_flags", "snapshot_validation_warnings",
        "config_engine_versions", "config_sdlt_versions", "config_sdlt_bands",
        "config_corporation_tax_versions", "config_assumption_versions",
        "audit_calculations",
    ):
        op.execute(
            f"REVOKE ALL PRIVILEGES ON {table} FROM propiq_app"
        )

    op.execute("DROP ROLE IF EXISTS propiq_admin")
    op.execute("DROP ROLE IF EXISTS propiq_app")
