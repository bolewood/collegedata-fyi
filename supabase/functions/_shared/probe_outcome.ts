// ProbeOutcome — the structured category of a school-level archive
// attempt. Superset of ArchiveAction (which records per-candidate
// success). Surfaces the failure modes that today live in free-text
// last_error and that tools/data_quality/force_resolve_missing.py
// reverse-engineers via string matching.
//
// Source-of-truth motivation: the 448-school force-resolve batch on
// 2026-04-18 produced 12 distinct outcome categories from the Python
// categoriser. Moving that classification into the pipeline makes
// observability first-class — cooldown policies, audit dashboards,
// and the eventual school_hosting table can all read a structured
// field instead of pattern-matching error strings.
//
// Values must stay in sync with the CHECK constraint on
// archive_queue.last_outcome (see migration
// 20260418230000_probe_outcome_categories.sql).

export type ProbeOutcome =
  // Success — per-candidate ArchiveAction values, rolled up at the
  // school level. When archiveOneSchool returns a successful
  // ArchiveOutcome, outcome equals the rollup'd action.
  | "inserted"
  | "refreshed"
  | "unchanged_verified"
  | "unchanged_repaired"
  | "marked_removed"
  // Failure — populated when archiveOneSchool throws. archive-process
  // reads PermanentError.category / TransientError.category and writes
  // it to archive_queue.last_outcome.
  | "dead_url" //               4xx-deletes (404/410) at resolve or download
  | "auth_walled_microsoft" //  redirect to login.microsoftonline.com
  | "auth_walled_okta" //       redirect to *.okta.com
  | "auth_walled_google" //     redirect to accounts.google.com
  | "no_pdfs_found" //          landing parsed but zero CDS-ish anchors
  | "wrong_content_type" //     non-PDF/XLSX/DOCX response (often HTML)
  | "file_too_large" //         exceeds MAX_SOURCE_BYTES
  | "blocked_url" //            SSRF guard or unsafe URL filter rejected the URL
  | "transient" //              5xx, timeout, network blip; will retry next cron
  | "permanent_other" //        unclassified permanent failure (should be rare)
  | "bot_challenge"; //         Cloudflare/Imperva WAF returned a verification
//                              challenge instead of the file. Distinct from
//                              wrong_content_type (school link returns
//                              generic HTML) and auth_walled_* (real SSO).
//                              Manual download via tools/finder/manual_urls.yaml
//                              is the expected mitigation. Surfaced via
//                              public.bot_challenged_documents view +
//                              ops-extraction-worker GitHub-issue notification.

export const PROBE_OUTCOME_VALUES: ProbeOutcome[] = [
  "inserted",
  "refreshed",
  "unchanged_verified",
  "unchanged_repaired",
  "marked_removed",
  "dead_url",
  "auth_walled_microsoft",
  "auth_walled_okta",
  "auth_walled_google",
  "no_pdfs_found",
  "wrong_content_type",
  "file_too_large",
  "blocked_url",
  "transient",
  "permanent_other",
  "bot_challenge",
];

// Hosts that, when reached as the final URL of a redirect chain,
// indicate the school's CDS files are behind a third-party SSO. The
// resolver/downloader can detect these by inspecting finalUrl after
// fetch redirects settle. Each maps to a specific ProbeOutcome so
// downstream policy (e.g., a 90-day cooldown for auth-walled schools
// vs 30 for unchanged_verified) can differentiate.
export function authWallOutcome(finalUrl: string): ProbeOutcome | null {
  let host: string;
  try {
    host = new URL(finalUrl).hostname.toLowerCase();
  } catch {
    return null;
  }
  if (host === "login.microsoftonline.com" || host.endsWith(".microsoftonline.com")) {
    return "auth_walled_microsoft";
  }
  if (host.endsWith(".okta.com") || host === "okta.com") {
    return "auth_walled_okta";
  }
  if (host === "accounts.google.com" || host === "myaccount.google.com") {
    return "auth_walled_google";
  }
  return null;
}

