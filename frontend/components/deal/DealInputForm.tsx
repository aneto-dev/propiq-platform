"use client";

import { useState } from "react";
import { updateWorkingInputs } from "@/lib/api/deals";
import { apiRequest } from "@/lib/api/client";
import type { Deal, DealWorkingInputs } from "@/lib/types/deal";
import type { Property } from "@/lib/types/property";
import type { CalculationSuccess } from "@/lib/types/calculation";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";

/**
 * Deal input form — all required and optional calculation inputs.
 *
 * Auto-saves each field to the backend on blur via
 * PATCH /api/v1/deals/{id}/inputs (partial update, DRAFT and ANALYSED only).
 *
 * "Analyse this deal" assembles the full CalculationRequest (combining working
 * inputs with property-level fields) and calls POST /api/v1/calculations/.
 * On success the onAnalysed callback receives the snapshot_id so the parent
 * can redirect to the analysis page.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.5.
 */

interface DealInputFormProps {
  deal: Deal;
  property: Property;
  onAnalysed: (snapshotId: string) => void;
}

// Internal form state — all values as strings for controlled inputs.
type FormValues = {
  purchase_price: string;
  monthly_rent: string;
  deposit_amount: string;
  mortgage_interest_rate: string;
  mortgage_term_years: string;
  mortgage_type: string;
  ownership_structure: string;
  income_tax_band: string;
  is_additional_dwelling: string;
  void_rate_percent: string;
  letting_agent_fee_percent: string;
  maintenance_reserve_percent: string;
  landlord_insurance_annual: string;
  purchase_legal_costs: string;
  refurbishment_cost: string;
  annual_service_charge: string;
  annual_ground_rent: string;
  annual_accountancy_cost: string;
};

function fromWorkingInputs(wi: DealWorkingInputs): FormValues {
  return {
    purchase_price: wi.purchase_price ?? "",
    monthly_rent: wi.monthly_rent ?? "",
    deposit_amount: wi.deposit_amount ?? "",
    mortgage_interest_rate: wi.mortgage_interest_rate ?? "",
    mortgage_term_years: wi.mortgage_term_years?.toString() ?? "",
    mortgage_type: wi.mortgage_type ?? "",
    ownership_structure: wi.ownership_structure ?? "",
    income_tax_band: wi.income_tax_band ?? "",
    is_additional_dwelling:
      wi.is_additional_dwelling === null ? "" : String(wi.is_additional_dwelling),
    void_rate_percent: wi.void_rate_percent ?? "",
    letting_agent_fee_percent: wi.letting_agent_fee_percent ?? "",
    maintenance_reserve_percent: wi.maintenance_reserve_percent ?? "",
    landlord_insurance_annual: wi.landlord_insurance_annual ?? "",
    purchase_legal_costs: wi.purchase_legal_costs ?? "",
    refurbishment_cost: wi.refurbishment_cost ?? "",
    annual_service_charge: wi.annual_service_charge ?? "",
    annual_ground_rent: wi.annual_ground_rent ?? "",
    annual_accountancy_cost: wi.annual_accountancy_cost ?? "",
  };
}

// Convert a string form value to the right PATCH body type for each field.
function toUpdateValue(
  field: keyof FormValues,
  value: string,
): DealWorkingInputs[keyof DealWorkingInputs] {
  if (value === "") return null;
  if (field === "mortgage_term_years") return parseInt(value, 10);
  if (field === "is_additional_dwelling") return value === "true";
  return value;
}

