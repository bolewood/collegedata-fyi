// PRD 040 "click a cell to list its reports". The reports file (src/data/data-quality/reports/<date>.json) has one row per
// report that a count in the snapshot counts, written by `scoreboard.py --public` from the same run. This module is the
// one place that says which rows a cell lists, and the build checks that every count in the snapshot equals the rows it
// lists. Pure functions; the page loads the file on the first click, never in its own bundle.

import { formatLabel } from "./format-labels";
import type { QualitySnapshot } from "./data-quality";

/** One letter per federal outcome: matched, no usable number of ours, differs by over 2% to 10%, differs by over 10%. */
export type OutcomeCode = "m" | "n" | "s" | "l";
export type ReportStatus = "published" | "set_aside" | "couldnt_read" | "not_read_yet";

export type ReportRow = {
  id: string;
  /** Null for a document this run has no school for (a run made before manifests carried it). */
  school: string | null;
  format: string;
  status: ReportStatus;
  /** Published reports only: applied, admitted, enrolled; null where the value is not counted. */
  fed?: (OutcomeCode | null)[];
  /** B1, C1, H1 outcome names, as the snapshot names them. */
  sums?: string[];
  /** Enrollment, tuition; null where not counted. */
  checks?: (OutcomeCode | null)[];
  /** True when the school's page for this year would not exist (a school with only a blank template that year): listed, not linked. */
  nopage?: true;
};

export type ReportsFile = {
  reports_format: number;
  snapshot_of: string;
  scoreboard_run: string;
  codes: Record<string, string>;
  schools: Record<string, string>;
  years: Record<string, ReportRow[]>;
};

export const KNOWN_REPORTS_FORMATS: readonly number[] = [1];

export type CellTable = "status" | "totals" | "federal" | "enrollment" | "tuition";
/** One count cell of the page: a year's row ("total" for All formats) and a column of one table. */
export type CellRef = { table: CellTable; row: string; column: string };

const STATUSES: ReportStatus[] = ["published", "set_aside", "couldnt_read", "not_read_yet"];
const SUM_TABLES = ["B1", "C1", "H1"] as const;
const CHECKS = ["enrollment", "tuition"] as const;
const CODE_COLUMN: Record<OutcomeCode, string> = { m: "matches", n: "no_value", s: "differs_2_to_10pct", l: "differs_over_10pct" };

export class ReportsError extends Error {}

/** Shape check of a loaded reports file: the page and the build both refuse one that isn't what the producer writes. */
export function validateReports(raw: unknown, source: string): ReportsFile {
  const fail = (why: string): never => {
    throw new ReportsError(`data-quality reports ${source}: ${why}`);
  };
  if (!raw || typeof raw !== "object") return fail("not an object");
  const r = raw as Record<string, unknown>;
  if (typeof r.reports_format !== "number" || !KNOWN_REPORTS_FORMATS.includes(r.reports_format)) {
    return fail(`unknown reports_format ${JSON.stringify(r.reports_format)}`);
  }
  for (const key of ["snapshot_of", "scoreboard_run"]) if (typeof r[key] !== "string") return fail(`${key} is missing`);
  const schools = r.schools as Record<string, unknown> | undefined;
  if (!schools || typeof schools !== "object") return fail("schools is missing");
  for (const [id, name] of Object.entries(schools)) if (typeof name !== "string" || !name) return fail(`school ${id} has no name`);
  const years = r.years as Record<string, unknown> | undefined;
  if (!years || typeof years !== "object") return fail("years is missing");
  const seen = new Set<string>();
  for (const [year, rows] of Object.entries(years)) {
    if (!Array.isArray(rows)) return fail(`${year} is not a list`);
    for (const row of rows as Record<string, unknown>[]) {
      if (typeof row?.id !== "string" || typeof row.format !== "string") return fail(`${year}: a row has no id or format`);
      if (seen.has(row.id as string)) return fail(`${year}: report ${row.id} is listed twice`);
      seen.add(row.id as string);
      if (!STATUSES.includes(row.status as ReportStatus)) return fail(`${year}: ${row.id} has status ${JSON.stringify(row.status)}`);
      if (row.school !== null && (typeof row.school !== "string" || !(row.school in schools))) return fail(`${year}: ${row.id} names a school that is not in the list`);
      if (row.nopage !== undefined && (row.nopage !== true || row.school === null)) return fail(`${year}: ${row.id} has a bad nopage`);
      if (row.nopage && row.status === "published") return fail(`${year}: ${row.id} is published but has no school page`);
      const published = row.status === "published";
      for (const key of ["fed", "sums", "checks"]) {
        if (published !== (row[key] !== undefined)) return fail(`${year}: ${row.id} must have ${key} exactly when it is published`);
      }
      if (published) {
        const codes = ["m", "n", "s", "l", null];
        if (!Array.isArray(row.fed) || row.fed.length !== 3 || !row.fed.every((c) => codes.includes(c as string | null))) return fail(`${year}: ${row.id} has a bad fed`);
        if (!Array.isArray(row.checks) || row.checks.length !== 2 || !row.checks.every((c) => codes.includes(c as string | null))) return fail(`${year}: ${row.id} has a bad checks`);
        if (!Array.isArray(row.sums) || row.sums.length !== 3 || !row.sums.every((c) => typeof c === "string")) return fail(`${year}: ${row.id} has a bad sums`);
      }
    }
  }
  return raw as ReportsFile;
}

