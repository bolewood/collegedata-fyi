// One-school archive pipeline. Used by both archive-process (queue consumer,
// production cron) and discover (HTTP dev entry for resolver iteration).
// All the business logic for "resolve → download → SHA → upsert + upload"
// lives here; the callers are thin wrappers that handle their own invocation
// context and finally-block accounting.

import { SupabaseClient } from "jsr:@supabase/supabase-js@2";
import {
  isSafeUrl,
  resolveCdsForSchool,
  ResolveProbeData,
  ResolveResult,
  USER_AGENT,
} from "./resolve.ts";
import { inferHosting, type HostingInference } from "./hosting.ts";
import {
  bumpVerified,
  fetchDocumentForSchoolYear,
  fetchLatestSourceArtifact,
  fetchMostRecentDocumentForSchool,
  insertFreshDocument,
  recordRemoval,
  recordRepair,
  refreshDocumentWithNewSha,
} from "./db.ts";
import {
  buildSourcePath,
  extForResponse,
  MAX_SOURCE_BYTES,
  objectExists,
  uploadSource,
} from "./storage.ts";
import { authWallOutcome, ProbeOutcome } from "./probe_outcome.ts";

// Transient: worth retrying next tick or next cron. Counts against the
// MAX_ATTEMPTS budget in archive-process. Carries a typed
// ProbeOutcome category so archive-process can record it in
// archive_queue.last_outcome without string-matching.
export class TransientError extends Error {
  category: ProbeOutcome;
  constructor(message: string, category: ProbeOutcome = "transient") {
    super(message);
    this.name = "TransientError";
    this.category = category;
  }
}

// Permanent: retrying cannot help. The row is marked failed_permanent and
// left for manual inspection. Carries a typed ProbeOutcome category
// (see probe_outcome.ts for the enum) so the failure mode is queryable.
export class PermanentError extends Error {
  category: ProbeOutcome;
  constructor(message: string, category: ProbeOutcome = "permanent_other") {
    super(message);
    this.name = "PermanentError";
    this.category = category;
  }
}

export type ArchiveAction =
  | "inserted"
  | "refreshed"
  | "unchanged_verified"
  | "unchanged_repaired"
  | "marked_removed";

// Per-candidate outcome. ADR 0007 Stage B fans the archiver out into
// one cds_documents row per CDS-ish anchor found on a landing page
// (Lafayette-style multi-year archives), so a single school run can
// produce multiple CandidateOutcomes.
export interface CandidateOutcome {
  action: ArchiveAction;
  document_id: string | null;
  cds_year: string | null;
  source_sha256: string | null;
  resolved_url: string | null;
  storage_path: string | null;
}

// Aggregate outcome for one archiveOneSchool call. `candidates` is the
// non-empty list of per-candidate outcomes on success, or a single
// marked_removed candidate on upstream_gone. `action` is a rollup:
// the action of the first candidate when all candidates took the same
// action, or the most specific one (inserted > refreshed >
// unchanged_repaired > unchanged_verified > marked_removed) when
// candidates differ — the log event only has room for one label.
//
// `outcome` is the structured ProbeOutcome the school-level attempt
// produced. For successful runs, outcome === action (since all
// ArchiveAction values are also ProbeOutcome values). For failed
// runs, archiveOneSchool throws and the caller (archive-process)
// reads the category from PermanentError/TransientError; this field
// is unused on the throw path.
export interface ArchiveOutcome {
  action: ArchiveAction;
  outcome: ProbeOutcome;
  candidates: CandidateOutcome[];
  // Back-compat fields for callers that expected a single outcome.
  // Populated from candidates[0] when there is exactly one candidate,
  // and left null when there are multiple (consumers should iterate
  // `candidates` in that case).
  document_id: string | null;
  cds_year: string | null;
  source_sha256: string | null;
  resolved_url: string | null;
  storage_path: string | null;
}

