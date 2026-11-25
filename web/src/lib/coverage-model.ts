// PRD 040 M2: pure model behind the /coverage dashboard. The component reads
// the URL, calls these, and renders. Keeping the logic here is what lets the
// tests cover default, preset and ?all=1 views, search, the weighted share and
// the CSVs without a browser.

import { isCanonicalCdsYear } from "./format";
import { DATA_LICENSE_NAME, DATA_LICENSE_URL } from "./data-license";
import { csvLine } from "./data-quality";
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

// ── CSV ───────────────────────────────────────────────────────────

export const COVERAGE_CSV_COLUMNS = [
  "ipeds_id",
  "school_id",
  "state",
  "undergraduate_enrollment",
  "status",
  "latest_year_with_numbers",
  "latest_year_found",
  "last_checked",
] as const;

/** `#` comment block for the coverage CSV (a browser download can't send the Link license header). */
export function coverageCsvNotice(generatedOn: string): string {
  return (
    [
      `collegedata.fyi coverage by school, downloaded ${generatedOn}.`,
      `school_id, state, status, latest_year_with_numbers, latest_year_found and last_checked are licensed ${DATA_LICENSE_NAME} (${DATA_LICENSE_URL}). Credit collegedata.fyi (https://www.collegedata.fyi).`,
      "ipeds_id and undergraduate_enrollment come from federal sources (NCES IPEDS and College Scorecard). Our license does not cover them: credit the federal source.",
      "latest_year_with_numbers is the latest year whose numbers we read. latest_year_found is the latest year of any file we hold.",
    ]
      .map((l) => `# ${l}`)
      .join("\r\n") + "\r\n"
  );
}

export function buildCoverageCsv(rows: InstitutionCoverage[], generatedOn: string): string {
  const lines = [csvLine([...COVERAGE_CSV_COLUMNS])];
  for (const r of rows) {
    lines.push(
      csvLine([
        r.ipeds_id,
        r.school_id,
        r.state,
        r.undergraduate_enrollment,
        COVERAGE_STATUS_LABELS[r.coverage_status] ?? r.coverage_status,
        hasYearWithNumbers(r) ? r.latest_available_cds_year : "",
        isCanonicalCdsYear(r.latest_found_cds_year) ? r.latest_found_cds_year : "",
        r.last_checked_at ?? "",
      ]),
    );
  }
  return coverageCsvNotice(generatedOn) + lines.join("\r\n") + "\r\n";
}
