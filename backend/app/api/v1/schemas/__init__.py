"""
Pydantic v2 DTO schemas for the PropIQ API v1.

Re-exports all request and response models for convenient import by route
modules.

All monetary fields are serialised as strings in decimal format to prevent
JSON float precision loss (e.g. "annual_cash_flow_gbp": "-331.90").

Architecture:
    APPLICATION_SERVICE_ARCHITECTURE.md Part 15 — DTO boundaries.
    IMPLEMENTATION_ROADMAP.md Commit 6.2.
"""

from app.api.v1.schemas.calculation import (
    CalculationRequest,
    CalculationSuccessResponse,
    CalculationValidationFailureResponse,
)
from app.api.v1.schemas.common import (
    ErrorResponse,
    FieldError,
    MoneyStr,
    RateStr,
)
from app.api.v1.schemas.deal import (
    DealResponse,
    DealSummaryResponse,
    DealWorkingInputsSchema,
    UpdateWorkingInputsRequest,
)
from app.api.v1.schemas.property import (
    CreatePropertyRequest,
    PropertyResponse,
)
from app.api.v1.schemas.snapshot import (
    RiskFlagResponse,
    SnapshotHistoryEntryResponse,
    SnapshotOutputsResponse,
    SnapshotSummaryResponse,
)

__all__ = [
    # common
    "ErrorResponse",
    "FieldError",
    "MoneyStr",
    "RateStr",
    # property
    "CreatePropertyRequest",
    "PropertyResponse",
    # deal
    "DealWorkingInputsSchema",
    "UpdateWorkingInputsRequest",
    "DealResponse",
    "DealSummaryResponse",
    # calculation
    "CalculationRequest",
    "CalculationSuccessResponse",
    "CalculationValidationFailureResponse",
    # snapshot
    "RiskFlagResponse",
    "SnapshotOutputsResponse",
    "SnapshotSummaryResponse",
    "SnapshotHistoryEntryResponse",
]
