import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

import { searchBrowserRows, type BrowserRow, type BrowserSearchRequest } from "./browser_search.ts";

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

Deno.serve(async (req: Request) => {
  if (req.method === "OPTIONS") {
    return new Response("ok", { headers: CORS_HEADERS });
  }
  if (req.method !== "POST") {
    return json({ error: "POST only" }, 405);
  }

  let payload: BrowserSearchRequest;
  try {
    payload = await req.json();
  } catch (_e) {
    return json({ error: "invalid JSON body" }, 400);
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const anonKey = Deno.env.get("SUPABASE_ANON_KEY");
  if (!supabaseUrl || !anonKey) {
    return json({ error: "missing Supabase env" }, 500);
  }

  try {
    const client = createClient(supabaseUrl, anonKey);
    const rows = await fetchCandidateRows(client, payload);
    return json(searchBrowserRows(rows, payload), 200);
  } catch (e) {
    return json({ error: (e as Error).message }, 400);
  }
});

async function fetchCandidateRows(
  // deno-lint-ignore no-explicit-any
  client: any,
  payload: BrowserSearchRequest,
): Promise<BrowserRow[]> {
  const minYear = payload.min_year_start ?? 2024;
  const variantScope = payload.variant_scope ?? "primary_only";
  const pageSize = 1000;
  const rows: BrowserRow[] = [];
  let from = 0;

  while (true) {
    let query = client
      .from("school_browser_rows")
      .select("*")
      .gte("year_start", minYear)
      .order("school_id")
      .range(from, from + pageSize - 1);

    if (variantScope === "primary_only") {
      query = query.is("sub_institutional", null);
    }

    const { data, error } = await query;
    if (error) throw new Error(`school_browser_rows query failed: ${error.message}`);
    const batch = (data ?? []) as BrowserRow[];
    rows.push(...batch);
    if (batch.length < pageSize) break;
    from += pageSize;
  }

  return rows;
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      ...CORS_HEADERS,
      "content-type": "application/json; charset=utf-8",
    },
  });
}
