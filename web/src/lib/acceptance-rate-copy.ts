// Generated copy for /schools/{id}/acceptance-rate (PRD 031). Deck:
// docs/copy/wave-6-acceptance-rate.md. Every sentence comes from usable
// years only; nothing here estimates, advises, or explains causes.
//
// This page uses one decimal for every rate (5.7%, 20.5%). Hub and year
// pages keep the site style (school-summary `share`).

import type { AcceptanceHistory, AcceptanceYear } from "./acceptance-history";

export const TITLE_MAX = 65;

function count(n: number): string {
  return n.toLocaleString("en-US");
}

/** One decimal, always: 0.0567 → "5.7%". */
export function pct(rate01: number): string {
  return `${(rate01 * 100).toFixed(1)}%`;
}

function same(a: number, b: number): boolean {
  return pct(a) === pct(b);
}

export function possessive(name: string): string {
  return /s$/i.test(name) ? `${name}’` : `${name}’s`;
}

function joinAnd(items: string[]): string {
  if (items.length <= 1) return items[0] ?? "";
  if (items.length === 2) return `${items[0]} and ${items[1]}`;
  return `${items.slice(0, -1).join(", ")}, and ${items[items.length - 1]}`;
}

/** The 2024-25 report counts the class that entered in fall 2024. */
export function fallYear(yearStart: number): number {
  return yearStart;
}

/** "Fall 2024" */
export function fallLabel(row: Pick<AcceptanceYear, "yearStart">): string {
  return `Fall ${fallYear(row.yearStart)}`;
}

/** "2024-25" → "2024–25" */
export function reportYear(year: string): string {
  return year.replace("-", "–");
}

/** "2024–25 report" */
export function reportLabel(year: string): string {
  return `${reportYear(year)} report`;
}

/** "’18" for the fall 2018 class. */
export function shortFall(yearStart: number): string {
  return `’${String(yearStart % 100).padStart(2, "0")}`;
}

function oldestFirst(history: AcceptanceHistory): AcceptanceYear[] {
  return [...history.years].sort((a, b) => a.yearStart - b.yearStart);
}

export type TurningPoint = { kind: "low" | "high"; row: AcceptanceYear };

/**
 * The interior year where the series changes direction overall: a rate
 * below (low) or above (high) both the first and latest years, compared at
 * one decimal. When both exist, the one farther from the latest rate wins;
 * ties go to the most recent year.
 */
export function turningPoint(history: AcceptanceHistory): TurningPoint | null {
  const series = oldestFirst(history);
  if (series.length < 3) return null;
  const first = series[0];
  const last = series[series.length - 1];
  const interior = series.slice(1, -1);
  const at = (rate: number) => Number((rate * 100).toFixed(1));
  const pick = (better: (a: AcceptanceYear, b: AcceptanceYear) => boolean) =>
    interior.reduce((best, row) => (better(row, best) || at(row.rate) === at(best.rate) ? row : best));
  const low = pick((a, b) => at(a.rate) < at(b.rate));
  const high = pick((a, b) => at(a.rate) > at(b.rate));
  const lowOk = at(low.rate) < at(first.rate) && at(low.rate) < at(last.rate);
  const highOk = at(high.rate) > at(first.rate) && at(high.rate) > at(last.rate);
  if (lowOk && highOk) {
    const dLow = Math.abs(at(last.rate) - at(low.rate));
    const dHigh = Math.abs(at(high.rate) - at(last.rate));
    return dHigh > dLow ? { kind: "high", row: high } : { kind: "low", row: low };
  }
  if (lowOk) return { kind: "low", row: low };
  if (highOk) return { kind: "high", row: high };
  return null;
}

function comparedWith(latest: AcceptanceYear, earlier: AcceptanceYear): string {
  const where = `${pct(earlier.rate)} for fall ${fallYear(earlier.yearStart)}`;
  if (same(latest.rate, earlier.rate)) return `the same as ${where}`;
  return latest.rate < earlier.rate ? `down from ${where}` : `up from ${where}`;
}

function change(from: number, to: number): string {
  return pct(Math.abs(to - from) / from);
}

/** Answer first: the latest year with exact counts, then the history. */
export function answerSentence(schoolName: string, history: AcceptanceHistory): string | null {
  const series = oldestFirst(history);
  const last = series[series.length - 1];
  if (!last) return null;
  const first = series[0];
  const base = `${schoolName} admitted ${pct(last.rate)} of first-year applicants for fall ${fallYear(last.yearStart)} (${count(last.admitted)} of ${count(last.applied)})`;
  if (first === last || turningPoint(history)) return `${base}.`;
  return `${base}, ${comparedWith(last, first)}.`;
}

export function turningSentence(history: AcceptanceHistory): string | null {
  const turn = turningPoint(history);
  if (!turn) return null;
  const series = oldestFirst(history);
  const first = series[0];
  const last = series[series.length - 1];
  const extreme = `${turn.kind === "low" ? "up from a low" : "down from a high"} of ${pct(turn.row.rate)} for fall ${fallYear(turn.row.yearStart)}`;
  return `That is ${extreme} and ${comparedWith(last, first)}.`;
}

/**
 * Four or more years: the span, plus the latest change when it runs the
 * other way. Fewer: just the latest change, since the table is short.
 */
