// archive-enqueue — cooldown-aware daily seeder for the archive pipeline.
//
// Invoked daily by pg_cron (PR 5). Each UTC day gets a deterministic run_id,
// so a transient schools.yaml fetch failure or school-level probe failure can
// self-heal the next day. Repeated calls within the same day are no-ops for
// rows that already landed because the archive_queue UNIQUE
// (enqueued_run_id, school_id) constraint fires under ignoreDuplicates and
// skips them.
//
// Per-outcome cooldowns control actual probe frequency: successful schools are
// checked every 7 days year-round, while stable failures back off longer and
// transient failures have no cooldown. A database-enforced active-row
// invariant prevents a lagging processor from accumulating duplicate work.
// archive-process claims in enqueued_at order so older batches drain first.
//
// Operator retry semantics: re-running archive-enqueue within the same UTC day
// is a no-op for existing rows. The next daily run can enqueue rows whose
// cooldown has elapsed. To retry a specific row immediately, use the
// archive-process operator backfill:
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
import { ProbeOutcome } from "../_shared/probe_outcome.ts";
import {
  archiveCooldownDaysForOutcome,
  archiveEnqueueRunId,
  parseCooldownDaysOverride,
} from "./schedule.ts";

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

  // run_id is deterministic for the UTC calendar day. Duplicate cron calls on
  // the same day collide on the unique (run_id, school_id) index and no-op via
  // ignoreDuplicates. The next day gets a fresh run_id, allowing cooldown-free
  // transient failures to retry. Operators can override via ?run_id=... when
  // manually reprocessing or testing.
  const url = new URL(req.url);
  const overrideRunId = url.searchParams.get("run_id");
  const now = new Date();
  const runId = overrideRunId ?? await archiveEnqueueRunId(now);

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

  // Cooldown: skip schools whose most recent terminal row has an
  // outcome whose archive cadence window hasn't elapsed yet.
  // PR 2 expanded this from a single hardcoded check on
  // unchanged_verified to a per-outcome policy:
  //   successful outcome → 7d year-round
  //   auth_walled_*      → 90d (rarely change)
  //   dead_url           → 14d (schools fix broken URLs in days/weeks)
  //   no_pdfs_found      → 14d
  //   transient          → 0d  (retry next cron — design intent)
  //   etc. (see DEFAULT_COOLDOWN_DAYS in _shared/probe_outcome.ts)
  //
  // Operator override: ?force_recheck=true bypasses cooldown for this
  // run only. ?cooldown_days=N (single integer) overrides ALL outcome
  // windows uniformly — useful for "process everything that hasn't
  // been touched in N days regardless of category."
  // force_school via archive-process always bypasses the queue and
  // is unaffected.
  const forceRecheck = url.searchParams.get("force_recheck") === "true";
  let uniformDays: number | null;
  try {
    uniformDays = parseCooldownDaysOverride(
      url.searchParams.get("cooldown_days"),
    );
  } catch (error) {
    return json({ error: (error as Error).message }, 400);
  }

  const inCooldown = new Set<string>();
  if (!forceRecheck) {
    // Pull the most-recent terminal row per school across both done
    // (success outcomes) and failed_permanent (failure outcomes). The RPC
    // performs DISTINCT ON in PostgreSQL. Calls are chunked by the current
    // schools.yaml corpus so each response stays below PostgREST's row cap and
    // directory-only queue history is never transferred.
    //
    // Bounds:
    //   (a) processed_at is bounded by the larger of 95 days or the operator's
    //       uniform override. The normal longest cooldown is 90d
    //       (auth_walled_*); anything older is out of cooldown.
    //       Without this bound the query would scan the full archive_queue
    //       history forever.
    const lookbackDays = Math.max(95, uniformDays ?? 0);
    const coolWindowMs = lookbackDays * 24 * 60 * 60 * 1000;
    const coolWindowCutoff = new Date(
      now.getTime() - coolWindowMs,
    ).toISOString();
    const terminalRows: Array<{
      school_id: string;
      processed_at: string;
      last_outcome: string;
    }> = [];
    let terminalError: string | null = null;
    const schoolIds = allSchools.map((school) => school.id);
    const rpcChunkSize = 500;
    for (let offset = 0; offset < schoolIds.length; offset += rpcChunkSize) {
      const { data, error } = await supabase.rpc(
        "latest_archive_terminal_rows",
        {
          p_since: coolWindowCutoff,
          p_school_ids: schoolIds.slice(offset, offset + rpcChunkSize),
        },
      );
      if (error) {
        terminalError = error.message;
        break;
      }
      terminalRows.push(...(data ?? []));
    }

    if (terminalError) {
      // Don't fail enqueue on cooldown query failure — log and proceed
      // with no cooldown applied. Better to over-enqueue than to skip
      // a fresh batch entirely.
      logEvent({
        event: "cooldown_query_failed",
        run_id: runId,
        error: terminalError,
      });
    } else {
      const latestBySchool = new Map<
        string,
        { processed_at: string; last_outcome: ProbeOutcome }
      >();
      for (const row of terminalRows) {
        latestBySchool.set(row.school_id, {
          processed_at: row.processed_at,
          last_outcome: row.last_outcome as ProbeOutcome,
        });
      }
      const nowMs = now.getTime();
      for (const [schoolId, latest] of latestBySchool) {
        const cooldownDays = uniformDays ??
          archiveCooldownDaysForOutcome(latest.last_outcome, now);
        if (cooldownDays <= 0) continue;
        const elapsedMs = nowMs - new Date(latest.processed_at).getTime();
        if (elapsedMs < cooldownDays * 24 * 60 * 60 * 1000) {
          inCooldown.add(schoolId);
        }
      }
    }
  }

  const rows = allSchools
    .filter((s) => !inCooldown.has(s.id))
    .map((s) => ({
      enqueued_run_id: runId,
      school_id: s.id,
      school_name: s.name,
      // archive_queue.cds_url_hint is the DB column (denormalized
      // cache); ArchivableSchool.discovery_seed_url is the runtime
      // field after PR 5's rename. Map at the boundary.
      cds_url_hint: s.discovery_seed_url,
      status: "ready" as const,
    }));

  if (inCooldown.size > 0) {
    logEvent({
      event: "cooldown_skipped",
      run_id: runId,
      uniform_cooldown_days: uniformDays,
      skipped: inCooldown.size,
    });
  }

  // Bulk insert with onConflict + ignoreDuplicates so re-running within the
  // same UTC day is a no-op on rows that already landed. A new daily run_id
  // makes the per-outcome cooldown the sole cross-day scheduling policy.
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

  // The RPC inserts under the database's one-active-row-per-school invariant
  // and uses ON CONFLICT DO NOTHING. That makes the active-row check atomic:
  // same-day retries and cross-day invocations during a worker outage cannot
  // build duplicate ready/processing rows.
  const { data: enqueuedCount, error } = await supabase.rpc(
    "enqueue_archive_queue_rows",
    { p_rows: rows },
  );

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

  const enqueued = Number(enqueuedCount ?? 0);
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
function isServiceRoleAuth(
  authHeader: string,
  envServiceRoleKey: string,
): boolean {
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
