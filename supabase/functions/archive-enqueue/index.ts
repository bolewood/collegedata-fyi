// archive-enqueue — monthly seeder for the archive pipeline.
//
// Invoked daily by pg_cron (PR 5). The daily cadence (rather than monthly)
// exists so a transient schools.yaml fetch failure on any given day
// self-heals on the next tick, instead of losing a whole month of
// enqueueing. Idempotency is guaranteed by a deterministic run_id derived
// from the current calendar month: within a month, repeated calls are
// no-ops for rows that already landed, because the archive_queue
// UNIQUE (enqueued_run_id, school_id) constraint fires under ignoreDuplicates
// and skips them.
//
// At the start of each new calendar month, run_id changes, which seeds a
// fresh batch alongside any unprocessed rows from the prior month.
// archive-process claims in enqueued_at order so older batches drain
// first.
//
// Operator retry semantics: re-running archive-enqueue within the same
// calendar month is a no-op for existing rows, including rows that are
// currently in status='failed_permanent'. This is deliberate. To retry
// a specific failed row, use the archive-process operator backfill:
//
//   curl -X POST https://<ref>.supabase.co/functions/v1/archive-process \
//        ?force_school=<school-id> \
//        -H "Authorization: Bearer $SUPABASE_SERVICE_ROLE_KEY"
//
// force_school bypasses the queue entirely and calls archiveOneSchool()
// directly. See supabase/functions/archive-process/index.ts.
//
// Auth: same pattern as archive-process. verify_jwt=true gatekeeps at the
// Supabase layer; the handler additionally verifies the bearer token
// matches SUPABASE_SERVICE_ROLE_KEY exactly. Only pg_cron and authorized
// operators can trigger a batch.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "jsr:@supabase/supabase-js@2";

