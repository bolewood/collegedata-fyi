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

export function extForContentTypeOnly(contentType: string | null): "pdf" | "xlsx" | "docx" | "html" | null {
  const ct = (contentType ?? "").toLowerCase();
  if (ct.includes("application/pdf")) return "pdf";
  if (ct.includes("officedocument.spreadsheetml.sheet")) return "xlsx";
  if (ct.includes("officedocument.wordprocessingml.document")) return "docx";
  if (ct.includes("text/html")) return "html";
  return null;
}

export function extForUrl(fallbackUrl: string): "pdf" | "xlsx" | "docx" | "html" | null {
  const lower = fallbackUrl.toLowerCase();
  if (lower.endsWith(".pdf") || lower.includes(".pdf?")) return "pdf";
  if (lower.endsWith(".xlsx") || lower.includes(".xlsx?")) return "xlsx";
  if (lower.endsWith(".docx") || lower.includes(".docx?")) return "docx";
  if (lower.endsWith(".html") || lower.endsWith(".htm") ||
      lower.includes(".html?") || lower.includes(".htm?")) return "html";
  return null;
}

export function extForContentType(contentType: string | null, fallbackUrl: string): string | null {
  return extForContentTypeOnly(contentType) ?? extForUrl(fallbackUrl);
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
//   HTML:         <html / <!DOCTYPE html / <head (case-insensitive text sniff
//                                                in the first 512 bytes)
//
// Returns the detected extension, or null if the magic doesn't match
// any supported format. For ZIP archives we return "xlsx" as a best
// guess since CDS filled templates are overwhelmingly spreadsheets
// rather than Word docs (and the extractor will re-detect format via
// openpyxl / python-docx anyway, so a wrong guess is recoverable).
// HTML sniff runs after binary magic so a ZIP/PDF with a stray "<html"
// byte sequence still classifies correctly.
export function sniffBytesForExt(bytes: Uint8Array): "pdf" | "xlsx" | "docx" | "html" | null {
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
  // HTML text sniff: decode the first 512 bytes as ASCII-ish UTF-8
  // fragment and check for an html-ish token at the start of the
  // document. Case-insensitive. Tolerates leading whitespace / BOM.
  const head = new TextDecoder("utf-8", { fatal: false })
    .decode(bytes.slice(0, 512))
    .toLowerCase()
    .trimStart();
  if (
    head.startsWith("<!doctype html") ||
    head.startsWith("<html") ||
    head.startsWith("<head") ||
    head.startsWith("<?xml") && head.includes("<html")
  ) {
    return "html";
  }
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
): "pdf" | "xlsx" | "docx" | "html" | null {
  const fromBytes = sniffBytesForExt(bytes);
  const fromCt = extForContentTypeOnly(contentType);
  const fromUrl = extForUrl(finalUrl);

  // WAF / auth challenges commonly return an HTML page at a URL ending in
  // .pdf. Bytes are authoritative; do not archive those pages as PDFs.
  if (fromBytes === "html" && (fromCt !== "html" || fromUrl !== "html")) {
    return null;
  }

  if (fromBytes) return fromBytes;
  return fromCt ?? fromUrl;
}

// XSS mitigation (PRD 008): the `sources` Storage bucket is public-read,
// so any stored object served with its native content-type is fair game
// for a browser to render. For binary formats (pdf/xlsx/docx) the browser
// downloads; but raw HTML bytes served with `text/html` would execute
// embedded `<script>` at the Supabase CDN URL. We intentionally store
// archived HTML and serve it with `text/plain; charset=utf-8` so a
// browser renders the markup as source text, never as a live page.
// The extractor reads the bytes from Storage directly (not via the
// browser-facing CDN), so the plain-text response header doesn't impair
// extraction — only XSS.
export function normalizedContentType(ext: string): string {
  switch (ext) {
    case "pdf":
      return "application/pdf";
    case "xlsx":
      return "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
    case "docx":
      return "application/vnd.openxmlformats-officedocument.wordprocessingml.document";
    case "html":
      // XSS mitigation: archived HTML bytes are uploaded with a declared
      // content-type of 'text/plain' (no charset param, so the string
      // exact-matches the 'text/plain' entry in the sources bucket MIME
      // allowlist). Public reads serve the object with this declared
      // type, so a browser loading the Supabase CDN URL sees plaintext,
      // never a live HTML page that could execute <script>. See PRD 008.
      return "text/plain";
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
