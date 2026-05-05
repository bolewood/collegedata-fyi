// cds_documents + cds_artifacts access for the archive pipeline. Every
// function here takes a SupabaseClient and returns typed results. The
// decision logic lives in archive.ts — this module is just the data-access
// layer.

import { SupabaseClient } from "jsr:@supabase/supabase-js@2";

export interface CdsDocumentRow {
  id: string;
  school_id: string;
  school_name: string;
  sub_institutional: string | null;
  cds_year: string;
  source_url: string | null;
  source_format: string | null;
  source_sha256: string | null;
  source_page_count: number | null;
  participation_status: string;
  discovered_at: string | null;
  last_verified_at: string | null;
  removed_at: string | null;
  extraction_status: string;
}

export interface CdsArtifactRow {
  id: string;
  document_id: string;
  kind: string;
  producer: string;
  producer_version: string;
  schema_version: string | null;
  storage_path: string;
  sha256: string | null;
  created_at: string;
}

export const ARCHIVER_PRODUCER = "archiver";
export const ARCHIVER_VERSION = "0.1";

// The `.is('sub_institutional', null)` filter is the codex finding #4 fix:
// PostgREST rejects `.eq(..., null)` for NULL comparisons and needs the
// explicit IS-NULL operator.
export async function fetchDocumentForSchoolYear(
  client: SupabaseClient,
  schoolId: string,
  cdsYear: string,
): Promise<CdsDocumentRow | null> {
  const { data, error } = await client
    .from("cds_documents")
    .select("*")
    .eq("school_id", schoolId)
    .eq("cds_year", cdsYear)
    .is("sub_institutional", null)
    .maybeSingle();
  if (error) throw new Error(`fetchDocumentForSchoolYear: ${error.message}`);
  return (data as CdsDocumentRow | null) ?? null;
}

// Most recent row (by cds_year desc) for a school with no sub-institutional
// variant. Used by the "hint resolution failed" path to mark only the
// current-year row as removed, not every historical year the school has
// ever published. Returns null if the school has never been archived.
export async function fetchMostRecentDocumentForSchool(
  client: SupabaseClient,
  schoolId: string,
): Promise<CdsDocumentRow | null> {
  const { data, error } = await client
    .from("cds_documents")
    .select("*")
    .eq("school_id", schoolId)
    .is("sub_institutional", null)
    .order("cds_year", { ascending: false })
    .limit(1)
    .maybeSingle();
  if (error) throw new Error(`fetchMostRecentDocumentForSchool: ${error.message}`);
  return (data as CdsDocumentRow | null) ?? null;
}

export async function fetchLatestSourceArtifact(
  client: SupabaseClient,
  documentId: string,
): Promise<CdsArtifactRow | null> {
  const { data, error } = await client
    .from("cds_artifacts")
    .select("*")
    .eq("document_id", documentId)
    .eq("kind", "source")
    .order("created_at", { ascending: false })
    .limit(1)
    .maybeSingle();
  if (error) throw new Error(`fetchLatestSourceArtifact: ${error.message}`);
  return (data as CdsArtifactRow | null) ?? null;
}

export interface InsertFreshArgs {
  school_id: string;
  school_name: string;
  ipeds_id?: string | null;
  cds_year: string;
  source_url: string;
  source_sha256: string;
  storage_path: string;
  source_page_count?: number | null;
  // Where this document came from — defaults to school_direct for the
  // normal resolver path. Mirror ingests pass their own value
  // (e.g., 'mirror_college_transitions'). See migration
  // 20260419100000_source_provenance.sql for the enum domain.
  source_provenance?: string;
  // HTTP Last-Modified header at fetch time, parsed to ISO 8601. Null
  // when the source host doesn't emit one. Persisted into
  // cds_documents.source_http_last_modified by migration
  // 20260505160000_archive_observability.sql for freshness audits.
  source_http_last_modified?: string | null;
}

// Used for the "no existing row" branch. Inserts cds_documents + the first
// cds_artifacts(kind='source') row. Returns the new document id so the
// caller can reference it in logs.
export async function insertFreshDocument(
  client: SupabaseClient,
  args: InsertFreshArgs,
): Promise<string> {
  const nowIso = new Date().toISOString();
  const { data: doc, error: docErr } = await client
    .from("cds_documents")
    .insert({
      school_id: args.school_id,
      school_name: args.school_name,
      ipeds_id: args.ipeds_id ?? null,
      cds_year: args.cds_year,
      sub_institutional: null,
      source_url: args.source_url,
      source_sha256: args.source_sha256,
      source_page_count: args.source_page_count ?? null,
      participation_status: "published",
      discovered_at: nowIso,
      last_verified_at: nowIso,
      extraction_status: "extraction_pending",
      source_provenance: args.source_provenance ?? "school_direct",
      source_http_last_modified: args.source_http_last_modified ?? null,
    })
    .select("id")
    .single();
  if (docErr) throw new Error(`insertFreshDocument (document): ${docErr.message}`);

  const { error: artErr } = await client.from("cds_artifacts").insert({
    document_id: doc.id,
    kind: "source",
    producer: ARCHIVER_PRODUCER,
    producer_version: ARCHIVER_VERSION,
    storage_path: args.storage_path,
    sha256: args.source_sha256,
  });
  if (artErr) throw new Error(`insertFreshDocument (artifact): ${artErr.message}`);

  return doc.id as string;
}

