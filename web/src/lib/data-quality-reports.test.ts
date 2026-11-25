import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { FIXTURE_SNAPSHOT_V3 } from "./__fixtures__/data-quality-snapshot";
import {
  ReportsError,
  cellCount,
  cellLabel,
  cellPhrase,
  cellRows,
  cellTitle,
  cellWeight,
  reportsAgreementProblems,
  rowDetail,
  schoolHref,
  snapshotCells,
  validateReports,
  type CellRef,
  type ReportRow,
  type ReportsFile,
} from "./data-quality-reports";
import { SNAPSHOT_DIR, loadLatestSnapshot, loadReportsFor } from "./data-quality-snapshots";
import { snapshotDay, validateSnapshot, type QualitySnapshot } from "./data-quality";
import { PUBLIC_HIDDEN_QUALITY_FLAGS, isPubliclyListedDocument } from "./public-documents";

// The latest committed snapshot and its reports file: a new snapshot brings its own, so nothing below names a date.
const DAY = () => snapshotDay(loadLatestSnapshot());
const realReports = (): ReportsFile => JSON.parse(fs.readFileSync(path.join(SNAPSHOT_DIR, "reports", `${DAY()}.json`), "utf8"));
const clone = <T,>(x: T): T => JSON.parse(JSON.stringify(x));

