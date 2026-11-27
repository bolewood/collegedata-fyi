import { describe, expect, it } from "vitest";
import {
  COVERAGE_CSV_COLUMNS,
  COVERAGE_CSV_DEFINITION_NOTE,
  COVERAGE_CSV_FEDERAL_COLUMNS,
  COVERAGE_CSV_FEDERAL_NOTE,
  COVERAGE_CSV_LICENSED_COLUMNS,
  COVERAGE_STATUS_LABELS,
  DEFAULT_MISSING,
  HAS_CDS_HREF,
  buildCoverageCsv,
  coverageCsvFilename,
  coverageViewRows,
  defaultSortDir,
  currentCdsYear,
  filterCoverageRows,
  latestYearBuckets,
  matchesSearch,
  parseCoverageView,
  sortCoverageRows,
  type SortDir,
  type SortKey,
  weightedShare,
} from "./coverage-model";
import type { CoverageStatus, InstitutionCoverage } from "./types";

function row(over: Partial<InstitutionCoverage> & { school_id: string }): InstitutionCoverage {
  return {
    ipeds_id: "100000",
    school_name: over.school_id,
    city: null,
    state: "NY",
    website_url: null,
    undergraduate_enrollment: 1000,
    coverage_status: "cds_available_current",
    coverage_label: "CDS available",
    coverage_summary: "",
    latest_available_cds_year: "2025-26",
    latest_found_cds_year: "2025-26",
    last_checked_at: "2026-11-20T00:00:00Z",
    can_submit_source: false,
    ...over,
  };
}

const ROWS: InstitutionCoverage[] = [
  row({ school_id: "alpha", school_name: "Alpha College", ipeds_id: "111111", undergraduate_enrollment: 5000 }),
  row({
    school_id: "beta", school_name: "Beta University", ipeds_id: "222222", undergraduate_enrollment: 3000,
    coverage_status: "cds_available_stale", latest_available_cds_year: "2023-24", latest_found_cds_year: "2024-25",
  }),
  row({
    school_id: "gamma", school_name: "Gamma Institute", ipeds_id: "333333", undergraduate_enrollment: 2000,
    coverage_status: "no_public_cds_found", latest_available_cds_year: null, latest_found_cds_year: null,
  }),
  row({
    school_id: "delta", school_name: "École Delta", ipeds_id: "444444", undergraduate_enrollment: null,
    coverage_status: "not_checked", latest_available_cds_year: null, latest_found_cds_year: null, state: "CA",
  }),
  row({
    school_id: "eps", school_name: "Epsilon State", ipeds_id: "555555", undergraduate_enrollment: 10000,
    coverage_status: "cds_available_stale", latest_available_cds_year: "2021-22", latest_found_cds_year: "2021-22",
  }),
];

const view = (qs: string) => parseCoverageView(new URLSearchParams(qs));
const ids = (rows: InstitutionCoverage[]) => rows.map((r) => r.school_id);

describe("views: default, preset and ?all=1", () => {
  it("defaults to missing-only", () => {
    const v = view("");
    expect([...v.statuses].sort()).toEqual([...DEFAULT_MISSING].sort());
    expect(ids(filterCoverageRows(ROWS, v))).toEqual(["beta", "gamma", "delta", "eps"]);
  });

  it("the Has a CDS preset is a plain link whose status list the view already accepts", () => {
    expect(HAS_CDS_HREF).toBe("/coverage?status=cds_available_current,cds_available_stale");
    const v = view(HAS_CDS_HREF.split("?")[1]);
    expect(ids(filterCoverageRows(ROWS, v))).toEqual(["alpha", "beta", "eps"]);
  });

  it("?all=1 means every tracked college, whatever status is also given", () => {
    const v = view("all=1&status=cds_available_current");
    expect(ids(filterCoverageRows(ROWS, v))).toEqual(ids(ROWS));
  });

  it("an empty status param falls back to the default", () => {
    expect([...view("status=").statuses].sort()).toEqual([...DEFAULT_MISSING].sort());
  });
});

