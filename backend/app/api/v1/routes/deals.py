"""
Deal CRUD routes.

Routes:
    POST   /api/v1/deals/                   → 201 DealResponse
    GET    /api/v1/deals/                   → 200 list of DealSummaryResponse
    GET    /api/v1/deals/{id}/              → 200 DealResponse
    PATCH  /api/v1/deals/{id}/inputs        → 200 DealResponse
    POST   /api/v1/deals/{id}/archive       → 200 DealResponse

All routes require authentication (get_current_user dependency).
Ownership is enforced by the service layer — NotFoundError propagates to 404
via the global error handler. DomainError (invalid state transitions such as
updating ARCHIVED deals) propagates to 422.

Architecture:
    SERVICE_ARCHITECTURE.md — "API layer calls services, not repositories."
    AUTHORIZATION_MODEL.md §9.2 — auth as FastAPI dependency.
    IMPLEMENTATION_ROADMAP.md Commit 6.3.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db, get_deal_service
from app.api.v1.schemas.deal import (
    DealResponse,
    DealSummaryResponse,
    DealWorkingInputsSchema,
    UpdateWorkingInputsRequest,
)
from app.domain.entities.deal import Deal
from app.domain.entities.user import User
from app.domain.enums import DealStatus
from app.repositories.interfaces.i_deal import DealSummary
from app.services.deal_service import DealInputUpdate, DealService

router = APIRouter(tags=["deals"])


# ---------------------------------------------------------------------------
# DTO mapping helpers
# ---------------------------------------------------------------------------

def _decimal_str(val: Decimal | None) -> str | None:
    return f"{val:.2f}" if val is not None else None


def _to_deal_response(deal: Deal) -> DealResponse:
    wi = deal.working_inputs
    return DealResponse(
        id=deal.id,
        user_id=deal.user_id,
        property_id=deal.property_id,
        label=deal.label,
        status=deal.status,
        investor_profile_id=deal.investor_profile_id,
        latest_snapshot_id=deal.latest_snapshot_id,
        working_inputs=DealWorkingInputsSchema(
            purchase_price=wi.purchase_price,
            monthly_rent=wi.monthly_rent,
            deposit_amount=wi.deposit_amount,
            mortgage_interest_rate=wi.mortgage_interest_rate,
            mortgage_term_years=wi.mortgage_term_years,
            mortgage_type=wi.mortgage_type,
            ownership_structure=wi.ownership_structure,
            income_tax_band=wi.income_tax_band,
            is_additional_dwelling=wi.is_additional_dwelling,
            void_rate_percent=wi.void_rate_percent,
            letting_agent_fee_percent=wi.letting_agent_fee_percent,
            maintenance_reserve_percent=wi.maintenance_reserve_percent,
            landlord_insurance_annual=wi.landlord_insurance_annual,
            purchase_legal_costs=wi.purchase_legal_costs,
            refurbishment_cost=wi.refurbishment_cost,
            annual_service_charge=wi.annual_service_charge,
            annual_ground_rent=wi.annual_ground_rent,
            annual_accountancy_cost=wi.annual_accountancy_cost,
        ),
        created_at=deal.created_at,
        updated_at=deal.updated_at,
    )


def _to_summary_response(summary: DealSummary) -> DealSummaryResponse:
    return DealSummaryResponse(
        id=summary.id,
        label=summary.label,
        status=summary.status,
        property_id=summary.property_id,
        latest_snapshot_id=summary.latest_snapshot_id,
        created_at=summary.created_at,
        updated_at=summary.updated_at,
        latest_snapshot_cash_flow_gbp=_decimal_str(
            summary.latest_snapshot_cash_flow_gbp
        ),
        latest_snapshot_gross_yield=_decimal_str(summary.latest_snapshot_gross_yield),
        latest_snapshot_calculated_at=summary.latest_snapshot_calculated_at,
        latest_snapshot_risk_flag_count_high=summary.latest_snapshot_risk_flag_count_high,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=DealResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create deal",
)
async def create_deal(
    property_id: uuid.UUID,
    label: str,
    investor_profile_id: uuid.UUID | None = None,
    current_user: User = Depends(get_current_user),
    svc: DealService = Depends(get_deal_service),
    db: AsyncSession = Depends(get_db),
) -> DealResponse:
    deal = await svc.create_deal(
        user_id=current_user.id,
        property_id=property_id,
        label=label,
        investor_profile_id=investor_profile_id,
    )
    await db.commit()
    return _to_deal_response(deal)


@router.get(
    "/",
    response_model=list[DealSummaryResponse],
    summary="List deals",
)
async def list_deals(
    status_filter: DealStatus | None = None,
    current_user: User = Depends(get_current_user),
    svc: DealService = Depends(get_deal_service),
) -> list[DealSummaryResponse]:
    page = await svc.list_deals(
        user_id=current_user.id,
        status_filter=status_filter,
    )
    return [_to_summary_response(s) for s in page.items]


@router.get(
    "/{deal_id}",
    response_model=DealResponse,
    summary="Get deal",
)
async def get_deal(
    deal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: DealService = Depends(get_deal_service),
) -> DealResponse:
    deal = await svc.get_deal(
        user_id=current_user.id,
        deal_id=deal_id,
    )
    return _to_deal_response(deal)


@router.patch(
    "/{deal_id}/inputs",
    response_model=DealResponse,
    summary="Update deal working inputs",
)
async def update_working_inputs(
    deal_id: uuid.UUID,
    body: UpdateWorkingInputsRequest,
    current_user: User = Depends(get_current_user),
    svc: DealService = Depends(get_deal_service),
    db: AsyncSession = Depends(get_db),
) -> DealResponse:
    updates = DealInputUpdate(
        purchase_price=body.purchase_price,
        monthly_rent=body.monthly_rent,
        deposit_amount=body.deposit_amount,
        mortgage_interest_rate=body.mortgage_interest_rate,
        mortgage_term_years=body.mortgage_term_years,
        mortgage_type=body.mortgage_type,
        ownership_structure=body.ownership_structure,
        income_tax_band=body.income_tax_band,
        is_additional_dwelling=body.is_additional_dwelling,
        void_rate_percent=body.void_rate_percent,
        letting_agent_fee_percent=body.letting_agent_fee_percent,
        maintenance_reserve_percent=body.maintenance_reserve_percent,
        landlord_insurance_annual=body.landlord_insurance_annual,
        purchase_legal_costs=body.purchase_legal_costs,
        refurbishment_cost=body.refurbishment_cost,
        annual_service_charge=body.annual_service_charge,
        annual_ground_rent=body.annual_ground_rent,
        annual_accountancy_cost=body.annual_accountancy_cost,
    )
    deal = await svc.update_working_inputs(
        user_id=current_user.id,
        deal_id=deal_id,
        input_updates=updates,
    )
    await db.commit()
    return _to_deal_response(deal)


@router.post(
    "/{deal_id}/archive",
    response_model=DealResponse,
    summary="Archive deal",
)
async def archive_deal(
    deal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: DealService = Depends(get_deal_service),
    db: AsyncSession = Depends(get_db),
) -> DealResponse:
    deal = await svc.archive_deal(
        user_id=current_user.id,
        deal_id=deal_id,
    )
    await db.commit()
    return _to_deal_response(deal)
