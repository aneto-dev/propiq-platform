/**
 * Property TypeScript types — mirror of backend app/api/v1/schemas/property.py.
 *
 * All UUIDs are strings. Timestamps are ISO 8601 strings.
 * Enum values match the backend string enum values exactly.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.2.
 */

// ---------------------------------------------------------------------------
// Enums
// ---------------------------------------------------------------------------

export type PropertyType = "RESIDENTIAL_SINGLE_LET";

export type Tenure = "FREEHOLD" | "LEASEHOLD";

// ---------------------------------------------------------------------------
// Request types
// ---------------------------------------------------------------------------

/** POST /api/v1/properties/ request body — mirrors CreatePropertyRequest. */
export interface CreatePropertyRequest {
  address_line_1: string;
  address_line_2?: string | null;
  city: string;
  postcode: string;
  property_type: PropertyType;
  tenure: Tenure;
  lease_years_remaining?: number | null;
  bedrooms?: number | null;
  epc_rating?: string | null;
}

/** PATCH /api/v1/properties/{id}/ request body — same shape as CreatePropertyRequest. */
export type UpdatePropertyRequest = CreatePropertyRequest;

// ---------------------------------------------------------------------------
// Response types
// ---------------------------------------------------------------------------

/** Mirrors PropertyResponse — single property from any property endpoint. */
export interface Property {
  id: string;
  user_id: string;
  address_line_1: string;
  address_line_2: string | null;
  city: string;
  postcode: string;
  property_type: PropertyType;
  tenure: Tenure;
  lease_years_remaining: number | null;
  bedrooms: number | null;
  epc_rating: string | null;
  is_archived: boolean;
  archived_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}
