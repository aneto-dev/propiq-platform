"use client";

import { use, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { getDeal, advanceDealStatus } from "@/lib/api/deals";
import { getProperty } from "@/lib/api/properties";
import { ApiError } from "@/lib/api/client";
import type { Deal, DealStatus } from "@/lib/types/deal";
import type { Property } from "@/lib/types/property";
import { DealStatusBadge } from "@/components/deal/DealStatusBadge";
import { DealInputForm } from "@/components/deal/DealInputForm";
import { Button } from "@/components/ui/Button";

/**
 * Deal workspace — input form and lifecycle controls.
 *
 * Shows the deal input form for DRAFT/ANALYSED deals, plus a status
 * advancement panel for deals that have been analysed. The pipeline
 * progression (ANALYSED → OFFER_SUBMITTED → PURCHASED → HELD → EXITED)
 * is driven by POST /api/v1/deals/{id}/advance.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.5 + Phase 10 Feature 1.
 */

// Labels and prompts for each advanceable stage
const ADVANCE_CONFIG: Partial<
  Record<DealStatus, { label: string; prompt: string; nextLabel: string }>
> = {
  ANALYSED: {
    label: "Ready to progress this deal?",
    prompt:
      "You've analysed the numbers. When you're ready to make an offer, mark it here.",
    nextLabel: "Mark offer submitted",
  },
  OFFER_SUBMITTED: {
    label: "Offer accepted?",
    prompt: "Once you've exchanged contracts and completed, mark the deal as purchased.",
    nextLabel: "Mark as purchased",
  },
  PURCHASED: {
    label: "Property live?",
    prompt: "Once the property is tenanted and generating rent, mark it as held.",
    nextLabel: "Mark as held",
  },
  HELD: {
    label: "Exiting this investment?",
    prompt: "When you sell the property or exit the investment, mark it as exited.",
    nextLabel: "Mark as exited",
  },
};

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
  const [advancing, setAdvancing] = useState(false);
  const [advanceError, setAdvanceError] = useState<string | null>(null);

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

  async function handleAdvance() {
    setAdvancing(true);
    setAdvanceError(null);
    try {
      const updated = await advanceDealStatus(dealId);
      setDeal(updated);
    } catch (err: unknown) {
      const body = (err as { body?: { detail?: string } })?.body;
      setAdvanceError(body?.detail ?? "Could not advance deal status.");
    } finally {
      setAdvancing(false);
    }
  }

  const advanceConfig = deal ? ADVANCE_CONFIG[deal.status] : null;

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
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-semibold text-gray-900">
              {deal?.label ?? "Deal workspace"}
            </h1>
            {deal && <DealStatusBadge status={deal.status} />}
          </div>
          {deal?.latest_snapshot_id && (
            <Link
              href={`/properties/${propertyId}/deals/${dealId}/analysis`}
              className="text-sm text-blue-600 hover:underline"
            >
              View analysis →
            </Link>
          )}
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8 space-y-6">
        {loading && <p className="text-gray-500 text-sm">Loading…</p>}

        {error && (
          <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-4 py-3">
            {error}
          </p>
        )}

        {/* Pipeline advancement panel — shown when the deal has a clear next step */}
        {deal && advanceConfig && (
          <div className="bg-white rounded-xl border border-gray-200 px-5 py-4">
            <p className="text-sm font-medium text-gray-800 mb-1">
              {advanceConfig.label}
            </p>
            <p className="text-xs text-gray-500 mb-3">{advanceConfig.prompt}</p>

            {advanceError && (
              <p className="text-xs text-red-600 mb-3">{advanceError}</p>
            )}

            <Button
              variant="secondary"
              onClick={handleAdvance}
              disabled={advancing}
            >
              {advancing ? "Updating…" : advanceConfig.nextLabel}
            </Button>
          </div>
        )}

        {/* Input form — only shown for deals where working inputs still matter */}
        {deal && property && deal.status !== "EXITED" && (
          <div className="bg-white rounded-xl border border-gray-200 p-6">
            <DealInputForm
              deal={deal}
              property={property}
              onAnalysed={handleAnalysed}
            />
          </div>
        )}

        {/* Exited state */}
        {deal && deal.status === "EXITED" && (
          <div className="bg-white rounded-xl border border-gray-200 px-5 py-8 text-center">
            <p className="text-gray-500 mb-1">This deal has been exited.</p>
            <p className="text-xs text-gray-400">
              All analysis snapshots remain available in the{" "}
              <Link
                href={`/properties/${propertyId}/deals/${dealId}/history`}
                className="text-blue-600 hover:underline"
              >
                analysis history
              </Link>
              .
            </p>
          </div>
        )}
      </main>
    </div>
  );
}