describe("search", () => {
  it("matches school names, ignoring case and accents", () => {
    expect(matchesSearch(ROWS[3], "ecole")).toBe(true);
    expect(matchesSearch(ROWS[0], "ALPHA")).toBe(true);
    expect(matchesSearch(ROWS[0], "beta")).toBe(false);
  });

  it("matches an IPEDS ID, only for digit queries", () => {
    expect(matchesSearch(ROWS[1], "2222")).toBe(true);
    expect(matchesSearch(ROWS[1], "999")).toBe(false);
  });

  it("combines with the status view and survives back/forward because it lives in the URL", () => {
    const v = view("all=1&q=state");
    expect(ids(filterCoverageRows(ROWS, v))).toEqual(["eps"]);
    expect(ids(filterCoverageRows(ROWS, view("status=cds_available_stale&q=state")))).toEqual(["eps"]);
    expect(ids(filterCoverageRows(ROWS, view("status=cds_available_stale&q=zzz")))).toEqual([]);
    expect(ids(filterCoverageRows(ROWS, view("all=1")))).toHaveLength(ROWS.length);
  });
});

describe("weighted share of undergraduates", () => {
  it("is enrollment with numbers over enrollment of rows with a known enrollment", () => {
    const s = weightedShare(ROWS);
    // numerator: alpha 5000 + beta 3000 + eps 10000. denominator adds gamma 2000. delta (null) is out of both.
    expect(s.numerator).toBe(18000);
    expect(s.denominator).toBe(20000);
    expect(s.share).toBe(0.9);
    expect(s.withoutEnrollment).toBe(1);
  });

  it("leaves null enrollments out of both sums, not in the denominator as zero", () => {
    const s = weightedShare([
      row({ school_id: "a", undergraduate_enrollment: 100 }),
      row({ school_id: "b", undergraduate_enrollment: null, latest_available_cds_year: null }),
    ]);
    expect(s.share).toBe(1);
    expect(s.withoutEnrollment).toBe(1);
  });

  it("does not count an unknown year as having numbers", () => {
    const s = weightedShare([
      row({ school_id: "a", undergraduate_enrollment: 100, latest_available_cds_year: "unknown" }),
      row({ school_id: "b", undergraduate_enrollment: 100 }),
    ]);
    expect(s.share).toBe(0.5);
  });

  it("has no share (not zero) when no row has an enrollment figure", () => {
    expect(weightedShare([row({ school_id: "a", undergraduate_enrollment: null })]).share).toBeNull();
    expect(weightedShare([]).share).toBeNull();
  });
});

describe("latest year with numbers", () => {
  it("uses a fixed window anchored on the current year, and a missing year shows as 0", () => {
    // ROWS has 2025-26, 2023-24 and 2021-22: nobody sits at 2024-25.
    const buckets = latestYearBuckets(ROWS, "2025-26");
    expect(buckets.map((b) => [b.label, b.count])).toEqual([
      ["2025-26", 1],
      ["2024-25", 0],
      ["2023-24", 1],
      ["Older", 1],
      ["None", 2],
    ]);
    expect(buckets.reduce((n, b) => n + b.count, 0)).toBe(ROWS.length);
  });

  it("moves with the anchor, not with the data", () => {
    expect(latestYearBuckets(ROWS, "2026-27").map((b) => b.label).slice(0, 3)).toEqual(["2026-27", "2025-26", "2024-25"]);
  });

  it("puts `unknown` in none, never above a real year, and a newer year in current", () => {
    const buckets = latestYearBuckets(
      [row({ school_id: "u", latest_available_cds_year: "unknown" }), row({ school_id: "n", latest_available_cds_year: "2026-27" })],
      "2025-26",
    );
    expect(buckets.find((b) => b.id === "none")?.count).toBe(1);
    expect(buckets[0].count).toBe(1);
  });

  it("anchors on the snapshot's current year, else the September-switch floor", () => {
    expect(currentCdsYear("2025-26", new Date("2026-01-01T00:00:00Z"))).toBe("2025-26");
    expect(currentCdsYear(undefined, new Date("2026-08-31T00:00:00Z"))).toBe("2024-25");
    expect(currentCdsYear(null, new Date("2026-09-01T00:00:00Z"))).toBe("2025-26");
    expect(currentCdsYear("unknown", new Date("2026-11-24T00:00:00Z"))).toBe("2025-26");
  });
});

