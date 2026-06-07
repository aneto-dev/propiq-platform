"""
Snapshot request/response Pydantic v2 schemas.

All monetary fields are serialised as strings to avoid JSON float precision
loss. e.g. "annual_cash_flow_gbp": "-331.90"

The Money value object's .amount (Decimal) and Rate value object's .value
(Decimal) are serialised via custom field validators.

Architecture:
    APPLICATION_SERVICE_ARCHITECTURE.md Part 15.
    IMPLEMENTATION_ROADMAP.md Commit 6.2.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.api.v1.schemas.common import MoneyStr, RateStr
from app.domain.enums import FlagSeverity
from app.domain.value_objects.money import Money
from app.domain.value_objects.rate import Rate


def _money_str(value: Money | None) -> MoneyStr | None:
    """Serialise a Money value object to a string with 2dp."""
    if value is None:
        return None
    return f"{value.amount:.2f}"


def _rate_str(value: Rate | None) -> RateStr | None:
    """Serialise a Rate value object to a string with 2dp."""
    if value is None:
        return None
    return f"{value.value:.2f}"


def _decimal_str(value: Decimal | None) -> str | None:
    """Serialise a plain Decimal to a string with 2dp."""
    if value is None:
        return None
    return f"{value:.2f}"


class RiskFlagResponse(BaseModel):
    """One triggered risk flag in a snapshot summary."""

    code: str
    severity: FlagSeverity
    triggered_by_field: str
    triggered_by_value: str
    message: str

    model_config = {"from_attributes": True}


class ValidationWarningResponse(BaseModel):
    """One validation warning attached to a snapshot."""

    rule_code: str
    field: str
    message: str

    model_config = {"from_attributes": True}


class SnapshotOutputsResponse(BaseModel):
    """
    All output metrics from a calculation, serialised as strings.

    All monetary fields use MoneyStr (2dp GBP string).
    All rate/percentage fields use RateStr (2dp percentage string).
    icr_percent is None for cash purchases.
    """

    gross_annual_rent_gbp: MoneyStr
    effective_annual_rent_gbp: MoneyStr
    total_operating_costs_annual_gbp: MoneyStr
    net_operating_income_gbp: MoneyStr
    annual_mortgage_cost_gbp: MoneyStr
    annual_tax_liability_gbp: MoneyStr
    annual_cash_flow_gbp: MoneyStr
    monthly_cash_flow_gbp: MoneyStr
    gross_yield_percent: RateStr
    net_yield_percent: RateStr
    roce_percent: RateStr
    cash_on_cash_return_percent: RateStr
    ltv_percent: RateStr
    icr_percent: RateStr | None
    total_sdlt_gbp: MoneyStr
    total_acquisition_cost_gbp: MoneyStr
    total_cash_deployed_gbp: MoneyStr

    model_config = {"from_attributes": True}

    @classmethod
    def from_snapshot_outputs(cls, outputs: object) -> SnapshotOutputsResponse:
        """
        Build from a SnapshotOutputs domain entity, converting Money/Rate
        value objects to strings.
        """
        from app.domain.entities.snapshot import SnapshotOutputs

        o: SnapshotOutputs = outputs  # type: ignore[assignment]
        return cls(
            gross_annual_rent_gbp=_money_str(o.gross_annual_rent_gbp) or "0.00",
            effective_annual_rent_gbp=_money_str(o.effective_annual_rent_gbp) or "0.00",
            total_operating_costs_annual_gbp=_money_str(o.total_operating_costs_annual_gbp) or "0.00",
            net_operating_income_gbp=_money_str(o.net_operating_income_gbp) or "0.00",
            annual_mortgage_cost_gbp=_money_str(o.annual_mortgage_cost_gbp) or "0.00",
            annual_tax_liability_gbp=_money_str(o.annual_tax_liability_gbp) or "0.00",
            annual_cash_flow_gbp=_money_str(o.annual_cash_flow_gbp) or "0.00",
            monthly_cash_flow_gbp=_money_str(o.monthly_cash_flow_gbp) or "0.00",
            gross_yield_percent=_rate_str(o.gross_yield_percent) or "0.00",
            net_yield_percent=_rate_str(o.net_yield_percent) or "0.00",
            roce_percent=_rate_str(o.roce_percent) or "0.00",
            cash_on_cash_return_percent=_rate_str(o.cash_on_cash_return_percent) or "0.00",
            ltv_percent=_rate_str(o.ltv_percent) or "0.00",
            icr_percent=_rate_str(o.icr_percent) if o.icr_percent is not None else None,
            total_sdlt_gbp=_money_str(o.total_sdlt_gbp) or "0.00",
            total_acquisition_cost_gbp=_money_str(o.total_acquisition_cost_gbp) or "0.00",
            total_cash_deployed_gbp=_money_str(o.total_cash_deployed_gbp) or "0.00",
        )


class SnapshotSummaryResponse(BaseModel):
    """
    DISPLAY-level snapshot response: outputs + risk flags + warnings.
    Suitable for the deal summary view and the API response after calculation.
    """

    id: uuid.UUID
    deal_id: uuid.UUID
    engine_version: str
    calculated_at: datetime
    is_superseded: bool
    outputs: SnapshotOutputsResponse
    risk_flags: list[RiskFlagResponse]
    validation_warnings: list[ValidationWarningResponse]

    @classmethod
    def from_snapshot_summary(cls, summary: object) -> SnapshotSummaryResponse:
        """Build from a SnapshotSummary domain projection."""
        from app.repositories.interfaces.i_snapshot import SnapshotSummary

        s: SnapshotSummary = summary  # type: ignore[assignment]
        return cls(
            id=s.id,
            deal_id=s.deal_id,
            engine_version=s.engine_version,
            calculated_at=s.calculated_at,
            is_superseded=s.is_superseded,
            outputs=SnapshotOutputsResponse.from_snapshot_outputs(s.outputs),
            risk_flags=[
                RiskFlagResponse(
                    code=f.code,
                    severity=f.severity,
                    triggered_by_field=f.triggered_by_field,
                    triggered_by_value=f.triggered_by_value,
                    message=f.message,
                )
                for f in s.risk_flags
            ],
            validation_warnings=[
                ValidationWarningResponse(
                    rule_code=w.rule_code,
                    field=w.field,
                    message=w.message,
                )
                for w in s.validation_warnings
            ],
        )


class SDLTBandResultResponse(BaseModel):
    """One SDLT band's contribution to the total SDLT calculation."""

    band_lower: MoneyStr
    band_upper: MoneyStr | None
    rate: RateStr
    taxable_in_band: MoneyStr
    tax_in_band: MoneyStr