export function applicationsSentence(history: AcceptanceHistory): string | null {
  const series = oldestFirst(history);
  if (series.length < 2) return null;
  const first = series[0];
  const last = series[series.length - 1];
  const prev = series[series.length - 2];
  const consecutive = prev.yearStart === last.yearStart - 1;
  const latestChange =
    consecutive && prev.applied !== last.applied
      ? `${last.applied > prev.applied ? "rose" : "fell"} ${change(prev.applied, last.applied)} for fall ${fallYear(last.yearStart)} (${count(prev.applied)} to ${count(last.applied)})`
      : null;

  if (series.length < 4) {
    return latestChange ? `Applications ${latestChange}.` : null;
  }
  if (first.applied === last.applied) {
    return `Applications were ${count(last.applied)} for both fall ${fallYear(first.yearStart)} and fall ${fallYear(last.yearStart)}.`;
  }
  const spanRose = last.applied > first.applied;
  const span = `Applications ${spanRose ? "rose" : "fell"} from ${count(first.applied)} to ${count(last.applied)} over that span`;
  const latestRose = consecutive ? last.applied > prev.applied : spanRose;
  if (latestChange && latestRose !== spanRose && Math.abs(last.applied - prev.applied) / prev.applied >= 0.01) {
    return `${span}, but ${latestChange}.`;
  }
  return `${span}.`;
}

export function gapSentence(history: AcceptanceHistory): string | null {
  if (history.gaps.length === 0) return null;
  const falls = [...history.gaps]
    .sort()
    .map((year) => `fall ${Number(year.slice(0, 4))}`);
  return `Figures for ${joinAnd(falls)} are not available.`;
}

export function leadSentences(schoolName: string, history: AcceptanceHistory): string[] {
  return [
    answerSentence(schoolName, history),
    turningSentence(history),
    applicationsSentence(history),
    gapSentence(history),
  ].filter((sentence): sentence is string => Boolean(sentence));
}

function span(history: AcceptanceHistory): { first: AcceptanceYear; last: AcceptanceYear } | null {
  const series = oldestFirst(history);
  if (series.length === 0) return null;
  return { first: series[0], last: series[series.length - 1] };
}

/**
 * "{school} Acceptance Rate: 5.7% for Fall 2024 (2018–2024 History)", kept
 * within TITLE_MAX characters before the site suffix by dropping the word
 * "History", then the range, then the rate.
 */
export function acceptanceTitle(schoolName: string, history: AcceptanceHistory): string {
  const ends = span(history);
  if (!ends) return `${schoolName} Acceptance Rate by Year`;
  const { first, last } = ends;
  const head = `${schoolName} Acceptance Rate: ${pct(last.rate)} for Fall ${fallYear(last.yearStart)}`;
  const range = `${fallYear(first.yearStart)}–${fallYear(last.yearStart)}`;
  const options = [
    first === last ? head : `${head} (${range} History)`,
    first === last ? head : `${head} (${range})`,
    head,
    `${schoolName} Acceptance Rate by Year`,
  ];
  return options.find((option) => option.length <= TITLE_MAX) ?? options[options.length - 1];
}

export function acceptanceDescription(schoolName: string, history: AcceptanceHistory): string {
  const lead = [answerSentence(schoolName, history), turningSentence(history)].filter(Boolean).join(" ");
  const tail = `Year-by-year figures from ${possessive(schoolName)} Common Data Set, with source files.`;
  return lead ? `${lead} ${tail}` : tail;
}

export function sectionHeading(schoolName: string, history: AcceptanceHistory): string {
  const ends = span(history);
  if (!ends) return `${possessive(schoolName)} acceptance rate`;
  const { first, last } = ends;
  return first === last
    ? `${possessive(schoolName)} acceptance rate, fall ${fallYear(last.yearStart)}`
    : `${possessive(schoolName)} acceptance rate, fall ${fallYear(first.yearStart)}–${fallYear(last.yearStart)}`;
}

export function spanLabel(history: AcceptanceHistory): string | null {
  const ends = span(history);
  if (!ends || ends.first === ends.last) return null;
  return `Fall ${fallYear(ends.first.yearStart)}–fall ${fallYear(ends.last.yearStart)}`;
}

export const KICKER = "First-year admissions";

export function sourceNote(schoolName: string): string {
  return `Source: Common Data Set reports published by ${schoolName}, section C1 (first-time, first-year, degree-seeking students). Note: Acceptance rate is admitted ÷ applied; yield is enrolled ÷ admitted. Each year is the class entering that fall; the 2024–25 report covers fall 2024. — = not reported or not usable.`;
}

/** Gap-row source cell. "On file" is checked against the archive's documents. */
export function gapLabel(hasReport: boolean): string {
  return hasReport ? "Report on file; counts not usable" : "No report in our archive";
}

export function relatedLinks(schoolName: string, latestYear: string | null): { hub: string; latest: string | null } {
  return {
    hub: `${schoolName} overview`,
    latest: latestYear ? `${possessive(schoolName)} ${reportYear(latestYear)} Common Data Set` : null,
  };
}

export function degradedNote(): string {
  return "Some years that used to appear here are no longer shown. The table lists the years we can still stand behind.";
}