export interface RefreshArgs {
  document_id: string;
  source_url: string;
  source_sha256: string;
  storage_path: string;
  // Provenance of the NEW bytes being written. If the caller is the
  // normal resolver path, this defaults to 'school_direct' and
  // correctly upgrades a row that was previously mirror-provenance.
  // Mirror ingests never call refresh (they only insert fresh), so a
  // refresh always means "the school's current file, or an explicit
  // operator override" which is school_direct by definition unless
  // otherwise stated.
  source_provenance?: string;
  // HTTP Last-Modified at refresh time. Captured fresh on every
  // re-archive; clears Stale value if the school stopped emitting
  // the header. Null is the correct "not reported by host" value.
  source_http_last_modified?: string | null;
}

// Used when a new SHA is seen for an existing (school, year) row.
// Update cds_documents FIRST (points at the new canonical version and flips
// extraction_status back to extraction_pending), then insert the new
// cds_artifacts row.
//
// The ordering matters for crash safety: if the document update commits
// and the artifact insert fails, the next run's fetchLatestSourceArtifact
// still returns the old artifact, the SHA comparison is still "different",
// and the refresh branch re-runs idempotently. A prior ordering that wrote
// the artifact first would leave cds_documents.source_url/source_sha256
// stale forever if the document update failed, because subsequent runs
// would match the new artifact's SHA and take the "unchanged" branch
// without touching cds_documents.
export async function refreshDocumentWithNewSha(
  client: SupabaseClient,
  args: RefreshArgs,
): Promise<void> {
  const { error: updErr } = await client
    .from("cds_documents")
    .update({
      source_url: args.source_url,
      source_sha256: args.source_sha256,
      last_verified_at: new Date().toISOString(),
      extraction_status: "extraction_pending",
      participation_status: "published",
      removed_at: null,
      source_provenance: args.source_provenance ?? "school_direct",
      source_http_last_modified: args.source_http_last_modified ?? null,
    })
    .eq("id", args.document_id);
  if (updErr) {
    throw new Error(`refreshDocumentWithNewSha (document): ${updErr.message}`);
  }

  const { error: artErr } = await client.from("cds_artifacts").insert({
    document_id: args.document_id,
    kind: "source",
    producer: ARCHIVER_PRODUCER,
    producer_version: ARCHIVER_VERSION,
    storage_path: args.storage_path,
    sha256: args.source_sha256,
  });
  if (artErr) {
    throw new Error(`refreshDocumentWithNewSha (artifact): ${artErr.message}`);
  }
}

// Bumps last_verified_at and optionally updates source_url if the school
// moved the file to a new location but republished identical bytes. The
// sourceUrl parameter is always passed; supabase-js's update will no-op at
// the storage layer when the value matches what's already there.
export async function bumpVerified(
  client: SupabaseClient,
  documentId: string,
  sourceUrl: string,
): Promise<void> {
  const { error } = await client
    .from("cds_documents")
    .update({
      last_verified_at: new Date().toISOString(),
      source_url: sourceUrl,
      removed_at: null,
    })
    .eq("id", documentId);
  if (error) throw new Error(`bumpVerified: ${error.message}`);
}

// Repair case: same SHA, but the Storage object is missing. Re-upload has
// already happened by the time this is called. Write a new artifact row
// pointing at the same SHA-addressed path so the history has a record that
// we had to repair, bump verified, and refresh source_url in case it moved.
// Do NOT flip extraction_status — the canonical bytes didn't change, just
// their existence.
export async function recordRepair(
  client: SupabaseClient,
  documentId: string,
  sourceSha256: string,
  storagePath: string,
  sourceUrl: string,
): Promise<void> {
  const { error: artErr } = await client.from("cds_artifacts").insert({
    document_id: documentId,
    kind: "source",
    producer: ARCHIVER_PRODUCER,
    producer_version: ARCHIVER_VERSION,
    storage_path: storagePath,
    sha256: sourceSha256,
    notes: { repair: true, repaired_at: new Date().toISOString() },
  });
  if (artErr) throw new Error(`recordRepair (artifact): ${artErr.message}`);
  await bumpVerified(client, documentId, sourceUrl);
}

// Mark a previously-archived document as removed upstream. Idempotent:
// calling this twice is a no-op on the second call because the .is filter
// on removed_at IS NULL matches zero rows. Does NOT touch participation_status
// because a single failed hint fetch is not the same as a school publicly
// refusing to publish; operators can promote removed rows to 'withdrawn' via
// a separate review process after observing sustained removal.
export async function recordRemoval(
  client: SupabaseClient,
  documentId: string,
  reason: string,
): Promise<void> {
  const { error } = await client
    .from("cds_documents")
    .update({ removed_at: new Date().toISOString() })
    .eq("id", documentId)
    .is("removed_at", null);
  if (error) {
    throw new Error(`recordRemoval (${reason}): ${error.message}`);
  }
}
