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
  if (same(latest.rate, earlier.rate)) return `unchanged from ${where}`;
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

/** "the six years shown" for an unbroken series; "the six years with figures" when some are missing. */
export function yearsPhrase(history: AcceptanceHistory): string {
  const n = history.years.length;
  return `the ${NUMBER_WORDS[n] ?? String(n)} years ${history.gaps.length > 0 ? "with figures" : "shown"}`;
}

/** "the years shown" / "the years with figures", without a count. */
function yearsNoun(history: AcceptanceHistory): string {
  return history.gaps.length > 0 ? "the years with figures" : "the years shown";
}

/** Years whose rate prints the same as `row`, most recent first. */
function tiedAtDisplay(series: AcceptanceYear[], row: AcceptanceYear): AcceptanceYear[] {
  return series.filter((r) => tenths(r.rate) === tenths(row.rate)).sort((a, b) => b.yearStart - a.yearStart);
}

function falls(rows: AcceptanceYear[]): string {
  return joinAnd(rows.map((r) => `fall ${fallYear(r.yearStart)}`));
}

/** True when no year prints below (low) / above (high) `row`. */
function extremeAtDisplay(series: AcceptanceYear[], row: AcceptanceYear, kind: "low" | "high"): boolean {
  return series.every((r) => (kind === "low" ? tenths(r.rate) >= tenths(row.rate) : tenths(r.rate) <= tenths(row.rate)));
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

type AnswerParts = {
  sentence: string;
  /** The far extreme, as its own sentence ("The high was 9.3%, for fall 2020."). */
  contrast: string | null;
  named: Set<AcceptanceYear>;
};

/**
 * The answer and which years it already named (so "It was …" never
 * repeats one). Rules, all at display precision (one decimal):
 * - Record: nothing prints below (above) the latest → "the lowest in the N
 *   years shown/with figures"; ties are named ("tied with fall X").
 *   Monotone series compare with the first year, others with the previous.
 * - Otherwise compare with the previous year ("unchanged" when it prints
 *   the same), then the recent turn (rateShape): in the previous year it
 *   is folded in, with every tied year named if it is the lowest/highest;
 *   older, it is "a low of" when global, else "the lowest since fall Z (v%)"
 *   where Z is the most recent earlier year that printed lower.
 * - Far extreme: moving down but not the series low → its own sentence,
 *   "The low was 7.3%, for fall 2022." (mirror for up), unless the first
 *   year ties it (the "It was" sentence then carries it) or it was already
 *   named. Kept out of the answer so it stays under ~35 words.
 */
function answerParts(schoolName: string, history: AcceptanceHistory): AnswerParts | null {
  const series = oldestFirst(history);
  const last = series[series.length - 1];
  if (!last) return null;
  const first = series[0];
  const prev = series[series.length - 2];
  const base = answerBase(schoolName, last);
  const named = new Set<AcceptanceYear>([last]);
  if (first === last) return { sentence: `${base}.`, contrast: null, named };
  const shape = rateShape(history);
  const allSame = series.every((r) => tenths(r.rate) === tenths(last.rate));

  const recordKind = allSame
    ? null
    : extremeAtDisplay(series, last, "low")
      ? "low"
      : extremeAtDisplay(series, last, "high")
        ? "high"
        : null;
  if (recordKind) {
    const others = tiedAtDisplay(series, last).filter((r) => r !== last);
    const tie = others.length > 0 ? `, tied with ${falls(others)}` : "";
    others.forEach((r) => named.add(r));
    const against = shape.kind === "monotone" ? first : prev;
    named.add(against);
    return {
      sentence: `${base}, the ${recordKind === "low" ? "lowest" : "highest"} in ${yearsPhrase(history)}${tie}, ${comparedWith(last, against)}.`,
      contrast: null,
      named,
    };
  }

  named.add(prev);
  let head = comparedWith(last, prev);
  const clauses: string[] = [];
  if (shape.kind === "turn") {
    const { row, extreme } = shape;
    const global = extremeAtDisplay(series, row, extreme);
    const word = extreme === "low" ? "lowest" : "highest";
    if (row === prev) {
      if (global) {
        const tied = tiedAtDisplay(series, row);
        tied.forEach((r) => named.add(r));
        head = `${head.split(" from ")[0]} from ${pct(row.rate)} for ${falls(tied)}, the ${word} in ${yearsPhrase(history)}`;
      }
    } else if (global) {
      const tied = tiedAtDisplay(series, row);
      tied.forEach((r) => named.add(r));
      clauses.push(` and from a ${extreme} of ${pct(row.rate)} for ${falls(tied)}`);
    } else {
      named.add(row);
      const beyond = [...series]
        .filter((r) => r.yearStart < row.yearStart)
        .reverse()
        .find((r) => (extreme === "low" ? tenths(r.rate) < tenths(row.rate) : tenths(r.rate) > tenths(row.rate)));
      if (beyond) {
        named.add(beyond);
        clauses.push(` and from ${pct(row.rate)} for fall ${fallYear(row.yearStart)}, the ${word} since fall ${fallYear(beyond.yearStart)} (${pct(beyond.rate)})`);
      }
    }
  }

  let contrast: string | null = null;
  const direction = Math.sign(tenths(last.rate) - tenths(prev.rate));
  if (direction !== 0) {
    const kind = direction < 0 ? "low" : "high";
    const extremeRow = [...series].sort((a, b) => (kind === "low" ? a.rate - b.rate : b.rate - a.rate))[0];
    const group = tiedAtDisplay(series, extremeRow);
    const covered = group.some((r) => named.has(r) || r === first);
    if (!covered) {
      group.forEach((r) => named.add(r));
      contrast = `The ${kind} was ${pct(extremeRow.rate)}, for ${falls(group)}.`;
    }
  }
  return { sentence: `${base}, ${head}${clauses.join("")}.`, contrast, named };
}

/** Answer first: the latest year with exact counts, then where it stands. */
export function answerSentence(schoolName: string, history: AcceptanceHistory): string | null {
  return answerParts(schoolName, history)?.sentence ?? null;
}

/** "The low was 7.3%, for fall 2022." when the answer's direction hides the series extreme. */
export function contrastSentence(history: AcceptanceHistory): string | null {
  return answerParts("", history)?.contrast ?? null;
}

/**
 * The long-run start, in its own sentence, only when it adds something:
 * dropped for monotone series (the answer already compares with it) and
 * whenever the answer already named the first year.
 */
export function firstYearSentence(history: AcceptanceHistory): string | null {
  const series = oldestFirst(history);
  if (series.length < 3) return null;
  const parts = answerParts("", history);
  const first = series[0];
  if (!parts || parts.named.has(first)) return null;
  return `It was ${pct(first.rate)} for fall ${fallYear(first.yearStart)}.`;
}

export const DOMINANT_SHARE = 0.6;

/**
 * The one consecutive-year change that makes up at least DOMINANT_SHARE of
 * the whole span's rate change, in the same direction, and no more than
 * all of it. Only for four or more years whose rate has no interior turn
 * (monotone, or the latest year is a record), so "most of the drop" is
 * literally true; skipped when it would repeat the answer's comparison.
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
  // A step larger than the whole change means the series went the other
  // way first; "most of the drop" would mislead.
  if (Math.abs(best.delta) > Math.abs(total)) return null;
  // The answer already compares a non-monotone latest year with the one before.
  if (shape.kind !== "monotone" && best.to === series[series.length - 1]) return null;
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
  if (series.length < 2) return null;
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
    const tied = series.filter((r) => r.applied === extreme.row.applied).sort((x, y) => y.yearStart - x.yearStart);
    const when = falls(tied);
    if (extreme.kind === "peak") {
      const most = `the most in ${yearsNoun(history)} was ${count(extreme.row.applied)}, for ${when}`;
      return latestChange
        ? `Applications ${latestChange}; ${most}.`
        : `Applications were ${count(last.applied)} for fall ${fallYear(last.yearStart)}; ${most}.`;
    }
    const fewest = `the fewest in ${yearsNoun(history)} was ${count(extreme.row.applied)}, for ${when}`;
    return latestChange
      ? `Applications ${latestChange}; ${fewest}.`
      : `Applications were ${count(last.applied)} for fall ${fallYear(last.yearStart)}; ${fewest}.`;
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

/**
 * Missing years, in the table's terms: a report on file whose counts are
 * not usable, or no report in the archive at all. `reportYears` holds the
 * canonical years with a whole-institution report on file; without it,
 * every gap is described as missing usable figures.
 */
export function gapSentence(history: AcceptanceHistory, reportYears?: ReadonlySet<string>): string | null {
  if (history.gaps.length === 0) return null;
  const sorted = [...history.gaps].sort();
  const label = (year: string) => `fall ${Number(year.slice(0, 4))}`;
  const unusable = reportYears ? sorted.filter((y) => reportYears.has(y)) : sorted;
  const absent = reportYears ? sorted.filter((y) => !reportYears.has(y)) : [];
  const noReport = absent.length > 0
    ? `No report${absent.length > 1 ? "s" : ""} for ${joinAnd(absent.map(label))} ${absent.length > 1 ? "are" : "is"} in our archive`
    : null;
  if (noReport && unusable.length === 0) return `${noReport}.`;
  if (!noReport) return `Usable figures for ${joinAnd(unusable.map(label))} are not in our archive.`;
  return `Our archive has no report for ${joinAnd(absent.map(label))} and no usable figures for ${joinAnd(unusable.map(label))}.`;
}

export const LEDE_MAX_WORDS = 35;
export const LEDE_MAX_SENTENCES = 5;
export const LEDE_MAX_TOTAL_WORDS = 75;

export function leadSentences(
  schoolName: string,
  history: AcceptanceHistory,
  reportYears?: ReadonlySet<string>,
): string[] {
  return [
    answerSentence(schoolName, history),
    contrastSentence(history),
    firstYearSentence(history),
    // With a dominant year, its sentence carries the application change;
    // keep only a plain span ("rose from … over that span").
    dominantChange(history) && /%/.test(applicationsSentence(history) ?? "") ? null : applicationsSentence(history),
    dominantSentence(history),
    gapSentence(history, reportYears),
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
