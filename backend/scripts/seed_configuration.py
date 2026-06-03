#!/usr/bin/env python3
"""
Configuration seed script — v1.0 defaults.

Inserts the initial configuration versions defined in
DATABASE_SCHEMA_DESIGN.md Section 9 into the database.

Idempotent: safe to re-run. All inserts use ON CONFLICT DO NOTHING.
No record is modified if it already exists.

Records inserted (if absent):
  1. config_engine_versions  — engine "1.0.0"
  2. config_sdlt_versions    — England, effective 2025-04-01
  3. config_sdlt_bands       — 5 bands for the above SDLT version
  4. config_corporation_tax_versions — rates effective 2023-04-01
  5. config_assumption_versions     — v1.0 defaults, effective 2025-01-01

Usage:
    cd backend
    poetry run python scripts/seed_configuration.py

    # Or with an explicit database URL:
    DATABASE_URL=postgresql+asyncpg://propiq:propiq@localhost:5432/propiq \
        poetry run python scripts/seed_configuration.py

Architecture:
    DATABASE_SCHEMA_DESIGN.md Section 9 — Configuration Seed Data
    PERSISTENCE_ARCHITECTURE.md Part 14.4 — Configuration Data Migrations
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from datetime import UTC, datetime, date
from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# ---------------------------------------------------------------------------
# Path bootstrap: allow running from backend/ or from repo root.
# ---------------------------------------------------------------------------
import os

_backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from app.core.config import get_settings  # noqa: E402


# ---------------------------------------------------------------------------
# Seed values — DATABASE_SCHEMA_DESIGN.md Section 9
# ---------------------------------------------------------------------------

# config_engine_versions
ENGINE_VERSION = "1.0.0"
ENGINE_CHANGE_SUMMARY = (
    "Initial engine release. Implements CALCULATION_SPEC v1.0. "
    "Covers RESIDENTIAL_SINGLE_LET, ENGLAND, INDIVIDUAL and LIMITED_COMPANY "
    "ownership, interest-only and repayment mortgages, SDLT with additional "
    "dwelling surcharge, Section 24 tax handling, Corporation Tax Pathway B."
)
ENGINE_SPECIFICATION_REF = "CALCULATION_SPEC.md v1.0"

# config_sdlt_versions — England, effective 1 April 2025
SDLT_EFFECTIVE_FROM = date(2025, 4, 1)
SDLT_COUNTRY = "ENGLAND"
SDLT_SURCHARGE_RATE = Decimal("0.030000")
SDLT_NOTES = (
    "Post-temporary threshold reversion. "
    "Residential rates effective from 1 April 2025."
)
SDLT_SOURCE = (
    "HMRC SDLT guidance. Finance Act 2024. "
    "Temporary nil-rate band threshold ended March 2025."
)

# config_sdlt_bands — 5 bands for England post-April 2025
SDLT_BANDS = [
    # (band_order, band_lower, band_upper, rate)
    (1, Decimal("0.00"),        Decimal("125000.00"),  Decimal("0.000000")),
    (2, Decimal("125000.00"),   Decimal("250000.00"),  Decimal("0.020000")),
    (3, Decimal("250000.00"),   Decimal("925000.00"),  Decimal("0.050000")),
    (4, Decimal("925000.00"),   Decimal("1500000.00"), Decimal("0.100000")),
    (5, Decimal("1500000.00"),  None,                  Decimal("0.120000")),
]

# config_corporation_tax_versions — Finance Act 2023, effective 2023-04-01
CT_EFFECTIVE_FROM = date(2023, 4, 1)
CT_SMALL_PROFITS_RATE = Decimal("0.190000")
CT_SMALL_PROFITS_THRESHOLD = Decimal("50000.000000")
CT_MAIN_RATE = Decimal("0.250000")
CT_MAIN_RATE_THRESHOLD = Decimal("250000.000000")
CT_MR_NUMERATOR = 3
CT_MR_DENOMINATOR = 200
CT_NOTES = (
    "Finance Act 2023. Small profits rate 19%. Main rate 25%. "
    "Marginal relief 3/200 fraction. Rates effective from 1 April 2023."
)
CT_SOURCE = "Finance Act 2023. HMRC Corporation Tax guidance."

# config_assumption_versions — v1.0 defaults, effective 2025-01-01
ASSUMPTION_EFFECTIVE_FROM = date(2025, 1, 1)
ASSUMPTION_VOID_RATE = Decimal("3.850000")
ASSUMPTION_LETTING_AGENT_FEE = Decimal("10.000000")
ASSUMPTION_LETTING_AGENT_VAT = Decimal("20.000000")
ASSUMPTION_MAINTENANCE = Decimal("1.000000")
ASSUMPTION_INSURANCE = Decimal("800.000000")
ASSUMPTION_LEGAL_COSTS = Decimal("2500.000000")
ASSUMPTION_ACCOUNTANCY_INDIVIDUAL = Decimal("0.000000")
ASSUMPTION_ACCOUNTANCY_LTD = Decimal("1200.000000")
ASSUMPTION_STRESS_RATE = Decimal("5.500000")
ASSUMPTION_ICR_BASIC = Decimal("125.000000")
ASSUMPTION_ICR_HIGHER = Decimal("145.000000")
ASSUMPTION_NOTES = (
    "Initial v1.0 assumption defaults. "
    "Sources: ARLA Propertymark, HMRC, industry market data 2023/24."
)
ASSUMPTION_SOURCE = (
    "ARLA Propertymark Letting Agent Survey 2023. "
    "HMRC landlord guidance 2024. "
    "PRA supervisory statement SS13/16."
)


# ---------------------------------------------------------------------------
# Seed functions
# ---------------------------------------------------------------------------

async def seed_engine_version(conn: object) -> bool:
    """
    Insert config_engine_versions row for "1.0.0".
    Returns True if inserted, False if already present.
    """
    result = await conn.execute(
        text(
            "INSERT INTO config_engine_versions "
            "(version_string, released_at, change_summary,"
            " is_breaking_change, specification_ref, created_at) "
            "VALUES (:version_string, :released_at, :change_summary,"
            " :is_breaking_change, :specification_ref, :created_at) "
            "ON CONFLICT (version_string) DO NOTHING"
        ),
        {
            "version_string": ENGINE_VERSION,
            "released_at": datetime.now(UTC),
            "change_summary": ENGINE_CHANGE_SUMMARY,
            "is_breaking_change": False,
            "specification_ref": ENGINE_SPECIFICATION_REF,
            "created_at": datetime.now(UTC),
        },
    )
    return result.rowcount == 1


async def seed_sdlt_version(conn: object) -> tuple[bool, uuid.UUID]:
    """
    Insert config_sdlt_versions row for England 2025-04-01.
    Returns (inserted: bool, sdlt_version_id: UUID).
    If already present, returns the existing ID.
    """
    # Check for existing record first (to retrieve the ID for band seeding).
    existing = await conn.execute(
        text(
            "SELECT id FROM config_sdlt_versions "
            "WHERE effective_from = :effective_from "
            "AND property_country = 'ENGLAND'"
        ),
        {"effective_from": SDLT_EFFECTIVE_FROM},
    )
    row = existing.fetchone()
    if row is not None:
        return False, uuid.UUID(str(row[0]))

    new_id = uuid.uuid4()
    await conn.execute(
        text(
            "INSERT INTO config_sdlt_versions "
            "(id, effective_from, property_country,"
            " additional_dwelling_surcharge_rate,"
            " notes, source_attribution, created_at) "
            "VALUES (:id, :effective_from, :property_country,"
            " :surcharge_rate, :notes, :source, :created_at)"
        ),
        {
            "id": new_id,
            "effective_from": SDLT_EFFECTIVE_FROM,
            "property_country": SDLT_COUNTRY,
            "surcharge_rate": SDLT_SURCHARGE_RATE,
            "notes": SDLT_NOTES,
            "source": SDLT_SOURCE,
            "created_at": datetime.now(UTC),
        },
    )
    return True, new_id


async def seed_sdlt_bands(conn: object, sdlt_version_id: uuid.UUID) -> int:
    """
    Insert config_sdlt_bands rows for the given SDLT version.
    Returns number of bands inserted (0 if all already present).
    """
    inserted = 0
    for band_order, band_lower, band_upper, rate in SDLT_BANDS:
        result = await conn.execute(
            text(
                "INSERT INTO config_sdlt_bands "
                "(id, sdlt_version_id, band_order,"
                " band_lower, band_upper, rate, created_at) "
                "VALUES (:id, :sdlt_version_id, :band_order,"
                " :band_lower, :band_upper, :rate, :created_at) "
                "ON CONFLICT (sdlt_version_id, band_order) DO NOTHING"
            ),
            {
                "id": uuid.uuid4(),
                "sdlt_version_id": sdlt_version_id,
                "band_order": band_order,
                "band_lower": band_lower,
                "band_upper": band_upper,
                "rate": rate,
                "created_at": datetime.now(UTC),
            },
        )
        if result.rowcount == 1:
            inserted += 1
    return inserted


async def seed_corporation_tax_version(conn: object) -> bool:
    """
    Insert config_corporation_tax_versions row for 2023-04-01 rates.
    Returns True if inserted, False if already present.
    """
    result = await conn.execute(
        text(
            "INSERT INTO config_corporation_tax_versions "
            "(id, effective_from, small_profits_rate,"
            " small_profits_upper_threshold, main_rate,"
            " main_rate_lower_threshold, marginal_relief_numerator,"
            " marginal_relief_denominator, notes, source_attribution,"
            " created_at) "
            "VALUES (:id, :effective_from, :small_profits_rate,"
            " :small_profits_threshold, :main_rate, :main_rate_threshold,"
            " :mr_numerator, :mr_denominator, :notes, :source, :created_at) "
            "ON CONFLICT (effective_from) DO NOTHING"
        ),
        {
            "id": uuid.uuid4(),
            "effective_from": CT_EFFECTIVE_FROM,
            "small_profits_rate": CT_SMALL_PROFITS_RATE,
            "small_profits_threshold": CT_SMALL_PROFITS_THRESHOLD,
            "main_rate": CT_MAIN_RATE,
            "main_rate_threshold": CT_MAIN_RATE_THRESHOLD,
            "mr_numerator": CT_MR_NUMERATOR,
            "mr_denominator": CT_MR_DENOMINATOR,
            "notes": CT_NOTES,
            "source": CT_SOURCE,
            "created_at": datetime.now(UTC),
        },
    )
    return result.rowcount == 1


async def seed_assumption_version(conn: object) -> bool:
    """
    Insert config_assumption_versions row for 2025-01-01 defaults.
    Returns True if inserted, False if already present.
    """
    result = await conn.execute(
        text(
            "INSERT INTO config_assumption_versions "
            "(id, effective_from,"
            " void_rate_percent_default,"
            " letting_agent_fee_percent_default,"
            " letting_agent_vat_rate_percent,"
            " maintenance_reserve_percent_default,"
            " landlord_insurance_annual_default,"
            " purchase_legal_costs_default,"
            " accountancy_cost_individual_default,"
            " accountancy_cost_ltd_default,"
            " stress_test_rate_percent,"
            " icr_threshold_basic_rate_percent,"
            " icr_threshold_higher_rate_percent,"
            " notes, source_attribution, created_at) "
            "VALUES (:id, :effective_from,"
            " :void_rate, :letting_fee, :letting_vat,"
            " :maintenance, :insurance, :legal_costs,"
            " :accountancy_individual, :accountancy_ltd,"
            " :stress_rate, :icr_basic, :icr_higher,"
            " :notes, :source, :created_at) "
            "ON CONFLICT (effective_from) DO NOTHING"
        ),
        {
            "id": uuid.uuid4(),
            "effective_from": ASSUMPTION_EFFECTIVE_FROM,
            "void_rate": ASSUMPTION_VOID_RATE,
            "letting_fee": ASSUMPTION_LETTING_AGENT_FEE,
            "letting_vat": ASSUMPTION_LETTING_AGENT_VAT,
            "maintenance": ASSUMPTION_MAINTENANCE,
            "insurance": ASSUMPTION_INSURANCE,
            "legal_costs": ASSUMPTION_LEGAL_COSTS,
            "accountancy_individual": ASSUMPTION_ACCOUNTANCY_INDIVIDUAL,
            "accountancy_ltd": ASSUMPTION_ACCOUNTANCY_LTD,
            "stress_rate": ASSUMPTION_STRESS_RATE,
            "icr_basic": ASSUMPTION_ICR_BASIC,
            "icr_higher": ASSUMPTION_ICR_HIGHER,
            "notes": ASSUMPTION_NOTES,
            "source": ASSUMPTION_SOURCE,
            "created_at": datetime.now(UTC),
        },
    )
    return result.rowcount == 1


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def run_seed() -> None:
    settings = get_settings()
    if not settings.database_url:
        print("ERROR: DATABASE_URL is not set.", file=sys.stderr)
        print(
            "Set DATABASE_URL in .env or pass as environment variable.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("PropIQ — Configuration seed script")
    print(f"Database: {settings.database_url.split('@')[-1]}")  # hide credentials
    print()

    engine = create_async_engine(settings.database_url, echo=False)

    async with engine.begin() as conn:
        # 1 — config_engine_versions
        inserted = await seed_engine_version(conn)
        status = "INSERTED" if inserted else "already present"
        print(f"  config_engine_versions  v{ENGINE_VERSION}  → {status}")

        # 2 — config_sdlt_versions
        sdlt_inserted, sdlt_version_id = await seed_sdlt_version(conn)
        status = "INSERTED" if sdlt_inserted else "already present"
        print(
            f"  config_sdlt_versions    "
            f"ENGLAND {SDLT_EFFECTIVE_FROM}  → {status}"
        )

        # 3 — config_sdlt_bands
        bands_inserted = await seed_sdlt_bands(conn, sdlt_version_id)
        total_bands = len(SDLT_BANDS)
        if bands_inserted == total_bands:
            print(f"  config_sdlt_bands       {bands_inserted}/{total_bands} bands  → INSERTED")
        elif bands_inserted == 0:
            print(f"  config_sdlt_bands       {total_bands}/{total_bands} bands  → already present")
        else:
            print(
                f"  config_sdlt_bands       "
                f"{bands_inserted}/{total_bands} bands  → PARTIALLY INSERTED"
            )

        # 4 — config_corporation_tax_versions
        inserted = await seed_corporation_tax_version(conn)
        status = "INSERTED" if inserted else "already present"
        print(
            f"  config_corporation_tax  "
            f"effective {CT_EFFECTIVE_FROM}  → {status}"
        )

        # 5 — config_assumption_versions
        inserted = await seed_assumption_version(conn)
        status = "INSERTED" if inserted else "already present"
        print(
            f"  config_assumption       "
            f"effective {ASSUMPTION_EFFECTIVE_FROM}  → {status}"
        )

    await engine.dispose()
    print()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(run_seed())
