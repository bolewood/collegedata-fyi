// PRD 040 M2: pure model behind the /coverage dashboard. The component reads
// the URL, calls these, and renders. Keeping the logic here is what lets the
// tests cover default, preset and ?all=1 views, search, the weighted share and
// the CSVs without a browser.

import { isCanonicalCdsYear } from "./format";
import { DATA_LICENSE_NAME } from "./data-license";
import { compareYearsDesc, csvLine } from "./data-quality";
import { cdsFreshnessFloor } from "./freshness";
import type { CoverageStatus, InstitutionCoverage } from "./types";

// Display order for the status tiles and the filter chips: most positive to
// least positive, then never checked.
export const STATUS_ORDER: CoverageStatus[] = [
  "cds_available_current",
  "cds_available_stale",
  "cds_found_processing",
  "latest_found_extract_failed_with_prior_available",
  "extract_failed",
  "source_not_automatically_accessible",
  "no_public_cds_found",
  "verified_absent",
  "not_checked",
];

/** The landing view: every status except "have it" and "verified absent". */
export const DEFAULT_MISSING: CoverageStatus[] = STATUS_ORDER.filter(
  (s) => s !== "cds_available_current" && s !== "verified_absent",
);

/** The "Has a CDS" preset: a link, because the dashboard already accepts a status list. */
export const HAS_CDS_STATUSES: CoverageStatus[] = ["cds_available_current", "cds_available_stale"];
export const HAS_CDS_HREF = `/coverage?status=${HAS_CDS_STATUSES.join(",")}`;

/** Plain-word status labels (PRD 040 glossary). Tiles and row badges both use this map. */
export const COVERAGE_STATUS_LABELS: Record<CoverageStatus, string> = {
  cds_available_current: "CDS available",
  cds_available_stale: "Older CDS",
  cds_found_processing: "Report not read yet",
  latest_found_extract_failed_with_prior_available: "Latest report couldn’t be read",
  extract_failed: "Report couldn’t be read",
  source_not_automatically_accessible: "Source blocked",
  no_public_cds_found: "No public CDS",
  verified_absent: "Verified absent",
  not_checked: "Not checked",
  out_of_scope: "Out of scope",
};

export const ENROLLMENT_BANDS = [
  { id: "any", label: "Any size" },
  { id: "u2k", label: "<2K", test: (n: number | null) => n != null && n < 2000 },
  { id: "2k-10k", label: "2–10K", test: (n: number | null) => n != null && n >= 2000 && n < 10000 },
  { id: "10k-25k", label: "10–25K", test: (n: number | null) => n != null && n >= 10000 && n < 25000 },
  { id: "25k+", label: "25K+", test: (n: number | null) => n != null && n >= 25000 },
] as const;
export type EnrollmentBandId = (typeof ENROLLMENT_BANDS)[number]["id"];

export const RECENCY_OPTIONS = [
  { id: "any", label: "Any time" },
  { id: "30d", label: "Last 30 days", days: 30 },
  { id: "90d", label: "Last 90 days", days: 90 },
  { id: "older", label: "Older than 90 days", olderThan: 90 },
  { id: "never", label: "Never checked" },
] as const;
export type RecencyId = (typeof RECENCY_OPTIONS)[number]["id"];

// ── View state (all of it lives in the URL) ───────────────────────

export type CoverageView = {
  statuses: Set<CoverageStatus>;
  all: boolean;
  state: string | null;
  size: EnrollmentBandId;
  checked: RecencyId;
  q: string;
};

export function parseCoverageView(params: { get(name: string): string | null }): CoverageView {
  const all = params.get("all") === "1";
  const statusParam = params.get("status");
  let statuses: Set<CoverageStatus>;
  if (all) {
    statuses = new Set(STATUS_ORDER);
  } else if (statusParam) {
    const parts = statusParam.split(",").filter(Boolean) as CoverageStatus[];
    statuses = new Set(parts.length > 0 ? parts : DEFAULT_MISSING);
  } else {
    statuses = new Set(DEFAULT_MISSING);
  }
  return {
    statuses,
    all,
    state: params.get("state") || null,
    size: (params.get("size") as EnrollmentBandId | null) ?? "any",
    checked: (params.get("checked") as RecencyId | null) ?? "any",
    q: params.get("q") ?? "",
  };
}

export function sameSet<T>(a: Set<T>, b: Set<T>): boolean {
  if (a.size !== b.size) return false;
  for (const v of a) if (!b.has(v)) return false;
  return true;
}

// ── Search ────────────────────────────────────────────────────────

function fold(s: string): string {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
}

