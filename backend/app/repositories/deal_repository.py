"""
DealRepository — SQLAlchemy implementation of IDealRepository.

Architecture:
    REPOSITORY_ARCHITECTURE.md Part 2.2, 5.2.
    DATABASE_SCHEMA_DESIGN.md Section 2 — deals table.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Row, func, outerjoin, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.deal import Deal as DealORM
from app.db.models.snapshot import (
    SnapshotCalculation,
    SnapshotOutputs,
    SnapshotRiskFlag,
)
from app.domain.entities.deal import Deal, DealWorkingInputs
from app.domain.enums import (
    DealStatus,
    FlagSeverity,
    IncomeTaxBand,
    MortgageType,
    OwnershipStructure,
)
from app.repositories.interfaces.i_deal import DealSummary
from app.repositories.pagination import Page, PageRequest


class DealRepository:
    """
    SQLAlchemy implementation of IDealRepository.

    Receives AsyncSession as a constructor dependency.
    Does not commit — the caller manages session lifecycle.

    Architecture: REPOSITORY_ARCHITECTURE.md Part 13.1–13.3.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save(self, deal: Deal) -> None:
        """Insert a new deal record."""
        wi = deal.working_inputs
        row = DealORM(
            id=deal.id,
            user_id=deal.user_id,
            property_id=deal.property_id,
            investor_profile_id=deal.investor_profile_id,
            label=deal.label,
            status=deal.status,
            latest_snapshot_id=deal.latest_snapshot_id,
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
        )
        self._session.add(row)

    async def update(self, deal: Deal) -> None:
        """
        Persist mutations to an existing deal.

        Updates: label, status, working_inputs columns, latest_snapshot_id,
                 investor_profile_id, updated_at.
        Never updates: user_id, property_id, created_at (RI-05).
        """
        wi = deal.working_inputs
        stmt = (
            update(DealORM)
            .where(DealORM.id == deal.id)
            .values(
                label=deal.label,
                status=deal.status,
                latest_snapshot_id=deal.latest_snapshot_id,
                investor_profile_id=deal.investor_profile_id,
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
                updated_at=datetime.now(UTC),
            )
        )
        await self._session.execute(stmt)

    async def find_by_id(self, deal_id: uuid.UUID) -> Deal | None:
        """Return the deal with this id (any user), or None if not found."""
        stmt = select(DealORM).where(DealORM.id == deal_id)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row is not None else None

    async def find_by_id_for_user(
        self, deal_id: uuid.UUID, user_id: uuid.UUID
    ) -> Deal | None:
        """
        Ownership-aware load.
        Returns None if not found OR if the deal belongs to a different user.
        Never distinguishes between the two cases (RI-06).
        """
        stmt = select(DealORM).where(
            DealORM.id == deal_id,
            DealORM.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._to_domain(row) if row is not None else None

    async def find_all_for_user(
        self,
        user_id: uuid.UUID,
        status_filter: DealStatus | None,
        page: PageRequest,
    ) -> Page[DealSummary]:
        """
        Paginated list of DealSummary projections for a user, newest-updated first.

        Joins snapshot_outputs and snapshot_calculations for the latest snapshot
        key metrics. High-severity risk flag count subqueried per deal.
        status_filter=None returns all statuses.
        Cursor-based pagination on (updated_at DESC, id DESC).

        Architecture: REPOSITORY_ARCHITECTURE.md Part 5.2, 15.2.
        """
        # --- HIGH flag count subquery (LEFT JOIN friendly) ---
        high_flag_sq = (
            select(
                SnapshotRiskFlag.snapshot_id,
                func.count(SnapshotRiskFlag.id).label("high_count"),
            )
            .where(SnapshotRiskFlag.severity == FlagSeverity.HIGH)
            .group_by(SnapshotRiskFlag.snapshot_id)
            .subquery()
        )

        # --- base join expression ---
        # deals LEFT JOIN snapshot_outputs ON deals.latest_snapshot_id
        # deals LEFT JOIN snapshot_calculations ON deals.latest_snapshot_id
        # deals LEFT JOIN high_flag_sq ON deals.latest_snapshot_id
        join_expr = (
            outerjoin(
                DealORM,
                SnapshotOutputs,
                DealORM.latest_snapshot_id == SnapshotOutputs.snapshot_id,
            )
            .outerjoin(
                SnapshotCalculation,
                DealORM.latest_snapshot_id == SnapshotCalculation.id,
            )
            .outerjoin(
                high_flag_sq,
                DealORM.latest_snapshot_id == high_flag_sq.c.snapshot_id,
            )
        )

        # --- shared WHERE conditions ---
        where_clauses = [DealORM.user_id == user_id]
        if status_filter is not None:
            where_clauses.append(DealORM.status == status_filter)

        # --- count query ---
        count_stmt = (
            select(func.count())
            .select_from(DealORM)
            .where(*where_clauses)
        )
        count_result = await self._session.execute(count_stmt)
        total_count = count_result.scalar_one()

        # --- list query ---
        cols = [
            DealORM.id,
            DealORM.label,
            DealORM.status,
            DealORM.property_id,
            DealORM.latest_snapshot_id,
            DealORM.created_at,
            DealORM.updated_at,
            SnapshotOutputs.annual_cash_flow_gbp,
            SnapshotOutputs.gross_yield_percent,
            SnapshotCalculation.calculated_at,
            high_flag_sq.c.high_count,
        ]
        stmt = select(*cols).select_from(join_expr).where(*where_clauses)

        cursor = page.decode_cursor()
        if cursor is not None:
            cursor_ts, cursor_id = cursor
            stmt = stmt.where(
                (DealORM.updated_at < cursor_ts)
                | (
                    (DealORM.updated_at == cursor_ts)
                    & (DealORM.id < cursor_id)
                )
            )

        stmt = stmt.order_by(
            DealORM.updated_at.desc(),
            DealORM.id.desc(),
        ).limit(page.limit + 1)

        result = await self._session.execute(stmt)
        rows = result.all()

        has_next = len(rows) > page.limit
        if has_next:
            rows = rows[: page.limit]

        items = [self._row_to_summary(r) for r in rows]

        next_cursor: str | None = None
        if has_next and rows:
            last = rows[-1]
            next_cursor = Page.encode_cursor(last.updated_at, last.id)

        return Page(items=items, next_cursor=next_cursor, total_count=total_count)

    async def find_all_for_property(
        self, property_id: uuid.UUID, user_id: uuid.UUID
    ) -> list[DealSummary]:
        """
        All deals for a property, ownership-filtered, newest-updated first.
        Not paginated — expected < 50 deals per property (RI-09).
        """
        high_flag_sq = (
            select(
                SnapshotRiskFlag.snapshot_id,
                func.count(SnapshotRiskFlag.id).label("high_count"),
            )
            .where(SnapshotRiskFlag.severity == FlagSeverity.HIGH)
            .group_by(SnapshotRiskFlag.snapshot_id)
            .subquery()
        )

        join_expr = (
            outerjoin(
                DealORM,
                SnapshotOutputs,
                DealORM.latest_snapshot_id == SnapshotOutputs.snapshot_id,
            )
            .outerjoin(
                SnapshotCalculation,
                DealORM.latest_snapshot_id == SnapshotCalculation.id,
            )
            .outerjoin(
                high_flag_sq,
                DealORM.latest_snapshot_id == high_flag_sq.c.snapshot_id,
            )
        )

        cols = [
            DealORM.id,
            DealORM.label,
            DealORM.status,
            DealORM.property_id,
            DealORM.latest_snapshot_id,
            DealORM.created_at,
            DealORM.updated_at,
            SnapshotOutputs.annual_cash_flow_gbp,
            SnapshotOutputs.gross_yield_percent,
            SnapshotCalculation.calculated_at,
            high_flag_sq.c.high_count,
        ]

        stmt = (
            select(*cols)
            .select_from(join_expr)
            .where(
                DealORM.property_id == property_id,
                DealORM.user_id == user_id,
            )
            .order_by(DealORM.updated_at.desc())
        )

        result = await self._session.execute(stmt)
        return [self._row_to_summary(r) for r in result.all()]

    async def count_for_user(self, user_id: uuid.UUID) -> int:
        """Count of non-ARCHIVED deals for a user."""
        stmt = (
            select(func.count())
            .select_from(DealORM)
            .where(
                DealORM.user_id == user_id,
                DealORM.status != DealStatus.ARCHIVED,
            )
        )
        result = await self._session.execute(stmt)
        return result.scalar_one()

    # ------------------------------------------------------------------
    # Private mapping helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_summary(row: Row) -> DealSummary:  # type: ignore[type-arg]
        """Map a joined query row to a DealSummary projection."""
        return DealSummary(
            id=row.id,
            label=row.label,
            status=row.status
            if isinstance(row.status, DealStatus)
            else DealStatus(row.status),
            property_id=row.property_id,
            latest_snapshot_id=row.latest_snapshot_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            latest_snapshot_cash_flow_gbp=Decimal(str(row.annual_cash_flow_gbp))
            if row.annual_cash_flow_gbp is not None
            else None,
            latest_snapshot_gross_yield=Decimal(str(row.gross_yield_percent))
            if row.gross_yield_percent is not None
            else None,
            latest_snapshot_calculated_at=row.calculated_at,
            latest_snapshot_risk_flag_count_high=int(row.high_count)
            if row.high_count is not None
            else None,
        )

    def _to_domain(self, row: DealORM) -> Deal:
        """Convert DealORM row → Deal domain entity."""
        status = (
            row.status
            if isinstance(row.status, DealStatus)
            else DealStatus(row.status)
        )
        mortgage_type: MortgageType | None = None
        if row.mortgage_type is not None:
            mortgage_type = (
                row.mortgage_type
                if isinstance(row.mortgage_type, MortgageType)
                else MortgageType(row.mortgage_type)
            )
        ownership_structure: OwnershipStructure | None = None
        if row.ownership_structure is not None:
            ownership_structure = (
                row.ownership_structure
                if isinstance(row.ownership_structure, OwnershipStructure)
                else OwnershipStructure(row.ownership_structure)
            )
        income_tax_band: IncomeTaxBand | None = None
        if row.income_tax_band is not None:
            income_tax_band = (
                row.income_tax_band
                if isinstance(row.income_tax_band, IncomeTaxBand)
                else IncomeTaxBand(row.income_tax_band)
            )

        working_inputs = DealWorkingInputs(
            purchase_price=Decimal(str(row.purchase_price))
            if row.purchase_price is not None
            else None,
            monthly_rent=Decimal(str(row.monthly_rent))
            if row.monthly_rent is not None
            else None,
            deposit_amount=Decimal(str(row.deposit_amount))
            if row.deposit_amount is not None
            else None,
            mortgage_interest_rate=Decimal(str(row.mortgage_interest_rate))
            if row.mortgage_interest_rate is not None
            else None,
            mortgage_term_years=row.mortgage_term_years,
            mortgage_type=mortgage_type,
            ownership_structure=ownership_structure,
            income_tax_band=income_tax_band,
            is_additional_dwelling=row.is_additional_dwelling,
            void_rate_percent=Decimal(str(row.void_rate_percent))
            if row.void_rate_percent is not None
            else None,
            letting_agent_fee_percent=Decimal(str(row.letting_agent_fee_percent))
            if row.letting_agent_fee_percent is not None
            else None,
            maintenance_reserve_percent=Decimal(str(row.maintenance_reserve_percent))
            if row.maintenance_reserve_percent is not None
            else None,
            landlord_insurance_annual=Decimal(str(row.landlord_insurance_annual))
            if row.landlord_insurance_annual is not None
            else None,
            purchase_legal_costs=Decimal(str(row.purchase_legal_costs))
            if row.purchase_legal_costs is not None
            else None,
            refurbishment_cost=Decimal(str(row.refurbishment_cost))
            if row.refurbishment_cost is not None
            else None,
            annual_service_charge=Decimal(str(row.annual_service_charge))
            if row.annual_service_charge is not None
            else None,
            annual_ground_rent=Decimal(str(row.annual_ground_rent))
            if row.annual_ground_rent is not None
            else None,
            annual_accountancy_cost=Decimal(str(row.annual_accountancy_cost))
            if row.annual_accountancy_cost is not None
            else None,
        )

        return Deal(
            id=row.id,
            user_id=row.user_id,
            property_id=row.property_id,
            investor_profile_id=row.investor_profile_id,
            label=row.label,
            status=status,
            working_inputs=working_inputs,
            latest_snapshot_id=row.latest_snapshot_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )
