"""
Calculation routes — the core product endpoints.

Routes:
    POST /api/v1/calculations/                   → 201 CalculationSuccessResponse
    POST /api/v1/calculations/recalculate        → 201 CalculationSuccessResponse
    POST /api/v1/calculations/reproduce-original → 201 CalculationSuccessResponse

All routes require authentication (get_current_user dependency).

Route responsibilities:
  - Parse and validate the request DTO.
  - Call the appropriate CalculationService method.
  - Map CalculationSuccess → CalculationSuccessResponse.
  - Raise domain exceptions for error results (global handlers produce
    the correct HTTP status code).

The CalculationService returns a discriminated union. Error variants are
converted to domain exceptions so the global error handlers produce the
correct HTTP status codes:
    CalculationValidationFailure → raise domain CalculationValidationFailure → 422
    CalculationError             → raise domain CalculationError             → 500

Architecture:
    SERVICE_ARCHITECTURE.md — API layer calls services only.
    APPLICATION_SERVICE_ARCHITECTURE.md Part 5.
    IMPLEMENTATION_ROADMAP.md Commit 6.4.
"""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, status

from app.api.dependencies import get_calculation_service, get_current_user
from app.api.v1.schemas.calculation import (
    CalculationRequest,
    CalculationSuccessResponse,
    RecalculateRequest,
    ReproduceOriginalRequest,
)
from app.api.v1.schemas.snapshot import SnapshotSummaryResponse
from app.domain.entities.user import User
from app.domain.errors import (
    CalculationError as DomainCalculationError,
)
from app.domain.errors import (
    CalculationValidationFailure as DomainCalculationValidationFailure,
)
from app.services.calculation_service import (
    CalculationError as SvcCalculationError,
)
from app.services.calculation_service import (
    CalculationService,
    CalculationSuccess,
)
from app.services.calculation_service import (
    CalculationValidationFailure as SvcCalculationValidationFailure,
)

router = APIRouter(tags=["calculations"])


# ---------------------------------------------------------------------------
# Shared helper
# ---------------------------------------------------------------------------

def _to_response(result: CalculationSuccess) -> CalculationSuccessResponse:
    """Map a CalculationSuccess service result to the API response DTO."""
    return CalculationSuccessResponse(
        snapshot_id=result.snapshot_id,
        deal_status=result.deal_status_after,
        snapshot=SnapshotSummaryResponse.from_snapshot_summary(result.snapshot_summary),
    )


def _raise_if_error(result: object) -> CalculationSuccess:
    """
    Raise the appropriate domain exception for error result variants.

    Returns the CalculationSuccess if the result is a success.
    """
    if isinstance(result, SvcCalculationValidationFailure):
        raise DomainCalculationValidationFailure(
            hard_errors=result.hard_errors,
            warnings=result.warnings,
        )
    if isinstance(result, SvcCalculationError):
        raise DomainCalculationError(message=result.message)
    assert isinstance(result, CalculationSuccess)
    return result


# ---------------------------------------------------------------------------
# POST /api/v1/calculations/
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=CalculationSuccessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Run calculation",
)
async def run_calculation(
    body: CalculationRequest,
    current_user: User = Depends(get_current_user),
    svc: CalculationService = Depends(get_calculation_service),
) -> CalculationSuccessResponse:
    """
    Run the full underwriting calculation for a deal using the supplied inputs.

    Inputs are merged against active configuration defaults for any optional
    field that is absent. The result is persisted as an immutable snapshot.
    The deal transitions from DRAFT → ANALYSED on the first successful
    calculation.
    """
    from app.services.configuration_service import RawCalculationInputs

    raw_inputs = RawCalculationInputs(
        purchase_price=body.purchase_price,
        monthly_rent=body.monthly_rent,
        deposit_amount=body.deposit_amount,
        mortgage_interest_rate=body.mortgage_interest_rate,
        mortgage_term_years=body.mortgage_term_years,
        mortgage_type=body.mortgage_type,
        ownership_structure=body.ownership_structure,
        income_tax_band=body.income_tax_band,
        is_additional_dwelling=body.is_additional_dwelling,
        property_type=body.property_type,
        tenure=body.tenure,
        property_country=body.property_country,
        postcode=body.postcode,
        lease_years_remaining=body.lease_years_remaining,
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

    result = await svc.run_calculation(
        user_id=current_user.id,
        deal_id=body.deal_id,
        raw_inputs=raw_inputs,
        calculation_date=body.calculation_date or date.today(),
        client_context=None,
    )

    return _to_response(_raise_if_error(result))


# ---------------------------------------------------------------------------
# POST /api/v1/calculations/recalculate
# ---------------------------------------------------------------------------

@router.post(
    "/recalculate",
    response_model=CalculationSuccessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Recalculate with current assumptions",
)
async def recalculate(
    body: RecalculateRequest,
    current_user: User = Depends(get_current_user),
    svc: CalculationService = Depends(get_calculation_service),
) -> CalculationSuccessResponse:
    """
    Recalculate a deal using its current stored working inputs and the latest
    active configuration assumptions.

    The previous snapshot is marked superseded. The deal's latest_snapshot_id
    is updated to the new snapshot.
    """
    result = await svc.recalculate_with_current_assumptions(
        user_id=current_user.id,
        deal_id=body.deal_id,
        calculation_date=body.calculation_date or date.today(),
        client_context=None,
    )

    return _to_response(_raise_if_error(result))


# ---------------------------------------------------------------------------
# POST /api/v1/calculations/reproduce-original
# ---------------------------------------------------------------------------

@router.post(
    "/reproduce-original",
    response_model=CalculationSuccessResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Reproduce original calculation",
)
async def reproduce_original(
    body: ReproduceOriginalRequest,
    current_user: User = Depends(get_current_user),
    svc: CalculationService = Depends(get_calculation_service),
) -> CalculationSuccessResponse:
    """
    Re-run the engine with the exact inputs and configuration of a historical
    snapshot for reproducibility verification.

    The deal's latest_snapshot_id is NOT updated — the reproduction snapshot is
    saved for audit purposes only (Variant B).
    """
    result = await svc.reproduce_original(
        user_id=current_user.id,
        source_snapshot_id=body.source_snapshot_id,
        calculation_date=body.calculation_date or date.today(),
        client_context=None,
    )

    return _to_response(_raise_if_error(result))
