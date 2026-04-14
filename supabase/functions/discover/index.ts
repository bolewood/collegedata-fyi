// collegedata.fyi — discovery scraper (M1a dry run)
//
// Reads each pilot school's IR landing page, parses the HTML for CDS-labeled
// links, optionally follows one hop of HTML sub-pages (some schools like
// CMU use a landing page that links to per-year HTML pages rather than
// directly to PDFs), normalizes the year span on each discovered document,
// and returns a structured JSON report of what would be discovered.
//
// No Storage uploads, no database writes. This is the parsing-logic
// iteration point.
//
// M1 subdivision:
//   M1a (this): HTML parsing, two-hop navigation, year normalization
//   M1b: swap embedded pilots for schools.yaml load; add Storage uploads
//        and cds_documents upsert
//   M1c: cron schedule + failure-state logging for the full corpus
//
// Format detection (Tier 2 fillable vs Tier 4 flattened) is deliberately
// NOT done here — that happens in the Python extraction worker where
// pypdf.get_fields() gives us a reliable answer. The edge function stays
// dumb: find URLs, record provenance, upsert, done.

import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { DOMParser, type Element as DomElement } from "jsr:@b-fuze/deno-dom";

const USER_AGENT =
  "collegedata.fyi/0.1 (research probe; https://collegedata.fyi)";
const LANDING_TIMEOUT_MS = 30_000;
const SUBPAGE_TIMEOUT_MS = 15_000;
const MAX_SUBPAGES_PER_SCHOOL = 25;

// ─── Pilot schools (embedded for M1a) ─────────────────────────────────────
// Schools are hard-coded here during M1a so we can iterate on parsing
// logic without coupling to schools.yaml loading. M1b replaces this
// constant with a fetch from the committed schools.yaml.

interface PilotSchool {
  id: string;
  name: string;
  cds_url_hint: string;
}

const PILOT_SCHOOLS: PilotSchool[] = [
  {
    id: "yale",
    name: "Yale University",
    cds_url_hint: "https://oir.yale.edu/common-data-set",
  },
  {
    id: "harvey-mudd",
    name: "Harvey Mudd College",
    cds_url_hint:
      "https://www.hmc.edu/institutional-research/common-data-set/",
  },
  {
    id: "harvard",
    name: "Harvard University",
    cds_url_hint: "https://oira.harvard.edu/common-data-set/",
  },
  {
    id: "mit",
    name: "MIT",
    cds_url_hint: "https://web.mit.edu/ir/cds/",
  },
  {
    id: "carnegie-mellon",
    name: "Carnegie Mellon University",
    cds_url_hint: "https://www.cmu.edu/ira/CDS/",
  },
];

// ─── Year normalization ──────────────────────────────────────────────────
// Schools use inconsistent year formats in filenames and link text.
// Handled forms:
//
//   2024-2025          → 2024-25   (long span, hyphen)
//   2024–2025          → 2024-25   (long span, en-dash)
//   2024_2025          → 2024-25   (long span, underscore)
//   2024 2025          → 2024-25   (long span, space)
//   2024-25            → 2024-25   (long + short, hyphen)
//   13-14              → 2013-14   (short + short — requires clean boundaries)
//   2425               → 2024-25   (no separator, 4-digit)
//
// Each pattern is tried in order. The first match whose two captured halves
// form a valid academic year span (y2 = y1 + 1 mod 100) wins.

const YEAR_PATTERNS: RegExp[] = [
  // long + long: 2024-2025, 2024–2025, 2024_2025, 2024 2025
  /(20\d{2})[\s_\-–—]+(20\d{2})/g,
  // long + short: 2024-25, 2024–25
  /(20\d{2})[\s_\-–—]+(\d{2})(?=\D|$)/g,
  // short + short: 13-14, 99-00 (requires non-digit boundaries)
  /(?:^|[^0-9])(\d{2})[\s_\-–—]+(\d{2})(?=\D|$)/g,
  // no separator 4-digit: 2425, 2526, 0001
  /(?:^|[^0-9])(\d{2})(\d{2})(?=\D|$)/g,
];

