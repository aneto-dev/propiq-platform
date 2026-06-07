"""
Calculation request/response Pydantic v2 schemas.

Architecture:
    APPLICATION_SERVICE_ARCHITECTURE.md Part 15.
    IMPLEMENTATION_ROADMAP.md Commit 6.2.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.api.v1.schemas.common import FieldError
from app.api.v1.schemas.snapshot import SnapshotSummaryResponse
from app.domain.enums import (
    DealStatus,
    IncomeTaxBand,
    MortgageType,
    OwnershipStructure,
    PropertyCountry,
    PropertyType,
    Tenure,
)


class CalculationRequest(BaseModel):
    """
    Request body for POST /api/v1/calculations/.

    Required fields must be supplied. Optional fields, if absent, are resolved
    to the active configuration defaults by ConfigurationService.resolve_defaults().
    """

    deal_id: uuid.UUID
    calculation_date: date | None = None  # defaults to today in the route handler

    # Required inputs
    purchase_price: Decimal
    monthly_rent: Decimal
    deposit_amount: Decimal
    mortgage_interest_rate: Decimal
    mortgage_term_years: int
    mortgage_type: MortgageType
    ownership_structure: OwnershipStructure
    income_tax_band: IncomeTaxBand | None = None  # required for INDIVIDUAL
    is_additional_dwelling: bool
    property_type: PropertyType
    tenure: Tenure
    property_country: PropertyCountry
    postcode: str

    # Optional inputs — absent = use config default
    void_rate_percent: Decimal | None = None
    letting_agent_fee_percent: Decimal | None = None
    maintenance_reserve_percent: Decimal | None = None
    landlord_insurance_annual: Decimal | None = None
    purchase_legal_costs: Decimal | None = None
    refurbishment_cost: Decimal | None = None
    annual_service_charge: Decimal | None = None
    annual_ground_rent: Decimal | None = None
    annual_accountancy_cost: Decimal | None = None
    lease_years_remaining: int | None = None


class CalculationSuccessResponse(BaseModel):
    """
    Response for a successful calculation.

    Returns the snapshot id, the deal's new status, and a display-level
    summary of the snapshot outputs and risk flags.
    """

    snapshot_id: uuid.UUID
    deal_status: DealStatus
    snapshot: SnapshotSummaryResponse


class CalculationValidationFailureResponse(BaseModel):
    """
    Response for a calculation that fails engine validation.

    field_errors carries structured errors that the frontend maps to
    specific form fields.
    """

    detail: str = "Calculation validation failed"
    field_errors: list[FieldError]
