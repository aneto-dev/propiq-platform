"use client";

import { createClient } from "@/lib/supabase/client";

/**
 * API client for the PropIQ backend.
 *
 * Provides a typed fetch wrapper that attaches the Supabase JWT to every
 * request via the Authorization header. Reads the session from the browser
 * Supabase client — for use in Client Components only.
 *
 * If no session exists (unauthenticated), the Authorization header is sent
 * as "Bearer undefined". The backend returns 401, which callers must handle.
 * The auth guard (Commit 7.3) ensures unauthenticated users are redirected
 * before they can trigger API calls.
 *
 * ApiError is thrown for any non-2xx response. Callers should catch it and
 * map status codes to appropriate UI states (e.g. 404 → not found, 422 →
 * validation errors).
 *
 * Architecture:
 *   IMPLEMENTATION_ROADMAP.md Commit 7.2 — base API client.
 *   SERVICE_ARCHITECTURE.md — API URL from NEXT_PUBLIC_API_URL env variable.
 */

// ---------------------------------------------------------------------------
// Error type
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly body: unknown,
  ) {
    super(`API error ${status}`);
    this.name = "ApiError";
  }
}

// ---------------------------------------------------------------------------
// Base request function
// ---------------------------------------------------------------------------

/**
 * Typed fetch wrapper with automatic JWT injection.
 *
 * Usage:
 *   const property = await apiRequest<Property>("/api/v1/properties/abc-123/");
 *   const list = await apiRequest<Property[]>("/api/v1/properties/");
 *
 * @param path   API path relative to NEXT_PUBLIC_API_URL (e.g. "/api/v1/properties/")
 * @param options Standard RequestInit options (method, body, headers, etc.)
 * @throws ApiError on non-2xx responses
 */
export async function apiRequest<T>(
  path: string,
  options?: RequestInit,
): Promise<T> {
  const supabase = createClient();
  const session = await supabase.auth.getSession();
  const token = session.data.session?.access_token;

  const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}${path}`, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    throw new ApiError(response.status, await response.json());
  }

  return response.json() as Promise<T>;
}