class SnapshotIntermediatesResponse(BaseModel):
    """
    All intermediate values from the calculation pipeline.

    Included in SnapshotFullResponse for audit and explainability.
    Monetary fields are serialised as strings to avoid float precision loss.
    void_rate_decimal_applied is a raw Decimal fraction (e.g. "0.038500")
    stored at its native precision.
    """

    void_rate_decimal_applied: str         # fraction form, native precision
    gross_annual_rent_gbp: MoneyStr
    effective_annual_rent_gbp: MoneyStr
    loan_amount_gbp: MoneyStr
    ltv_percent: RateStr
    monthly_mortgage_payment_gbp: MoneyStr
    annual_mortgage_cost_gbp: MoneyStr
    annual_mortgage_interest_gbp: MoneyStr
    letting_agent_annual_gbp: MoneyStr
    letting_agent_vat_rate_applied: RateStr
    annual_maintenance_reserve_gbp: MoneyStr
    total_operating_costs_annual_gbp: MoneyStr
    net_operating_income_gbp: MoneyStr
    sdlt_band_breakdown: list[SDLTBandResultResponse]
    sdlt_base_gbp: MoneyStr
    sdlt_surcharge_gbp: MoneyStr
    sdlt_surcharge_rate_applied: RateStr
    total_sdlt_gbp: MoneyStr
    total_acquisition_cost_gbp: MoneyStr
    total_cash_deployed_gbp: MoneyStr
    stressed_annual_interest_gbp: MoneyStr
    stress_test_rate_applied_percent: RateStr
    taxable_income_or_profit_gbp: MoneyStr
    income_tax_gross_gbp: MoneyStr | None
    mortgage_interest_tax_credit_gbp: MoneyStr | None
    corporation_tax_gross_gbp: MoneyStr | None
    annual_tax_liability_gbp: MoneyStr
    pre_tax_annual_cash_flow_gbp: MoneyStr
    section_24_applies: bool

    @classmethod
    def from_intermediates(cls, i: object) -> SnapshotIntermediatesResponse:
        """Build from a SnapshotIntermediates domain entity."""
        from app.domain.entities.snapshot import SnapshotIntermediates

        v: SnapshotIntermediates = i  # type: ignore[assignment]
        return cls(
            void_rate_decimal_applied=str(v.void_rate_decimal_applied),
            gross_annual_rent_gbp=_money_str(v.gross_annual_rent_gbp) or "0.00",
            effective_annual_rent_gbp=_money_str(v.effective_annual_rent_gbp) or "0.00",
            loan_amount_gbp=_money_str(v.loan_amount_gbp) or "0.00",
            ltv_percent=_rate_str(v.ltv_percent) or "0.00",
            monthly_mortgage_payment_gbp=_money_str(v.monthly_mortgage_payment_gbp) or "0.00",
            annual_mortgage_cost_gbp=_money_str(v.annual_mortgage_cost_gbp) or "0.00",
            annual_mortgage_interest_gbp=_money_str(v.annual_mortgage_interest_gbp) or "0.00",
            letting_agent_annual_gbp=_money_str(v.letting_agent_annual_gbp) or "0.00",
            letting_agent_vat_rate_applied=_rate_str(v.letting_agent_vat_rate_applied) or "0.00",
            annual_maintenance_reserve_gbp=_money_str(v.annual_maintenance_reserve_gbp) or "0.00",
            total_operating_costs_annual_gbp=_money_str(v.total_operating_costs_annual_gbp) or "0.00",
            net_operating_income_gbp=_money_str(v.net_operating_income_gbp) or "0.00",
            sdlt_band_breakdown=[
                SDLTBandResultResponse(
                    band_lower=_money_str(b.band_lower) or "0.00",
                    band_upper=_money_str(b.band_upper) if b.band_upper is not None else None,
                    rate=_rate_str(b.rate) or "0.00",
                    taxable_in_band=_money_str(b.taxable_in_band) or "0.00",
                    tax_in_band=_money_str(b.tax_in_band) or "0.00",
                )
                for b in v.sdlt_band_breakdown
            ],
            sdlt_base_gbp=_money_str(v.sdlt_base_gbp) or "0.00",
            sdlt_surcharge_gbp=_money_str(v.sdlt_surcharge_gbp) or "0.00",
            sdlt_surcharge_rate_applied=_rate_str(v.sdlt_surcharge_rate_applied) or "0.00",
            total_sdlt_gbp=_money_str(v.total_sdlt_gbp) or "0.00",
            total_acquisition_cost_gbp=_money_str(v.total_acquisition_cost_gbp) or "0.00",
            total_cash_deployed_gbp=_money_str(v.total_cash_deployed_gbp) or "0.00",
            stressed_annual_interest_gbp=_money_str(v.stressed_annual_interest_gbp) or "0.00",
            stress_test_rate_applied_percent=_rate_str(v.stress_test_rate_applied_percent) or "0.00",
            taxable_income_or_profit_gbp=_money_str(v.taxable_income_or_profit_gbp) or "0.00",
            income_tax_gross_gbp=_money_str(v.income_tax_gross_gbp),
            mortgage_interest_tax_credit_gbp=_money_str(v.mortgage_interest_tax_credit_gbp),
            corporation_tax_gross_gbp=_money_str(v.corporation_tax_gross_gbp),
            annual_tax_liability_gbp=_money_str(v.annual_tax_liability_gbp) or "0.00",
            pre_tax_annual_cash_flow_gbp=_money_str(v.pre_tax_annual_cash_flow_gbp) or "0.00",
            section_24_applies=v.section_24_applies,
        )


