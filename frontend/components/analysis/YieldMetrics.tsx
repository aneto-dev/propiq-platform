import type { SnapshotOutputs } from "@/lib/types/snapshot";

/**
 * Yield and return metrics — key percentage outputs from the snapshot.
 *
 * Displays: gross yield, net yield, cash-on-cash return, ROCE, LTV, ICR.
 * icr_percent is null for cash purchases (no mortgage); rendered as N/A.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.6.
 * SERVICE_ARCHITECTURE.md Part 10 — renders API values; no derived logic.
 */

interface YieldMetricsProps {
  outputs: SnapshotOutputs;
}

interface Metric {
  label: string;
  value: string | null;
  suffix: string;
  note?: string;
}

export function YieldMetrics({ outputs }: YieldMetricsProps) {
  const metrics: Metric[] = [
    {
      label: "Gross yield",
      value: outputs.gross_yield_percent,
      suffix: "%",
    },
    {
      label: "Net yield",
      value: outputs.net_yield_percent,
      suffix: "%",
    },
    {
      label: "Cash-on-cash return",
      value: outputs.cash_on_cash_return_percent,
      suffix: "%",
    },
    {
      label: "ROCE",
      value: outputs.roce_percent,
      suffix: "%",
    },
    {
      label: "LTV",
      value: outputs.ltv_percent,
      suffix: "%",
    },
    {
      label: "ICR (stressed)",
      value: outputs.icr_percent,
      suffix: "%",
      note: outputs.icr_percent === null ? "N/A — cash purchase" : undefined,
    },
  ];

  return (
    <dl className="grid grid-cols-2 sm:grid-cols-3 gap-4">
      {metrics.map((m) => (
        <div
          key={m.label}
          className="bg-gray-50 rounded-lg px-4 py-3 border border-gray-100"
        >
          <dt className="text-xs text-gray-500 mb-1">{m.label}</dt>
          <dd className="text-xl font-semibold text-gray-900 tabular-nums">
            {m.note ?? (m.value !== null ? `${m.value}${m.suffix}` : "—")}
          </dd>
        </div>
      ))}
    </dl>
  );
}
