// directory-enqueue — operator-triggered seeder for Scorecard-only
// institutions (PRD 015 M2).
//
// Companion to archive-enqueue. Both write to archive_queue, but they
// pull from different universes:
//
//   archive-enqueue     reads tools/finder/schools.yaml. Daily cron.
//                       Source of truth for hand-curated, actively
//                       scraped schools. Source = 'schools_yaml'.
//
//   directory-enqueue   (this function) reads institution_directory.
//                       Operator-triggered, no cron. Targets the Scorecard
//                       universe of in-scope schools that have not yet
//                       been probed. Source = 'institution_directory'.
//
// PRD 015's honesty constraint is what makes this milestone necessary:
// the coverage table (M3) cannot move a school from `not_checked` to
// `no_public_cds_found` without an actual resolver attempt. Adding the
// whole Scorecard universe to search before probing them would surface
// thousands of false "no public CDS found" claims. directory-enqueue is
// the path that turns `not_checked` rows into real archive_queue
// attempts so M3's status precedence has real data to work with.
//
// Deliberate design choices:
//
//   1. No cron. Operator passes ?limit=N every run. The PRD pins this
//      ("Keep run limits operator-controlled; no full discovery drain
//      in PR CI"). The first few runs against the ~5,500 unprobed
//      Scorecard schools should be small enough to triage outcomes
//      before scaling up.
//
//   2. limit is required. Defaults to 0 means "do nothing" rather than
//      "drain everything." Forces the operator to think about batch
//      size every time.
//
//   3. Selection prioritizes by undergraduate_enrollment DESC. High-
//      enrollment schools deliver the most product value when their
//      coverage status flips off `not_checked`, and are the schools
//      where missing-CDS visibility matters most.
//
//   4. Schools already covered by schools.yaml are skipped. archive-enqueue
//      owns those; double-enqueueing would race the cooldown logic.
//      Excluded by joining institution_slug_crosswalk.
//
//   5. cooldown / in-flight / has-cds checks all use the existing
//      archive_queue + cds_documents tables. directory-sourced rows
//      flow through the same archive-process worker as schools_yaml
//      rows; no worker changes were required.
//
// Auth: same isServiceRoleAuth pattern as archive-enqueue. verify_jwt=true
// gatekeeps at the Supabase layer; the handler additionally checks the
// bearer token matches SUPABASE_SERVICE_ROLE_KEY.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient, SupabaseClient } from "jsr:@supabase/supabase-js@2";

