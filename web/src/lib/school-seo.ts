// SEO title/description builders and compact key-facts helpers for school
// hub (/schools/{id}) and year (/schools/{id}/{year}) pages (#518).
//
// Hub pages own un-yeared "{school} common data set" queries (archive span,
// federal context, and downloads). Year pages own year-specific queries and
// AI-answer SERP citations (year + headline number + quotable key facts).

import { TITLE_MAX, DESCRIPTION_MAX } from "./acceptance-rate-copy";
import { yearRange } from "./format";
import {
  acceptanceRateOf,
  actRangeOf,
  longYear,
  metaFactFragment,
  satRangeOf,
  share,
  usableFacts,
  type SchoolYearFacts,
} from "./school-summary";

export { TITLE_MAX, DESCRIPTION_MAX };

function pickWithin(candidates: string[], max: number): string {
  return candidates.find((candidate) => candidate.length <= max) ?? candidates[candidates.length - 1];
}

function formatCount(n: number): string {
  return n.toLocaleString("en-US");
}

/** Hub `<title>`: cleanly un-yeared so it never competes with `/2025-26`. */
export function hubMetadataTitle(schoolName: string): string {
  return `${schoolName} Common Data Set`;
}

/**
 * Hub `<meta name="description">`: archive-level scope, federal context, and
 * original files — deliberately distinct from the year page's `metaFactFragment`.
 */
export function hubMetadataDescription({
  schoolName,
  years,
}: {
  schoolName: string;
  years: string[];
}): string {
  const unique = Array.from(new Set(years)).sort();
  if (unique.length >= 2) {
    const range = yearRange(unique[0], unique[unique.length - 1]);
    const latest = unique[unique.length - 1];
    return pickWithin(
      [
        `${schoolName} Common Data Set (${unique.length} years, ${range}): every archived report, latest ${latest} highlights, federal debt and earnings, and original files.`,
        `${schoolName} Common Data Set (${unique.length} years, ${range}): archived reports, federal debt and earnings, and original files to download.`,
        `${schoolName} Common Data Set (${range}): archived reports, federal outcomes, and original files to download.`,
        `${schoolName} Common Data Set (${range}): archived reports and original files.`,
      ],
      DESCRIPTION_MAX,
    );
  }
  if (unique.length === 1) {
    const only = unique[0];
    return pickWithin(
      [
        `${schoolName} Common Data Set (${only} on file): admissions, cost, and aid alongside federal debt and earnings data, with the original file to download.`,
        `${schoolName} Common Data Set (${only} on file): admissions, cost, aid, federal outcomes, and the original file.`,
        `${schoolName} Common Data Set (${only}): published school report and original file.`,
      ],
      DESCRIPTION_MAX,
    );
  }
  return pickWithin(
    [
      `${schoolName} Common Data Set archive: published school reports alongside federal debt and earnings data, with original files to download.`,
      `${schoolName} Common Data Set archive: published school reports and federal outcomes.`,
    ],
    DESCRIPTION_MAX,
  );
}

/**
 * Year `<title>`: leads with year + headline figure when it fits within
 * TITLE_MAX (65 chars), never inventing a school nickname.
 */
export function yearMetadataTitle({
  schoolName,
  year,
  facts,
}: {
  schoolName: string;
  year: string;
  facts?: SchoolYearFacts | null;
}): string {
  const base = `${schoolName} Common Data Set ${year}`;
  if (!usableFacts(facts)) return base;

  const rate = acceptanceRateOf(facts);
  const sat = satRangeOf(facts);
  const candidates: string[] = [];

  if (rate != null && facts.applied != null && facts.applied > 0) {
    candidates.push(`${base}: ${share(rate)} admit rate, ${formatCount(facts.applied)} applicants`);
  }
  if (rate != null) {
    candidates.push(`${base}: ${share(rate)} admit rate`);
  }
  if (rate == null && sat) {
    candidates.push(`${base}: SAT ${sat}`);
  }
  candidates.push(base);

  return pickWithin(candidates, TITLE_MAX);
}

/**
 * Year `<meta name="description">`: leads with the specific CDS year and its
 * headline numbers, plus a pointer to the original file.
 */
export function yearMetadataDescription({
  schoolName,
  year,
  facts,
}: {
  schoolName: string;
  year: string;
  facts?: SchoolYearFacts | null;
}): string {
  const printedYear = longYear(year);
  const yearLabel = printedYear ? `${year} (${printedYear})` : year;
  const fragment = metaFactFragment(facts);

  if (fragment) {
    return pickWithin(
      [
        `${yearLabel} Common Data Set for ${schoolName}: ${fragment}. Full tables and the original file.`,
        `${year} Common Data Set for ${schoolName}: ${fragment}. Full tables and the original file.`,
        `${year} ${schoolName} CDS: ${fragment}. Original file linked.`,
      ],
      DESCRIPTION_MAX,
    );
  }

  return pickWithin(
    [
      `${yearLabel} Common Data Set for ${schoolName}: admissions, enrollment, cost, and aid as the school published them, with the original file.`,
      `${year} Common Data Set for ${schoolName}: admissions, cost, and aid as published, with the original file.`,
    ],
    DESCRIPTION_MAX,
  );
}

export type YearKeyFactItem = {
  label: string;
  value: string;
};

/**
 * Structured above-the-fold facts for the year page's `<dl>` summary block.
 * Uses the exact same gated `SchoolYearFacts` as the ribbon and lead.
 */
export function buildYearKeyFacts(facts: SchoolYearFacts | null | undefined): YearKeyFactItem[] {
  if (!usableFacts(facts)) return [];

  const items: YearKeyFactItem[] = [];
  const rate = acceptanceRateOf(facts);
  if (rate != null) {
    items.push({ label: "Acceptance rate", value: share(rate) });
  }
  if (facts.applied != null && facts.applied > 0) {
    items.push({ label: "First-year applicants", value: formatCount(facts.applied) });
  }
  if (facts.admitted != null && facts.admitted >= 0) {
    items.push({ label: "Admitted", value: formatCount(facts.admitted) });
  }
  if (facts.enrolledFirstYear != null && facts.enrolledFirstYear > 0) {
    const yieldRate =
      facts.admitted != null && facts.admitted > 0 && facts.enrolledFirstYear <= facts.admitted
        ? facts.enrolledFirstYear / facts.admitted
        : null;
    items.push({
      label: "Enrolled",
      value: yieldRate != null
        ? `${formatCount(facts.enrolledFirstYear)} (${share(yieldRate)} yield)`
        : formatCount(facts.enrolledFirstYear),
    });
  }
  const sat = satRangeOf(facts);
  if (sat) {
    items.push({ label: "SAT middle 50%", value: sat });
  }
  const act = actRangeOf(facts);
  if (act) {
    items.push({ label: "ACT middle 50%", value: act });
  }

  return items;
}
