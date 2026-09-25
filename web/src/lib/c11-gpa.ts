// CDS C11 GPA bands and C12 average. PRD 014 treats these IDs as
// DirectAlias across years; the year-aware choice is which C11 column
// to read. The 2023-24+ template has three identical 10-row blocks:
// score-submitters (C.1101–C.1110), non-submitters (C.1111–C.1120),
// and all enrolled who reported a GPA (C.1121–C.1130). Older files
// print a single table at C.1101–C.1110. The page answers with all
// enrolled when that column is usable; otherwise the single/reported
// table. Non-submitters are never the answer.

import {
  ACCEPTANCE_LATEST_MIN_YEAR_START,
  ACCEPTANCE_MIN_USABLE_YEARS,
  academicYearLabel,
  academicYearStart,
  isHistoryCandidate,
  type Eligibility,
  type HistoryDocument,
  type HistoryExtract,
} from "./acceptance-history";
import { fieldNumber } from "./c1-headline-totals";
import type { FieldValue } from "./types";

export const GPA_BANDS = [
  { key: "gpa4", label: "4.0", pattern: /percent who had gpa of 4\.0(?!\d)/i },
  { key: "gpa375", label: "3.75–3.99", pattern: /percent who had gpa between 3\.75 and 3\.99/i },
  { key: "gpa350", label: "3.50–3.74", pattern: /percent who had gpa between 3\.50 and 3\.74/i },
  { key: "gpa325", label: "3.25–3.49", pattern: /percent who had gpa between 3\.25 and 3\.49/i },
  { key: "gpa300", label: "3.00–3.24", pattern: /percent who had gpa between 3\.00 and 3\.24/i },
  { key: "gpa250", label: "2.50–2.99", pattern: /percent who had gpa between 2\.50 and 2\.99/i },
  { key: "gpa200", label: "2.00–2.49", pattern: /percent who had gpa between 2\.0 and 2\.49/i },
  { key: "gpa100", label: "1.00–1.99", pattern: /percent who had gpa between 1\.0 and 1\.99/i },
  { key: "below1", label: "below 1.0", pattern: /percent who had gpa below 1\.0/i },
] as const;

export type GpaBandKey = (typeof GPA_BANDS)[number]["key"];
export type GpaColumn = "all-enrolled" | "reported";

export type GpaBands = {
  column: GpaColumn;
  percents: Record<GpaBandKey, number>;
  sum: number;
};

export type GpaReading = {
  bands: GpaBands;
  average: number | null;
  submittedPct: number | null;
};

