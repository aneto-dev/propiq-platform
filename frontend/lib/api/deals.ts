"use client";

import { apiRequest } from "@/lib/api/client";
import type { Deal, DealSummary, UpdateWorkingInputsRequest } from "@/lib/types/deal";

/**
 * Deal API functions.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.5.
 */

/**
 * GET /api/v1/deals/ — list all deals for the authenticated user.
 * The backend does not filter by property; filter client-side via DealSummary.property_id.
 */
export async function getDeals(): Promise<DealSummary[]> {
  return apiRequest<DealSummary[]>("/api/v1/deals/");
}

/**
 * GET /api/v1/deals/{id}/ — fetch a single deal with full working inputs.
 */
export async function getDeal(id: string): Promise<Deal> {
  return apiRequest<Deal>(`/api/v1/deals/${id}/`);
}

/**
 * POST /api/v1/deals/ — create a new deal.
 * property_id and label are query parameters (not body) per the backend route.
 */
export async function createDeal(propertyId: string, label: string): Promise<Deal> {
  const params = new URLSearchParams({ property_id: propertyId, label });
  return apiRequest<Deal>(`/api/v1/deals/?${params.toString()}`, {
    method: "POST",
  });
}

/**
 * PATCH /api/v1/deals/{id}/inputs — update working inputs (partial update).
 * Only supplied fields are applied; absent fields preserve their current value.
 */
export async function updateWorkingInputs(
  id: string,
  updates: UpdateWorkingInputsRequest,
): Promise<Deal> {
  return apiRequest<Deal>(`/api/v1/deals/${id}/inputs`, {
    method: "PATCH",
    body: JSON.stringify(updates),
  });
}
