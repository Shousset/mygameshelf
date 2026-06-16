import { createBrowserClient } from "@supabase/ssr";

// Browser Supabase client. The anon key is public by design (safe to ship to the
// client) — row access is enforced by the backend JWT check, not by hiding this key.
const url = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

// True only when both vars look like real values (not empty, not the .env.example
// placeholder). The UI uses this to show a clear setup message instead of letting
// auth calls blow up with a cryptic "NetworkError when attempting to fetch resource".
export const isSupabaseConfigured =
  !!url && !!anonKey && !url.includes("your-project-ref") && url.startsWith("http");

if (!isSupabaseConfigured && typeof window !== "undefined") {
  // eslint-disable-next-line no-console
  console.error(
    "[MyGameShelf] Supabase is not configured. Set NEXT_PUBLIC_SUPABASE_URL and " +
      "NEXT_PUBLIC_SUPABASE_ANON_KEY in web/.env.local with your real Supabase project " +
      "values, then restart `npm run dev`.",
  );
}

// Fall back to a syntactically valid dummy URL when unconfigured so importing this
// module never throws at build/render time; actual auth calls will fail clearly and
// are gated by isSupabaseConfigured in the UI.
export const supabase = createBrowserClient(
  isSupabaseConfigured ? url : "https://unconfigured.invalid",
  isSupabaseConfigured ? anonKey : "unconfigured",
);
