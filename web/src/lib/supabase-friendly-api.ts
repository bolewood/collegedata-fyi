import { createClient } from "@supabase/supabase-js";
import type { Database } from "./database.types";
import { clientInfoHeaders, FRIENDLY_API_CLIENT_INFO } from "./client-info";

// Kept out of supabase.ts so browser bundles never build a second auth client.
export const friendlyApiSupabase = createClient<Database>(
  process.env.NEXT_PUBLIC_SUPABASE_URL!,
  process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  {
    auth: { persistSession: false, autoRefreshToken: false },
    global: { headers: clientInfoHeaders(FRIENDLY_API_CLIENT_INFO) },
  },
);
