"""
Property CRUD routes.

Routes:
    POST   /api/v1/properties/              → 201 PropertyResponse
    GET    /api/v1/properties/              → 200 list of PropertyResponse
    GET    /api/v1/properties/{id}/         → 200 PropertyResponse
    PATCH  /api/v1/properties/{id}/         → 200 PropertyResponse
    DELETE /api/v1/properties/{id}/archive  → 200 PropertyResponse

All routes require authentication (get_current_user dependency).
Ownership is enforced by the service layer — NotFoundError propagates to 404
via the global error handler registered in app/main.py.

Architecture:
    SERVICE_ARCHITECTURE.md — "API layer calls services, not repositories."
    AUTHORIZATION_MODEL.md §9.2 — auth as FastAPI dependency.
    IMPLEMENTATION_ROADMAP.md Commit 6.3.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user, get_db, get_property_service
from app.api.v1.schemas.property import CreatePropertyRequest, PropertyResponse
from app.domain.entities.property import Property
from app.domain.entities.user import User
from app.domain.value_objects.address import PropertyAddress
from app.services.property_service import PropertyService

router = APIRouter(tags=["properties"])


# ---------------------------------------------------------------------------
# DTO mapping helper
# ---------------------------------------------------------------------------

def _to_response(prop: Property) -> PropertyResponse:
    """Map a Property domain entity to PropertyResponse, flattening address."""
    return PropertyResponse(
        id=prop.id,
        user_id=prop.user_id,
        address_line_1=prop.address.address_line_1,
        address_line_2=prop.address.address_line_2,
        city=prop.address.city,
        postcode=prop.address.postcode,
        property_type=prop.property_type,
        tenure=prop.tenure,
        lease_years_remaining=prop.lease_years_remaining,
        bedrooms=prop.bedrooms,
        epc_rating=prop.epc_rating,
        is_archived=prop.is_archived,
        archived_at=prop.archived_at,
        created_at=prop.created_at,
        updated_at=prop.updated_at,
    )


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.post(
    "/",
    response_model=PropertyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create property",
)
async def create_property(
    body: CreatePropertyRequest,
    current_user: User = Depends(get_current_user),
    svc: PropertyService = Depends(get_property_service),
    db: AsyncSession = Depends(get_db),
) -> PropertyResponse:
    address = PropertyAddress(
        address_line_1=body.address_line_1,
        address_line_2=body.address_line_2,
        city=body.city,
        postcode=body.postcode,
    )
    prop = await svc.create_property(
        user_id=current_user.id,
        address=address,
        property_type=body.property_type,
        tenure=body.tenure,
        lease_years_remaining=body.lease_years_remaining,
        bedrooms=body.bedrooms,
        epc_rating=body.epc_rating,
    )
    await db.commit()
    return _to_response(prop)


@router.get(
    "/",
    response_model=list[PropertyResponse],
    summary="List properties",
)
async def list_properties(
    include_archived: bool = False,
    current_user: User = Depends(get_current_user),
    svc: PropertyService = Depends(get_property_service),
) -> list[PropertyResponse]:
    page = await svc.list_properties(
        user_id=current_user.id,
        include_archived=include_archived,
    )
    return [_to_response(p) for p in page.items]


@router.get(
    "/{property_id}",
    response_model=PropertyResponse,
    summary="Get property",
)
async def get_property(
    property_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: PropertyService = Depends(get_property_service),
) -> PropertyResponse:
    prop = await svc.get_property_for_user(
        property_id=property_id,
        user_id=current_user.id,
    )
    return _to_response(prop)


@router.patch(
    "/{property_id}",
    response_model=PropertyResponse,
    summary="Update property",
)
async def update_property(
    property_id: uuid.UUID,
    body: CreatePropertyRequest,
    current_user: User = Depends(get_current_user),
    svc: PropertyService = Depends(get_property_service),
    db: AsyncSession = Depends(get_db),
) -> PropertyResponse:
    address = PropertyAddress(
        address_line_1=body.address_line_1,
        address_line_2=body.address_line_2,
        city=body.city,
        postcode=body.postcode,
    )
    prop = await svc.update_property(
        user_id=current_user.id,
        property_id=property_id,
        address=address,
        property_type=body.property_type,
        bedrooms=body.bedrooms,
        epc_rating=body.epc_rating,
    )
    await db.commit()
    return _to_response(prop)


@router.delete(
    "/{property_id}/archive",
    response_model=PropertyResponse,
    summary="Archive property",
)
async def archive_property(
    property_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    svc: PropertyService = Depends(get_property_service),
    db: AsyncSession = Depends(get_db),
) -> PropertyResponse:
    prop = await svc.archive_property(
        user_id=current_user.id,
        property_id=property_id,
    )
    await db.commit()
    return _to_response(prop)
