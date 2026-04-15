// One-school archive pipeline. Used by both archive-process (queue consumer,
// production cron) and discover (HTTP dev entry for resolver iteration).
// All the business logic for "resolve → download → SHA → upsert + upload"
// lives here; the callers are thin wrappers that handle their own invocation
// context and finally-block accounting.

import { SupabaseClient } from "jsr:@supabase/supabase-js@2";
import {
  isSafeUrl,
  resolveCdsForSchool,
  ResolveResult,
  USER_AGENT,
} from "./resolve.ts";
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

// Transient: worth retrying next tick or next cron. Counts against the
// MAX_ATTEMPTS budget in archive-process.
export class TransientError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "TransientError";
  }
}

// Permanent: retrying cannot help. The row is marked failed_permanent and
// left for manual inspection.
export class PermanentError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "PermanentError";
  }
}

export type ArchiveAction =
  | "inserted"
  | "refreshed"
  | "unchanged_verified"
  | "unchanged_repaired"
  | "marked_removed";

export interface ArchiveOutcome {
  action: ArchiveAction;
  document_id: string | null;
  cds_year: string | null;
  source_sha256: string | null;
  resolved_url: string | null;
  storage_path: string | null;
}

export interface SchoolInput {
  school_id: string;
  school_name: string;
  cds_url_hint: string;
}

const DOWNLOAD_TIMEOUT_MS = 30_000;

export async function archiveOneSchool(
  supabase: SupabaseClient,
  school: SchoolInput,
): Promise<ArchiveOutcome> {
  // 1. Resolve the hint to a direct document URL + cds_year.
  const result = await resolveCdsForSchool(school.cds_url_hint);
  switch (result.kind) {
    case "resolved":
      break;
    case "upstream_gone":
      return handleUpstreamGone(supabase, school, result);
    case "transient":
      throw new TransientError(`resolve transient: ${result.reason}`);
    case "blocked_url":
      throw new PermanentError(`resolve blocked: ${result.reason}`);
    case "unsupported_content":
      throw new PermanentError(`resolve unsupported: ${result.reason}`);
    case "no_cds_found":
      throw new PermanentError(`resolve no cds found: ${result.reason}`);
  }
  const resolved = result.doc;

  // 2. Download the resolved document with a hard memory + wall clock cap.
  const { bytes, sha256, contentType, finalUrl } = await downloadWithCaps(
    resolved.url,
  );
  // extForResponse tries content-type → URL suffix → magic-byte sniff.
  // The magic-byte path is what rescues Google Drive (serves everything
  // as application/octet-stream) and any other host whose download
  // endpoint doesn't set a canonical Content-Type.
  const ext = extForResponse(contentType, finalUrl, bytes);
  if (!ext) {
    throw new PermanentError(
      `unknown content type for ${finalUrl}: ${contentType || "(none)"}, bytes do not match PDF/XLSX/DOCX magic`,
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

  // 3. Look up existing state.
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
  return {
    action: "marked_removed",
    document_id: mostRecent?.id ?? null,
    cds_year: mostRecent?.cds_year ?? null,
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
    throw new TransientError((e as Error).message);
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
    throw new PermanentError(`download blocked unsafe URL: ${url}`);
  }

  let resp: Response;
  try {
    resp = await fetch(url, {
      headers: { "User-Agent": USER_AGENT },
      signal: AbortSignal.timeout(DOWNLOAD_TIMEOUT_MS),
      redirect: "follow",
    });
  } catch (e) {
    throw new TransientError(`download fetch failed: ${(e as Error).message}`);
  }

  if (!isSafeUrl(resp.url)) {
    throw new PermanentError(
      `download redirect target blocked as unsafe URL: ${resp.url}`,
    );
  }

  if (resp.status === 404 || resp.status === 410) {
    throw new PermanentError(`download HTTP ${resp.status} at ${url}`);
  }
  if (!resp.ok) {
    throw new TransientError(`download HTTP ${resp.status} at ${url}`);
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
      );
    }
  }

  const reader = resp.body?.getReader();
  if (!reader) throw new TransientError(`no response body at ${url}`);

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
        );
      }
      chunks.push(value);
    }
  } catch (e) {
    if (e instanceof PermanentError) throw e;
    throw new TransientError(`download read failed: ${(e as Error).message}`);
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