// SchoolInput is the runtime shape passed into archiveOneSchool.
// `discovery_seed_url` is the URL the resolver fetches first (then walks
// up / probes well-known paths). `browse_url`, when set, is the
// human-friendly URL contributors use — distinct from the resolver
// seed so direct-PDF schools can still expose a browseable IR landing
// page to humans without confusing the resolver.
//
// PR 5 of the URL hint refactor renamed cds_url_hint → discovery_seed_url.
// archive_queue.cds_url_hint (the DB column) keeps its name as a
// denormalized cache; the rename happens at the boundary in
// archive-process and archive-enqueue.
export interface SchoolInput {
  school_id: string;
  school_name: string;
  discovery_seed_url: string;
  browse_url?: string;
}

// Rollup precedence: when a multi-candidate school has a mix of
// actions, the log event's single `action` field reports the most
// specific one. Order here is "most meaningful" first.
const ACTION_PRIORITY: ArchiveAction[] = [
  "inserted",
  "refreshed",
  "unchanged_repaired",
  "unchanged_verified",
  "marked_removed",
];

function rollupAction(candidates: CandidateOutcome[]): ArchiveAction {
  if (candidates.length === 0) {
    throw new Error("rollupAction called with empty candidates");
  }
  const present = new Set(candidates.map((c) => c.action));
  for (const a of ACTION_PRIORITY) {
    if (present.has(a)) return a;
  }
  return candidates[0].action;
}

// When all candidates in a multi-candidate run fail permanently,
// promote the most specific category (anything more specific than
// permanent_other) so the school-level error preserves diagnostic
// signal. If every candidate failed with permanent_other, that's
// what we surface. If the failures span categories (rare; auth-walled
// hosts usually fail uniformly), pick the first non-generic one.
const GENERIC_CATEGORIES: Set<ProbeOutcome> = new Set([
  "permanent_other",
  "transient",
]);

function pickAggregateCategory(categories: ProbeOutcome[]): ProbeOutcome {
  if (categories.length === 0) return "permanent_other";
  const specific = categories.find((c) => !GENERIC_CATEGORIES.has(c));
  return specific ?? categories[0];
}

const DOWNLOAD_TIMEOUT_MS = 30_000;

// Feature flag for hosting-environment observations. The plan calls
// for this gate so the riskiest part of PR 4 (resolver writes a new
// row per probe) can be reverted without a code rollback if it
// causes problems in production. Default off; flip to "true" once
// the table has been migrated and a smoke test on a single school
// looks clean.
function hostingObservationsEnabled(): boolean {
  return (Deno.env.get("HOSTING_OBSERVATIONS_ENABLED") ?? "").toLowerCase() === "true";
}

// Record a single school_hosting_observations row. Best-effort: any
// error is swallowed and logged so observation failures never break
// archiving. The whole point of the env var is the safety net here.
async function recordHostingObservation(
  supabase: SupabaseClient,
  school: SchoolInput,
  probe: ResolveProbeData | undefined,
  resolvedDocs: { url: string }[] | undefined,
  outcome: ProbeOutcome,
  outcomeReason: string | null,
): Promise<void> {
  if (!hostingObservationsEnabled()) return;

  // Build the inferHosting input from whatever we have. archive.ts
  // is the natural orchestration point because it has both probe (from
  // resolver) and resolvedDocs (also from resolver). The hint URL is
  // always available from school.discovery_seed_url (renamed from
  // cds_url_hint in PR 5 of the URL hint refactor).
  const inference: HostingInference = inferHosting({
    hintUrl: school.discovery_seed_url,
    finalUrl: probe?.finalUrl,
    contentType: probe?.contentType,
    headers: probe?.headers,
    resolvedDocs,
    anchorCount: probe?.anchorCount,
    bodyLength: probe?.bodyLength,
  });

  // Truncate outcome_reason so a chatty error message doesn't bloat
  // the table. 200 chars matches the categoriseLegacyError pattern
  // window; longer is the underlying last_error in archive_queue.
  const reasonTrunc = outcomeReason && outcomeReason.length > 200
    ? outcomeReason.slice(0, 200)
    : outcomeReason;

  try {
    const { error } = await supabase
      .from("school_hosting_observations")
      .insert({
        school_id: school.school_id,
        observation_source: "resolver",
        seed_url: school.discovery_seed_url,
        origin_domain: inference.origin_domain,
        final_url_host: inference.final_url_host,
        cms: inference.cms,
        file_storage: inference.file_storage,
        auth_required: inference.auth_required,
        rendering: inference.rendering,
        waf: inference.waf,
        outcome,
        outcome_reason: reasonTrunc,
      });
    if (error) {
      console.log(JSON.stringify({
        ts: new Date().toISOString(),
        fn: "archive.ts",
        event: "hosting_observation_insert_failed",
        school_id: school.school_id,
        error: error.message,
      }));
    }
  } catch (e) {
    console.log(JSON.stringify({
      ts: new Date().toISOString(),
      fn: "archive.ts",
      event: "hosting_observation_threw",
      school_id: school.school_id,
      error: (e as Error).message,
    }));
  }
}

