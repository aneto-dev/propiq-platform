"""
Deal request/response Pydantic v2 schemas.

Architecture:
    APPLICATION_SERVICE_ARCHITECTURE.md Part 15.
    IMPLEMENTATION_ROADMAP.md Commit 6.2.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.api.v1.schemas.common import MoneyStr
from app.domain.enums import (
    DealStatus,
    IncomeTaxBand,
    MortgageType,
    OwnershipStructure,
)


class DealWorkingInputsSchema(BaseModel):
    """Current working inputs for a deal — all fields optional (may be incomplete)."""

    purchase_price: Decimal | None = None
    monthly_rent: Decimal | None = None
    deposit_amount: Decimal | None = None
    mortgage_interest_rate: Decimal | None = None
    mortgage_term_years: int | None = None
    mortgage_type: MortgageType | None = None
    ownership_structure: OwnershipStructure | None = None
    income_tax_band: IncomeTaxBand | None = None
    is_additional_dwelling: bool | None = None
    void_rate_percent: Decimal | None = None
    letting_agent_fee_percent: Decimal | None = None
    maintenance_reserve_percent: Decimal | None = None
    landlord_insurance_annual: Decimal | None = None
    purchase_legal_costs: Decimal | None = None
    refurbishment_cost: Decimal | None = None
    annual_service_charge: Decimal | None = None
    annual_ground_rent: Decimal | None = None
    annual_accountancy_cost: Decimal | None = None


class UpdateWorkingInputsRequest(BaseModel):
    """
    Request body for PATCH /api/v1/deals/{id}/inputs.
    Only supplied fields are applied — absent fields leave current value unchanged.
    """

    purchase_price: Decimal | None = None
    monthly_rent: Decimal | None = None
    deposit_amount: Decimal | None = None
    mortgage_interest_rate: Decimal | None = None
    mortgage_term_years: int | None = None
    mortgage_type: MortgageType | None = None
    ownership_structure: OwnershipStructure | None = None
    income_tax_band: IncomeTaxBand | None = None
    is_additional_dwelling: bool | None = None
    void_rate_percent: Decimal | None = None
    letting_agent_fee_percent: Decimal | None = None
    maintenance_reserve_percent: Decimal | None = None
    landlord_insurance_annual: Decimal | None = None
    purchase_legal_costs: Decimal | None = None
    refurbishment_cost: Decimal | None = None
    annual_service_charge: Decimal | None = None
    annual_ground_rent: Decimal | None = None
    annual_accountancy_cost: Decimal | None = None


class DealResponse(BaseModel):
    """Response for a single deal with full working inputs."""

    id: uuid.UUID
    user_id: uuid.UUID
    property_id: uuid.UUID
    label: str
    status: DealStatus
    investor_profile_id: uuid.UUID | None
    latest_snapshot_id: uuid.UUID | None
    working_inputs: DealWorkingInputsSchema
    created_at: datetime | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class DealSummaryResponse(BaseModel):
    """
    Lightweight deal summary for list views.
    Includes key metrics from the latest snapshot (None for DRAFT deals).
    Monetary fields are serialised as strings to avoid float precision loss.
    """

    id: uuid.UUID
    label: str
    status: DealStatus
    property_id: uuid.UUID
    latest_snapshot_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    latest_snapshot_cash_flow_gbp: MoneyStr | None
    latest_snapshot_gross_yield: str | None
    latest_snapshot_calculated_at: datetime | None
    latest_snapshot_risk_flag_count_high: int | None

    model_config = {"from_attributes": True}
