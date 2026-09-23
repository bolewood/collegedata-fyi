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

export type RateShape =
  /** Never reverses at one decimal, or too short to say. */
  | { kind: "monotone" }
  /** Latest equals the previous year at one decimal. */
  | { kind: "flat" }
  /** Latest is the lowest (or highest) rate of the years shown. */
  | { kind: "record"; extreme: "low" | "high" }
  /**
   * The most recent extreme the series has since moved away from. `global`
   * when it is also the lowest/highest of all years shown; otherwise it is
   * the lowest/highest since fall `since`.
   */
  | { kind: "turn"; extreme: "low" | "high"; row: AcceptanceYear; global: boolean; since: AcceptanceYear };

/**
 * Where the latest rate stands, compared at one decimal. The direction is
 * the latest year against the previous one. Rising: find the most recent
 * earlier year at or above the latest rate; the turn is the lowest year
 * after it — the low the series has since moved away from. Falling is the
 * mirror image. No such earlier year means the latest year is a record.
 * Ties go to the most recent of the tied years (the one the series left
 * last).
 */
export function rateShape(history: AcceptanceHistory): RateShape {
  const series = oldestFirst(history);
  if (series.length < 3) return { kind: "monotone" };
  const t = series.map((row) => tenths(row.rate));
  const nonDecreasing = t.every((v, i) => i === 0 || v >= t[i - 1]);
  const nonIncreasing = t.every((v, i) => i === 0 || v <= t[i - 1]);
  if (nonDecreasing || nonIncreasing) return { kind: "monotone" };
  const last = t.length - 1;
  const direction = Math.sign(t[last] - t[last - 1]);
  if (direction === 0) return { kind: "flat" };
  const rising = direction > 0;
  let ref = -1;
  for (let i = last - 1; i >= 0; i--) {
    if (rising ? t[i] >= t[last] : t[i] <= t[last]) {
      ref = i;
      break;
    }
  }
  if (ref < 0) return { kind: "record", extreme: rising ? "high" : "low" };
  let best = ref + 1;
  for (let i = ref + 1; i < last; i++) {
    if (rising ? t[i] <= t[best] : t[i] >= t[best]) best = i;
  }
  const global = rising ? t.every((v) => v >= t[best]) : t.every((v) => v <= t[best]);
  return { kind: "turn", extreme: rising ? "low" : "high", row: series[best], global, since: series[ref] };
}

/** Answer first: the latest year with exact counts, then where it stands. */
export function answerSentence(schoolName: string, history: AcceptanceHistory): string | null {
  const series = oldestFirst(history);
  const last = series[series.length - 1];
  if (!last) return null;
  const first = series[0];
  const prev = series[series.length - 2];
  const base = answerBase(schoolName, last);
  if (first === last) return `${base}.`;
  const shape = rateShape(history);

  if (shape.kind === "record") {
    const extreme = shape.extreme === "low" ? "lowest" : "highest";
    return `${base}, the ${extreme} in ${yearsShown(series.length)}, ${comparedWith(last, prev)}.`;
  }
  if (shape.kind === "turn") {
    const { row } = shape;
    if (row === prev) {
      const note = shape.global ? `, the ${shape.extreme === "low" ? "lowest" : "highest"} in ${yearsShown(series.length)}` : "";
      return `${base}, ${comparedWith(last, prev)}${note}.`;
    }
    const word = shape.extreme === "low" ? "low" : "high";
    const extreme = shape.global
      ? `from a ${word} of ${pct(row.rate)} for fall ${fallYear(row.yearStart)}`
      : `from ${pct(row.rate)} for fall ${fallYear(row.yearStart)}, the ${shape.extreme === "low" ? "lowest" : "highest"} since fall ${fallYear(shape.since.yearStart)}`;
    return `${base}, ${comparedWith(last, prev)} and ${extreme}.`;
  }
  if (dominantChange(history)) {
    // Applications sentence is skipped when the dominant year runs; the
    // span rides on the answer.
    const apps = first.applied === last.applied
      ? `while applications held at ${count(last.applied)}`
      : `while applications ${last.applied > first.applied ? "rose" : "fell"} from ${count(first.applied)} to ${count(last.applied)}`;
    return `${base}, ${comparedWith(last, first)}, ${apps}.`;
  }
  return `${base}, ${comparedWith(last, first)}.`;
}

