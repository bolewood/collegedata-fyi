// PRD 040: model for /data-quality and the snapshot-driven parts of /coverage.
// Pure functions over the committed public snapshot (web/src/data/data-quality).
// The page never computes live: it reads the newest reviewed snapshot at build.

import { isCanonicalCdsYear } from "./format";
import { DATA_LICENSE_NAME, DATA_LICENSE_URL } from "./data-license";

/**
 * Launch gate, on the isUsageLaunched pattern. It stays far in the future
 * until the owner decides to launch; flipping it is a one-line change that
 * turns on the header tab, nav and footer labels, sitemap entry and indexing
 * in one build. Do not set a date that has already passed without the owner.
 */
export const DATA_QUALITY_LAUNCH_DATE = "2099-01-01";

export function isDataQualityLaunched(now: Date = new Date()): boolean {
  return now.getTime() >= Date.parse(`${DATA_QUALITY_LAUNCH_DATE}T00:00:00Z`);
}

/** A rate over fewer reports than this isn't meaningful; the row shows counts only. */
export const MIN_REPORTS_FOR_RATE = 5;

/** Years before this start year aren't in the published projection (MIN_YEAR_START in project_browser_data.py). */
export const PROJECTED_FROM_YEAR_START = 2024;

export const KNOWN_PUBLIC_FORMATS: readonly number[] = [1];

export type StatusCounts = {
  published: number;
  set_aside: number;
  couldnt_read: number;
  not_read_yet: number;
};
export type FieldsStored = { median: number; p10: number };
export type FederalCounts = {
  reports: number;
  values: number;
  matches: number;
  no_value: number;
  differs: number;
};
export type SumOutcomes = {
  adds_up: number;
  under_2pct: number;
  off_more: number;
  cant_check: number;
};
export type AidOutcomes = { adds_up: number; doesnt: number; cant_check: number };
export type TotalsCounts = { reports: number; B1: SumOutcomes; C1: SumOutcomes; H1: AidOutcomes };

export type QualityRow = {
  status: StatusCounts;
  fields_stored: FieldsStored;
  federal: FederalCounts;
  totals: TotalsCounts;
};

export type QualityFormatRow = QualityRow & { format: string; label: string };

export type QualityYear = {
  cds_year: string;
  form: { form_year: string; full_field_schema: boolean; questions: number };
  federal_fall_loaded: boolean;
  other_form_numbering: number;
  removed: number;
  no_file: number;
  set_aside_reasons: { blank_form: number; too_little_read: number; wrong_file: number };
  federal_left_out: { single_campus: number; no_federal_figures: number };
  rows: QualityFormatRow[];
  total: QualityRow;
};

export type Renewal = {
  current_year: string;
  previous_year: string;
  current: number;
  previous: number;
  both: number;
};

export type QualitySnapshot = {
  public_format: number;
  snapshot_of: string;
  scoreboard_run: string;
  renewal: Renewal;
  years: QualityYear[];
};

// ── Years ─────────────────────────────────────────────────────────

/** Integer start year of a canonical CDS year, or null for `unknown` and anything else. */
export function yearStart(year: string | null | undefined): number | null {
  return isCanonicalCdsYear(year) ? Number(year.slice(0, 4)) : null;
}

/** Newest first. Non-year values sort last, never first (`unknown` is not a year). */
export function compareYearsDesc(a: string, b: string): number {
  const x = yearStart(a);
  const y = yearStart(b);
  if (x === null && y === null) return a.localeCompare(b);
  if (x === null) return 1;
  if (y === null) return -1;
  return y - x;
}

/** Fall of a CDS year: 2025-26 is fall 2025. */
export function fallOf(year: string): string {
  return year.slice(0, 4);
}

// ── Snapshot selection and validation ─────────────────────────────

export class SnapshotError extends Error {}

function isCount(v: unknown): v is number {
  return typeof v === "number" && Number.isInteger(v) && v >= 0;
}

