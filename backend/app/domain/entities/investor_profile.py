"""
InvestorProfile domain entity.

A named set of investor-level tax and ownership preferences. A user may have
multiple profiles — for example, one for personal ownership and one for a
limited company. Profiles are reusable across deals.

Profiles are a deal-creation convenience. Values are copied into snapshot
inputs at calculation time. The snapshot never references the profile by FK.
A profile change or archival does not affect historical snapshots.

Architecture: DOMAIN_MODEL_ARCHITECTURE.md Part 11.2.
Mutation rules: DOMAIN_MODEL_ARCHITECTURE.md Part 16.
Lifecycle:      DOMAIN_MODEL_ARCHITECTURE.md Part 4.2.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.domain.enums import IncomeTaxBand, OwnershipStructure


@dataclass
class InvestorProfile:
    """
    Named investor tax and ownership profile.

    Immutable after creation: id, user_id, created_at
    Mutable: label, ownership_structure, income_tax_band, is_default,
             is_archived, archived_at, updated_at

    Domain constraint (I-06): income_tax_band must be present for
    INDIVIDUAL and absent (None) for LIMITED_COMPANY. This constraint
    is enforced at the service layer and database level; the entity
    stores whatever the caller provides.

    At most one profile per user may have is_default = True. Enforced
    at the service layer — not a field-level invariant on the entity.
    """

    # Identity
    id: uuid.UUID
    user_id: uuid.UUID  # immutable

    # Profile
    label: str
    ownership_structure: OwnershipStructure
    income_tax_band: IncomeTaxBand | None  # required for INDIVIDUAL; None for LTD_CO

    # Flags
    is_default: bool = False
    is_archived: bool = False

    # Timestamps
    archived_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
