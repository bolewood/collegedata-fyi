// Plain-English summary of the numbers a school reported in a Common Data
// Set year. Every sentence is generated from reported values; a sentence is
// omitted when its inputs are missing or fail a sanity check, never guessed.

export type SchoolYearFacts = {
  document_id: string | null;
  school_id: string | null;
  ipeds_id: string | null;
  canonical_year: string;
  sub_institutional: null;
  yearStart: number | null;
  dataQualityFlag: string | null;
  applied: number | null;
  admitted: number | null;
  enrolledFirstYear: number | null;
  acceptanceRate: number | null;
  satCompositeP25: number | null;
  satCompositeP75: number | null;
  actCompositeP25: number | null;
  actCompositeP75: number | null;
  edApplicants: number | null;
  edAdmitted: number | null;
  waitListOffered: number | null;
  waitListAccepted: number | null;
  waitListAdmitted: number | null;
};

const HIDDEN_FLAGS = new Set(["wrong_file", "blank_template", "low_coverage"]);

function count(n: number): string {
  return n.toLocaleString("en-US");
}

export function share(rate01: number): string {
  const pct = rate01 * 100;
  return `${pct.toFixed(pct > 0 && pct < 10 ? 1 : 0)}%`;
}

/** 2025-26 → 2025-2026, the form printed on the CDS template itself. */
export function longYear(year: string): string | null {
  const match = /^(\d{4})-(\d{2})$/.exec(year);
  if (!match) return null;
  return `${match[1]}-${Number(match[1]) + 1}`;
}

function ratio(part: number | null, whole: number | null): number | null {
  if (part == null || whole == null || whole <= 0 || part < 0 || part > whole) {
    return null;
  }
  return part / whole;
}

function range(
  low: number | null,
  high: number | null,
  min: number,
  max: number,
): string | null {
  if (low == null || high == null) return null;
  if (low < min || high > max || low > high) return null;
  return `${low}–${high}`;
}

export function usableFacts(row: SchoolYearFacts | null | undefined): row is SchoolYearFacts {
  return Boolean(row) && !HIDDEN_FLAGS.has(row?.dataQualityFlag ?? "");
}

export function acceptanceRateOf(row: SchoolYearFacts): number | null {
  return ratio(row.admitted, row.applied) ?? (
    row.acceptanceRate != null && row.acceptanceRate >= 0 && row.acceptanceRate <= 1
      ? row.acceptanceRate
      : null
  );
}

export function satRangeOf(row: SchoolYearFacts): string | null {
  return range(row.satCompositeP25, row.satCompositeP75, 400, 1600);
}

export function actRangeOf(row: SchoolYearFacts): string | null {
  return range(row.actCompositeP25, row.actCompositeP75, 1, 36);
}

export function edRateOf(row: SchoolYearFacts): number | null {
  return ratio(row.edAdmitted, row.edApplicants);
}

/** Sentences for one reported year, in reading order. */
export function yearSummarySentences(
  schoolName: string,
  row: SchoolYearFacts | null | undefined,
): string[] {
  if (!usableFacts(row)) return [];
  const sentences: string[] = [];
  const year = row.canonical_year;

  const rate = ratio(row.admitted, row.applied);
  if (rate != null && row.applied != null && row.admitted != null) {
    sentences.push(
      `In its ${year} report, ${schoolName} says ${count(row.applied)} first-year students applied and ${count(row.admitted)} were admitted, an acceptance rate of ${share(rate)}.`,
    );
  } else {
    const fallback = acceptanceRateOf(row);
    if (fallback != null) {
      sentences.push(
        `In its ${year} report, ${schoolName} lists a first-year acceptance rate of ${share(fallback)}.`,
      );
    }
  }

  const yieldRate = ratio(row.enrolledFirstYear, row.admitted);
  if (yieldRate != null && row.enrolledFirstYear != null) {
    sentences.push(
      `${count(row.enrolledFirstYear)} admitted students enrolled (${share(yieldRate)} yield).`,
    );
  }

  const sat = satRangeOf(row);
  const act = actRangeOf(row);
  if (sat && act) {
    sentences.push(
      `Enrolled students who sent scores had a middle-50% SAT of ${sat} and ACT of ${act}.`,
    );
  } else if (sat) {
    sentences.push(`Enrolled students who sent scores had a middle-50% SAT of ${sat}.`);
  } else if (act) {
    sentences.push(`Enrolled students who sent scores had a middle-50% ACT of ${act}.`);
  }

  const edRate = edRateOf(row);
  if (edRate != null && row.edApplicants != null && row.edAdmitted != null) {
    sentences.push(
      `Early decision: ${count(row.edAdmitted)} of ${count(row.edApplicants)} applicants admitted (${share(edRate)}).`,
    );
  }

  const offered = row.waitListOffered;
  const waitAdmitted = row.waitListAdmitted;
  if (offered != null && offered > 0 && waitAdmitted != null && waitAdmitted >= 0) {
    const accepted = row.waitListAccepted;
    const acceptedClause =
      accepted != null && accepted >= 0 && accepted <= offered && waitAdmitted <= accepted
        ? `, ${count(accepted)} accepted one,`
        : "";
    sentences.push(
      `Waitlist: ${count(offered)} offered a spot${acceptedClause} and ${count(waitAdmitted)} admitted from it.`,
    );
  }

  return sentences;
}

