import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { describe, expect, it } from "vitest";
import { FIXTURE_SNAPSHOT, FIXTURE_SNAPSHOT_V1, FIXTURE_SNAPSHOT_V2, FIXTURE_SNAPSHOT_V3, FIXTURE_SNAPSHOT_V4 } from "./__fixtures__/data-quality-snapshot";
import { SnapshotError, percent, selectAllSnapshots, selectSnapshot, snapshotDay, type QualitySnapshot } from "./data-quality";
import { buildTrend, cohortChanges, lineRuns, renewalRow, seriesStart, seriesStarts, trendRows, type TrendPoint, type TrendRow } from "./data-quality-trend";
import { SNAPSHOT_DIR, loadAllSnapshots, loadLatestSnapshot } from "./data-quality-snapshots";

const clone = (s: QualitySnapshot): QualitySnapshot => JSON.parse(JSON.stringify(s));
/** A fixture snapshot on another date and run (never a committed file). */
function at(base: QualitySnapshot, day: string, change: (s: QualitySnapshot) => void = () => {}): QualitySnapshot {
  const s = clone(base);
  s.snapshot_of = `${day}T12:00:00Z`;
  s.scoreboard_run = `scoreboard-${day.replaceAll("-", "")}T120000Z.json`;
  change(s);
  return s;
}
const files = (...snaps: QualitySnapshot[]) => snaps.map((json, i) => ({ name: `f${i}.json`, json }));

// Mixed formats, deliberately out of order: format 2 (Nov 17), format 5 (Nov 24), format 1 (Nov 10), format 3 (Nov 20), format 4 (Nov 22).
// These four are valid snapshots (they go through the loader); the metric tests below use `shifted`, which changes numbers.
const OLDEST = at(FIXTURE_SNAPSHOT_V1, "2026-11-10");
const SECOND = at(FIXTURE_SNAPSHOT_V2, "2026-11-17");
const THIRD = at(FIXTURE_SNAPSHOT_V3, "2026-11-20");
const FOURTH = at(FIXTURE_SNAPSHOT_V4, "2026-11-22");
const NEWEST = at(FIXTURE_SNAPSHOT, "2026-11-24");

/**
 * A snapshot whose every trended number for every year differs by `k`: published, couldn't read, the federal match rate, the
 * three adds-up rates and renewal. Not validated (the arithmetic no longer adds up): `buildTrend` only reads the numbers, so a
 * test that takes any metric from the wrong snapshot fails.
 */
function shifted(base: QualitySnapshot, day: string, k: number): QualitySnapshot {
  return at(base, day, (s) => {
    for (const y of s.years) {
      for (const r of [y.total, y.rows[0]]) {
        r.status.published += 7 * k;
        r.status.couldnt_read += 2 * k;
        r.federal.matches += 20 * k;
        r.totals.B1.adds_up += 6 * k;
        r.totals.C1.adds_up += 4 * k;
        r.totals.H1.adds_up += 5 * k;
      }
    }
    s.renewal.both += 5 * k;
  });
}
/** The committed snapshot days, from the directory (so the next snapshot changes no test). */
const committedDays = () => fs.readdirSync(SNAPSHOT_DIR).filter((n) => n.endsWith(".json")).map((n) => n.slice(0, -".json".length)).sort();