describe("status wording", () => {
  it("uses plain words for the failed and processing states", () => {
    expect(COVERAGE_STATUS_LABELS.extract_failed).toBe("Report couldn’t be read");
    expect(COVERAGE_STATUS_LABELS.latest_found_extract_failed_with_prior_available).toBe(
      "Latest report couldn’t be read",
    );
    for (const status of Object.keys(COVERAGE_STATUS_LABELS) as CoverageStatus[]) {
      expect(COVERAGE_STATUS_LABELS[status]).not.toMatch(/extract/i);
    }
  });
});

describe("coverage CSV", () => {
  const csv = buildCoverageCsv(ROWS);
  const lines = csv.split("\r\n").filter(Boolean);

  it("starts with the real header: no comment block", () => {
    expect(csv.startsWith("#")).toBe(false);
    expect(lines.some((l) => l.startsWith("#"))).toBe(false);
    expect(lines[0]).toBe(COVERAGE_CSV_COLUMNS.join(","));
    expect(lines[0]).toBe(
      "ipeds_id,school_id,school_name,state,undergraduate_enrollment,status,latest_year_with_numbers,latest_year_found,last_checked",
    );
  });

  it("has one line per row", () => {
    expect(lines).toHaveLength(1 + ROWS.length);
    expect(lines[2]).toBe("222222,beta,Beta University,NY,3000,Older CDS,2023-24,2024-25,2026-11-20T00:00:00Z");
  });

  it("leaves unknown values blank, not zero", () => {
    expect(lines[4]).toBe("444444,delta,\u00c9cole Delta,CA,,Not checked,,,2026-11-20T00:00:00Z");
  });

  it("quotes a school name with a comma and a quote so it round-trips", () => {
    const name = 'St. John\'s, "Great Books" College';
    const out = buildCoverageCsv([row({ school_id: "sj", school_name: name })]);
    expect(out.split("\r\n")[1]).toContain('"St. John\'s, ""Great Books"" College"');
  });

  it("covers just the rows it is given, so the view and all-rows downloads differ", () => {
    const view = buildCoverageCsv(filterCoverageRows(ROWS, view0()));
    expect(view.split("\r\n").filter(Boolean)).toHaveLength(1 + 4);
    expect(lines).toHaveLength(1 + 5);
  });

});