function applicationsClause(prior: SchoolYearFacts, current: SchoolYearFacts): string | null {
  if (!prior.applied || !current.applied || prior.applied <= 0) return null;
  const change = (current.applied - prior.applied) / prior.applied;
  if (Math.abs(change) < 0.005) {
    return `applications held about even at ${count(current.applied)}`;
  }
  const direction = change > 0 ? "rose" : "fell";
  return `applications ${direction} ${share(Math.abs(change))} (${count(prior.applied)} to ${count(current.applied)})`;
}

function rateClause(label: string, before: number | null, after: number | null): string | null {
  if (before == null || after == null) return null;
  if (share(before) === share(after)) return `the ${label} held at ${share(after)}`;
  return `the ${label} went from ${share(before)} to ${share(after)}`;
}

function joinClauses(clauses: string[]): string {
  if (clauses.length === 1) return clauses[0];
  if (clauses.length === 2) return `${clauses[0]} and ${clauses[1]}`;
  return `${clauses.slice(0, -1).join(", ")}, and ${clauses[clauses.length - 1]}`;
}

/**
 * One sentence comparing a year with the immediately preceding one. Null
 * when the prior year is missing, not consecutive, or unusable.
 */
export function yearOverYearSentence(
  current: SchoolYearFacts | null | undefined,
  prior: SchoolYearFacts | null | undefined,
): string | null {
  if (!usableFacts(current) || !usableFacts(prior)) return null;
  if (current.yearStart == null || prior.yearStart !== current.yearStart - 1) return null;

  const clauses = [
    applicationsClause(prior, current),
    rateClause("acceptance rate", acceptanceRateOf(prior), acceptanceRateOf(current)),
    rateClause("early decision admit rate", edRateOf(prior), edRateOf(current)),
  ].filter((clause): clause is string => Boolean(clause));
  if (clauses.length === 0) return null;

  const sentence = joinClauses(clauses);
  return `Compared with ${prior.canonical_year}, ${sentence}.`;
}

/** Short fact fragment for meta descriptions: "8.4% acceptance rate, SAT 1490–1560". */
export function metaFactFragment(row: SchoolYearFacts | null | undefined): string | null {
  if (!usableFacts(row)) return null;
  const parts: string[] = [];
  const rate = acceptanceRateOf(row);
  if (rate != null) parts.push(`${share(rate)} acceptance rate`);
  if (row.applied != null && row.applied > 0) parts.push(`${count(row.applied)} applicants`);
  const sat = satRangeOf(row);
  if (sat) parts.push(`SAT ${sat}`);
  const ed = edRateOf(row);
  if (ed != null) parts.push(`${share(ed)} early decision admit rate`);
  return parts.length > 0 ? parts.join(", ") : null;
}

/** Keep only rows for documents the page serves, so sentences match the files shown. */
export function servedFacts(
  rows: SchoolYearFacts[],
  documentIds: Iterable<string | null | undefined>,
): SchoolYearFacts[] {
  const served = new Set(Array.from(documentIds).filter(Boolean));
  return rows.filter((row) => row.document_id != null && served.has(row.document_id));
}

export function factsForYear(
  rows: SchoolYearFacts[],
  year: string,
): { current: SchoolYearFacts | null; prior: SchoolYearFacts | null } {
  const current = rows.find((row) => row.canonical_year === year) ?? null;
  const prior =
    current?.yearStart != null
      ? rows.find((row) => row.yearStart === (current.yearStart as number) - 1) ?? null
      : null;
  return { current, prior };
}