export function validateSnapshot(raw: unknown, source: string): QualitySnapshot {
  const fail = (why: string): never => {
    throw new SnapshotError(`data-quality snapshot ${source}: ${why}`);
  };
  if (!raw || typeof raw !== "object") return fail("not an object");
  const s = raw as Record<string, unknown>;
  if (typeof s.public_format !== "number" || !KNOWN_PUBLIC_FORMATS.includes(s.public_format)) {
    return fail(`unknown public_format ${JSON.stringify(s.public_format)}`);
  }
  if (typeof s.snapshot_of !== "string" || Number.isNaN(Date.parse(s.snapshot_of))) {
    return fail("snapshot_of is missing or not a date");
  }
  if (typeof s.scoreboard_run !== "string") return fail("scoreboard_run is missing");
  const r = s.renewal as Record<string, unknown> | undefined;
  if (
    !r ||
    !isCanonicalCdsYear(r.current_year as string) ||
    !isCanonicalCdsYear(r.previous_year as string) ||
    !isCount(r.current) ||
    !isCount(r.previous) ||
    !isCount(r.both)
  ) {
    return fail("renewal block is missing or malformed");
  }
  if (r.previous === 0) return fail("renewal.previous is 0, so there is no denominator");
  if ((r.both as number) > (r.previous as number) || (r.both as number) > (r.current as number)) {
    return fail("renewal.both exceeds renewal.previous or renewal.current");
  }
  if (!Array.isArray(s.years) || s.years.length === 0) return fail("years is empty");
  for (const y of s.years as Record<string, unknown>[]) {
    if (!isCanonicalCdsYear(y.cds_year as string)) return fail(`bad cds_year ${JSON.stringify(y.cds_year)}`);
    if (!y.total || !Array.isArray(y.rows) || !y.form || !y.set_aside_reasons || !y.federal_left_out) {
      return fail(`year ${String(y.cds_year)} is missing rows, total, form or counts`);
    }
  }
  return raw as QualitySnapshot;
}

/**
 * Pick the snapshot with the newest `snapshot_of`. Throws on: no files (when
 * `requireAny`), two files with the same date, or a file the page can't read.
 */
export function selectSnapshot(
  files: { name: string; json: unknown }[],
  requireAny: boolean,
): QualitySnapshot | null {
  if (files.length === 0) {
    if (requireAny) {
      throw new SnapshotError("web/src/data/data-quality has no snapshot (.json) files");
    }
    return null;
  }
  const parsed = files.map((f) => validateSnapshot(f.json, f.name));
  const days = new Map<string, string>();
  parsed.forEach((snap, i) => {
    const day = new Date(snap.snapshot_of).toISOString().slice(0, 10);
    const seen = days.get(day);
    if (seen) {
      throw new SnapshotError(`data-quality snapshots ${seen} and ${files[i].name} have the same date ${day}`);
    }
    days.set(day, files[i].name);
  });
  return parsed.reduce((a, b) => (Date.parse(b.snapshot_of) > Date.parse(a.snapshot_of) ? b : a));
}

// ── Rates ─────────────────────────────────────────────────────────

/** Whole-number percent, or null when there is no denominator. */
export function percent(num: number, den: number): number | null {
  return den > 0 ? Math.round((100 * num) / den) : null;
}

/** Percent for a table row: null for groups under the floor (counts only). */
export function rowPercent(num: number, den: number, reports: number): number | null {
  return reports < MIN_REPORTS_FOR_RATE ? null : percent(num, den);
}

export function liveCount(s: StatusCounts): number {
  return s.published + s.set_aside + s.couldnt_read + s.not_read_yet;
}

export type YearGlance = {
  year: string;
  status: StatusCounts;
  /** null: no federal figures for the year (dash, not zero). */
  matchRate: number | null;
  b1: number | null;
  c1: number | null;
  h1: number | null;
};

/** One row of "All years at a glance", from year totals (always shown in full). */
export function yearGlance(year: QualityYear): YearGlance {
  const t = year.total;
  const reports = t.totals.reports;
  return {
    year: year.cds_year,
    status: t.status,
    matchRate: year.federal_fall_loaded ? percent(t.federal.matches, t.federal.values) : null,
    b1: percent(t.totals.B1.adds_up, reports),
    c1: percent(t.totals.C1.adds_up, reports),
    h1: percent(t.totals.H1.adds_up, reports),
  };
}

export function yearsNewestFirst(snapshot: QualitySnapshot): QualityYear[] {
  return [...snapshot.years].sort((a, b) => compareYearsDesc(a.cds_year, b.cds_year));
}

/** The year the picker selects when the URL names none or names one we don't have. */
export function resolveYear(snapshot: QualitySnapshot, requested: string | null | undefined): QualityYear {
  const years = yearsNewestFirst(snapshot);
  return years.find((y) => y.cds_year === requested) ?? years[0];
}

export function publishedTotal(snapshot: QualitySnapshot): number {
  return snapshot.years.reduce((n, y) => n + y.total.status.published, 0);
}

export function isProjectedYear(year: string): boolean {
  const start = yearStart(year);
  return start !== null && start >= PROJECTED_FROM_YEAR_START;
}

const NUMBER_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"];

/** The two-sentence lede: what the page measures, the snapshot date, the populations. */
export function qualityLede(snapshot: QualitySnapshot): { populations: string; meaning: string } {
  const published = publishedTotal(snapshot).toLocaleString("en-US");
  const count = snapshot.years.length;
  const years = count < NUMBER_WORDS.length ? NUMBER_WORDS[count] : String(count);
  return {
    populations: `Snapshot of ${formatSnapshotDate(snapshot.snapshot_of)}: ${published} reports published with numbers across ${years} ${count === 1 ? "year" : "years"}, checked against federal figures and against their own printed totals.`,
    meaning: "Data quality here means the quality of what this archive publishes, not the quality of any school’s own data.",
  };
}

