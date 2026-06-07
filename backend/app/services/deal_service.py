"""
DealService — deal lifecycle and working input management.

Responsibilities (APPLICATION_SERVICE_ARCHITECTURE.md Part 12):
  - create_deal: verify property ownership, pre-populate from profile, persist
  - update_working_inputs: ownership check, ARCHIVED guard, merge, persist
  - archive_deal: ownership check, domain transition, persist

Types defined here:
  DealInputUpdate — partial working input update (all fields nullable).
                    Distinct from DealWorkingInputs (which is the full state)
                    and RawCalculationInputs (which is a calculation request).

Status transitions:
  DRAFT → ANALYSED  — via Deal.apply_snapshot_created(); owned by CalculationService
  DRAFT/ANALYSED → ARCHIVED — via Deal.archive(); called by archive_deal()
  These use the domain entity behaviour directly. No DealStatusTransitionService.

Architecture:
    APPLICATION_SERVICE_ARCHITECTURE.md Part 12.
    DOMAIN_MODEL_ARCHITECTURE.md §6.5 (transition rules).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from app.domain.entities.deal import Deal, DealWorkingInputs
from app.domain.enums import (
    DealStatus,
    IncomeTaxBand,
    MortgageType,
    OwnershipStructure,
)
from app.domain.errors import DomainError, NotFoundError
from app.repositories.interfaces.i_deal import DealSummary, IDealRepository
from app.repositories.interfaces.i_investor_profile import IInvestorProfileRepository
from app.repositories.interfaces.i_property import IPropertyRepository
from app.repositories.pagination import Page, PageRequest

# ---------------------------------------------------------------------------
# DealInputUpdate — partial working input update
# APPLICATION_SERVICE_ARCHITECTURE.md Part 15.3
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DealInputUpdate:
    """
    Partial update to a deal's working inputs.

    Every field is nullable. None means "no change to this field" — only
    non-None values are merged into the existing DealWorkingInputs.

    Distinct from DealWorkingInputs (the full current state) and from
    RawCalculationInputs (a complete calculation request).

    Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 15.3.
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


def _merge_input_update(
    current: DealWorkingInputs,
    updates: DealInputUpdate,
) -> DealWorkingInputs:
    """
    Produce a new DealWorkingInputs with non-None fields from updates applied.

    None fields in updates leave the corresponding current value unchanged.
    """
    return DealWorkingInputs(
        purchase_price=updates.purchase_price
        if updates.purchase_price is not None
        else current.purchase_price,
        monthly_rent=updates.monthly_rent
        if updates.monthly_rent is not None
        else current.monthly_rent,
        deposit_amount=updates.deposit_amount
        if updates.deposit_amount is not None
        else current.deposit_amount,
        mortgage_interest_rate=updates.mortgage_interest_rate
        if updates.mortgage_interest_rate is not None
        else current.mortgage_interest_rate,
        mortgage_term_years=updates.mortgage_term_years
        if updates.mortgage_term_years is not None
        else current.mortgage_term_years,
        mortgage_type=updates.mortgage_type
        if updates.mortgage_type is not None
        else current.mortgage_type,
        ownership_structure=updates.ownership_structure
        if updates.ownership_structure is not None
        else current.ownership_structure,
        income_tax_band=updates.income_tax_band
        if updates.income_tax_band is not None
        else current.income_tax_band,
        is_additional_dwelling=updates.is_additional_dwelling
        if updates.is_additional_dwelling is not None
        else current.is_additional_dwelling,
        void_rate_percent=updates.void_rate_percent
        if updates.void_rate_percent is not None
        else current.void_rate_percent,
        letting_agent_fee_percent=updates.letting_agent_fee_percent
        if updates.letting_agent_fee_percent is not None
        else current.letting_agent_fee_percent,
        maintenance_reserve_percent=updates.maintenance_reserve_percent
        if updates.maintenance_reserve_percent is not None
        else current.maintenance_reserve_percent,
        landlord_insurance_annual=updates.landlord_insurance_annual
        if updates.landlord_insurance_annual is not None
        else current.landlord_insurance_annual,
        purchase_legal_costs=updates.purchase_legal_costs
        if updates.purchase_legal_costs is not None
        else current.purchase_legal_costs,
        refurbishment_cost=updates.refurbishment_cost
        if updates.refurbishment_cost is not None
        else current.refurbishment_cost,
        annual_service_charge=updates.annual_service_charge
        if updates.annual_service_charge is not None
        else current.annual_service_charge,
        annual_ground_rent=updates.annual_ground_rent
        if updates.annual_ground_rent is not None
        else current.annual_ground_rent,
        annual_accountancy_cost=updates.annual_accountancy_cost
        if updates.annual_accountancy_cost is not None
        else current.annual_accountancy_cost,
    )


# ---------------------------------------------------------------------------
# DealService
# ---------------------------------------------------------------------------

