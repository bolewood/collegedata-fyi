// Supabase Storage helpers for the archive pipeline. SHA-addressed paths,
// no overwrites, no history copies. Upload is idempotent via upsert so a
// retry on the same SHA is a no-op regardless of whether the object already
// exists.

import { SupabaseClient } from "jsr:@supabase/supabase-js@2";

export const SOURCES_BUCKET = "sources";
export const MAX_SOURCE_BYTES = 50 * 1024 * 1024; // matches bucket file_size_limit

export function buildSourcePath(
  schoolId: string,
  cdsYear: string,
  sha256: string,
  ext: string,
): string {
  return `${schoolId}/${cdsYear}/${sha256}.${ext}`;
}

export function extForContentType(contentType: string | null, fallbackUrl: string): string | null {
  const ct = (contentType ?? "").toLowerCase();
  if (ct.includes("application/pdf")) return "pdf";
  if (ct.includes("officedocument.spreadsheetml.sheet")) return "xlsx";
  if (ct.includes("officedocument.wordprocessingml.document")) return "docx";

  const lower = fallbackUrl.toLowerCase();
  if (lower.endsWith(".pdf") || lower.includes(".pdf?")) return "pdf";
  if (lower.endsWith(".xlsx") || lower.includes(".xlsx?")) return "xlsx";
  if (lower.endsWith(".docx") || lower.includes(".docx?")) return "docx";
  return null;
}

// Magic-byte sniffer. Used as a last-resort fallback when content-type
// and URL extension both fail to identify the file — most commonly
// for Google Drive direct-download URLs which serve every file as
// application/octet-stream regardless of the actual contents. Trusts
// the first 8 bytes since the magic numbers for all three supported
// formats are unambiguous and unique.
//
//   PDF:          %PDF-       → 0x25 0x50 0x44 0x46 0x2d
//   XLSX / DOCX:  PK\x03\x04  → 0x50 0x4b 0x03 0x04  (they are both ZIP
//                                                     archives; distinguishing
//                                                     them would require
//                                                     reading [Content_Types].xml)
//
// Returns the detected extension, or null if the magic doesn't match
// any supported format. For ZIP archives we return "xlsx" as a best
// guess since CDS filled templates are overwhelmingly spreadsheets
// rather than Word docs (and the extractor will re-detect format via
// openpyxl / python-docx anyway, so a wrong guess is recoverable).
export function sniffBytesForExt(bytes: Uint8Array): "pdf" | "xlsx" | "docx" | null {
  if (bytes.length < 4) return null;
  // %PDF- → PDF
  if (
    bytes[0] === 0x25 &&
    bytes[1] === 0x50 &&
    bytes[2] === 0x44 &&
    bytes[3] === 0x46
  ) return "pdf";
  // PK\x03\x04 → ZIP archive (xlsx or docx). Default to xlsx for CDS.
  if (
    bytes[0] === 0x50 &&
    bytes[1] === 0x4b &&
    bytes[2] === 0x03 &&
    bytes[3] === 0x04
  ) return "xlsx";
  return null;
}

// Combined classifier: tries content-type first, then URL suffix, then
// magic-byte sniffing. This is what downloadWithCaps uses to decide the
// final extension for the SHA-addressed Storage path after the bytes
// are in hand.
export function extForResponse(
  contentType: string | null,
  finalUrl: string,
  bytes: Uint8Array,
): "pdf" | "xlsx" | "docx" | null {
  const fromCt = extForContentType(contentType, finalUrl);
  if (fromCt === "pdf" || fromCt === "xlsx" || fromCt === "docx") {
    return fromCt;
  }
  return sniffBytesForExt(bytes);
}

export function normalizedContentType(ext: string): string {
  switch (ext) {
    case "pdf":
      return "application/pdf";
    case "xlsx":
      return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
    case "docx":
      return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    default:
      return "application/octet-stream";
  }
}

// HEAD-like check. The supabase-js storage client doesn't expose a direct
// HEAD; `.list()` on the parent prefix with a search filter for the exact
// filename is the cheapest equivalent. Returns true if an object with that
// exact name exists at that path.
export async function objectExists(
  client: SupabaseClient,
  path: string,
): Promise<boolean> {
  const lastSlash = path.lastIndexOf("/");
  const prefix = lastSlash >= 0 ? path.slice(0, lastSlash) : "";
  const filename = lastSlash >= 0 ? path.slice(lastSlash + 1) : path;

  const { data, error } = await client.storage
    .from(SOURCES_BUCKET)
    .list(prefix, { limit: 100, search: filename });
  if (error) return false;
  return (data ?? []).some((entry) => entry.name === filename);
}

export async function uploadSource(
  client: SupabaseClient,
  path: string,
  bytes: Uint8Array,
  ext: string,
): Promise<void> {
  const { error } = await client.storage
    .from(SOURCES_BUCKET)
    .upload(path, bytes, {
      contentType: normalizedContentType(ext),
      upsert: true,
    });
  if (error) {
    throw new Error(`storage upload failed at ${path}: ${error.message}`);
  }
}