export async function archiveOneSchool(
  supabase: SupabaseClient,
  school: SchoolInput,
): Promise<ArchiveOutcome> {
  // 1. Resolve the hint. Post-Stage-B the resolver returns docs[] —
  //    one CDS-ish anchor per historical year for schools that expose
  //    a multi-year landing page, one row for the direct-doc case.
  const result = await resolveCdsForSchool(school.discovery_seed_url);

  // Branch on the resolver's discriminated union. Each non-resolved
  // kind triggers an observation write before throwing so failure
  // probes show up in school_hosting_observations alongside successes.
  switch (result.kind) {
    case "resolved":
      break;
    case "upstream_gone":
      // upstream_gone is handled below by handleUpstreamGone which
      // returns ArchiveOutcome; observation is recorded inside that
      // path.
      return handleUpstreamGone(supabase, school, result);
    case "transient": {
      await recordHostingObservation(
        supabase, school, result.probe, undefined, "transient", result.reason,
      );
      throw new TransientError(`resolve transient: ${result.reason}`, "transient");
    }
    case "blocked_url": {
      // blocked_url has no probe (we never made the request). Skip the
      // observation — there's nothing to observe.
      throw new PermanentError(`resolve blocked: ${result.reason}`, "blocked_url");
    }
    case "unsupported_content": {
      await recordHostingObservation(
        supabase, school, result.probe, undefined, "wrong_content_type", result.reason,
      );
      throw new PermanentError(`resolve unsupported: ${result.reason}`, "wrong_content_type");
    }
    case "no_cds_found": {
      await recordHostingObservation(
        supabase, school, result.probe, undefined, "no_pdfs_found", result.reason,
      );
      throw new PermanentError(`resolve no cds found: ${result.reason}`, "no_pdfs_found");
    }
  }

  if (result.docs.length === 0) {
    throw new PermanentError(
      "resolver returned resolved kind with empty docs[]",
      "permanent_other",
    );
  }

  // 2. Archive each candidate in order. PermanentError on one candidate
  //    (typically a 404 on a stale URL) is caught and skipped so the
  //    other candidates still land — e.g., Cornell's direct-PDF hint
  //    is stale but the well-known-paths fallback yields 17 valid years.
  //    TransientError still propagates school-level so the whole batch
  //    retries on the next run. Processing is serial, not parallel:
  //    parallelism would race against the existing-row lookup and
  //    risk double-inserting rows for the same (school, cds_year)
  //    before either upload completes.
  const candidates: CandidateOutcome[] = [];
  const skipped: { url: string; reason: string; category: ProbeOutcome }[] = [];
  for (const resolved of result.docs) {
    try {
      candidates.push(await archiveOneCandidate(supabase, school, resolved));
    } catch (e) {
      if (e instanceof PermanentError) {
        skipped.push({
          url: resolved.url,
          reason: e.message,
          category: e.category,
        });
        continue;
      }
      throw e;
    }
  }

  // If ALL candidates failed permanently, surface as school-level
  // PermanentError so the queue row lands in failed_permanent instead
  // of silently succeeding with zero rows. Promote the most specific
  // category from the per-candidate failures so the aggregated error
  // doesn't lose its diagnostic value (e.g., 6 candidates all
  // auth_walled_microsoft → school-level outcome should be
  // auth_walled_microsoft, not permanent_other).
  if (candidates.length === 0) {
    const reasons = skipped.map((s) => `${s.url}: ${s.reason}`).join("; ");
    const aggregate = pickAggregateCategory(skipped.map((s) => s.category));
    await recordHostingObservation(
      supabase, school, result.probe, result.docs, aggregate, reasons,
    );
    throw new PermanentError(
      `all ${skipped.length} candidate(s) failed permanently: ${reasons}`,
      aggregate,
    );
  }

  const first = candidates[0];
  const action = rollupAction(candidates);
  // Success path: record observation. resolvedDocs uses the resolver
  // outputs (not the candidates outcomes) so file_storage inference
  // sees ALL candidate URLs, including ones that got skipped due to
  // per-candidate transient errors.
  await recordHostingObservation(
    supabase, school, result.probe, result.docs, action, null,
  );
  return {
    action,
    outcome: action, // ArchiveAction values are valid ProbeOutcome values
    candidates,
    // Back-compat single-candidate fields: populated only when the
    // school yielded one document. Multi-candidate callers should
    // iterate `candidates`.
    document_id: candidates.length === 1 ? first.document_id : null,
    cds_year: candidates.length === 1 ? first.cds_year : null,
    source_sha256: candidates.length === 1 ? first.source_sha256 : null,
    resolved_url: candidates.length === 1 ? first.resolved_url : null,
    storage_path: candidates.length === 1 ? first.storage_path : null,
  };
}

