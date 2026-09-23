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

/** Rate in tenths of a point, as printed: 0.0567 → 57. Comparisons use this. */
function tenths(rate: number): number {
  return Math.round(rate * 1000);
}

const NUMBER_WORDS = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten"];

function yearsShown(n: number): string {
  return `the ${NUMBER_WORDS[n] ?? String(n)} years shown`;
}

function answerBase(schoolName: string, last: AcceptanceYear): string {
  return `${schoolName} admitted ${pct(last.rate)} of first-year applicants for fall ${fallYear(last.yearStart)} (${count(last.admitted)} of ${count(last.applied)})`;
}

/** A turning point in the year just before the latest one reads as part of the answer. */
function turnIsPrevious(history: AcceptanceHistory, turn: TurningPoint | null): boolean {
  const series = oldestFirst(history);
  const last = series[series.length - 1];
  return Boolean(turn && last && turn.row.yearStart === last.yearStart - 1 && series[series.length - 2] === turn.row);
}

/** Answer first: the latest year with exact counts. */
export function answerSentence(schoolName: string, history: AcceptanceHistory): string | null {
  const series = oldestFirst(history);
  const last = series[series.length - 1];
  if (!last) return null;
  const first = series[0];
  const base = answerBase(schoolName, last);
  const turn = turningPoint(history);
  if (turn && turnIsPrevious(history, turn)) {
    const dir = turn.kind === "low" ? "up from" : "down from";
    const extreme = turn.kind === "low" ? "lowest" : "highest";
    return `${base}, ${dir} ${pct(turn.row.rate)} for fall ${fallYear(turn.row.yearStart)}, the ${extreme} in ${yearsShown(series.length)}.`;
  }
  if (first === last || turn) return `${base}.`;
  return `${base}, ${comparedWith(last, first)}.`;
}

export function turningSentence(history: AcceptanceHistory): string | null {
  const turn = turningPoint(history);
  if (!turn || turnIsPrevious(history, turn)) return null;
  const series = oldestFirst(history);
  const first = series[0];
  const last = series[series.length - 1];
  const shown = history.gaps.length > 0 ? " (the lowest in the years shown)" : "";
  const extreme = turn.kind === "low"
    ? `up from a low of ${pct(turn.row.rate)} for fall ${fallYear(turn.row.yearStart)}${shown}`
    : `down from a high of ${pct(turn.row.rate)} for fall ${fallYear(turn.row.yearStart)}${shown.replace("lowest", "highest")}`;
  return `That is ${extreme} and ${comparedWith(last, first)}.`;
}

export const DOMINANT_SHARE = 0.6;

/**
 * The one consecutive-year change that makes up at least DOMINANT_SHARE of
 * the whole span's rate change, in the same direction. Only for four or
 * more years with no turning point, so "most of the drop" is literally
 * true and not a restatement of a short table.
 */
export function dominantChange(
  history: AcceptanceHistory,
): { from: AcceptanceYear; to: AcceptanceYear } | null {
  const series = oldestFirst(history);
  if (series.length < 4 || turningPoint(history)) return null;
  const total = tenths(series[series.length - 1].rate) - tenths(series[0].rate);
  if (total === 0) return null;
  let best: { from: AcceptanceYear; to: AcceptanceYear; delta: number } | null = null;
  for (let i = 1; i < series.length; i++) {
    const from = series[i - 1];
    const to = series[i];
    if (to.yearStart !== from.yearStart + 1) continue;
    const delta = tenths(to.rate) - tenths(from.rate);
    if (Math.sign(delta) !== Math.sign(total)) continue;
    if (!best || Math.abs(delta) > Math.abs(best.delta)) best = { from, to, delta };
  }
  if (!best || Math.abs(best.delta) < DOMINANT_SHARE * Math.abs(total)) return null;
  return { from: best.from, to: best.to };
}

export function dominantSentence(history: AcceptanceHistory): string | null {
  const dominant = dominantChange(history);
  if (!dominant) return null;
  const { from, to } = dominant;
  const series = oldestFirst(history);
  const drop = series[series.length - 1].rate < series[0].rate;
  const step = `from ${pct(from.rate)} for fall ${fallYear(from.yearStart)} to ${pct(to.rate)} for fall ${fallYear(to.yearStart)}`;
  const admits = to.admitted === from.admitted
    ? `admits held at ${count(to.admitted)}`
    : `admits ${to.admitted < from.admitted ? "fell" : "rose"} from ${count(from.admitted)} to ${count(to.admitted)}`;
  const apps = to.applied === from.applied
    ? `applications held at ${count(to.applied)}`
    : `applications ${to.applied > from.applied ? "rose" : "fell"} ${change(from.applied, to.applied)}`;
  return `Most of the ${drop ? "drop" : "rise"} came in one year, ${step}: ${admits}, while ${apps}.`;
}

