// Generated copy for /schools/{id}/early-decision (PRD 031 M3). Deck:
// docs/copy/wave-7-early-decision.md. Same bones as acceptance-rate; the
// numbers are C21, never overall first-year, never "odds" or "early action".

import {
  asEdSeries,
  latestOwnEdNote,
  type AcceptanceHistory,
} from "./acceptance-history";
import {
  DESCRIPTION_MAX,
  LEDE_MAX_SENTENCES,
  LEDE_MAX_TOTAL_WORDS,
  LEDE_MAX_WORDS,
  TITLE_MAX,
  answerSentence,
  contrastSentence,
  fallYear,
  firstYearSentence,
  gapSentence,
  pct,
  possessive,
  reportYear,
} from "./acceptance-rate-copy";

export { TITLE_MAX, DESCRIPTION_MAX, pct, possessive, reportYear };
export { LEDE_MAX_WORDS, LEDE_MAX_SENTENCES, LEDE_MAX_TOTAL_WORDS };

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

export function edAnswerSentence(schoolName: string, history: AcceptanceHistory): string | null {
  const sentence = answerSentence(schoolName, asEdSeries(history));
  return sentence?.replace("first-year applicants", "early-decision applicants") ?? null;
}

export function edLeadSentences(
  schoolName: string,
  history: AcceptanceHistory,
  reportYears?: ReadonlySet<string>,
): string[] {
  const series = asEdSeries(history);
  return fitLead(
    [
      edAnswerSentence(schoolName, history),
      contrastSentence(series),
      firstYearSentence(series),
      gapSentence(series, reportYears),
    ].filter((sentence): sentence is string => Boolean(sentence)),
  );
}

function span(history: AcceptanceHistory): { first: ReturnType<typeof asEdSeries>["years"][0]; last: ReturnType<typeof asEdSeries>["years"][0] } | null {
  const series = asEdSeries(history).years.slice().sort((a, b) => a.yearStart - b.yearStart);
  if (series.length === 0) return null;
  return { first: series[0], last: series[series.length - 1] };
}

export function earlyDecisionTitle(schoolName: string, history: AcceptanceHistory): string {
  const ends = span(history);
  const head = ends
    ? `${schoolName} Early Decision Rate: ${pct(ends.last.rate)} for Fall ${fallYear(ends.last.yearStart)}`
    : null;
  return head && head.length <= TITLE_MAX ? head : `${schoolName} Early Decision by Year`;
}

export function earlyDecisionDescription(schoolName: string, history: AcceptanceHistory): string {
  const ends = span(history);
  if (!ends) return `Early decision acceptance rate by year for ${schoolName}, with source files.`;
  const { first, last } = ends;
  const rate = pct(last.rate);
  const fall = fallYear(last.yearStart);
  const core = `${schoolName} admitted ${rate} of early-decision applicants for fall ${fall}.`;
  const back = first === last
    ? "With source files."
    : asEdSeries(history).gaps.length > 0
      ? `Figures back to fall ${fallYear(first.yearStart)}, with source files.`
      : `Figures for each year since fall ${fallYear(first.yearStart)}, with source files.`;
  const options = [
    `${core} ${back}`,
    `${core} With source files.`,
    core,
    `${schoolName} early decision rate: ${rate} for fall ${fall}.`,
  ];
  return options.find((option) => option.length <= DESCRIPTION_MAX) ?? options[options.length - 1];
}

export function earlyDecisionHeading(schoolName: string, history: AcceptanceHistory): string {
  const ends = span(history);
  if (!ends) return `${possessive(schoolName)} early decision`;
  const { first, last } = ends;
  const range = first === last
    ? `fall ${fallYear(last.yearStart)}`
    : `fall ${fallYear(first.yearStart)}–${fallYear(last.yearStart)}`;
  return `${possessive(schoolName)} early decision, ${range}`;
}

export const ED_KICKER = "Early decision";

export function earlyDecisionSourceNote(schoolName: string): string {
  return `Source: Common Data Set reports published by ${schoolName}, section C21 (applications received and admitted under the early decision plan). Note: Early decision acceptance rate is admitted ÷ applied. Each year is the class entering that fall; the 2024–25 report covers fall 2024. — = not reported or not usable.`;
}

export function earlyDecisionNoteAttribution(year: string): string {
  return `From the ${reportYear(year)} report`;
}

export { latestOwnEdNote };
