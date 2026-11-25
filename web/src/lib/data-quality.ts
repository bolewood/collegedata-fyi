// PRD 040: model for /data-quality and the snapshot-driven parts of /coverage.
// Pure functions over the committed public snapshot (web/src/data/data-quality).
// The page never computes live: it reads the newest reviewed snapshot at build.

import { isCanonicalCdsYear } from "./format";
import { formatLabel } from "./format-labels";

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

/**
 * Format 1 is the first snapshot shape. Format 2 adds the size of federal differences (`federal.differs_2_to_10pct`
 * and `federal.differs_over_10pct`); those keys are required on 2 and refused on 1. Format 1 files stay readable so a
 * later trend line can use them. Format 3 adds `sections` to each year (fields stored and usable answers by CDS
 * section): required on 3, refused on 1 and 2. Format 4 adds the enrollment (B1) and tuition (G1) checks against IPEDS
 * (`checks` in each row and total, `federal_checks` in each year): required on 4, refused on 1 to 3.
 */
export const KNOWN_PUBLIC_FORMATS: readonly number[] = [1, 2, 3, 4];

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
  /**
   * Differing values split by the gap as a share of the federal figure: over 2% up to and including 10%, and over
   * 10% (exactly 10% is in the first). They add up to `differs`. Present on public_format 2, absent on 1.
   */
  differs_2_to_10pct?: number;
  differs_over_10pct?: number;
};
export type SumOutcomes = {
  adds_up: number;
  under_2pct: number;
  off_more: number;
  cant_check: number;
};
export type AidOutcomes = { adds_up: number; doesnt: number; cant_check: number };
export type TotalsCounts = { reports: number; B1: SumOutcomes; C1: SumOutcomes; H1: AidOutcomes };

/**
 * One of the two extra federal checks, one value per report, so `reports` is also the number of values:
 * matches + no_value + differs = reports. Differs split by size as in Table B.
 */
export type CheckCounts = {
  reports: number;
  matches: number;
  no_value: number;
  differs: number;
  differs_2_to_10pct: number;
  differs_over_10pct: number;
};
export type CheckName = "enrollment" | "tuition";
export type ChecksBlock = Record<CheckName, CheckCounts>;
/** What a year knows about a check: whether IPEDS figures are loaded for it, which IPEDS year they are, who was left out. */
export type CheckInfo = { loaded: boolean; data_year: number; single_campus: number; no_federal_figures: number };

export type QualityRow = {
  status: StatusCounts;
  fields_stored: FieldsStored;
  federal: FederalCounts;
  totals: TotalsCounts;
  /** public_format 4; absent on 1 to 3. */
  checks?: ChecksBlock;
};

export type QualityFormatRow = QualityRow & { format: string; label: string };

/** One CDS section of the year's form: its questions, and the median per report over the reports in `QualitySections`. */
export type SectionRow = {
  /** Section letter, A to J. */
  section: string;
  questions: number;
  stored_median: number;
  /** Median of usable answers (value_status `reported`). Never above stored_median. */
  usable_median: number;
};
export type QualitySections = {
  /** Published reports numbered by the year's own form: published minus other_form_numbering. 0 with no rows. */
  reports: number;
  /** One row per section of the form, A to J; empty for a year whose form has no full field schema. */
  rows: SectionRow[];
};

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
  /** public_format 3; absent on 1 and 2. */
  sections?: QualitySections;
  /** public_format 4; absent on 1 to 3. */
  federal_checks?: Record<CheckName, CheckInfo>;
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

/**
 * `obj` must have exactly the named keys (plus any `optional` ones), each a non-negative integer, like the Python
 * `--public` allow-list. A misspelled or extra key is refused, so a count can't hide under a name nothing reads.
 */
function allCounts(obj: unknown, keys: string[], optional: string[] = []): string | null {
  if (!obj || typeof obj !== "object") return "missing counts";
  const o = obj as Record<string, unknown>;
  for (const k of keys) {
    if (!isCount(o[k])) return `${k} must be a non-negative integer`;
  }
  for (const k of Object.keys(o)) {
    if (!keys.includes(k) && !optional.includes(k)) return `unexpected key ${k}`;
    if (optional.includes(k) && !isCount(o[k])) return `${k} must be a non-negative integer`;
  }
  return null;
}