function normalizeYear(raw: string | null | undefined): string | null {
  if (!raw) return null;
  for (let patternIndex = 0; patternIndex < YEAR_PATTERNS.length; patternIndex++) {
    const pattern = YEAR_PATTERNS[patternIndex];
    pattern.lastIndex = 0;
    for (const m of raw.matchAll(pattern)) {
      const rawA = parseInt(m[1], 10);
      const rawB = parseInt(m[2], 10);

      // Pattern 4 (no-separator 4-digit) false-positive guard:
      // "2021" would parse as span 20-21 (matching rawA=20, rawB=21).
      // But "2021" is almost always a full-year reference, not a 2-digit
      // span. Skip any match where the first two digits are "19" or "20".
      if (patternIndex === 3 && (m[1] === "19" || m[1] === "20")) continue;

      let y1: number;
      let y2Partial: number;

      if (rawA >= 1990 && rawA <= 2099) {
        // rawA is a full year (from long-form patterns 1 or 2)
        y1 = rawA;
        y2Partial = rawB >= 100 ? rawB % 100 : rawB;
      } else if (rawA >= 0 && rawA <= 99 && rawB >= 0 && rawB <= 99) {
        // Both short. Determine century: 9X-0Y spans the millennium
        // (1999-00, 1998-99, etc.); otherwise assume 20xx.
        if (rawA >= 90 && rawB <= 9) {
          y1 = 1900 + rawA;
        } else if (rawA >= 80 && rawA <= 89) {
          y1 = 1900 + rawA;
        } else {
          y1 = 2000 + rawA;
        }
        y2Partial = rawB;
      } else {
        continue;
      }

      const expectedY2 = (y1 + 1) % 100;
      if (y2Partial !== expectedY2) continue;

      // Reject implausibly old/new academic years. Lower bound is 1990
      // to accommodate schools with deep archives (CMU has 1999-00).
      if (y1 < 1990 || y1 > 2035) continue;

      return `${y1}-${expectedY2.toString().padStart(2, "0")}`;
    }
  }
  return null;
}

// ─── CDS anchor extraction ───────────────────────────────────────────────
// Walks every <a href> on a page and returns anchors that match CDS
// keywords. Each anchor is categorized as a document (PDF / XLSX / DOCX)
// or as a subpage (HTML or no extension — a candidate for second-hop
// navigation).

