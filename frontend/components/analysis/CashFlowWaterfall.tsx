import type { SnapshotOutputs } from "@/lib/types/snapshot";

/**
 * Cash flow waterfall — line-by-line annual cash flow breakdown.
 *
 * Traces the calculation pipeline from gross rent down to annual cash flow:
 *   Gross annual rent
 *   − Void allowance  →  Effective annual rent
 *   − Operating costs →  Net operating income
 *   − Mortgage cost
 *   − Tax liability
 *   = Annual cash flow   (monthly equivalent shown beneath)
 *
 * All values are rendered from snapshot outputs — no derivation.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.6.
 * SERVICE_ARCHITECTURE.md Part 10 — frontend never computes yields or cash flows.
 */

interface CashFlowWaterfallProps {
  outputs: SnapshotOutputs;
}

function gbp(value: string): string {
  const num = parseFloat(value);
  const abs = Math.abs(num).toLocaleString("en-GB", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return num < 0 ? `-£${abs}` : `£${abs}`;
}

interface WaterfallRow {
  label: string;
  value: string;
  indent?: boolean;
  subtotal?: boolean;
  total?: boolean;
  deduction?: boolean;
}

export function CashFlowWaterfall({ outputs }: CashFlowWaterfallProps) {
  const rows: WaterfallRow[] = [
    {
      label: "Gross annual rent",
      value: outputs.gross_annual_rent_gbp,
    },
    {
      label: "Effective annual rent (after void allowance)",
      value: outputs.effective_annual_rent_gbp,
      indent: true,
      subtotal: true,
    },
    {
      label: "Operating costs",
      value: outputs.total_operating_costs_annual_gbp,
      deduction: true,
    },
    {
      label: "Net operating income",
      value: outputs.net_operating_income_gbp,
      subtotal: true,
    },
    {
      label: "Mortgage cost",
      value: outputs.annual_mortgage_cost_gbp,
      deduction: true,
    },
    {
      label: "Estimated tax liability",
      value: outputs.annual_tax_liability_gbp,
      deduction: true,
    },
  ];

  const annualCashFlow = parseFloat(outputs.annual_cash_flow_gbp);
  const isNegative = annualCashFlow < 0;

  return (
    <div className="space-y-1">
      {rows.map((row) => (
        <div
          key={row.label}
          className={[
            "flex items-baseline justify-between py-1.5",
            row.subtotal
              ? "border-t border-gray-200 mt-1 pt-2"
              : "",
            row.indent ? "pl-4" : "",
          ]
            .filter(Boolean)
            .join(" ")}
        >
          <span
            className={`text-sm ${row.subtotal ? "font-medium text-gray-700" : "text-gray-600"}`}
          >
            {row.deduction ? "− " : ""}{row.label}
          </span>
          <span className={`text-sm tabular-nums ${row.subtotal ? "font-medium text-gray-900" : "text-gray-700"}`}>
            {row.deduction ? `(${gbp(row.value)})` : gbp(row.value)}
          </span>
        </div>
      ))}

      {/* Annual cash flow — total line */}
      <div className="border-t-2 border-gray-800 mt-2 pt-3 flex items-baseline justify-between">
        <span className="text-sm font-semibold text-gray-900">
          Annual cash flow
        </span>
        <span
          className={`text-base font-bold tabular-nums ${isNegative ? "text-red-600" : "text-green-700"}`}
        >
          {gbp(outputs.annual_cash_flow_gbp)}
        </span>
      </div>
      <div className="flex items-baseline justify-between">
        <span className="text-xs text-gray-500">Monthly equivalent</span>
        <span
          className={`text-sm font-medium tabular-nums ${isNegative ? "text-red-600" : "text-green-700"}`}
        >
          {gbp(outputs.monthly_cash_flow_gbp)}/mo
        </span>
      </div>
    </div>
  );
}