describe("loading every snapshot", () => {
  it("reads snapshots of every format together, each against its own format, oldest first", () => {
    const all = selectAllSnapshots(files(NEWEST, OLDEST, FOURTH, THIRD, SECOND));
    expect(all.map((s) => s.snapshot_of.slice(0, 10))).toEqual(["2026-11-10", "2026-11-17", "2026-11-20", "2026-11-22", "2026-11-24"]);
    expect(all.map((s) => s.public_format)).toEqual([1, 2, 3, 4, 5]);
  });

  it("still picks the newest for the tables, whatever the order", () => {
    expect(selectSnapshot(files(OLDEST, NEWEST, SECOND)).public_format).toBe(5);
    expect(selectSnapshot(files(NEWEST, OLDEST)).snapshot_of).toBe(NEWEST.snapshot_of);
  });

  it("fails on two snapshots with one date, an unknown format, a broken file or no file", () => {
    expect(() => selectAllSnapshots(files(OLDEST, at(FIXTURE_SNAPSHOT_V2, "2026-11-10")))).toThrow(/same date 2026-11-10/);
    expect(() => selectAllSnapshots(files(OLDEST, { ...SECOND, public_format: 9 } as QualitySnapshot))).toThrow(/public_format/);
    const broken = clone(NEWEST);
    delete (broken.years[0].total as Partial<typeof broken.years[0]["total"]>).federal;
    expect(() => selectAllSnapshots(files(OLDEST, broken))).toThrow(SnapshotError);
    expect(() => selectAllSnapshots([])).toThrow(/no snapshot/);
    // The older snapshot is not exempt because a newer one is fine: its own format is checked.
    const old = clone(OLDEST);
    (old.years[0].total.federal as unknown as Record<string, number>).differs_2_to_10pct = 0;
    expect(() => selectAllSnapshots(files(old, NEWEST))).toThrow(/unexpected key/);
  });

  it("reads the committed directory: every snapshot file, oldest first, and the newest is the latest", () => {
    const all = loadAllSnapshots();
    expect(all.map(snapshotDay)).toEqual(committedDays());
    expect(loadLatestSnapshot()).toEqual(all[all.length - 1]);
  });

  it("reads a directory of several files, ignores the reports subdirectory and a README, and fails on a duplicate date", () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "dq-trend-"));
    try {
      fs.mkdirSync(path.join(dir, "reports"));
      fs.writeFileSync(path.join(dir, "reports", "2026-11-24.json"), "not a snapshot");
      fs.writeFileSync(path.join(dir, "README.md"), "x");
      for (const s of [NEWEST, OLDEST, SECOND]) fs.writeFileSync(path.join(dir, `${s.snapshot_of.slice(0, 10)}.json`), JSON.stringify(s));
      expect(loadAllSnapshots(dir).map((s) => s.snapshot_of.slice(0, 10))).toEqual(["2026-11-10", "2026-11-17", "2026-11-24"]);
      fs.writeFileSync(path.join(dir, "dup.json"), JSON.stringify(at(FIXTURE_SNAPSHOT_V2, "2026-11-17")));
      expect(() => loadAllSnapshots(dir)).toThrow(/same date/);
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });

  it("finds no stray .json file next to the snapshots (a reports file or a draft would be read as one)", () => {
    expect(fs.readdirSync(SNAPSHOT_DIR).filter((n) => n.endsWith(".json")).every((n) => /^\d{4}-\d{2}-\d{2}\.json$/.test(n))).toBe(true);
    expect(loadAllSnapshots().map(snapshotDay)).toEqual(committedDays());
  });
});