describe("coverage sort", () => {
  // Two schools tie on every column except name, plus a null in each nullable column.
  const T = [
    row({ school_id: "zed", school_name: "Zed College", state: "NY", undergraduate_enrollment: 2000, coverage_status: "cds_available_stale", latest_available_cds_year: "2023-24", latest_found_cds_year: "2024-25", last_checked_at: "2026-11-10T00:00:00Z" }),
    row({ school_id: "abe", school_name: "Abe College", state: "NY", undergraduate_enrollment: 2000, coverage_status: "cds_available_stale", latest_available_cds_year: "2023-24", latest_found_cds_year: "2024-25", last_checked_at: "2026-11-10T00:00:00Z" }),
    row({ school_id: "new", school_name: "Newest U", state: "CA", undergraduate_enrollment: 9000, coverage_status: "cds_available_current", latest_available_cds_year: "2025-26", latest_found_cds_year: "2025-26", last_checked_at: "2026-11-20T00:00:00Z" }),
    row({ school_id: "nul", school_name: "Null U", state: null, undergraduate_enrollment: null, coverage_status: "not_checked", latest_available_cds_year: null, latest_found_cds_year: null, last_checked_at: null }),
  ];
  const order = (key: SortKey, dir: SortDir) => ids(sortCoverageRows(T, key, dir));

  it("name: A to Z and back", () => {
    expect(order("name", "asc")).toEqual(["abe", "new", "nul", "zed"]);
    expect(order("name", "desc")).toEqual(["zed", "nul", "new", "abe"]);
  });

  it("state: blank state first when ascending, ties by name", () => {
    expect(order("state", "asc")).toEqual(["nul", "new", "abe", "zed"]);
    expect(order("state", "desc")).toEqual(["abe", "zed", "new", "nul"]);
  });

  it("enrollment: equal enrollments tie by name, unknown always last", () => {
    expect(order("enrollment", "desc")).toEqual(["new", "abe", "zed", "nul"]);
    expect(order("enrollment", "asc")).toEqual(["abe", "zed", "new", "nul"]);
  });

  it("status: the display order of the tiles, ties by name", () => {
    expect(order("status", "asc")).toEqual(["new", "abe", "zed", "nul"]);
    expect(order("status", "desc")).toEqual(["nul", "abe", "zed", "new"]);
  });

  it("numbers and found: oldest first when ascending, no year first, ties by name", () => {
    expect(order("numbers", "asc")).toEqual(["nul", "abe", "zed", "new"]);
    expect(order("numbers", "desc")).toEqual(["new", "abe", "zed", "nul"]);
    expect(order("found", "asc")).toEqual(["nul", "abe", "zed", "new"]);
    expect(order("found", "desc")).toEqual(["new", "abe", "zed", "nul"]);
  });

  it("checked: never checked counts as oldest, ties by name", () => {
    expect(order("checked", "desc")).toEqual(["new", "abe", "zed", "nul"]);
    expect(order("checked", "asc")).toEqual(["nul", "abe", "zed", "new"]);
  });

  it("does not change the rows it is given", () => {
    const before = ids(T);
    sortCoverageRows(T, "enrollment", "desc");
    expect(ids(T)).toEqual(before);
  });

  it("starts each column in the direction the table does", () => {
    expect(defaultSortDir("enrollment")).toBe("desc");
    expect(defaultSortDir("checked")).toBe("desc");
    expect(defaultSortDir("name")).toBe("asc");
  });

  it("is the table's rows: filtered by the query, then sorted", () => {
    const rows = coverageViewRows(ROWS, "all=1&state=NY&sort=ignored", "enrollment", "desc");
    expect(ids(rows)).toEqual(["eps", "alpha", "beta", "gamma"]);
    expect(rows).toEqual(sortCoverageRows(filterCoverageRows(ROWS, parseCoverageView(new URLSearchParams("all=1&state=NY"))), "enrollment", "desc"));
  });
});

describe("coverage CSV notes", () => {
  it("keeps federal columns out of the licensed list and every column in one list or the other", () => {
    const fed: readonly string[] = COVERAGE_CSV_FEDERAL_COLUMNS;
    const ours: readonly string[] = COVERAGE_CSV_LICENSED_COLUMNS;
    expect(fed.filter((c) => ours.includes(c))).toEqual([]);
    expect([...fed, ...ours].sort()).toEqual([...COVERAGE_CSV_COLUMNS].sort());
  });

  it("says our license does not cover the federal columns and names the Scorecard", () => {
    expect(COVERAGE_CSV_FEDERAL_NOTE).toContain("College Scorecard");
    expect(COVERAGE_CSV_FEDERAL_NOTE).toMatch(/our license doesn\u2019t cover/);
    expect(COVERAGE_CSV_FEDERAL_NOTE).not.toMatch(/licensed|CC BY/);
    for (const w of ["IPEDS ID", "school name", "state", "undergraduate enrollment"]) expect(COVERAGE_CSV_FEDERAL_NOTE).toContain(w);
  });

  it("defines the two year columns", () => {
    expect(COVERAGE_CSV_DEFINITION_NOTE).toContain("latest_year_with_numbers is the latest year whose numbers we read");
    expect(COVERAGE_CSV_DEFINITION_NOTE).toContain("latest_year_found is the latest year of any file we hold");
  });

  it("names the view and all-colleges files differently", () => {
    expect(coverageCsvFilename("view", "2026-11-25")).toBe("quadfile-coverage-view-2026-11-25.csv");
    expect(coverageCsvFilename("all", "2026-11-25")).toBe("quadfile-coverage-all-colleges-2026-11-25.csv");
  });
});

function view0() {
  return parseCoverageView(new URLSearchParams(""));
}
