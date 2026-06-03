"""
Engine orchestrator — single public entry point.

Executes the 13-step calculation sequence defined in ENGINE_ARCHITECTURE.md
Part 6. Returns one of three types:

    EngineResult       — successful calculation
    ValidationResult   — HARD validation failure (calculation not attempted)
    EngineError        — unexpected failure after validation passes

The orchestrator is the ONLY module with imports from all four sub-modules.
No sub-module imports from any other sub-module (ENGINE_ARCHITECTURE.md).

Rounding: values are kept at full Decimal precision throughout the pipeline.
Rounding to 2dp ROUND_HALF_UP occurs ONLY when writing into EngineOutputs
and EngineIntermediates (Step 13). Never earlier.
(ENGINE_CONTRACTS.md Part 7.2 — canonical precision rule.)

Architecture: ENGINE_ARCHITECTURE.md Part 6 — Calculation Orchestration Flow.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, getcontext

from app.domain.enums import OwnershipStructure
from app.engine.calculations.formulas import (
    f01_gross_annual_rent,
    f02_void_rate_decimal,
    f03_effective_annual_rent,
    f04_loan_amount,
    f05_ltv_percent,
    f06_monthly_mortgage_payment,
    f07_annual_mortgage_cost,
    f08_annual_mortgage_interest,
    f09_letting_agent_annual,
    f10_annual_maintenance_reserve,
    f11_total_operating_costs,
    f12_net_operating_income,
    f13_sdlt,
    f14_total_acquisition_cost,
    f15_total_cash_deployed,
    f16_gross_yield_percent,
    f17_net_yield_percent,
    f18_roce_percent,
    f19_annual_cash_flow,
    f20_monthly_cash_flow,
    f21_cash_on_cash_return_percent,
    f22_icr_percent,
    f22_stressed_annual_interest,
)
from app.engine.contracts import (
    EngineConfig,
    EngineError,
    EngineInput,
    EngineIntermediates,
    EngineOutputs,
    EngineResult,
    SDLTBandResult,
    ValidationResult,
    ValidationWarning,
)
from app.engine.risk_flags.definitions import EvaluationContext, evaluate_flags
from app.engine.tax.individual import calculate_individual_tax
from app.engine.tax.limited_company import calculate_limited_company_tax
from app.engine.validation.rules import run_validation
from app.engine.version import ENGINE_VERSION

# ENGINE_CONTRACTS.md Part 7.1 — minimum working precision of 10 significant
# decimal places. Set at module level; applies to all Decimal operations in
# this process. Sub-modules never override this.
getcontext().prec = 10

_TWO_DP = Decimal("0.01")


def _r(value: Decimal) -> Decimal:
    """Round to 2dp ROUND_HALF_UP. Applied ONLY at Step 13."""
    return value.quantize(_TWO_DP, rounding=ROUND_HALF_UP)


def run(
    engine_input: EngineInput,
    engine_config: EngineConfig,
) -> EngineResult | ValidationResult | EngineError:
    """
    Execute the full underwriting engine pipeline.

    Steps 0–13 follow ENGINE_ARCHITECTURE.md Part 6 exactly.
    Each step receives only the values it needs — never the full EngineInput.

    Returns:
        EngineResult       — all outputs, intermediates, flags, warnings
        ValidationResult   — when any HARD validation rule fires
        EngineError        — when an unexpected exception occurs after
                             validation passes (engine never raises to caller)
    """
    # ------------------------------------------------------------------
    # STEP 0 — Validation pipeline
    # ------------------------------------------------------------------
    try:
        validation_result = run_validation(engine_input)
    except Exception as exc:  # pragma: no cover
        return EngineError(
            error_code="VALIDATION_ERROR",
            detail=f"Validation pipeline raised unexpectedly: {type(exc).__name__}",
            engine_version=ENGINE_VERSION,
        )

    if not validation_result.is_valid:
        # Return ValidationResult unchanged — caller routes on this type
        return validation_result

    # Carry WARN-only warnings forward into the final EngineResult
    validation_warnings: list[ValidationWarning] = (
        validation_result.warnings
    )


    try:
        return _calculate(engine_input, engine_config, validation_warnings)
    except Exception as exc:  # pragma: no cover
        return EngineError(
            error_code="CALCULATION_ERROR",
            detail=(
                f"Unexpected error during calculation: {type(exc).__name__}: {exc}"
            ),
            engine_version=ENGINE_VERSION,
        )


def _calculate(
    i: EngineInput,
    cfg: EngineConfig,
    validation_warnings: list[ValidationWarning],
) -> EngineResult:
    """
    Execute Steps 1–13. Called only when validation has passed.

    Parameters named `i` (input) and `cfg` (config) for brevity in a function
    where every line references them. All local names match ENGINE_CONTRACTS.md
    EngineIntermediates field names exactly (without the _gbp suffix that
    appears in the persisted record).
    """
    # ------------------------------------------------------------------
    # STEP 1 — Resolve mortgage scenario
    # cash_purchase = True → loan = 0, all mortgage calcs produce zero.
    # This is an internal branch, not a flag. (ENGINE_ARCHITECTURE.md Step 1.)
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # STEP 2 — Income
    # F-01, F-02, F-03
    # ------------------------------------------------------------------
    gross_annual_rent = f01_gross_annual_rent(i.monthly_rent)
    void_rate_decimal = f02_void_rate_decimal(i.void_rate_percent)
    effective_annual_rent = f03_effective_annual_rent(
        gross_annual_rent, void_rate_decimal
    )

    # ------------------------------------------------------------------
    # STEP 3 — Financing
    # F-04, F-05, F-06, F-07, F-08
    # ------------------------------------------------------------------
    loan_amount = f04_loan_amount(i.purchase_price, i.deposit_amount)
    ltv_percent = f05_ltv_percent(loan_amount, i.purchase_price)
    monthly_mortgage_payment = f06_monthly_mortgage_payment(
        loan_amount,
        i.mortgage_interest_rate,
        i.mortgage_term_years,
        i.mortgage_type,
    )
    annual_mortgage_cost = f07_annual_mortgage_cost(monthly_mortgage_payment)
    annual_mortgage_interest = f08_annual_mortgage_interest(
        loan_amount,
        i.mortgage_interest_rate,
        i.mortgage_type,
        monthly_mortgage_payment,
    )

    # ------------------------------------------------------------------
    # STEP 4 — SDLT
    # F-13: orchestrator unpacks SDLTBand objects → plain tuples before
    # calling f13, keeping calculations/ free of contracts imports.
    # ------------------------------------------------------------------
    sdlt_bands_plain = tuple(
        (b.band_lower, b.band_upper, b.rate)
        for b in cfg.sdlt_config.bands
    )
    sdlt_result = f13_sdlt(
        i.purchase_price,
        sdlt_bands_plain,
        cfg.sdlt_config.additional_dwelling_surcharge_rate,
        i.is_additional_dwelling,
    )

    # ------------------------------------------------------------------
    # STEP 5 — Acquisition totals
    # F-14, F-15
    # ------------------------------------------------------------------
    total_acquisition_cost = f14_total_acquisition_cost(
        i.purchase_price,
        sdlt_result.total_sdlt,
        i.purchase_legal_costs,
        i.refurbishment_cost,
    )
    total_cash_deployed = f15_total_cash_deployed(
        i.deposit_amount,
        sdlt_result.total_sdlt,
        i.purchase_legal_costs,
        i.refurbishment_cost,
    )

    # ------------------------------------------------------------------
    # STEP 6 — Operating costs
    # F-09, F-10, F-11
    # VAT rate taken from config — never hardcoded.
    # ------------------------------------------------------------------
    letting_agent_annual = f09_letting_agent_annual(
        gross_annual_rent,
        i.letting_agent_fee_percent,
        cfg.assumption_config.letting_agent_vat_rate_percent,
    )
    annual_maintenance_reserve = f10_annual_maintenance_reserve(
        i.purchase_price,
        i.maintenance_reserve_percent,
    )
    total_operating_costs = f11_total_operating_costs(
        letting_agent_annual,
        annual_maintenance_reserve,
        i.landlord_insurance_annual,
        i.annual_service_charge,
        i.annual_ground_rent,
        i.annual_accountancy_cost,
    )

    # ------------------------------------------------------------------
    # STEP 7 — Net Operating Income
    # F-12
    # ------------------------------------------------------------------
    net_operating_income = f12_net_operating_income(
        effective_annual_rent, total_operating_costs
    )

    # ------------------------------------------------------------------
    # STEP 8 — Tax pathway
    # Branch on ownership_structure. Both pathways use the same operating
    # cost components — passed explicitly, not via a sub-object.
    # ------------------------------------------------------------------
    pre_tax_annual_cash_flow = net_operating_income - annual_mortgage_cost

    if i.ownership_structure == OwnershipStructure.INDIVIDUAL:
        tax_result_ind = calculate_individual_tax(
            effective_annual_rent=effective_annual_rent,
            letting_agent_annual=letting_agent_annual,
            annual_maintenance_reserve=annual_maintenance_reserve,
            landlord_insurance_annual=i.landlord_insurance_annual,
            annual_service_charge=i.annual_service_charge,
            annual_ground_rent=i.annual_ground_rent,
            annual_accountancy_cost=i.annual_accountancy_cost,
            annual_mortgage_interest=annual_mortgage_interest,
            income_tax_band=i.income_tax_band,  # type: ignore[arg-type]
        )
        annual_tax_liability = tax_result_ind.annual_tax_liability
        taxable_income_or_profit = tax_result_ind.taxable_rental_income
        income_tax_gross: Decimal | None = tax_result_ind.income_tax_gross
        mortgage_interest_tax_credit: Decimal | None = (
            tax_result_ind.mortgage_interest_tax_credit
        )
        corporation_tax_gross: Decimal | None = None
        section_24_applies = tax_result_ind.section_24_applies

    else:  # LIMITED_COMPANY
        ct_cfg = cfg.corporation_tax_config
        tax_result_ltd = calculate_limited_company_tax(
            effective_annual_rent=effective_annual_rent,
            letting_agent_annual=letting_agent_annual,
            annual_maintenance_reserve=annual_maintenance_reserve,
            landlord_insurance_annual=i.landlord_insurance_annual,
            annual_service_charge=i.annual_service_charge,
            annual_ground_rent=i.annual_ground_rent,
            annual_accountancy_cost=i.annual_accountancy_cost,
            annual_mortgage_interest=annual_mortgage_interest,
            small_profits_rate=ct_cfg.small_profits_rate,
            small_profits_upper_threshold=ct_cfg.small_profits_upper_threshold,
            main_rate=ct_cfg.main_rate,
            main_rate_lower_threshold=ct_cfg.main_rate_lower_threshold,
            marginal_relief_numerator=ct_cfg.marginal_relief_numerator,
            marginal_relief_denominator=ct_cfg.marginal_relief_denominator,
        )
        annual_tax_liability = tax_result_ltd.annual_tax_liability
        taxable_income_or_profit = tax_result_ltd.taxable_company_profit
        income_tax_gross = None
        mortgage_interest_tax_credit = None
        corporation_tax_gross = tax_result_ltd.corporation_tax_gross
        section_24_applies = False

    # ------------------------------------------------------------------
    # STEP 9 — Cash flow
    # F-19, F-20
    # ------------------------------------------------------------------
    annual_cash_flow = f19_annual_cash_flow(
        net_operating_income, annual_mortgage_cost, annual_tax_liability
    )
    monthly_cash_flow = f20_monthly_cash_flow(annual_cash_flow)

    # ------------------------------------------------------------------
    # STEP 10 — Yields and returns
    # F-16, F-17, F-18, F-21
    # ------------------------------------------------------------------
    gross_yield_percent = f16_gross_yield_percent(
        gross_annual_rent, i.purchase_price
    )
    net_yield_percent = f17_net_yield_percent(
        net_operating_income, i.purchase_price
    )
    roce_percent = f18_roce_percent(net_operating_income, total_cash_deployed)
    cash_on_cash_return_percent = f21_cash_on_cash_return_percent(
        annual_cash_flow, total_cash_deployed
    )

    # ------------------------------------------------------------------
    # STEP 11 — Stress test
    # F-22a, F-22b
    # ------------------------------------------------------------------
    stressed_annual_interest = f22_stressed_annual_interest(
        loan_amount,
        cfg.assumption_config.stress_test_rate_percent,
    )
    icr_percent = f22_icr_percent(effective_annual_rent, stressed_annual_interest)

    # ------------------------------------------------------------------
    # STEP 12 — Risk flag evaluation
    # All values passed explicitly into EvaluationContext.
    # Context receives full-precision (unrounded) values — flags fire on
    # the same values that flow into outputs.
    # ------------------------------------------------------------------
    context = EvaluationContext(
        annual_cash_flow=annual_cash_flow,
        gross_annual_rent=gross_annual_rent,
        net_operating_income=net_operating_income,
        gross_yield_percent=gross_yield_percent,
        net_yield_percent=net_yield_percent,
        ltv_percent=ltv_percent,
        icr_percent=icr_percent,
        pre_tax_annual_cash_flow=pre_tax_annual_cash_flow,
        ownership_structure=i.ownership_structure,
        income_tax_band=i.income_tax_band,
        tenure=i.tenure,
        lease_years_remaining=i.lease_years_remaining,
        purchase_price=i.purchase_price,
        refurbishment_cost=i.refurbishment_cost,
        monthly_rent=i.monthly_rent,
    )
    risk_flags = evaluate_flags(context)

    # ------------------------------------------------------------------
    # STEP 13 — Assemble EngineResult
    # ALL rounding occurs here and only here.
    # ENGINE_CONTRACTS.md Part 7.2: round only when writing into
    # EngineOutputs and EngineIntermediates.
    # ------------------------------------------------------------------

    # Map SDLTBandCalculation NamedTuples → SDLTBandResult contract objects
    sdlt_band_results = tuple(
        SDLTBandResult(
            band_lower=_r(b.band_lower),
            band_upper=_r(b.band_upper) if b.band_upper is not None else None,
            rate=b.rate,  # rate is exact (e.g. 0.02); no rounding needed
            taxable_in_band=_r(b.taxable_in_band),
            tax_in_band=_r(b.tax_in_band),
        )
        for b in sdlt_result.band_breakdown
    )

    outputs = EngineOutputs(
        gross_annual_rent_gbp=_r(gross_annual_rent),
        effective_annual_rent_gbp=_r(effective_annual_rent),
        total_operating_costs_annual_gbp=_r(total_operating_costs),
        net_operating_income_gbp=_r(net_operating_income),
        annual_mortgage_cost_gbp=_r(annual_mortgage_cost),
        annual_tax_liability_gbp=_r(annual_tax_liability),
        annual_cash_flow_gbp=_r(annual_cash_flow),
        monthly_cash_flow_gbp=_r(monthly_cash_flow),
        gross_yield_percent=_r(gross_yield_percent),
        net_yield_percent=_r(net_yield_percent),
        roce_percent=_r(roce_percent),
        cash_on_cash_return_percent=_r(cash_on_cash_return_percent),
        ltv_percent=_r(ltv_percent),
        icr_percent=_r(icr_percent) if icr_percent is not None else None,
        total_sdlt_gbp=_r(sdlt_result.total_sdlt),
        total_acquisition_cost_gbp=_r(total_acquisition_cost),
        total_cash_deployed_gbp=_r(total_cash_deployed),
    )

    intermediates = EngineIntermediates(
        void_rate_decimal_applied=_r(void_rate_decimal),
        gross_annual_rent_gbp=_r(gross_annual_rent),
        effective_annual_rent_gbp=_r(effective_annual_rent),
        loan_amount_gbp=_r(loan_amount),
        ltv_percent=_r(ltv_percent),
        monthly_mortgage_payment_gbp=_r(monthly_mortgage_payment),
        annual_mortgage_cost_gbp=_r(annual_mortgage_cost),
        annual_mortgage_interest_gbp=_r(annual_mortgage_interest),
        letting_agent_annual_gbp=_r(letting_agent_annual),
        letting_agent_vat_rate_applied=(
            cfg.assumption_config.letting_agent_vat_rate_percent
        ),
        annual_maintenance_reserve_gbp=_r(annual_maintenance_reserve),
        total_operating_costs_annual_gbp=_r(total_operating_costs),
        net_operating_income_gbp=_r(net_operating_income),
        sdlt_band_breakdown=sdlt_band_results,
        sdlt_base_gbp=_r(sdlt_result.sdlt_base),
        sdlt_surcharge_gbp=_r(sdlt_result.sdlt_surcharge),
        sdlt_surcharge_rate_applied=cfg.sdlt_config.additional_dwelling_surcharge_rate,
        total_sdlt_gbp=_r(sdlt_result.total_sdlt),
        total_acquisition_cost_gbp=_r(total_acquisition_cost),
        total_cash_deployed_gbp=_r(total_cash_deployed),
        stressed_annual_interest_gbp=_r(stressed_annual_interest),
        stress_test_rate_applied_percent=cfg.assumption_config.stress_test_rate_percent,
        taxable_income_or_profit_gbp=_r(taxable_income_or_profit),
        income_tax_gross_gbp=(
            _r(income_tax_gross) if income_tax_gross is not None else None
        ),
        mortgage_interest_tax_credit_gbp=(
            _r(mortgage_interest_tax_credit)
            if mortgage_interest_tax_credit is not None
            else None
        ),
        corporation_tax_gross_gbp=(
            _r(corporation_tax_gross) if corporation_tax_gross is not None else None
        ),
        annual_tax_liability_gbp=_r(annual_tax_liability),
        pre_tax_annual_cash_flow_gbp=_r(pre_tax_annual_cash_flow),
        section_24_applies=section_24_applies,
    )

    return EngineResult(
        outputs=outputs,
        intermediates=intermediates,
        risk_flags=risk_flags,
        validation_warnings=validation_warnings,
    )
