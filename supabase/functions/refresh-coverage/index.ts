// refresh-coverage — operator + cron entry point for the M3 coverage
// table refresh.
//
// PRD 015 M3. Calls refresh_institution_cds_coverage() (which does the
// atomic TRUNCATE+INSERT inside its own transaction) and returns the
// row count and duration. Operators can request a coverage_status histogram
// with {"include_histogram": true}; cron omits it to avoid a second full-table
// read after every refresh.
//
// pg_cron hits this hourly (refresh_coverage_cron migrations);
// operators can also curl it for debugging or after a manual archive
// drain when waiting for the next cron feels too long.
//
// Auth: same isServiceRoleAuth pattern as archive-enqueue.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient, SupabaseClient } from "jsr:@supabase/supabase-js@2";

Deno.serve(async (req: Request) => {
  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!supabaseUrl || !serviceRoleKey) {
    return json({ error: "missing supabase env" }, 500);
  }

  const auth = req.headers.get("Authorization") ?? "";
  if (!isServiceRoleAuth(auth, serviceRoleKey)) {
    return json({ error: "unauthorized" }, 403);
  }

  const supabase = createClient(supabaseUrl, serviceRoleKey);
  const started = Date.now();
  const body = await parseBody(req);
  const includeHistogram = body.include_histogram === true;

  logEvent({ event: "refresh_start", include_histogram: includeHistogram });

  const { data: refreshData, error: refreshErr } = await supabase
    .rpc("refresh_institution_cds_coverage");

  if (refreshErr) {
    logEvent({ event: "refresh_failed", error: refreshErr.message });
    return json({ error: `refresh failed: ${refreshErr.message}` }, 500);
  }

  // The RPC returns SETOF (rows_written int, duration_ms int) — supabase-js
  // surfaces it as an array with one row.
  const rpcResult = Array.isArray(refreshData) ? refreshData[0] : refreshData;
  const rowsWritten = (rpcResult as { rows_written?: number })?.rows_written ?? 0;
  const durationMs = (rpcResult as { duration_ms?: number })?.duration_ms ?? 0;

  const histogram = includeHistogram ? await loadStatusHistogram(supabase) : null;

  const totalMs = Date.now() - started;
  logEvent({
    event: "refresh_completed",
    rows_written: rowsWritten,
    refresh_duration_ms: durationMs,
    total_duration_ms: totalMs,
    histogram_included: includeHistogram,
    ...(histogram ? { histogram } : {}),
  });

  return json({
    rows_written: rowsWritten,
    refresh_duration_ms: durationMs,
    total_duration_ms: totalMs,
    ...(histogram ? { coverage_status_histogram: histogram } : {}),
  });
});

async function parseBody(req: Request): Promise<{ include_histogram?: boolean }> {
  try {
    const text = await req.text();
    if (!text.trim()) return {};
    const parsed = JSON.parse(text);
    return typeof parsed === "object" && parsed !== null ? parsed : {};
  } catch {
    return {};
  }
}

// Pull every coverage_status value and bucket in JS. Paginated for the
// same reason directory-enqueue paginates: PostgREST silently caps
// responses at PGRST_DB_MAX_ROWS (default 1000) and the coverage table
// will be ~6K rows. The histogram has to count ALL rows, not just the
// first page.
async function loadStatusHistogram(
  supabase: SupabaseClient,
): Promise<Record<string, number>> {
  const PAGE = 1000;
  const HARD_CAP = 50_000;
  const buckets: Record<string, number> = {};
  for (let start = 0; start < HARD_CAP; start += PAGE) {
    const { data, error } = await supabase
      .from("institution_cds_coverage")
      .select("coverage_status")
      .order("ipeds_id", { ascending: true })
      .range(start, start + PAGE - 1);
    if (error) {
      logEvent({ event: "histogram_failed", error: error.message });
      return buckets;
    }
    const page = data ?? [];
    for (const row of page) {
      const s = (row as { coverage_status: string }).coverage_status;
      buckets[s] = (buckets[s] ?? 0) + 1;
    }
    if (page.length < PAGE) break;
  }
  return buckets;
}

function logEvent(payload: Record<string, unknown>): void {
  console.log(JSON.stringify({
    ts: new Date().toISOString(),
    fn: "refresh-coverage",
    ...payload,
  }));
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body, null, 2), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Cache-Control": "no-store",
    },
  });
}

// Same dual-format service-role auth as archive-enqueue (exact match
// against env, or legacy JWT with role=service_role). Survives the
// Supabase key rotation transition window.
function isServiceRoleAuth(authHeader: string, envServiceRoleKey: string): boolean {
  if (!authHeader.startsWith("Bearer ")) return false;
  const token = authHeader.slice(7).trim();
  if (!token) return false;

  if (token === envServiceRoleKey) return true;

  if (token.startsWith("eyJ")) {
    const parts = token.split(".");
    if (parts.length !== 3) return false;
    try {
      const payloadB64 = parts[1].replace(/-/g, "+").replace(/_/g, "/");
      const padded = payloadB64 + "=".repeat((4 - payloadB64.length % 4) % 4);
      const payload = JSON.parse(atob(padded));
      return payload?.role === "service_role";
    } catch {
      return false;
    }
  }

  return false;
}
