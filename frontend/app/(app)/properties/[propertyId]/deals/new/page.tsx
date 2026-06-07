"use client";

import { use, useState } from "react";
import { useRouter } from "next/navigation";
import { createDeal } from "@/lib/api/deals";
import { ApiError } from "@/lib/api/client";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";

/**
 * Create deal form.
 *
 * Collects a label for the new deal and submits to POST /api/v1/deals/.
 * On success, redirects to the deal workspace.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.5.
 */
export default function NewDealPage({
  params,
}: {
  params: Promise<{ propertyId: string }>;
}) {
  const { propertyId } = use(params);
  const router = useRouter();
  const [label, setLabel] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const deal = await createDeal(propertyId, label);
      router.push(`/properties/${propertyId}/deals/${deal.id}`);
    } catch (err: unknown) {
      const body = (err instanceof ApiError ? err.body : null) as
        | { detail?: string }
        | null;
      setError(body?.detail ?? "Failed to create deal.");
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4">
        <h1 className="text-lg font-semibold text-gray-900">PropIQ</h1>
      </header>

      <main className="max-w-lg mx-auto px-6 py-8">
        <h2 className="text-xl font-semibold text-gray-900 mb-6">New deal</h2>

        <form
          onSubmit={handleSubmit}
          className="bg-white rounded-xl border border-gray-200 p-6 flex flex-col gap-4"
        >
          <Input
            id="label"
            label="Deal label"
            placeholder="e.g. 25% deposit scenario"
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            required
          />

          {error && (
            <p className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">
              {error}
            </p>
          )}

          <div className="flex gap-3 pt-2">
            <Button type="submit" disabled={loading}>
              {loading ? "Creating…" : "Create deal"}
            </Button>
            <Button type="button" variant="secondary" onClick={() => router.back()}>
              Cancel
            </Button>
          </div>
        </form>
      </main>
    </div>
  );
}
