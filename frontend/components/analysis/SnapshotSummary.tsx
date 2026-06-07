import type { SnapshotFull } from "@/lib/types/snapshot";
import { CashFlowWaterfall } from "@/components/analysis/CashFlowWaterfall";
import { YieldMetrics } from "@/components/analysis/YieldMetrics";
import { SDLTBreakdown } from "@/components/analysis/SDLTBreakdown";
import { AcquisitionCostBreakdown } from "@/components/analysis/AcquisitionCostBreakdown";
import { RiskFlagList } from "@/components/analysis/RiskFlagList";
import type { DealWorkingInputs } from "@/lib/types/deal";

/**
 * Snapshot summary — the primary analysis output component.
 *
 * Composes all analysis sub-components from a single SnapshotFull source.
 * Receives the deal's working inputs for AcquisitionCostBreakdown line items
 * (purchase_price, legal_costs, refurbishment_cost) which are not stored
 * in the snapshot itself.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.6.
 * SERVICE_ARCHITECTURE.md Part 10 — snapshot-first rendering; no derived values.
 */

interface SnapshotSummaryProps {
  snapshot: SnapshotFull;
  workingInputs: DealWorkingInputs;
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString("en-GB", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function Section({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="bg-white rounded-xl border border-gray-200 p-6">
      <h3 className="text-sm font-semibold text-gray-500 uppercase tracking-wide mb-5">
        {title}
      </h3>
      {children}
    </section>
  );
}

export function SnapshotSummary({ snapshot, workingInputs }: SnapshotSummaryProps) {
  const { outputs, risk_flags, intermediates } = snapshot;

  return (
    <div className="space-y-6">
      {/* Metadata */}
      {snapshot.is_superseded && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg px-4 py-3 text-sm text-amber-800">
          This snapshot has been superseded by a later calculation.
        </div>
      )}
      <p className="text-xs text-gray-400">
        Calculated {formatDate(snapshot.calculated_at)} · Engine v{snapshot.engine_version}
      </p>

      {/* Cash flow waterfall */}
      <Section title="Cash flow">
        <CashFlowWaterfall outputs={outputs} />
      </Section>

      {/* Yield & return metrics */}
      <Section title="Yields & returns">
        <YieldMetrics outputs={outputs} />
      </Section>

      {/* Acquisition cost breakdown */}
      <Section title="Acquisition costs">
        <AcquisitionCostBreakdown
          outputs={outputs}
          intermediates={intermediates}
          workingInputs={workingInputs}
        />
      </Section>

      {/* SDLT breakdown */}
      <Section title="SDLT breakdown">
        <SDLTBreakdown intermediates={intermediates} />
      </Section>

      {/* Risk flags */}
      <Section title={`Risk flags (${risk_flags.length})`}>
        <RiskFlagList flags={risk_flags} />
      </Section>
    </div>
  );
}
