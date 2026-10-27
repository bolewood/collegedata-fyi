import { createClient } from "@supabase/supabase-js";
import type { Database } from "./database.types";
import { clientInfoHeaders, SITE_CLIENT_INFO } from "./client-info";
import { timedFetch } from "./supabase-fetch";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export const supabase = createClient<Database>(supabaseUrl, supabaseAnonKey, {
  auth: { persistSession: false, autoRefreshToken: false },
  global: {
    headers: clientInfoHeaders(SITE_CLIENT_INFO),
    fetch: timedFetch,
  },
});

export const STORAGE_BASE_URL = `${supabaseUrl}/storage/v1/object/public/sources`;
