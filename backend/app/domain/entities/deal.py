"""
Deal domain entity.

The Deal is the primary domain concept in PropIQ. It represents an investor's
analysis of a property under a specific set of financial assumptions.

A deal is the mutable workspace: it holds the user's current working inputs
and points to the latest calculated snapshot. Working inputs change as the
investor refines their analysis. Each calculation creates a new immutable
snapshot; the deal records which snapshot is current.

Architecture: DOMAIN_MODEL_ARCHITECTURE.md Parts 3.2, 4.4, 9.1, 9.2, 9.3.
Mutation rules: DOMAIN_MODEL_ARCHITECTURE.md Part 16.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal

from app.domain.enums import (
    DealStatus,
    IncomeTaxBand,
    MortgageType,
    OwnershipStructure,
)
from app.domain.errors import DomainError


@dataclass
class DealWorkingInputs:
    """
    The user's current editable input state for a deal.

    All fields are nullable because a DRAFT deal may have incomplete inputs.
    Null means "not yet entered by the user" — the engine's validation
    pipeline enforces completeness at calculation time, not here.

    Optional inputs (void_rate_percent etc.) being None means "use the
    active configuration default." The InputDefaultResolutionService
    resolves these before passing to the engine.

    Monetary fields are Decimal | None (not Money) because working inputs
    are a scratchpad of partial user data, not typed financial values.
    The Money value object is appropriate for calculated/stored outputs.

    Architecture: DOMAIN_MODEL_ARCHITECTURE.md Part 9.2.
    Database: DATABASE_SCHEMA_DESIGN.md — deals table working input columns.
    """

    # Required inputs — no defaults; engine will fail validation if absent
    purchase_price: Decimal | None = None
    monthly_rent: Decimal | None = None
    deposit_amount: Decimal | None = None
    mortgage_interest_rate: Decimal | None = None
    mortgage_term_years: int | None = None
    mortgage_type: MortgageType | None = None
    ownership_structure: OwnershipStructure | None = None
    income_tax_band: IncomeTaxBand | None = None
    is_additional_dwelling: bool | None = None

    # Optional inputs — None means use the active assumption config default
    void_rate_percent: Decimal | None = None
    letting_agent_fee_percent: Decimal | None = None
    maintenance_reserve_percent: Decimal | None = None
    landlord_insurance_annual: Decimal | None = None
    purchase_legal_costs: Decimal | None = None
    refurbishment_cost: Decimal | None = None
    annual_service_charge: Decimal | None = None
    annual_ground_rent: Decimal | None = None
    annual_accountancy_cost: Decimal | None = None


@dataclass
class Deal:
    """
    Investment deal — the primary domain concept.

    Immutable after creation: id, user_id, property_id, created_at

    Mutable:
        label, status (via transition rules), working_inputs,
        latest_snapshot_id (updated on snapshot creation),
        investor_profile_id, updated_at

    Behaviour methods enforce state transitions directly on the entity.
    All other business rules (ownership verification, recalculation
    triggering) belong in the service layer.

    Phase 1 status vocabulary: DRAFT, ANALYSED, ARCHIVED.
    Phase 2 will add: OFFER_SUBMITTED, PURCHASED, HELD, EXITED.
    """

    # Identity
    id: uuid.UUID
    user_id: uuid.UUID        # immutable — ownership cannot be transferred
    property_id: uuid.UUID    # immutable — a deal belongs to one property

    # Workspace
    label: str
    status: DealStatus
    working_inputs: DealWorkingInputs = field(default_factory=DealWorkingInputs)

    # Snapshot pointer — None until the first calculation
    latest_snapshot_id: uuid.UUID | None = None

    # Convenience reference to the investor profile used at deal creation
    # Informational only — snapshots store copied values, not this FK
    investor_profile_id: uuid.UUID | None = None

    # Timestamps
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # ------------------------------------------------------------------
    # Behaviour methods
    # ------------------------------------------------------------------

    def apply_snapshot_created(self, snapshot_id: uuid.UUID) -> None:
        """
        Record that a new snapshot has been created for this deal.

        Updates latest_snapshot_id to the new snapshot.
        Transitions status from DRAFT → ANALYSED on the first calculation.
        ANALYSED → ANALYSED on subsequent recalculations (no status change).

        Called by CalculationService after a successful snapshot persist.

        Architecture: DOMAIN_MODEL_ARCHITECTURE.md Part 9.3.
        """
        self.latest_snapshot_id = snapshot_id
        if self.status == DealStatus.DRAFT:
            self.status = DealStatus.ANALYSED
        self.updated_at = datetime.now(UTC)

    def advance_status(self) -> None:
        """
        Advance this deal to the next pipeline stage.

        Valid transitions (user-initiated forward progression):
          ANALYSED        → OFFER_SUBMITTED
          OFFER_SUBMITTED → PURCHASED
          PURCHASED       → HELD
          HELD            → EXITED

        Raises DomainError if the current status has no forward transition
        (DRAFT, EXITED, ARCHIVED).

        Architecture: DOMAIN_MODEL_ARCHITECTURE.md Part 4.4, Part 19.1.
        IMPLEMENTATION_ROADMAP.md Phase 10 Feature 1.
        """
        _transitions = {
            DealStatus.ANALYSED:        DealStatus.OFFER_SUBMITTED,
            DealStatus.OFFER_SUBMITTED: DealStatus.PURCHASED,
            DealStatus.PURCHASED:       DealStatus.HELD,
            DealStatus.HELD:            DealStatus.EXITED,
        }
        next_status = _transitions.get(self.status)
        if next_status is None:
            raise DomainError(
                f"Cannot advance deal from status {self.status.value}. "
                f"Valid statuses to advance: ANALYSED, OFFER_SUBMITTED, PURCHASED, HELD."
            )
        self.status = next_status
        self.updated_at = datetime.now(UTC)

    def archive(self) -> None:
        """
        Transition this deal to ARCHIVED status.

        Valid from any non-ARCHIVED status. Raises DomainError if already ARCHIVED.
        Once archived, no further mutations are permitted (enforced by the
        service layer — the entity itself does not re-check on every field
        access, but DealService.update_working_inputs guards against it).

        Snapshots belonging to this deal are unaffected. They remain fully
        accessible via SnapshotService regardless of deal status.

        Architecture: DOMAIN_MODEL_ARCHITECTURE.md Part 4.4.
        """
        if self.status == DealStatus.ARCHIVED:
            raise DomainError("Deal is already archived")
        self.status = DealStatus.ARCHIVED
        self.updated_at = datetime.now(UTC)
