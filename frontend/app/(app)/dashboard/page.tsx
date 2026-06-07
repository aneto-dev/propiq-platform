import { createClient } from "@/lib/supabase/server";
import { SignOutButton } from "./SignOutButton";

/**
 * Dashboard — deal pipeline entry point.
 *
 * Phase 7 stub: shows an empty state inviting the user to add their first deal.
 * The deal list is populated in Commit 7.5.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.3.
 */
export default async function DashboardPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between">
        <h1 className="text-lg font-semibold text-gray-900">PropIQ</h1>
        <div className="flex items-center gap-4">
          {user?.email && (
            <span className="text-sm text-gray-500">{user.email}</span>
          )}
          <SignOutButton />
        </div>
      </header>

      <main className="max-w-3xl mx-auto px-6 py-16 text-center">
        <h2 className="text-2xl font-semibold text-gray-900 mb-3">
          Your deal pipeline
        </h2>
        <p className="text-gray-500 mb-8">
          Add your first deal to start analysing UK property investments.
        </p>
        <p className="text-sm text-gray-400">
          Property and deal creation coming in the next step.
        </p>
      </main>
    </div>
  );
}