describe("the trend", () => {
  const points = buildTrend(selectAllSnapshots(files(NEWEST, OLDEST, THIRD, SECOND)));

  it("has one point per snapshot, oldest first, labelled with its date and run", () => {
    expect(points.map((p) => [p.snapshot_of, p.run])).toEqual([
      ["2026-11-10T12:00:00Z", "scoreboard-20261110T120000Z.json"],
      ["2026-11-17T12:00:00Z", "scoreboard-20261117T120000Z.json"],
      ["2026-11-20T12:00:00Z", "scoreboard-20261120T120000Z.json"],
      ["2026-11-24T12:00:00Z", "scoreboard-20261124T120000Z.json"],
    ]);
  });

  it("holds the fixture's own numbers by hand (2024-25: 78 published, 0 couldn't read, 46%, 83%, 88%, 71%)", () => {
    for (const p of points) {
      expect(p.years["2024-25"]).toEqual({ published: 78, couldnt_read: 0, match_rate: 46, b1: 83, c1: 88, h1: 71 });
    }
    expect(points.map((p) => p.renewal.percent)).toEqual([76, 76, 76, 76]);   // 364 / 479
  });

  it("takes every metric from its own snapshot: with every number different in every snapshot, each value is that snapshot's", () => {
    const snaps = [shifted(FIXTURE_SNAPSHOT, "2026-11-01", 0), shifted(FIXTURE_SNAPSHOT, "2026-11-08", 1), shifted(FIXTURE_SNAPSHOT, "2026-11-15", 2), shifted(FIXTURE_SNAPSHOT, "2026-11-22", 3)];
    const trend = buildTrend(snaps);
    for (const year of ["2023-24", "2024-25", "2025-26"]) {
      const rows = trendRows(trend, year);
      snaps.forEach((snap, i) => {
        const y = snap.years.find((x) => x.cds_year === year)!;
        const t = y.total;
        const own = {
          published: t.status.published,
          couldnt_read: t.status.couldnt_read,
          match_rate: y.federal_fall_loaded ? percent(t.federal.matches, t.federal.values) : null,
          b1: percent(t.totals.B1.adds_up, t.totals.reports),
          c1: percent(t.totals.C1.adds_up, t.totals.reports),
          h1: percent(t.totals.H1.adds_up, t.totals.reports),
        };
        for (const row of rows) expect(row.values[i], `${year} ${row.key} snapshot ${i}`).toBe(own[row.key as keyof typeof own]);
      });
      // No metric is the same in two snapshots (except where a year has no federal figures), so taking any of them from the
      // newest snapshot, or the first, would fail the check above.
      for (const row of rows) {
        const values = row.values.filter((v) => v !== null);
        if (values.length) expect(new Set(values).size, `${year} ${row.key}`).toBe(values.length);
      }
    }
    expect(renewalRow(trend).values).toEqual([0, 1, 2, 3].map((k) => percent(FIXTURE_SNAPSHOT.renewal.both + 5 * k, FIXTURE_SNAPSHOT.renewal.previous)));
    expect(new Set(renewalRow(trend).values).size).toBe(4);
  });

  it("gives renewal its own table (row), with the school years each snapshot compares, and none of the per-year rows", () => {
    expect(trendRows(points, "2024-25").map((r) => r.key)).toEqual(["published", "couldnt_read", "match_rate", "b1", "c1", "h1"]);
    const renewal = renewalRow(points);
    expect(renewal.key).toBe("renewal");
    expect(renewal.cohorts).toEqual(Array(4).fill("2025-26 of 2024-25"));
  });

  it("gives a dash (null) where a snapshot has no figure or no such year", () => {
    const rows = trendRows(points, "2025-26");   // 2025-26 has no federal figures in the fixture
    expect(rows.find((r) => r.key === "match_rate")!.values).toEqual([null, null, null, null]);
    expect(rows.find((r) => r.key === "published")!.values).toEqual([60, 60, 60, 60]);
    expect(trendRows(points, "1999-00").every((r) => r.values.every((v) => v === null))).toBe(true);
  });

  it("starts a series at the first snapshot that has it, and groups series that start together", () => {
    const early = at(FIXTURE_SNAPSHOT_V1, "2026-11-01", (s) => {
      s.years = s.years.filter((y) => y.cds_year !== "2025-26");
    });
    const pts = buildTrend(selectAllSnapshots(files(NEWEST, early)));
    const published = trendRows(pts, "2025-26").find((r) => r.key === "published")!;
    expect(published.values).toEqual([null, 60]);
    expect(seriesStart(published)).toBe(1);
    expect(seriesStart(trendRows(pts, "2024-25").find((r) => r.key === "published")!)).toBe(0);
    expect(seriesStart({ key: "published", label: "", unit: "count", values: [null, null], cohorts: null })).toBeNull();
    // Every 2025-26 row that exists starts at snapshot 1: one group naming them all.
    const groups = seriesStarts(trendRows(pts, "2025-26"));
    expect(groups).toHaveLength(1);
    expect(groups[0].index).toBe(1);
    expect(groups[0].labels).toEqual(["Reports published", "Reports we couldn’t read", "Enrollment totals that add up", "Admissions totals that add up", "Financial aid totals that add up"]);
    expect(seriesStarts(trendRows(pts, "2024-25"))).toEqual([]);
  });
});

