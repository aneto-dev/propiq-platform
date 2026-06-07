import type { ReactNode } from "react";
import { redirect } from "next/navigation";
import { createClient } from "@/lib/supabase/server";

/**
 * Authenticated app shell layout.
 *
 * Runs as a Server Component on every request to any route under (app)/.
 * Reads the Supabase session from cookies via @supabase/ssr. If no valid
 * session exists, redirects to /login before rendering any content.
 *
 * Routes protected by this layout (after Phase 7):
 *   /dashboard
 *   /properties/...
 *   /properties/[propertyId]/deals/...
 *
 * The (app) route group does not appear in the URL — /dashboard,
 * /properties, etc. are the public paths.
 *
 * Architecture:
 *   IMPLEMENTATION_ROADMAP.md Commit 7.3 — auth guard.
 *   @supabase/ssr — server-side session reading.
 */
export default async function AppLayout({
  children,
}: {
  children: ReactNode;
}) {
  const supabase = await createClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();

  if (!session) {
    redirect("/login");
  }

  return <>{children}</>;
}