/** The long-run start, in its own sentence, when the answer compared with a later year. */
export function firstYearSentence(history: AcceptanceHistory): string | null {
  const series = oldestFirst(history);
  if (series.length < 3) return null;
  const shape = rateShape(history);
  if (shape.kind !== "record" && shape.kind !== "turn") return null;
  const first = series[0];
  const prev = series[series.length - 2];
  if (first === prev || (shape.kind === "turn" && first === shape.row)) return null;
  return `It was ${pct(first.rate)} for fall ${fallYear(first.yearStart)}.`;
}

export const DOMINANT_SHARE = 0.6;

/**
 * The one consecutive-year change that makes up at least DOMINANT_SHARE of
 * the whole span's rate change, in the same direction. Only for four or
 * more years whose rate has no interior turn (monotone, or the latest
 * year is a record), so "most of the drop" is literally true.
 */
export function dominantChange(
  history: AcceptanceHistory,
): { from: AcceptanceYear; to: AcceptanceYear } | null {
  const series = oldestFirst(history);
  if (series.length < 4) return null;
  const shape = rateShape(history);
  if (shape.kind !== "monotone" && shape.kind !== "record") return null;
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

/**
 * Both counts for both years, neutral verbs: applications rose/fell;
 * admits fell/rose when they moved with the rate, "went from" otherwise,
 * so a falling rate beside rising admits does not read as a typo.
 */
export function dominantSentence(history: AcceptanceHistory): string | null {
  const dominant = dominantChange(history);
  if (!dominant) return null;
  const { from, to } = dominant;
  const series = oldestFirst(history);
  const drop = series[series.length - 1].rate < series[0].rate;
  const step = `from ${pct(from.rate)} for fall ${fallYear(from.yearStart)} to ${pct(to.rate)} for fall ${fallYear(to.yearStart)}`;
  const apps = to.applied === from.applied
    ? `applications held at ${count(to.applied)}`
    : `applications ${to.applied > from.applied ? "rose" : "fell"} from ${count(from.applied)} to ${count(to.applied)}`;
  const admitsDown = to.admitted < from.admitted;
  const admits = to.admitted === from.admitted
    ? `admits held at ${count(to.admitted)}`
    : `admits ${admitsDown === drop ? (admitsDown ? "fell" : "rose") : "went"} from ${count(from.admitted)} to ${count(to.admitted)}`;
  return `Most of the ${drop ? "drop" : "rise"} came in one year, ${step}, when ${apps} and ${admits}.`;
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
 * Every percent change names its base-year count: "fell 12.5% for fall
 * 2025, to 42,774 from 48,904". Four or more years: the latest change plus
 * a true peak or low of the years shown when there is one, else the span.
 * Fewer: just the latest change. Skipped when the dominant-year sentence
 * runs (the answer carries the span).
 */
export function applicationsSentence(history: AcceptanceHistory): string | null {
  const series = oldestFirst(history);
  if (series.length < 2 || dominantChange(history)) return null;
  const first = series[0];
  const last = series[series.length - 1];
  const prev = series[series.length - 2];
  const consecutive = prev.yearStart === last.yearStart - 1;
  const latestChange =
    consecutive && prev.applied !== last.applied
      ? `${last.applied > prev.applied ? "rose" : "fell"} ${change(prev.applied, last.applied)} for fall ${fallYear(last.yearStart)}, to ${count(last.applied)} from ${count(prev.applied)}`
      : null;

  if (series.length < 4) {
    return latestChange ? `Applications ${latestChange}.` : null;
  }

  const extreme = applicationsExtreme(series);
  if (extreme) {
    if (extreme.row === prev && latestChange) return `Applications ${latestChange}.`;
    const shown = history.gaps.length > 0 ? " in the years shown" : "";
    const where = `${count(extreme.row.applied)} for fall ${fallYear(extreme.row.yearStart)}${shown}`;
    const clause = extreme.kind === "peak" ? `peaked at ${where}` : `were lowest at ${where}`;
    return latestChange
      ? `Applications ${latestChange}; they ${clause}.`
      : `Applications ${clause} and were ${count(last.applied)} for fall ${fallYear(last.yearStart)}.`;
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
    firstYearSentence(history),
    applicationsSentence(history),
    dominantSentence(history),
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
