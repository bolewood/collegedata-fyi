// Generated copy for /schools/{id}/acceptance-rate (PRD 031). Deck:
// docs/copy/wave-6-acceptance-rate.md. Every sentence comes from usable
// years only; nothing here estimates or advises.

import { share } from "./school-summary";
import type { AcceptanceHistory, AcceptanceYear } from "./acceptance-history";

function count(n: number): string {
  return n.toLocaleString("en-US");
}

export function possessive(name: string): string {
  return /s$/i.test(name) ? `${name}’` : `${name}’s`;
}

function joinOr(items: string[]): string {
  if (items.length <= 1) return items[0] ?? "";
  if (items.length === 2) return `${items[0]} or ${items[1]}`;
  return `${items.slice(0, -1).join(", ")}, or ${items[items.length - 1]}`;
}

/** "fall 2024" for the 2024-25 report: the class that applied to enter that fall. */
export function entryTerm(row: Pick<AcceptanceYear, "yearStart">): string {
  return `fall ${row.yearStart}`;
}

function ends(history: AcceptanceHistory): { first: AcceptanceYear; last: AcceptanceYear } | null {
  if (history.years.length === 0) return null;
  return { first: history.years[history.years.length - 1], last: history.years[0] };
}

export function spanSentence(schoolName: string, history: AcceptanceHistory): string | null {
  const span = ends(history);
  if (!span || span.first === span.last) return null;
  const { first, last } = span;
  const from = share(first.rate);
  const to = share(last.rate);
  const trend = from === to
    ? `an acceptance rate of ${to} in both years`
    : `the acceptance rate going from ${from} to ${to}`;
  return `${possessive(schoolName)} reports from ${first.year} to ${last.year} show ${trend}.`;
}

export function applicationsSentence(history: AcceptanceHistory): string | null {
  const span = ends(history);
  if (!span || span.first === span.last) return null;
  const { first, last } = span;
  if (first.applied === last.applied) {
    return `First-year applications were ${count(last.applied)} in both years.`;
  }
  return `Over the same years, first-year applications went from ${count(first.applied)} to ${count(last.applied)}.`;
}

export function gapSentence(history: AcceptanceHistory): string | null {
  if (history.gaps.length === 0) return null;
  const years = [...history.gaps].sort();
  return `There is no usable report for ${joinOr(years)}, so ${years.length === 1 ? "that year is" : "those years are"} left out.`;
}

export function leadSentences(schoolName: string, history: AcceptanceHistory): string[] {
  return [
    spanSentence(schoolName, history),
    applicationsSentence(history),
    gapSentence(history),
  ].filter((sentence): sentence is string => Boolean(sentence));
}

export function acceptanceTitle(schoolName: string, history: AcceptanceHistory): string {
  const span = ends(history);
  if (!span) return `${schoolName} Acceptance Rate by Year`;
  const { first, last } = span;
  const range = first.yearStart === last.yearStart
    ? `${last.yearStart}`
    : `${first.yearStart}–${last.yearStart}`;
  return `${schoolName} Acceptance Rate by Year, ${range}`;
}

export function acceptanceDescription(schoolName: string, history: AcceptanceHistory): string {
  const span = ends(history);
  if (!span) return `${schoolName} first-year acceptance rate by year, with the original files.`;
  const { last } = span;
  const lead = spanSentence(schoolName, history);
  const latest = `In ${last.year}, ${count(last.admitted)} of ${count(last.applied)} applicants were admitted (${share(last.rate)}), with the original files.`;
  return lead ? `${lead} ${latest}` : latest;
}

export const DEFINITION_NOTE =
  "From each year’s Common Data Set, section C1: first-time, first-year, degree-seeking applicants and admits.";

export const METHOD_NOTES = [
  "Acceptance rate is admitted ÷ applied. Yield is enrolled ÷ admitted.",
  "Each report covers the class that entered that fall: the 2024-25 report counts students who applied to start in fall 2024.",
  "Numbers are as the school reported them. A dash means that count isn’t shown for the year because it could not be read in full from the report.",
];

export function degradedNote(): string {
  return "Some years that used to appear here are no longer shown. The table lists the years we can still stand behind.";
}
