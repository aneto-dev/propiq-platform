"""
Repository interface package.

Re-exports all abstract repository interfaces so service-layer code can
import from a single location.

Architecture: REPOSITORY_ARCHITECTURE.md Part 5.
"""

from app.repositories.interfaces.i_audit import (
    CalculationAuditEvent,
    IAuditRepository,
)
from app.repositories.interfaces.i_configuration import (
    AssumptionConfigSummary,
    AssumptionConfiguration,
    CorporationTaxConfigSummary,
    CorporationTaxConfiguration,
    EngineVersionRecord,
    IConfigurationRepository,
    SDLTConfiguration,
    SDLTConfigurationSummary,
)
from app.repositories.interfaces.i_deal import DealSummary, IDealRepository
from app.repositories.interfaces.i_investor_profile import (
    IInvestorProfileRepository,
)
from app.repositories.interfaces.i_property import IPropertyRepository
from app.repositories.interfaces.i_snapshot import (
    ISnapshotRepository,
    SnapshotHistoryEntry,
    SnapshotSummary,
)
from app.repositories.interfaces.i_user import IUserRepository

__all__ = [
    # Interfaces
    "IAuditRepository",
    "IConfigurationRepository",
    "IDealRepository",
    "IInvestorProfileRepository",
    "IPropertyRepository",
    "ISnapshotRepository",
    "IUserRepository",
    # Projection types
    "CalculationAuditEvent",
    "DealSummary",
    "SnapshotHistoryEntry",
    "SnapshotSummary",
    # Configuration types
    "AssumptionConfiguration",
    "AssumptionConfigSummary",
    "CorporationTaxConfiguration",
    "CorporationTaxConfigSummary",
    "EngineVersionRecord",
    "SDLTConfiguration",
    "SDLTConfigurationSummary",
]
