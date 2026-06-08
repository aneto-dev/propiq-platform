/**
 * Deal TypeScript types — mirror of backend app/api/v1/schemas/deal.py.
 *
 * All UUIDs are strings. Timestamps are ISO 8601 strings.
 * Decimal fields in DealWorkingInputs are serialised as JSON strings
 * (Pydantic v2 Decimal → string, e.g. "200000.50"). Monetary fields in DealSummaryResponse
 * are explicit strings (MoneyStr) per backend schema.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.2.
 */

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export type DealStatus =
  | "DRAFT"
  | "ANALYSED"
  | "OFFER_SUBMITTED"
  | "PURCHASED"
  | "HELD"
  | "EXITED"
  | "ARCHIVED";

export type MortgageType = "INTEREST_ONLY" | "REPAYMENT";

export type OwnershipStructure = "INDIVIDUAL" | "LIMITED_COMPANY";

export type IncomeTaxBand = "BASIC_RATE" | "HIGHER_RATE" | "ADDITIONAL_RATE";

// ---------------------------------------------------------------------------
// Nested types
// ---------------------------------------------------------------------------

/**
 * Mirrors DealWorkingInputsSchema.
 *
 * All fields are optional/nullable — a DRAFT deal may have incomplete inputs.
 * Decimal fields (Python Decimal) are serialised as JSON strings by Pydantic v2,
 * e.g. "200000.50". mortgage_term_years is a Python int and remains a number.
 */
export interface DealWorkingInputs {
  purchase_price: string | null;
  monthly_rent: string | null;
  deposit_amount: string | null;
  mortgage_interest_rate: string | null;
  mortgage_term_years: number | null;
  mortgage_type: MortgageType | null;
  ownership_structure: OwnershipStructure | null;
  income_tax_band: IncomeTaxBand | null;
  is_additional_dwelling: boolean | null;
  void_rate_percent: string | null;
  letting_agent_fee_percent: string | null;
  maintenance_reserve_percent: string | null;
  landlord_insurance_annual: string | null;
  purchase_legal_costs: string | null;
  refurbishment_cost: string | null;
  annual_service_charge: string | null;
  annual_ground_rent: string | null;
  annual_accountancy_cost: string | null;
}

// ---------------------------------------------------------------------------
// Request types
// ---------------------------------------------------------------------------

/**
 * PATCH /api/v1/deals/{id}/inputs request body.
 * Mirrors UpdateWorkingInputsRequest — all fields optional.
 */
export type UpdateWorkingInputsRequest = Partial<DealWorkingInputs>;

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

/**
 * Mirrors DealResponse — full deal with working inputs.
 * Returned by GET /api/v1/deals/{id}/ and POST /api/v1/deals/.
 */
export interface Deal {
  id: string;
  user_id: string;
  property_id: string;
  label: string;
  status: DealStatus;
  investor_profile_id: string | null;
  latest_snapshot_id: string | null;
  working_inputs: DealWorkingInputs;
  created_at: string | null;
  updated_at: string | null;
}

/**
 * Mirrors DealSummaryResponse — lightweight deal for list views.
 * Returned by GET /api/v1/deals/.
 * Monetary snapshot fields are strings (MoneyStr) to avoid float precision loss.
 */
export interface DealSummary {
  id: string;
  label: string;
  status: DealStatus;
  property_id: string;
  latest_snapshot_id: string | null;
  created_at: string;
  updated_at: string;
  latest_snapshot_cash_flow_gbp: string | null;
  latest_snapshot_gross_yield: string | null;
  latest_snapshot_calculated_at: string | null;
  latest_snapshot_risk_flag_count_high: number | null;
}