const STATUS_KEYS = ["published", "set_aside", "couldnt_read", "not_read_yet"];
const FEDERAL_KEYS = ["reports", "values", "matches", "no_value", "differs"];
const FEDERAL_SPLIT_KEYS = ["differs_2_to_10pct", "differs_over_10pct"];
const SUM_KEYS = ["adds_up", "under_2pct", "off_more", "cant_check"];
const AID_KEYS = ["adds_up", "doesnt", "cant_check"];

const CHECK_KEYS = ["reports", "matches", "no_value", "differs", "differs_2_to_10pct", "differs_over_10pct"];
const CHECK_NAMES: CheckName[] = ["enrollment", "tuition"];

/** `checks` of a row or total: both checks, each exactly the six counts (format 4), or absent (formats 1 to 3). */
function checksProblem(r: Record<string, unknown>, format: number): string | null {
  if (format < 4) return r.checks === undefined ? null : `unexpected key checks on public_format ${format}`;
  const checks = r.checks as Record<string, unknown> | undefined;
  if (!checks || typeof checks !== "object") return "checks is missing";
  const extra = Object.keys(checks).find((k) => !CHECK_NAMES.includes(k as CheckName));
  if (extra) return `checks: unexpected key ${extra}`;
  for (const name of CHECK_NAMES) {
    const problem = allCounts(checks[name], CHECK_KEYS);
    if (problem) return `checks.${name}: ${problem}`;
  }
  return null;
}

/** A row or year total: status, fields_stored, federal and totals blocks, all counts, no other keys. */
function rowCountsProblem(row: unknown, format: number): string | null {
  if (!row || typeof row !== "object") return "missing";
  const r = row as Record<string, unknown>;
  const totals = r.totals as Record<string, unknown> | undefined;
  return (
    allCounts(r.status, STATUS_KEYS) ??
    allCounts(r.fields_stored, ["median", "p10"]) ??
    allCounts(r.federal, format >= 2 ? [...FEDERAL_KEYS, ...FEDERAL_SPLIT_KEYS] : FEDERAL_KEYS) ??
    (totals && isCount(totals.reports) ? null : "totals.reports must be a non-negative integer") ??
    allCounts(totals?.B1, SUM_KEYS) ??
    allCounts(totals?.C1, SUM_KEYS) ??
    allCounts(totals?.H1, AID_KEYS) ??
    checksProblem(r, format)
  );
}

/** CDS section letters and names, as in the form schemas. A snapshot with another letter is refused. */
export const SECTION_NAMES: Readonly<Record<string, string>> = {
  A: "General information",
  B: "Enrollment and persistence",
  C: "First-time, first-year admission",
  D: "Transfer admission",
  E: "Academic offerings and policies",
  F: "Student life",
  G: "Annual expenses",
  H: "Financial aid",
  I: "Instructional faculty and class size",
  J: "Disciplinary areas of degrees conferred",
};

/**
 * `federal_checks` of a year (format 4): per check, whether IPEDS figures are loaded, the IPEDS year, and who was left
 * out. The IPEDS year is the fall for enrollment and the next fall's academic year for tuition (the CDS form asks for the
 * following year's price). When loaded, reports checked + left out = published; when not, no report is checked.
 */
function federalChecksProblem(year: Record<string, unknown>): string | null {
  const block = year.federal_checks as Record<string, Record<string, unknown>> | undefined;
  if (!block || typeof block !== "object") return "federal_checks is missing";
  const extra = Object.keys(block).find((k) => !CHECK_NAMES.includes(k as CheckName));
  if (extra) return `federal_checks: unexpected key ${extra}`;
  const total = year.total as QualityRow;
  for (const name of CHECK_NAMES) {
    const info = block[name];
    if (!info || typeof info !== "object") return `federal_checks.${name} is missing`;
    const { loaded, ...counts } = info;
    if (typeof loaded !== "boolean") return `federal_checks.${name}: loaded must be a boolean`;
    const problem = allCounts(counts, ["data_year", "single_campus", "no_federal_figures"]);
    if (problem) return `federal_checks.${name}: ${problem}`;
    const expected = Number(String(year.cds_year).slice(0, 4)) + (name === "tuition" ? 1 : 0);
    if (info.data_year !== expected) return `federal_checks.${name}: data_year is ${String(info.data_year)}, not ${expected}`;
    const reports = total.checks![name].reports;
    if ((info.single_campus as number) > total.status.published) return `federal_checks.${name}: single_campus exceeds the total's published`;
    if (!loaded) {
      if (info.no_federal_figures !== 0) return `federal_checks.${name}: no_federal_figures must be 0 for a year with no IPEDS figures`;
      for (const r of [...(year.rows as QualityRow[]), total]) {
        if (Object.values(r.checks![name]).some((n) => n !== 0)) return `federal_checks.${name}: counts are not zero for a year with no IPEDS figures`;
      }
    } else if (reports + (info.single_campus as number) + (info.no_federal_figures as number) !== total.status.published) {
      return `federal_checks.${name}: reports checked + left out don't add up to the total's published`;
    }
  }
  return null;
}