/** Name substring (accent- and case-insensitive) or IPEDS ID prefix/substring. An empty query matches all. */
export function matchesSearch(row: Pick<InstitutionCoverage, "school_name" | "ipeds_id">, query: string): boolean {
  const q = fold(query);
  if (!q) return true;
  if (fold(row.school_name).includes(q)) return true;
  return /^\d+$/.test(q) && String(row.ipeds_id ?? "").includes(q);
}

// ── Filtering ─────────────────────────────────────────────────────

export function filterCoverageRows(
  rows: InstitutionCoverage[],
  view: CoverageView,
  now: number = Date.now(),
): InstitutionCoverage[] {
  const band = ENROLLMENT_BANDS.find((b) => b.id === view.size);
  const recency = RECENCY_OPTIONS.find((r) => r.id === view.checked);
  return rows.filter((r) => {
    if (!view.statuses.has(r.coverage_status)) return false;
    if (view.state && r.state !== view.state) return false;
    if (band && "test" in band && !band.test(r.undergraduate_enrollment)) return false;
    if (recency && recency.id !== "any") {
      const ts = r.last_checked_at ? new Date(r.last_checked_at).getTime() : null;
      if (recency.id === "never") {
        if (ts != null) return false;
      } else if ("days" in recency) {
        if (ts == null || now - ts > recency.days * 86_400_000) return false;
      } else if ("olderThan" in recency) {
        if (ts == null) return false;
        if (now - ts <= recency.olderThan * 86_400_000) return false;
      }
    }
    return matchesSearch(r, view.q);
  });
}

// ── Summary strip ─────────────────────────────────────────────────

export type WeightedShare = {
  /** Summed enrollment of rows with a latest year with numbers. */
  numerator: number;
  /** Summed enrollment of all rows with a known enrollment. */
  denominator: number;
  /** null when no row has an enrollment figure: there is no share to show. */
  share: number | null;
  /** Rows with no enrollment figure, left out of both sums. */
  withoutEnrollment: number;
};

export function hasYearWithNumbers(row: Pick<InstitutionCoverage, "latest_available_cds_year">): boolean {
  return isCanonicalCdsYear(row.latest_available_cds_year);
}

export function weightedShare(rows: InstitutionCoverage[]): WeightedShare {
  let numerator = 0;
  let denominator = 0;
  let withoutEnrollment = 0;
  for (const r of rows) {
    const n = r.undergraduate_enrollment;
    if (n == null) {
      withoutEnrollment += 1;
      continue;
    }
    denominator += n;
    if (hasYearWithNumbers(r)) numerator += n;
  }
  return { numerator, denominator, share: denominator > 0 ? numerator / denominator : null, withoutEnrollment };
}

export type YearBucket = { id: string; label: string; count: number };

/** The year to anchor the breakdown on: the snapshot's current year if there is one, else the freshness floor. */
export function currentCdsYear(snapshotCurrentYear: string | null | undefined, now: Date = new Date()): string {
  return isCanonicalCdsYear(snapshotCurrentYear) ? snapshotCurrentYear : cdsFreshnessFloor(now);
}

/** Academic year `back` years before `year` ("2025-26", 1 gives "2024-25"). */
function yearBefore(year: string, back: number): string {
  const start = Number(year.slice(0, 4)) - back;
  return `${start}-${String((start + 1) % 100).padStart(2, "0")}`;
}

/**
 * Latest year with numbers, in a fixed window anchored on the current CDS year:
 * current, previous, the one before, older, none. A year nobody has shows as 0
 * rather than vanishing. A value that isn't a real year (`unknown`) counts as
 * none, and a year newer than the anchor counts as current, so the buckets
 * always add up to the row count.
 */
export function latestYearBuckets(rows: InstitutionCoverage[], currentYear: string): YearBucket[] {
  const window = [0, 1, 2].map((back) => yearBefore(currentYear, back));
  const counts = new Map(window.map((y) => [y, 0]));
  const anchorStart = Number(currentYear.slice(0, 4));
  let older = 0;
  let none = 0;
  for (const r of rows) {
    const y = r.latest_available_cds_year;
    if (!hasYearWithNumbers(r)) {
      none += 1;
    } else if (Number((y as string).slice(0, 4)) >= anchorStart) {
      counts.set(currentYear, (counts.get(currentYear) ?? 0) + 1);
    } else if (counts.has(y as string)) {
      counts.set(y as string, (counts.get(y as string) ?? 0) + 1);
    } else {
      older += 1;
    }
  }
  return [
    ...window.map((y) => ({ id: y, label: y, count: counts.get(y) ?? 0 })),
    { id: "older", label: "Older", count: older },
    { id: "none", label: "None", count: none },
  ];
}

// ── Sorting (the table on screen and the CSV route share it) ───────

