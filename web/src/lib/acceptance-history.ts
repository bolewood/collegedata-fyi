// PRD 031 M0-lite: first-year acceptance history read from each year's
// extract. The browser tables only hold 2024-25 onward, so older years come
// from the extract values through the year-aware C1 mapping in
// c1-headline-totals. A year is shown only when its mapping is known and its
// counts pass the sanity checks below; nothing is estimated.

import { readC1Totals, type C1Template } from "./c1-headline-totals";
import type { FieldValue, ManifestRow } from "./types";

export const ACCEPTANCE_MIN_USABLE_YEARS = 3;
export const ACCEPTANCE_LATEST_MIN_YEAR_START = 2023;
/** Oldest year whose C1 mapping has been checked against source files. */
export const ACCEPTANCE_HISTORY_MIN_YEAR_START = 2018;

const HIDDEN_FLAGS = new Set(["wrong_file", "blank_template", "low_coverage"]);

export type HistoryDocument = Pick<
  ManifestRow,
  | "document_id"
  | "canonical_year"
  | "extraction_status"
  | "data_quality_flag"
  | "sub_institutional"
  | "source_storage_path"
  | "source_format"
>;

export type HistoryExtract = {
  values: Record<string, FieldValue>;
  schemaVersion: string | null;
  producer: string | null;
  markdown?: string | null;
};

export type AcceptanceYear = {
  year: string;
  yearStart: number;
  documentId: string;
  sourceStoragePath: string | null;
  sourceFormat: string | null;
  /** Where the counts came from: the projected browser row, or the extract read with this C1 numbering. */
  source: "projection" | C1Template;
  applied: number;
  admitted: number;
  enrolled: number | null;
  rate: number;
  yieldRate: number | null;
};

export type ExcludedYear = {
  year: string;
  documentId: string;
  reason: string;
};

export type AcceptanceHistory = {
  /** Usable years, newest first, one per academic year. */
  years: AcceptanceYear[];
  /** Years between the first and last usable year with no usable row, newest first. */
  gaps: string[];
  /** Documents considered and rejected, for the validation report. */
  excluded: ExcludedYear[];
};

/** "2025-26" → 2025 when the two halves are consecutive years. */
export function academicYearStart(year: string | null | undefined): number | null {
  const match = /^(\d{4})-(\d{2})$/.exec(year ?? "");
  if (!match) return null;
  const start = Number(match[1]);
  return Number(match[2]) === (start + 1) % 100 ? start : null;
}

export function academicYearLabel(start: number): string {
  return `${start}-${String((start + 1) % 100).padStart(2, "0")}`;
}

/** Whole-institution, extracted, canonical-year, not quality-flagged, in the checked window. */
export function isHistoryCandidate(doc: HistoryDocument): boolean {
  const start = academicYearStart(doc.canonical_year);
  return (
    Boolean(doc.document_id) &&
    doc.extraction_status === "extracted" &&
    doc.sub_institutional == null &&
    start != null &&
    start >= ACCEPTANCE_HISTORY_MIN_YEAR_START &&
    !HIDDEN_FLAGS.has(doc.data_quality_flag ?? "")
  );
}

export type YearReading =
  | { ok: true; row: AcceptanceYear }
  | { ok: false; reason: string };

type Counts = { applied: number; admitted: number; enrolled: number | null };

type ExtractReading =
  | { ok: true; counts: Counts; template: C1Template }
  | { ok: false; reason: string };

function readExtract(extract: HistoryExtract | null, yearStart: number): ExtractReading {
  if (!extract) return { ok: false, reason: "no extract" };
  const reading = readC1Totals({ ...extract, yearStart });
  if (!reading.template) return { ok: false, reason: reading.reason };
  const { applied, admitted, enrolled } = reading.totals;
  if (applied == null || applied <= 0) return { ok: false, reason: "no reliable applicant count" };
  if (admitted == null || admitted <= 0) return { ok: false, reason: "no reliable admitted count" };
  return {
    ok: true,
    counts: { applied, admitted, enrolled: enrolled != null && enrolled > 0 ? enrolled : null },
    template: reading.template,
  };
}

/** First year the browser projection (and so the hub sentence) covers. */
export const BROWSER_FACTS_MIN_YEAR_START = 2024;

/** The projected row the hub sentence reads, for the same document. */
export type BrowserCounts = {
  applied: number | null;
  admitted: number | null;
  enrolled: number | null;
};

