"use client";

import { apiRequest } from "@/lib/api/client";
import type { CreatePropertyRequest, Property } from "@/lib/types/property";

/**
 * Property API functions.
 *
 * Thin wrappers over apiRequest — each maps to one backend route.
 * Authentication is handled by apiRequest via the Supabase browser client.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.4.
 */

/** GET /api/v1/properties/ — list all non-archived properties for the authenticated user. */
export async function getProperties(): Promise<Property[]> {
  return apiRequest<Property[]>("/api/v1/properties/");
}

/** GET /api/v1/properties/{id}/ — fetch a single property by ID. */
export async function getProperty(id: string): Promise<Property> {
  return apiRequest<Property>(`/api/v1/properties/${id}/`);
}

/** POST /api/v1/properties/ — create a new property. */
export async function createProperty(
  body: CreatePropertyRequest,
): Promise<Property> {
  return apiRequest<Property>("/api/v1/properties/", {
    method: "POST",
    body: JSON.stringify(body),
  });
}
