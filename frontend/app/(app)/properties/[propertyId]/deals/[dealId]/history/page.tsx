"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { getSnapshotHistory } from "@/lib/api/snapshots";
import { getDeal } from "@/lib/api/deals";
import { ApiError } from "@/lib/api/client";
import type { Deal } from "@/lib/types/deal";
import type { SnapshotHistoryEntry } from "@/lib/types/snapshot";
import { DealStatusBadge } from "@/components/deal/DealStatusBadge";

/**
 * Snapshot history page — all analysis runs for a deal.
 *
 * Lists every snapshot for this deal in reverse-chronological order
 * (most recent first). Each row shows the key metrics and links to the
 * full analysis view for that snapshot.
 *
 * Superseded snapshots are shown with a visual indicator; the current
 * (non-superseded) analysis is highlighted.
 *
 * API:
 *   GET /api/v1/deals/{dealId}                    → deal label + status
 *   GET /api/v1/snapshots/?deal_id={dealId}       → SnapshotHistoryEntry[]
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Phase 9 — snapshot history list UI.
 */
export default function SnapshotHistoryPage({
  params,
}: {
  params: Promise<{ propertyId: string; dealId: string }>;
}) {
  const { propertyId, dealId } = use(params);

  const [deal, setDeal] = useState<Deal | null>(null);
  const [history, setHistory] = useState<SnapshotHistoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getDeal(dealId), getSnapshotHistory(dealId)])
      .then(([d, entries]) => {
        setDeal(d);
        setHistory(entries);
      })
      .catch((err: unknown) => {
        setError(
          err instanceof ApiError
            ? "Failed to load history."
            : "Unexpected error.",
        );
      })
      .finally(() => setLoading(false));
  }, [dealId]);

  function formatDate(iso: string) {
    return new Date(iso).toLocaleString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  }

  function gbpPerYear(value: string) {
    const n = parseFloat(value);
    const abs = Math.abs(n).toLocaleString("en-GB", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return n < 0 ? `-£${abs}/yr` : `£${abs}/yr`;
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
          <h1 className="text-lg font-semibold text-gray-900">
            Analysis history
          </h1>
          {deal && <DealStatusBadge status={deal.status} />}
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8">
        {loading && (
          <p className="text-sm text-gray-500">Loading history…</p>
        )}

        {error && (
          <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-4 py-3">
            {error}
          </p>
        )}

        {!loading && !error && history.length === 0 && (
          <div className="text-center py-16">
            <p className="text-gray-500 mb-4">No analyses run yet.</p>
            <Link
              href={`/properties/${propertyId}/deals/${dealId}`}
              className="text-sm text-blue-600 hover:underline"
            >
              ← Back to deal workspace
            </Link>
          </div>
        )}

        {!loading && !error && history.length > 0 && (
          <div className="space-y-3">
            {history.map((entry, index) => {
              const isCurrent = !entry.is_superseded;
              const cashFlow = gbpPerYear(entry.annual_cash_flow_gbp);
              const isNegative = parseFloat(entry.annual_cash_flow_gbp) < 0;

              return (
                <Link
                  key={entry.id}
                  href={`/properties/${propertyId}/deals/${dealId}/analysis`}
                  className={[
                    "block rounded-lg border px-5 py-4 transition-colors",
                    isCurrent
                      ? "bg-white border-blue-200 hover:border-blue-400"
                      : "bg-gray-50 border-gray-200 hover:border-gray-300",
                  ].join(" ")}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="flex items-center gap-2 mb-1">
                        {isCurrent ? (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-blue-100 text-blue-700">
                            Current
                          </span>
                        ) : (
                          <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-500">
                            Superseded
                          </span>
                        )}
                        {index === 0 && history.length > 1 && (
                          <span className="text-xs text-gray-400">
                            Latest run
                          </span>
                        )}
                      </div>
                      <p className="text-xs text-gray-500">
                        {formatDate(entry.calculated_at)} · Engine v
                        {entry.engine_version}
                      </p>
                    </div>

                    <div className="text-right shrink-0">
                      <p
                        className={`text-sm font-medium tabular-nums ${
                          isNegative ? "text-red-600" : "text-green-700"
                        }`}
                      >
                        {cashFlow}
                      </p>
                      <p className="text-xs text-gray-400 mt-0.5">
                        Yield: {entry.gross_yield_percent}%
                      </p>
                    </div>
                  </div>

                  {(entry.risk_flag_count_high > 0 ||
                    entry.risk_flag_count_medium > 0) && (
                    <div className="mt-2 flex gap-3 text-xs">
                      {entry.risk_flag_count_high > 0 && (
                        <span className="text-red-600 font-medium">
                          {entry.risk_flag_count_high} HIGH
                        </span>
                      )}
                      {entry.risk_flag_count_medium > 0 && (
                        <span className="text-amber-600">
                          {entry.risk_flag_count_medium} MEDIUM
                        </span>
                      )}
                    </div>
                  )}
                </Link>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