/** Most recent interior year whose applications are above (peak) or below (low) both ends. */
function applicationsExtreme(series: AcceptanceYear[]): { kind: "peak" | "low"; row: AcceptanceYear } | null {
  const first = series[0];
  const last = series[series.length - 1];
  for (let i = series.length - 2; i >= 1; i--) {
    const row = series[i];
    const interior = series.slice(1, -1).map((r) => r.applied);
    if (row.applied === Math.max(...interior) && row.applied > first.applied && row.applied > last.applied) {
      return { kind: "peak", row };
    }
    if (row.applied === Math.min(...interior) && row.applied < first.applied && row.applied < last.applied) {
      return { kind: "low", row };
    }
  }
  return null;
}

/**
 * Four or more years: a peak or low in applications when there is one
 * (the true max or min of the years shown), else the span; plus the latest
 * change. Fewer: just the latest change.
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
      ? `${last.applied > prev.applied ? "rose" : "fell"} ${change(prev.applied, last.applied)} for fall ${fallYear(last.yearStart)}, to ${count(last.applied)}`
      : null;

  if (series.length < 4) {
    return latestChange ? `Applications ${latestChange}.` : null;
  }

  const extreme = applicationsExtreme(series);
  if (extreme) {
    if (extreme.row === prev && latestChange) return `Applications ${latestChange}.`;
    const shown = history.gaps.length > 0 ? " in the years shown" : "";
    const where = `${count(extreme.row.applied)} for fall ${fallYear(extreme.row.yearStart)}${shown}`;
    const head = extreme.kind === "peak" ? `Applications peaked at ${where}` : `Applications were lowest at ${where}`;
    const awayFromExtreme = extreme.kind === "peak" ? last.applied < prev.applied : last.applied > prev.applied;
    if (latestChange && awayFromExtreme) return `${head} and ${latestChange}.`;
    const tail = latestChange
      ? `, ${last.applied > prev.applied ? "up" : "down"} ${change(prev.applied, last.applied)} from fall ${fallYear(prev.yearStart)}`
      : "";
    return `${head} and were ${count(last.applied)} for fall ${fallYear(last.yearStart)}${tail}.`;
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
  return `Usable figures for ${joinAnd(falls)} are not in our archive.`;
}

export function leadSentences(schoolName: string, history: AcceptanceHistory): string[] {
  return [
    answerSentence(schoolName, history),
    turningSentence(history),
    dominantSentence(history),
    applicationsSentence(history),
    gapSentence(history),
  ].filter((sentence): sentence is string => Boolean(sentence));
}

function span(history: AcceptanceHistory): { first: AcceptanceYear; last: AcceptanceYear } | null {
  const series = oldestFirst(history);
  if (series.length === 0) return null;
  return { first: series[0], last: series[series.length - 1] };
}

/** "{school} Acceptance Rate: 6.3% for Fall 2025", or "by Year" when that runs past TITLE_MAX. */
export function acceptanceTitle(schoolName: string, history: AcceptanceHistory): string {
  const ends = span(history);
  const head = ends
    ? `${schoolName} Acceptance Rate: ${pct(ends.last.rate)} for Fall ${fallYear(ends.last.yearStart)}`
    : null;
  return head && head.length <= TITLE_MAX ? head : `${schoolName} Acceptance Rate by Year`;
}

export const DESCRIPTION_MAX = 155;

/**
 * Answer sentence plus how far back the figures go, within
 * DESCRIPTION_MAX. Longer names drop whole sentences or clauses, never
 * part of a number.
 */
export function acceptanceDescription(schoolName: string, history: AcceptanceHistory): string {
  const ends = span(history);
  if (!ends) return `First-year acceptance rate by year for ${schoolName}, with source files.`;
  const { first, last } = ends;
  const rate = pct(last.rate);
  const fall = fallYear(last.yearStart);
  const core = `${answerBase(schoolName, last)}.`;
  const back = first === last
    ? "With source files."
    : history.gaps.length > 0
      ? `Figures back to fall ${fallYear(first.yearStart)}, with source files.`
      : `Figures for each year since fall ${fallYear(first.yearStart)}, with source files.`;
  const options = [
    `${core} ${back}`,
    `${core} With source files.`,
    core,
    `${schoolName} admitted ${rate} of first-year applicants for fall ${fall}.`,
    `${schoolName} acceptance rate: ${rate} for fall ${fall}.`,
    `First-year acceptance rate: ${rate} for fall ${fall}, with source files.`,
  ];
  return options.find((option) => option.length <= DESCRIPTION_MAX) ?? options[options.length - 1];
}

export function sectionHeading(schoolName: string, history: AcceptanceHistory): string {
  const ends = span(history);
  if (!ends) return `${possessive(schoolName)} acceptance rate`;
  const { first, last } = ends;
  const range = first === last
    ? `fall ${fallYear(last.yearStart)}`
    : `fall ${fallYear(first.yearStart)}–${fallYear(last.yearStart)}`;
  return history.years.length < 4
    ? `${schoolName} first-year admissions, ${range}`
    : `${possessive(schoolName)} acceptance rate, ${range}`;
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