// ── Renewal (the amendment) ───────────────────────────────────────

export type RenewalTile = {
  both: number;
  previous: number;
  /** both / previous as a fraction; validateSnapshot guarantees previous > 0. */
  share: number;
  percent: number;
  sentence: string;
};

export function renewalTile(renewal: Renewal): RenewalTile {
  const share = renewal.both / renewal.previous;
  return {
    both: renewal.both,
    previous: renewal.previous,
    share,
    percent: Math.round(share * 100),
    sentence: `Of the ${renewal.previous.toLocaleString("en-US")} schools with a ${renewal.previous_year} report on file, ${renewal.both.toLocaleString("en-US")} also have a ${renewal.current_year} report on file.`,
  };
}

export function formatSnapshotDate(iso: string): string {
  return new Date(iso).toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
    timeZone: "UTC",
  });
}

// ── CSV ───────────────────────────────────────────────────────────

export function csvCell(v: string | number | null | undefined): string {
  if (v === null || v === undefined) return "";
  const s = String(v);
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function csvLine(cells: (string | number | null | undefined)[]): string {
  return cells.map(csvCell).join(",");
}

/** A `#` comment block that opens a downloaded CSV. */
export function csvNotice(lines: string[]): string {
  return lines.map((l) => `# ${l}`).join("\r\n") + "\r\n";
}

export type QualityTableId = "reports" | "federal" | "totals";

export const TABLE_TITLES: Record<QualityTableId, string> = {
  reports: "Reports and fields stored",
  federal: "Admissions against federal figures",
  totals: "Do the printed totals add up?",
};

const TABLE_SLUG: Record<QualityTableId, string> = {
  reports: "reports",
  federal: "federal-match",
  totals: "totals-add-up",
};

export function qualityCsvFilename(table: QualityTableId, year: string, snapshotOf: string): string {
  return `collegedata-data-quality-${TABLE_SLUG[table]}-${year}-${snapshotOf.slice(0, 10)}.csv`;
}

/** CSV of one table for one year: licence notice, header, one line per format, then the year total. */
export function buildQualityCsv(table: QualityTableId, year: QualityYear, snapshot: QualitySnapshot): string {
  const notice = csvNotice([
    `collegedata.fyi data quality, snapshot of ${snapshot.snapshot_of.slice(0, 10)}, CDS year ${year.cds_year}, table: ${TABLE_TITLES[table]}.`,
    `Counts of reports in this archive, licensed ${DATA_LICENSE_NAME} (${DATA_LICENSE_URL}). Credit collegedata.fyi (https://www.collegedata.fyi).`,
    `Counts only: a rate over fewer than ${MIN_REPORTS_FOR_RATE} reports isn't meaningful.`,
  ]);
  const lines: string[] = [];
  const all: { name: string; row: QualityRow }[] = [
    ...year.rows.map((r) => ({ name: r.label, row: r as QualityRow })),
    { name: "All formats", row: year.total },
  ];
  if (table === "reports") {
    lines.push(csvLine(["format", "published", "set_aside", "couldnt_read", "not_read_yet", "fields_stored_median", "fields_stored_lowest_10pct"]));
    for (const { name, row } of all) {
      lines.push(csvLine([name, row.status.published, row.status.set_aside, row.status.couldnt_read, row.status.not_read_yet, row.fields_stored.median, row.fields_stored.p10]));
    }
  } else if (table === "federal") {
    lines.push(csvLine(["format", "reports_checked", "values_up_to_3_per_report", "matches", "no_value", "differs"]));
    for (const { name, row } of all) {
      const f = row.federal;
      // No federal figures for the year: blanks, not zeros.
      lines.push(csvLine(year.federal_fall_loaded ? [name, f.reports, f.values, f.matches, f.no_value, f.differs] : [name, "", "", "", "", ""]));
    }
  } else {
    lines.push(csvLine(["format", "reports", "B1_adds_up", "B1_off_by_under_2pct", "B1_off_by_more", "B1_cant_check", "C1_adds_up", "C1_off_by_under_2pct", "C1_off_by_more", "C1_cant_check", "H1_adds_up", "H1_doesnt_add_up", "H1_cant_check"]));
    for (const { name, row } of all) {
      const t = row.totals;
      lines.push(csvLine([name, t.reports, t.B1.adds_up, t.B1.under_2pct, t.B1.off_more, t.B1.cant_check, t.C1.adds_up, t.C1.under_2pct, t.C1.off_more, t.C1.cant_check, t.H1.adds_up, t.H1.doesnt, t.H1.cant_check]));
    }
  }
  return notice + lines.join("\r\n") + "\r\n";
}
