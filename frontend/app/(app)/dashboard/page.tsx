"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { createClient } from "@/lib/supabase/client";
import { getDeals } from "@/lib/api/deals";
import { getProperties } from "@/lib/api/properties";
import type { DealSummary } from "@/lib/types/deal";
import type { Property } from "@/lib/types/property";
import { DealStatusBadge } from "@/components/deal/DealStatusBadge";
import { Button } from "@/components/ui/Button";
import { SignOutButton } from "./SignOutButton";

/**
 * Dashboard — deal pipeline.
 *
 * Shows all active deals across all properties, sorted by most recently
 * updated. Provides navigation to individual deal workspaces and analysis
 * pages, and a quick path to add a new property.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Phase 9.
 */
export default function DashboardPage() {
  const [userEmail, setUserEmail] = useState<string | null>(null);
  const [deals, setDeals] = useState<DealSummary[]>([]);
  const [propertiesById, setPropertiesById] = useState<
    Record<string, Property>
  >({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function load() {
      const supabase = createClient();
      const {
        data: { user },
      } = await supabase.auth.getUser();
      setUserEmail(user?.email ?? null);

      try {
        const [allDeals, allProperties] = await Promise.all([
          getDeals(),
          getProperties(),
        ]);

        // Only show DRAFT and ANALYSED deals on the pipeline view
        const active = allDeals.filter((d) => d.status !== "ARCHIVED");
        // Sort by most recently updated (API returns ISO strings)
        active.sort((a, b) => b.updated_at.localeCompare(a.updated_at));

        const byId: Record<string, Property> = {};
        for (const p of allProperties) {
          byId[p.id] = p;
        }

        setDeals(active);
        setPropertiesById(byId);
      } catch {
        // Silently degrade — user can still navigate
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  function cashFlowDisplay(deal: DealSummary): string | null {
    if (!deal.latest_snapshot_cash_flow_gbp) return null;
    const n = parseFloat(deal.latest_snapshot_cash_flow_gbp);
    const abs = Math.abs(n).toLocaleString("en-GB", {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    });
    return n < 0 ? `-£${abs}/yr` : `£${abs}/yr`;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-gray-900">PropIQ</h1>
        <div className="flex items-center gap-4">
          {userEmail && (
            <span className="text-sm text-gray-500">{userEmail}</span>
          )}
          <SignOutButton />
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8">
        <div className="flex items-center justify-between mb-6">
          <h2 className="text-xl font-semibold text-gray-900">Deal pipeline</h2>
          <Link href="/properties">
            <Button variant="secondary">Properties</Button>
          </Link>
        </div>

        {loading && (
          <p className="text-sm text-gray-500">Loading pipeline…</p>
        )}

        {!loading && deals.length === 0 && (
          <div className="text-center py-20 bg-white rounded-xl border border-gray-200">
            <p className="text-gray-500 mb-2">No active deals yet.</p>
            <p className="text-sm text-gray-400 mb-6">
              Add a property, then create a deal to start analysing.
            </p>
            <Link href="/properties">
              <Button>Add your first property</Button>
            </Link>
          </div>
        )}

        {!loading && deals.length > 0 && (
          <ul className="space-y-3">
            {deals.map((deal) => {
              const property = propertiesById[deal.property_id];
              const cf = cashFlowDisplay(deal);
              const isNegative =
                cf !== null && cf.startsWith("-");

              return (
                <li key={deal.id}>
                  <Link
                    href={`/properties/${deal.property_id}/deals/${deal.id}`}
                    className="block bg-white rounded-lg border border-gray-200 px-5 py-4 hover:border-blue-300 transition-colors"
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="font-medium text-gray-900 truncate">
                          {deal.label}
                        </p>
                        {property && (
                          <p className="text-xs text-gray-400 mt-0.5 truncate">
                            {property.address_line_1}
                            {property.city ? `, ${property.city}` : ""}
                          </p>
                        )}
                      </div>
                      <div className="flex items-center gap-3 shrink-0">
                        {cf !== null && (
                          <span
                            className={`text-sm font-medium tabular-nums ${
                              isNegative ? "text-red-600" : "text-green-700"
                            }`}
                          >
                            {cf}
                          </span>
                        )}
                        <DealStatusBadge status={deal.status} />
                      </div>
                    </div>

                    {deal.status === "ANALYSED" && deal.latest_snapshot_id && (
                      <div className="mt-2 flex items-center gap-4 text-xs text-gray-400">
                        {deal.latest_snapshot_gross_yield && (
                          <span>
                            Gross yield: {deal.latest_snapshot_gross_yield}%
                          </span>
                        )}
                        {deal.latest_snapshot_risk_flag_count_high != null &&
                          deal.latest_snapshot_risk_flag_count_high > 0 && (
                            <span className="text-red-500 font-medium">
                              {deal.latest_snapshot_risk_flag_count_high} HIGH{" "}
                              {deal.latest_snapshot_risk_flag_count_high === 1
                                ? "flag"
                                : "flags"}
                            </span>
                          )}
                        {deal.latest_snapshot_calculated_at && (
                          <span>
                            Analysed{" "}
                            {new Date(
                              deal.latest_snapshot_calculated_at,
                            ).toLocaleDateString("en-GB", {
                              day: "numeric",
                              month: "short",
                            })}
                          </span>
                        )}
                      </div>
                    )}
                  </Link>
                </li>
              );
            })}
          </ul>
        )}
      </main>
    </div>
  );
}