/** Shape and arithmetic of a year's `sections` block. Returns the first problem or null. */
function sectionsProblem(year: Record<string, unknown>): string | null {
  const block = year.sections as Record<string, unknown> | undefined;
  if (!block || typeof block !== "object" || Array.isArray(block)) return "sections is missing";
  const bad = allCounts({ reports: block.reports }, ["reports"]);
  if (bad) return `sections: ${bad}`;
  const extra = Object.keys(block).filter((k) => k !== "reports" && k !== "rows");
  if (extra.length) return `sections: unexpected key ${extra[0]}`;
  const rows = block.rows;
  if (!Array.isArray(rows)) return "sections.rows is missing";
  const letters = Object.keys(SECTION_NAMES);
  // Every CDS form has all ten sections, A to J, so a row may not be left out.
  if (rows.length > 0 && rows.length !== letters.length) return `sections: ${rows.length} sections, not all of A to J`;
  let last = -1;
  let questions = 0;
  for (const row of rows as Record<string, unknown>[]) {
    if (typeof row?.section !== "string") return "sections: a section letter must be text";
    const letter = row.section;
    const at = letters.indexOf(letter);
    if (at < 0) return `sections: unknown section ${JSON.stringify(row?.section)}`;
    if (at <= last) return `sections: section ${letter} is out of order or listed twice`;
    last = at;
    // Exactly these four keys; the letter is already known, so the rest are counts (allCounts also refuses extras).
    const { section: _letter, ...counts } = row;
    const problem = allCounts(counts, ["questions", "stored_median", "usable_median"]);
    if (problem) return `sections: section ${letter}: ${problem}`;
    const r = row as unknown as SectionRow;
    if (r.questions === 0) return `sections: section ${letter} has no questions`;
    if (r.stored_median > r.questions) return `sections: section ${letter} stores more fields than the form has questions`;
    if (r.usable_median > r.stored_median) return `sections: section ${letter} has more usable answers than fields stored`;
    if (block.reports === 0 && (r.stored_median !== 0 || r.usable_median !== 0)) return `sections: section ${letter} has a median but no reports`;
    questions += r.questions;
  }
  const form = year.form as { full_field_schema: boolean; questions: number };
  if (form.full_field_schema !== (rows.length > 0)) return "sections: rows are present exactly when the form has a full field schema";
  if (rows.length > 0 && questions !== form.questions) return `sections: the sections' questions add up to ${questions}, not the form's ${form.questions}`;
  const total = year.total as QualityRow;
  const expected = rows.length > 0 ? total.status.published - (year.other_form_numbering as number) : 0;
  if (block.reports !== expected) return `sections.reports is ${String(block.reports)}, not published minus other_form_numbering (${expected})`;
  return null;
}

type Counts = Record<string, number>;

