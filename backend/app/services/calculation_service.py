"""
CalculationService — end-to-end calculation pipeline.

Assembles ConfigurationService, engine, AuditService, and SnapshotService
into the complete calculation flow defined in APPLICATION_SERVICE_ARCHITECTURE.md
Part 5.

Public method:
  run_calculation(user_id, deal_id, raw_inputs, calculation_date, client_context)
      → CalculationSuccess | CalculationValidationFailure | CalculationError

Result types defined here (service-layer only):
  CalculationSuccess          — snapshot created; returns id, summary, deal status
  CalculationValidationFailure — engine rejected inputs; returns structured errors
  CalculationError            — unexpected engine failure; sanitised message

Internal helpers:
  assemble_engine_input(resolved_inputs) → EngineInput
      Constructs EngineInput from ResolvedInputs. Fields are identical;
      this is a direct constructor call with no type conversion required.

  build_snapshot_from_engine_result(...) → CalculationSnapshot
      Maps EngineResult + EngineInput + InputSourceMap → CalculationSnapshot
      domain aggregate. Converts Decimal fields from the engine contract layer
      into Money/Rate domain value objects.

Architecture:
    APPLICATION_SERVICE_ARCHITECTURE.md Part 5, Part 6.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.domain.entities.snapshot import (
    CalculationSnapshot,
    ConfigVersionRefs,
    RiskFlag,
    SDLTBandResult,
    SnapshotInputs,
    SnapshotIntermediates,
    SnapshotOutputs,
    ValidationWarning,
)
from app.domain.enums import CalculationOutcome, DealStatus
from app.domain.errors import DomainError, NotFoundError
from app.domain.value_objects.money import Money
from app.domain.value_objects.rate import Rate
from app.engine import run as engine_run
from app.engine.contracts import (
    EngineError,
    EngineInput,
    EngineResult,
    ValidationError,
    ValidationResult,
)
from app.engine.contracts import RiskFlag as EngineRiskFlag
from app.engine.contracts import SDLTBandResult as EngineSDLTBandResult
from app.engine.contracts import (
    ValidationWarning as EngineValidationWarning,
)
from app.engine.version import ENGINE_VERSION
from app.repositories.deal_repository import DealRepository
from app.repositories.interfaces.i_audit import CalculationAuditEvent
from app.repositories.interfaces.i_deal import IDealRepository
from app.services.audit_service import AuditService
from app.services.configuration_service import (
    ConfigurationService,
    InputSourceMap,
    RawCalculationInputs,
    ResolvedInputs,
)
from app.services.snapshot_service import SnapshotService, make_snapshot_service

# ---------------------------------------------------------------------------
# Result types
# APPLICATION_SERVICE_ARCHITECTURE.md Part 5.1
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CalculationSuccess:
    """
    Returned when the engine produces a valid result and the snapshot is
    persisted. The snapshot_summary is loaded immediately after persistence
    for the API response.

    Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 5.1.
    """

    snapshot_id: uuid.UUID
    snapshot_summary: object  # SnapshotSummary — typed as object to avoid circular import
    deal_status_after: DealStatus


@dataclass(frozen=True)
class CalculationValidationFailure:
    """
    Returned when the engine's validation pipeline rejects the inputs.

    hard_errors is non-empty. No snapshot is created. An audit record is
    written with outcome=VALIDATION_FAILURE.

    Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 5.1.
    """

    hard_errors: list[ValidationError]
    warnings: list[EngineValidationWarning]


@dataclass(frozen=True)
class CalculationError:
    """
    Returned on unexpected engine failure. message is sanitised — no stack
    traces, no internal detail.

    Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 5.1.
    """

    message: str


CalculationResult = CalculationSuccess | CalculationValidationFailure | CalculationError


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def assemble_engine_input(resolved: ResolvedInputs) -> EngineInput:
    """
    Construct an EngineInput from ResolvedInputs.

    ResolvedInputs and EngineInput share identical field names and types
    (all Decimal for numeric fields). This is a direct field-for-field
    constructor call — no type conversion required.

    Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 5.2 STEP 5.
    """
    return EngineInput(
        purchase_price=resolved.purchase_price,
        monthly_rent=resolved.monthly_rent,
        deposit_amount=resolved.deposit_amount,
        mortgage_interest_rate=resolved.mortgage_interest_rate,
        mortgage_term_years=resolved.mortgage_term_years,
        mortgage_type=resolved.mortgage_type,
        ownership_structure=resolved.ownership_structure,
        income_tax_band=resolved.income_tax_band,
        is_additional_dwelling=resolved.is_additional_dwelling,
        property_type=resolved.property_type,
        tenure=resolved.tenure,
        property_country=resolved.property_country,
        postcode=resolved.postcode,
        void_rate_percent=resolved.void_rate_percent,
        letting_agent_fee_percent=resolved.letting_agent_fee_percent,
        maintenance_reserve_percent=resolved.maintenance_reserve_percent,
        landlord_insurance_annual=resolved.landlord_insurance_annual,
        purchase_legal_costs=resolved.purchase_legal_costs,
        refurbishment_cost=resolved.refurbishment_cost,
        annual_service_charge=resolved.annual_service_charge,
        annual_ground_rent=resolved.annual_ground_rent,
        annual_accountancy_cost=resolved.annual_accountancy_cost,
        lease_years_remaining=resolved.lease_years_remaining,
    )


def _m(d: Decimal) -> Money:
    """Wrap a Decimal in Money(GBP)."""
    return Money(d)


def _r(d: Decimal) -> Rate:
    """Wrap a Decimal in Rate."""
    return Rate(d)


def _m_or_none(d: Decimal | None) -> Money | None:
    return Money(d) if d is not None else None


def _map_sdlt_band(band: EngineSDLTBandResult) -> SDLTBandResult:
    return SDLTBandResult(
        band_lower=Money(band.band_lower),
        band_upper=Money(band.band_upper) if band.band_upper is not None else None,
        rate=Rate(band.rate),
        taxable_in_band=Money(band.taxable_in_band),
        tax_in_band=Money(band.tax_in_band),
    )


def _map_risk_flag(flag: EngineRiskFlag) -> RiskFlag:
    return RiskFlag(
        code=flag.code,
        severity=flag.severity,
        triggered_by_field=flag.triggered_by_field,
        triggered_by_value=flag.triggered_by_value,
        message=flag.message,
    )


def _map_warning(w: EngineValidationWarning) -> ValidationWarning:
    return ValidationWarning(
        rule_code=w.rule_code,
        field=w.field,
        message=w.message,
    )


def build_snapshot_from_engine_result(
    snapshot_id: uuid.UUID,
    deal_id: uuid.UUID,
    user_id: uuid.UUID,
    engine_result: EngineResult,
    engine_input: EngineInput,
    input_sources: InputSourceMap,
    config_version_refs: ConfigVersionRefs,
    calculated_at: datetime,
) -> CalculationSnapshot:
    """
    Map EngineResult + EngineInput + InputSourceMap → CalculationSnapshot.

    Converts engine contract types (plain Decimal) to domain value objects
    (Money for monetary fields, Rate for percentages). The engine's SDLTBandResult
    and RiskFlag types have identical field names to the domain types but
    different numeric wrappers — each is converted individually.

    Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 5.2 PATH C.
    """
    o = engine_result.outputs
    i = engine_result.intermediates

    outputs = SnapshotOutputs(
        gross_annual_rent_gbp=_m(o.gross_annual_rent_gbp),
        effective_annual_rent_gbp=_m(o.effective_annual_rent_gbp),
        total_operating_costs_annual_gbp=_m(o.total_operating_costs_annual_gbp),
        net_operating_income_gbp=_m(o.net_operating_income_gbp),
        annual_mortgage_cost_gbp=_m(o.annual_mortgage_cost_gbp),
        annual_tax_liability_gbp=_m(o.annual_tax_liability_gbp),
        annual_cash_flow_gbp=_m(o.annual_cash_flow_gbp),
        monthly_cash_flow_gbp=_m(o.monthly_cash_flow_gbp),
        gross_yield_percent=_r(o.gross_yield_percent),
        net_yield_percent=_r(o.net_yield_percent),
        roce_percent=_r(o.roce_percent),
        cash_on_cash_return_percent=_r(o.cash_on_cash_return_percent),
        ltv_percent=_r(o.ltv_percent),
        icr_percent=_r(o.icr_percent) if o.icr_percent is not None else None,
        total_sdlt_gbp=_m(o.total_sdlt_gbp),
        total_acquisition_cost_gbp=_m(o.total_acquisition_cost_gbp),
        total_cash_deployed_gbp=_m(o.total_cash_deployed_gbp),
    )

    intermediates = SnapshotIntermediates(
        void_rate_decimal_applied=i.void_rate_decimal_applied,
        gross_annual_rent_gbp=_m(i.gross_annual_rent_gbp),
        effective_annual_rent_gbp=_m(i.effective_annual_rent_gbp),
        loan_amount_gbp=_m(i.loan_amount_gbp),
        ltv_percent=_r(i.ltv_percent),
        monthly_mortgage_payment_gbp=_m(i.monthly_mortgage_payment_gbp),
        annual_mortgage_cost_gbp=_m(i.annual_mortgage_cost_gbp),
        annual_mortgage_interest_gbp=_m(i.annual_mortgage_interest_gbp),
        letting_agent_annual_gbp=_m(i.letting_agent_annual_gbp),
        letting_agent_vat_rate_applied=_r(i.letting_agent_vat_rate_applied),
        annual_maintenance_reserve_gbp=_m(i.annual_maintenance_reserve_gbp),
        total_operating_costs_annual_gbp=_m(i.total_operating_costs_annual_gbp),
        net_operating_income_gbp=_m(i.net_operating_income_gbp),
        sdlt_band_breakdown=tuple(_map_sdlt_band(b) for b in i.sdlt_band_breakdown),
        sdlt_base_gbp=_m(i.sdlt_base_gbp),
        sdlt_surcharge_gbp=_m(i.sdlt_surcharge_gbp),
        sdlt_surcharge_rate_applied=_r(i.sdlt_surcharge_rate_applied),
        total_sdlt_gbp=_m(i.total_sdlt_gbp),
        total_acquisition_cost_gbp=_m(i.total_acquisition_cost_gbp),
        total_cash_deployed_gbp=_m(i.total_cash_deployed_gbp),
        stressed_annual_interest_gbp=_m(i.stressed_annual_interest_gbp),
        stress_test_rate_applied_percent=_r(i.stress_test_rate_applied_percent),
        taxable_income_or_profit_gbp=_m(i.taxable_income_or_profit_gbp),
        income_tax_gross_gbp=_m_or_none(i.income_tax_gross_gbp),
        mortgage_interest_tax_credit_gbp=_m_or_none(i.mortgage_interest_tax_credit_gbp),
        corporation_tax_gross_gbp=_m_or_none(i.corporation_tax_gross_gbp),
        annual_tax_liability_gbp=_m(i.annual_tax_liability_gbp),
        pre_tax_annual_cash_flow_gbp=_m(i.pre_tax_annual_cash_flow_gbp),
        section_24_applies=i.section_24_applies,
    )

    inputs = SnapshotInputs(
        purchase_price=_m(engine_input.purchase_price),
        monthly_rent=_m(engine_input.monthly_rent),
        deposit_amount=_m(engine_input.deposit_amount),
        mortgage_interest_rate=_r(engine_input.mortgage_interest_rate),
        mortgage_term_years=engine_input.mortgage_term_years,
        mortgage_type=engine_input.mortgage_type,
        ownership_structure=engine_input.ownership_structure,
        income_tax_band=engine_input.income_tax_band,
        is_additional_dwelling=engine_input.is_additional_dwelling,
        property_type=engine_input.property_type,
        tenure=engine_input.tenure,
        property_country=engine_input.property_country,
        postcode=engine_input.postcode,
        lease_years_remaining=engine_input.lease_years_remaining,
        void_rate_percent=_r(engine_input.void_rate_percent),
        void_rate_percent_source=input_sources.void_rate_percent_source,
        letting_agent_fee_percent=_r(engine_input.letting_agent_fee_percent),
        letting_agent_fee_percent_source=input_sources.letting_agent_fee_percent_source,
        maintenance_reserve_percent=_r(engine_input.maintenance_reserve_percent),
        maintenance_reserve_percent_source=input_sources.maintenance_reserve_percent_source,
        landlord_insurance_annual=_m(engine_input.landlord_insurance_annual),
        landlord_insurance_annual_source=input_sources.landlord_insurance_annual_source,
        purchase_legal_costs=_m(engine_input.purchase_legal_costs),
        purchase_legal_costs_source=input_sources.purchase_legal_costs_source,
        refurbishment_cost=_m(engine_input.refurbishment_cost),
        refurbishment_cost_source=input_sources.refurbishment_cost_source,
        annual_service_charge=_m(engine_input.annual_service_charge),
        annual_service_charge_source=input_sources.annual_service_charge_source,
        annual_ground_rent=_m(engine_input.annual_ground_rent),
        annual_ground_rent_source=input_sources.annual_ground_rent_source,
        annual_accountancy_cost=_m(engine_input.annual_accountancy_cost),
        annual_accountancy_cost_source=input_sources.annual_accountancy_cost_source,
    )

    return CalculationSnapshot(
        id=snapshot_id,
        deal_id=deal_id,
        user_id=user_id,
        engine_version=ENGINE_VERSION,
        config_version_refs=config_version_refs,
        calculated_at=calculated_at,
        inputs=inputs,
        outputs=outputs,
        intermediates=intermediates,
        risk_flags=[_map_risk_flag(f) for f in engine_result.risk_flags],
        validation_warnings=[_map_warning(w) for w in engine_result.validation_warnings],
    )


# ---------------------------------------------------------------------------
# CalculationService
# ---------------------------------------------------------------------------

class CalculationService:
    """
    Orchestrates the full calculation pipeline.

    Dependencies (all injected):
      session          — AsyncSession for deal load and snapshot persistence
      deal_repo        — IDealRepository for ownership verification
      config_repo      — IConfigurationRepository for ConfigurationService
      snapshot_service — SnapshotService for atomic snapshot persist + read
      audit_service    — AuditService for failure path audit writes
      config_service   — ConfigurationService for config load + default resolution

    Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 5.
    """

    def __init__(
        self,
        session: AsyncSession,
        deal_repo: IDealRepository,
        config_service: ConfigurationService,
        snapshot_service: SnapshotService,
        audit_service: AuditService,
    ) -> None:
        self._session = session
        self._deal_repo = deal_repo
        self._config_service = config_service
        self._snapshot_service = snapshot_service
        self._audit_service = audit_service

    async def run_calculation(
        self,
        user_id: uuid.UUID,
        deal_id: uuid.UUID,
        raw_inputs: RawCalculationInputs,
        calculation_date: date,
        client_context: str | None = None,
    ) -> CalculationResult:
        """
        Run the full calculation pipeline and return the result.

        Steps (APPLICATION_SERVICE_ARCHITECTURE.md Part 5.2):
          1. Verify deal ownership → NotFoundError if not found/wrong user
          2. Check deal is not ARCHIVED → DomainError if archived
          3. Load active configuration via ConfigurationService
          4. Resolve optional input defaults via ConfigurationService
          5. Assemble EngineInput
          6. Call engine.run()
          7. Route on result type (PATH A: validation failure, PATH B: engine error,
             PATH C: success)
          8. On success: persist snapshot atomically via SnapshotService
          9. Load SnapshotSummary for response
         10. Return CalculationSuccess

        Architecture: APPLICATION_SERVICE_ARCHITECTURE.md Part 5.2.
        """

        # STEP 1 — Ownership verification
        deal = await self._deal_repo.find_by_id_for_user(deal_id, user_id)
        if deal is None:
            raise NotFoundError(entity="deal", id=deal_id)

        # STEP 2 — Domain precondition check
        if deal.status == DealStatus.ARCHIVED:
            raise DomainError("Cannot calculate on an archived deal")

        # STEP 3 — Load active configuration
        config_bundle = await self._config_service.load_for_calculation(calculation_date)

        # STEP 4 — Resolve input defaults
        resolved_inputs, input_sources = self._config_service.resolve_defaults(
            raw_inputs=raw_inputs,
            assumption_config=config_bundle.assumption_config_domain,
            ownership_structure=raw_inputs.ownership_structure,
        )

        # STEP 5 — Assemble EngineInput
        engine_input = assemble_engine_input(resolved_inputs)

        # STEP 6 — Call the engine
        engine_result = engine_run(engine_input, config_bundle.engine_config)

        now = datetime.now(UTC)

        # STEP 7 — Route on engine result type

        # PATH A: Validation failure
        if isinstance(engine_result, ValidationResult) and not engine_result.is_valid:
            audit_event = CalculationAuditEvent(
                id=uuid.uuid4(),
                user_id=user_id,
                deal_id=deal_id,
                snapshot_id=None,
                triggered_at=now,
                outcome=CalculationOutcome.VALIDATION_FAILURE,
                engine_version=ENGINE_VERSION,
                validation_errors=[
                    {"rule_code": e.rule_code, "field": e.field, "message": e.message}
                    for e in engine_result.hard_errors
                ],
                error_detail=None,
                client_context=client_context,
                created_at=now,
            )
            await self._audit_service.write_failure(audit_event)
            return CalculationValidationFailure(
                hard_errors=engine_result.hard_errors,
                warnings=engine_result.warnings,
            )

        # PATH B: Engine error
        if isinstance(engine_result, EngineError):
            audit_event = CalculationAuditEvent(
                id=uuid.uuid4(),
                user_id=user_id,
                deal_id=deal_id,
                snapshot_id=None,
                triggered_at=now,
                outcome=CalculationOutcome.ENGINE_ERROR,
                engine_version=ENGINE_VERSION,
                validation_errors=None,
                error_detail=engine_result.detail,
                client_context=client_context,
                created_at=now,
            )
            await self._audit_service.write_failure(audit_event)
            return CalculationError(message="Calculation could not be completed.")

        # PATH C: Success (EngineResult)
        assert isinstance(engine_result, EngineResult)
        snapshot_id = uuid.uuid4()
        calculated_at = now

        audit_event = CalculationAuditEvent(
            id=uuid.uuid4(),
            user_id=user_id,
            deal_id=deal_id,
            snapshot_id=snapshot_id,
            triggered_at=calculated_at,
            outcome=CalculationOutcome.SUCCESS,
            engine_version=ENGINE_VERSION,
            validation_errors=None,
            error_detail=None,
            client_context=client_context,
            created_at=calculated_at,
        )

        snapshot = build_snapshot_from_engine_result(
            snapshot_id=snapshot_id,
            deal_id=deal_id,
            user_id=user_id,
            engine_result=engine_result,
            engine_input=engine_input,
            input_sources=input_sources,
            config_version_refs=config_bundle.version_refs,
            calculated_at=calculated_at,
        )

        # STEP 8 — Persist (atomic)
        await self._snapshot_service.save_snapshot_and_update_deal(
            snapshot=snapshot,
            deal=deal,
            audit_event=audit_event,
        )

        # STEP 9 — Load summary for response
        snapshot_summary = await self._snapshot_service.get_display_summary(
            snapshot_id, user_id
        )

        # STEP 10 — Return
        return CalculationSuccess(
            snapshot_id=snapshot_id,
            snapshot_summary=snapshot_summary,
            deal_status_after=DealStatus.ANALYSED,
        )


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------

def make_calculation_service(
    session: AsyncSession,
    session_factory: async_sessionmaker[AsyncSession],
    config_repo: object,
) -> CalculationService:
    """
    Construct a CalculationService with all concrete dependencies.

    session         — live session for deal load and snapshot persist
    session_factory — for AuditService.write_failure() (fresh session)
    config_repo     — IConfigurationRepository implementation
    """

    if not isinstance(config_repo, object):
        pass  # type narrowing only

    return CalculationService(
        session=session,
        deal_repo=DealRepository(session),
        config_service=ConfigurationService(config_repo),  # type: ignore[arg-type]
        snapshot_service=make_snapshot_service(session),
        audit_service=AuditService(session_factory=session_factory),
    )