// ── Which rows a cell lists ───────────────────────────────────────

/** How many of the cell's counts this report holds: 0 means it is not listed. Federal cells count values, so a report can hold up to 3. */
export function cellWeight(r: ReportRow, cell: CellRef): number {
  if (cell.row !== "total" && cell.row !== r.format) return 0;
  const { table, column } = cell;
  if (table === "status") return r.status === column ? 1 : 0;
  if (r.status !== "published") return 0;
  if (table === "totals") {
    if (column === "reports") return 1;
    const [which, outcome] = column.split(".");
    return r.sums![SUM_TABLES.indexOf(which as (typeof SUM_TABLES)[number])] === outcome ? 1 : 0;
  }
  const codes = (table === "federal" ? r.fed! : [r.checks![CHECKS.indexOf(table)]]).filter((c): c is OutcomeCode => !!c);
  if (column === "reports") return codes.length > 0 ? 1 : 0;
  if (column === "values") return codes.length;
  if (column === "differs") return codes.filter((c) => c === "s" || c === "l").length;
  return codes.filter((c) => CODE_COLUMN[c] === column).length;
}

export function cellRows(reports: ReportsFile, year: string, cell: CellRef): { row: ReportRow; weight: number }[] {
  return (reports.years[year] ?? []).flatMap((row) => {
    const weight = cellWeight(row, cell);
    return weight > 0 ? [{ row, weight }] : [];
  });
}

export function cellCount(reports: ReportsFile, year: string, cell: CellRef): number {
  return cellRows(reports, year, cell).reduce((n, x) => n + x.weight, 0);
}

/** Every count cell the snapshot holds, with its count: Tables A, B, B2 (when present) and C, for every year and row. */
export function snapshotCells(snapshot: QualitySnapshot): { year: string; cell: CellRef; count: number }[] {
  const out: { year: string; cell: CellRef; count: number }[] = [];
  for (const y of snapshot.years) {
    const blocks = [...y.rows.map((r) => ({ key: r.format, r })), { key: "total", r: y.total }];
    for (const { key, r } of blocks) {
      const add = (table: CellTable, column: string, count: number) => out.push({ year: y.cds_year, cell: { table, row: key, column }, count });
      for (const s of STATUSES) add("status", s, r.status[s]);
      add("totals", "reports", r.totals.reports);
      for (const t of SUM_TABLES) for (const [outcome, n] of Object.entries(r.totals[t])) add("totals", `${t}.${outcome}`, n);
      for (const [column, n] of Object.entries(r.federal)) add("federal", column, n as number);
      for (const name of CHECKS) if (r.checks) for (const [column, n] of Object.entries(r.checks[name])) add(name, column, n);
    }
  }
  return out;
}

/** Cells where the snapshot's count is not the number of rows listed (empty when the file agrees); also names rows no cell lists. */
export function reportsAgreementProblems(snapshot: QualitySnapshot, reports: ReportsFile): string[] {
  const problems: string[] = [];
  if (reports.snapshot_of !== snapshot.snapshot_of || reports.scoreboard_run !== snapshot.scoreboard_run) {
    problems.push("the reports file is not from the same run as the snapshot");
  }
  for (const { year, cell, count } of snapshotCells(snapshot)) {
    const listed = cellCount(reports, year, cell);
    if (listed !== count) problems.push(`${year} ${cell.row} ${cell.table}.${cell.column}: the snapshot counts ${count}, the file lists ${listed}`);
  }
  for (const year of Object.keys(reports.years)) {
    if (!snapshot.years.some((y) => y.cds_year === year)) problems.push(`${year}: the reports file has a year the snapshot lacks`);
  }
  return problems;
}

