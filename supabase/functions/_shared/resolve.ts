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

// Mozilla-compatible UA. The plain "collegedata.fyi/0.1" UA was getting
// 403'd by Bepress-hosted Digital Commons sites (Fairfield, others) and
// likely by other WAFs tuned to block non-browser UAs. Keeping the
// project identity in the comment so we're honest about who we are
// while passing naive UA filters. The format (Mozilla/5.0 (compatible;
// name/version; +url)) is the convention used by most crawler bots.
export const USER_AGENT =
  "Mozilla/5.0 (compatible; collegedata.fyi/0.1; +https://collegedata.fyi)";
export const LANDING_TIMEOUT_MS = 30_000;
export const SUBPAGE_TIMEOUT_MS = 15_000;
const MAX_SUBPAGES_PER_SCHOOL = 25;

// Matches "common data set" (with flexible whitespace) or "cds" as a
// left-boundaried token not followed by another letter. The right-
// side guard is `(?![a-z])` rather than `\b` so that filenames with
// no separator between CDS and the year — like Lafayette's
// `CDS2025-2026.pdf` or Samford's `CDS2024_Section_A.pdf` — still
// match. `\bcds\b` would require a word boundary between `s` and
// the following digit/underscore, which is not a word boundary at
// all (both are word characters), and dropped every year on those
// schools' landing pages during the Stage B resolver rewrite.
// `(?![a-z])` still rejects `cdsomething`, `CDSummit`, and similar
// false positives where cds is a prefix of a different word.
const CDS_KEYWORDS_RE = /common\s*data\s*set|\bcds(?![a-z])/i;
const DOCUMENT_EXT_RE = /\.(pdf|xlsx|docx)(\?|#|$)/i;

// Section-file detection deliberately scoped to filenames only.
// The earlier broader regex produced false positives when legit full-CDS
// anchors had link text like "Enrollment and First-Time Information" in
// the school's IR page hierarchy. Filenames are the only reliable signal.
// "section [a-j]" suffix or explicit "section-d" prefix is the canonical
// marker across the corpus.
const SECTION_MARKER_RE = /\bsection[-_ ]?[a-j]\b/i;

// Staging artifacts schools leave behind on their CMS. CSULB's
// cds_url_hint landing page exposes `cds_2015-2016_test.pdf` twice
// (once labeled "CDS 2015-2016", once labeled "CDS 2016-2017") and
// nothing else — so the resolver picks a test upload as the school's
// canonical CDS. Content-based year detection surfaced the bug by
// flagging CSULB as a year mismatch in the ADR 0007 Stage A harness
// (stored 2015-16, detected 2016-17). More generally: schools
// frequently leave `_test|_draft|_old|_copy|_backup|_archive` files
// sitting in their document roots after real uploads go live. We
// don't want to *drop* these anchors entirely, because a school whose
// only linked CDS is a test artifact is still better-archived than
// skipped — but we do want to deprioritize them so a clean sibling
// always wins. Ranking happens in findBestSourceAnchor below.
const TEST_ARTIFACT_RE =
  /[_\-.](?:test|draft|old|copy|backup|archive|bak|tmp|temp|staging|dev|preview)\b/i;

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

// Google Drive file-share URLs point at an HTML viewer, not the file
// itself. Our resolver's two-hop fetch lands on the viewer, sees
// text/html, and can't classify it as a document. The fix is to rewrite
// share URLs into the direct-download form before we try to follow them.
//
// Example input:
//   https://drive.google.com/file/d/1GIPKgVj1d86dkmLkHI_mZVCk_iY6kiCp/view?usp=sharing
// Example output:
//   https://drive.google.com/uc?export=download&id=1GIPKgVj1d86dkmLkHI_mZVCk_iY6kiCp
//
// Stanford hosts all 18 years of their CDS on Drive. The whole pattern
// is probably not unique to them — any school that lets their IR
// office use Drive for public document distribution lands here.
//
// The confirm=t parameter defeats Google's "virus scan warning" interstitial
// for larger files. Without it, Drive returns an HTML confirmation page
// instead of the binary bytes for files over ~25MB.
const GOOGLE_DRIVE_FILE_RE = /^https?:\/\/drive\.google\.com\/file\/d\/([^/]+)/i;
const GOOGLE_DRIVE_OPEN_RE = /^https?:\/\/drive\.google\.com\/open\?id=([^&]+)/i;

export function rewriteGoogleDriveUrl(url: string): string {
  const fileMatch = url.match(GOOGLE_DRIVE_FILE_RE);
  if (fileMatch) {
    return `https://drive.google.com/uc?export=download&id=${fileMatch[1]}&confirm=t`;
  }
  const openMatch = url.match(GOOGLE_DRIVE_OPEN_RE);
  if (openMatch) {
    return `https://drive.google.com/uc?export=download&id=${openMatch[1]}&confirm=t`;
  }
  return url;
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
  is_test_artifact: boolean;
}

export interface ResolvedDocument {
  url: string;
  cds_year: string;
  filename: string;
  is_section_file: boolean;
  is_test_artifact: boolean;
  discovered_via: "direct" | "landing" | "subpage";
  parent_subpage_url?: string;
}

// Sentinel cds_year for direct-doc hints whose filename carries no
// parseable year (e.g. `cds_all.pdf`, `common-data-set.pdf`, UCLA's
// `/file/<uuid>`). Per ADR 0007 Stage B the archiver writes the
// document anyway and defers year assignment to the extraction
// worker, which populates detected_year from page-1 content. The
// sentinel stays in cds_year as a historical marker; consumers read
// cds_manifest.canonical_year which COALESCEs detected_year over
// cds_year and suppresses the sentinel for any extracted row.
export const UNKNOWN_YEAR_SENTINEL = "unknown";

// Discriminated union so callers can classify failure modes. This replaces
// the earlier "return null for everything that isn't happy path" design,
// which collapsed transient network errors into "upstream gone" and caused
// cds_documents.removed_at to fire on DNS blips. Codex flagged it as the
// #1 critical finding in review.
//
// The `resolved` variant carries `docs: ResolvedDocument[]` — a
// non-empty list of candidates — rather than a single doc, so the
// archiver can fan out into multiple cds_documents rows per school
// (ADR 0007 Stage B: one row per historical year for schools like
// Lafayette that expose 20 years on a single landing page).
export type ResolveResult =
  | { kind: "resolved"; docs: ResolvedDocument[] }
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

    // Rewrite Google Drive share URLs into direct-download form before
    // any classification. Without this, the subsequent two-hop fetch
    // lands on Drive's HTML viewer and we can't classify it as a
    // document. See rewriteGoogleDriveUrl comment above.
    absoluteUrl = rewriteGoogleDriveUrl(absoluteUrl);

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
      is_test_artifact: TEST_ARTIFACT_RE.test(filename),
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

    // Same Google Drive rewrite as extractCdsAnchors.
    absoluteUrl = rewriteGoogleDriveUrl(absoluteUrl);

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
      is_test_artifact: TEST_ARTIFACT_RE.test(filename),
    });
  }

  return out;
}

