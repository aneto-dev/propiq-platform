"""
SnapshotRepository — SQLAlchemy implementation of ISnapshotRepository.

The most critical repository: save() atomically writes 7 records across
6 tables plus a deal pointer update. All writes either commit together
or roll back together (RI-01, RI-02).

Loading levels (REPOSITORY_ARCHITECTURE.md Part 6):
    find_by_id              → FULL (6 queries — root + all sub-tables)
    find_by_id_outputs_only → DISPLAY (3 queries — root + outputs + flags/warnings)
    find_history_for_deal   → SUMMARY (1 aggregating query — key metrics + counts)

Architecture:
    REPOSITORY_ARCHITECTURE.md Part 2.1, 5.1, 7.1–7.3, 10.2.
    DATABASE_SCHEMA_DESIGN.md Sections 3 and 5.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.deal import Deal as DealORM
from app.db.models.snapshot import (
    SnapshotCalculation,
    SnapshotInputs,
    SnapshotIntermediates,
    SnapshotOutputs,
    SnapshotRiskFlag,
    SnapshotValidationWarning,
)
from app.domain.entities.snapshot import (
    CalculationSnapshot,
    ConfigVersionRefs,
    RiskFlag,
    SDLTBandResult,
    ValidationWarning,
)
from app.domain.entities.snapshot import (
    SnapshotInputs as DomainSnapshotInputs,
)
from app.domain.entities.snapshot import (
    SnapshotIntermediates as DomainSnapshotIntermediates,
)
from app.domain.entities.snapshot import (
    SnapshotOutputs as DomainSnapshotOutputs,
)
from app.domain.enums import (
    FlagSeverity,
    IncomeTaxBand,
    InputSource,
    MortgageType,
    OwnershipStructure,
    PropertyCountry,
    PropertyType,
    Tenure,
)
from app.domain.value_objects.money import Money
from app.domain.value_objects.rate import Rate
from app.repositories.interfaces.i_snapshot import SnapshotHistoryEntry, SnapshotSummary


class SnapshotRepository:
    """
    SQLAlchemy implementation of ISnapshotRepository.

    Receives AsyncSession as a constructor dependency.
    Does not commit — the caller manages session lifecycle (RI-07, RI-08).

    save() adds all rows to the session in sequence; atomicity is guaranteed
    by the caller's commit — a failure at any point prevents the commit and
    leaves the database unchanged.

    Architecture: REPOSITORY_ARCHITECTURE.md Part 13.1–13.3.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    async def save(self, snapshot: CalculationSnapshot) -> None:
        """
        Atomically persist the complete snapshot aggregate.

        Adds to the session (all flushed together at commit):
          1. snapshot_calculations (root)
          2. snapshot_inputs
          3. snapshot_outputs
          4. snapshot_intermediates
          5. snapshot_risk_flags (one row per flag)
          6. snapshot_validation_warnings (one row per warning)
          7. UPDATE deals.latest_snapshot_id

        The caller's session.commit() makes all writes durable or rolls all
        back on failure (RI-01, RI-02).

        Architecture: REPOSITORY_ARCHITECTURE.md Part 10.2.
        """
        refs = snapshot.config_version_refs

        # 1. Root record
        root = SnapshotCalculation(
            id=snapshot.id,
            deal_id=snapshot.deal_id,
            user_id=snapshot.user_id,
            engine_version=snapshot.engine_version,
            assumption_config_version_id=refs.assumption_config_version_id,
            sdlt_config_version_id=refs.sdlt_config_version_id,
            corporation_tax_config_version_id=refs.corporation_tax_config_version_id,
            calculated_at=snapshot.calculated_at,
            is_superseded=snapshot.is_superseded,
            superseded_at=snapshot.superseded_at,
            calculation_duration_ms=snapshot.calculation_duration_ms,
        )
        self._session.add(root)

        # 2. Inputs
        self._session.add(self._build_inputs_row(snapshot.id, snapshot.inputs))

        # 3. Outputs
        self._session.add(self._build_outputs_row(snapshot.id, snapshot.outputs))

        # 4. Intermediates
        self._session.add(
            self._build_intermediates_row(snapshot.id, snapshot.intermediates)
        )

        # 5. Risk flags (one row per flag)
        for flag in snapshot.risk_flags:
            self._session.add(
                SnapshotRiskFlag(
                    snapshot_id=snapshot.id,
                    flag_code=flag.code,
                    severity=flag.severity,
                    triggered_by_field=flag.triggered_by_field,
                    triggered_by_value=flag.triggered_by_value,
                    message=flag.message,
                )
            )

        # 6. Validation warnings (one row per warning)
        for warning in snapshot.validation_warnings:
            self._session.add(
                SnapshotValidationWarning(
                    snapshot_id=snapshot.id,
                    rule_code=warning.rule_code,
                    field=warning.field,
                    message=warning.message,
                )
            )

        # 7. Update deals.latest_snapshot_id pointer
        await self._session.execute(
            update(DealORM)
            .where(DealORM.id == snapshot.deal_id)
            .values(latest_snapshot_id=snapshot.id)
        )

    async def save_without_deal_pointer_update(
        self, snapshot: CalculationSnapshot
    ) -> None:
        """
        Persist snapshot sub-tables (1–6) without updating deals.latest_snapshot_id.

        Used for reproduction snapshots — the original snapshot remains the
        "current" analysis and the deal pointer is not moved.

        Architecture: APPLICATION_SERVICE_ARCHITECTURE.md §5.4.
        """
        refs = snapshot.config_version_refs

        self._session.add(
            SnapshotCalculation(
                id=snapshot.id,
                deal_id=snapshot.deal_id,
                user_id=snapshot.user_id,
                engine_version=snapshot.engine_version,
                assumption_config_version_id=refs.assumption_config_version_id,
                sdlt_config_version_id=refs.sdlt_config_version_id,
                corporation_tax_config_version_id=refs.corporation_tax_config_version_id,
                calculated_at=snapshot.calculated_at,
                is_superseded=snapshot.is_superseded,
                superseded_at=snapshot.superseded_at,
                calculation_duration_ms=snapshot.calculation_duration_ms,
            )
        )
        self._session.add(self._build_inputs_row(snapshot.id, snapshot.inputs))
        self._session.add(self._build_outputs_row(snapshot.id, snapshot.outputs))
        self._session.add(
            self._build_intermediates_row(snapshot.id, snapshot.intermediates)
        )
        for flag in snapshot.risk_flags:
            self._session.add(
                SnapshotRiskFlag(
                    snapshot_id=snapshot.id,
                    flag_code=flag.code,
                    severity=flag.severity,
                    triggered_by_field=flag.triggered_by_field,
                    triggered_by_value=flag.triggered_by_value,
                    message=flag.message,
                )
            )
        for warning in snapshot.validation_warnings:
            self._session.add(
                SnapshotValidationWarning(
                    snapshot_id=snapshot.id,
                    rule_code=warning.rule_code,
                    field=warning.field,
                    message=warning.message,
                )
            )

    async def mark_superseded(
        self, snapshot_id: uuid.UUID, superseded_at: datetime
    ) -> None:
        """
        Set is_superseded=True and superseded_at on the specified snapshot.

        The only permitted UPDATE on any snapshot table (RI-03).
        Column-level privilege grant enforces this at the database level.
        """
        await self._session.execute(
            update(SnapshotCalculation)
            .where(SnapshotCalculation.id == snapshot_id)
            .values(is_superseded=True, superseded_at=superseded_at)
        )

    # ------------------------------------------------------------------
    # Read — FULL level (6 queries)
    # ------------------------------------------------------------------

    async def find_by_id(
        self, snapshot_id: uuid.UUID
    ) -> CalculationSnapshot | None:
        """
        Load the full snapshot aggregate (all 6 sub-tables).
        Uses 6 separate indexed queries — no JOINs (Part 7.1).
        Returns None if not found.
        """
        root = await self._fetch_root(snapshot_id)
        if root is None:
            return None

        inputs_row = await self._fetch_one(SnapshotInputs, snapshot_id)
        outputs_row = await self._fetch_one(SnapshotOutputs, snapshot_id)
        intermediates_row = await self._fetch_one(SnapshotIntermediates, snapshot_id)
        flag_rows = await self._fetch_many(SnapshotRiskFlag, snapshot_id)
        warning_rows = await self._fetch_many(SnapshotValidationWarning, snapshot_id)

        return self._assemble_full(
            root, inputs_row, outputs_row, intermediates_row, flag_rows, warning_rows
        )

    # ------------------------------------------------------------------
    # Read — DISPLAY level (3 queries)
    # ------------------------------------------------------------------

    async def find_by_id_outputs_only(
        self, snapshot_id: uuid.UUID
    ) -> SnapshotSummary | None:
        """
        Load root + outputs + risk flags + warnings (DISPLAY level).
        Does NOT load inputs or intermediates (Part 7.2).
        Returns None if not found.
        """
        root = await self._fetch_root(snapshot_id)
        if root is None:
            return None

        outputs_row = await self._fetch_one(SnapshotOutputs, snapshot_id)
        flag_rows = await self._fetch_many(SnapshotRiskFlag, snapshot_id)
        warning_rows = await self._fetch_many(SnapshotValidationWarning, snapshot_id)

        if outputs_row is None:
            return None

        return SnapshotSummary(
            id=root.id,
            deal_id=root.deal_id,
            engine_version=root.engine_version,
            calculated_at=root.calculated_at,
            is_superseded=root.is_superseded,
            outputs=self._map_outputs(outputs_row),  # type: ignore[arg-type]
            risk_flags=[self._map_flag(r) for r in flag_rows],  # type: ignore[arg-type]
            validation_warnings=[self._map_warning(r) for r in warning_rows],  # type: ignore[arg-type]
            config_version_refs=ConfigVersionRefs(
                assumption_config_version_id=root.assumption_config_version_id,
                sdlt_config_version_id=root.sdlt_config_version_id,
                corporation_tax_config_version_id=root.corporation_tax_config_version_id,
            ),
        )

    # ------------------------------------------------------------------
    # Read — SUMMARY level (1 aggregating query)
    # ------------------------------------------------------------------

    async def find_history_for_deal(
        self, deal_id: uuid.UUID
    ) -> list[SnapshotHistoryEntry]:
        """
        Load SUMMARY entries for all snapshots of a deal, calculated_at DESC.
        Computes flag counts via aggregation — not N+1 (Part 7.3).
        """
        # Flag count subquery
        flag_counts_sq = (
            select(
                SnapshotRiskFlag.snapshot_id,
                func.count()
                .filter(SnapshotRiskFlag.severity == FlagSeverity.HIGH)
                .label("high_count"),
                func.count()
                .filter(SnapshotRiskFlag.severity == FlagSeverity.MEDIUM)
                .label("medium_count"),
                func.count()
                .filter(SnapshotRiskFlag.severity == FlagSeverity.INFO)
                .label("info_count"),
            )
            .where(
                SnapshotRiskFlag.snapshot_id.in_(
                    select(SnapshotCalculation.id).where(
                        SnapshotCalculation.deal_id == deal_id
                    )
                )
            )
            .group_by(SnapshotRiskFlag.snapshot_id)
            .subquery()
        )

        from sqlalchemy import outerjoin

        join_expr = outerjoin(
            SnapshotCalculation,
            SnapshotOutputs,
            SnapshotCalculation.id == SnapshotOutputs.snapshot_id,
        ).outerjoin(
            flag_counts_sq,
            SnapshotCalculation.id == flag_counts_sq.c.snapshot_id,
        )

        stmt = (
            select(
                SnapshotCalculation.id,
                SnapshotCalculation.deal_id,
                SnapshotCalculation.engine_version,
                SnapshotCalculation.calculated_at,
                SnapshotCalculation.is_superseded,
                SnapshotOutputs.annual_cash_flow_gbp,
                SnapshotOutputs.gross_yield_percent,
                flag_counts_sq.c.high_count,
                flag_counts_sq.c.medium_count,
                flag_counts_sq.c.info_count,
            )
            .select_from(join_expr)
            .where(SnapshotCalculation.deal_id == deal_id)
            .order_by(SnapshotCalculation.calculated_at.desc())
        )

        result = await self._session.execute(stmt)
        rows = result.all()

        return [
            SnapshotHistoryEntry(
                id=r.id,
                deal_id=r.deal_id,
                engine_version=r.engine_version,
                calculated_at=r.calculated_at,
                is_superseded=r.is_superseded,
                risk_flag_count_high=int(r.high_count) if r.high_count else 0,
                risk_flag_count_medium=int(r.medium_count) if r.medium_count else 0,
                risk_flag_count_info=int(r.info_count) if r.info_count else 0,
                annual_cash_flow_gbp=Decimal(str(r.annual_cash_flow_gbp)),
                gross_yield_percent=Decimal(str(r.gross_yield_percent)),
            )
            for r in rows
        ]

    # ------------------------------------------------------------------
    # Internal fetch helpers
    # ------------------------------------------------------------------

    async def _fetch_root(
        self, snapshot_id: uuid.UUID
    ) -> SnapshotCalculation | None:
        result = await self._session.execute(
            select(SnapshotCalculation).where(SnapshotCalculation.id == snapshot_id)
        )
        return result.scalar_one_or_none()

    async def _fetch_one(self, model: type, snapshot_id: uuid.UUID) -> object | None:
        from sqlalchemy.engine import Result  # noqa: PLC0415

        execute_result: Result = await self._session.execute(  # type: ignore[type-arg]
            select(model).where(model.snapshot_id == snapshot_id)  # type: ignore[attr-defined]
        )
        return execute_result.scalar_one_or_none()

    async def _fetch_many(self, model: type, snapshot_id: uuid.UUID) -> list[object]:
        from sqlalchemy.engine import Result  # noqa: PLC0415

        execute_result: Result = await self._session.execute(  # type: ignore[type-arg]
            select(model).where(model.snapshot_id == snapshot_id)  # type: ignore[attr-defined]
        )
        return list(execute_result.scalars().all())

    # ------------------------------------------------------------------
    # ORM → Domain mappers
    # ------------------------------------------------------------------

    def _assemble_full(
        self,
        root: SnapshotCalculation,
        inputs_row: object | None,
        outputs_row: object | None,
        intermediates_row: object | None,
        flag_rows: list[object],
        warning_rows: list[object],
    ) -> CalculationSnapshot:
        assert inputs_row is not None, "snapshot_inputs row missing for snapshot"
        assert outputs_row is not None, "snapshot_outputs row missing for snapshot"
        assert intermediates_row is not None, "snapshot_intermediates row missing"

        return CalculationSnapshot(
            id=root.id,
            deal_id=root.deal_id,
            user_id=root.user_id,
            engine_version=root.engine_version,
            config_version_refs=ConfigVersionRefs(
                assumption_config_version_id=root.assumption_config_version_id,
                sdlt_config_version_id=root.sdlt_config_version_id,
                corporation_tax_config_version_id=root.corporation_tax_config_version_id,
            ),
            calculated_at=root.calculated_at,
            inputs=self._map_inputs(inputs_row),  # type: ignore[arg-type]
            outputs=self._map_outputs(outputs_row),  # type: ignore[arg-type]
            intermediates=self._map_intermediates(intermediates_row),  # type: ignore[arg-type]
            risk_flags=[self._map_flag(r) for r in flag_rows],  # type: ignore[arg-type]
            validation_warnings=[self._map_warning(r) for r in warning_rows],  # type: ignore[arg-type]
            is_superseded=root.is_superseded,
            superseded_at=root.superseded_at,
            calculation_duration_ms=root.calculation_duration_ms,
        )

    @staticmethod
    def _d(val: Decimal | None) -> Decimal:
        """Coerce ORM Decimal to a clean Decimal (RI-13)."""
        return Decimal(str(val))

    @staticmethod
    def _m(val: Decimal | None) -> Money:
        """ORM Decimal → Money."""
        return Money(Decimal(str(val)))

    @staticmethod
    def _r(val: Decimal | None) -> Rate:
        """ORM Decimal → Rate."""
        return Rate(Decimal(str(val)))

    @staticmethod
    def _r_or_none(val: Decimal | None) -> Rate | None:
        """ORM nullable Decimal → Rate | None."""
        return Rate(Decimal(str(val))) if val is not None else None

    @staticmethod
    def _m_or_none(val: Decimal | None) -> Money | None:
        """ORM nullable Decimal → Money | None."""
        return Money(Decimal(str(val))) if val is not None else None

    @staticmethod
    def _coerce_enum(val: object, enum_type: type) -> object:
        """Defensive asyncpg enum coercion."""
        return val if isinstance(val, enum_type) else enum_type(val)

    def _map_inputs(self, row: SnapshotInputs) -> DomainSnapshotInputs:
        return DomainSnapshotInputs(
            purchase_price=self._m(row.purchase_price),
            monthly_rent=self._m(row.monthly_rent),
            deposit_amount=self._m(row.deposit_amount),
            mortgage_interest_rate=self._r(row.mortgage_interest_rate),
            mortgage_term_years=row.mortgage_term_years,
            mortgage_type=self._coerce_enum(row.mortgage_type, MortgageType),  # type: ignore[arg-type]
            ownership_structure=self._coerce_enum(row.ownership_structure, OwnershipStructure),  # type: ignore[arg-type]
            income_tax_band=self._coerce_enum(row.income_tax_band, IncomeTaxBand)  # type: ignore[arg-type]
            if row.income_tax_band is not None
            else None,
            is_additional_dwelling=row.is_additional_dwelling,
            property_type=self._coerce_enum(row.property_type, PropertyType),  # type: ignore[arg-type]
            tenure=self._coerce_enum(row.tenure, Tenure),  # type: ignore[arg-type]
            property_country=self._coerce_enum(row.property_country, PropertyCountry),  # type: ignore[arg-type]
            postcode=row.postcode,
            lease_years_remaining=row.lease_years_remaining,
            void_rate_percent=self._r(row.void_rate_percent),
            void_rate_percent_source=self._coerce_enum(row.void_rate_percent_source, InputSource),  # type: ignore[arg-type]
            letting_agent_fee_percent=self._r(row.letting_agent_fee_percent),
            letting_agent_fee_percent_source=self._coerce_enum(row.letting_agent_fee_percent_source, InputSource),  # type: ignore[arg-type]
            maintenance_reserve_percent=self._r(row.maintenance_reserve_percent),
            maintenance_reserve_percent_source=self._coerce_enum(row.maintenance_reserve_percent_source, InputSource),  # type: ignore[arg-type]
            landlord_insurance_annual=self._m(row.landlord_insurance_annual),
            landlord_insurance_annual_source=self._coerce_enum(row.landlord_insurance_annual_source, InputSource),  # type: ignore[arg-type]
            purchase_legal_costs=self._m(row.purchase_legal_costs),
            purchase_legal_costs_source=self._coerce_enum(row.purchase_legal_costs_source, InputSource),  # type: ignore[arg-type]
            refurbishment_cost=self._m(row.refurbishment_cost),
            refurbishment_cost_source=self._coerce_enum(row.refurbishment_cost_source, InputSource),  # type: ignore[arg-type]
            annual_service_charge=self._m(row.annual_service_charge),
            annual_service_charge_source=self._coerce_enum(row.annual_service_charge_source, InputSource),  # type: ignore[arg-type]
            annual_ground_rent=self._m(row.annual_ground_rent),
            annual_ground_rent_source=self._coerce_enum(row.annual_ground_rent_source, InputSource),  # type: ignore[arg-type]
            annual_accountancy_cost=self._m(row.annual_accountancy_cost),
            annual_accountancy_cost_source=self._coerce_enum(row.annual_accountancy_cost_source, InputSource),  # type: ignore[arg-type]
        )

    def _map_outputs(self, row: SnapshotOutputs) -> DomainSnapshotOutputs:
        return DomainSnapshotOutputs(
            gross_annual_rent_gbp=self._m(row.gross_annual_rent_gbp),
            effective_annual_rent_gbp=self._m(row.effective_annual_rent_gbp),
            total_operating_costs_annual_gbp=self._m(row.total_operating_costs_annual_gbp),
            net_operating_income_gbp=self._m(row.net_operating_income_gbp),
            annual_mortgage_cost_gbp=self._m(row.annual_mortgage_cost_gbp),
            annual_tax_liability_gbp=self._m(row.annual_tax_liability_gbp),
            annual_cash_flow_gbp=self._m(row.annual_cash_flow_gbp),
            monthly_cash_flow_gbp=self._m(row.monthly_cash_flow_gbp),
            gross_yield_percent=self._r(row.gross_yield_percent),
            net_yield_percent=self._r(row.net_yield_percent),
            roce_percent=self._r(row.roce_percent),
            cash_on_cash_return_percent=self._r(row.cash_on_cash_return_percent),
            ltv_percent=self._r(row.ltv_percent),
            icr_percent=self._r_or_none(row.icr_percent),
            total_sdlt_gbp=self._m(row.total_sdlt_gbp),
            total_acquisition_cost_gbp=self._m(row.total_acquisition_cost_gbp),
            total_cash_deployed_gbp=self._m(row.total_cash_deployed_gbp),
        )

    def _map_intermediates(self, row: SnapshotIntermediates) -> DomainSnapshotIntermediates:
        return DomainSnapshotIntermediates(
            void_rate_decimal_applied=self._d(row.void_rate_decimal_applied),
            gross_annual_rent_gbp=self._m(row.gross_annual_rent_gbp),
            effective_annual_rent_gbp=self._m(row.effective_annual_rent_gbp),
            loan_amount_gbp=self._m(row.loan_amount_gbp),
            ltv_percent=self._r(row.ltv_percent),
            monthly_mortgage_payment_gbp=self._m(row.monthly_mortgage_payment_gbp),
            annual_mortgage_cost_gbp=self._m(row.annual_mortgage_cost_gbp),
            annual_mortgage_interest_gbp=self._m(row.annual_mortgage_interest_gbp),
            letting_agent_annual_gbp=self._m(row.letting_agent_annual_gbp),
            letting_agent_vat_rate_applied=self._r(row.letting_agent_vat_rate_applied),
            annual_maintenance_reserve_gbp=self._m(row.annual_maintenance_reserve_gbp),
            total_operating_costs_annual_gbp=self._m(row.total_operating_costs_annual_gbp),
            net_operating_income_gbp=self._m(row.net_operating_income_gbp),
            sdlt_band_breakdown=self._map_sdlt_bands_from_jsonb(row.sdlt_band_breakdown),
            sdlt_base_gbp=self._m(row.sdlt_base_gbp),
            sdlt_surcharge_gbp=self._m(row.sdlt_surcharge_gbp),
            sdlt_surcharge_rate_applied=self._r(row.sdlt_surcharge_rate_applied),
            total_sdlt_gbp=self._m(row.total_sdlt_gbp),
            total_acquisition_cost_gbp=self._m(row.total_acquisition_cost_gbp),
            total_cash_deployed_gbp=self._m(row.total_cash_deployed_gbp),
            stressed_annual_interest_gbp=self._m(row.stressed_annual_interest_gbp),
            stress_test_rate_applied_percent=self._r(row.stress_test_rate_applied_percent),
            taxable_income_or_profit_gbp=self._m(row.taxable_income_or_profit_gbp),
            income_tax_gross_gbp=self._m_or_none(row.income_tax_gross_gbp),
            mortgage_interest_tax_credit_gbp=self._m_or_none(
                row.mortgage_interest_tax_credit_gbp
            ),
            corporation_tax_gross_gbp=self._m_or_none(row.corporation_tax_gross_gbp),
            annual_tax_liability_gbp=self._m(row.annual_tax_liability_gbp),
            pre_tax_annual_cash_flow_gbp=self._m(row.pre_tax_annual_cash_flow_gbp),
            section_24_applies=row.section_24_applies,
        )

    @staticmethod
    def _map_flag(row: SnapshotRiskFlag) -> RiskFlag:
        severity = (
            row.severity
            if isinstance(row.severity, FlagSeverity)
            else FlagSeverity(row.severity)
        )
        return RiskFlag(
            code=row.flag_code,
            severity=severity,
            triggered_by_field=row.triggered_by_field,
            triggered_by_value=row.triggered_by_value,
            message=row.message,
        )

    @staticmethod
    def _map_warning(row: SnapshotValidationWarning) -> ValidationWarning:
        return ValidationWarning(
            rule_code=row.rule_code,
            field=row.field,
            message=row.message,
        )

    # ------------------------------------------------------------------
    # Domain → ORM builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_inputs_row(
        snapshot_id: uuid.UUID, inputs: DomainSnapshotInputs
    ) -> SnapshotInputs:
        return SnapshotInputs(
            snapshot_id=snapshot_id,
            purchase_price=inputs.purchase_price.amount,
            monthly_rent=inputs.monthly_rent.amount,
            deposit_amount=inputs.deposit_amount.amount,
            mortgage_interest_rate=inputs.mortgage_interest_rate.value,
            mortgage_term_years=inputs.mortgage_term_years,
            mortgage_type=inputs.mortgage_type,
            ownership_structure=inputs.ownership_structure,
            income_tax_band=inputs.income_tax_band,
            is_additional_dwelling=inputs.is_additional_dwelling,
            property_type=inputs.property_type,
            tenure=inputs.tenure,
            property_country=inputs.property_country,
            postcode=inputs.postcode,
            lease_years_remaining=inputs.lease_years_remaining,
            void_rate_percent=inputs.void_rate_percent.value,
            void_rate_percent_source=inputs.void_rate_percent_source,
            letting_agent_fee_percent=inputs.letting_agent_fee_percent.value,
            letting_agent_fee_percent_source=inputs.letting_agent_fee_percent_source,
            maintenance_reserve_percent=inputs.maintenance_reserve_percent.value,
            maintenance_reserve_percent_source=inputs.maintenance_reserve_percent_source,
            landlord_insurance_annual=inputs.landlord_insurance_annual.amount,
            landlord_insurance_annual_source=inputs.landlord_insurance_annual_source,
            purchase_legal_costs=inputs.purchase_legal_costs.amount,
            purchase_legal_costs_source=inputs.purchase_legal_costs_source,
            refurbishment_cost=inputs.refurbishment_cost.amount,
            refurbishment_cost_source=inputs.refurbishment_cost_source,
            annual_service_charge=inputs.annual_service_charge.amount,
            annual_service_charge_source=inputs.annual_service_charge_source,
            annual_ground_rent=inputs.annual_ground_rent.amount,
            annual_ground_rent_source=inputs.annual_ground_rent_source,
            annual_accountancy_cost=inputs.annual_accountancy_cost.amount,
            annual_accountancy_cost_source=inputs.annual_accountancy_cost_source,
        )

    @staticmethod
    def _build_outputs_row(
        snapshot_id: uuid.UUID, outputs: DomainSnapshotOutputs
    ) -> SnapshotOutputs:
        return SnapshotOutputs(
            snapshot_id=snapshot_id,
            gross_annual_rent_gbp=outputs.gross_annual_rent_gbp.amount,
            effective_annual_rent_gbp=outputs.effective_annual_rent_gbp.amount,
            total_operating_costs_annual_gbp=outputs.total_operating_costs_annual_gbp.amount,
            net_operating_income_gbp=outputs.net_operating_income_gbp.amount,
            annual_mortgage_cost_gbp=outputs.annual_mortgage_cost_gbp.amount,
            annual_tax_liability_gbp=outputs.annual_tax_liability_gbp.amount,
            annual_cash_flow_gbp=outputs.annual_cash_flow_gbp.amount,
            monthly_cash_flow_gbp=outputs.monthly_cash_flow_gbp.amount,
            gross_yield_percent=outputs.gross_yield_percent.value,
            net_yield_percent=outputs.net_yield_percent.value,
            roce_percent=outputs.roce_percent.value,
            cash_on_cash_return_percent=outputs.cash_on_cash_return_percent.value,
            ltv_percent=outputs.ltv_percent.value,
            icr_percent=outputs.icr_percent.value if outputs.icr_percent is not None else None,
            total_sdlt_gbp=outputs.total_sdlt_gbp.amount,
            total_acquisition_cost_gbp=outputs.total_acquisition_cost_gbp.amount,
            total_cash_deployed_gbp=outputs.total_cash_deployed_gbp.amount,
        )

    @classmethod
    def _build_intermediates_row(
        cls, snapshot_id: uuid.UUID, inter: DomainSnapshotIntermediates
    ) -> SnapshotIntermediates:
        return SnapshotIntermediates(
            snapshot_id=snapshot_id,
            void_rate_decimal_applied=inter.void_rate_decimal_applied,
            gross_annual_rent_gbp=inter.gross_annual_rent_gbp.amount,
            effective_annual_rent_gbp=inter.effective_annual_rent_gbp.amount,
            loan_amount_gbp=inter.loan_amount_gbp.amount,
            ltv_percent=inter.ltv_percent.value,
            monthly_mortgage_payment_gbp=inter.monthly_mortgage_payment_gbp.amount,
            annual_mortgage_cost_gbp=inter.annual_mortgage_cost_gbp.amount,
            annual_mortgage_interest_gbp=inter.annual_mortgage_interest_gbp.amount,
            letting_agent_annual_gbp=inter.letting_agent_annual_gbp.amount,
            letting_agent_vat_rate_applied=inter.letting_agent_vat_rate_applied.value,
            annual_maintenance_reserve_gbp=inter.annual_maintenance_reserve_gbp.amount,
            total_operating_costs_annual_gbp=inter.total_operating_costs_annual_gbp.amount,
            net_operating_income_gbp=inter.net_operating_income_gbp.amount,
            sdlt_band_breakdown=cls._sdlt_bands_to_jsonb(inter.sdlt_band_breakdown),
            sdlt_base_gbp=inter.sdlt_base_gbp.amount,
            sdlt_surcharge_gbp=inter.sdlt_surcharge_gbp.amount,
            sdlt_surcharge_rate_applied=inter.sdlt_surcharge_rate_applied.value,
            total_sdlt_gbp=inter.total_sdlt_gbp.amount,
            total_acquisition_cost_gbp=inter.total_acquisition_cost_gbp.amount,
            total_cash_deployed_gbp=inter.total_cash_deployed_gbp.amount,
            stressed_annual_interest_gbp=inter.stressed_annual_interest_gbp.amount,
            stress_test_rate_applied_percent=inter.stress_test_rate_applied_percent.value,
            taxable_income_or_profit_gbp=inter.taxable_income_or_profit_gbp.amount,
            income_tax_gross_gbp=inter.income_tax_gross_gbp.amount
            if inter.income_tax_gross_gbp is not None
            else None,
            mortgage_interest_tax_credit_gbp=inter.mortgage_interest_tax_credit_gbp.amount
            if inter.mortgage_interest_tax_credit_gbp is not None
            else None,
            corporation_tax_gross_gbp=inter.corporation_tax_gross_gbp.amount
            if inter.corporation_tax_gross_gbp is not None
            else None,
            annual_tax_liability_gbp=inter.annual_tax_liability_gbp.amount,
            pre_tax_annual_cash_flow_gbp=inter.pre_tax_annual_cash_flow_gbp.amount,
            section_24_applies=inter.section_24_applies,
        )

    # ------------------------------------------------------------------
    # SDLT band JSONB serialisation (DATABASE_SCHEMA_DESIGN.md Part 3.3)
    # All numbers stored as strings; band_upper is None for the top band.
    # ------------------------------------------------------------------

    @staticmethod
    def _sdlt_bands_to_jsonb(
        bands: tuple[SDLTBandResult, ...],
    ) -> list[dict[str, str | None]]:
        result = []
        for band in bands:
            result.append(
                {
                    "band_lower": str(band.band_lower.amount),
                    "band_upper": str(band.band_upper.amount)
                    if band.band_upper is not None
                    else None,
                    "rate": str(band.rate.value),
                    "taxable_in_band": str(band.taxable_in_band.amount),
                    "tax_in_band": str(band.tax_in_band.amount),
                }
            )
        return result

    @staticmethod
    def _map_sdlt_bands_from_jsonb(
        data: list[dict[str, str | None]],
    ) -> tuple[SDLTBandResult, ...]:
        bands = []
        for item in data:
            band_upper_str = item.get("band_upper")
            bands.append(
                SDLTBandResult(
                    band_lower=Money(Decimal(str(item["band_lower"]))),
                    band_upper=Money(Decimal(str(band_upper_str)))
                    if band_upper_str is not None
                    else None,
                    rate=Rate(Decimal(str(item["rate"]))),
                    taxable_in_band=Money(Decimal(str(item["taxable_in_band"]))),
                    tax_in_band=Money(Decimal(str(item["tax_in_band"]))),
                )
            )
        return tuple(bands)