// Operator entry point: archive an explicit list of URLs for a school,
// bypassing the resolver entirely. Used by the manual-urls tooling that
// feeds Playwright-collected anchors directly into the archive pipeline
// when the resolver can't see them (JS-rendered IR pages).
//
// Each URL is treated as an independent candidate. URL→year parsing uses
// the same normalizeYear heuristic as the resolver; filenames are derived
// from the URL path. PermanentError on one candidate is caught and
// skipped (same semantics as the resolver-driven path), so one stale URL
// in the batch doesn't abandon the rest.
// Item accepted by archiveManualUrls: a URL and optional explicit cds_year.
// The caller (typically the Playwright URL collector) knows the year from
// the link text or surrounding page context, which is NOT recoverable from
// opaque share-viewer URLs like Box /s/<id> or Drive /file/d/<id>. If
// `year` is omitted, archiveManualUrls falls back to URL+filename parsing.
export interface ManualUrlItem {
  url: string;
  year?: string;
}

export async function archiveManualUrls(
  supabase: SupabaseClient,
  school: SchoolInput,
  items: (string | ManualUrlItem)[],
  // options.source_provenance lets callers tag the resulting
  // cds_documents row with the right provenance value. Mirror ingest
  // scripts pass 'mirror_college_transitions' (or similar); the
  // default undefined falls through to insertFreshDocument's
  // 'school_direct' default, which is correct for the existing
  // manual_urls.yaml / Playwright-collector call sites where the URLs
  // are the school's own-domain hosts.
  options: { source_provenance?: string } = {},
): Promise<ArchiveOutcome> {
  if (items.length === 0) {
    throw new PermanentError(
      "archiveManualUrls called with empty url list",
      "permanent_other",
    );
  }
  const { normalizeYear } = await import("./year.ts");
  const { UNKNOWN_YEAR_SENTINEL, rewriteBoxUrl, rewriteGoogleDriveUrl } =
    await import("./resolve.ts");

  const candidates: CandidateOutcome[] = [];
  const skipped: { url: string; reason: string; category: ProbeOutcome }[] = [];
  for (const raw of items) {
    const rawUrl = typeof raw === "string" ? raw : raw.url;
    const explicitYear = typeof raw === "string" ? null : (raw.year ?? null);

    // Rewrite share-viewer URLs (Google Drive, Box) into direct-download
    // form before handing to the downloader.
    let url = rewriteGoogleDriveUrl(rawUrl);
    url = rewriteBoxUrl(url);

    let parsedUrl: URL;
    try {
      parsedUrl = new URL(url);
    } catch {
      skipped.push({
        url: rawUrl,
        reason: "invalid URL",
        category: "blocked_url",
      });
      continue;
    }
    const filename = decodeURIComponent(
      parsedUrl.pathname.split("/").filter(Boolean).pop() ?? "",
    );
    // Year precedence: explicit (from caller) → pre-rewrite URL → post-rewrite
    // URL → filename. Box/Drive opaque-id URLs yield nothing on their own,
    // so the explicit year is the authoritative source for those.
    const year =
      explicitYear ??
      normalizeYear(rawUrl) ??
      normalizeYear(url) ??
      normalizeYear(filename);
    try {
      candidates.push(await archiveOneCandidate(supabase, school, {
        url,
        cds_year: year ?? UNKNOWN_YEAR_SENTINEL,
      }, { source_provenance: options.source_provenance }));
    } catch (e) {
      if (e instanceof PermanentError) {
        skipped.push({
          url: rawUrl,
          reason: e.message,
          category: e.category,
        });
        continue;
      }
      throw e;
    }
  }

  if (candidates.length === 0) {
    const reasons = skipped.map((s) => `${s.url}: ${s.reason}`).join("; ");
    throw new PermanentError(
      `all ${skipped.length} manual url(s) failed: ${reasons}`,
      pickAggregateCategory(skipped.map((s) => s.category)),
    );
  }

  const first = candidates[0];
  const action = rollupAction(candidates);
  return {
    action,
    outcome: action,
    candidates,
    document_id: candidates.length === 1 ? first.document_id : null,
    cds_year: candidates.length === 1 ? first.cds_year : null,
    source_sha256: candidates.length === 1 ? first.source_sha256 : null,
    resolved_url: candidates.length === 1 ? first.resolved_url : null,
    storage_path: candidates.length === 1 ? first.storage_path : null,
  };
}

