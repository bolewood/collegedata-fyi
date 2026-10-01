import { createClient } from "@supabase/supabase-js";
import type { Database } from "./database.types";
import { clientInfoHeaders, FRIENDLY_API_CLIENT_INFO, SITE_CLIENT_INFO } from "./client-info";

const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL!;
const supabaseAnonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!;

export const supabase = createClient<Database>(supabaseUrl, supabaseAnonKey, {
  global: { headers: clientInfoHeaders(SITE_CLIENT_INFO) },
});

export const friendlyApiSupabase = createClient<Database>(supabaseUrl, supabaseAnonKey, {
  global: { headers: clientInfoHeaders(FRIENDLY_API_CLIENT_INFO) },
});

export const STORAGE_BASE_URL = `${supabaseUrl}/storage/v1/object/public/sources`;