class SnapshotFullResponse(BaseModel):
    """
    FULL-level snapshot response: outputs + risk flags + warnings + intermediates.

    Used for audit display and reproducibility verification.
    Includes sdlt_band_breakdown as an ordered array.

    Architecture:
        APPLICATION_SERVICE_ARCHITECTURE.md Part 6.2 — FULL loading level.
        IMPLEMENTATION_ROADMAP.md Commit 6.5.
    """

    id: uuid.UUID
    deal_id: uuid.UUID
    engine_version: str
    calculated_at: datetime
    is_superseded: bool
    outputs: SnapshotOutputsResponse
    risk_flags: list[RiskFlagResponse]
    validation_warnings: list[ValidationWarningResponse]
    intermediates: SnapshotIntermediatesResponse

    @classmethod
    def from_full_snapshot(cls, snapshot: object) -> SnapshotFullResponse:
        """Build from a CalculationSnapshot domain aggregate."""
        from app.domain.entities.snapshot import CalculationSnapshot

        s: CalculationSnapshot = snapshot  # type: ignore[assignment]
        return cls(
            id=s.id,
            deal_id=s.deal_id,
            engine_version=s.engine_version,
            calculated_at=s.calculated_at,
            is_superseded=s.is_superseded,
            outputs=SnapshotOutputsResponse.from_snapshot_outputs(s.outputs),
            risk_flags=[
                RiskFlagResponse(
                    code=f.code,
                    severity=f.severity,
                    triggered_by_field=f.triggered_by_field,
                    triggered_by_value=f.triggered_by_value,
                    message=f.message,
                )
                for f in s.risk_flags
            ],
            validation_warnings=[
                ValidationWarningResponse(
                    rule_code=w.rule_code,
                    field=w.field,
                    message=w.message,
                )
                for w in s.validation_warnings
            ],
            intermediates=SnapshotIntermediatesResponse.from_intermediates(s.intermediates),
        )


