"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { createProperty } from "@/lib/api/properties";
import { ApiError } from "@/lib/api/client";
import type { CreatePropertyRequest, Tenure } from "@/lib/types/property";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";

/**
 * Create property form.
 *
 * Collects the minimum required fields: address line 1, city, postcode,
 * property type, and tenure. When tenure is LEASEHOLD, an additional
 * lease_years_remaining field is shown and required.
 *
 * On success, redirects to the deals page for the new property
 * (/properties/{id}/deals — created in Commit 7.5).
 *
 * Validation:
 *   - address_line_1, city, postcode, property_type, tenure: required
 *   - lease_years_remaining: required and positive when tenure === "LEASEHOLD"
 *   - Backend validates UK postcode format and leasehold consistency (422)
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.4.
 */
export default function NewPropertyPage() {
  const router = useRouter();
  const [tenure, setTenure] = useState<Tenure | "">("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const data = new FormData(e.currentTarget);

    setLoading(true);
    setError(null);

    const leaseYears = data.get("lease_years_remaining");
    const body: CreatePropertyRequest = {
      address_line_1: data.get("address_line_1") as string,
      city: data.get("city") as string,
      postcode: data.get("postcode") as string,
      property_type: "RESIDENTIAL_SINGLE_LET",
      tenure: tenure as Tenure,
      lease_years_remaining:
        tenure === "LEASEHOLD" && leaseYears
          ? Number(leaseYears)
          : null,
    };

    try {
      const property = await createProperty(body);
      router.push(`/properties/${property.id}/deals`);
    } catch (err: unknown) {
      if (err instanceof ApiError) {
        const body = err.body as { detail?: string };
        setError(body.detail ?? "Failed to create property.");
      } else {
        setError("An unexpected error occurred.");
      }
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <h1 className="text-lg font-semibold text-gray-900">PropIQ</h1>
      </header>

      <main className="max-w-lg mx-auto px-6 py-8">
        <h2 className="text-xl font-semibold text-gray-900 mb-6">
          Add property
        </h2>

        <form
          onSubmit={handleSubmit}
          className="bg-white rounded-xl border border-gray-200 p-6 flex flex-col gap-4"
        >
          <Input
            id="address_line_1"
            name="address_line_1"
            label="Address line 1"
            placeholder="1 Example Street"
            required
          />

          <Input
            id="city"
            name="city"
            label="City"
            placeholder="London"
            required
          />

          <Input
            id="postcode"
            name="postcode"
            label="Postcode"
            placeholder="SW1A 1AA"
            required
          />

          <Select
            id="property_type"
            name="property_type"
            label="Property type"
            required
            defaultValue="RESIDENTIAL_SINGLE_LET"
            options={[
              {
                value: "RESIDENTIAL_SINGLE_LET",
                label: "Residential single let",
              },
            ]}
          />

          <Select
            id="tenure"
            name="tenure"
            label="Tenure"
            required
            value={tenure}
            onChange={(e) => setTenure(e.target.value as Tenure | "")}
            options={[
              { value: "", label: "Select tenure…" },
              { value: "FREEHOLD", label: "Freehold" },
              { value: "LEASEHOLD", label: "Leasehold" },
            ]}
          />

          {tenure === "LEASEHOLD" && (
            <Input
              id="lease_years_remaining"
              name="lease_years_remaining"
              label="Lease years remaining"
              type="number"
              min={1}
              placeholder="e.g. 125"
              required
            />
          )}

          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">
              {error}
            </p>
          )}

          <div className="flex gap-3 pt-2">
            <Button type="submit" disabled={loading}>
              {loading ? "Saving…" : "Add property"}
            </Button>
            <Button
              type="button"
              variant="secondary"
              onClick={() => router.back()}
            >
              Cancel
            </Button>
          </div>
        </form>
      </main>
    </div>
  );
}
