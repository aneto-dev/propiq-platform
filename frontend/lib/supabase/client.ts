"use client";

import { createBrowserClient } from "@supabase/ssr";

/**
 * Browser-side Supabase client — for use in Client Components only.
 *
 * Reads session state from cookies via the browser's cookie API.
 * Call this function within a Client Component or client-side hook.
 * Do not call from Server Components or Route Handlers — use
 * lib/supabase/server.ts instead.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.2.
 */
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
}
