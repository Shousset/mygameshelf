import { createBrowserClient } from "@supabase/ssr";

// Browser Supabase client. The anon key is public by design (safe to ship to the
// client) — row access is enforced by the backend JWT check, not by hiding this key.
export const supabase = createBrowserClient(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
);
