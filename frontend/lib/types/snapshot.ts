/**
 * Snapshot TypeScript types — mirror of backend app/api/v1/schemas/snapshot.py.
 *
 * All monetary and rate fields are strings (MoneyStr / RateStr) serialised
 * with 2 decimal places, e.g. "-331.90", "75.00".
 * All UUIDs are strings. Timestamps are ISO 8601 strings.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.2.
 */

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export type FlagSeverity = "HIGH" | "MEDIUM" | "INFO";

// ---------------------------------------------------------------------------
// Sub-types
// ---------------------------------------------------------------------------

/** Mirrors RiskFlagResponse — one triggered risk flag. */
export interface RiskFlag {
  code: string;
  severity: FlagSeverity;
  triggered_by_field: string;
  triggered_by_value: string;
  message: string;
}

/** Mirrors ValidationWarningResponse — one WARN-level validation note. */
export interface ValidationWarning {
  rule_code: string;
  field: string;
  message: string;
}

/**
 * Mirrors SnapshotOutputsResponse — all 17 calculation output metrics.
 * All monetary fields are MoneyStr strings. Rate fields are RateStr strings.
 * icr_percent is null for cash purchases (no mortgage).
 */
export interface SnapshotOutputs {
  gross_annual_rent_gbp: string;
  effective_annual_rent_gbp: string;
  total_operating_costs_annual_gbp: string;
  net_operating_income_gbp: string;
  annual_mortgage_cost_gbp: string;
  annual_tax_liability_gbp: string;
  annual_cash_flow_gbp: string;
  monthly_cash_flow_gbp: string;
  gross_yield_percent: string;
  net_yield_percent: string;
  roce_percent: string;
  cash_on_cash_return_percent: string;
  ltv_percent: string;
  icr_percent: string | null;
  total_sdlt_gbp: string;
  total_acquisition_cost_gbp: string;
  total_cash_deployed_gbp: string;
}

/** Mirrors SDLTBandResultResponse — one SDLT band's contribution. */
export interface SDLTBandResult {
  band_lower: string;
  band_upper: string | null;
  rate: string;
  taxable_in_band: string;
  tax_in_band: string;
}

/**
 * Mirrors SnapshotIntermediatesResponse — all calculation intermediates.
 * Included in SnapshotFull for audit and explainability.
 * void_rate_decimal_applied is a fraction string at native Decimal precision.
 * Nullable tax fields are null for the pathway that did not apply.
 */
export interface SnapshotIntermediates {
  void_rate_decimal_applied: string;
  gross_annual_rent_gbp: string;
  effective_annual_rent_gbp: string;
  loan_amount_gbp: string;
  ltv_percent: string;
  monthly_mortgage_payment_gbp: string;
  annual_mortgage_cost_gbp: string;
  annual_mortgage_interest_gbp: string;
  letting_agent_annual_gbp: string;
  letting_agent_vat_rate_applied: string;
  annual_maintenance_reserve_gbp: string;
  total_operating_costs_annual_gbp: string;
  net_operating_income_gbp: string;
  sdlt_band_breakdown: SDLTBandResult[];
  sdlt_base_gbp: string;
  sdlt_surcharge_gbp: string;
  sdlt_surcharge_rate_applied: string;
  total_sdlt_gbp: string;
  total_acquisition_cost_gbp: string;
  total_cash_deployed_gbp: string;
  stressed_annual_interest_gbp: string;
  stress_test_rate_applied_percent: string;
  taxable_income_or_profit_gbp: string;
  income_tax_gross_gbp: string | null;
  mortgage_interest_tax_credit_gbp: string | null;
  corporation_tax_gross_gbp: string | null;
  annual_tax_liability_gbp: string;
  pre_tax_annual_cash_flow_gbp: string;
  section_24_applies: boolean;
}

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

/**
 * Mirrors SnapshotSummaryResponse — DISPLAY level.
 * Root + outputs + risk flags + warnings. No intermediates.
 * Returned by GET /api/v1/snapshots/{id}/ and embedded in CalculationSuccess.
 */
export interface SnapshotSummary {
  id: string;
  deal_id: string;
  engine_version: string;
  calculated_at: string;
  is_superseded: boolean;
  outputs: SnapshotOutputs;
  risk_flags: RiskFlag[];
  validation_warnings: ValidationWarning[];
}

/**
 * Mirrors SnapshotFullResponse — FULL level.
 * Root + outputs + risk flags + warnings + intermediates (including
 * sdlt_band_breakdown as ordered array).
 * Returned by GET /api/v1/snapshots/{id}/full/.
 */
export interface SnapshotFull extends SnapshotSummary {
  intermediates: SnapshotIntermediates;
}

/**
 * Mirrors SnapshotHistoryEntryResponse — SUMMARY level for history lists.
 * Key metrics and flag counts only. No full outputs.
 * Returned by GET /api/v1/snapshots/?deal_id={id}.
 */
export interface SnapshotHistoryEntry {
  id: string;
  deal_id: string;
  engine_version: string;
  calculated_at: string;
  is_superseded: boolean;
  risk_flag_count_high: number;
  risk_flag_count_medium: number;
  risk_flag_count_info: number;
  annual_cash_flow_gbp: string;
  gross_yield_percent: string;
}