describe("the line", () => {
  const point = (day: string, renewal = "2025-26"): TrendPoint => ({
    snapshot_of: `${day}T12:00:00Z`,
    run: "x",
    renewal: { percent: 50, current_year: renewal, previous_year: String(Number(renewal.slice(0, 4)) - 1) + "-" + renewal.slice(2, 4) },
    years: {},
  });
  const row = (values: (number | null)[], cohorts: (string | null)[] | null = null): TrendRow => ({ key: "published", label: "", unit: "percent", values, cohorts });
  const idx = (runs: ReturnType<typeof lineRuns>) => runs.map((r) => r.map((p) => p.index));

  it("is one run when every point has a value", () => {
    const pts = ["2026-11-01", "2026-11-08", "2026-11-15"].map((d) => point(d));
    expect(idx(lineRuns(row([10, 20, 30]), pts))).toEqual([[0, 1, 2]]);
  });

  it("breaks at an interior null: no segment is drawn through a missing point", () => {
    const pts = ["2026-11-01", "2026-11-08", "2026-11-15", "2026-11-22", "2026-11-29"].map((d) => point(d));
    expect(idx(lineRuns(row([10, 20, null, 40, 50]), pts))).toEqual([[0, 1], [3, 4]]);
    expect(idx(lineRuns(row([10, null, 30]), pts.slice(0, 3)))).toEqual([[0], [2]]);   // two single points: dots, no line
    expect(idx(lineRuns(row([null, null, 30]), pts.slice(0, 3)))).toEqual([[2]]);
    expect(lineRuns(row([null, null]), pts.slice(0, 2))).toEqual([]);
  });

  it("starts a new series where the cohort changes, even with no missing value", () => {
    const pts = ["2026-08-25", "2026-09-01", "2026-09-08", "2026-09-15"].map((d) => point(d));
    const cohorts = ["2025-26 of 2024-25", "2025-26 of 2024-25", "2026-27 of 2025-26", "2026-27 of 2025-26"];
    expect(idx(lineRuns(row([60, 62, 5, 9], cohorts), pts))).toEqual([[0, 1], [2, 3]]);
    // Without cohorts the same values are one line.
    expect(idx(lineRuns(row([60, 62, 5, 9]), pts))).toEqual([[0, 1, 2, 3]]);
    // A cohort change and a gap together.
    expect(idx(lineRuns(row([60, null, 5, 9], cohorts), pts))).toEqual([[0], [2, 3]]);
  });

  it("finds cohort changes for the page to name, and none when the cohort never changes", () => {
    const pts = [point("2026-08-25"), point("2026-09-01", "2026-27"), point("2026-09-08", "2026-27")];
    expect(cohortChanges(renewalRow(pts))).toEqual([{ index: 1, from: "2025-26 of 2024-25", to: "2026-27 of 2025-26" }]);
    expect(cohortChanges(renewalRow([point("2026-08-25"), point("2026-09-01")]))).toEqual([]);
    expect(cohortChanges(row([1, 2]))).toEqual([]);
  });

  it("clamps a value outside the scale to the edge of the box", () => {
    const pts = [point("2026-11-01"), point("2026-11-08"), point("2026-11-15")];
    expect(lineRuns(row([150, -20, 50]), pts, 72, 22)[0].map((p) => p.y)).toEqual([2, 20, 11]);
  });

  it("spaces points by snapshot date, not by their place in the list", () => {
    const pts = [point("2026-11-01"), point("2026-11-02"), point("2026-11-30")];
    const [run] = lineRuns(row([10, 20, 30]), pts, 72, 22);
    expect(run.map((p) => p.x)).toEqual([2, expect.closeTo(2 + (1 / 29) * 68, 5), 70]);
    // Evenly spaced dates are evenly spaced points.
    const even = lineRuns(row([10, 20, 30]), [point("2026-11-01"), point("2026-11-08"), point("2026-11-15")])[0];
    expect(even.map((p) => p.x)).toEqual([2, 36, 70]);
  });

  it("is on a fixed scale: a rate from 0% to 100% (the top is 2px in), a count from 0 to its largest", () => {
    const pts = [point("2026-11-01"), point("2026-11-08")];
    expect(lineRuns(row([100, 0]), pts, 72, 22)[0].map((p) => p.y)).toEqual([2, 20]);
    expect(lineRuns(row([83, 87]), pts, 72, 22)[0].map((p) => p.y.toFixed(1))).toEqual(["5.1", "4.3"]);
    const count: TrendRow = { key: "published", label: "", unit: "count", values: [40, 80], cohorts: null };
    expect(lineRuns(count, pts, 72, 22)[0].map((p) => p.y)).toEqual([11, 2]);
  });
});
