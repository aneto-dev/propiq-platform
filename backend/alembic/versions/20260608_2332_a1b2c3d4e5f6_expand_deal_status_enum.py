"""expand deal_status_enum with workflow stages

Revision ID: a1b2c3d4e5f6
Revises: 1d56deba40c1
Create Date: 2026-06-08 23:32:00.000000+00:00

Adds OFFER_SUBMITTED, PURCHASED, HELD, EXITED to the deal_status_enum
PostgreSQL type. These are purely additive — no existing rows are affected.

Architecture: DOMAIN_MODEL_ARCHITECTURE.md Part 19.1.
IMPLEMENTATION_ROADMAP.md Phase 10 Feature 1 — Deal status tracking.
"""

from __future__ import annotations

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "1d56deba40c1"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    # ALTER TYPE … ADD VALUE is transactional in PostgreSQL 12+.
    # Values are added in pipeline order so the enum definition is
    # self-documenting.
    op.execute("ALTER TYPE deal_status_enum ADD VALUE IF NOT EXISTS 'OFFER_SUBMITTED'")
    op.execute("ALTER TYPE deal_status_enum ADD VALUE IF NOT EXISTS 'PURCHASED'")
    op.execute("ALTER TYPE deal_status_enum ADD VALUE IF NOT EXISTS 'HELD'")
    op.execute("ALTER TYPE deal_status_enum ADD VALUE IF NOT EXISTS 'EXITED'")


def downgrade() -> None:
    # PostgreSQL does not support removing individual values from an enum
    # without recreating the type. Downgrade is intentionally a no-op:
    # removing enum values from a live type requires a full type rebuild and
    # data migration — not appropriate for a hotfix rollback path.
    # To fully revert, restore the prior migration baseline.
    pass
