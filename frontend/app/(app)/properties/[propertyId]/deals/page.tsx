"use client";

import { use, useEffect, useState } from "react";
import Link from "next/link";
import { getDeals } from "@/lib/api/deals";
import { ApiError } from "@/lib/api/client";
import type { DealSummary } from "@/lib/types/deal";
import { Button } from "@/components/ui/Button";
import { DealStatusBadge } from "@/components/deal/DealStatusBadge";

/**
 * Deal list for a property.
 *
 * Fetches all user deals and filters client-side by property_id.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.5.
 */
export default function DealsPage({
  params,
}: {
  params: Promise<{ propertyId: string }>;
}) {
  const { propertyId } = use(params);
  const [deals, setDeals] = useState<DealSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getDeals()
      .then((all) => setDeals(all.filter((d) => d.property_id === propertyId)))
      .catch((err: unknown) => {
        setError(err instanceof ApiError ? "Failed to load deals." : "Unexpected error.");
      })
      .finally(() => setLoading(false));
  }, [propertyId]);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link href="/properties" className="text-sm text-gray-500 hover:text-gray-700">
            ← Properties
          </Link>
          <span className="text-gray-300">/</span>
          <h1 className="text-lg font-semibold text-gray-900">Deals</h1>
        </div>
        <Link href={`/properties/${propertyId}/deals/new`}>
          <Button>New deal</Button>
        </Link>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8">
        <h2 className="text-xl font-semibold text-gray-900 mb-6">Your deals</h2>

        {loading && <p className="text-gray-500 text-sm">Loading…</p>}
        {error && (
          <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-4 py-3">
            {error}
          </p>
        )}

        {!loading && !error && deals.length === 0 && (
          <div className="text-center py-20">
            <p className="text-gray-500 mb-6">No deals yet for this property.</p>
            <Link href={`/properties/${propertyId}/deals/new`}>
              <Button>Add your first deal</Button>
            </Link>
          </div>
        )}

        {deals.map((deal) => (
          <Link
            key={deal.id}
            href={`/properties/${propertyId}/deals/${deal.id}`}
            className="block bg-white rounded-lg border border-gray-200 px-5 py-4 mb-3 hover:border-blue-300 transition-colors"
          >
            <div className="flex items-center justify-between">
              <p className="font-medium text-gray-900">{deal.label}</p>
              <DealStatusBadge status={deal.status} />
            </div>
            {deal.latest_snapshot_cash_flow_gbp && (
              <p className="text-sm text-gray-500 mt-1">
                Cash flow: £{deal.latest_snapshot_cash_flow_gbp}/yr
              </p>
            )}
          </Link>
        ))}
      </main>
    </div>
  );
}
