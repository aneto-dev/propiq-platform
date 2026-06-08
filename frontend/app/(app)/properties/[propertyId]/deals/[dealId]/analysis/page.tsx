"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { getDeal } from "@/lib/api/deals";
import { getSnapshotFull } from "@/lib/api/snapshots";
import { recalculate } from "@/lib/api/calculations";
import { ApiError } from "@/lib/api/client";
import type { Deal } from "@/lib/types/deal";
import type { SnapshotFull } from "@/lib/types/snapshot";
import { DealStatusBadge } from "@/components/deal/DealStatusBadge";
import { SnapshotSummary } from "@/components/analysis/SnapshotSummary";
import { Button } from "@/components/ui/Button";

/**
 * Deal analysis page — renders the snapshot summary for a deal.
 *
 * Loading strategy (resolved in pre-implementation audit):
 *   1. GET /api/v1/deals/{dealId}        → deal.latest_snapshot_id + working_inputs
 *   2. GET /api/v1/snapshots/{id}/full   → SnapshotFull (outputs + intermediates)
 *
 * The full endpoint is required because SDLTBreakdown and AcquisitionCostBreakdown
 * consume sdlt_band_breakdown and loan_amount_gbp from SnapshotIntermediates,
 * which are absent from the display-level summary response.
 *
 * If the deal has no snapshot yet (DRAFT), an empty state prompts the user
 * to return to the deal workspace and run the analysis.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.6 + Phase 9.
 * SERVICE_ARCHITECTURE.md Part 10 — snapshot-first rendering.
 */
export default function AnalysisPage({
  params,
}: {
  params: Promise<{ propertyId: string; dealId: string }>;
}) {
  const { propertyId, dealId } = use(params);
  const router = useRouter();

  const [deal, setDeal] = useState<Deal | null>(null);
  const [snapshot, setSnapshot] = useState<SnapshotFull | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [recalculating, setRecalculating] = useState(false);
  const [recalcError, setRecalcError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const d = await getDeal(dealId);
        setDeal(d);

        if (!d.latest_snapshot_id) {
          // DRAFT deal — no snapshot yet
          return;
        }

        const snap = await getSnapshotFull(d.latest_snapshot_id);
        setSnapshot(snap);
      } catch (err: unknown) {
        setError(
          err instanceof ApiError ? "Failed to load analysis." : "Unexpected error.",
        );
      } finally {
        setLoading(false);
      }
    }
    load();
  }, [dealId]);

  async function handleRecalculate() {
    setRecalculating(true);
    setRecalcError(null);
    try {
      await recalculate({ deal_id: dealId });
      // Reload the page — the deal's latest_snapshot_id will have changed
      router.refresh();
      // Re-run the load effect by resetting state
      setLoading(true);
      setSnapshot(null);
      const d = await getDeal(dealId);
      setDeal(d);
      if (d.latest_snapshot_id) {
        const snap = await getSnapshotFull(d.latest_snapshot_id);
        setSnapshot(snap);
      }
    } catch (err: unknown) {
      const body = (err as { body?: { detail?: string } })?.body;
      setRecalcError(body?.detail ?? "Recalculation failed. Check your inputs.");
    } finally {
      setRecalculating(false);
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <div className="flex items-center gap-3 text-sm text-gray-500 mb-1">
          <Link href="/properties" className="hover:text-gray-700">
            Properties
          </Link>
          <span className="text-gray-300">/</span>
          <Link
            href={`/properties/${propertyId}/deals`}
            className="hover:text-gray-700"
          >
            Deals
          </Link>
          <span className="text-gray-300">/</span>
          <Link
            href={`/properties/${propertyId}/deals/${dealId}`}
            className="hover:text-gray-700"
          >
            {deal?.label ?? "Deal"}
          </Link>
        </div>
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold text-gray-900">Analysis</h1>
          {deal && <DealStatusBadge status={deal.status} />}
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8">
        {loading && <p className="text-gray-500 text-sm">Loading analysis…</p>}

        {error && (
          <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-4 py-3">
            {error}
          </p>
        )}

        {!loading && !error && deal && !snapshot && (
          <div className="text-center py-20">
            <p className="text-gray-500 mb-6">
              No analysis yet. Return to the deal and click &ldquo;Analyse this deal&rdquo;.
            </p>
            <Link
              href={`/properties/${propertyId}/deals/${dealId}`}
              className="text-sm text-blue-600 hover:underline"
            >
              ← Back to deal workspace
            </Link>
          </div>
        )}

        {deal && snapshot && (
          <>
            <div className="mb-6 flex items-center justify-between flex-wrap gap-3">
              <Link
                href={`/properties/${propertyId}/deals/${dealId}`}
                className="text-sm text-gray-500 hover:text-gray-700"
              >
                ← Back to deal workspace
              </Link>
              <div className="flex items-center gap-3">
                <Link
                  href={`/properties/${propertyId}/deals/${dealId}/history`}
                  className="text-sm text-gray-500 hover:text-gray-700"
                >
                  View history
                </Link>
                {deal.status !== "ARCHIVED" && (
                  <Button
                    variant="secondary"
                    onClick={handleRecalculate}
                    disabled={recalculating}
                  >
                    {recalculating ? "Recalculating…" : "Recalculate"}
                  </Button>
                )}
              </div>
            </div>

            {recalcError && (
              <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2 mb-4">
                {recalcError}
              </p>
            )}

            <SnapshotSummary
              snapshot={snapshot}
              workingInputs={deal.working_inputs}
            />
          </>
        )}
      </main>
    </div>
  );
}