/** Every count in a row that is a plain sum across rows, named one by one (fields_stored is a median, so it is not). */
function summedCounts(r: QualityRow): Counts {
  const { status: s, federal: f, totals: t } = r;
  return {
    "status.published": s.published,
    "status.set_aside": s.set_aside,
    "status.couldnt_read": s.couldnt_read,
    "status.not_read_yet": s.not_read_yet,
    "federal.reports": f.reports,
    "federal.values": f.values,
    "federal.matches": f.matches,
    "federal.no_value": f.no_value,
    "federal.differs": f.differs,
    // Public format 1 has no split: leave the keys out (a sum of rows that are all absent is zero either way).
    ...(f.differs_2_to_10pct === undefined ? {} : { "federal.differs_2_to_10pct": f.differs_2_to_10pct }),
    ...(f.differs_over_10pct === undefined ? {} : { "federal.differs_over_10pct": f.differs_over_10pct }),
    ...(r.checks === undefined
      ? {}
      : Object.fromEntries(
          CHECK_NAMES.flatMap((name) => CHECK_KEYS.map((k) => [`checks.${name}.${k}`, r.checks![name][k as keyof CheckCounts]])),
        )),
    "totals.reports": t.reports,
    "totals.B1.adds_up": t.B1.adds_up,
    "totals.B1.under_2pct": t.B1.under_2pct,
    "totals.B1.off_more": t.B1.off_more,
    "totals.B1.cant_check": t.B1.cant_check,
    "totals.C1.adds_up": t.C1.adds_up,
    "totals.C1.under_2pct": t.C1.under_2pct,
    "totals.C1.off_more": t.C1.off_more,
    "totals.C1.cant_check": t.C1.cant_check,
    "totals.H1.adds_up": t.H1.adds_up,
    "totals.H1.doesnt": t.H1.doesnt,
    "totals.H1.cant_check": t.H1.cant_check,
  };
}

const sumB = (o: SumOutcomes) => o.adds_up + o.under_2pct + o.off_more + o.cant_check;
const sumH = (o: AidOutcomes) => o.adds_up + o.doesnt + o.cant_check;

/**
 * Part of the arithmetic the Python `--public` step enforces (PRD 040, "Tests: Sums"), repeated here so a
 * hand-edited or mis-merged snapshot fails the build instead of rendering a rate over 100%. Checked: the total
 * equals the sum of the rows in every summed count (so the rows' statuses give the live count), federal
 * matches + no value + differs = values, differs = its two size parts (format 2), values <= 3 per report, federal reports <= published, B1, C1 and H1
 * outcomes = totals.reports = published, set-aside reasons = set aside, and, for a year with federal figures,
 * checked + left out = published, and (for a year with no federal figures) every federal count zero. Not checked here: live + removed + no file = manifest (the snapshot has no
 * manifest count) and the run-level agreement with `aggregate()`. Counts are already known to be non-negative
 * integers. Returns the first problem or null.
 */
