import { redirect } from "next/navigation";

/**
 * Root page — redirects to the authenticated application area.
 *
 * The session-aware redirect (login vs dashboard) is added in Commit 7.3
 * once Supabase Auth is wired. This stub redirects to /dashboard; the
 * auth guard in (app)/layout.tsx will redirect unauthenticated users to
 * /login once that layout exists.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.1.
 */
export default function RootPage(): never {
  redirect("/dashboard");
}
