"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getDeal } from "@/lib/api/deals";
import { getProperty } from "@/lib/api/properties";
import { ApiError } from "@/lib/api/client";
import type { Deal } from "@/lib/types/deal";
import type { Property } from "@/lib/types/property";
import { DealStatusBadge } from "@/components/deal/DealStatusBadge";
import { DealInputForm } from "@/components/deal/DealInputForm";

/**
 * Deal workspace — the primary analysis page.
 *
 * Loads the deal and its parent property, then renders DealInputForm.
 * The page header shows the deal label and status badge per the roadmap:
 * "The user is working on a deal, not running a calculation."
 *
 * After a successful calculation, redirects to the analysis page
 * (/properties/[propertyId]/deals/[dealId]/analysis — added in Commit 7.6).
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.5.
 */
export default function DealWorkspacePage({
  params,
}: {
  params: Promise<{ propertyId: string; dealId: string }>;
}) {
  const { propertyId, dealId } = use(params);
  const router = useRouter();

  const [deal, setDeal] = useState<Deal | null>(null);
  const [property, setProperty] = useState<Property | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getDeal(dealId), getProperty(propertyId)])
      .then(([d, p]) => {
        setDeal(d);
        setProperty(p);
      })
      .catch((err: unknown) => {
        setError(
          err instanceof ApiError ? "Failed to load deal." : "Unexpected error.",
        );
      })
      .finally(() => setLoading(false));
  }, [dealId, propertyId]);

  function handleAnalysed() {
    router.push(`/properties/${propertyId}/deals/${dealId}/analysis`);
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
        </div>
        <div className="flex items-center gap-3">
          <h1 className="text-lg font-semibold text-gray-900">
            {deal?.label ?? "Deal workspace"}
          </h1>
          {deal && <DealStatusBadge status={deal.status} />}
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8">
        {loading && <p className="text-gray-500 text-sm">Loading…</p>}

        {error && (
          <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-4 py-3">
            {error}
          </p>
        )}

        {deal && property && (
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <DealInputForm
              deal={deal}
              property={property}
              onAnalysed={handleAnalysed}
            />
          </div>
        )}
      </main>
    </div>
  );
}