import {
  DirectoryRow,
  LatestTerminal,
  normalizeSeedUrl,
  selectCandidates,
} from "./select.ts";
import { ProbeOutcome } from "../_shared/probe_outcome.ts";

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

  const url = new URL(req.url);
  const params = parseParams(url);
  if ("error" in params) {
    return json({ error: params.error }, 400);
  }

  const supabase = createClient(supabaseUrl, serviceRoleKey);
  const runId = params.runId ?? crypto.randomUUID();
  const started = Date.now();

  logEvent({
    event: "enqueue_start",
    run_id: runId,
    limit: params.limit,
    min_enrollment: params.minEnrollment,
    state: params.state,
    force_recheck: params.forceRecheck,
    dry_run: params.dryRun,
  });

  // ─── Load all five inputs in parallel ─────────────────────────────
  // institution_directory has ~6K rows; the other lookups are smaller.
  // Parallel fetches keep the function comfortably under the 400s edge
  // function budget even on the first cold run.
  const [
    directoryResult,
    crosswalkResult,
    cdsResult,
    inFlightResult,
    terminalResult,
  ] = await Promise.all([
    loadDirectoryRows(supabase, params),
    loadSchoolsYamlIpeds(supabase),
    loadSchoolsWithCds(supabase),
    loadInFlightSchools(supabase),
    loadLatestTerminals(supabase),
  ]);

  for (const r of [directoryResult, crosswalkResult, cdsResult, inFlightResult, terminalResult]) {
    if ("error" in r) {
      logEvent({ event: "load_failed", run_id: runId, ...r });
      return json({ error: `load failed: ${r.error}`, run_id: runId }, 500);
    }
  }

  const result = selectCandidates({
    rows: (directoryResult as { rows: DirectoryRow[] }).rows,
    schoolsYamlIpeds: (crosswalkResult as { ipeds: Set<string> }).ipeds,
    schoolsWithCds: (cdsResult as { schoolIds: Set<string> }).schoolIds,
    inFlightSchools: (inFlightResult as { schoolIds: Set<string> }).schoolIds,
    latestTerminals: (terminalResult as { latest: Map<string, LatestTerminal> }).latest,
    minEnrollment: params.minEnrollment,
    state: params.state,
    forceRecheck: params.forceRecheck,
    uniformCooldownDays: params.uniformCooldownDays,
    limit: params.limit,
    now: new Date(),
  });

  // Build queue rows. Drop any whose website_url cannot be normalized
  // into a fetchable seed — bucket those under no_website_url so the
  // skip-reason summary stays honest. selectCandidates already dropped
  // empty website_url; this catches rows where the value parsed as
  // garbage (e.g., literal "Not Available").
  const skippedNormalize: string[] = [];
  const rowsToInsert = result.selected.flatMap((c) => {
    const seed = normalizeSeedUrl(c.website_url);
    if (!seed) {
      skippedNormalize.push(c.school_id);
      return [];
    }
    return [{
      enqueued_run_id: runId,
      school_id: c.school_id,
      school_name: c.school_name,
      cds_url_hint: seed,
      status: "ready" as const,
      source: "institution_directory" as const,
    }];
  });

  const skipSummary = Object.fromEntries(result.skipped);
  if (skippedNormalize.length > 0) {
    skipSummary["unparseable_website_url"] = skippedNormalize.length;
  }

  if (params.dryRun) {
    logEvent({
      event: "dry_run_completed",
      run_id: runId,
      considered: result.considered,
      would_enqueue: rowsToInsert.length,
      skipped: skipSummary,
      duration_ms: Date.now() - started,
    });
    return json({
      mode: "dry_run",
      run_id: runId,
      considered: result.considered,
      would_enqueue: rowsToInsert.length,
      sample_school_ids: rowsToInsert.slice(0, 25).map((r) => r.school_id),
      skipped: skipSummary,
    });
  }

  if (rowsToInsert.length === 0) {
    logEvent({
      event: "enqueue_completed",
      run_id: runId,
      enqueued: 0,
      skipped: skipSummary,
      duration_ms: Date.now() - started,
    });
    return json({
      mode: "enqueue",
      run_id: runId,
      enqueued: 0,
      considered: result.considered,
      skipped: skipSummary,
      note: "no candidates passed all filters",
    });
  }

  // Bulk insert with onConflict + ignoreDuplicates so re-running with
  // the same run_id is a no-op on rows that already landed. Same
  // retry-safety property as archive-enqueue.
  const { data, error } = await supabase
    .from("archive_queue")
    .upsert(rowsToInsert, {
      onConflict: "enqueued_run_id,school_id",
      ignoreDuplicates: true,
    })
    .select("id");

  if (error) {
    logEvent({
      event: "enqueue_failed",
      run_id: runId,
      intended_count: rowsToInsert.length,
      error: error.message,
    });
    return json({
      error: `enqueue failed: ${error.message}`,
      run_id: runId,
      intended_count: rowsToInsert.length,
    }, 500);
  }

  const enqueued = data?.length ?? 0;
  const skippedExisting = rowsToInsert.length - enqueued;
  logEvent({
    event: "enqueue_completed",
    run_id: runId,
    enqueued,
    skipped_existing: skippedExisting,
    skipped: skipSummary,
    duration_ms: Date.now() - started,
  });

  return json({
    mode: "enqueue",
    run_id: runId,
    enqueued,
    considered: result.considered,
    skipped_existing: skippedExisting,
    skipped: skipSummary,
  });
});

// ─── Param parsing ───────────────────────────────────────────────────

interface Params {
  limit: number;
  minEnrollment: number;
  state: string | null;
  forceRecheck: boolean;
  uniformCooldownDays: number | null;
  dryRun: boolean;
  runId: string | null;
}

function parseParams(url: URL): Params | { error: string } {
  const limitStr = url.searchParams.get("limit");
  if (limitStr === null) {
    return { error: "limit is required (operator must size each batch explicitly)" };
  }
  const limit = parseInt(limitStr, 10);
  if (!Number.isFinite(limit) || limit < 0) {
    return { error: `limit must be a non-negative integer, got '${limitStr}'` };
  }

  const minEnrollmentStr = url.searchParams.get("min_enrollment");
  let minEnrollment = 0;
  if (minEnrollmentStr !== null) {
    const parsed = parseInt(minEnrollmentStr, 10);
    if (!Number.isFinite(parsed) || parsed < 0) {
      return { error: `min_enrollment must be a non-negative integer, got '${minEnrollmentStr}'` };
    }
    minEnrollment = parsed;
  }

  const state = url.searchParams.get("state");
  if (state !== null && !/^[A-Z]{2}$/.test(state)) {
    return { error: `state must be a two-letter uppercase code, got '${state}'` };
  }

  const cooldownStr = url.searchParams.get("cooldown_days");
  let uniformCooldownDays: number | null = null;
  if (cooldownStr !== null) {
    const parsed = parseInt(cooldownStr, 10);
    if (!Number.isFinite(parsed) || parsed < 0) {
      return { error: `cooldown_days must be a non-negative integer, got '${cooldownStr}'` };
    }
    uniformCooldownDays = parsed;
  }

  return {
    limit,
    minEnrollment,
    state,
    forceRecheck: url.searchParams.get("force_recheck") === "true",
    uniformCooldownDays,
    dryRun: url.searchParams.get("dry_run") === "true",
    runId: url.searchParams.get("run_id"),
  };
}

