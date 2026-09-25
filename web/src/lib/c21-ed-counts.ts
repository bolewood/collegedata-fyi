// CDS C21 early-decision counts. Modern templates print applications
// received and admits; they do not print early-action counts (C22 is
// offered / restrictive / dates only). So a second series on the
// acceptance-rate page is early decision, never inferred REA/EA.

import { c1TemplateForArtifact, fieldNumber } from "./c1-headline-totals";
import { C21_NEXT_SECTION } from "./c21-ed-note";
import type { FieldValue } from "./types";

export type C21Counts = { applied: number; admitted: number; rate: number };

const APPLIED_LABEL = /number of early decision applications received by your institution:?/i;
const ADMITTED_LABEL = /number of applicants admitted under early decision plan:?/i;
const DETAILS_OR_NEXT =
  /please provide significant details about your early decision plan|number enrolled under early decision plan/i;

function c21CountIds(yearStart: number | null | undefined): { applied: string; admitted: string }[] {
  // 2025-26 inserted extra date parts at C.2106–C.2109, so counts live at
  // C.2110 / C.2111. Older templates keep counts at C.2106 / C.2107.
  // Prefer the pair that matches the report year; on pre-2025 files also
  // try the 2025-26 ids, in case the cleaner indexed the current schema.
  if (yearStart != null && yearStart >= 2025) {
    return [{ applied: "C.2110", admitted: "C.2111" }];
  }
  return [
    { applied: "C.2106", admitted: "C.2107" },
    { applied: "C.2110", admitted: "C.2111" },
  ];
}

function integers(text: string): number[] {
  const out: number[] = [];
  for (const match of text.matchAll(/\b(\d{1,3}(?:,\d{3})+|\d{2,})\b/g)) {
    const n = Number(match[1].replace(/,/g, ""));
    if (Number.isFinite(n) && n >= 20) out.push(n);
  }
  return out;
}

function sliceUntil(text: string, stop: RegExp): string {
  const at = text.search(stop);
  return at >= 0 ? text.slice(0, at) : text;
}

/**
 * Counts printed next to the C21 labels in markdown, when the cleaner left
 * the fields empty. Two numbers after both labels (Lafayette 2023-24,
 * Duke 2023-24) are applied then admitted.
 */
export function c21MarkdownCounts(markdown: string | null | undefined): C21Counts | null {
  if (!markdown) return null;
  const appliedAt = APPLIED_LABEL.exec(markdown);
  const admittedAt = ADMITTED_LABEL.exec(markdown);
  if (!appliedAt || !admittedAt || appliedAt.index == null || admittedAt.index == null) return null;

  const afterApplied = markdown.slice(appliedAt.index + appliedAt[0].length);
  const afterAdmitted = markdown.slice(admittedAt.index + admittedAt[0].length);
  const appliedSlice = sliceUntil(afterApplied, ADMITTED_LABEL);
  const admittedSlice = sliceUntil(sliceUntil(afterAdmitted, DETAILS_OR_NEXT), C21_NEXT_SECTION);

  const appliedOwn = integers(appliedSlice)[0] ?? null;
  const admittedOwn = integers(admittedSlice)[0] ?? null;
  if (appliedOwn != null && admittedOwn != null) {
    return saneEdCounts(appliedOwn, admittedOwn);
  }

  const pair = integers(admittedSlice);
  if (appliedOwn == null && pair.length >= 2) return saneEdCounts(pair[0], pair[1]);
  return null;
}

export function readC21Counts(extract: {
  values: Record<string, FieldValue>;
  schemaVersion?: string | null;
  producer?: string | null;
  yearStart?: number | null;
  markdown?: string | null;
}): C21Counts | null {
  const resolved = c1TemplateForArtifact({
    schemaVersion: extract.schemaVersion,
    producer: extract.producer,
    yearStart: extract.yearStart,
  });
  if (!resolved.template) return null;
  for (const ids of c21CountIds(extract.yearStart)) {
    const counts = saneEdCounts(
      fieldNumber(extract.values, ids.applied),
      fieldNumber(extract.values, ids.admitted),
    );
    if (counts) return counts;
  }
  return c21MarkdownCounts(extract.markdown);
}

export function saneEdCounts(
  applied: number | null | undefined,
  admitted: number | null | undefined,
  overallAdmitted?: number | null,
): C21Counts | null {
  if (applied == null || applied <= 0) return null;
  if (admitted == null || admitted <= 0) return null;
  if (admitted > applied) return null;
  // A 1–9 admit count against a large pool is the C21 date-part leak
  // (month/day written into C.2106/C.2107), not a real early-decision class.
  if (admitted < 10 && applied >= 200) return null;
  if (overallAdmitted != null && overallAdmitted > 0 && admitted > overallAdmitted) return null;
  return { applied, admitted, rate: admitted / applied };
}