function saneBrowserCounts(browser: BrowserCounts | null | undefined): browser is BrowserCounts & {
  applied: number;
  admitted: number;
} {
  return (
    browser != null &&
    browser.applied != null &&
    browser.applied > 0 &&
    browser.admitted != null &&
    browser.admitted > 0 &&
    browser.admitted <= browser.applied
  );
}

/**
 * Read one document's C1 counts and apply the sanity checks. The
 * extract's reading of the school's printed C1 table wins; from 2024-25 on,
 * a sane projected row is the fallback when the extract can't be read, and
 * fills an enrolled count the extract lacks. Disagreements are listed in
 * docs/prd/assets/031/m0-lite-validation.md.
 */
export function readAcceptanceYear(
  doc: HistoryDocument,
  extract: HistoryExtract | null,
  browser?: BrowserCounts | null,
): YearReading {
  const yearStart = academicYearStart(doc.canonical_year);
  if (!isHistoryCandidate(doc) || yearStart == null || !doc.document_id || !doc.canonical_year) {
    return { ok: false, reason: "not a whole-institution extracted report" };
  }

  const reading = readExtract(extract, yearStart);
  let counts: Counts;
  let source: AcceptanceYear["source"];
  if (reading.ok) {
    // The school's printed C1 counts (validated extract) are the source of
    // truth; the projection only fills an enrolled count the extract lacks.
    const enrolled = reading.counts.enrolled ??
      (yearStart >= BROWSER_FACTS_MIN_YEAR_START && saneBrowserCounts(browser) && browser.enrolled != null && browser.enrolled > 0
        ? browser.enrolled
        : null);
    counts = { ...reading.counts, enrolled };
    source = reading.template;
  } else if (yearStart >= BROWSER_FACTS_MIN_YEAR_START && saneBrowserCounts(browser)) {
    counts = {
      applied: browser.applied,
      admitted: browser.admitted,
      enrolled: browser.enrolled != null && browser.enrolled > 0 ? browser.enrolled : null,
    };
    source = "projection";
  } else {
    return reading;
  }

  const { applied, admitted, enrolled } = counts;
  if (admitted > applied) return { ok: false, reason: "admitted exceeds applied" };
  if (enrolled != null && enrolled > admitted) {
    return { ok: false, reason: "enrolled exceeds admitted" };
  }

  return {
    ok: true,
    row: {
      year: doc.canonical_year,
      yearStart,
      documentId: doc.document_id,
      sourceStoragePath: doc.source_storage_path,
      sourceFormat: doc.source_format,
      source,
      applied,
      admitted,
      enrolled,
      rate: admitted / applied,
      yieldRate: enrolled != null ? enrolled / admitted : null,
    },
  };
}

/**
 * Candidates arrive in the order the school pages list documents (newest
 * first, the year page's first document first). The first usable document
 * for a year wins.
 */
export function buildAcceptanceHistory(
  candidates: { doc: HistoryDocument; extract: HistoryExtract | null }[],
  browserByDocument: ReadonlyMap<string, BrowserCounts> = new Map(),
): AcceptanceHistory {
  const byYear = new Map<string, AcceptanceYear>();
  const excluded: ExcludedYear[] = [];
  for (const { doc, extract } of candidates) {
    if (!isHistoryCandidate(doc) || !doc.canonical_year || !doc.document_id) continue;
    if (byYear.has(doc.canonical_year)) continue;
    const reading = readAcceptanceYear(doc, extract, browserByDocument.get(doc.document_id));
    if (reading.ok) {
      byYear.set(doc.canonical_year, reading.row);
    } else {
      excluded.push({ year: doc.canonical_year, documentId: doc.document_id, reason: reading.reason });
    }
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

export type Eligibility = { eligible: true } | { eligible: false; reason: string };

export function acceptanceEligibility(history: AcceptanceHistory): Eligibility {
  if (history.years.length < ACCEPTANCE_MIN_USABLE_YEARS) {
    return { eligible: false, reason: `fewer than ${ACCEPTANCE_MIN_USABLE_YEARS} usable years` };
  }
  if (history.years[0].yearStart < ACCEPTANCE_LATEST_MIN_YEAR_START) {
    return { eligible: false, reason: "latest usable year is older than 2023-24" };
  }
  return { eligible: true };
}
