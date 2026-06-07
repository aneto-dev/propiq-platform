import type { SnapshotOutputs, SnapshotIntermediates } from "@/lib/types/snapshot";
import type { DealWorkingInputs } from "@/lib/types/deal";

/**
 * Acquisition cost breakdown — shows the components of total acquisition cost
 * and total cash deployed.
 *
 * Sources:
 *   - Purchase price, legal costs, refurbishment: DealWorkingInputs (inputs)
 *   - Loan amount: SnapshotIntermediates (intermediates — full endpoint only)
 *   - SDLT total, acquisition total, cash deployed: SnapshotOutputs (summary/full)
 *
 * Requires SnapshotFull for loan_amount_gbp.
 *
 * Formulae (CALCULATION_SPEC.md F-14, F-15):
 *   total_acquisition_cost = purchase_price + total_sdlt + purchase_legal_costs + refurbishment_cost
 *   total_cash_deployed    = deposit_amount  + total_sdlt + purchase_legal_costs + refurbishment_cost
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.6.
 * SERVICE_ARCHITECTURE.md Part 10 — renders API values; no re-computation.
 */

interface AcquisitionCostBreakdownProps {
  outputs: SnapshotOutputs;
  intermediates: SnapshotIntermediates;
  workingInputs: DealWorkingInputs;
}

function gbp(value: string | null | undefined): string {
  if (value === null || value === undefined || value === "") return "—";
  const num = parseFloat(value);
  return `£${Math.abs(num).toLocaleString("en-GB", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

interface CostRow {
  label: string;
  value: string | null | undefined;
  subtotal?: boolean;
  muted?: boolean;
}

export function AcquisitionCostBreakdown({
  outputs,
  intermediates,
  workingInputs,
}: AcquisitionCostBreakdownProps) {
  const acquisitionRows: CostRow[] = [
    { label: "Purchase price", value: workingInputs.purchase_price },
    { label: "SDLT", value: outputs.total_sdlt_gbp },
    {
      label: "Legal costs",
      value: workingInputs.purchase_legal_costs,
      muted: !workingInputs.purchase_legal_costs,
    },
    {
      label: "Refurbishment",
      value: workingInputs.refurbishment_cost,
      muted: !workingInputs.refurbishment_cost,
    },
    {
      label: "Total acquisition cost",
      value: outputs.total_acquisition_cost_gbp,
      subtotal: true,
    },
  ];

  const deployedRows: CostRow[] = [
    { label: "Deposit", value: workingInputs.deposit_amount },
    { label: "SDLT", value: outputs.total_sdlt_gbp },
    {
      label: "Legal costs",
      value: workingInputs.purchase_legal_costs,
      muted: !workingInputs.purchase_legal_costs,
    },
    {
      label: "Refurbishment",
      value: workingInputs.refurbishment_cost,
      muted: !workingInputs.refurbishment_cost,
    },
    {
      label: "Total cash deployed",
      value: outputs.total_cash_deployed_gbp,
      subtotal: true,
    },
  ];

  function renderRows(rows: CostRow[]) {
    return rows.map((row) => (
      <div
        key={row.label}
        className={[
          "flex items-baseline justify-between py-1.5",
          row.subtotal ? "border-t border-gray-300 mt-1 pt-2 font-semibold" : "",
        ]
          .filter(Boolean)
          .join(" ")}
      >
        <span
          className={`text-sm ${row.subtotal ? "text-gray-900" : row.muted ? "text-gray-400" : "text-gray-600"}`}
        >
          {row.label}
          {row.muted ? " (not entered)" : ""}
        </span>
        <span
          className={`text-sm tabular-nums ${row.subtotal ? "text-gray-900 font-semibold" : row.muted ? "text-gray-400" : "text-gray-700"}`}
        >
          {gbp(row.value)}
        </span>
      </div>
    ));
  }

  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 gap-8">
      {/* Acquisition cost */}
      <div>
        <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Acquisition cost
        </h4>
        {renderRows(acquisitionRows)}
      </div>

      {/* Cash deployed */}
      <div>
        <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-3">
          Cash deployed
        </h4>
        {renderRows(deployedRows)}
        <div className="mt-3 pt-3 border-t border-gray-100">
          <div className="flex items-baseline justify-between">
            <span className="text-xs text-gray-500">Loan amount</span>
            <span className="text-sm tabular-nums text-gray-600">
              {gbp(intermediates.loan_amount_gbp)}
            </span>
          </div>
          <div className="flex items-baseline justify-between mt-1">
            <span className="text-xs text-gray-500">LTV</span>
            <span className="text-sm tabular-nums text-gray-600">
              {outputs.ltv_percent}%
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}
