"use client";

import { apiRequest } from "@/lib/api/client";
import type {
  CalculationRequest,
  CalculationSuccess,
  RecalculateRequest,
} from "@/lib/types/calculation";

/**
 * Calculation API functions.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.6.
 * SERVICE_ARCHITECTURE.md Part 10 — no component makes raw fetch calls;
 * all HTTP calls go through the typed API client layer.
 */

/**
 * POST /api/v1/calculations/ — run a new calculation from explicit inputs.
 * Returns snapshot_id, updated deal_status, and a display-level snapshot summary.
 */
export async function runCalculation(
  body: CalculationRequest,
): Promise<CalculationSuccess> {
  return apiRequest<CalculationSuccess>("/api/v1/calculations/", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/**
 * POST /api/v1/calculations/recalculate — re-run using stored working inputs.
 * Returns the same shape as runCalculation.
 */
export async function recalculate(
  body: RecalculateRequest,
): Promise<CalculationSuccess> {
  return apiRequest<CalculationSuccess>("/api/v1/calculations/recalculate", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
