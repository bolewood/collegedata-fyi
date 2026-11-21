import { authWallOutcome, type ProbeOutcome } from "./probe_outcome.ts";
import { sniffBytesForExt } from "./storage.ts";

function htmlPreview(bytes: Uint8Array): string {
  return new TextDecoder("utf-8", { fatal: false })
    .decode(bytes.slice(0, 64 * 1024))
    .toLowerCase();
}

function hasAny(value: string, needles: string[]): boolean {
  return needles.some((needle) => value.includes(needle));
}

export function rejectableHtmlSourceOutcome(
  bytes: Uint8Array,
  finalUrl: string,
): ProbeOutcome | null {
  const finalUrlOutcome = authWallOutcome(finalUrl);
  if (finalUrlOutcome) return finalUrlOutcome;

  let host = "";
  try {
    host = new URL(finalUrl).hostname.toLowerCase();
  } catch {
    // Continue with body classification.
  }

  const text = htmlPreview(bytes);
  const haystack = `${host}\n${text}`;

  if (
    hasAny(haystack, [
      "login.microsoftonline.com",
      "sign in to your account",
      "aadcdn",
      "samlrequest",
      "microsoft corporation. all rights reserved",
    ])
  ) {
    return "auth_walled_microsoft";
  }

  if (
    hasAny(haystack, [
      "accounts.google.com",
      "service_login",
      "google accounts",
      "google sign in",
      "identifierid",
    ])
  ) {
    return "auth_walled_google";
  }

  if (host.endsWith(".okta.com") || hasAny(haystack, ["okta sign in", "okta-signin"])) {
    return "auth_walled_okta";
  }

  if (
    hasAny(haystack, [
      "cloudflare",
      "just a moment",
      "cf-mitigated",
      "cf-chl-",
      "__cf_chl_",
      "captcha",
      "incapsula incident",
      "imperva",
      "perfdrive",
      "validate.perfdrive.com",
      "access denied",
      "request unsuccessful",
    ])
  ) {
    return "bot_challenge";
  }

  const cdsLike = hasAny(text, [
    "common data set",
    "common dataset",
    "cds",
    "b1 men women another gender",
    "first-time, first-year",
    "degree-seeking undergraduate",
  ]);
  const hasTableMarkup = text.includes("<table") && (
    text.includes("<td") || text.includes("<th")
  );

  if (
    hasAny(text, [
      "404 not found",
      "404 error",
      "page not found",
      "file not found",
      "the page you requested could not be found",
      "server error",
      "temporarily unavailable",
      "please sign in",
      "single sign-on",
      "single sign on",
    ])
  ) {
    return "wrong_content_type";
  }

  if (cdsLike && !hasTableMarkup) {
    return "wrong_content_type";
  }

  return null;
}

// Some hosts answer a request for a .pdf URL with a small PDF.js viewer
// page that loads the real file from a URL in a script constant
// (archive.swarthmore.edu: `const PDF_URL = ".../cds2014.pdf?__raw=1";`).
// Returns that URL when `bytes` is such a page, else null. The URL must be
// on the same host and scheme as the page and its path must end in .pdf, so
// a page cannot name a file on another site. (Where that URL redirects to
// is the caller's check.)
export function pdfViewerRawUrl(bytes: Uint8Array, pageUrl: string): string | null {
  let page: URL;
  try {
    page = new URL(pageUrl);
  } catch {
    return null;
  }
  if (!page.pathname.toLowerCase().endsWith(".pdf")) return null;
  // Bytes are authoritative: a real PDF that happens to contain these
  // strings is not a viewer page.
  if (sniffBytesForExt(bytes) !== "html") return null;

  const html = new TextDecoder("utf-8", { fatal: false }).decode(bytes.slice(0, 64 * 1024));
  const lower = html.toLowerCase();
  if (!lower.includes("<html") || !(lower.includes("pdf.js") || lower.includes("pdfjs"))) {
    return null;
  }
  const match = html.match(/\bPDF_URL\s*=\s*(["'])([^"'\s<>]+)\1/);
  if (!match) return null;

  let raw: URL;
  try {
    raw = new URL(match[2], page);
  } catch {
    return null;
  }
  if (raw.protocol !== page.protocol || raw.host !== page.host) return null;
  if (!raw.pathname.toLowerCase().endsWith(".pdf")) return null;
  if (raw.href === page.href) return null;
  return raw.href;
}
