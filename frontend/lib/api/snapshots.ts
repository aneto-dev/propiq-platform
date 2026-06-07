"use client";

import { apiRequest } from "@/lib/api/client";
import type {
  SnapshotSummary,
  SnapshotFull,
  SnapshotHistoryEntry,
} from "@/lib/types/snapshot";

/**
 * Snapshot API functions.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.6.
 */

/**
 * GET /api/v1/snapshots/{id} — fetch display-level snapshot (outputs + risk flags).
 * Does not include intermediates. Use getSnapshotFull for SDLT bands and other
 * intermediate values.
 */
export async function getSnapshot(id: string): Promise<SnapshotSummary> {
  return apiRequest<SnapshotSummary>(`/api/v1/snapshots/${id}`);
}

/**
 * GET /api/v1/snapshots/{id}/full — fetch full snapshot including intermediates.
 * Required for SDLTBreakdown and AcquisitionCostBreakdown which need
 * sdlt_band_breakdown and loan_amount_gbp from SnapshotIntermediates.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.6 — snapshot-first rendering.
 * SERVICE_ARCHITECTURE.md Part 10 — frontend renders what the API returns.
 */
export async function getSnapshotFull(id: string): Promise<SnapshotFull> {
  return apiRequest<SnapshotFull>(`/api/v1/snapshots/${id}/full`);
}

/**
 * GET /api/v1/snapshots/?deal_id={dealId} — list snapshot history for a deal.
 * Returns lightweight summary entries (key metrics only, no full outputs).
 */
export async function getSnapshotHistory(
  dealId: string,
): Promise<SnapshotHistoryEntry[]> {
  return apiRequest<SnapshotHistoryEntry[]>(
    `/api/v1/snapshots/?deal_id=${dealId}`,
  );
}
