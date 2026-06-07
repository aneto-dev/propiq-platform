import { createServerClient } from "@supabase/ssr";
import type { CookieOptions } from "@supabase/ssr";
import { cookies } from "next/headers";

/**
 * Server-side Supabase client — for use in Server Components and Route Handlers.
 *
 * Reads session state from cookies via next/headers. The factory is async
 * because Next.js 15 cookies() returns a Promise.
 *
 * Cookie handling:
 *   getAll — reads all cookies for auth state verification
 *   setAll — updates cookies after token refresh; silently ignored in Server
 *            Components where cookies cannot be mutated (see try/catch below).
 *            A middleware is required for correct session refresh in production
 *            (added in a later commit).
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.2.
 * Supabase: @supabase/ssr 0.5.x CookieMethodsServer interface.
 */
export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(
          cookiesToSet: { name: string; value: string; options: CookieOptions }[],
        ) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options),
            );
          } catch {
            // setAll is called from a Server Component where cookies
            // cannot be set. Silently ignored — middleware handles
            // session refresh.
          }
        },
      },
    },
  );
}
