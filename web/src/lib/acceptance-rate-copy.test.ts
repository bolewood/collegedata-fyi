import { describe, expect, it } from "vitest";
import fixture from "./__fixtures__/acceptance-2024-plus.json";
import { buildAcceptanceHistory, readAcceptanceYear, type HistoryDocument } from "./acceptance-history";
import {
  DEFINITION_NOTE,
  METHOD_NOTES,
  acceptanceDescription,
  acceptanceTitle,
  degradedNote,
  leadSentences,
  possessive,
  spanSentence,
} from "./acceptance-rate-copy";
import { archiveLead, leadContainsBannedCopy, leadPlainText } from "./archive-lead";
import type { FieldValue } from "./types";

function doc(year: string): HistoryDocument {
  return {
    document_id: `doc-${year}`,
    canonical_year: year,
    extraction_status: "extracted",
    data_quality_flag: null,
    sub_institutional: null,
    source_storage_path: `duke/${year}/x.pdf`,
    source_format: "pdf_flat",
  };
}

function extract(applied: number, admitted: number, enrolled?: number) {
  const values: Record<string, FieldValue> = {
    "C.116": { value: String(applied) },
    "C.117": { value: String(admitted) },
  };
  if (enrolled != null) values["C.118"] = { value: String(enrolled) };
  return { values, schemaVersion: null, producer: "tier4_docling", markdown: "| fixture |" };
}

// Duke's usable years; 2021-22 is on file but unreadable, 2022-23 is not on file.
const duke = buildAcceptanceHistory([
  { doc: doc("2024-25"), extract: extract(51795, 2957, 1740) },
  { doc: doc("2023-24"), extract: extract(46366, 3145) },
  { doc: doc("2021-22"), extract: null },
  { doc: doc("2020-21"), extract: extract(39603, 3085, 1584) },
  { doc: doc("2019-20"), extract: extract(41471, 3190, 1730) },
  { doc: doc("2018-19"), extract: extract(35767, 3189, 1745) },
]);

const EXTRA_BANNED = ["odds", "chance", "selective", "best ", "top ", "easy to get", "hard to get", "parsed", "projection"];

describe("acceptance-rate copy", () => {
  it("titles the page with the usable span only", () => {
    expect(acceptanceTitle("Duke University", duke)).toBe(
      "Duke University Acceptance Rate by Year, 2018–2024",
    );
    const lateStart = buildAcceptanceHistory([
      { doc: doc("2025-26"), extract: extract(100, 10) },
      { doc: doc("2024-25"), extract: extract(100, 10) },
      { doc: doc("2023-24"), extract: extract(100, 10) },
      // Older reports on file whose numbers are unusable must not widen the span.
      { doc: doc("2019-20"), extract: null },
      { doc: doc("2018-19"), extract: null },
    ]);
    expect(acceptanceTitle("Virginia Tech", lateStart)).toBe(
      "Virginia Tech Acceptance Rate by Year, 2023–2025",
    );
  });

  it("leads with the span, the applications change, and the named gaps", () => {
    expect(leadSentences("Duke University", duke)).toEqual([
      "Duke University’s reports from 2018-19 to 2024-25 show the acceptance rate going from 8.9% to 5.7%.",
      "Over the same years, first-year applications went from 35,767 to 51,795.",
      "There is no usable report for 2021-22 or 2022-23, so those years are left out.",
    ]);
  });

  it("uses the site's percent style and handles a flat rate", () => {
    const flat = buildAcceptanceHistory([
      { doc: doc("2025-26"), extract: extract(1000, 551) },
      { doc: doc("2024-25"), extract: extract(1000, 548) },
      { doc: doc("2023-24"), extract: extract(1000, 552) },
    ]);
    expect(spanSentence("Bates College", flat)).toBe(
      "Bates College’s reports from 2023-24 to 2025-26 show an acceptance rate of 55% in both years.",
    );
    expect(possessive("Williams")).toBe("Williams’");
  });

  it("describes the page with the span, the latest rate, and the original files", () => {
    expect(acceptanceDescription("Duke University", duke)).toBe(
      "Duke University’s reports from 2018-19 to 2024-25 show the acceptance rate going from 8.9% to 5.7%. In 2024-25, 2,957 of 51,795 applicants were admitted (5.7%), with the original files.",
    );
  });

  it("never uses banned, advice, or odds wording", () => {
    const copy = [
      acceptanceTitle("Duke University", duke),
      acceptanceDescription("Duke University", duke),
      ...leadSentences("Duke University", duke),
      DEFINITION_NOTE,
      ...METHOD_NOTES,
      degradedNote(),
      "Acceptance rate",
      "By year",
    ].join(" ");
    expect(leadContainsBannedCopy(copy)).toBe(false);
    for (const word of EXTRA_BANNED) expect(copy.toLowerCase()).not.toContain(word);
  });
});

describe("hub summary link", () => {
  const base = {
    schoolId: "duke",
    schoolName: "Duke University",
    documents: [{ canonical_year: "2024-25", source_format: "pdf", extraction_status: "extracted" }],
    summary: [
      "In its 2024-25 report, Duke University says 51,795 first-year students applied and 2,957 were admitted, an acceptance rate of 5.7%.",
      "Compared with 2023-24, the acceptance rate went from 6.8% to 5.7%.",
    ],
  };

  it("links the first 'acceptance rate' only when the page is served, keeping the sentence identical", () => {
    const linked = archiveLead({ ...base, acceptanceRateHref: "/schools/duke/acceptance-rate" })!;
    const plain = archiveLead({ ...base, acceptanceRateHref: null })!;
    expect(leadPlainText(linked)).toBe(leadPlainText(plain));
    const links = linked.paragraphs.flat().filter((part) => part.type === "link" && part.href.includes("acceptance-rate"));
    expect(links).toEqual([{ type: "link", href: "/schools/duke/acceptance-rate", text: "acceptance rate" }]);
    expect(plain.paragraphs.flat().some((part) => part.type === "link" && part.href.includes("acceptance-rate"))).toBe(false);
  });
});

describe("2024-25+ extract reading vs school_browser_rows", () => {
  type Row = (typeof fixture)[number];
  const read = (row: Row) =>
    readAcceptanceYear(doc(row.year), {
      values: Object.fromEntries(Object.entries(row.values).map(([id, value]) => [id, { value: String(value) }])),
      schemaVersion: row.schemaVersion,
      producer: row.producer,
      markdown: row.producer === "tier4_docling" ? "| fixture |" : null,
    });

  it.each(fixture.filter((row) => row.match).map((row) => [`${row.school} ${row.year}`, row] as const))(
    "%s matches the projected row",
    (_, row) => {
      const reading = read(row);
      expect(reading.ok).toBe(true);
      if (!reading.ok) return;
      expect([reading.row.applied, reading.row.admitted, reading.row.enrolled]).toEqual([
        row.browser.applied,
        row.browser.admitted,
        row.browser.enrolled,
      ]);
    },
  );

  it("documents the known disagreements (the page shows the projected value when it is sane)", () => {
    const known = fixture.filter((row) => !row.match).map((row) => `${row.school} ${row.year}`);
    expect(known.sort()).toEqual(["amherst 2024-25", "stanford 2024-25", "ucla 2024-25"]);
  });
});