import {
  ArchivableSchool,
  fetchSchoolsYaml,
  filterArchivable,
} from "../_shared/schools.ts";

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

  // run_id is deterministic on the calendar month (UTC). Daily cron calls
  // within the same month collide on the unique (run_id, school_id) index
  // and no-op via ignoreDuplicates. At the start of a new month, run_id
  // changes, seeding a fresh batch. Operators can override via ?run_id=...
  // when manually reprocessing or testing.
  const url = new URL(req.url);
  const overrideRunId = url.searchParams.get("run_id");
  const runId = overrideRunId ?? await monthlyRunId(new Date());

  const started = Date.now();
  logEvent({ event: "enqueue_start", run_id: runId });

  let allSchools: ArchivableSchool[];
  let skippedInvalid: number;
  try {
    const result = await fetchSchoolsYaml();
    allSchools = filterArchivable(result.entries);
    skippedInvalid = result.skipped_invalid;
  } catch (e) {
    const err = e as Error;
    logEvent({
      event: "schools_fetch_failed",
      run_id: runId,
      error: err.message,
    });
    return json({
      error: `schools.yaml fetch failed: ${err.message}`,
    }, 502);
  }

  if (skippedInvalid > 0) {
    // Not fatal — validation filters out malformed rows so the good ones
    // still enqueue. Log the count so the operator can investigate.
    logEvent({
      event: "schools_yaml_skipped_invalid",
      run_id: runId,
      skipped_invalid: skippedInvalid,
    });
  }

  if (allSchools.length === 0) {
    logEvent({ event: "no_schools_to_enqueue", run_id: runId });
    return json({
      mode: "enqueue",
      run_id: runId,
      enqueued: 0,
      note: "schools.yaml has no archivable schools",
    });
  }

  // Cooldown: skip schools whose most recent done row had
  // last_outcome=unchanged_verified within the cooldown window.
  // Empirical motivation in migration 20260418220000.
  // Operator override: ?force_recheck=true bypasses the cooldown for
  // this run only. force_school via archive-process always bypasses
  // the queue and is unaffected.
  const forceRecheck = url.searchParams.get("force_recheck") === "true";
  const cooldownDays = parseInt(
    url.searchParams.get("cooldown_days") ?? "30",
    10,
  );

  let inCooldown = new Set<string>();
  if (!forceRecheck && cooldownDays > 0) {
    const cooldownCutoff = new Date(
      Date.now() - cooldownDays * 24 * 60 * 60 * 1000,
    ).toISOString();

    const { data: cooldownRows, error: cooldownErr } = await supabase
      .from("archive_queue")
      .select("school_id, processed_at")
      .eq("status", "done")
      .eq("last_outcome", "unchanged_verified")
      .gte("processed_at", cooldownCutoff);

    if (cooldownErr) {
      // Don't fail enqueue on cooldown query failure — log and proceed
      // with no cooldown applied. Better to over-enqueue than to skip
      // a fresh batch entirely.
      logEvent({
        event: "cooldown_query_failed",
        run_id: runId,
        error: cooldownErr.message,
      });
    } else {
      // Multiple rows per school can match (one per past run); we only
      // need the school_ids.
      inCooldown = new Set((cooldownRows ?? []).map((r) => r.school_id));
    }
  }

  const rows = allSchools
    .filter((s) => !inCooldown.has(s.id))
    .map((s) => ({
      enqueued_run_id: runId,
      school_id: s.id,
      school_name: s.name,
      cds_url_hint: s.cds_url_hint,
      status: "ready" as const,
    }));

  if (inCooldown.size > 0) {
    logEvent({
      event: "cooldown_skipped",
      run_id: runId,
      cooldown_days: cooldownDays,
      skipped: inCooldown.size,
    });
  }

  // Bulk insert with onConflict + ignoreDuplicates so re-running with the
  // same run_id is a no-op on rows that already landed. This is the
  // retry-safety property the plan's Rollout step 2 assumes.
  // After cooldown filtering, rows may be empty. Short-circuit so we
  // don't issue an empty upsert (which Supabase rejects).
  if (rows.length === 0) {
    logEvent({
      event: "enqueue_completed",
      run_id: runId,
      enqueued: 0,
      skipped_existing: 0,
      skipped_cooldown: inCooldown.size,
      duration_ms: Date.now() - started,
    });
    return json({
      mode: "enqueue",
      run_id: runId,
      enqueued: 0,
      skipped_existing: 0,
      skipped_cooldown: inCooldown.size,
      skipped_invalid_yaml: skippedInvalid,
      total_archivable: allSchools.length,
      note: "all archivable schools were in cooldown",
    });
  }

  const { data, error } = await supabase
    .from("archive_queue")
    .upsert(rows, {
      onConflict: "enqueued_run_id,school_id",
      ignoreDuplicates: true,
    })
    .select("id");

  if (error) {
    logEvent({
      event: "enqueue_failed",
      run_id: runId,
      intended_count: rows.length,
      error: error.message,
    });
    return json({
      error: `enqueue failed: ${error.message}`,
      run_id: runId,
      intended_count: rows.length,
    }, 500);
  }

  const enqueued = data?.length ?? 0;
  const skippedExisting = rows.length - enqueued;
  logEvent({
    event: "enqueue_completed",
    run_id: runId,
    enqueued,
    skipped_existing: skippedExisting,
    skipped_cooldown: inCooldown.size,
    duration_ms: Date.now() - started,
  });

  return json({
    mode: "enqueue",
    run_id: runId,
    enqueued,
    skipped_existing: skippedExisting,
    skipped_cooldown: inCooldown.size,
    skipped_invalid_yaml: skippedInvalid,
    total_archivable: allSchools.length,
  });
});

// Deterministic UUID derived from the (year, month) of the supplied date.
// Ensures repeated archive-enqueue calls within the same calendar month
// collide on the unique (run_id, school_id) index so existing rows are
// no-ops and only new schools land. First byte of the uuid v5-style layout
// is tagged with namespace string 'archive-enqueue:' so a future skill
// or tool with a different key doesn't collide with our namespace.
async function monthlyRunId(now: Date): Promise<string> {
  const yyyy = now.getUTCFullYear().toString().padStart(4, "0");
  const mm = (now.getUTCMonth() + 1).toString().padStart(2, "0");
  const key = `archive-enqueue:${yyyy}-${mm}`;
  const data = new TextEncoder().encode(key);
  const hashBuf = await crypto.subtle.digest("SHA-256", data);
  const hex = Array.from(new Uint8Array(hashBuf).slice(0, 16))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  return (
    hex.slice(0, 8) + "-" +
    hex.slice(8, 12) + "-" +
    hex.slice(12, 16) + "-" +
    hex.slice(16, 20) + "-" +
    hex.slice(20, 32)
  );
}

function logEvent(payload: Record<string, unknown>): void {
  console.log(JSON.stringify({
    ts: new Date().toISOString(),
    fn: "archive-enqueue",
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

// Accept both service-role credential formats. See archive-process/index.ts
// for the full explanation — legacy JWT (eyJ...) and new sb_secret_ format
// both need to work during the Supabase key rotation transition window.
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
