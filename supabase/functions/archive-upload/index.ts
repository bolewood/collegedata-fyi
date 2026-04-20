// archive-upload — operator endpoint for uploading a CDS file directly
// from the operator's disk. Used when the public file is behind a WAF,
// an auth wall, a JS dropdown, or some other obstacle the resolver
// can't punch through. The operator downloads the PDF in their browser,
// runs tools/upload/upload.py, and we archive it with
// source_provenance='operator_manual' (or whatever the caller passes,
// within the allowlist).
//
// Auth: same pattern as archive-process — verify_jwt=true at the
// Supabase layer plus an in-handler service-role check. This is NOT
// the public upload pathway (see docs/backlog.md entry "Public CDS
// upload form"). That needs moderation, captcha, and trust-model
// design. This endpoint is operator-only and trusts the caller.
//
// Request: multipart/form-data with fields:
//   school_id          (required) — schools.yaml slug
//   cds_year           (required) — 'YYYY-YY' (e.g., '2024-25')
//   file               (required) — the PDF/XLSX/DOCX bytes
//   source_url         (optional) — the URL the operator downloaded from,
//                                   for provenance logging
//   source_provenance  (optional) — default 'operator_manual'; must be in
//                                   the schema CHECK allowlist
//   school_name        (optional) — looked up from schools.yaml if missing
//
// Response: same shape as force_urls single-candidate — action +
// document_id + source_sha256 + storage_path.
//
// Semantics:
//   - Magic-byte validation: bytes must be PDF/XLSX/DOCX. HTML or
//     other content rejected with a 400.
//   - Dedup by sha256: if the existing row's artifact has the same
//     sha, return 'unchanged_verified' (no-op).
//   - Same-year replacement: if the (school, year) row exists with a
//     different sha, insert a new artifact AND update cds_documents
//     to point at the new file (refresh semantics).
//   - Never auto-overwrites a school_direct row with an operator_manual
//     upload unless the caller asks. The "school wins" policy from
//     the mirror pipeline applies here too in reverse: the CALLER
//     decides provenance explicitly.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient, type SupabaseClient } from "jsr:@supabase/supabase-js@2";

import {
  fetchDocumentForSchoolYear,
  fetchLatestSourceArtifact,
  insertFreshDocument,
  refreshDocumentWithNewSha,
  recordRepair,
  bumpVerified,
} from "../_shared/db.ts";
import {
  buildSourcePath,
  MAX_SOURCE_BYTES,
  objectExists,
  sniffBytesForExt,
  uploadSource,
} from "../_shared/storage.ts";
import {
  fetchSchoolsYaml,
  resolveSchoolIpedsId,
  resolveSchoolName,
  UnknownSchoolError,
} from "../_shared/schools.ts";

const ALLOWED_PROVENANCE = new Set([
  "school_direct",
  "mirror_college_transitions",
  "operator_manual",
]);

// deno-lint-ignore no-explicit-any
type Client = SupabaseClient<any, any, any>;