// Ranks candidate document anchors and returns the best single one.
// Legacy single-pick helper kept for tests and any caller that still
// wants "the one" document. The main resolveCdsForSchool path uses
// pickCandidates below, which returns every qualifying anchor so the
// archiver can fan out into multiple cds_documents rows (ADR 0007
// Stage B).
//
//   1. Full CDS beats section files
//   2. Non-test files beat test/draft/backup staging artifacts
//   3. Anchors with a year beat anchors without
//   4. More recent year beats older
//   5. Within ties, document order wins (earlier in HTML = more prominent)
export function findBestSourceAnchor(
  anchors: CdsAnchor[],
): CdsAnchor | null {
  const docs = anchors.filter((a) => a.kind === "document");
  if (docs.length === 0) return null;

  const ranked = [...docs].sort((a, b) => {
    if (a.is_section_file !== b.is_section_file) {
      return a.is_section_file ? 1 : -1;
    }
    if (a.is_test_artifact !== b.is_test_artifact) {
      return a.is_test_artifact ? 1 : -1;
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

// pickCandidates — ADR 0007 Stage B candidate selection.
//
// Transforms a list of document-kind anchors into a list of
// ResolvedDocument candidates the archiver should fan out into. The
// rules are deliberately conservative to keep the unique constraint
// on (school_id, sub_institutional, cds_year) working without schema
// surgery:
//
//   1. Deduplicate by URL. extractCdsAnchors already does intra-HTML
//      dedup; this also catches duplicates across subpage walk results.
//   2. Partition into clean vs demoted (section files + test
//      artifacts). If the clean set is non-empty, use it; otherwise
//      fall back to the demoted set so schools whose only archivable
//      file is a `_test` upload (CSULB) still ship.
//   3. Within the chosen set:
//      - **All have URL years** → return every candidate as its own
//        ResolvedDocument. This is the Lafayette / NMU multi-year
//        historical archive case.
//      - **Exactly one candidate, no URL year** → return it with
//        cds_year = UNKNOWN_YEAR_SENTINEL. This is the direct-doc
//        no-year-in-filename case. Single row per school, no
//        collision.
//      - **Mixed: some have years, some don't** → keep only the
//        year-known candidates. Year-less ones are dropped. They
//        would otherwise collide in the unique key with each other
//        or with each others' sentinels.
//      - **Multiple candidates, none have years** → return null.
//        Caller emits no_cds_found with a "Stage B limitation"
//        reason. Out of scope for this PR; tracked as a follow-up
//        because the real fix needs either a per-candidate
//        disambiguator in cds_year (ugly) or the unique constraint
//        to drop cds_year entirely (riskier).
//
// Return value of null means "fail this school with no_cds_found."
// Empty array means "no document-kind anchors at all" — caller's
// choice how to classify.
export function pickCandidates(
  docs: CdsAnchor[],
  discoveredVia: "landing" | "subpage",
): ResolvedDocument[] | null {
  if (docs.length === 0) return [];

  // Dedupe by URL (minus fragment). extractCdsAnchors does this on
  // its own output, but subpage walk results can collide across
  // parallel fetches.
  const byUrl = new Map<string, CdsAnchor>();
  for (const d of docs) {
    const key = d.url.split("#")[0];
    if (!byUrl.has(key)) byUrl.set(key, d);
  }
  const unique = Array.from(byUrl.values());

  const clean = unique.filter(
    (d) => !d.is_section_file && !d.is_test_artifact,
  );
  const set = clean.length > 0 ? clean : unique;

  const withYear = set.filter((a) => a.year !== null);
  const withoutYear = set.filter((a) => a.year === null);

  let chosen: CdsAnchor[];
  if (withoutYear.length === 0) {
    chosen = withYear;
  } else if (set.length === 1) {
    // Single year-less candidate — sentinel is safe, no collision.
    chosen = set;
  } else if (withYear.length > 0) {
    // Mixed set. Drop year-less to avoid collisions; keep year-known.
    chosen = withYear;
  } else {
    // Multiple year-less candidates. Out of Stage B scope.
    return null;
  }

  return chosen.map((d) => ({
    url: d.url,
    cds_year: d.year ?? UNKNOWN_YEAR_SENTINEL,
    filename: d.filename,
    is_section_file: d.is_section_file,
    is_test_artifact: d.is_test_artifact,
    discovered_via: discoveredVia,
  }));
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

// Walk up the URL path of a direct-document hint and return ancestor URLs
// that could plausibly be CDS landing pages. A school like Boston College
// has `cds_url_hint: .../irp/ir/cds/BC-2022-2023-CDS.pdf` — stripping the
// filename lands on `.../irp/ir/cds/` which, if indexed, lists every year
// the school published. Without this walk, the resolver archives only the
// specific year in the hint and never finds sibling years.
//
// Strategy: ONLY return ancestors whose path contains at least one
// CDS-related segment ("cds", "common-data-set", "ir", "oir", "irp", ...).
// That keeps us from blindly hammering generic Drupal `/sites/default/files/`
// or WordPress `/wp-content/uploads/<date>/` paths that reliably 403 and
// have nothing to do with CDS. For schools whose CDS lives at a semantic
// URL (`/ir/cds/`, `/oira/common-data-set/`), the walk succeeds cheaply;
// for schools with opaque upload-dir URLs, we skip silently and return
// just the direct doc (pre-upgrade behavior).
const MAX_PARENT_LEVELS = 3;
const CDS_LIKE_PATH_SEGMENT_RE =
  /^(cds|common-data-set|common_data_set|institutional-research|institutional_research|ir|oir|oira|iro|irp)$/i;

function pathHasCdsLikeSegment(segments: string[]): boolean {
  return segments.some((s) => CDS_LIKE_PATH_SEGMENT_RE.test(s));
}

export function parentLandingCandidates(hint: string): string[] {
  let parsed: URL;
  try {
    parsed = new URL(hint);
  } catch {
    return [];
  }
  if (parsed.protocol !== "https:" && parsed.protocol !== "http:") return [];

  const segments = parsed.pathname.split("/").filter(Boolean);
  if (segments.length === 0) return [];

  // Strip filename; now segments represent the direct-parent directory.
  const withoutFilename = segments.slice(0, -1);
  if (withoutFilename.length === 0) return [];

  const origin = `${parsed.protocol}//${parsed.host}`;
  const out: string[] = [];

  for (let i = 0; i < MAX_PARENT_LEVELS && i < withoutFilename.length; i++) {
    const ancestorSegments = withoutFilename.slice(0, withoutFilename.length - i);
    if (ancestorSegments.length === 0) break;

    // Only include ancestors whose path has a CDS-related segment. This
    // excludes the common Drupal/WordPress upload trees and other generic
    // file stores.
    if (!pathHasCdsLikeSegment(ancestorSegments)) continue;

    const pathPart = ancestorSegments.join("/");
    out.push(`${origin}/${pathPart}/`);
  }
  return out;
}

// Fetch each candidate ancestor URL; the first one that returns HTML with
// at least one CDS-like document anchor wins. Return that ancestor's
// resolved candidates. Returns [] if no ancestor yielded CDS docs.
//
// This is called ONLY when the hint is a direct document URL. Landing-
// page hints already get the full Case C treatment and don't need this.
async function findSiblingDocsFromParents(
  hint: string,
): Promise<ResolvedDocument[]> {
  const candidates = parentLandingCandidates(hint);
  for (const ancestorUrl of candidates) {
    const resp = await fetchText(ancestorUrl, SUBPAGE_TIMEOUT_MS);
    if (!resp.ok) continue;
    const ct = resp.contentType.toLowerCase();
    if (!ct.includes("text/html")) continue;

    const anchors = extractCdsAnchors(resp.text, resp.finalUrl);
    const docs = anchors.filter((a) => a.kind === "document");
    if (docs.length === 0) continue;

    const picked = pickCandidates(docs, "landing");
    if (picked && picked.length > 0) {
      return picked;
    }
  }
  return [];
}

// Top-level resolver. Given a hint URL, returns a ResolveResult discriminated
// union. See the type for the six possible kinds. Callers branch on kind:
// resolved → archive every doc in `docs`; upstream_gone → mark removed;
// transient → retry later; no_cds_found / unsupported_content → permanent
// failure for human review; blocked_url → permanent (SSRF defense tripped).
//
// ADR 0007 Stage B: `docs` is a non-empty list. Direct-doc hints return
// a single candidate (with cds_year set to the parsed year or the
// UNKNOWN_YEAR_SENTINEL if the filename had no parseable year). Landing
// pages return every CDS-ish document anchor that passes pickCandidates'
// scope rules — which for the common case means one row per historical
// year for schools like Lafayette that expose a long archive on one
// page.
export async function resolveCdsForSchool(
  hint: string,
): Promise<ResolveResult> {
  if (!isSafeUrl(hint)) {
    return { kind: "blocked_url", reason: "hint URL failed safety check" };
  }

  // Case A: direct document hint. schools.yaml points straight at the
  // file. Archive the document, AND try the directory ancestors to find
  // any sibling years the school also publishes.
  //
  // 63% of schools.yaml hints are direct PDFs (e.g. Boston College points
  // at a specific 2022-23 PDF). Without the parent walk we'd archive only
  // that year and walk past every other year in the same directory. The
  // parent walk is best-effort: if every ancestor 403s or has no CDS
  // anchors, we still return the direct doc (current pre-upgrade behavior).
  if (DOCUMENT_EXT_RE.test(hint)) {
    const parsed = new URL(hint);
    const filename = decodeURIComponent(
      parsed.pathname.split("/").filter(Boolean).pop() ?? "",
    );
    const year = normalizeYear(hint) ?? normalizeYear(filename);
    const directDoc: ResolvedDocument = {
      url: hint,
      cds_year: year ?? UNKNOWN_YEAR_SENTINEL,
      filename,
      is_section_file: SECTION_MARKER_RE.test(filename),
      is_test_artifact: TEST_ARTIFACT_RE.test(filename),
      discovered_via: "direct",
    };

    const siblings = await findSiblingDocsFromParents(hint);

    // Merge direct + siblings, dedupe by URL (fragments stripped).
    const byUrl = new Map<string, ResolvedDocument>();
    byUrl.set(directDoc.url.split("#")[0], directDoc);
    for (const sib of siblings) {
      const key = sib.url.split("#")[0];
      if (!byUrl.has(key)) byUrl.set(key, sib);
    }

    return { kind: "resolved", docs: Array.from(byUrl.values()) };
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

  // Case B: landing redirected to a supported document MIME directly.
  // Some schools host their CDS behind an opaque download URL that
  // 302s to the PDF. Same year-fallback treatment as Case A.
  const directExt = extensionFromContentType(ct);
  if (directExt) {
    const parsed = new URL(landing.finalUrl);
    const filename = decodeURIComponent(
      parsed.pathname.split("/").filter(Boolean).pop() ?? "",
    );
    const year = normalizeYear(filename) ?? normalizeYear(landing.finalUrl);
    return {
      kind: "resolved",
      docs: [{
        url: landing.finalUrl,
        cds_year: year ?? UNKNOWN_YEAR_SENTINEL,
        filename,
        is_section_file: SECTION_MARKER_RE.test(filename),
        is_test_artifact: TEST_ARTIFACT_RE.test(filename),
        discovered_via: "direct",
      }],
    };
  }

  if (!ct.includes("text/html")) {
    return {
      kind: "unsupported_content",
      reason: `landing content-type ${landing.contentType || "(none)"}`,
    };
  }

  // Case C: HTML landing page. Extract every CDS-ish document anchor
  // and let pickCandidates decide how many to return.
  const anchors = extractCdsAnchors(landing.text, landing.finalUrl);
  const landingDocs = anchors.filter((a) => a.kind === "document");

  if (landingDocs.length > 0) {
    const candidates = pickCandidates(landingDocs, "landing");
    if (candidates === null) {
      return {
        kind: "no_cds_found",
        reason: "landing has multiple CDS-ish docs but none carry a year signal (Stage B limitation)",
      };
    }
    if (candidates.length > 0) {
      return { kind: "resolved", docs: candidates };
    }
  }

  // Case D: two-hop fallback. Landing has subpage anchors; follow one
  // hop each and collect document candidates from the child pages.
  const subpages = anchors
    .filter((a) => a.kind === "subpage")
    .slice(0, MAX_SUBPAGES_PER_SCHOOL);

  if (subpages.length === 0) {
    return {
      kind: "no_cds_found",
      reason: "landing parsed, no CDS-ish document anchors and no subpages",
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
        return [{
          url: resp.finalUrl,
          filename,
          link_text: sub.link_text,
          year,
          year_source: (year ? "filename" : "unknown") as YearSource,
          kind: "document" as AnchorKind,
          is_section_file: SECTION_MARKER_RE.test(filename),
          is_test_artifact: TEST_ARTIFACT_RE.test(filename),
        }];
      }
      // Non-HTML response with an unrecognized content-type (e.g.
      // application/octet-stream from Google Drive direct-download, or
      // a bare 200 from a CGI endpoint). Inherit the parent subpage's
      // year if it had one and let downloadWithCaps do magic-byte
      // sniffing on the actual bytes.
      if (!subCt.includes("text/html")) {
        if (!sub.year) return [];
        const parsed = new URL(resp.finalUrl);
        const filename = decodeURIComponent(
          parsed.pathname.split("/").filter(Boolean).pop() ?? "",
        );
        return [{
          url: resp.finalUrl,
          filename,
          link_text: sub.link_text,
          year: sub.year,
          year_source: sub.year_source,
          kind: "document" as AnchorKind,
          is_section_file: SECTION_MARKER_RE.test(filename),
          is_test_artifact: TEST_ARTIFACT_RE.test(filename),
        }];
      }
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

  if (allSubDocs.length === 0) {
    return {
      kind: "no_cds_found",
      reason: "two-hop walk found no document anchors",
    };
  }

  const subCandidates = pickCandidates(allSubDocs, "subpage");
  if (subCandidates === null) {
    return {
      kind: "no_cds_found",
      reason: "two-hop walk found multiple CDS-ish docs but none carry a year signal (Stage B limitation)",
    };
  }
  if (subCandidates.length === 0) {
    return {
      kind: "no_cds_found",
      reason: "two-hop walk found no qualifying document candidates",
    };
  }
  return { kind: "resolved", docs: subCandidates };
}