// ── Words ─────────────────────────────────────────────────────────

const SUM_WORDS: Record<string, string> = { B1: "enrollment", C1: "admissions", H1: "financial aid" };
/** B1 and C1 are "totals" (plural); H1 is one "table". */
const TOTALS_OUTCOME: Record<string, string> = {
  adds_up: "add up",
  under_2pct: "are off by under 2%",
  off_more: "are off by more",
  cant_check: "can’t be checked",
};
const TABLE_OUTCOME: Record<string, string> = { adds_up: "adds up", doesnt: "doesn’t add up", cant_check: "can’t be checked" };
const CHECK_WORDS: Record<string, string> = { enrollment: "undergraduate enrollment", tuition: "tuition" };
const CODE_WORDS: Record<OutcomeCode, string> = { m: "matches", n: "no value", s: "differs by over 2% to 10%", l: "differs by over 10%" };
const STATUS_WORDS: Record<string, string> = {
  published: "published",
  set_aside: "set aside",
  couldnt_read: "that couldn’t be read",
  not_read_yet: "not read yet",
};

/** The cell's meaning, as a phrase that follows "the 46 standard PDF reports" (or "values", "checks"); `one` is for a count of 1. */
export function cellPhrase(cell: CellRef, one = false): string {
  const { table, column } = cell;
  if (table === "status") return STATUS_WORDS[column];
  if (table === "totals") {
    if (column === "reports") return "published";
    const [which, outcome] = column.split(".");
    return which === "H1"
      ? `where the financial aid table ${TABLE_OUTCOME[outcome]}`
      : `where the ${SUM_WORDS[which]} totals ${TOTALS_OUTCOME[outcome]}`;
  }
  const subject = `${table === "federal" ? "admissions" : CHECK_WORDS[table]} ${one ? "value" : "values"}`;
  const what: Record<string, string> = {
    values: "compared with the federal figure",
    matches: one ? "that matches the federal figure" : "that match the federal figure",
    no_value: "with no usable number of ours",
    differs: one ? "that differs from the federal figure" : "that differ from the federal figure",
    differs_2_to_10pct: one ? "that differs by over 2% to 10%" : "that differ by over 2% to 10%",
    differs_over_10pct: one ? "that differs by over 10%" : "that differ by over 10%",
  };
  return column === "reports"
    ? `checked against federal ${table === "federal" ? "admissions figures" : `${CHECK_WORDS[table]} figures`}`
    : `${subject} ${what[column]}`;
}

/** Accessible name of a count button, e.g. "List the 46 standard PDF reports where the financial aid table adds up (2023-24)". */
export function cellLabel(cell: CellRef, year: string, count: number): string {
  return `List the ${cellTitle(cell, year, count)}`;
}

/** The cell's list, as a heading would say it: "46 standard PDF reports where the financial aid table adds up (2023-24)". */
export function cellTitle(cell: CellRef, year: string, count: number): string {
  const one = count === 1;
  const whoIn = (plural: boolean) => (cell.row === "total" ? `${plural ? "reports" : "report"} in all formats` : `${formatLabel(cell.row)} ${plural ? "reports" : "report"}`);
  const who = whoIn(!one);
  const n = count.toLocaleString("en-US");
  const where = ` (${year})`;
  if (cell.table === "status") return `${n} ${who} ${STATUS_WORDS[cell.column]}${where}`;
  if (cell.table === "totals" || cell.column === "reports") return `${n} ${who} ${cellPhrase(cell, one)}${where}`;
  // A count of values is "from reports": the one value still comes from a category of reports.
  return `${n} ${cellPhrase(cell, one)}, from ${whoIn(true)}${where}`;
}

/** What a listed report held for the cell's table, in words ("applied: matches; admitted: differs by over 10%"). */
export function rowDetail(row: ReportRow, cell: CellRef): string | null {
  if (row.status !== "published") return null;
  if (cell.table === "federal") {
    const names = ["applied", "admitted", "enrolled"];
    return row.fed!.map((c, i) => (c ? `${names[i]}: ${CODE_WORDS[c]}` : null)).filter(Boolean).join("; ");
  }
  if (cell.table === "enrollment" || cell.table === "tuition") {
    const c = row.checks![CHECKS.indexOf(cell.table)];
    return c ? CODE_WORDS[c] : null;
  }
  return null;
}

export function schoolHref(school: string, year: string): string {
  return `/schools/${school}/${year}`;
}