// ─── Loaders ─────────────────────────────────────────────────────────

async function loadDirectoryRows(
  supabase: SupabaseClient,
  params: Params,
): Promise<{ rows: DirectoryRow[] } | { error: string }> {
  // Pull all in-scope rows with a website_url. We do operator filters
  // (state, min_enrollment) in TS since selectCandidates needs the
  // skip-reason counts to reflect each filter.
  let query = supabase
    .from("institution_directory")
    .select(
      "ipeds_id, school_id, school_name, state, website_url, undergraduate_enrollment",
    )
    .eq("in_scope", true)
    .not("website_url", "is", null)
    .limit(20000);
  // PostgREST default is 1,000 rows — well under the ~5,500 in-scope
  // directory rows we expect after schools.yaml exclusions. Bump to
  // 20K to comfortably cover Scorecard's full Title-IV universe.
  if (params.state) {
    // Pre-filter at the DB to keep the response small when an operator
    // targets one state. selectCandidates still re-applies the filter
    // for skip-reason accounting, but on a smaller candidate pool
    // there's nothing to count there.
    query = query.eq("state", params.state);
  }
  const { data, error } = await query;
  if (error) return { error: error.message };
  return { rows: (data ?? []) as DirectoryRow[] };
}

async function loadSchoolsYamlIpeds(
  supabase: SupabaseClient,
): Promise<{ ipeds: Set<string> } | { error: string }> {
  const { data, error } = await supabase
    .from("institution_slug_crosswalk")
    .select("ipeds_id")
    .eq("source", "schools_yaml")
    .limit(20000);
  if (error) return { error: error.message };
  return { ipeds: new Set((data ?? []).map((r) => r.ipeds_id as string)) };
}

async function loadSchoolsWithCds(
  supabase: SupabaseClient,
): Promise<{ schoolIds: Set<string> } | { error: string }> {
  // cds_documents holds one row per (school, sub-institutional, year).
  // We just need the distinct school_ids; PostgREST has no DISTINCT but
  // dedup'ing in JS over a few thousand rows is trivial.
  const { data, error } = await supabase
    .from("cds_documents")
    .select("school_id")
    .limit(20000);
  if (error) return { error: error.message };
  return { schoolIds: new Set((data ?? []).map((r) => r.school_id as string)) };
}

async function loadInFlightSchools(
  supabase: SupabaseClient,
): Promise<{ schoolIds: Set<string> } | { error: string }> {
  const { data, error } = await supabase
    .from("archive_queue")
    .select("school_id")
    .in("status", ["ready", "processing"])
    .limit(20000);
  if (error) return { error: error.message };
  return { schoolIds: new Set((data ?? []).map((r) => r.school_id as string)) };
}

async function loadLatestTerminals(
  supabase: SupabaseClient,
): Promise<{ latest: Map<string, LatestTerminal> } | { error: string }> {
  // Same 95-day window archive-enqueue uses. Longest cooldown is 90d
  // (auth_walled_*); rows older than that can never be in cooldown.
  const coolWindowMs = 95 * 24 * 60 * 60 * 1000;
  const cutoff = new Date(Date.now() - coolWindowMs).toISOString();
  const { data, error } = await supabase
    .from("archive_queue")
    .select("school_id, processed_at, last_outcome")
    .in("status", ["done", "failed_permanent"])
    .not("last_outcome", "is", null)
    .not("processed_at", "is", null)
    .gte("processed_at", cutoff)
    .limit(20000);
  if (error) return { error: error.message };
  const latest = new Map<string, LatestTerminal>();
  for (const row of data ?? []) {
    const r = row as { school_id: string; processed_at: string; last_outcome: string };
    const prior = latest.get(r.school_id);
    if (!prior || r.processed_at > prior.processed_at) {
      latest.set(r.school_id, {
        school_id: r.school_id,
        processed_at: r.processed_at,
        last_outcome: r.last_outcome as ProbeOutcome,
      });
    }
  }
  return { latest };
}

// ─── Helpers ─────────────────────────────────────────────────────────

function logEvent(payload: Record<string, unknown>): void {
  console.log(JSON.stringify({
    ts: new Date().toISOString(),
    fn: "directory-enqueue",
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

// Accept both service-role credential formats during the Supabase key
// rotation transition window. Mirrors archive-enqueue exactly.
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