export function DealInputForm({ deal, property, onAnalysed }: DealInputFormProps) {
  const [form, setForm] = useState<FormValues>(() =>
    fromWorkingInputs(deal.working_inputs),
  );
  const [analysing, setAnalysing] = useState(false);
  const [calcError, setCalcError] = useState<string | null>(null);

  const isArchived = deal.status === "ARCHIVED";

  function handleChange(field: keyof FormValues, value: string) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  async function handleBlur(field: keyof FormValues) {
    if (isArchived) return;
    const value = form[field];
    const updateValue = toUpdateValue(field, value);
    // Fire-and-forget; silently ignore errors for the vertical slice.
    updateWorkingInputs(deal.id, {
      [field]: updateValue,
    } as Partial<DealWorkingInputs>).catch(() => undefined);
  }

  async function handleAnalyse() {
    setAnalysing(true);
    setCalcError(null);
    try {
      const result = await apiRequest<CalculationSuccess>("/api/v1/calculations/", {
        method: "POST",
        body: JSON.stringify({
          deal_id: deal.id,
          purchase_price: form.purchase_price ? parseFloat(form.purchase_price) : undefined,
          monthly_rent: form.monthly_rent ? parseFloat(form.monthly_rent) : undefined,
          deposit_amount: form.deposit_amount ? parseFloat(form.deposit_amount) : undefined,
          mortgage_interest_rate: form.mortgage_interest_rate
            ? parseFloat(form.mortgage_interest_rate)
            : undefined,
          mortgage_term_years: form.mortgage_term_years
            ? parseInt(form.mortgage_term_years, 10)
            : undefined,
          mortgage_type: form.mortgage_type || undefined,
          ownership_structure: form.ownership_structure || undefined,
          income_tax_band: form.income_tax_band || undefined,
          is_additional_dwelling:
            form.is_additional_dwelling !== ""
              ? form.is_additional_dwelling === "true"
              : undefined,
          property_type: property.property_type,
          tenure: property.tenure,
          property_country: "ENGLAND",
          postcode: property.postcode,
        }),
      });
      onAnalysed(result.snapshot_id);
    } catch (err: unknown) {
      const body = (err as { body?: { detail?: string; field_errors?: unknown[] } })?.body;
      if (body?.field_errors) {
        setCalcError("Validation failed — check required fields.");
      } else {
        setCalcError(body?.detail ?? "Calculation failed. Check your inputs.");
      }
    } finally {
      setAnalysing(false);
    }
  }

  // ---------------------------------------------------------------------------
  // Input helpers
  // ---------------------------------------------------------------------------

  function textInput(
    field: keyof FormValues,
    label: string,
    placeholder?: string,
    required?: boolean,
  ) {
    return (
      <Input
        id={field}
        label={label}
        placeholder={placeholder}
        value={form[field]}
        onChange={(e) => handleChange(field, e.target.value)}
        onBlur={() => handleBlur(field)}
        disabled={isArchived}
        required={required}
      />
    );
  }

  function selectInput(
    field: keyof FormValues,
    label: string,
    options: { value: string; label: string }[],
    required?: boolean,
  ) {
    return (
      <Select
        id={field}
        label={label}
        value={form[field]}
        onChange={(e) => {
          handleChange(field, e.target.value);
          handleBlur(field);
        }}
        disabled={isArchived}
        required={required}
        options={options}
      />
    );
  }

  return (
    <div className="space-y-8">
      {/* Required inputs */}
      <section>
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">
          Deal financials
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {textInput("purchase_price", "Purchase price (£)", "e.g. 200000", true)}
          {textInput("monthly_rent", "Monthly rent (£)", "e.g. 950", true)}
          {textInput("deposit_amount", "Deposit (£)", "e.g. 50000", true)}
        </div>
      </section>

      <section>
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">
          Mortgage
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {selectInput("mortgage_type", "Mortgage type", [
            { value: "", label: "Select…" },
            { value: "INTEREST_ONLY", label: "Interest only" },
            { value: "REPAYMENT", label: "Repayment" },
          ], true)}
          {textInput("mortgage_interest_rate", "Interest rate (%)", "e.g. 4.75", true)}
          {textInput("mortgage_term_years", "Term (years)", "e.g. 25", true)}
        </div>
      </section>

      <section>
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-4">
          Ownership
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {selectInput("ownership_structure", "Ownership structure", [
            { value: "", label: "Select…" },
            { value: "INDIVIDUAL", label: "Individual" },
            { value: "LIMITED_COMPANY", label: "Limited company" },
          ], true)}
          {form.ownership_structure === "INDIVIDUAL" &&
            selectInput("income_tax_band", "Income tax band", [
              { value: "", label: "Select…" },
              { value: "BASIC_RATE", label: "Basic rate (20%)" },
              { value: "HIGHER_RATE", label: "Higher rate (40%)" },
              { value: "ADDITIONAL_RATE", label: "Additional rate (45%)" },
            ], true)}
          {selectInput("is_additional_dwelling", "Additional dwelling surcharge", [
            { value: "", label: "Select…" },
            { value: "true", label: "Yes" },
            { value: "false", label: "No" },
          ], true)}
        </div>
      </section>

      {/* Optional inputs */}
      <section>
        <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-1">
          Optional costs &amp; rates
        </h3>
        <p className="text-xs text-gray-400 mb-4">
          Leave blank to use platform defaults.
        </p>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {textInput("void_rate_percent", "Void rate (%)", "e.g. 3.6")}
          {textInput("letting_agent_fee_percent", "Letting agent fee (%)", "e.g. 10")}
          {textInput("maintenance_reserve_percent", "Maintenance reserve (%)", "e.g. 0.5")}
          {textInput("landlord_insurance_annual", "Landlord insurance (£/yr)", "e.g. 300")}
          {textInput("purchase_legal_costs", "Purchase legal costs (£)", "e.g. 1500")}
          {textInput("refurbishment_cost", "Refurbishment cost (£)", "e.g. 0")}
          {textInput("annual_service_charge", "Service charge (£/yr)", "e.g. 0")}
          {textInput("annual_ground_rent", "Ground rent (£/yr)", "e.g. 0")}
          {textInput("annual_accountancy_cost", "Accountancy cost (£/yr)", "e.g. 200")}
        </div>
      </section>

      {/* Analyse */}
      {!isArchived && (
        <div className="pt-2 border-t border-gray-100">
          {calcError && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2 mb-4">
              {calcError}
            </p>
          )}
          <Button onClick={handleAnalyse} disabled={analysing}>
            {analysing ? "Analysing…" : "Analyse this deal"}
          </Button>
        </div>
      )}
    </div>
  );
}