// Suggested cooldown window per outcome, in days. Used by
// archive-enqueue to skip schools whose last attempt landed in a
// stable failure state where retrying soon is unlikely to help.
//
// Values reflect product judgment, not load-bearing magic numbers:
//   - unchanged_verified: 30d — the file changes maybe once a year;
//     re-checking monthly was the original waste signal.
//   - auth_walled_*: 90d — schools rarely un-wall their archives;
//     re-check quarterly.
//   - dead_url: 14d — schools fix broken URLs in days/weeks; check
//     more often than auth-walled but not every month.
//   - no_pdfs_found / wrong_content_type: 14d — landing pages
//     change content; worth re-checking sooner than auth-walled.
//   - transient: 0 (no cooldown) — these retry next cron by design.
//   - permanent_other / blocked_url / file_too_large: 30d — stable
//     enough to throttle but worth re-evaluating monthly.
//   - inserted/refreshed/unchanged_repaired: 0 — success outcomes
//     other than unchanged_verified mean we did meaningful work; no
//     cooldown.
//
// archive-enqueue's existing 30d default still applies to
// unchanged_verified for back-compat with PR 1; this map will be
// consulted by a future cooldown policy upgrade.
export const DEFAULT_COOLDOWN_DAYS: Record<ProbeOutcome, number> = {
  inserted: 0,
  refreshed: 0,
  unchanged_verified: 30,
  unchanged_repaired: 0,
  marked_removed: 14, // re-check in case the school re-publishes
  dead_url: 14,
  auth_walled_microsoft: 90,
  auth_walled_okta: 90,
  auth_walled_google: 90,
  no_pdfs_found: 14,
  wrong_content_type: 14,
  file_too_large: 30,
  blocked_url: 30,
  transient: 0,
  permanent_other: 30,
  // bot_challenge: 7d. Long enough that the daily extraction cron does not
  // re-fire identical GitHub issues; short enough that a school's WAF policy
  // change is picked up within a week. The mitigation (manual upload) takes
  // operator-time, not cron-time, so the cooldown isn't really about backoff
  // — it's about how often we want to surface the same "still blocked" fact.
  bot_challenge: 7,
};

// Best-effort categorisation of pre-existing free-text error messages
// for the migration backfill. Each pattern reflects a string actually
// observed in the 2026-04-18 force-resolve batch JSONL output. New
// errors thrown after PR 2 carry their category directly via the
// .category field on PermanentError/TransientError; this helper exists
// only to retrofit historical archive_queue.last_error rows.
export function categoriseLegacyError(
  errorMessage: string,
): ProbeOutcome | null {
  if (!errorMessage) return null;
  const m = errorMessage.toLowerCase();

  // Auth wall — finalUrl host appears inside the error text emitted
  // by downloadWithCaps's "unknown content type for ${finalUrl}"
  // throw, so we can detect it from the string.
  if (m.includes("login.microsoftonline.com") || m.includes("/saml")) {
    return "auth_walled_microsoft";
  }
  if (m.includes(".okta.com")) return "auth_walled_okta";
  if (m.includes("accounts.google.com")) return "auth_walled_google";

  // Bot-challenge — match BEFORE generic HTTP-status patterns so a 403
  // from Cloudflare lands as bot_challenge instead of being mis-bucketed
  // as transient. Patterns reflect the canonical strings emitted by
  // archive.ts when WAF detection fires plus the body markers Cloudflare
  // and Imperva inject into challenge responses.
  if (
    m.includes("bot challenge") ||
    m.includes("cloudflare bot") ||
    m.includes("imperva bot") ||
    m.includes("just a moment") ||
    m.includes("cf-mitigated") ||
    m.includes("cf-chl-") ||
    m.includes("__cf_chl_") ||
    m.includes("incapsula incident")
  ) {
    return "bot_challenge";
  }

  // HTTP-status-specific
  if (m.includes("http 404") || m.includes("http 410") || m.includes("upstream_gone")) {
    return "dead_url";
  }
  if (
    m.includes("http 5") ||
    m.includes("timeout") ||
    m.includes("transient")
  ) {
    return "transient";
  }

  // Resolver kinds
  if (m.includes("no cds found") || m.includes("no_cds_found") || m.includes("no anchors")) {
    return "no_pdfs_found";
  }
  if (m.includes("unsupported") || m.includes("magic") || m.includes("content type")) {
    return "wrong_content_type";
  }
  if (m.includes("blocked") || m.includes("unsafe url")) {
    return "blocked_url";
  }
  if (m.includes("exceeds") && m.includes("bytes")) {
    return "file_too_large";
  }

  // Aggregated permanent failures (e.g. "all 6 candidate(s) failed permanently:")
  // contain sub-errors from each candidate. The most informative bucket is
  // typically auth_walled or dead_url; if those didn't match, fall through.
  return "permanent_other";
}