// Archive a single resolved candidate. Shared by archiveOneSchool for
// both the single-candidate direct-doc path and the multi-candidate
// landing-page fan-out. This is the body of the pre-Stage-B
// archiveOneSchool lifted as-is; the outer function just loops.
async function archiveOneCandidate(
  supabase: SupabaseClient,
  school: SchoolInput,
  resolved: { url: string; cds_year: string },
  // options.source_provenance propagates into insertFreshDocument and
  // refreshDocumentWithNewSha. Defaults to undefined (→ 'school_direct'
  // via db.ts default), which is correct for the resolver-driven path
  // that archiveOneSchool uses. Mirror ingests pass
  // { source_provenance: 'mirror_college_transitions' } through
  // archiveManualUrls.
  options: { source_provenance?: string } = {},
): Promise<CandidateOutcome> {
  // Download with a hard memory + wall clock cap.
  const { bytes, sha256, contentType, finalUrl } = await downloadWithCaps(
    resolved.url,
  );
  // extForResponse tries content-type → URL suffix → magic-byte sniff.
  // The magic-byte path is what rescues Google Drive (serves everything
  // as application/octet-stream) and any other host whose download
  // endpoint doesn't set a canonical Content-Type.
  const ext = extForResponse(contentType, finalUrl, bytes);
  if (!ext) {
    // Auth-wall detection: when a school's CDS lives behind SSO, the
    // download follow-redirects path lands on an SSO HTML page (e.g.,
    // login.microsoftonline.com/<tenant>/saml2). The bytes are HTML, not
    // PDF, so extForResponse rejects them — but the *reason* matters.
    // An auth-walled school is structurally different from a school
    // whose link 404s, and downstream cooldown / hosting policy needs
    // to distinguish them.
    const authCategory = authWallOutcome(finalUrl);
    if (authCategory) {
      throw new PermanentError(
        `auth-walled: download for ${resolved.url} redirected to ${finalUrl}`,
        authCategory,
      );
    }
    throw new PermanentError(
      `unknown content type for ${finalUrl}: ${contentType || "(none)"}, bytes do not match PDF/XLSX/DOCX magic`,
      "wrong_content_type",
    );
  }

  // Use the post-redirect URL when persisting provenance. A school may
  // rewrite its hint to a short CDN URL that 302s to the real file; we
  // want to remember the final location, not the entry point.
  const sourceUrl = finalUrl;
  const storagePath = buildSourcePath(
    school.school_id,
    resolved.cds_year,
    sha256,
    ext,
  );

  // Look up existing state for this (school, cds_year) combo.
  const existing = await fetchDocumentForSchoolYear(
    supabase,
    school.school_id,
    resolved.cds_year,
  );

  // Branch A: no existing row → fresh insert.
  if (!existing) {
    await ensureObjectUploaded(supabase, storagePath, bytes, ext);
    const docId = await insertFreshDocument(supabase, {
      school_id: school.school_id,
      school_name: school.school_name,
      cds_year: resolved.cds_year,
      source_url: sourceUrl,
      source_sha256: sha256,
      storage_path: storagePath,
      source_provenance: options.source_provenance,
    });
    return {
      action: "inserted",
      document_id: docId,
      cds_year: resolved.cds_year,
      source_sha256: sha256,
      resolved_url: sourceUrl,
      storage_path: storagePath,
    };
  }

  const latestArtifact = await fetchLatestSourceArtifact(supabase, existing.id);

  // Branch B: existing row, same SHA. Verify the Storage object is actually
  // present before declaring "unchanged" — otherwise a deleted blob would
  // silently live on as a row pointing nowhere.
  if (latestArtifact && latestArtifact.sha256 === sha256) {
    const present = await objectExists(supabase, latestArtifact.storage_path);
    if (present) {
      await bumpVerified(supabase, existing.id, sourceUrl);
      return {
        action: "unchanged_verified",
        document_id: existing.id,
        cds_year: resolved.cds_year,
        source_sha256: sha256,
        resolved_url: sourceUrl,
        storage_path: latestArtifact.storage_path,
      };
    }
    // Repair: re-upload to the same SHA-addressed path. Idempotent.
    await ensureObjectUploaded(supabase, latestArtifact.storage_path, bytes, ext);
    await recordRepair(
      supabase,
      existing.id,
      sha256,
      latestArtifact.storage_path,
      sourceUrl,
    );
    return {
      action: "unchanged_repaired",
      document_id: existing.id,
      cds_year: resolved.cds_year,
      source_sha256: sha256,
      resolved_url: sourceUrl,
      storage_path: latestArtifact.storage_path,
    };
  }

  // Branch C: existing row, new SHA. Upload the new bytes to their own
  // SHA-addressed path, then update cds_documents, then insert a new
  // cds_artifacts row. The document-first ordering is self-healing: if
  // the artifact insert crashes after the document update commits, the
  // next run's fetchLatestSourceArtifact still returns the old artifact
  // (old sha), the sha comparison takes the refresh branch again, and
  // we idempotently re-apply the missing insert. A prior ordering that
  // wrote the artifact first could leave cds_documents stale forever
  // because the next run would see "same sha" and take the unchanged
  // branch.
  await ensureObjectUploaded(supabase, storagePath, bytes, ext);
  await refreshDocumentWithNewSha(supabase, {
    document_id: existing.id,
    source_url: sourceUrl,
    source_sha256: sha256,
    storage_path: storagePath,
    source_provenance: options.source_provenance,
  });
  return {
    action: "refreshed",
    document_id: existing.id,
    cds_year: resolved.cds_year,
    source_sha256: sha256,
    resolved_url: sourceUrl,
    storage_path: storagePath,
  };
}

