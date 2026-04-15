// Landing-page → direct CDS document URL resolver. Walks every <a href>
// on the hint page, filters to CDS-keyword matches, categorizes into
// document (.pdf/.xlsx/.docx) vs subpage (HTML or no extension), and for
// subpages follows one hop to find the real documents. Ranks the resulting
// set and returns a discriminated union so callers can distinguish
// resolved-happy-path from the four failure modes that demand different
// responses: transient (retry), upstream gone (mark removed), no CDS found
// (permanent, needs human), and unsupported content type (permanent).

import { DOMParser, type Element as DomElement } from "jsr:@b-fuze/deno-dom";
import { normalizeYear } from "./year.ts";

export const USER_AGENT =
  "collegedata.fyi/0.1 (research probe; https://collegedata.fyi)";
export const LANDING_TIMEOUT_MS = 30_000;
export const SUBPAGE_TIMEOUT_MS = 15_000;
const MAX_SUBPAGES_PER_SCHOOL = 25;

const CDS_KEYWORDS_RE = /common\s*data\s*set|\bcds\b/i;
const DOCUMENT_EXT_RE = /\.(pdf|xlsx|docx)(\?|#|$)/i;

// Section-file detection deliberately scoped to filenames only.
// The earlier broader regex produced false positives when legit full-CDS
// anchors had link text like "Enrollment and First-Time Information" in
// the school's IR page hierarchy. Filenames are the only reliable signal.
// "section [a-j]" suffix or explicit "section-d" prefix is the canonical
// marker across the corpus.
const SECTION_MARKER_RE = /\bsection[-_ ]?[a-j]\b/i;

// SSRF defense. The resolver follows arbitrary URLs out of HTML, so a
// compromised school website could try to pivot into cloud metadata
// endpoints or private address space via the edge function's network
// context. We reject:
//   - non-http(s) schemes (javascript:, file:, ftp:, data:, ...)
//   - IP literals in RFC1918, loopback, link-local, cloud metadata, or ULA
//   - explicit localhost hostnames
// Names that resolve to private IPs via DNS are not pre-checked here, but
// Deno Deploy's sandbox has no route to Supabase internal services so the
// blast radius is bounded even if DNS-based exfiltration slipped through.
const PRIVATE_IP_PATTERNS: RegExp[] = [
  /^127\./,                                    // loopback
  /^10\./,                                     // RFC1918
  /^192\.168\./,                               // RFC1918
  /^172\.(1[6-9]|2\d|3[01])\./,                // RFC1918
  /^169\.254\./,                               // link-local + cloud metadata
  /^0\./,                                      // non-routable
  /^100\.(6[4-9]|[7-9]\d|1[01]\d|12[0-7])\./,  // carrier-grade NAT
  /^::1$/,                                     // ipv6 loopback
  /^fe80:/i,                                   // ipv6 link-local
  /^fc00:/i,                                   // ipv6 ULA
  /^fd00:/i,                                   // ipv6 ULA
];

const BLOCKED_HOSTNAMES = new Set<string>([
  "localhost",
  "metadata.google.internal",
  "metadata",
]);

// Hosts whose documents look like CDS files but are NOT an individual
// school's filled CDS. Anchors pointing at these hosts get dropped during
// extraction even if their filename/text matches the CDS keyword filter.
//
// commondataset.org is the CDS Initiative's own site. It publishes the
// blank template, the Summary of Changes reference doc, and the value-
// options spec — all of which contain "CDS" in the filename and match
// the keyword filter. IR landing pages link to those references for
// context, and on pages that link both the reference AND the school's
// own CDS, the ranker used to pick the reference (more recent year in
// the filename) and archive it as the school's data. Surfaced by the
// tier probe when stanford, georgetown, and davidson all archived the
// exact same 326023-byte "Summary of Changes" docx, byte-for-byte
// identical SHA.
//
// Match is suffix-based so subdomains (www.commondataset.org, etc) are
// covered automatically. Add more entries if other upstream aggregators
// show the same false-positive pattern.
const EXCLUDED_DOCUMENT_HOSTS: string[] = [
  "commondataset.org",
];

function isExcludedDocumentHost(hostname: string): boolean {
  const h = hostname.toLowerCase();
  for (const suffix of EXCLUDED_DOCUMENT_HOSTS) {
    if (h === suffix || h.endsWith("." + suffix)) return true;
  }
  return false;
}

export function isSafeUrl(raw: string): boolean {
  let parsed: URL;
  try {
    parsed = new URL(raw);
  } catch {
    return false;
  }
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:") return false;

  const host = parsed.hostname.toLowerCase();
  if (BLOCKED_HOSTNAMES.has(host)) return false;
  if (host.endsWith(".localhost")) return false;
  for (const pat of PRIVATE_IP_PATTERNS) {
    if (pat.test(host)) return false;
  }
  return true;
}

export type AnchorKind = "document" | "subpage";
export type YearSource = "filename" | "url_path" | "link_text" | "unknown";

export interface CdsAnchor {
  url: string;
  filename: string;
  link_text: string;
  year: string | null;
  year_source: YearSource;
  kind: AnchorKind;
  is_section_file: boolean;
}

export interface ResolvedDocument {
  url: string;
  cds_year: string;
  filename: string;
  is_section_file: boolean;
  discovered_via: "direct" | "landing" | "subpage";
  parent_subpage_url?: string;
}

// Discriminated union so callers can classify failure modes. This replaces
// the earlier "return null for everything that isn't happy path" design,
// which collapsed transient network errors into "upstream gone" and caused
// cds_documents.removed_at to fire on DNS blips. Codex flagged it as the
// #1 critical finding in review.
export type ResolveResult =
  | { kind: "resolved"; doc: ResolvedDocument }
  | { kind: "upstream_gone"; status: number; reason: string }
  | { kind: "transient"; reason: string }
  | { kind: "no_cds_found"; reason: string }
  | { kind: "unsupported_content"; reason: string }
  | { kind: "blocked_url"; reason: string };

export interface FetchResult {
  ok: boolean;
  status: number;
  contentType: string;
  text: string;
  finalUrl: string;
  error?: string;
}

export async function fetchText(
  url: string,
  timeoutMs: number,
): Promise<FetchResult> {
  if (!isSafeUrl(url)) {
    return {
      ok: false,
      status: 0,
      contentType: "",
      text: "",
      finalUrl: url,
      error: "blocked unsafe URL",
    };
  }
  try {
    const r = await fetch(url, {
      headers: { "User-Agent": USER_AGENT },
      signal: AbortSignal.timeout(timeoutMs),
      redirect: "follow",
    });
    // Re-check the final URL after redirects: a school page could 302 us
    // to an internal address. isSafeUrl on the origin alone isn't enough.
    if (!isSafeUrl(r.url)) {
      return {
        ok: false,
        status: r.status,
        contentType: "",
        text: "",
        finalUrl: r.url,
        error: "redirect target blocked as unsafe URL",
      };
    }
    const contentType = r.headers.get("content-type") ?? "";
    const text =
      r.ok && contentType.toLowerCase().includes("text/html") ? await r.text() : "";
    return {
      ok: r.ok,
      status: r.status,
      contentType,
      text,
      finalUrl: r.url,
    };
  } catch (e) {
    return {
      ok: false,
      status: 0,
      contentType: "",
      text: "",
      finalUrl: url,
      error: (e as Error).message,
    };
  }
}

export function extractCdsAnchors(html: string, baseUrl: string): CdsAnchor[] {
  const doc = new DOMParser().parseFromString(html, "text/html");
  if (!doc) return [];

  const base = new URL(baseUrl);
  const all: CdsAnchor[] = [];

  for (const node of doc.querySelectorAll("a[href]")) {
    const el = node as unknown as DomElement;
    const href = el.getAttribute("href") ?? "";
    if (!href) continue;
    if (/^(#|mailto:|tel:|javascript:)/i.test(href)) continue;

    const linkText = (el.textContent ?? "").replace(/\s+/g, " ").trim();

    let absoluteUrl: string;
    try {
      absoluteUrl = new URL(href, base).toString();
    } catch {
      continue;
    }

    const parsed = new URL(absoluteUrl);

    // Drop anchors pointing at upstream aggregator sites that host CDS
    // reference documents (blank template, Summary of Changes, etc).
    // See EXCLUDED_DOCUMENT_HOSTS comment above.
    if (isExcludedDocumentHost(parsed.hostname)) continue;

    const pathSegments = parsed.pathname.split("/").filter(Boolean);
    const filename = decodeURIComponent(
      pathSegments[pathSegments.length - 1] ?? "",
    );
    const fullPath = decodeURIComponent(parsed.pathname);

    // Deliberately excludes hostname to avoid false-matching every
    // commondataset.org link (e.g. the CDS Initiative's brochure).
    if (
      !CDS_KEYWORDS_RE.test(filename) &&
      !CDS_KEYWORDS_RE.test(linkText) &&
      !CDS_KEYWORDS_RE.test(fullPath)
    ) continue;

    let year: string | null = normalizeYear(filename);
    let yearSource: YearSource = year ? "filename" : "unknown";
    if (!year) {
      year = normalizeYear(fullPath);
      if (year) yearSource = "url_path";
    }
    if (!year) {
      year = normalizeYear(linkText);
      if (year) yearSource = "link_text";
    }

    const kind: AnchorKind = DOCUMENT_EXT_RE.test(filename)
      ? "document"
      : "subpage";

    all.push({
      url: absoluteUrl,
      filename,
      link_text: linkText,
      year,
      year_source: yearSource,
      kind,
      // Section marker checked only against filename. Link text like
      // "Enrollment and General Information" on a CDS overview page would
      // otherwise flag a full CDS as a section file and demote it.
      is_section_file: SECTION_MARKER_RE.test(filename),
    });
  }

  // Dedupe by URL (minus fragment). Earlier "first wins" deduplication
  // dropped year-bearing duplicates behind yearless ones on schools that
  // link the same CDS twice on a landing page with different anchor text.
  // Rules, in order:
  //   1. Anchor with a year beats anchor without
  //   2. Anchor with a more recent year beats anchor with an older year
  //   3. Earlier anchor (document order) wins ties
  const byUrl = new Map<string, CdsAnchor>();
  for (const a of all) {
    const key = a.url.split("#")[0];
    const prior = byUrl.get(key);
    if (!prior) {
      byUrl.set(key, a);
      continue;
    }
    const priorHasYear = prior.year !== null;
    const currHasYear = a.year !== null;
    if (!priorHasYear && currHasYear) {
      byUrl.set(key, a);
    } else if (priorHasYear && currHasYear && a.year! > prior.year!) {
      byUrl.set(key, a);
    }
  }

  return Array.from(byUrl.values());
}

// Patterns for recognizing "download" links on item pages that don't have
// a file extension and don't carry CDS keywords in the link text. Used as
// a fallback when the strict extractCdsAnchors pass finds no document
// anchors on a subpage — which is the Digital Commons / Bepress / DSpace
// item-page shape (Fairfield being the concrete example from tonight's
// failed_permanent rows).
const DOWNLOAD_TEXT_RE =
  /\b(download|full[\s-]?text|view[\s-]?pdf|open[\s-]?access|pdf)\b/i;
const DOWNLOAD_URL_RE =
  /\b(viewcontent|bitstream|download|getfile|attachment|fulltext)\b/i;

// Scans a subpage HTML for anchors that look like document download links
// even when they don't carry a file extension or CDS keyword. Used only as
// a fallback in the two-hop walk — the parent subpage already confirmed
// CDS context, so anchors here are trusted to be the download for the
// CDS item the parent was pointing at. Caller fills year from parent.
// Content-type is confirmed at download time in downloadWithCaps, so a
// false-positive here becomes a clean PermanentError downstream rather
// than corrupted data.
export function findDownloadLinks(html: string, baseUrl: string): CdsAnchor[] {
  const doc = new DOMParser().parseFromString(html, "text/html");
  if (!doc) return [];

  const base = new URL(baseUrl);
  const seen = new Set<string>();
  const out: CdsAnchor[] = [];

  for (const node of doc.querySelectorAll("a[href]")) {
    const el = node as unknown as DomElement;
    const href = el.getAttribute("href") ?? "";
    if (!href) continue;
    if (/^(#|mailto:|tel:|javascript:)/i.test(href)) continue;

    const linkText = (el.textContent ?? "").replace(/\s+/g, " ").trim();

    let absoluteUrl: string;
    try {
      absoluteUrl = new URL(href, base).toString();
    } catch {
      continue;
    }

    const parsed = new URL(absoluteUrl);
    if (isExcludedDocumentHost(parsed.hostname)) continue;

    const fullPath = decodeURIComponent(parsed.pathname + parsed.search);
    const matchesText = DOWNLOAD_TEXT_RE.test(linkText);
    const matchesUrl = DOWNLOAD_URL_RE.test(fullPath);
    if (!matchesText && !matchesUrl) continue;

    const key = absoluteUrl.split("#")[0];
    if (seen.has(key)) continue;
    seen.add(key);

    const pathSegments = parsed.pathname.split("/").filter(Boolean);
    const filename = decodeURIComponent(
      pathSegments[pathSegments.length - 1] ?? "",
    );

    out.push({
      url: absoluteUrl,
      filename,
      link_text: linkText,
      year: null,
      year_source: "unknown",
      kind: "document",
      is_section_file: false,
    });
  }

  return out;
}

// Ranks candidate document anchors and returns the best one.
//   1. Full CDS beats section files
//   2. Anchors with a year beat anchors without
//   3. More recent year beats older
//   4. Within ties, document order wins (earlier in HTML = more prominent)
export function findBestSourceAnchor(
  anchors: CdsAnchor[],
): CdsAnchor | null {
  const docs = anchors.filter((a) => a.kind === "document");
  if (docs.length === 0) return null;

  const ranked = [...docs].sort((a, b) => {
    if (a.is_section_file !== b.is_section_file) {
      return a.is_section_file ? 1 : -1;
    }
    const aHas = a.year !== null;
    const bHas = b.year !== null;
    if (aHas !== bHas) return aHas ? -1 : 1;
    if (a.year && b.year) {
      if (a.year !== b.year) return a.year < b.year ? 1 : -1;
    }
    return 0;
  });

  return ranked[0];
}

// Translates a content-type header into an extension symbol. Shared with
// storage.ts — kept local here so the resolver can classify direct-file
// landing responses without pulling storage.ts into resolve.ts's import
// graph (the storage module depends on the supabase client).
function extensionFromContentType(contentType: string): "pdf" | "xlsx" | "docx" | null {
  const ct = contentType.toLowerCase();
  if (ct.includes("application/pdf")) return "pdf";
  if (ct.includes("officedocument.spreadsheetml.sheet")) return "xlsx";
  if (ct.includes("officedocument.wordprocessingml.document")) return "docx";
  return null;
}

// Top-level resolver. Given a hint URL, returns a ResolveResult discriminated
// union. See the type for the five possible kinds. Callers branch on kind:
// resolved → archive; upstream_gone → mark removed; transient → retry later;
// no_cds_found / unsupported_content → permanent failure for human review;
// blocked_url → permanent (SSRF defense tripped).
export async function resolveCdsForSchool(
  hint: string,
): Promise<ResolveResult> {
  if (!isSafeUrl(hint)) {
    return { kind: "blocked_url", reason: "hint URL failed safety check" };
  }

  // Direct document hint: the schools.yaml entry points straight at the
  // file. Skip landing-page parsing entirely.
  if (DOCUMENT_EXT_RE.test(hint)) {
    const year = normalizeYear(hint);
    if (!year) {
      return {
        kind: "no_cds_found",
        reason: "direct document hint has no parseable year",
      };
    }
    const parsed = new URL(hint);
    const filename = decodeURIComponent(
      parsed.pathname.split("/").filter(Boolean).pop() ?? "",
    );
    return {
      kind: "resolved",
      doc: {
        url: hint,
        cds_year: year,
        filename,
        is_section_file: SECTION_MARKER_RE.test(filename),
        discovered_via: "direct",
      },
    };
  }

  const landing = await fetchText(hint, LANDING_TIMEOUT_MS);
  if (!landing.ok) {
    if (landing.status === 404 || landing.status === 410) {
      return {
        kind: "upstream_gone",
        status: landing.status,
        reason: `landing HTTP ${landing.status}`,
      };
    }
    return {
      kind: "transient",
      reason: landing.error ?? `landing HTTP ${landing.status}`,
    };
  }

  const ct = landing.contentType.toLowerCase();

  // Landing redirected to a supported document MIME directly (some schools
  // host their CDS behind an opaque download URL that 302s to the PDF).
  const directExt = extensionFromContentType(ct);
  if (directExt) {
    const parsed = new URL(landing.finalUrl);
    const filename = decodeURIComponent(
      parsed.pathname.split("/").filter(Boolean).pop() ?? "",
    );
    const year = normalizeYear(filename) ?? normalizeYear(landing.finalUrl);
    if (!year) {
      return {
        kind: "no_cds_found",
        reason: "direct document response has no parseable year",
      };
    }
    return {
      kind: "resolved",
      doc: {
        url: landing.finalUrl,
        cds_year: year,
        filename,
        is_section_file: SECTION_MARKER_RE.test(filename),
        discovered_via: "direct",
      },
    };
  }

  if (!ct.includes("text/html")) {
    return {
      kind: "unsupported_content",
      reason: `landing content-type ${landing.contentType || "(none)"}`,
    };
  }

  const anchors = extractCdsAnchors(landing.text, landing.finalUrl);
  const landingDocsWithYear = anchors
    .filter((a) => a.kind === "document" && a.year !== null);

  if (landingDocsWithYear.length > 0) {
    const best = findBestSourceAnchor(landingDocsWithYear);
    if (best && best.year) {
      return {
        kind: "resolved",
        doc: {
          url: best.url,
          cds_year: best.year,
          filename: best.filename,
          is_section_file: best.is_section_file,
          discovered_via: "landing",
        },
      };
    }
  }

  // Two-hop fallback: landing has subpage anchors; follow one hop each.
  const subpages = anchors
    .filter((a) => a.kind === "subpage")
    .slice(0, MAX_SUBPAGES_PER_SCHOOL);

  if (subpages.length === 0) {
    return {
      kind: "no_cds_found",
      reason: "landing parsed, no year-bearing document anchors and no subpages",
    };
  }

  const allSubDocs: CdsAnchor[] = [];
  const subResults = await Promise.all(
    subpages.map(async (sub) => {
      const resp = await fetchText(sub.url, SUBPAGE_TIMEOUT_MS);
      if (!resp.ok) return [] as CdsAnchor[];
      const subCt = resp.contentType.toLowerCase();
      const subExt = extensionFromContentType(subCt);
      if (subExt) {
        const parsed = new URL(resp.finalUrl);
        const filename = decodeURIComponent(
          parsed.pathname.split("/").filter(Boolean).pop() ?? "",
        );
        const year = normalizeYear(filename) ?? sub.year;
        if (!year) return [];
        return [{
          url: resp.finalUrl,
          filename,
          link_text: sub.link_text,
          year,
          year_source: "filename" as YearSource,
          kind: "document" as AnchorKind,
          is_section_file: SECTION_MARKER_RE.test(filename),
        }];
      }
      if (!subCt.includes("text/html")) return [];
      const subAnchors = extractCdsAnchors(resp.text, resp.finalUrl);
      const out: CdsAnchor[] = [];
      for (const a of subAnchors) {
        if (a.kind !== "document") continue;
        out.push({
          ...a,
          year: a.year ?? sub.year,
        });
      }

      // Fallback for Digital Commons / Bepress / DSpace item pages where
      // the real PDF download link has no file extension and no CDS
      // keyword. The CDS context was established on the parent subpage,
      // so we trust any download-pattern anchor on the child and let
      // downloadWithCaps validate the content-type before archiving.
      if (out.length === 0) {
        const downloadAnchors = findDownloadLinks(resp.text, resp.finalUrl);
        for (const a of downloadAnchors) {
          out.push({
            ...a,
            year: sub.year,
            year_source: sub.year_source,
          });
        }
      }

      return out;
    }),
  );

  for (const docs of subResults) allSubDocs.push(...docs);

  const subDocsWithYear = allSubDocs.filter((a) => a.year !== null);
  if (subDocsWithYear.length === 0) {
    return {
      kind: "no_cds_found",
      reason: "two-hop walk found no year-bearing document anchors",
    };
  }

  const best = findBestSourceAnchor(subDocsWithYear);
  if (!best || !best.year) {
    return {
      kind: "no_cds_found",
      reason: "ranking found no valid best anchor",
    };
  }

  return {
    kind: "resolved",
    doc: {
      url: best.url,
      cds_year: best.year,
      filename: best.filename,
      is_section_file: best.is_section_file,
      discovered_via: "subpage",
    },
  };
}