export type SortKey = "name" | "state" | "enrollment" | "status" | "numbers" | "found" | "checked";
export type SortDir = "asc" | "desc";

const SORT_KEYS: readonly SortKey[] = ["name", "state", "enrollment", "status", "numbers", "found", "checked"];

/** The direction a column starts in when first chosen. */
export function defaultSortDir(key: SortKey): SortDir {
  return key === "enrollment" || key === "checked" ? "desc" : "asc";
}

/** `sort` and `dir` from a query string. Anything unrecognised falls back to name, A to Z. */
export function parseCoverageSort(params: { get(name: string): string | null }): { key: SortKey; dir: SortDir } {
  const key = SORT_KEYS.find((k) => k === params.get("sort")) ?? "name";
  const dir = params.get("dir") === "asc" || params.get("dir") === "desc" ? (params.get("dir") as SortDir) : defaultSortDir(key);
  return { key, dir };
}

/** A sorted copy. Ties break by school name, except name itself. */
export function sortCoverageRows(rows: InstitutionCoverage[], key: SortKey, dir: SortDir): InstitutionCoverage[] {
  const d = dir === "asc" ? 1 : -1;
  const byName = (a: InstitutionCoverage, b: InstitutionCoverage) => a.school_name.localeCompare(b.school_name);
  return [...rows].sort((a, b) => {
    switch (key) {
      case "name":
        return byName(a, b) * d;
      case "state":
        return (a.state ?? "").localeCompare(b.state ?? "") * d || byName(a, b);
      case "enrollment": {
        const ae = a.undergraduate_enrollment;
        const be = b.undergraduate_enrollment;
        if (ae == null && be == null) return byName(a, b);
        if (ae == null) return 1;
        if (be == null) return -1;
        return (ae - be) * d;
      }
      case "status":
        return (STATUS_ORDER.indexOf(a.coverage_status) - STATUS_ORDER.indexOf(b.coverage_status)) * d || byName(a, b);
      case "numbers":
        // compareYearsDesc is newest-first, so flip it: ascending means oldest first.
        return -compareYearsDesc(a.latest_available_cds_year ?? "none", b.latest_available_cds_year ?? "none") * d || byName(a, b);
      case "found":
        return -compareYearsDesc(a.latest_found_cds_year ?? "none", b.latest_found_cds_year ?? "none") * d || byName(a, b);
      case "checked": {
        const ac = a.last_checked_at ? new Date(a.last_checked_at).getTime() : 0;
        const bc = b.last_checked_at ? new Date(b.last_checked_at).getTime() : 0;
        return (ac - bc) * d || byName(a, b);
      }
    }
  });
}

// ── CSV ───────────────────────────────────────────────────────────

export const COVERAGE_CSV_COLUMNS = [
  "ipeds_id",
  "school_id",
  "school_name",
  "state",
  "undergraduate_enrollment",
  "status",
  "latest_year_with_numbers",
  "latest_year_found",
  "last_checked",
] as const;

/** Said next to the download links. The file itself carries no notice (a comment block breaks readers); the license rides in the route's Link header. */
export const COVERAGE_CSV_FEDERAL_NOTE = `IPEDS ID and undergraduate enrollment are federal figures from IPEDS, which our license doesn\u2019t cover; the other columns are licensed ${DATA_LICENSE_NAME}.`;

/** The route that serves the CSV. `query` is the page's own query string; the sort is added so the file matches the table on screen. */
export function coverageCsvHref(query: string, sort?: { key: SortKey; dir: SortDir }): string {
  const params = new URLSearchParams(query);
  if (sort) {
    params.set("sort", sort.key);
    params.set("dir", sort.dir);
  }
  const qs = params.toString();
  return qs ? `/coverage.csv?${qs}` : "/coverage.csv";
}

export function coverageCsvFilename(scope: "view" | "all", day: string): string {
  return `collegedata-coverage-${scope === "all" ? "all-colleges" : "view"}-${day}.csv`;
}

export function buildCoverageCsv(rows: InstitutionCoverage[]): string {
  const lines = [csvLine([...COVERAGE_CSV_COLUMNS])];
  for (const r of rows) {
    lines.push(
      csvLine([
        r.ipeds_id,
        r.school_id,
        r.school_name,
        r.state,
        r.undergraduate_enrollment,
        COVERAGE_STATUS_LABELS[r.coverage_status] ?? r.coverage_status,
        hasYearWithNumbers(r) ? r.latest_available_cds_year : "",
        isCanonicalCdsYear(r.latest_found_cds_year) ? r.latest_found_cds_year : "",
        r.last_checked_at ?? "",
      ]),
    );
  }
  return lines.join("\r\n") + "\r\n";
}
