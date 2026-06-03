"""
IConfigurationRepository — abstract interface for configuration version persistence.

Also defines EngineVersionRecord and config summary projection types.

Architecture: REPOSITORY_ARCHITECTURE.md Part 2.6, 5.6.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol, runtime_checkable

from app.engine.contracts import AssumptionConfig, CorporationTaxConfig, SDLTConfig

# ---------------------------------------------------------------------------
# Type aliases — repository layer uses descriptive names; underlying types
# are the engine contract definitions. This ensures the configuration loaded
# by the repository is directly usable by the engine without conversion.
# ---------------------------------------------------------------------------

SDLTConfiguration = SDLTConfig
CorporationTaxConfiguration = CorporationTaxConfig
AssumptionConfiguration = AssumptionConfig


# ---------------------------------------------------------------------------
# EngineVersionRecord — registry entry for a deployed engine version.
# Architecture: REPOSITORY_ARCHITECTURE.md Part 2.6.
# DATABASE_SCHEMA_DESIGN.md Section 4 — config_engine_versions.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EngineVersionRecord:
    """
    Registry entry for a deployed underwriting engine version.

    version_string is the semantic version (e.g. "1.0.0") and is the
    primary key — stored on snapshot_calculations.engine_version for
    cross-reference without a JOIN.
    """

    version_string: str
    released_at: datetime
    change_summary: str
    is_breaking_change: bool
    specification_ref: str | None


# ---------------------------------------------------------------------------
# Summary projection types — for version listing views (admin and transparency)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SDLTConfigurationSummary:
    """Minimal projection for SDLT version list view."""

    id: uuid.UUID
    effective_from: date
    property_country: str
    additional_dwelling_surcharge_rate: Decimal
    band_count: int


@dataclass(frozen=True)
class CorporationTaxConfigSummary:
    """Minimal projection for Corporation Tax version list view."""

    id: uuid.UUID
    effective_from: date
    small_profits_rate: Decimal
    main_rate: Decimal


@dataclass(frozen=True)
class AssumptionConfigSummary:
    """Minimal projection for Assumption version list view."""

    id: uuid.UUID
    effective_from: date
    void_rate_percent_default: Decimal
    stress_test_rate_percent: Decimal


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------


@runtime_checkable
class IConfigurationRepository(Protocol):
    """
    Read-focused interface to versioned configuration data.

    All reads are active-version resolution or specific-ID lookup.
    Writes are admin-only INSERTs — never UPDATEs or DELETEs (RI-04).

    Active version resolution:
        SELECT * FROM config_[name]_versions
        WHERE effective_from <= :as_of_date
        ORDER BY effective_from DESC LIMIT 1

    This runs three times per calculation (one per table). The result is
    passed to the engine as EngineConfig. Version IDs are stored in the
    snapshot for historical reproducibility.

    Architecture: REPOSITORY_ARCHITECTURE.md Part 2.6, 5.6, 8.1–8.5.
    """

    # ------------------------------------------------------------------
    # Active version reads — used on every calculation
    # ------------------------------------------------------------------

    async def find_active_sdlt_config(
        self, as_of_date: date
    ) -> SDLTConfiguration:
        """
        Return the most recent SDLT config with effective_from <= as_of_date.
        Includes all band records (loaded together — Part 8.2).
        Raises ConfigurationNotFoundError if no config exists for the date.
        """
        ...

    async def find_active_corporation_tax_config(
        self, as_of_date: date
    ) -> CorporationTaxConfiguration:
        """
        Return the most recent CT config with effective_from <= as_of_date.
        Raises ConfigurationNotFoundError if no config exists for the date.
        """
        ...

    async def find_active_assumption_config(
        self, as_of_date: date
    ) -> AssumptionConfiguration:
        """
        Return the most recent assumption config with effective_from <= as_of_date.
        Raises ConfigurationNotFoundError if no config exists for the date.
        """
        ...

    # ------------------------------------------------------------------
    # Specific version reads — used for snapshot reproduction (RI-12)
    # ------------------------------------------------------------------

    async def find_sdlt_config_by_id(
        self, version_id: uuid.UUID
    ) -> SDLTConfiguration:
        """
        Load the exact SDLT config version referenced by a snapshot.
        Raises ConfigurationNotFoundError if id does not exist.
        """
        ...

    async def find_corporation_tax_config_by_id(
        self, version_id: uuid.UUID
    ) -> CorporationTaxConfiguration:
        """
        Load the exact CT config version referenced by a snapshot.
        Raises ConfigurationNotFoundError if id does not exist.
        """
        ...

    async def find_assumption_config_by_id(
        self, version_id: uuid.UUID
    ) -> AssumptionConfiguration:
        """
        Load the exact assumption config version referenced by a snapshot.
        Raises ConfigurationNotFoundError if id does not exist.
        """
        ...

    # ------------------------------------------------------------------
    # Admin writes — INSERT only, append-only (RI-04)
    # ------------------------------------------------------------------

    async def save_sdlt_config(self, config: SDLTConfiguration) -> None:
        """
        Insert a new SDLT config version and all its bands atomically.
        The version root record and all band records commit together.
        Architecture: REPOSITORY_ARCHITECTURE.md Part 10.4.
        """
        ...

    async def save_corporation_tax_config(
        self, config: CorporationTaxConfiguration
    ) -> None:
        """Insert a new Corporation Tax config version."""
        ...

    async def save_assumption_config(
        self, config: AssumptionConfiguration
    ) -> None:
        """Insert a new assumption config version."""
        ...

    async def save_engine_version(
        self, version: EngineVersionRecord
    ) -> None:
        """Insert a new engine version registry entry."""
        ...

    # ------------------------------------------------------------------
    # Version listing — admin and transparency views
    # ------------------------------------------------------------------

    async def find_all_sdlt_config_versions(
        self,
    ) -> list[SDLTConfigurationSummary]:
        """All SDLT config versions, ordered by effective_from DESC."""
        ...

    async def find_all_corporation_tax_config_versions(
        self,
    ) -> list[CorporationTaxConfigSummary]:
        """All CT config versions, ordered by effective_from DESC."""
        ...

    async def find_all_assumption_config_versions(
        self,
    ) -> list[AssumptionConfigSummary]:
        """All assumption config versions, ordered by effective_from DESC."""
        ...

    async def find_all_engine_versions(self) -> list[EngineVersionRecord]:
        """All engine version registry entries, ordered by released_at DESC."""
        ...
