"""
User domain entity.

Represents a PropIQ platform account. Extends the Supabase Auth identity —
the platform record is created on first authenticated login and linked by
supabase_auth_id.

Authentication is fully delegated to Supabase Auth. This entity holds the
platform-level information needed for ownership verification, audit
attribution, and future GDPR anonymisation.

Architecture: DOMAIN_MODEL_ARCHITECTURE.md Part 11.1.
Mutation rules: DOMAIN_MODEL_ARCHITECTURE.md Part 16.
Lifecycle:      DOMAIN_MODEL_ARCHITECTURE.md Part 4.1.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from app.domain.enums import UserStatus


@dataclass
class User:
    """
    Platform user account.

    Immutable after creation: id, supabase_auth_id, created_at
    Mutable: email, display_name, status, updated_at

    The User entity does not own deals, properties, or snapshots.
    Those entities reference user_id but are not held inside this aggregate.

    Phase 1 status transitions:
        ACTIVE ↔ SUSPENDED  (admin action)
        → ARCHIVED requires the Phase 2 GDPR anonymisation process.
    """

    # Identity
    id: uuid.UUID
    supabase_auth_id: uuid.UUID  # join key to Supabase Auth — immutable

    # Profile
    email: str                   # synced from auth; not authoritative here
    display_name: str | None

    # Status
    status: UserStatus

    # Timestamps — set by the persistence layer; None until persisted
    created_at: datetime | None = None
    updated_at: datetime | None = None
