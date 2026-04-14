// archive-process — queue consumer for the archive pipeline.
//
// Invoked every 30 seconds by pg_cron (PR 5). Each invocation processes
// exactly one school: claim a ready row from archive_queue, run the shared
// archiveOneSchool pipeline, and mark the row terminal in a finally block
// so a crashed processor cannot wedge the queue. This one-row-per-call
// shape is what keeps us inside Supabase Edge Function limits (400s wall
// clock, 256 MB memory, 2s CPU); the per-school work of fetch+hash+upload
// is well under all three.
//
// Also supports operator backfill via ?force_school=yale. That path skips
// the queue entirely, looks up the school in schools.yaml, and runs the
// pipeline directly. Use it when you need to re-archive a specific school
// outside the monthly cron cadence.
//
// Auth: verify_jwt=true in config.toml lets Supabase validate that a JWT
// is present. This handler additionally verifies the bearer token matches
// SUPABASE_SERVICE_ROLE_KEY exactly. Cron invocations pass the service
// role key via the net.http_post Authorization header; operators do the
// same from curl. Any other authenticated caller gets 403.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient, type SupabaseClient } from "jsr:@supabase/supabase-js@2";

import {
  archiveOneSchool,
  ArchiveOutcome,
  PermanentError,
  TransientError,
} from "../_shared/archive.ts";
import { fetchSchoolsYaml, filterArchivable } from "../_shared/schools.ts";

// Relaxed client typing. supabase-js v2's strict generics collapse to never
// when no Database type parameter is supplied, which breaks .update() with
// inferred payload types. Carrying SupabaseClient<any> through the helpers
// restores ergonomic typing for this project.
// deno-lint-ignore no-explicit-any
type Client = SupabaseClient<any, any, any>;

const MAX_ATTEMPTS = 3;

interface ArchiveQueueRow {
  id: string;
  enqueued_run_id: string;
  school_id: string;
  school_name: string;
  cds_url_hint: string;
  status: string;
  attempts: number;
  last_error: string | null;
  enqueued_at: string;
  claimed_at: string | null;
  processed_at: string | null;
}

Deno.serve(async (req: Request) => {
  // ── Auth: require the service role key via Bearer ────────────────────
  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!supabaseUrl || !serviceRoleKey) {
    return json({ error: "missing supabase env" }, 500);
  }

  const auth = req.headers.get("Authorization") ?? "";
  if (!isServiceRoleAuth(auth, serviceRoleKey)) {
    return json({ error: "unauthorized" }, 403);
  }

  // deno-lint-ignore no-explicit-any
  const supabase: Client = createClient<any, any, any>(supabaseUrl, serviceRoleKey);
  const url = new URL(req.url);
  const forceSchool = url.searchParams.get("force_school");

  if (forceSchool) {
    return await runForceSchool(supabase, forceSchool);
  }

  return await runQueueClaim(supabase);
});

// ── Queue mode ──────────────────────────────────────────────────────────
async function runQueueClaim(
  supabase: Client,
): Promise<Response> {
  const { data: claimed, error: claimErr } = await supabase
    .rpc("claim_archive_queue_row");

  if (claimErr) {
    logEvent({ event: "claim_error", error: claimErr.message });
    return json({ error: `claim failed: ${claimErr.message}` }, 500);
  }

  if (!claimed) {
    logEvent({ event: "queue_drained" });
    return json({ status: "queue_drained" });
  }

  const row = claimed as ArchiveQueueRow;
  const started = Date.now();
  // attempts is already incremented by claim_archive_queue_row() so that a
  // worker which crashes before its finally block still consumes an attempt.
  // We use the row's value directly rather than adding 1 here.
  const attempts = row.attempts;
  // claim_archive_queue_row() always sets claimed_at to now() on the row it
  // returns, so a null here would indicate RPC-contract corruption; bail
  // loud rather than silently writing a bad guard.
  if (!row.claimed_at) {
    logEvent({
      event: "unexpected_null_claimed_at",
      id: row.id,
      school_id: row.school_id,
    });
    return json({ error: "RPC returned row with null claimed_at" }, 500);
  }
  const claimLease: string = row.claimed_at;
  let finalStatus: "ready" | "done" | "failed_permanent" = "ready";
  let finalError: string | null = null;
  let outcome: ArchiveOutcome | null = null;

  logEvent({
    event: "claim",
    id: row.id,
    school_id: row.school_id,
    attempts,
  });

  try {
    outcome = await archiveOneSchool(supabase, {
      school_id: row.school_id,
      school_name: row.school_name,
      cds_url_hint: row.cds_url_hint,
    });
    finalStatus = "done";
  } catch (e) {
    const err = e as Error;
    if (err instanceof PermanentError) {
      finalStatus = "failed_permanent";
      finalError = `PermanentError: ${err.message}`;
    } else if (err instanceof TransientError) {
      if (attempts >= MAX_ATTEMPTS) {
        finalStatus = "failed_permanent";
        finalError =
          `exhausted ${MAX_ATTEMPTS} attempts (last: TransientError: ${err.message})`;
      } else {
        finalStatus = "ready";
        finalError = `attempt ${attempts} TransientError: ${err.message}`;
      }
    } else {
      // Unclassified error. Treat as transient so a one-off blip doesn't
      // immediately burn the row, but cap the retries same as TransientError.
      if (attempts >= MAX_ATTEMPTS) {
        finalStatus = "failed_permanent";
        finalError =
          `exhausted ${MAX_ATTEMPTS} attempts (last: ${err.name}: ${err.message})`;
      } else {
        finalStatus = "ready";
        finalError = `attempt ${attempts} ${err.name}: ${err.message}`;
      }
    }
  } finally {
    // ALWAYS write the terminal state. If this update itself fails (DB
    // transient), the row stays status=processing with claimed_at set and
    // the 10-minute visibility timeout in claim_archive_queue_row() will
    // re-pick it on a later tick.
    //
    // attempts is NOT written here — claim_archive_queue_row() already
    // incremented it when the row was leased.
    //
    // The .eq('claimed_at', claimLease) guard prevents a stale owner from
    // overwriting a newer owner's state. Scenario: this worker hangs past
    // the 10-minute visibility timeout, another worker reclaims the row
    // (updating claimed_at to a newer value), we finally reach this finally
    // block and try to write our terminal state. The guard makes our
    // UPDATE affect 0 rows because claimLease no longer matches the row's
    // current claimed_at. In the current deploy, edge function wall clock
    // (400s) is already shorter than the visibility timeout (600s) so the
    // window is closed by construction — this guard is defense in depth
    // against any future wall-clock bump or operator misconfiguration.
    const update: Record<string, unknown> = {
      status: finalStatus,
      last_error: finalError,
    };
    if (finalStatus === "ready") {
      // Release the claim AND push the row to the tail of the queue by
      // bumping enqueued_at. Without the bump, ORDER BY enqueued_at ASC
      // would re-pick the same flaky row every 30s, head-of-line blocking
      // younger rows behind a persistent failure.
      update.claimed_at = null;
      update.enqueued_at = new Date().toISOString();
    }
    if (finalStatus === "done" || finalStatus === "failed_permanent") {
      update.processed_at = new Date().toISOString();
    }
    const { error: updErr } = await supabase
      .from("archive_queue")
      .update(update)
      .eq("id", row.id)
      .eq("claimed_at", claimLease);
    if (updErr) {
      logEvent({
        event: "terminal_update_failed",
        id: row.id,
        school_id: row.school_id,
        intended_status: finalStatus,
        error: updErr.message,
      });
    }
  }

  const duration_ms = Date.now() - started;
  logEvent({
    event: "completed",
    id: row.id,
    school_id: row.school_id,
    attempts,
    final_status: finalStatus,
    action: outcome?.action ?? null,
    duration_ms,
    error: finalError,
  });

  return json({
    status: finalStatus,
    school_id: row.school_id,
    attempts,
    action: outcome?.action ?? null,
    error: finalError,
  });
}