async function handleUpstreamGone(
  supabase: SupabaseClient,
  school: SchoolInput,
  result: Extract<ResolveResult, { kind: "upstream_gone" }>,
): Promise<ArchiveOutcome> {
  const mostRecent = await fetchMostRecentDocumentForSchool(
    supabase,
    school.school_id,
  );
  if (mostRecent) {
    await recordRemoval(supabase, mostRecent.id, result.reason);
  }
  const candidate: CandidateOutcome = {
    action: "marked_removed",
    document_id: mostRecent?.id ?? null,
    cds_year: mostRecent?.cds_year ?? null,
    source_sha256: null,
    resolved_url: null,
    storage_path: null,
  };
  await recordHostingObservation(
    supabase,
    school,
    result.probe,
    undefined,
    "dead_url", // upstream_gone is the dead-url failure mode
    result.reason,
  );
  return {
    action: "marked_removed",
    outcome: "marked_removed",
    candidates: [candidate],
    document_id: candidate.document_id,
    cds_year: candidate.cds_year,
    source_sha256: null,
    resolved_url: null,
    storage_path: null,
  };
}

async function ensureObjectUploaded(
  supabase: SupabaseClient,
  path: string,
  bytes: Uint8Array,
  ext: string,
): Promise<void> {
  if (await objectExists(supabase, path)) return;
  try {
    await uploadSource(supabase, path, bytes, ext);
  } catch (e) {
    throw new TransientError((e as Error).message, "transient");
  }
}