Deno.serve(async (req: Request) => {
  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceRoleKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  if (!supabaseUrl || !serviceRoleKey) {
    return json({ error: "missing supabase env" }, 500);
  }

  if (req.method !== "POST") {
    return json({ error: "POST only" }, 405);
  }

  const auth = req.headers.get("Authorization") ?? "";
  if (!isServiceRoleAuth(auth, serviceRoleKey)) {
    return json({ error: "unauthorized" }, 403);
  }

  // deno-lint-ignore no-explicit-any
  const supabase: Client = createClient<any, any, any>(supabaseUrl, serviceRoleKey);

  let form: FormData;
  try {
    form = await req.formData();
  } catch (e) {
    return json({ error: `multipart parse failed: ${(e as Error).message}` }, 400);
  }

  const schoolId = form.get("school_id");
  const cdsYear = form.get("cds_year");
  const file = form.get("file");
  const sourceUrlInput = form.get("source_url");
  const provenanceInput = form.get("source_provenance");
  const schoolNameInput = form.get("school_name");

  if (typeof schoolId !== "string" || !schoolId) {
    return json({ error: "school_id required" }, 400);
  }
  if (typeof cdsYear !== "string" || !cdsYear) {
    return json({ error: "cds_year required (e.g. 2024-25)" }, 400);
  }
  if (!(file instanceof File)) {
    return json({ error: "file field required (multipart)" }, 400);
  }
  const sourceUrl = typeof sourceUrlInput === "string" && sourceUrlInput.length > 0
    ? sourceUrlInput
    : `upload://${schoolId}/${cdsYear}/${file.name || "unknown"}`;
  const provenance = typeof provenanceInput === "string" && ALLOWED_PROVENANCE.has(provenanceInput)
    ? provenanceInput
    : "operator_manual";

  // Read bytes
  const buffer = await file.arrayBuffer();
  const bytes = new Uint8Array(buffer);
  if (bytes.length === 0) {
    return json({ error: "empty file" }, 400);
  }
  if (bytes.length > MAX_SOURCE_BYTES) {
    return json({
      error: `file exceeds MAX_SOURCE_BYTES (${bytes.length} > ${MAX_SOURCE_BYTES})`,
    }, 413);
  }

  // Magic-byte check ONLY — not extForResponse. The upload path must
  // not trust content-type or URL suffix: content-type comes from the
  // client's multipart form (easily forged as application/pdf), and
  // sourceUrl is synthetic ('upload://...') or operator-supplied (they
  // could paste 'example.com/garbage.pdf' and we'd accept anything).
  // The bytes are the only source of truth. Reject if the first 4
  // bytes don't match PDF or ZIP (XLSX/DOCX).
  const ext = sniffBytesForExt(bytes);
  if (!ext) {
    return json({
      error: "uploaded bytes do not match PDF/XLSX/DOCX magic. Content-type and filename are ignored; bytes must match.",
      content_type: file.type,
      size_bytes: bytes.length,
      first_bytes_hex: Array.from(bytes.slice(0, 8))
        .map((b) => b.toString(16).padStart(2, "0")).join(""),
    }, 400);
  }

  // sha256
  const hashBuf = await crypto.subtle.digest("SHA-256", bytes);
  const sha256 = Array.from(new Uint8Array(hashBuf))
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");

  // Resolve school_name — fail-closed via resolveSchoolName(). Rejects
  // unknown school_ids instead of silently stuffing the slug into the
  // display column (the root cause of the 2026-04-20 dedup cleanup; see
  // docs/dedup-plan-20260420.md).
  let schoolName: string;
  try {
    schoolName = await resolveSchoolName(
      schoolId,
      typeof schoolNameInput === "string" ? schoolNameInput : null,
    );
  } catch (e) {
    if (e instanceof UnknownSchoolError) {
      logEvent({
        event: "upload_rejected_unknown_school",
        school_id: schoolId,
        suggestion: e.suggestion,
      });
      return json({
        error: e.message,
        code: e.code,
        suggestion: e.suggestion,
      }, 400);
    }
    throw e;
  }

  const storagePath = buildSourcePath(schoolId, cdsYear, sha256, ext);

  logEvent({
    event: "upload_received",
    school_id: schoolId,
    cds_year: cdsYear,
    sha256,
    size_bytes: bytes.length,
    ext,
    source_provenance: provenance,
  });

  // Look up existing row and branch.
  const existing = await fetchDocumentForSchoolYear(supabase, schoolId, cdsYear);

  // Branch A: no existing row → fresh insert
  if (!existing) {
    await ensureUploaded(supabase, storagePath, bytes, ext);
    const ipedsId = await resolveSchoolIpedsId(schoolId);
    const docId = await insertFreshDocument(supabase, {
      school_id: schoolId,
      school_name: schoolName,
      ipeds_id: ipedsId,
      cds_year: cdsYear,
      source_url: sourceUrl,
      source_sha256: sha256,
      storage_path: storagePath,
      source_provenance: provenance,
    });
    logEvent({ event: "upload_inserted", school_id: schoolId, cds_year: cdsYear, document_id: docId });
    return json({
      action: "inserted",
      document_id: docId,
      cds_year: cdsYear,
      source_sha256: sha256,
      source_url: sourceUrl,
      storage_path: storagePath,
      source_provenance: provenance,
    });
  }

  const latestArtifact = await fetchLatestSourceArtifact(supabase, existing.id);

  // Branch B: same SHA — unchanged (or repair if storage blob missing)
  if (latestArtifact && latestArtifact.sha256 === sha256) {
    const present = await objectExists(supabase, latestArtifact.storage_path);
    if (present) {
      await bumpVerified(supabase, existing.id, sourceUrl);
      logEvent({ event: "upload_unchanged_verified", school_id: schoolId, cds_year: cdsYear });
      return json({
        action: "unchanged_verified",
        document_id: existing.id,
        cds_year: cdsYear,
        source_sha256: sha256,
        source_url: sourceUrl,
        storage_path: latestArtifact.storage_path,
      });
    }
    await ensureUploaded(supabase, latestArtifact.storage_path, bytes, ext);
    await recordRepair(
      supabase,
      existing.id,
      sha256,
      latestArtifact.storage_path,
      sourceUrl,
    );
    logEvent({ event: "upload_unchanged_repaired", school_id: schoolId, cds_year: cdsYear });
    return json({
      action: "unchanged_repaired",
      document_id: existing.id,
      cds_year: cdsYear,
      source_sha256: sha256,
      source_url: sourceUrl,
      storage_path: latestArtifact.storage_path,
    });
  }

  // Branch C: existing row, new SHA → refresh
  await ensureUploaded(supabase, storagePath, bytes, ext);
  await refreshDocumentWithNewSha(supabase, {
    document_id: existing.id,
    source_url: sourceUrl,
    source_sha256: sha256,
    storage_path: storagePath,
    source_provenance: provenance,
  });
  logEvent({ event: "upload_refreshed", school_id: schoolId, cds_year: cdsYear });
  return json({
    action: "refreshed",
    document_id: existing.id,
    cds_year: cdsYear,
    source_sha256: sha256,
    source_url: sourceUrl,
    storage_path: storagePath,
    source_provenance: provenance,
  });
});

async function ensureUploaded(
  supabase: Client,
  path: string,
  bytes: Uint8Array,
  ext: string,
): Promise<void> {
  if (await objectExists(supabase, path)) return;
  await uploadSource(supabase, path, bytes, ext);
}

function logEvent(payload: Record<string, unknown>): void {
  console.log(JSON.stringify({
    ts: new Date().toISOString(),
    fn: "archive-upload",
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

// Same pattern as archive-process/archive-enqueue. Accepts the legacy
// JWT format and the sb_secret_ format during the Supabase key rotation.
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