class DealService:
    """
    Manages deal lifecycle: creation, input updates, archival.

    Depends on IDealRepository, IPropertyRepository, and
    IInvestorProfileRepository (injected). Does not manage session lifecycle.

    Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 12.
    """

    def __init__(
        self,
        deal_repo: IDealRepository,
        property_repo: IPropertyRepository,
        profile_repo: IInvestorProfileRepository,
    ) -> None:
        self._deal_repo = deal_repo
        self._property_repo = property_repo
        self._profile_repo = profile_repo

    # ------------------------------------------------------------------
    # 12.1 — Create deal
    # APPLICATION_SERVICE_ARCHITECTURE.md Part 12.1
    # ------------------------------------------------------------------

    async def create_deal(
        self,
        user_id: uuid.UUID,
        property_id: uuid.UUID,
        label: str,
        investor_profile_id: uuid.UUID | None = None,
    ) -> Deal:
        """
        Create a new DRAFT deal linked to a user-owned property.

        Verifies property ownership. If investor_profile_id is given, loads
        that profile; otherwise falls back to the user's default profile.
        Pre-populates ownership_structure and income_tax_band from the profile
        if one is found. Saves the deal and returns it.

        Raises NotFoundError if property is not found or belongs to another user.
        Raises NotFoundError if investor_profile_id is given but not found or
        belongs to another user.

        Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 12.1.
        """
        # STEP 1 — Verify property ownership
        prop = await self._property_repo.find_by_id_for_user(property_id, user_id)
        if prop is None:
            raise NotFoundError(entity="property", id=property_id)

        # STEP 2 — Optionally load investor profile for pre-population
        profile = None
        if investor_profile_id is not None:
            profile = await self._profile_repo.find_by_id_for_user(
                investor_profile_id, user_id
            )
            if profile is None:
                raise NotFoundError(entity="investor_profile", id=investor_profile_id)
        else:
            profile = await self._profile_repo.find_default_for_user(user_id)

        # STEP 3 — Construct deal (pre-populate from profile if available)
        working_inputs = DealWorkingInputs()
        if profile is not None:
            working_inputs.ownership_structure = profile.ownership_structure
            working_inputs.income_tax_band = profile.income_tax_band

        deal = Deal(
            id=uuid.uuid4(),
            user_id=user_id,
            property_id=property_id,
            label=label,
            status=DealStatus.DRAFT,
            investor_profile_id=investor_profile_id,
            working_inputs=working_inputs,
        )

        # STEP 4 — Persist
        await self._deal_repo.save(deal)
        return deal

    # ------------------------------------------------------------------
    # 12.2 — Update working inputs
    # APPLICATION_SERVICE_ARCHITECTURE.md Part 12.2
    # ------------------------------------------------------------------

    async def update_working_inputs(
        self,
        user_id: uuid.UUID,
        deal_id: uuid.UUID,
        input_updates: DealInputUpdate,
    ) -> Deal:
        """
        Merge input_updates into a deal's working inputs and persist.

        Only non-None fields in input_updates are applied. Existing values for
        fields not included in input_updates are preserved unchanged.

        Raises NotFoundError if deal not found or belongs to another user.
        Raises DomainError if the deal is ARCHIVED.

        Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 12.2.
        """
        # STEP 1 — Load and verify ownership
        deal = await self._deal_repo.find_by_id_for_user(deal_id, user_id)
        if deal is None:
            raise NotFoundError(entity="deal", id=deal_id)

        # STEP 2 — Domain precondition check
        if deal.status == DealStatus.ARCHIVED:
            raise DomainError("Cannot update inputs on an archived deal")

        # STEP 3 — Merge updates
        deal.working_inputs = _merge_input_update(deal.working_inputs, input_updates)
        deal.updated_at = datetime.now(UTC)

        # STEP 4 — Persist
        await self._deal_repo.update(deal)
        return deal

    # ------------------------------------------------------------------
    # 12.3 — Archive deal
    # APPLICATION_SERVICE_ARCHITECTURE.md Part 12.3
    # ------------------------------------------------------------------

    async def archive_deal(
        self,
        user_id: uuid.UUID,
        deal_id: uuid.UUID,
    ) -> Deal:
        """
        Archive a deal, preventing further input updates or calculations.

        Uses Deal.archive() (the domain entity method) which raises DomainError
        if the deal is already ARCHIVED. Snapshots are unaffected.

        Raises NotFoundError if deal not found or belongs to another user.
        Raises DomainError if the deal is already ARCHIVED.

        Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 12.3.
        """
        # STEP 1 — Load and verify ownership
        deal = await self._deal_repo.find_by_id_for_user(deal_id, user_id)
        if deal is None:
            raise NotFoundError(entity="deal", id=deal_id)

        # STEP 2 — Apply domain transition (raises DomainError if already ARCHIVED)
        deal.archive()

        # STEP 3 — Persist
        await self._deal_repo.update(deal)
        return deal

    async def get_deal(
        self,
        user_id: uuid.UUID,
        deal_id: uuid.UUID,
    ) -> Deal:
        """
        Return a deal owned by the given user.

        Raises NotFoundError if the deal does not exist or belongs to a
        different user — both cases produce the same error per SI-13
        (non-disclosure of existence).

        Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 10.1, SI-13.
        SERVICE_ARCHITECTURE.md — API layer calls services, not repositories.
        """
        deal = await self._deal_repo.find_by_id_for_user(deal_id, user_id)
        if deal is None:
            raise NotFoundError(entity="deal", id=deal_id)
        return deal

    async def list_deals(
        self,
        user_id: uuid.UUID,
        status_filter: DealStatus | None = None,
        page: PageRequest | None = None,
    ) -> Page[DealSummary]:
        """
        Return a paginated list of deal summaries for the given user.

        status_filter=None returns all statuses. The query is already scoped
        to user_id — no additional ownership check is required.

        Returns DealSummary projections (not full Deal aggregates) including
        the latest snapshot key metrics for list view display.

        Architecture: SERVICE_ARCHITECTURE.md — API layer calls services.
        REPOSITORY_ARCHITECTURE.md Part 5.2 — DealSummary projection.
        """
        return await self._deal_repo.find_all_for_user(
            user_id,
            status_filter=status_filter,
            page=page or PageRequest(),
        )