const CDS_KEYWORDS_RE = /common\s*data\s*set|\bcds\b/i;
const DOCUMENT_EXT_RE = /\.(pdf|xlsx|docx)(\?|#|$)/i;
const SECTION_MARKER_RE =
  /\b(general[-_ ]?information|enrollment|first[-_ ]?time|transfer|academic[-_ ]?offerings?|student[-_ ]?life|annual[-_ ]?expenses?|financial[-_ ]?aid|instructional[-_ ]?faculty|degrees?[-_ ]?conferred|section[-_ ]?[a-j])/i;

type AnchorKind = "document" | "subpage";
type YearSource = "filename" | "url_path" | "link_text" | "unknown";

interface CdsAnchor {
  url: string;
  filename: string;
  link_text: string;
  year: string | null;
  year_source: YearSource;
  kind: AnchorKind;
  is_section_file: boolean;
}

function extractCdsAnchors(
  html: string,
  baseUrl: string,
): CdsAnchor[] {
  const doc = new DOMParser().parseFromString(html, "text/html");
  if (!doc) return [];

  const base = new URL(baseUrl);
  const seen = new Set<string>();
  const results: CdsAnchor[] = [];

  for (const node of doc.querySelectorAll("a[href]")) {
    const el = node as unknown as DomElement;
    const href = el.getAttribute("href") ?? "";
    if (!href) continue;
    if (/^(#|mailto:|tel:|javascript:)/i.test(href)) continue;

    const linkText = (el.textContent ?? "").replace(/\s+/g, " ").trim();

    // Resolve to absolute URL first so we can check the pathname (not the
    // hostname) for keywords. Without this, links to commondataset.org
    // would false-match simply because "commondataset" is in the hostname.
    let absoluteUrl: string;
    try {
      absoluteUrl = new URL(href, base).toString();
    } catch {
      continue;
    }

    const absNoFragment = absoluteUrl.split("#")[0];
    if (seen.has(absNoFragment)) continue;
    seen.add(absNoFragment);

    const parsed = new URL(absoluteUrl);
    const pathSegments = parsed.pathname.split("/").filter(Boolean);
    const filename = decodeURIComponent(
      pathSegments[pathSegments.length - 1] ?? "",
    );
    const fullPath = decodeURIComponent(parsed.pathname);

    // CDS keyword check: filename, link text, or URL path. Deliberately
    // excludes the hostname — otherwise every link to commondataset.org
    // would match even when the document itself has nothing to do with CDS
    // (e.g. the Initiative's "Benefits of Completing Publisher Survey"
    // brochure that several IR pages link to).
    if (
      !CDS_KEYWORDS_RE.test(filename) &&
      !CDS_KEYWORDS_RE.test(linkText) &&
      !CDS_KEYWORDS_RE.test(fullPath)
    ) continue;

    let year: string | null = null;
    let yearSource: YearSource = "unknown";
    year = normalizeYear(filename);
    if (year) {
      yearSource = "filename";
    } else {
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

    results.push({
      url: absoluteUrl,
      filename,
      link_text: linkText,
      year,
      year_source: yearSource,
      kind,
      is_section_file: SECTION_MARKER_RE.test(filename),
    });
  }

  return results;
}

// ─── Per-school discovery ────────────────────────────────────────────────

interface DiscoveredDocument {
  year: string | null;
  year_source: YearSource;
  url: string;
  filename: string;
  link_text: string;
  is_section_file: boolean;
  discovered_via: "landing" | "subpage";
  parent_subpage_url?: string;
}

interface SchoolResult {
  school_id: string;
  school_name: string;
  landing_url: string;
  landing_final_url: string | null;
  landing_status: number | null;
  landing_content_type: string | null;
  subpages_fetched: number;
  discovered_documents: DiscoveredDocument[];
  year_summary: {
    distinct_years: number;
    years: string[];
    links_without_year: number;
    section_files: number;
  };
  failures: string[];
  duration_ms: number;
}

async function fetchText(
  url: string,
  timeoutMs: number,
): Promise<{ ok: boolean; status: number; contentType: string; text: string; finalUrl: string; error?: string }> {
  try {
    const r = await fetch(url, {
      headers: { "User-Agent": USER_AGENT },
      signal: AbortSignal.timeout(timeoutMs),
      redirect: "follow",
    });
    const contentType = r.headers.get("content-type") ?? "";
    const text = r.ok && contentType.toLowerCase().includes("text/html")
      ? await r.text()
      : "";
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

async function discoverSchool(school: PilotSchool): Promise<SchoolResult> {
  const started = performance.now();
  const result: SchoolResult = {
    school_id: school.id,
    school_name: school.name,
    landing_url: school.cds_url_hint,
    landing_final_url: null,
    landing_status: null,
    landing_content_type: null,
    subpages_fetched: 0,
    discovered_documents: [],
    year_summary: {
      distinct_years: 0,
      years: [],
      links_without_year: 0,
      section_files: 0,
    },
    failures: [],
    duration_ms: 0,
  };

  const landingResp = await fetchText(school.cds_url_hint, LANDING_TIMEOUT_MS);
  result.landing_final_url = landingResp.finalUrl;
  result.landing_status = landingResp.status || null;
  result.landing_content_type = landingResp.contentType || null;

  if (!landingResp.ok) {
    result.failures.push(
      `landing fetch failed: ${landingResp.error ?? `HTTP ${landingResp.status}`}`,
    );
    result.duration_ms = Math.round(performance.now() - started);
    return result;
  }

  const ct = landingResp.contentType.toLowerCase();

  // Direct-PDF landing
  if (ct.includes("application/pdf")) {
    const parsed = new URL(landingResp.finalUrl);
    const filename = decodeURIComponent(
      parsed.pathname.split("/").filter(Boolean).pop() ?? "",
    );
    const year = normalizeYear(filename);
    result.discovered_documents.push({
      year,
      year_source: year ? "filename" : "unknown",
      url: landingResp.finalUrl,
      filename,
      link_text: "(direct PDF landing)",
      is_section_file: false,
      discovered_via: "landing",
    });
    result.duration_ms = Math.round(performance.now() - started);
    summarizeYears(result);
    return result;
  }

  if (!ct.includes("text/html")) {
    result.failures.push(`unexpected content-type: ${landingResp.contentType}`);
    result.duration_ms = Math.round(performance.now() - started);
    return result;
  }

  // Parse the landing HTML
  const anchors = extractCdsAnchors(landingResp.text, landingResp.finalUrl);

  // First pass: documents linked directly from the landing page
  for (const a of anchors) {
    if (a.kind === "document") {
      result.discovered_documents.push({
        year: a.year,
        year_source: a.year_source,
        url: a.url,
        filename: a.filename,
        link_text: a.link_text,
        is_section_file: a.is_section_file,
        discovered_via: "landing",
      });
    }
  }

  // Second pass: follow HTML subpages (CMU-style two-hop navigation)
  const subpages = anchors
    .filter((a) => a.kind === "subpage")
    .slice(0, MAX_SUBPAGES_PER_SCHOOL);

  if (subpages.length > 0) {
    const subResults = await Promise.all(
      subpages.map(async (sub) => {
        const subResp = await fetchText(sub.url, SUBPAGE_TIMEOUT_MS);
        if (!subResp.ok) return { sub, docs: [] as DiscoveredDocument[] };
        const ctSub = subResp.contentType.toLowerCase();
        if (!ctSub.includes("text/html")) {
          // Subpage turned out to be a direct PDF — rare but possible
          if (ctSub.includes("application/pdf")) {
            const parsed = new URL(subResp.finalUrl);
            const filename = decodeURIComponent(
              parsed.pathname.split("/").filter(Boolean).pop() ?? "",
            );
            const year = normalizeYear(filename) ?? sub.year;
            return {
              sub,
              docs: [{
                year,
                year_source: (year
                  ? (normalizeYear(filename) ? "filename" : sub.year_source)
                  : "unknown") as YearSource,
                url: subResp.finalUrl,
                filename,
                link_text: sub.link_text,
                is_section_file: false,
                discovered_via: "subpage" as const,
                parent_subpage_url: sub.url,
              }],
            };
          }
          return { sub, docs: [] as DiscoveredDocument[] };
        }
        const subAnchors = extractCdsAnchors(subResp.text, subResp.finalUrl);
        const docs: DiscoveredDocument[] = [];
        for (const a of subAnchors) {
          if (a.kind !== "document") continue;
          docs.push({
            year: a.year ?? sub.year,
            year_source: a.year ?? a.year_source !== "unknown"
              ? a.year_source
              : (sub.year ? "link_text" : "unknown"),
            url: a.url,
            filename: a.filename,
            link_text: a.link_text,
            is_section_file: a.is_section_file,
            discovered_via: "subpage",
            parent_subpage_url: sub.url,
          });
        }
        return { sub, docs };
      }),
    );

    result.subpages_fetched = subpages.length;
    for (const sr of subResults) {
      result.discovered_documents.push(...sr.docs);
    }

    // Deduplicate by final URL
    const dedupe = new Map<string, DiscoveredDocument>();
    for (const d of result.discovered_documents) {
      if (!dedupe.has(d.url)) dedupe.set(d.url, d);
    }
    result.discovered_documents = Array.from(dedupe.values());
  }

  if (result.discovered_documents.length === 0) {
    result.failures.push("landing parsed, no CDS documents found");
  }

  summarizeYears(result);
  result.duration_ms = Math.round(performance.now() - started);
  return result;
}

function summarizeYears(result: SchoolResult): void {
  const yearSet = new Set<string>();
  let missingYear = 0;
  let sectionCount = 0;
  for (const d of result.discovered_documents) {
    if (d.year) yearSet.add(d.year);
    else missingYear += 1;
    if (d.is_section_file) sectionCount += 1;
  }
  result.year_summary.distinct_years = yearSet.size;
  result.year_summary.years = Array.from(yearSet).sort().reverse();
  result.year_summary.links_without_year = missingYear;
  result.year_summary.section_files = sectionCount;
}

// ─── HTTP handler ────────────────────────────────────────────────────────

Deno.serve(async (req: Request) => {
  const url = new URL(req.url);
  const schoolFilter = url.searchParams.get("schools")?.split(",").map((s) =>
    s.trim()
  );

  const target = schoolFilter
    ? PILOT_SCHOOLS.filter((s) => schoolFilter.includes(s.id))
    : PILOT_SCHOOLS;

  const results = await Promise.all(target.map((s) => discoverSchool(s)));

  const summary = {
    status: "dry_run",
    mode: "m1a",
    probed_schools: results.length,
    schools_with_discoveries:
      results.filter((r) => r.discovered_documents.length > 0).length,
    schools_with_failures: results.filter((r) => r.failures.length > 0).length,
    total_documents_discovered: results.reduce(
      (n, r) => n + r.discovered_documents.length,
      0,
    ),
    total_distinct_year_slots: results.reduce(
      (n, r) => n + r.year_summary.distinct_years,
      0,
    ),
    total_subpages_fetched: results.reduce((n, r) => n + r.subpages_fetched, 0),
  };

  return new Response(
    JSON.stringify({ summary, results }, null, 2),
    {
      headers: {
        "Content-Type": "application/json",
        "Cache-Control": "no-store",
      },
    },
  );
});
