// Generated copy for /schools/{id}/gpa (PRD 031 / #195). Deck:
// docs/copy/wave-8-gpa.md. C11 is enrolled first-years who reported a
// GPA, never a cutoff, minimum, or "the GPA you need."

import type { GpaHistory, GpaYear } from "./c11-gpa";
import {
  DESCRIPTION_MAX,
  LEDE_MAX_SENTENCES,
  LEDE_MAX_TOTAL_WORDS,
  LEDE_MAX_WORDS,
  TITLE_MAX,
  fallYear,
  gapSentence,
  pct,
  possessive,
  reportYear,
} from "./acceptance-rate-copy";

export { TITLE_MAX, DESCRIPTION_MAX, pct, possessive, reportYear };
export { LEDE_MAX_WORDS, LEDE_MAX_SENTENCES, LEDE_MAX_TOTAL_WORDS };

const BANNED = /\b(cutoff|minimum|odds|chances|need to get in|gpa you need)\b/i;

export function gpa(n: number): string {
  return n.toFixed(2);
}

export function bandShare(percent: number): string {
  return pct(percent / 100);
}

function wordCount(sentence: string): number {
  return sentence.trim().split(/\s+/).length;
}

function fitLead(sentences: string[]): string[] {
  const keep = sentences.filter(Boolean);
  const within = (list: string[]) =>
    list.length <= LEDE_MAX_SENTENCES &&
    list.every((s) => wordCount(s) <= LEDE_MAX_WORDS) &&
    wordCount(list.join(" ")) <= LEDE_MAX_TOTAL_WORDS;
  if (within(keep)) return keep;
  const trimmed = [...keep];
  for (const extra of [...keep].reverse()) {
    if (trimmed.length <= 1) break;
    const at = trimmed.indexOf(extra);
    if (at <= 0) continue;
    trimmed.splice(at, 1);
    if (within(trimmed)) return trimmed;
  }
  return trimmed;
}

function oldestFirst(history: GpaHistory): GpaYear[] {
  return [...history.years].sort((a, b) => a.yearStart - b.yearStart);
}

function span(history: GpaHistory): { first: GpaYear; last: GpaYear } | null {
  const series = oldestFirst(history);
  if (series.length === 0) return null;
  return { first: series[0], last: series[series.length - 1] };
}

export function gpaAnswerSentence(schoolName: string, history: GpaHistory): string | null {
  const last = oldestFirst(history).at(-1);
  if (!last) return null;
  const fall = fallYear(last.yearStart);
  if (last.average != null) {
    return `${schoolName} reports an average high school GPA of ${gpa(last.average)} for enrolled first-years who reported one for fall ${fall}.`;
  }
  return `${schoolName} reports that ${bandShare(last.bands.percents.gpa4)} of enrolled first-years who reported a GPA had a 4.0 for fall ${fall}.`;
}

function contrastSentence(history: GpaHistory): string | null {
  const series = oldestFirst(history);
  if (series.length < 2) return null;
  const last = series[series.length - 1];
  const prev = series[series.length - 2];
  if (last.average != null && prev.average != null) {
    if (gpa(last.average) === gpa(prev.average)) {
      return `Unchanged from ${gpa(prev.average)} for fall ${fallYear(prev.yearStart)}.`;
    }
    const direction = last.average > prev.average ? "up" : "down";
    return `${direction === "up" ? "Up" : "Down"} from ${gpa(prev.average)} for fall ${fallYear(prev.yearStart)}.`;
  }
  const latestShare = bandShare(last.bands.percents.gpa4);
  const prevShare = bandShare(prev.bands.percents.gpa4);
  if (latestShare === prevShare) {
    return `The 4.0 share is unchanged from fall ${fallYear(prev.yearStart)}.`;
  }
  const direction = last.bands.percents.gpa4 > prev.bands.percents.gpa4 ? "Up" : "Down";
  return `${direction} from ${prevShare} at 4.0 for fall ${fallYear(prev.yearStart)}.`;
}

function firstYearSentence(history: GpaHistory): string | null {
  const ends = span(history);
  if (!ends || ends.first === ends.last) return null;
  return `Figures go back to fall ${fallYear(ends.first.yearStart)}.`;
}

export function gpaLeadSentences(
  schoolName: string,
  history: GpaHistory,
  reportYears?: ReadonlySet<string>,
): string[] {
  const lead = fitLead(
    [
      gpaAnswerSentence(schoolName, history),
      contrastSentence(history),
      firstYearSentence(history),
      gapSentence({ years: [], gaps: history.gaps, excluded: [] }, reportYears),
    ].filter((sentence): sentence is string => Boolean(sentence)),
  );
  return lead.filter((sentence) => !BANNED.test(sentence));
}

export function gpaTitle(schoolName: string, history: GpaHistory): string {
  const ends = span(history);
  if (!ends) return `${schoolName} First-Year GPA by Year`;
  const fall = fallYear(ends.last.yearStart);
  const head =
    ends.last.average != null
      ? `${schoolName} Average GPA: ${gpa(ends.last.average)} for Fall ${fall}`
      : `${schoolName} GPA: ${bandShare(ends.last.bands.percents.gpa4)} at 4.0 for Fall ${fall}`;
  return head.length <= TITLE_MAX ? head : `${schoolName} First-Year GPA by Year`;
}

export function gpaDescription(schoolName: string, history: GpaHistory): string {
  const ends = span(history);
  if (!ends) return `Enrolled first-year GPA for ${schoolName}, with source files.`;
  const core = gpaAnswerSentence(schoolName, history) ?? "";
  const back =
    ends.first === ends.last
      ? "With source files."
      : history.gaps.length > 0
        ? `Figures back to fall ${fallYear(ends.first.yearStart)}, with source files.`
        : `Figures for each year since fall ${fallYear(ends.first.yearStart)}, with source files.`;
  const options = [`${core} ${back}`, `${core} With source files.`, core];
  return options.find((option) => option.length <= DESCRIPTION_MAX && !BANNED.test(option)) ?? options[options.length - 1];
}

export function gpaHeading(schoolName: string, history: GpaHistory): string {
  const ends = span(history);
  if (!ends) return `${possessive(schoolName)} enrolled first-year GPA`;
  const range =
    ends.first === ends.last
      ? `fall ${fallYear(ends.last.yearStart)}`
      : `fall ${fallYear(ends.first.yearStart)}–${fallYear(ends.last.yearStart)}`;
  return `${possessive(schoolName)} enrolled first-year GPA, ${range}`;
}

export const GPA_KICKER = "High school GPA";

export function gpaSourceNote(schoolName: string): string {
  return `Source: Common Data Set reports published by ${schoolName}, section C11 (GPA of enrolled first-years who reported one) and C12 (average, when printed). Each year is the class entering that fall; the 2024–25 report covers fall 2024. — = not reported or not usable.`;
}

export function gpaChartCaption(history: GpaHistory): string {
  const averages = history.years.filter((row) => row.average != null).length;
  return averages >= 4
    ? "Average high school GPA of enrolled first-years who reported one, by fall entering class."
    : "Share of enrolled first-years who reported a GPA of 4.0, by fall entering class.";
}

export function gpaChartKind(history: GpaHistory): "average" | "gpa4" {
  return history.years.filter((row) => row.average != null).length >= 4 ? "average" : "gpa4";
}