describe("the reports behind every count (the latest committed snapshot)", () => {
  it("lists, for every count cell of every table and year, exactly as many reports as the count says", () => {
    const snapshot = loadLatestSnapshot();
    const reports = validateReports(realReports(), `${DAY()}.json`);
    const cells = snapshotCells(snapshot);
    // Not an empty comparison: 3 years x (formats + total) x every column of Tables A, B, B2 and C.
    expect(cells.length).toBeGreaterThan(600);
    expect(new Set(cells.map((c) => c.cell.table))).toEqual(new Set(["status", "totals", "federal", "enrollment", "tuition"]));
    const wrong = cells.filter(({ year, cell, count }) => cellCount(reports, year, cell) !== count);
    expect(wrong).toEqual([]);
    expect(reportsAgreementProblems(snapshot, reports)).toEqual([]);
    expect(cells.some((c) => c.count > 0 && c.cell.column === "differs_over_10pct")).toBe(true);
  });

  it("is what the build loads for the latest snapshot, and lists every published report once", () => {
    const snapshot = loadLatestSnapshot();
    const reports = loadReportsFor(snapshot)!;
    expect(reports).not.toBeNull();
    for (const y of snapshot.years) {
      const published = reports.years[y.cds_year].filter((r) => r.status === "published");
      expect(published).toHaveLength(y.total.status.published);
      expect(new Set(reports.years[y.cds_year].map((r) => r.id)).size).toBe(reports.years[y.cds_year].length);
    }
  });

  it("links every listed school to a school page of that year, and names it from the school list", () => {
    const reports = realReports();
    const rows = Object.entries(reports.years).flatMap(([year, list]) => list.map((r) => ({ year, r })));
    const withSchool = rows.filter(({ r }) => r.school);
    expect(withSchool.length).toBeGreaterThan(1300);
    for (const { year, r } of withSchool) {
      expect(reports.schools[r.school!], r.id).toBeTruthy();
      expect(schoolHref(r.school!, year)).toBe(`/schools/${r.school}/${year}`);
    }
    // The route exists in the app (the real /schools/[school_id]/[year] page).
    expect(fs.existsSync(path.join(process.cwd(), "src", "app", "schools", "[school_id]", "[year]", "page.tsx"))).toBe(true);
    // Documents this run has no school for are listed without a link; there are few and they are not published.
    const unlinked = rows.filter(({ r }) => !r.school);
    expect(unlinked.length).toBeLessThan(80);
    expect(unlinked.every(({ r }) => r.status !== "published")).toBe(true);
  });

  it("lists, unlinked, exactly the school-years whose page would 404 (a blank template with no other document), and links the rest", () => {
    const reports = realReports();
    const unlinked = Object.fromEntries(
      Object.entries(reports.years).map(([year, rows]) => [year, rows.filter((r) => r.nopage).map((r) => r.school).sort()]),
    );
    // The 2026-11-25 run (scoreboard-20261125T233202Z.json): the fifteen blank-form reports whose /schools/<id>/<year> page does not exist (public-documents.ts hides
    // a blank template, and the page 404s with no other listed document that year). Pinned by name; a new snapshot updates this.
    if (DAY() === "2026-11-25") {
      expect(unlinked).toEqual({
        "2023-24": ["alfred-university", "auburn-university", "austin-peay-state-university", "florida-state-university", "old-dominion-university", "university-of-connecticut", "university-of-houston"],
        "2024-25": ["auburn-university", "florida-state-university", "university-of-nebraska-lincoln", "virginia-military-institute"],
        "2025-26": ["depaul-university", "the-university-of-texas-permian-basin", "towson-university", "union-college"],
      });
    }
    for (const rows of Object.values(reports.years)) {
      for (const r of rows) {
        if (r.nopage) expect(r.status).not.toBe("published");
        if (r.status === "published") expect(r.school, r.id).toBeTruthy();   // a published report always has its year page
      }
    }
  });

  it("hides the same quality flags as the Python producer (so a row is unlinked exactly when the page query would find nothing)", () => {
    const py = fs.readFileSync(path.join(process.cwd(), "..", "tools", "extraction-validator", "scoreboard.py"), "utf8");
    const listed = /PUBLIC_HIDDEN_QUALITY_FLAGS = \(([^)]*)\)/.exec(py)![1];
    expect([...listed.matchAll(/"([^"]+)"/g)].map((m) => m[1])).toEqual([...PUBLIC_HIDDEN_QUALITY_FLAGS]);
    for (const flag of [...PUBLIC_HIDDEN_QUALITY_FLAGS, "low_coverage", "wrong_file", null]) {
      expect(isPubliclyListedDocument({ data_quality_flag: flag })).toBe(!(PUBLIC_HIDDEN_QUALITY_FLAGS as readonly string[]).includes(flag ?? ""));
    }
  });

  it("pins the 2026-11-25 snapshot's cells and rows (665 cells, 1,444 rows, 1,339 published, 105 not)", () => {
    // Only while that is the latest snapshot: the next snapshot's PR deletes this reports file (see the README), and its
    // own pins replace these.
    if (DAY() !== "2026-11-25") return;
    const snap = JSON.parse(fs.readFileSync(path.join(SNAPSHOT_DIR, "2026-11-25.json"), "utf8"));
    const reports = JSON.parse(fs.readFileSync(path.join(SNAPSHOT_DIR, "reports", "2026-11-25.json"), "utf8")) as ReportsFile;
    expect(snapshotCells(validateSnapshot(snap, "2026-11-25.json")).length).toBe(665);
    const all = Object.values(reports.years).flat();
    expect(all).toHaveLength(1444);
    expect(all.filter((r) => r.status === "published")).toHaveLength(1339);
    expect(all.filter((r) => r.status !== "published")).toHaveLength(105);
    // Since #510 the run keeps school_id on a couldn't-read report too, so every row names its school.
    expect(all.filter((r) => !r.school)).toHaveLength(0);
  });

  it("is in the producer's order, so a file written before a change to the order fails: school name ignoring case, then id", () => {
    const reports = realReports();
    for (const [year, rows] of Object.entries(reports.years)) {
      // The producer sorts by (casefolded school name, document id), with rows that have no school last.
      const key = (r: ReportsFile["years"][string][number]) => [r.school ? reports.schools[r.school].toLowerCase() : "~", r.id];
      const sorted = [...rows].sort((a, b) => {
        const [x, y] = [key(a), key(b)];
        return x[0] < y[0] ? -1 : x[0] > y[0] ? 1 : x[1] < y[1] ? -1 : x[1] > y[1] ? 1 : 0;
      });
      expect(rows.map((r) => r.id), year).toEqual(sorted.map((r) => r.id));
    }
    // A name that differs only by case is where a plain sort and a casefolded one disagree; the file must follow the latter.
    const names = Object.values(reports.schools);
    expect(names.some((n) => n !== n.toLowerCase())).toBe(true);
  });

  it("keeps a reports file only for the latest snapshot (older ones are never served, so they are pruned)", () => {
    const files = fs.readdirSync(path.join(SNAPSHOT_DIR, "reports")).filter((n) => n.endsWith(".json"));
    expect(files).toEqual([`${DAY()}.json`]);
  });

  it("ships the reports file only with the routes that read it, not with /coverage", async () => {
    const { nextConfig } = await import("../../next.config");
    const include = nextConfig.outputFileTracingIncludes as Record<string, string[]>;
    expect(include["/coverage"]).toEqual(["./src/data/data-quality/*.json"]);   // top-level snapshots only
    expect(include["/data-quality"]).toEqual(["./src/data/data-quality/**/*.json"]);
    expect(include["/data-quality/reports/[date]"]).toEqual(["./src/data/data-quality/**/*.json"]);
    // Next traces the whole directory for /coverage anyway, so the reports are excluded there explicitly.
    expect((nextConfig.outputFileTracingExcludes as Record<string, string[]>)["/coverage"]).toEqual(["./src/data/data-quality/reports/**"]);
  });

  it("holds no values and no field counts: only ids, school, format, status and outcomes", () => {
    const reports = realReports();
    const keys = new Set(Object.values(reports.years).flatMap((rows) => rows.flatMap((r) => Object.keys(r))));
    expect([...keys].sort()).toEqual(["checks", "fed", "format", "id", "nopage", "school", "status", "sums"]);
  });
});

