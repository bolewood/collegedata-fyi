// CDS C21 "significant details" free text. PRD 031 M3 serves an
// early-decision page only when the school's own note is in the extract
// (not a stock disclaimer) and shown on the page.

import { c1TemplateForArtifact, fieldText } from "./c1-headline-totals";
import type { FieldValue } from "./types";

function noteIds(yearStart: number | null | undefined): string[] {
  // 2025-26 moved the note to C.2112; C.2108 is a notification-date month.
  if (yearStart != null && yearStart >= 2025) return ["C.2112"];
  return ["C.2108", "C.2112"];
}

const STOCK =
  /^(n\/?a|n\.a\.|none|nil|not applicable|no|yes|-|—|\.|see (the )?(college'?s? )?(admission|admissions|website|web site|college website).*\.?)$/i;

const URL_ONLY = /^(for more information,? visit |see ).*(https?:\/\/|www\.)/i;
const BARE_URL = /^(https?:\/\/\S+|www\.\S+)$/i;
const HEADING_ONLY = /^(?:#{1,6}\s+)?(?:for the fall \d{4} entering class:?|c22\b.*)$/i;

/** CDS form chrome that is not the school's own plan note. */
export const C21_FORM_CHROME =
  /does your institution offer an early decision plan|number of early decision applications received|number of applicants admitted under early decision|if ['']yes,?[''] please complete|click or tap here to enter text|first or only early decision plan (closing|notification) date|other early decision plan (closing|notification) date|do you have a nonbinding early action|is your early action plan a ['']restrictive[''] plan|please provide significant details about your early decision plan|<!-- image -->|c22\b.*early action/i;

const DETAILS_PROMPT = /please provide significant details about your early decision plan:\s*/i;

export const C21_NEXT_SECTION =
  /(?:^|\n)\s*(?:#{1,3}\s*)?(?:[-*]\s*)?(?:c22|early action|d\.\s|d1[-–]d2|transfer admission)\b/i;

const DETAILS_STOP =
  /(?:^|\s)(?:if ['']yes,?[''] please complete|does your institution offer an early decision plan|do you have a nonbinding early action|number of early decision applications received|c22\.?\s+early action)/i;

export function isOwnEdNote(text: string | null | undefined): text is string {
  if (text == null) return false;
  const trimmed = text.replace(/\s+/g, " ").trim();
  if (trimmed.length < 24) return false;
  if (STOCK.test(trimmed)) return false;
  if (URL_ONLY.test(trimmed)) return false;
  if (BARE_URL.test(trimmed)) return false;
  if (HEADING_ONLY.test(trimmed)) return false;
  // A URL with almost no surrounding prose is still a disclaimer.
  if (/https?:\/\//i.test(trimmed) && trimmed.replace(/https?:\/\/\S+/gi, "").trim().length < 24) {
    return false;
  }
  if (C21_FORM_CHROME.test(trimmed)) return false;
  return true;
}

function cleanNoteBody(raw: string): string | null {
  const stopped = DETAILS_STOP.exec(raw);
  const cut = stopped && stopped.index > 0 ? raw.slice(0, stopped.index) : raw;
  const body = cut
    .replace(/^\s*\|\s*/gm, "")
    .replace(/\|/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  return body || null;
}

/** Free text after the C21 details prompt, up to C22 / the next form prompt. */
export function c21MarkdownNote(markdown: string | null | undefined): string | null {
  if (!markdown) return null;
  const match = DETAILS_PROMPT.exec(markdown);
  if (!match || match.index == null) return null;
  const rest = markdown.slice(match.index + match[0].length);
  const end = rest.search(C21_NEXT_SECTION);
  return cleanNoteBody(end >= 0 ? rest.slice(0, end) : rest.slice(0, 1200));
}

export function readC21Note(extract: {
  values: Record<string, FieldValue>;
  schemaVersion?: string | null;
  producer?: string | null;
  yearStart?: number | null;
  markdown?: string | null;
}): string | null {
  const resolved = c1TemplateForArtifact({
    schemaVersion: extract.schemaVersion,
    producer: extract.producer,
    yearStart: extract.yearStart,
  });
  if (!resolved.template) return null;
  for (const id of noteIds(extract.yearStart)) {
    const text = fieldText(extract.values, id);
    if (text && !/^\d{1,2}$/.test(text)) return text;
  }
  return c21MarkdownNote(extract.markdown);
}