function arithmeticProblem(year: QualityYear): string | null {
  const rowSums: Counts = {};
  for (const r of year.rows) {
    for (const [k, v] of Object.entries(summedCounts(r))) rowSums[k] = (rowSums[k] ?? 0) + v;
  }
  // A year with no live documents has no rows, so a missing row sum is zero, not "undefined".
  for (const [k, v] of Object.entries(summedCounts(year.total))) {
    if (v !== (rowSums[k] ?? 0)) return `total ${k} is ${v}, but the rows add up to ${rowSums[k] ?? 0}`;
  }
  if (!year.federal_fall_loaded) {
    for (const r of [...year.rows, year.total]) {
      if (Object.values(r.federal).some((n) => n !== 0)) return "federal counts are not zero for a year with no federal figures";
    }
  }
  const check = (name: string, r: QualityRow): string | null => {
    const f = r.federal;
    if (f.matches + f.no_value + f.differs !== f.values) return `${name}: federal matches + no_value + differs is not values`;
    if (f.differs_2_to_10pct !== undefined && f.differs_2_to_10pct + (f.differs_over_10pct ?? 0) !== f.differs) {
      return `${name}: federal differs_2_to_10pct + differs_over_10pct is not differs`;
    }
    for (const which of r.checks ? CHECK_NAMES : []) {
      const c = r.checks![which];
      if (c.matches + c.no_value + c.differs !== c.reports) return `${name}: ${which} matches + no_value + differs is not reports`;
      if (c.differs_2_to_10pct + c.differs_over_10pct !== c.differs) return `${name}: ${which} differs_2_to_10pct + differs_over_10pct is not differs`;
      if (c.reports > r.status.published) return `${name}: ${which} reports exceeds published`;
    }
    if (f.values > 3 * f.reports) return `${name}: federal values exceed 3 per report`;
    if (f.reports > r.status.published) return `${name}: federal.reports exceeds published`;
    if (r.totals.reports !== r.status.published) return `${name}: totals.reports is not status.published`;
    if (sumB(r.totals.B1) !== r.totals.reports) return `${name}: B1 outcomes don't add up to totals.reports`;
    if (sumB(r.totals.C1) !== r.totals.reports) return `${name}: C1 outcomes don't add up to totals.reports`;
    if (sumH(r.totals.H1) !== r.totals.reports) return `${name}: H1 outcomes don't add up to totals.reports`;
    return null;
  };
  for (const r of year.rows) {
    const p = check(`row ${r.format}`, r);
    if (p) return p;
  }
  const total = check("total", year.total);
  if (total) return total;
  const why = year.set_aside_reasons;
  if (why.blank_form + why.too_little_read + why.wrong_file !== year.total.status.set_aside) {
    return "set_aside_reasons don't add up to the total's set_aside";
  }
  const left = year.federal_left_out;
  if (year.federal_fall_loaded && year.total.federal.reports + left.single_campus + left.no_federal_figures !== year.total.status.published) {
    return "federal reports checked + left out don't add up to the total's published";
  }
  return null;
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
    return fail("renewal block is missing or malformed (years and counts must be real)");
  }
  if (yearStart(r.current_year as string) !== (yearStart(r.previous_year as string) as number) + 1) {
    return fail("renewal.current_year is not the year after renewal.previous_year");
  }
  if (r.previous === 0) return fail("renewal.previous is 0, so there is no denominator");
  if ((r.both as number) > (r.previous as number) || (r.both as number) > (r.current as number)) {
    return fail("renewal.both exceeds renewal.previous or renewal.current");
  }
  if (!Array.isArray(s.years) || s.years.length === 0) return fail("years is empty");
  const seen = new Set<string>();
  for (const y of s.years as Record<string, unknown>[]) {
    if (!y || typeof y !== "object") return fail("a year entry is not an object");
    const label = String(y.cds_year);
    if (!isCanonicalCdsYear(y.cds_year as string)) return fail(`bad cds_year ${JSON.stringify(y.cds_year)}`);
    if (seen.has(label)) return fail(`duplicate cds_year ${label}`);
    seen.add(label);
    const where = `year ${label}`;
    // Years the producer can write but the page can't show yet (#516): refuse them rather than render zeros.
    if (y.sum_checks_unavailable !== undefined) {
      return fail(`${where}: sum_checks_unavailable is not shown by the page yet (#516), so this snapshot can't be published`);
    }
    if (((y.federal_left_out as Record<string, unknown> | undefined)?.not_compared ?? 0) !== 0) {
      return fail(`${where}: federal_left_out.not_compared is not shown by the page yet (#516), so this snapshot can't be published`);
    }
    if (typeof y.federal_fall_loaded !== "boolean") return fail(`${where}: federal_fall_loaded must be a boolean`);
    const form = y.form as Record<string, unknown> | undefined;
    if (!form || typeof form !== "object") return fail(`${where}: form is missing`);
    if (typeof form.full_field_schema !== "boolean") return fail(`${where}: form.full_field_schema must be a boolean`);
    if (typeof form.form_year !== "string") return fail(`${where}: form.form_year is missing`);
    for (const [k, v] of [
      ["form.questions", form.questions],
      ["other_form_numbering", y.other_form_numbering],
      ["removed", y.removed],
      ["no_file", y.no_file],
    ] as const) {
      if (!isCount(v)) return fail(`${where}: ${k} must be a non-negative integer`);
    }
    const problem =
      allCounts(y.set_aside_reasons, ["blank_form", "too_little_read", "wrong_file"]) ??
      allCounts(y.federal_left_out, ["single_campus", "no_federal_figures"], ["not_compared"]);
    if (problem) return fail(`${where}: ${problem}`);
    if (!Array.isArray(y.rows)) return fail(`${where}: rows is missing`);
    const totalProblem = rowCountsProblem(y.total, s.public_format);
    if (totalProblem) return fail(`${where}: total: ${totalProblem}`);
    for (const row of y.rows as Record<string, unknown>[]) {
      if (typeof row?.format !== "string" || typeof row?.label !== "string") {
        return fail(`${where}: a row has no format or label`);
      }
      const rowProblem = rowCountsProblem(row, s.public_format);
      if (rowProblem) return fail(`${where}: row ${row.format}: ${rowProblem}`);
    }
    const arithmetic = arithmeticProblem(y as unknown as QualityYear);
    if (arithmetic) return fail(`${where}: ${arithmetic}`);
    // Public format 3 adds `sections`; formats 1 and 2 must not carry it.
    if (s.public_format >= 4) {
      const checks = federalChecksProblem(y);
      if (checks) return fail(`${where}: ${checks}`);
    } else if (y.federal_checks !== undefined) {
      return fail(`${where}: unexpected key federal_checks on public_format ${s.public_format}`);
    }
    if (s.public_format >= 3) {
      const sections = sectionsProblem(y);
      if (sections) return fail(`${where}: ${sections}`);
    } else if (y.sections !== undefined) {
      return fail(`${where}: unexpected key sections on public_format ${s.public_format}`);
    }
  }
  return raw as QualitySnapshot;
}

