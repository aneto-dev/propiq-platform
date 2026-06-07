"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { getProperties } from "@/lib/api/properties";
import { ApiError } from "@/lib/api/client";
import type { Property } from "@/lib/types/property";
import { Button } from "@/components/ui/Button";

/**
 * Property list page.
 *
 * Fetches the authenticated user's properties and displays them.
 * Empty state invites the user to add their first property.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.4.
 */
export default function PropertiesPage() {
  const [properties, setProperties] = useState<Property[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getProperties()
      .then(setProperties)
      .catch((err: unknown) => {
        if (err instanceof ApiError) {
          setError("Failed to load properties.");
        } else {
          setError("An unexpected error occurred.");
        }
      })
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-gray-900">PropIQ</h1>
        <Link href="/properties/new">
          <Button>Add property</Button>
        </Link>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-8">
        <h2 className="text-xl font-semibold text-gray-900 mb-6">Properties</h2>

        {loading && (
          <p className="text-gray-500 text-sm">Loading…</p>
        )}

        {error && (
          <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-4 py-3">
            {error}
          </p>
        )}

        {!loading && !error && properties.length === 0 && (
          <div className="text-center py-20">
            <p className="text-gray-500 mb-6">No properties yet.</p>
            <Link href="/properties/new">
              <Button>Add your first property</Button>
            </Link>
          </div>
        )}

        {properties.map((p) => (
          <Link
            key={p.id}
            href={`/properties/${p.id}/deals`}
            className="block bg-white rounded-lg border border-gray-200 px-5 py-4 mb-3 hover:border-blue-300 transition-colors"
          >
            <p className="font-medium text-gray-900">{p.address_line_1}</p>
            <p className="text-sm text-gray-500 mt-0.5">
              {p.city}&nbsp;·&nbsp;{p.postcode}&nbsp;·&nbsp;
              {p.tenure === "FREEHOLD" ? "Freehold" : "Leasehold"}
            </p>
          </Link>
        ))}
      </main>
    </div>
  );
}