// ── Operator backfill mode ─────────────────────────────────────────────
// Skips archive_queue entirely. Looks up the school in schools.yaml and
// runs the pipeline directly. Returns the outcome or the error verbatim.
async function runForceSchool(
  supabase: Client,
  schoolId: string,
): Promise<Response> {
  const { entries: allSchools } = await fetchSchoolsYaml();
  const archivable = filterArchivable(allSchools);
  const school = archivable.find((s) => s.id === schoolId);

  if (!school) {
    return json({
      error: `school '${schoolId}' not found in archivable schools`,
      hint:
        "Active scrape_policy + non-null cds_url_hint + no sub_institutions. Columbia and other multi-CDS schools are excluded in V1.",
    }, 404);
  }

  const started = Date.now();
  logEvent({
    event: "force_school_start",
    school_id: school.id,
  });

  try {
    const outcome = await archiveOneSchool(supabase, {
      school_id: school.id,
      school_name: school.name,
      cds_url_hint: school.cds_url_hint,
    });
    logEvent({
      event: "force_school_completed",
      school_id: school.id,
      action: outcome.action,
      duration_ms: Date.now() - started,
    });
    return json({ mode: "force_school", school_id: school.id, outcome });
  } catch (e) {
    const err = e as Error;
    logEvent({
      event: "force_school_failed",
      school_id: school.id,
      error_class: err.name,
      error: err.message,
      duration_ms: Date.now() - started,
    });
    return json({
      mode: "force_school",
      school_id: school.id,
      error_class: err.name,
      error: err.message,
    }, 500);
  }
}

// Structured log line. Supabase's edge function dashboard captures stdout
// so operators can grep event names ("claim", "completed", "force_school_*",
// "queue_drained", "terminal_update_failed") when inspecting a cron run.
function logEvent(payload: Record<string, unknown>): void {
  console.log(JSON.stringify({
    ts: new Date().toISOString(),
    fn: "archive-process",
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

// Accept both service-role credential formats. Supabase projects have been
// migrating from the legacy JWT service_role key (eyJ... ~220 chars) to the
// new opaque sb_secret_... format (~40 chars). Both are valid service-role
// credentials at the Supabase gateway (verify_jwt=true will accept either),
// but the env var injected into edge functions only contains ONE of them —
// the current canonical form, which on a rotated project is sb_secret_.
//
// Strict string-compare against that env var rejects callers who legitimately
// have the legacy JWT. This function normalizes by:
//   1. Exact match against the injected env var (handles the new sb_secret_
//      case and also older projects where the env var is still a legacy JWT).
//   2. Legacy-JWT path: decode the base64 payload (Supabase already verified
//      the signature cryptographically at verify_jwt=true; we just need to
//      read the claim) and accept only role="service_role".
//
// An attacker cannot forge a legacy JWT with role=service_role because the
// signature check at the gateway would reject it — we rely on Supabase's
// upstream verification rather than re-verifying here.
function isServiceRoleAuth(authHeader: string, envServiceRoleKey: string): boolean {
  if (!authHeader.startsWith("Bearer ")) return false;
  const token = authHeader.slice(7).trim();
  if (!token) return false;

  if (token === envServiceRoleKey) return true;

  // Legacy JWT path: three base64url segments joined by dots. Payload is
  // segment 1. Role claim must equal "service_role".
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