// A hand-made file: three reports in one year.
const row = (id: string, over: Partial<ReportRow> = {}): ReportRow => ({
  id, school: "alpha", format: "pdf_flat", status: "published", fed: ["m", "l", null], sums: ["adds_up", "off_more", "doesnt"], checks: ["s", null], ...over,
});
const HAND: ReportsFile = {
  reports_format: 1, snapshot_of: "2026-11-25T00:00:00Z", scoreboard_run: "x.json", codes: {},
  schools: { alpha: "Alpha College", beta: "Beta University" },
  years: {
    "2024-25": [
      row("a"),
      row("b", { school: "beta", format: "xlsx", fed: ["s", "s", "n"], sums: ["cant_check", "adds_up", "adds_up"], checks: [null, "m"] }),
      row("c", { school: null, status: "couldnt_read", fed: undefined, sums: undefined, checks: undefined }),
      row("d", { status: "set_aside", fed: undefined, sums: undefined, checks: undefined }),
    ],
  },
};
const c = (table: CellRef["table"], column: string, rowKey = "total"): CellRef => ({ table, row: rowKey, column });

describe("which reports a cell lists", () => {
  it("lists by status in Table A, by format row and for all formats", () => {
    expect(cellRows(HAND, "2024-25", c("status", "published")).map((x) => x.row.id)).toEqual(["a", "b"]);
    expect(cellRows(HAND, "2024-25", c("status", "published", "pdf_flat")).map((x) => x.row.id)).toEqual(["a"]);
    expect(cellRows(HAND, "2024-25", c("status", "couldnt_read")).map((x) => x.row.id)).toEqual(["c"]);
    expect(cellRows(HAND, "2024-25", c("status", "not_read_yet"))).toEqual([]);
  });

  it("counts federal values, so a report can weigh 1 to 3", () => {
    const w = (col: string, rowKey = "total") => cellRows(HAND, "2024-25", c("federal", col, rowKey)).map((x) => [x.row.id, x.weight]);
    expect(w("reports")).toEqual([["a", 1], ["b", 1]]);
    expect(w("values")).toEqual([["a", 2], ["b", 3]]);
    expect(w("matches")).toEqual([["a", 1]]);
    expect(w("no_value")).toEqual([["b", 1]]);
    expect(w("differs")).toEqual([["a", 1], ["b", 2]]);
    expect(w("differs_2_to_10pct")).toEqual([["b", 2]]);
    expect(w("differs_over_10pct")).toEqual([["a", 1]]);
    expect(cellCount(HAND, "2024-25", c("federal", "values"))).toBe(5);
    expect(w("values", "xlsx")).toEqual([["b", 3]]);
  });

  it("lists the sum outcomes, one report per outcome per table", () => {
    expect(cellRows(HAND, "2024-25", c("totals", "B1.adds_up")).map((x) => x.row.id)).toEqual(["a"]);
    expect(cellRows(HAND, "2024-25", c("totals", "C1.off_more")).map((x) => x.row.id)).toEqual(["a"]);
    expect(cellRows(HAND, "2024-25", c("totals", "H1.adds_up")).map((x) => x.row.id)).toEqual(["b"]);
    expect(cellRows(HAND, "2024-25", c("totals", "reports")).map((x) => x.row.id)).toEqual(["a", "b"]);
  });

  it("lists the enrollment and tuition checks, one value per report", () => {
    expect(cellRows(HAND, "2024-25", c("enrollment", "differs_2_to_10pct")).map((x) => x.row.id)).toEqual(["a"]);
    expect(cellRows(HAND, "2024-25", c("tuition", "matches")).map((x) => x.row.id)).toEqual(["b"]);
    expect(cellRows(HAND, "2024-25", c("enrollment", "reports")).map((x) => x.row.id)).toEqual(["a"]);
    expect(cellWeight(HAND.years["2024-25"][3], c("enrollment", "reports"))).toBe(0);
  });

  it("lists nothing for a year, row or column the file lacks", () => {
    expect(cellRows(HAND, "1999-00", c("status", "published"))).toEqual([]);
    expect(cellRows(HAND, "2024-25", c("status", "published", "html"))).toEqual([]);
  });
});

