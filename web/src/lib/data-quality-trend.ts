// PRD 040 "trend across snapshots". One row of numbers per committed snapshot, per CDS year, read from each snapshot's
// own numbers (never recomputed or smoothed). Renewal is archive-wide, not per CDS year, so it has its own table. The metrics are the ones every snapshot format carries; a metric a snapshot
// can't give (a year it lacks, no federal figures) is null and shows as a dash.

import { formatSnapshotDate, renewalTile, yearGlance, type QualitySnapshot } from "./data-quality";

export type TrendMetricKey = "published" | "couldnt_read" | "match_rate" | "b1" | "c1" | "h1";

export const TREND_METRICS: { key: TrendMetricKey; label: string; unit: "count" | "percent" }[] = [
  { key: "published", label: "Reports published", unit: "count" },
  { key: "couldnt_read", label: "Reports we couldn’t read", unit: "count" },
  { key: "match_rate", label: "Admissions values matching federal figures", unit: "percent" },
  { key: "b1", label: "Enrollment totals that add up", unit: "percent" },
  { key: "c1", label: "Admissions totals that add up", unit: "percent" },
  { key: "h1", label: "Financial aid totals that add up", unit: "percent" },
];

export type TrendPoint = {
  snapshot_of: string;
  run: string;
  /** Current-year renewal, as /coverage shows it: schools with both years over schools with the earlier year. */
  renewal: { percent: number; current_year: string; previous_year: string };
  /** Per CDS year in that snapshot. */
  years: Record<string, Record<TrendMetricKey, number | null>>;
};

/** The trend's data, small enough to hand to the page: one point per snapshot, oldest first. */
export function buildTrend(snapshots: QualitySnapshot[]): TrendPoint[] {
  return snapshots.map((s) => {
    const tile = renewalTile(s.renewal);
    return {
      snapshot_of: s.snapshot_of,
      run: s.scoreboard_run,
      renewal: { percent: tile.percent, current_year: s.renewal.current_year, previous_year: s.renewal.previous_year },
      years: Object.fromEntries(
        s.years.map((y) => {
          const g = yearGlance(y);
          return [
            y.cds_year,
            { published: y.total.status.published, couldnt_read: y.total.status.couldnt_read, match_rate: g.matchRate, b1: g.b1, c1: g.c1, h1: g.h1 },
          ];
        }),
      ),
    };
  });
}

export type TrendRow = {
  key: TrendMetricKey | "renewal";
  label: string;
  unit: "count" | "percent";
  values: (number | null)[];
  /** What each value is a share of, where that changes over time (renewal compares different school years). Null: one definition throughout. */
  cohorts: (string | null)[] | null;
};

/** The table's rows for one CDS year: one value per point, null where the snapshot lacks the year or the figure. Renewal is not here: it is not per year. */
export function trendRows(points: TrendPoint[], year: string): TrendRow[] {
  return TREND_METRICS.map((m) => ({ ...m, values: points.map((p) => p.years[year]?.[m.key] ?? null), cohorts: null }));
}

/** Current-year renewal across the archive (all schools, not one CDS year), with the school years each snapshot compares. */
export function renewalRow(points: TrendPoint[]): TrendRow {
  return {
    key: "renewal",
    label: "Schools with a report for the current year, of those with one for the year before",
    unit: "percent",
    values: points.map((p) => p.renewal.percent),
    cohorts: points.map(renewalYears),
  };
}

/** The first snapshot that has each series, as an index into the points: a series starts there and the page says so. */
export function seriesStart(row: TrendRow): number | null {
  const i = row.values.findIndex((v) => v !== null);
  return i === -1 ? null : i;
}

/** Rows that start after the first snapshot, grouped by the snapshot they start at, so one sentence can name several. */
export function seriesStarts(rows: TrendRow[]): { index: number; labels: string[] }[] {
  const groups = new Map<number, string[]>();
  for (const r of rows) {
    const i = seriesStart(r);
    if (i !== null && i > 0) groups.set(i, [...(groups.get(i) ?? []), r.label]);
  }
  return [...groups.entries()].sort((a, b) => a[0] - b[0]).map(([index, labels]) => ({ index, labels }));
}

/** Where the school years a snapshot compares change (September, when the current year moves on): index of the first point of each new cohort. */
export function cohortChanges(row: TrendRow): { index: number; from: string; to: string }[] {
  const c = row.cohorts;
  if (!c) return [];
  const out: { index: number; from: string; to: string }[] = [];
  for (let i = 1; i < c.length; i++) if (c[i] !== c[i - 1] && c[i] !== null && c[i - 1] !== null) out.push({ index: i, from: c[i - 1]!, to: c[i]! });
  return out;
}

export type LinePoint = { index: number; x: number; y: number };

/**
 * The geometry of a row's line: runs of consecutive points, broken at a missing value and wherever the cohort changes (a
 * new cohort is a new series, never joined to the old). Points are spaced by snapshot date, not by their place in the list.
 * The scale is fixed, not stretched to the data: a rate runs from 0% to 100% and a count from 0 to its largest value, so a
 * one-point change looks as small as it is. A single point is a run of one (a dot, no line).
 */
export function lineRuns(row: TrendRow, points: TrendPoint[], width = 72, height = 22): LinePoint[][] {
  const times = points.map((p) => Date.parse(p.snapshot_of));
  const first = Math.min(...times);
  const span = Math.max(...times) - first;
  const top = row.unit === "percent" ? 100 : Math.max(...row.values.filter((v): v is number => v !== null), 1);
  const x = (t: number) => 2 + (span === 0 ? 0 : ((t - first) / span) * (width - 4));
  // Clamped to the scale: a value above the top (or below zero) is drawn at the edge, never outside the box.
  const y = (v: number) => 2 + (1 - Math.min(Math.max(v / top, 0), 1)) * (height - 4);
  const runs: LinePoint[][] = [];
  let run: LinePoint[] = [];
  row.values.forEach((v, i) => {
    const breaks = v === null || (run.length > 0 && row.cohorts && row.cohorts[i] !== row.cohorts[i - 1]);
    if (breaks && run.length) {
      runs.push(run);
      run = [];
    }
    if (v !== null) run.push({ index: i, x: x(times[i]), y: y(v) });
  });
  if (run.length) runs.push(run);
  return runs;
}

export function pointLabel(p: TrendPoint): string {
  return formatSnapshotDate(p.snapshot_of);
}

/** "2025-26 of 2024-25" for the school years a point's renewal compares. */
export function renewalYears(p: TrendPoint): string {
  return `${p.renewal.current_year} of ${p.renewal.previous_year}`;
}