/**
 * Pick the snapshot with the newest `snapshot_of`. Throws on: no files, two
 * files with the same date, or a file the page can't read.
 */
export function selectSnapshot(files: { name: string; json: unknown }[]): QualitySnapshot {
  if (files.length === 0) {
    throw new SnapshotError("web/src/data/data-quality has no snapshot (.json) files");
  }
  const parsed = files.map((f) => validateSnapshot(f.json, f.name));
  const days = new Map<string, string>();
  parsed.forEach((snap, i) => {
    const day = snapshotDay(snap);
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

// ── Hand checks (PRD 040 "M0 samples", 2026-11-25) ────────────────
// Each note is tied to the CDS years its sample covered and shows only there.

export const HAND_CHECK_ISO = "2026-11-25";
export const HAND_CHECK_DATE = formatSnapshotDate(`${HAND_CHECK_ISO}T00:00:00Z`);

/**
 * 20 of the 217 published 2023-24 reports whose financial aid result was "can't check" in the 2026-11-25 run, read
 * against the schools' files: 19 had the table filled in and we hadn't stored it in full.
 *
 * The note describes that pool of 217. Once the fix lands the pool shrinks and the note would be false, so it shows
 * only while the snapshot's 2023-24 count is within 90% to 110% of 217: below that the pool the sample described has
 * mostly gone, above it the pool has grown a lot (a regression), and either way the sample no longer describes it.
 * A new sample is needed to say anything about what is left.
 */
export const AID_CANT_CHECK_SAMPLE = {
  years: ["2023-24"],
  checked: 20,
  ours: 19,
  population: 217,
  /** The note shows while the snapshot's count is within this share of the population, both ways. */
  keepRange: [0.9, 1.1],
} as const;

/**
 * 10 admissions "differs" reports from 2023-24 and 2024-25. In 8 the file had the number we compared. 2 were on our
 * side: one misread and one report filed for a different scope than the federal record.
 */
export const FEDERAL_DIFFERS_SAMPLE = {
  years: ["2023-24", "2024-25"],
  checked: 10,
  sameInFile: 8,
  ours: 2,
  /**
   * The pool the 10 were drawn from, in the 2026-11-25 run: 140 published reports with at least one differing value,
   * pooled over the two years. The snapshot counts differing VALUES (up to 3 per report), not reports, so the guard
   * is on values: 219 in that run. The note shows while the two years together are within `keepRange` of 219.
   */
  populationReports: 140,
  populationValues: 219,
  keepRange: [0.9, 1.1],
} as const;

/** True when the year carries the size of federal differences (public_format 2). Validation makes every row agree with the total. */
export function hasDifferenceSplit(year: QualityYear): boolean {
  return year.total.federal.differs_2_to_10pct !== undefined;
}

/** Differing values pooled over the years the sample covered, from the snapshot. */
export function pooledDiffers(snapshot: QualitySnapshot): number {
  return snapshot.years
    .filter((y) => (FEDERAL_DIFFERS_SAMPLE.years as readonly string[]).includes(y.cds_year))
    .reduce((n, y) => n + y.total.federal.differs, 0);
}

/** The pooled count of differing values between which the note shows: 198 to 240 for a pool of 219. */
export function differsPoolBounds(): { low: number; high: number } {
  const s = FEDERAL_DIFFERS_SAMPLE;
  return { low: Math.ceil(s.populationValues * s.keepRange[0]), high: Math.floor(s.populationValues * s.keepRange[1]) };
}

/** The counts of can't-check reports between which the 2023-24 note shows: 196 to 238 for a pool of 217. */
export function aidPoolBounds(): { low: number; high: number } {
  const s = AID_CANT_CHECK_SAMPLE;
  return { low: Math.ceil(s.population * s.keepRange[0]), high: Math.floor(s.population * s.keepRange[1]) };
}

/** The 2023-24 financial aid sample. Null for a year it didn't cover, or once the pool it described has mostly gone (see above). */
export function aidCantCheckNote(year: QualityYear): string | null {
  const s = AID_CANT_CHECK_SAMPLE;
  const count = year.total.totals.H1.cant_check;
  const stillThere = count >= aidPoolBounds().low && count <= aidPoolBounds().high;
  if (!(s.years as readonly string[]).includes(year.cds_year) || !stillThere) return null;
  return `For financial aid in ${year.cds_year}: in a hand check of ${s.checked} of the reports we couldn’t check, sampled on ${HAND_CHECK_DATE}, ${s.ours} had the financial aid table filled in and we hadn’t stored it in full.`;
}

/**
 * The admissions "differs" sample. Null for a year it didn't cover, one with no federal figures, one with no differing
 * values, or once the two covered years together have moved out of 90% to 110% of the pool the sample was drawn from.
 */
export function federalDiffersNote(year: QualityYear, snapshot: QualitySnapshot): string | null {
  const s = FEDERAL_DIFFERS_SAMPLE;
  const pooled = pooledDiffers(snapshot);
  const { low, high } = differsPoolBounds();
  if (!(s.years as readonly string[]).includes(year.cds_year) || !year.federal_fall_loaded || year.total.federal.differs === 0) return null;
  if (pooled < low || pooled > high) return null;
  return `In a hand check of ${s.checked} differing reports (${s.years.join(" and ")}, sampled on ${HAND_CHECK_DATE}), ${s.sameInFile} had the number we compared in the school’s file, so the difference came from the federal side or from how the two filings were matched, which can include our matching. ${s.ours} were on our side: one misread and one report filed for a different scope than the federal record.`;
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

/** "12:25 UTC" for a snapshot timestamp. Built by hand from the UTC fields: a locale formatter can print midnight as 24:05. */
export function formatSnapshotTime(iso: string): string {
  const d = new Date(iso);
  const two = (n: number) => String(n).padStart(2, "0");
  return `${two(d.getUTCHours())}:${two(d.getUTCMinutes())} UTC`;
}

/** The snapshot's date as `YYYY-MM-DD` (UTC): the name of its file and of its reports file, and the reports URL. */
export function snapshotDay(snapshot: { snapshot_of: string }): string {
  return new Date(snapshot.snapshot_of).toISOString().slice(0, 10);
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

/** UTF-8 byte order mark. Excel needs it to read non-ASCII text; CSV routes start the body with it. */
export const CSV_BOM = "\uFEFF";

export type QualityTableId = "reports" | "sections" | "federal" | "enrollment" | "tuition" | "totals";

export const TABLE_TITLES: Record<QualityTableId, string> = {
  reports: "Reports and fields stored",
  sections: "Fields stored and usable answers by section",
  federal: "Admissions against federal figures",
  enrollment: "Undergraduate enrollment against federal figures",
  tuition: "Tuition against federal figures",
  totals: "Do the printed totals add up?",
};

const TABLE_SLUG: Record<QualityTableId, string> = {
  reports: "reports",
  sections: "sections",
  federal: "federal-match",
  enrollment: "federal-enrollment",
  tuition: "federal-tuition",
  totals: "totals-add-up",
};

/**
 * The IPEDS table the federal tuition comes from, by data year, as tools/ipeds/mappings.py names it: the COST1 table
 * from data year 2024 on and the institutional characteristics academic-year table (IC<year>_AY) before.
 */
export function ipedsTuitionTable(dataYear: number): string {
  return dataYear >= 2024 ? `COST1_${dataYear}` : `IC${dataYear}_AY`;
}

/** True when the year has the enrollment and tuition checks (public_format 4). */
export function hasFederalChecks(year: QualityYear): boolean {
  return year.federal_checks !== undefined;
}

/** True when the year has a by-section table (public_format 3 and a form with a full field schema). */
export function hasSections(year: QualityYear): boolean {
  return (year.sections?.rows.length ?? 0) > 0;
}

/**
 * Usable answers as a whole-number share of the section's questions; null with fewer than 5 reports. Rounds half up
 * (Math.round): 12 of 32 is 38%. Only the page and its CSV compute the share; the snapshot stores the medians.
 */
export function sectionUsableShare(row: SectionRow, reports: number): number | null {
  return rowPercent(row.usable_median, row.questions, reports);
}

/** The route that serves one table for one year. */
export function qualityCsvPath(table: QualityTableId, year: string): string {
  return `/data-quality/csv/${table}/${year}`;
}

export function qualityCsvFilename(table: QualityTableId, year: string, snapshotOf: string): string {
  return `collegedata-data-quality-${TABLE_SLUG[table]}-${year}-${snapshotOf.slice(0, 10)}.csv`;
}

/** CSV of one table for one year: header, one line per format, then the year total. */
export function buildQualityCsv(table: QualityTableId, year: QualityYear): string {
  const lines: string[] = [];
  const all: { name: string; row: QualityRow }[] = [
    ...year.rows.map((r) => ({ name: formatLabel(r.format), row: r as QualityRow })),
    { name: "All formats", row: year.total },
  ];
  if (table === "reports") {
    lines.push(csvLine(["format", "published", "set_aside", "couldnt_read", "not_read_yet", "fields_stored_median", "fields_stored_lowest_10pct"]));
    for (const { name, row } of all) {
      // No published reports: nothing to take a median of. Blank, like the page's dash, not 0.
      const none = row.status.published === 0;
      lines.push(csvLine([name, row.status.published, row.status.set_aside, row.status.couldnt_read, row.status.not_read_yet, none ? "" : row.fields_stored.median, none ? "" : row.fields_stored.p10]));
    }
  } else if (table === "sections") {
    // Only a year with sections is served (the route 404s otherwise), so this is never an empty table.
    const block = year.sections!;
    lines.push(csvLine(["section", "section_name", "questions", "reports", "fields_stored_median", "usable_answers_median", "usable_share_of_questions_pct"]));
    for (const r of block.rows) {
      // No reports: nothing to take a median of. Blank, like the page's dash, not 0. Under 5 reports: no share.
      const none = block.reports === 0;
      lines.push(csvLine([r.section, SECTION_NAMES[r.section], r.questions, block.reports, none ? "" : r.stored_median, none ? "" : r.usable_median, none ? "" : sectionUsableShare(r, block.reports)]));
    }
  } else if (table === "enrollment" || table === "tuition") {
    // Only a year with the checks is served (the route 404s otherwise).
    const loaded = year.federal_checks![table].loaded;
    lines.push(csvLine(["format", "reports_checked", "matches", "no_value", "differs", "differs_over_2pct_to_10pct", "differs_over_10pct"]));
    for (const { name, row } of all) {
      const c = row.checks![table];
      // No IPEDS figures for the year: blanks, not zeros.
      lines.push(csvLine(loaded ? [name, c.reports, c.matches, c.no_value, c.differs, c.differs_2_to_10pct, c.differs_over_10pct] : [name, "", "", "", "", "", ""]));
    }
  } else if (table === "federal") {
    // The size columns exist only for a public_format 2 snapshot.
    const split = hasDifferenceSplit(year);
    lines.push(csvLine(["format", "reports_checked", "values_up_to_3_per_report", "matches", "no_value", "differs", ...(split ? ["differs_over_2pct_to_10pct", "differs_over_10pct"] : [])]));
    for (const { name, row } of all) {
      const f = row.federal;
      // No federal figures for the year: blanks, not zeros.
      lines.push(csvLine(year.federal_fall_loaded
        ? [name, f.reports, f.values, f.matches, f.no_value, f.differs, ...(split ? [f.differs_2_to_10pct, f.differs_over_10pct] : [])]
        : [name, "", "", "", "", "", ...(split ? ["", ""] : [])]));
    }
  } else {
    lines.push(csvLine(["format", "reports", "B1_adds_up", "B1_off_by_under_2pct", "B1_off_by_more", "B1_cant_check", "C1_adds_up", "C1_off_by_under_2pct", "C1_off_by_more", "C1_cant_check", "H1_adds_up", "H1_doesnt_add_up", "H1_cant_check"]));
    for (const { name, row } of all) {
      const t = row.totals;
      lines.push(csvLine([name, t.reports, t.B1.adds_up, t.B1.under_2pct, t.B1.off_more, t.B1.cant_check, t.C1.adds_up, t.C1.under_2pct, t.C1.off_more, t.C1.cant_check, t.H1.adds_up, t.H1.doesnt, t.H1.cant_check]));
    }
  }
  return lines.join("\r\n") + "\r\n";
}