describe("the agreement check", () => {
  const snapshot = (): QualitySnapshot => {
    const s = clone(FIXTURE_SNAPSHOT_V3);
    s.snapshot_of = HAND.snapshot_of;
    s.scoreboard_run = HAND.scoreboard_run;
    return s;
  };

  it("reports a cell whose count differs from the rows listed, and a different run", () => {
    const problems = reportsAgreementProblems(snapshot(), HAND);
    expect(problems.length).toBeGreaterThan(10);   // the fixture's invented counts are not these three reports
    expect(problems.some((p) => /snapshot counts \d+, the file lists \d+/.test(p))).toBe(true);
    expect(reportsAgreementProblems({ ...snapshot(), scoreboard_run: "other.json" }, HAND)[0]).toMatch(/not from the same run/);
    expect(problems.some((p) => /has a year the snapshot lacks/.test(p))).toBe(false);
  });

  it("agrees for the committed snapshot and fails when one row is dropped, added or changed", () => {
    const snap = loadLatestSnapshot();
    const base = realReports();
    expect(reportsAgreementProblems(snap, base)).toEqual([]);
    const drop = clone(base);
    drop.years["2024-25"].pop();
    expect(reportsAgreementProblems(snap, drop).length).toBeGreaterThan(0);
    const status = clone(base);
    const first = status.years["2024-25"].find((r) => r.status === "published")!;
    first.status = "set_aside";
    delete first.fed; delete first.sums; delete first.checks;
    expect(reportsAgreementProblems(snap, status).length).toBeGreaterThan(0);
    const code = clone(base);
    const withFed = code.years["2023-24"].find((r) => r.fed && r.fed[0] === "m")!;
    withFed.fed![0] = "n";
    expect(reportsAgreementProblems(snap, code).length).toBeGreaterThan(0);
    const extra = clone(base);
    extra.years["2025-26"].push({ ...extra.years["2025-26"][0], id: "extra" });
    expect(reportsAgreementProblems(snap, extra).length).toBeGreaterThan(0);
  });

  it("makes the build fail (ReportsError) for a file that disagrees, and loads none for a snapshot without one", () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "dq-reports-"));
    try {
      const snap = loadLatestSnapshot();
      expect(loadReportsFor(snap, dir)).toBeNull();
      fs.mkdirSync(path.join(dir, "reports"));
      const broken = realReports();
      broken.years["2024-25"].pop();
      fs.writeFileSync(path.join(dir, "reports", `${DAY()}.json`), JSON.stringify(broken));
      expect(() => loadReportsFor(snap, dir)).toThrow(ReportsError);
      fs.writeFileSync(path.join(dir, "reports", `${DAY()}.json`), "{");
      expect(() => loadReportsFor(snap, dir)).toThrow(/not valid JSON/);
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });
});

