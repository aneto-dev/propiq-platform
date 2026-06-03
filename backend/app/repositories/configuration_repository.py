"""
ConfigurationRepository — SQLAlchemy implementation of IConfigurationRepository.

Read-focused: loads active configuration versions for calculation and specific
versions for snapshot reproduction. Admin write operations are INSERT-only.

Architecture:
    REPOSITORY_ARCHITECTURE.md Part 2.6, 5.6, 8.1–8.5, 14.
    DATABASE_SCHEMA_DESIGN.md Section 4 — configuration tables.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.configuration import (
    ConfigAssumptionVersion,
    ConfigCorporationTaxVersion,
    ConfigEngineVersion,
    ConfigSdltBand,
    ConfigSdltVersion,
)
from app.domain.errors import ConfigurationNotFoundError, PersistenceIntegrityError
from app.engine.contracts import (
    AssumptionConfig,
    CorporationTaxConfig,
    SDLTBand,
    SDLTConfig,
)
from app.repositories.interfaces.i_configuration import (
    AssumptionConfigSummary,
    AssumptionConfiguration,
    CorporationTaxConfigSummary,
    CorporationTaxConfiguration,
    EngineVersionRecord,
    SDLTConfiguration,
    SDLTConfigurationSummary,
)


class ConfigurationRepository:
    """
    SQLAlchemy implementation of IConfigurationRepository.

    Receives an AsyncSession as a constructor dependency. Does not commit —
    the caller (service layer) is responsible for session lifecycle.

    Architecture: REPOSITORY_ARCHITECTURE.md Part 13.1–13.3.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Active version reads — used on every calculation (Part 8.1)
    # ------------------------------------------------------------------

    async def find_active_sdlt_config(
        self, as_of_date: date
    ) -> SDLTConfig:
        """
        Return the most recent SDLT config with effective_from <= as_of_date.
        Loads all band records in a second query (Part 8.2).
        Raises ConfigurationNotFoundError if none found.
        """
        stmt = (
            select(ConfigSdltVersion)
            .where(ConfigSdltVersion.effective_from <= as_of_date)
            .order_by(ConfigSdltVersion.effective_from.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        version = result.scalar_one_or_none()
        if version is None:
            raise ConfigurationNotFoundError(config_type="sdlt")
        return await self._load_sdlt_with_bands(version)

    async def find_active_corporation_tax_config(
        self, as_of_date: date
    ) -> CorporationTaxConfig:
        """
        Return the most recent CT config with effective_from <= as_of_date.
        Raises ConfigurationNotFoundError if none found.
        """
        stmt = (
            select(ConfigCorporationTaxVersion)
            .where(ConfigCorporationTaxVersion.effective_from <= as_of_date)
            .order_by(ConfigCorporationTaxVersion.effective_from.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            raise ConfigurationNotFoundError(config_type="corporation_tax")
        return self._to_ct_domain(row)

    async def find_active_assumption_config(
        self, as_of_date: date
    ) -> AssumptionConfig:
        """
        Return the most recent assumption config with effective_from <= as_of_date.
        Raises ConfigurationNotFoundError if none found.
        """
        stmt = (
            select(ConfigAssumptionVersion)
            .where(ConfigAssumptionVersion.effective_from <= as_of_date)
            .order_by(ConfigAssumptionVersion.effective_from.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            raise ConfigurationNotFoundError(config_type="assumption")
        return self._to_assumption_domain(row)

    # ------------------------------------------------------------------
    # Specific version reads — snapshot reproduction (Part 8.3)
    # ------------------------------------------------------------------

    async def find_sdlt_config_by_id(
        self, version_id: uuid.UUID
    ) -> SDLTConfig:
        """
        Load the exact SDLT config version referenced by a snapshot.
        Raises ConfigurationNotFoundError if id does not exist.
        """
        stmt = select(ConfigSdltVersion).where(
            ConfigSdltVersion.id == version_id
        )
        result = await self._session.execute(stmt)
        version = result.scalar_one_or_none()
        if version is None:
            raise ConfigurationNotFoundError(
                config_type="sdlt", version_id=version_id
            )
        return await self._load_sdlt_with_bands(version)

    async def find_corporation_tax_config_by_id(
        self, version_id: uuid.UUID
    ) -> CorporationTaxConfig:
        """
        Load the exact CT config version referenced by a snapshot.
        Raises ConfigurationNotFoundError if id does not exist.
        """
        stmt = select(ConfigCorporationTaxVersion).where(
            ConfigCorporationTaxVersion.id == version_id
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            raise ConfigurationNotFoundError(
                config_type="corporation_tax", version_id=version_id
            )
        return self._to_ct_domain(row)

    async def find_assumption_config_by_id(
        self, version_id: uuid.UUID
    ) -> AssumptionConfig:
        """
        Load the exact assumption config version referenced by a snapshot.
        Raises ConfigurationNotFoundError if id does not exist.
        """
        stmt = select(ConfigAssumptionVersion).where(
            ConfigAssumptionVersion.id == version_id
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            raise ConfigurationNotFoundError(
                config_type="assumption", version_id=version_id
            )
        return self._to_assumption_domain(row)

    # ------------------------------------------------------------------
    # Version listing — admin and transparency views
    # ------------------------------------------------------------------

    async def find_all_sdlt_config_versions(
        self,
    ) -> list[SDLTConfigurationSummary]:
        """All SDLT versions ordered by effective_from DESC."""
        stmt = select(ConfigSdltVersion).order_by(
            ConfigSdltVersion.effective_from.desc()
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        summaries = []
        for row in rows:
            # Count bands for each version
            bands_stmt = select(ConfigSdltBand).where(
                ConfigSdltBand.sdlt_version_id == row.id
            )
            bands_result = await self._session.execute(bands_stmt)
            band_count = len(list(bands_result.scalars().all()))
            summaries.append(
                SDLTConfigurationSummary(
                    id=row.id,
                    effective_from=row.effective_from,
                    property_country=str(row.property_country.value)
                    if hasattr(row.property_country, "value")
                    else str(row.property_country),
                    additional_dwelling_surcharge_rate=Decimal(
                        str(row.additional_dwelling_surcharge_rate)
                    ),
                    band_count=band_count,
                )
            )
        return summaries

    async def find_all_corporation_tax_config_versions(
        self,
    ) -> list[CorporationTaxConfigSummary]:
        """All CT versions ordered by effective_from DESC."""
        stmt = select(ConfigCorporationTaxVersion).order_by(
            ConfigCorporationTaxVersion.effective_from.desc()
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [
            CorporationTaxConfigSummary(
                id=row.id,
                effective_from=row.effective_from,
                small_profits_rate=Decimal(str(row.small_profits_rate)),
                main_rate=Decimal(str(row.main_rate)),
            )
            for row in rows
        ]

    async def find_all_assumption_config_versions(
        self,
    ) -> list[AssumptionConfigSummary]:
        """All assumption versions ordered by effective_from DESC."""
        stmt = select(ConfigAssumptionVersion).order_by(
            ConfigAssumptionVersion.effective_from.desc()
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [
            AssumptionConfigSummary(
                id=row.id,
                effective_from=row.effective_from,
                void_rate_percent_default=Decimal(
                    str(row.void_rate_percent_default)
                ),
                stress_test_rate_percent=Decimal(
                    str(row.stress_test_rate_percent)
                ),
            )
            for row in rows
        ]

    async def find_all_engine_versions(self) -> list[EngineVersionRecord]:
        """All engine versions ordered by released_at DESC."""
        stmt = select(ConfigEngineVersion).order_by(
            ConfigEngineVersion.released_at.desc()
        )
        result = await self._session.execute(stmt)
        rows = result.scalars().all()
        return [
            EngineVersionRecord(
                version_string=row.version_string,
                released_at=row.released_at,
                change_summary=row.change_summary,
                is_breaking_change=row.is_breaking_change,
                specification_ref=row.specification_ref,
            )
            for row in rows
        ]

    # ------------------------------------------------------------------
    # Admin writes — INSERT only, append-only (RI-04)
    # Invoked exclusively from admin service layer.
    # ------------------------------------------------------------------

    async def save_sdlt_config(
        self, config: SDLTConfiguration
    ) -> None:
        raise NotImplementedError(
            "save_sdlt_config: admin write not yet implemented. "
            "Requires effective_from, property_country, notes, and source_attribution "
            "in addition to the SDLTConfig values."
        )

    async def save_corporation_tax_config(
        self, config: CorporationTaxConfiguration
    ) -> None:
        raise NotImplementedError(
            "save_corporation_tax_config: admin write not yet implemented."
        )

    async def save_assumption_config(
        self, config: AssumptionConfiguration
    ) -> None:
        raise NotImplementedError(
            "save_assumption_config: admin write not yet implemented."
        )

    async def save_engine_version(self, version: EngineVersionRecord) -> None:
        """Insert a new engine version registry entry."""
        row = ConfigEngineVersion(
            version_string=version.version_string,
            released_at=version.released_at,
            change_summary=version.change_summary,
            is_breaking_change=version.is_breaking_change,
            specification_ref=version.specification_ref,
        )
        self._session.add(row)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _load_sdlt_with_bands(
        self, version: ConfigSdltVersion
    ) -> SDLTConfig:
        """
        Load SDLT bands for the given version and assemble the domain object.
        Raises PersistenceIntegrityError if no bands found (data integrity failure).
        Architecture: REPOSITORY_ARCHITECTURE.md Part 8.2.
        """
        bands_stmt = (
            select(ConfigSdltBand)
            .where(ConfigSdltBand.sdlt_version_id == version.id)
            .order_by(ConfigSdltBand.band_order)
        )
        result = await self._session.execute(bands_stmt)
        band_rows = list(result.scalars().all())
        if not band_rows:
            raise PersistenceIntegrityError(
                f"SDLT version {version.id} has no band records — "
                "data integrity violation"
            )
        return self._to_sdlt_domain(version, band_rows)

    def _to_sdlt_domain(
        self,
        version: ConfigSdltVersion,
        bands: list[ConfigSdltBand],
    ) -> SDLTConfig:
        """
        Convert ConfigSdltVersion ORM row + [ConfigSdltBand] rows
        → SDLTConfig domain type.

        Architecture: REPOSITORY_ARCHITECTURE.md Part 4.1 (_to_domain mapping).
        IMPLEMENTATION_ROADMAP.md Commit 4.3 — _to_sdlt_domain() spec.
        """
        return SDLTConfig(
            bands=tuple(
                SDLTBand(
                    band_lower=Decimal(str(band.band_lower)),
                    band_upper=Decimal(str(band.band_upper))
                    if band.band_upper is not None
                    else None,
                    rate=Decimal(str(band.rate)),
                )
                for band in bands
            ),
            additional_dwelling_surcharge_rate=Decimal(
                str(version.additional_dwelling_surcharge_rate)
            ),
        )

    def _to_ct_domain(
        self, row: ConfigCorporationTaxVersion
    ) -> CorporationTaxConfig:
        """Convert ConfigCorporationTaxVersion ORM row → CorporationTaxConfig."""
        return CorporationTaxConfig(
            small_profits_rate=Decimal(str(row.small_profits_rate)),
            small_profits_upper_threshold=Decimal(
                str(row.small_profits_upper_threshold)
            ),
            main_rate=Decimal(str(row.main_rate)),
            main_rate_lower_threshold=Decimal(str(row.main_rate_lower_threshold)),
            marginal_relief_numerator=int(row.marginal_relief_numerator),
            marginal_relief_denominator=int(row.marginal_relief_denominator),
        )

    def _to_assumption_domain(
        self, row: ConfigAssumptionVersion
    ) -> AssumptionConfig:
        """Convert ConfigAssumptionVersion ORM row → AssumptionConfig."""
        return AssumptionConfig(
            void_rate_percent_default=Decimal(str(row.void_rate_percent_default)),
            letting_agent_fee_percent_default=Decimal(
                str(row.letting_agent_fee_percent_default)
            ),
            letting_agent_vat_rate_percent=Decimal(
                str(row.letting_agent_vat_rate_percent)
            ),
            maintenance_reserve_percent_default=Decimal(
                str(row.maintenance_reserve_percent_default)
            ),
            landlord_insurance_annual_default=Decimal(
                str(row.landlord_insurance_annual_default)
            ),
            purchase_legal_costs_default=Decimal(
                str(row.purchase_legal_costs_default)
            ),
            accountancy_cost_individual_default=Decimal(
                str(row.accountancy_cost_individual_default)
            ),
            accountancy_cost_ltd_default=Decimal(
                str(row.accountancy_cost_ltd_default)
            ),
            stress_test_rate_percent=Decimal(str(row.stress_test_rate_percent)),
            icr_threshold_basic_rate_percent=Decimal(
                str(row.icr_threshold_basic_rate_percent)
            ),
            icr_threshold_higher_rate_percent=Decimal(
                str(row.icr_threshold_higher_rate_percent)
            ),
        )
