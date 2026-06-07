"use client";

import { useRouter } from "next/navigation";
import { createClient } from "@/lib/supabase/client";
import { Button } from "@/components/ui/Button";

/**
 * Sign-out button — Client Component.
 *
 * Calls supabase.auth.signOut() and redirects to /login.
 * Co-located with the dashboard page; not a shared component because
 * logout is only needed in authenticated layouts.
 *
 * Architecture: IMPLEMENTATION_ROADMAP.md Commit 7.3.
 */
export function SignOutButton() {
  const router = useRouter();

  async function handleSignOut() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
  }

  return (
    <Button variant="secondary" onClick={handleSignOut}>
      Sign out
    </Button>
  );
}
