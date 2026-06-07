/**
 * Calculation TypeScript types — mirror of backend app/api/v1/schemas/calculation.py.
 *
 * Numeric input fields (Decimal in Python) are numbers in JSON.
 * Monetary response fields from SnapshotSummaryResponse are strings (MoneyStr).
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.2.
 */

import type { SnapshotSummary } from "@/lib/types/snapshot";

// ---------------------------------------------------------------------------
// Enums (required by CalculationRequest)
// ---------------------------------------------------------------------------

export type MortgageType = "INTEREST_ONLY" | "REPAYMENT";

export type OwnershipStructure = "INDIVIDUAL" | "LIMITED_COMPANY";

export type IncomeTaxBand = "BASIC_RATE" | "HIGHER_RATE" | "ADDITIONAL_RATE";

export type PropertyType = "RESIDENTIAL_SINGLE_LET";

export type Tenure = "FREEHOLD" | "LEASEHOLD";

export type PropertyCountry = "ENGLAND";

export type DealStatus = "DRAFT" | "ANALYSED" | "ARCHIVED";

// ---------------------------------------------------------------------------
// Request types
// ---------------------------------------------------------------------------

/**
 * POST /api/v1/calculations/ request body.
 * Mirrors CalculationRequest. Numeric fields are numbers (Decimal → JSON number).
 */
export interface CalculationRequest {
  deal_id: string;
  calculation_date?: string | null;
  // Required inputs
  purchase_price: number;
  monthly_rent: number;
  deposit_amount: number;
  mortgage_interest_rate: number;
  mortgage_term_years: number;
  mortgage_type: MortgageType;
  ownership_structure: OwnershipStructure;
  income_tax_band?: IncomeTaxBand | null;
  is_additional_dwelling: boolean;
  property_type: PropertyType;
  tenure: Tenure;
  property_country: PropertyCountry;
  postcode: string;
  // Optional inputs — absent means use config default
  void_rate_percent?: number | null;
  letting_agent_fee_percent?: number | null;
  maintenance_reserve_percent?: number | null;
  landlord_insurance_annual?: number | null;
  purchase_legal_costs?: number | null;
  refurbishment_cost?: number | null;
  annual_service_charge?: number | null;
  annual_ground_rent?: number | null;
  annual_accountancy_cost?: number | null;
  lease_years_remaining?: number | null;
}

/**
 * POST /api/v1/calculations/recalculate request body.
 * Mirrors RecalculateRequest — uses stored working inputs, no inputs in body.
 */
export interface RecalculateRequest {
  deal_id: string;
  calculation_date?: string | null;
}

/**
 * POST /api/v1/calculations/reproduce-original request body.
 * Mirrors ReproduceOriginalRequest.
 */
export interface ReproduceOriginalRequest {
  source_snapshot_id: string;
  calculation_date?: string | null;
}

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

/**
 * Mirrors CalculationSuccessResponse — successful calculation result.
 * Returned by all three calculation endpoints on success (HTTP 201).
 */
export interface CalculationSuccess {
  snapshot_id: string;
  deal_status: DealStatus;
  snapshot: SnapshotSummary;
}

/** One structured field validation error from the engine. */
export interface FieldError {
  rule_code: string;
  field: string;
  message: string;
}

/**
 * Mirrors CalculationValidationFailureResponse — engine rejected inputs.
 * Returned as HTTP 422 body when engine validation fails.
 */
export interface CalculationValidationFailure {
  detail: string;
  field_errors: FieldError[];
}