const ALL_ENROLLED_OFFSET = 21; // C.1121
const REPORTED_OFFSET = 1; // C.1101
const C12_NEXT =
  /(?:^|\n)\s*(?:#{1,3}\s*)?(?:[-*]\s*)?(?:c13|c13-c20|application fee|admission policies)\b/i;

function bandId(offset: number, index: number): string {
  return `C.11${String(offset + index).padStart(2, "0")}`;
}

/** Percents, 0–100. A whole column of 0–1 values is treated as fractions. */
export function asPercent(n: number | null | undefined, asFraction: boolean): number | null {
  if (n == null || !Number.isFinite(n) || n < 0) return null;
  const scaled = asFraction ? n * 100 : n;
  if (scaled > 100.5) return null;
  return scaled;
}

function columnAsFractions(raw: (number | null)[]): boolean {
  const present = raw.filter((n): n is number => n != null);
  return present.length > 0 && present.every((n) => n <= 1);
}

/** Printed C12 average on a 4.0 (sometimes weighted 5.0) scale. */
export function saneAverage(n: number | null | undefined): number | null {
  if (n == null || !Number.isFinite(n)) return null;
  if (n >= 2 && n <= 5) return n;
  if (n >= 20 && n <= 50) return n / 10;
  if (n >= 200 && n <= 500) return n / 100;
  return null;
}

export function saneSubmittedPct(n: number | null | undefined): number | null {
  if (n == null || !Number.isFinite(n) || n < 0) return null;
  if (n <= 1) return n * 100;
  if (n > 100.5) return null;
  return n;
}

function readColumn(
  values: Record<string, FieldValue>,
  offset: number,
): Record<GpaBandKey, number> | null {
  const raw = GPA_BANDS.map((_, i) => fieldNumber(values, bandId(offset, i)));
  if (raw.every((n) => n == null)) return null;
  const asFraction = columnAsFractions(raw);
  const percents = {} as Record<GpaBandKey, number>;
  for (let i = 0; i < GPA_BANDS.length; i++) {
    percents[GPA_BANDS[i].key] = asPercent(raw[i], asFraction) ?? 0;
  }
  return percents;
}

export function saneBands(
  percents: Record<GpaBandKey, number> | null | undefined,
  column: GpaColumn,
): GpaBands | null {
  if (!percents) return null;
  let filled = 0;
  let sum = 0;
  for (const band of GPA_BANDS) {
    const n = percents[band.key];
    if (n == null || n < 0 || n > 100.5) return null;
    if (n > 0) filled += 1;
    sum += n;
  }
  if (filled === 0) return null;
  if (sum < 95 || sum > 105) return null;
  return { column, percents, sum };
}

function percentsFromNumbers(nums: number[]): Record<GpaBandKey, number> | null {
  if (nums.length < GPA_BANDS.length) return null;
  const asFraction = columnAsFractions(nums);
  const percents = {} as Record<GpaBandKey, number>;
  for (let i = 0; i < GPA_BANDS.length; i++) {
    const pct = asPercent(nums[i], asFraction);
    if (pct == null) return null;
    percents[GPA_BANDS[i].key] = pct;
  }
  return percents;
}

function numbersAfter(text: string, start: number, stop: number): number[] {
  const slice = text.slice(start, stop);
  const out: number[] = [];
  for (const match of slice.matchAll(/\b(\d{1,3}(?:\.\d+)?)\s*%?/g)) {
    const n = Number(match[1]);
    if (Number.isFinite(n) && n <= 100.5) out.push(n);
  }
  return out;
}

function columnFromRow(nums: number[]): number | null {
  if (nums.length === 0) return null;
  // Three-column C11: submitters / non-submitters / all enrolled.
  if (nums.length >= 3) return nums[2];
  return nums[0];
}

/**
 * Band percents printed next to the C11 labels in markdown, when the
 * cleaner left the fields empty. Prefers the last number on a three-column
 * row (all enrolled).
 */
export function c11MarkdownBands(markdown: string | null | undefined): GpaBands | null {
  if (!markdown) return null;
  const first = /percent who had gpa of 4\.0/i.exec(markdown);
  if (!first || first.index == null) return null;
  const from = first.index;
  const c12 = markdown.slice(from).search(/average high school gpa of all degree-seeking|c12\b/i);
  const region = markdown.slice(from, c12 >= 0 ? from + c12 : from + 4000);
  const picks: number[] = [];
  for (let i = 0; i < GPA_BANDS.length; i++) {
    const match = GPA_BANDS[i].pattern.exec(region);
    if (!match || match.index == null) return null;
    const next = i + 1 < GPA_BANDS.length ? GPA_BANDS[i + 1].pattern.exec(region) : null;
    const stop = next && next.index != null ? next.index : Math.min(region.length, match.index + 180);
    const n = columnFromRow(numbersAfter(region, match.index + match[0].length, stop));
    if (n == null) return null;
    picks.push(n);
  }
  const threeColumn = GPA_BANDS.every((_, i) => {
    const match = GPA_BANDS[i].pattern.exec(region);
    if (!match || match.index == null) return false;
    const next = i + 1 < GPA_BANDS.length ? GPA_BANDS[i + 1].pattern.exec(region) : null;
    const stop = next && next.index != null ? next.index : Math.min(region.length, match.index + 180);
    return numbersAfter(region, match.index + match[0].length, stop).length >= 3;
  });
  const column: GpaColumn = threeColumn ? "all-enrolled" : "reported";
  return saneBands(percentsFromNumbers(picks), column);
}

function firstNumber(text: string): number | null {
  const match = /\b(\d(?:\.\d{1,3})?|\d{2,3}(?:\.\d+)?)\b/.exec(text);
  if (!match) return null;
  return Number(match[1]);
}

export function c12MarkdownAverage(markdown: string | null | undefined): number | null {
  if (!markdown) return null;
  const match = /average high school gpa of all degree-seeking[^\n|]{0,160}/i.exec(markdown);
  if (!match || match.index == null) return null;
  const rest = markdown.slice(match.index + match[0].length);
  const end = rest.search(C12_NEXT);
  return saneAverage(firstNumber(end >= 0 ? rest.slice(0, end) : rest.slice(0, 80)));
}

export function c12MarkdownSubmitted(markdown: string | null | undefined): number | null {
  if (!markdown) return null;
  const match = /percent of total first-time, first-year students who submitted high school gpa/i.exec(
    markdown,
  );
  if (!match || match.index == null) return null;
  const rest = markdown.slice(match.index + match[0].length);
  const end = rest.search(C12_NEXT);
  return saneSubmittedPct(firstNumber(end >= 0 ? rest.slice(0, end) : rest.slice(0, 80)));
}

export function readC11Gpa(extract: {
  values: Record<string, FieldValue>;
  markdown?: string | null;
}): GpaReading | null {
  const allEnrolled = saneBands(readColumn(extract.values, ALL_ENROLLED_OFFSET), "all-enrolled");
  const reported = saneBands(readColumn(extract.values, REPORTED_OFFSET), "reported");
  const bands = allEnrolled ?? reported ?? c11MarkdownBands(extract.markdown);
  if (!bands) return null;
  const average =
    saneAverage(fieldNumber(extract.values, "C.1201")) ?? c12MarkdownAverage(extract.markdown);
  const submittedRaw =
    saneSubmittedPct(fieldNumber(extract.values, "C.1202")) ?? c12MarkdownSubmitted(extract.markdown);
  // A 1–9 "percent submitted" next to a full C11 table is a date-part or
  // column leak, not a class that almost no one reported a GPA for.
  const submittedPct = submittedRaw != null && submittedRaw < 25 ? null : submittedRaw;
  return { bands, average, submittedPct };
}

export type GpaYear = {
  year: string;
  yearStart: number;
  documentId: string;
  sourceStoragePath: string | null;
  sourceFormat: string | null;
  bands: GpaBands;
  average: number | null;
  submittedPct: number | null;
};

export type GpaHistory = {
  years: GpaYear[];
  gaps: string[];
  excluded: { year: string; documentId: string; reason: string }[];
};

export function buildGpaHistory(
  candidates: { doc: HistoryDocument; extract: HistoryExtract | null }[],
): GpaHistory {
  const byYear = new Map<string, GpaYear>();
  const excluded: GpaHistory["excluded"] = [];
  for (const { doc, extract } of candidates) {
    if (!isHistoryCandidate(doc) || !doc.canonical_year || !doc.document_id) continue;
    if (byYear.has(doc.canonical_year)) continue;
    const yearStart = academicYearStart(doc.canonical_year);
    if (yearStart == null) continue;
    const reading = extract ? readC11Gpa(extract) : null;
    if (!reading) {
      excluded.push({
        year: doc.canonical_year,
        documentId: doc.document_id,
        reason: extract ? "no usable C11 bands" : "no extract",
      });
      continue;
    }
    byYear.set(doc.canonical_year, {
      year: doc.canonical_year,
      yearStart,
      documentId: doc.document_id,
      sourceStoragePath: doc.source_storage_path,
      sourceFormat: doc.source_format,
      ...reading,
    });
  }
  const years = Array.from(byYear.values()).sort((a, b) => b.yearStart - a.yearStart);
  const gaps: string[] = [];
  if (years.length > 1) {
    const have = new Set(years.map((row) => row.yearStart));
    for (let start = years[0].yearStart - 1; start > years[years.length - 1].yearStart; start--) {
      if (!have.has(start)) gaps.push(academicYearLabel(start));
    }
  }
  return {
    years,
    gaps,
    excluded: excluded.filter((row) => !byYear.has(row.year)),
  };
}

export function gpaEligibility(history: GpaHistory): Eligibility {
  if (history.years.length < ACCEPTANCE_MIN_USABLE_YEARS) {
    return { eligible: false, reason: `fewer than ${ACCEPTANCE_MIN_USABLE_YEARS} usable GPA years` };
  }
  if (history.years[0].yearStart < ACCEPTANCE_LATEST_MIN_YEAR_START) {
    return { eligible: false, reason: "latest usable GPA year is older than 2023-24" };
  }
  return { eligible: true };
}