describe("validation of a reports file", () => {
  const bad = (mutate: (r: ReportsFile) => void, why: RegExp) => {
    const r = clone(HAND);
    mutate(r);
    expect(() => validateReports(r, "x")).toThrow(why);
  };
  it("accepts the hand file and refuses what the producer never writes", () => {
    expect(validateReports(clone(HAND), "x").years["2024-25"]).toHaveLength(4);
    bad((r) => (r.reports_format = 9), /unknown reports_format/);
    bad((r) => (r.years["2024-25"][1].id = "a"), /listed twice/);
    bad((r) => (r.years["2024-25"][0].status = "removed" as never), /has status/);
    bad((r) => (r.years["2024-25"][0].school = "nobody"), /not in the list/);
    bad((r) => delete r.years["2024-25"][0].fed, /must have fed exactly when it is published/);
    bad((r) => (r.years["2024-25"][2].fed = [null, null, null]), /must have fed exactly when it is published/);
    bad((r) => (r.years["2024-25"][0].fed = ["x" as never, null, null]), /bad fed/);
    bad((r) => (r.years["2024-25"][0].checks = [null]), /bad checks/);
    bad((r) => (r.schools.alpha = ""), /has no name/);
  });
});

describe("words", () => {
  it("gives a count button a name that says how many, which reports, what and when", () => {
    expect(cellLabel(c("totals", "H1.adds_up", "pdf_flat"), "2023-24", 46)).toBe("List the 46 standard PDF reports where the financial aid table adds up (2023-24)");
    expect(cellLabel(c("status", "published"), "2024-25", 1346)).toBe("List the 1,346 reports in all formats published (2024-25)");
    expect(cellLabel(c("status", "couldnt_read", "pdf_scanned"), "2023-24", 3)).toBe("List the 3 scanned PDF reports that couldn’t be read (2023-24)");
    expect(cellLabel(c("federal", "matches"), "2024-25", 898)).toBe("List the 898 admissions values that match the federal figure, from reports in all formats (2024-25)");
    expect(cellLabel(c("tuition", "differs_over_10pct", "pdf_flat"), "2023-24", 22)).toBe("List the 22 tuition values that differ by over 10%, from standard PDF reports (2023-24)");
    expect(cellLabel(c("enrollment", "reports", "xlsx"), "2023-24", 51)).toBe("List the 51 spreadsheet reports checked against federal undergraduate enrollment figures (2023-24)");
  });

  it("agrees in number: B1 and C1 are totals (plural), H1 is a table (singular), for every outcome", () => {
    const t = (column: string) => cellPhrase(c("totals", column));
    expect([t("B1.adds_up"), t("B1.under_2pct"), t("B1.off_more"), t("B1.cant_check")]).toEqual([
      "where the enrollment totals add up",
      "where the enrollment totals are off by under 2%",
      "where the enrollment totals are off by more",
      "where the enrollment totals can’t be checked",
    ]);
    expect([t("C1.adds_up"), t("C1.under_2pct"), t("C1.off_more"), t("C1.cant_check")]).toEqual([
      "where the admissions totals add up",
      "where the admissions totals are off by under 2%",
      "where the admissions totals are off by more",
      "where the admissions totals can’t be checked",
    ]);
    expect([t("H1.adds_up"), t("H1.doesnt"), t("H1.cant_check")]).toEqual([
      "where the financial aid table adds up",
      "where the financial aid table doesn’t add up",
      "where the financial aid table can’t be checked",
    ]);
    expect(cellLabel(c("totals", "B1.under_2pct", "xlsx"), "2024-25", 12)).toBe("List the 12 spreadsheet reports where the enrollment totals are off by under 2% (2024-25)");
    expect(cellLabel(c("totals", "C1.cant_check"), "2024-25", 3)).toBe("List the 3 reports in all formats where the admissions totals can’t be checked (2024-25)");
  });

  it("says 'report' and 'value' for a count of 1, and the plural otherwise, in every kind of cell", () => {
    const one = (cell: CellRef) => cellTitle(cell, "2024-25", 1);
    const two = (cell: CellRef) => cellTitle(cell, "2024-25", 2);
    // Table A
    expect(one(c("status", "published"))).toBe("1 report in all formats published (2024-25)");
    expect(one(c("status", "couldnt_read", "pdf_flat"))).toBe("1 standard PDF report that couldn’t be read (2024-25)");
    expect(two(c("status", "set_aside", "pdf_flat"))).toBe("2 standard PDF reports set aside (2024-25)");
    // Table C
    expect(one(c("totals", "reports"))).toBe("1 report in all formats published (2024-25)");
    expect(one(c("totals", "B1.adds_up", "xlsx"))).toBe("1 spreadsheet report where the enrollment totals add up (2024-25)");
    expect(one(c("totals", "H1.doesnt"))).toBe("1 report in all formats where the financial aid table doesn’t add up (2024-25)");
    // Table B: values, with the verb agreeing
    expect(one(c("federal", "matches"))).toBe("1 admissions value that matches the federal figure, from reports in all formats (2024-25)");
    expect(one(c("federal", "matches", "pdf_flat"))).toBe("1 admissions value that matches the federal figure, from standard PDF reports (2024-25)");
    expect(one(c("federal", "differs_over_10pct", "pdf_flat"))).toBe("1 admissions value that differs by over 10%, from standard PDF reports (2024-25)");
    expect(one(c("federal", "differs_2_to_10pct"))).toBe("1 admissions value that differs by over 2% to 10%, from reports in all formats (2024-25)");
    expect(one(c("federal", "no_value"))).toBe("1 admissions value with no usable number of ours, from reports in all formats (2024-25)");
    expect(one(c("federal", "values"))).toBe("1 admissions value compared with the federal figure, from reports in all formats (2024-25)");
    expect(one(c("federal", "reports", "pdf_flat"))).toBe("1 standard PDF report checked against federal admissions figures (2024-25)");
    expect(two(c("federal", "matches", "pdf_flat"))).toBe("2 admissions values that match the federal figure, from standard PDF reports (2024-25)");
    // Tables B2
    expect(one(c("tuition", "differs", "pdf_flat"))).toBe("1 tuition value that differs from the federal figure, from standard PDF reports (2024-25)");
    expect(one(c("enrollment", "matches"))).toBe("1 undergraduate enrollment value that matches the federal figure, from reports in all formats (2024-25)");
    expect(one(c("enrollment", "reports", "xlsx"))).toBe("1 spreadsheet report checked against federal undergraduate enrollment figures (2024-25)");
    expect(two(c("tuition", "differs_over_10pct"))).toBe("2 tuition values that differ by over 10%, from reports in all formats (2024-25)");
    // Large counts keep their thousands separators and stay plural.
    expect(cellTitle(c("status", "published"), "2024-25", 1346)).toBe("1,346 reports in all formats published (2024-25)");
    expect(cellLabel(c("status", "published"), "2024-25", 1)).toBe("List the 1 report in all formats published (2024-25)");
  });

  it("describes what a listed report held, only for the table clicked", () => {
    expect(rowDetail(HAND.years["2024-25"][0], c("federal", "values"))).toBe("applied: matches; admitted: differs by over 10%");
    expect(rowDetail(HAND.years["2024-25"][0], c("enrollment", "reports"))).toBe("differs by over 2% to 10%");
    expect(rowDetail(HAND.years["2024-25"][0], c("totals", "B1.adds_up"))).toBeNull();
    expect(rowDetail(HAND.years["2024-25"][2], c("status", "couldnt_read"))).toBeNull();
  });
});