interface DownloadResult {
  bytes: Uint8Array;
  sha256: string;
  contentType: string;
  finalUrl: string;
}

async function downloadWithCaps(url: string): Promise<DownloadResult> {
  if (!isSafeUrl(url)) {
    // Resolver should already have rejected this, but double-check at the
    // actual download boundary so there is no single-point-of-failure in
    // SSRF defense.
    throw new PermanentError(`download blocked unsafe URL: ${url}`, "blocked_url");
  }

  let resp: Response;
  try {
    resp = await fetch(url, {
      headers: { "User-Agent": USER_AGENT },
      signal: AbortSignal.timeout(DOWNLOAD_TIMEOUT_MS),
      redirect: "follow",
    });
  } catch (e) {
    throw new TransientError(`download fetch failed: ${(e as Error).message}`, "transient");
  }

  if (!isSafeUrl(resp.url)) {
    throw new PermanentError(
      `download redirect target blocked as unsafe URL: ${resp.url}`,
      "blocked_url",
    );
  }

  if (resp.status === 404 || resp.status === 410) {
    throw new PermanentError(`download HTTP ${resp.status} at ${url}`, "dead_url");
  }
  if (!resp.ok) {
    throw new TransientError(`download HTTP ${resp.status} at ${url}`, "transient");
  }

  const contentType = resp.headers.get("content-type") ?? "";

  // Preflight on Content-Length so a 5 GB file bounces early with a clean
  // permanent error instead of burning wall clock on a doomed download.
  const contentLength = resp.headers.get("content-length");
  if (contentLength) {
    const n = parseInt(contentLength, 10);
    if (!Number.isNaN(n) && n > MAX_SOURCE_BYTES) {
      throw new PermanentError(
        `file exceeds ${MAX_SOURCE_BYTES} bytes (Content-Length ${n}) at ${url}`,
        "file_too_large",
      );
    }
  }

  const reader = resp.body?.getReader();
  if (!reader) throw new TransientError(`no response body at ${url}`, "transient");

  // Wrap the streaming read in try/catch/finally. A mid-stream abort
  // (timeout signal, connection reset) would otherwise surface as a raw
  // DOMException, bypassing the TransientError/PermanentError classifier
  // that the queue worker's retry logic depends on. Also cancels the
  // reader in all exit paths so the connection is released promptly.
  const chunks: Uint8Array[] = [];
  let total = 0;
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      if (!value) continue;
      total += value.byteLength;
      if (total > MAX_SOURCE_BYTES) {
        throw new PermanentError(
          `file exceeds ${MAX_SOURCE_BYTES} bytes (streamed) at ${url}`,
          "file_too_large",
        );
      }
      chunks.push(value);
    }
  } catch (e) {
    if (e instanceof PermanentError) throw e;
    throw new TransientError(`download read failed: ${(e as Error).message}`, "transient");
  } finally {
    try { await reader.cancel(); } catch { /* ignore */ }
  }

  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) {
    bytes.set(chunk, offset);
    offset += chunk.byteLength;
  }

  const hashBuf = await crypto.subtle.digest("SHA-256", bytes);
  const hashBytes = new Uint8Array(hashBuf);
  const sha256 = Array.from(hashBytes)
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");

  return { bytes, sha256, contentType, finalUrl: resp.url };
}
