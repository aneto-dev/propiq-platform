"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { getDeal } from "@/lib/api/deals";
import { getSnapshotFull } from "@/lib/api/snapshots";
import { ApiError } from "@/lib/api/client";
import type { Deal } from "@/lib/types/deal";
import type { SnapshotFull } from "@/lib/types/snapshot";
import { DealStatusBadge } from "@/components/deal/DealStatusBadge";
import { SnapshotSummary } from "@/components/analysis/SnapshotSummary";

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
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.6.
 * SERVICE_ARCHITECTURE.md Part 10 — snapshot-first rendering.
 */
export default function AnalysisPage({
  params,
}: {
  params: Promise<{ propertyId: string; dealId: string }>;
}) {
  const { propertyId, dealId } = use(params);

  const [deal, setDeal] = useState<Deal | null>(null);
  const [snapshot, setSnapshot] = useState<SnapshotFull | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

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
            <div className="mb-6 flex items-center justify-between">
              <Link
                href={`/properties/${propertyId}/deals/${dealId}`}
                className="text-sm text-gray-500 hover:text-gray-700"
              >
                ← Back to deal workspace
              </Link>
            </div>
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
