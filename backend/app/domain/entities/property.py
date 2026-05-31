"""
Property domain entity.

Represents a specific real-world property that is the subject of a deal
analysis. Holds stable identifying and descriptive attributes of the
physical asset, separate from any financial analysis.

Multiple deals may be created against the same property — for example, to
compare a 25% deposit scenario against a 40% deposit scenario, or to model
personal versus limited company ownership.

Architecture: DOMAIN_MODEL_ARCHITECTURE.md Part 3.3.
Mutation rules: DOMAIN_MODEL_ARCHITECTURE.md Part 16.
Lifecycle:      DOMAIN_MODEL_ARCHITECTURE.md Part 4.3.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.domain.enums import PropertyType, Tenure
from app.domain.value_objects.address import PropertyAddress


@dataclass
class Property:
    """
    Real-world investment property.

    Immutable after creation: id, user_id, tenure, created_at

    Tenure is immutable because it determines calculation pathways recorded
    in historical snapshots. If entered incorrectly, the property should be
    archived and a replacement created.

    Mutable: address, property_type, bedrooms, epc_rating,
             is_archived, archived_at, updated_at

    address is a PropertyAddress value object. The repository layer maps
    between the flat database columns and this value object.
    """

    # Identity
    id: uuid.UUID
    user_id: uuid.UUID  # immutable — ownership cannot be transferred

    # Location
    address: PropertyAddress

    # Classification
    property_type: PropertyType
    tenure: Tenure              # immutable after creation

    # Detail (optional)
    bedrooms: int | None = None
    epc_rating: str | None = None    # A–G; sourced from user or EPC register

    # Soft deletion
    is_archived: bool = False
    archived_at: datetime | None = None

    # Timestamps
    created_at: datetime | None = None
    updated_at: datetime | None = None
