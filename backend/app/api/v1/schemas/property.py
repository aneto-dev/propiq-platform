"""
Property request/response Pydantic v2 schemas.

Architecture:
    APPLICATION_SERVICE_ARCHITECTURE.md Part 15.
    IMPLEMENTATION_ROADMAP.md Commit 6.2.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel

from app.domain.enums import PropertyType, Tenure


class CreatePropertyRequest(BaseModel):
    """Request body for POST /api/v1/properties/."""

    address_line_1: str
    address_line_2: str | None = None
    city: str
    postcode: str
    property_type: PropertyType
    tenure: Tenure
    lease_years_remaining: int | None = None
    bedrooms: int | None = None
    epc_rating: str | None = None


class PropertyResponse(BaseModel):
    """Response for a single property."""

    id: uuid.UUID
    user_id: uuid.UUID
    address_line_1: str
    address_line_2: str | None
    city: str
    postcode: str
    property_type: PropertyType
    tenure: Tenure
    lease_years_remaining: int | None
    bedrooms: int | None
    epc_rating: str | None
    is_archived: bool
    archived_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}