class SnapshotHistoryEntryResponse(BaseModel):
    """
    SUMMARY-level snapshot response for history list views.
    Key metrics only — no full outputs list.
    """

    id: uuid.UUID
    deal_id: uuid.UUID
    engine_version: str
    calculated_at: datetime
    is_superseded: bool
    risk_flag_count_high: int
    risk_flag_count_medium: int
    risk_flag_count_info: int
    annual_cash_flow_gbp: str   # Decimal serialised as string
    gross_yield_percent: str    # Decimal serialised as string

    @classmethod
    def from_history_entry(cls, entry: object) -> SnapshotHistoryEntryResponse:
        """Build from a SnapshotHistoryEntry domain projection."""
        from app.repositories.interfaces.i_snapshot import SnapshotHistoryEntry

        e: SnapshotHistoryEntry = entry  # type: ignore[assignment]
        return cls(
            id=e.id,
            deal_id=e.deal_id,
            engine_version=e.engine_version,
            calculated_at=e.calculated_at,
            is_superseded=e.is_superseded,
            risk_flag_count_high=e.risk_flag_count_high,
            risk_flag_count_medium=e.risk_flag_count_medium,
            risk_flag_count_info=e.risk_flag_count_info,
            annual_cash_flow_gbp=_decimal_str(e.annual_cash_flow_gbp) or "0.00",
            gross_yield_percent=_decimal_str(e.gross_yield_percent) or "0.00",
        )
