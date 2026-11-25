// Drift check between the copy deck (docs/copy/data-quality.md) and the page. Every blockquote in the deck is a
// sentence the page says; each must still appear in the rendered page. Limits, stated plainly:
// - Text in {braces} is filled from the snapshot, so a sentence is checked only in the literal pieces between its
//   braces; a braced conditional (e.g. "{For years with another form's numbering: ...}") is not checked at all.
// - A piece under 15 characters is skipped, so a short sentence made only of such pieces isn't pinned.
// - Only blockquotes are checked: the deck's notes, headings and prose around them are not.
// - It proves every checked piece appears somewhere in the three years' pages together, not that it appears under
//   the right heading, and nothing checks that the page has no sentence the deck lacks.
// Conditional notes (hand checks, the 2023-24 counting note, the older-form notice) are rendered by building a
// snapshot that satisfies their conditions. CI runs this on a deck-only change (see .github/workflows/ci.yml).

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FIXTURE_SNAPSHOT } from "@/lib/__fixtures__/data-quality-snapshot";
import { AID_CANT_CHECK_SAMPLE, FEDERAL_DIFFERS_SAMPLE, type QualitySnapshot } from "@/lib/data-quality";

let currentParams = new URLSearchParams();
const mocks = vi.hoisted(() => ({ loadLatestSnapshot: vi.fn() }));
vi.mock("@/lib/data-quality-snapshots", () => ({ loadLatestSnapshot: mocks.loadLatestSnapshot }));
vi.mock("next/navigation", () => ({
  notFound: () => {
    throw new Error("NEXT_NOT_FOUND");
  },
  useSearchParams: () => currentParams,
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/data-quality",
}));

import DataQualityPage from "./page";

afterEach(() => {
  currentParams = new URLSearchParams();
  mocks.loadLatestSnapshot.mockReset();
});

const plain = (s: string) =>
  s
    .replace(/<\/?(a|strong|em|span|b|i)\b[^>]*>/g, "")
    .replace(/<[^>]*>/g, " ")
    .replace(/&#x27;|&#39;|’|‘/g, "'")
    .replace(/&quot;|“|”/g, '"')
    .replace(/&amp;/g, "&")
    .replace(/\*\*|\*/g, "")
    .replace(/\s+/g, " ")
    .trim();

/** The deck's page copy: each blockquote, as the pieces of literal text between its {placeholders}. */
function deckSentences(): { quote: string; pieces: string[] }[] {
  const deck = readFileSync(resolve(__dirname, "../../../../docs/copy/data-quality.md"), "utf8");
  const quotes: string[] = [];
  let current: string[] = [];
  for (const line of deck.split("\n")) {
    const m = /^\s*(-\s+)?>\s?(.*)$/.exec(line);
    if (m) {
      // A list item that opens with ">" is a new sentence even when the one before it ended on the line above.
      if (m[1] && current.length) {
        quotes.push(current.join(" "));
        current = [];
      }
      current.push(m[2]);
    } else if (current.length) {
      quotes.push(current.join(" "));
      current = [];
    }
  }
  if (current.length) quotes.push(current.join(" "));
  return quotes.map((quote) => {
    let text = quote;
    // Innermost braces first, so {, {n} with no file} and {For years ...: The {n} reports ...} both go.
    for (let prev = ""; prev !== text; ) {
      prev = text;
      text = text.replace(/\{[^{}]*\}/g, "\u0000");
    }
    return { quote, pieces: text.split("\u0000").map(plain).filter((p) => p.length >= 15) };
  });
}

/** A snapshot in which both hand-check notes apply: the pools they were drawn from are back in range. */
function snapshotWithNotes(): QualitySnapshot {
  const snap: QualitySnapshot = JSON.parse(JSON.stringify(FIXTURE_SNAPSHOT));
  const y2324 = snap.years.find((y) => y.cds_year === "2023-24")!;
  y2324.total.totals.H1.cant_check = AID_CANT_CHECK_SAMPLE.population;
  y2324.form.full_field_schema = false;
  y2324.federal_left_out.single_campus = 2;
  const other = snap.years.find((y) => y.cds_year === "2024-25")!;
  y2324.total.federal.differs = FEDERAL_DIFFERS_SAMPLE.populationValues - other.total.federal.differs;
  return snap;
}

function renderedCorpus(): string {
  const snap = snapshotWithNotes();
  mocks.loadLatestSnapshot.mockReturnValue(snap);
  const texts = snap.years.map((y) => {
    currentParams = new URLSearchParams(`year=${y.cds_year}`);
    return plain(renderToStaticMarkup(<DataQualityPage />));
  });
  return texts.join(" ");
}

describe("copy deck and page", () => {
  it("finds the deck's page copy (a parse that finds nothing would pass anything)", () => {
    const sentences = deckSentences();
    expect(sentences.length).toBeGreaterThan(20);
    for (const s of sentences) expect(s.pieces.length, `no literal text in: ${s.quote}`).toBeGreaterThan(0);
  });

  it("still says every sentence the deck marks as page copy", () => {
    const corpus = renderedCorpus();
    const missing = deckSentences().flatMap((s) => s.pieces.filter((p) => !corpus.includes(p)).map((p) => `${p}  [in: ${s.quote.slice(0, 50)}]`));
    expect(missing).toEqual([]);
  });
});
