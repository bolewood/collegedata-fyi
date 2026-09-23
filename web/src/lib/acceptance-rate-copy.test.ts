import { describe, expect, it } from "vitest";
import fixture from "./__fixtures__/acceptance-2024-plus.json";
import { buildAcceptanceHistory, readAcceptanceYear, type HistoryDocument } from "./acceptance-history";
import {
  TITLE_MAX,
  KICKER,
  acceptanceDescription,
  acceptanceTitle,
  applicationsSentence,
  degradedNote,
  fallLabel,
  gapLabel,
  gapSentence,
  leadSentences,
  pct,
  possessive,
  relatedLinks,
  reportLabel,
  sectionHeading,
  shortFall,
  sourceNote,
  DESCRIPTION_MAX,
  dominantChange,
  turningPoint,
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
    source_storage_path: `x/${year}/x.pdf`,
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

function label(start: number): string {
  return `${start}-${String((start + 1) % 100).padStart(2, "0")}`;
}

/** [yearStart, applied, admitted] triples, any order; null counts = unreadable report. */
function history(rows: [number, number | null, number | null][]) {
  return buildAcceptanceHistory(
    [...rows]
      .sort((a, b) => b[0] - a[0])
      .map(([start, applied, admitted]) => ({
        doc: doc(label(start)),
        extract: applied == null || admitted == null ? null : extract(applied, admitted),
      })),
  );
}

// Production values (validated against the schools' files).
const duke = history([
  [2024, 51795, 2957], [2023, 46366, 3145], [2021, null, null],
  [2020, 39603, 3085], [2019, 41471, 3190], [2018, 35767, 3189],
]);
const brown = history([
  [2025, 42774, 2710], [2024, 48904, 2638], [2023, 51316, 2686], [2022, 50649, 2562],
  [2021, 46568, 2568], [2020, 36793, 2822], [2019, 38674, 2733], [2018, 35437, 2718],
]);
const vt = history([[2025, 57755, 31515], [2024, 52296, 28758], [2023, 47207, 26923]]);
const northeastern = history([
  [2024, 98425, 5133], [2023, 96631, 5459], [2022, 91000, 6191], [2021, 75244, 13829], [2020, 64459, 13199],
]);

const haverford = history([
  [2025, 6730, 896], [2024, 7341, 908], [2023, 6391, 825], [2022, 5657, 804],
  [2021, 5332, 951], [2020, 4530, 826], [2019, 4963, 810], [2018, 4672, 878],
]);

// Hub display names of the 20 pilot schools (newest report's name).
const PILOT_NAMES = [
  "Virginia Tech", "Haverford College", "Brown University", "Northeastern University", "Duke University",
  "University of Pennsylvania", "Harvard University", "Princeton University", "Johns Hopkins University",
  "Northwestern University", "Emory University", "Rice University", "University of Notre Dame",
  "Georgetown University", "New York University", "Bowdoin College", "Amherst College", "Hamilton College",
  "University of Richmond", "Bates College",
];

const EXTRA_BANNED = ["odds", "chance", "selective", "best ", "top ", "easy to get", "hard to get", "parsed", "projection", "because", "due to", "driven by", "after ", "as a result", "led to", "thanks to"];

describe("lead: answer first, then history", () => {
  it("Duke: no turning point, applications span, missing years disclosed", () => {
    expect(leadSentences("Duke University", duke)).toEqual([
      "Duke University admitted 5.7% of first-year applicants for fall 2024 (2,957 of 51,795), down from 8.9% for fall 2018.",
      "Applications rose from 35,767 to 51,795 over that span.",
      "Usable figures for fall 2021 and fall 2022 are not in our archive.",
    ]);
  });

  it("Brown: names the low and the latest application drop", () => {
    expect(leadSentences("Brown University", brown)).toEqual([
      "Brown University admitted 6.3% of first-year applicants for fall 2025 (2,710 of 42,774).",
      "That is up from a low of 5.1% for fall 2022 and down from 7.7% for fall 2018.",
      "Applications peaked at 51,316 for fall 2023 and fell 12.5% for fall 2025, to 42,774.",
    ]);
  });

  it("Virginia Tech (3 years): answer plus the plain year-over-year change", () => {
    expect(leadSentences("Virginia Tech", vt)).toEqual([
      "Virginia Tech admitted 54.6% of first-year applicants for fall 2025 (31,515 of 57,755), down from 57.0% for fall 2023.",
      "Applications rose 10.4% for fall 2025, to 57,755.",
    ]);
  });

  it("Northeastern: names the one year that made most of the drop", () => {
    expect(leadSentences("Northeastern University", northeastern)).toEqual([
      "Northeastern University admitted 5.2% of first-year applicants for fall 2024 (5,133 of 98,425), down from 20.5% for fall 2020.",
      "Most of the drop came in one year, from 18.4% for fall 2021 to 6.8% for fall 2022: admits fell from 13,829 to 6,191, while applications rose 20.9%.",
      "Applications rose from 64,459 to 98,425 over that span.",
    ]);
  });

  it("Haverford: a low in the previous year reads as part of the answer", () => {
    expect(leadSentences("Haverford College", haverford)).toEqual([
      "Haverford College admitted 13.3% of first-year applicants for fall 2025 (896 of 6,730), up from 12.4% for fall 2024, the lowest in the eight years shown.",
      "Applications fell 8.3% for fall 2025, to 6,730.",
    ]);
  });

  it("uses one decimal for every rate", () => {
    const text = leadSentences("Northeastern University", northeastern).join(" ");
    expect(text).toContain("5.2%");
    expect(text).toContain("20.5%");
    expect(text).not.toMatch(/\b\d{2}%/);
    expect(pct(0.2)).toBe("20.0%");
  });
});

describe("turning points", () => {
  it("finds an interior low below both ends", () => {
    expect(turningPoint(brown)).toMatchObject({ kind: "low", row: { yearStart: 2022 } });
  });

  it("finds an interior high above both ends", () => {
    const h = history([[2025, 100, 10], [2024, 100, 30], [2023, 100, 20], [2022, 100, 12]]);
    expect(turningPoint(h)).toMatchObject({ kind: "high", row: { yearStart: 2024 } });
    expect(leadSentences("X College", h)[0]).toBe(
      "X College admitted 10.0% of first-year applicants for fall 2025 (10 of 100), down from 30.0% for fall 2024, the highest in the four years shown.",
    );
    const earlier = history([[2025, 100, 10], [2024, 100, 20], [2023, 100, 30], [2022, 100, 12]]);
    expect(leadSentences("X College", earlier)[1]).toBe(
      "That is down from a high of 30.0% for fall 2023 and down from 12.0% for fall 2022.",
    );
    expect(dominantChange(vt)).toBeNull();
  });

  it("returns none for a series that keeps one direction overall", () => {
    expect(turningPoint(duke)).toBeNull();
    expect(turningPoint(northeastern)).toBeNull();
  });

  it("ignores differences that vanish at one decimal", () => {
    const h = history([[2025, 10000, 1001], [2024, 10000, 1000], [2023, 10000, 1002]]);
    expect(turningPoint(h)).toBeNull();
    expect(leadSentences("X College", h)[0]).toContain("the same as 10.0% for fall 2023");
  });

  it("picks the extreme farther from the latest rate when both exist", () => {
    const h = history([[2025, 100, 20], [2024, 100, 5], [2023, 100, 50], [2022, 100, 25]]);
    expect(turningPoint(h)).toMatchObject({ kind: "high", row: { yearStart: 2023 } });
  });
});

describe("dominant single-year change", () => {
  it("fires at >= 60% of the span's change, consecutive years only", () => {
    expect(dominantChange(northeastern)).toMatchObject({ from: { yearStart: 2021 }, to: { yearStart: 2022 } });
    expect(dominantChange(duke)).toBeNull();
    // 40.0% -> 30.0% -> 20.0% -> 10.0%: each step is a third of the change.
    expect(dominantChange(history([[2025, 100, 10], [2024, 100, 20], [2023, 100, 30], [2022, 100, 40]]))).toBeNull();
    // The big step spans a gap year, so it is not one year.
    const gapped = history([[2025, 100, 10], [2024, 100, 11], [2022, 100, 40], [2021, 100, 41]]);
    expect(dominantChange(gapped)).toBeNull();
  });

  it("does not fire when the series turns (the drop is not one-directional)", () => {
    expect(turningPoint(brown)).not.toBeNull();
    expect(dominantChange(brown)).toBeNull();
  });

  it("phrases a rise the same way", () => {
    const h = history([[2025, 1000, 400], [2024, 1000, 380], [2023, 1000, 150], [2022, 1000, 140]]);
    expect(leadSentences("X College", h)[1]).toBe(
      "Most of the rise came in one year, from 15.0% for fall 2023 to 38.0% for fall 2024: admits rose from 150 to 380, while applications held at 1,000.",
    );
  });
});

describe("peaks and lows are true extremes of the years shown", () => {
  it("says 'in the years shown' when the history has gaps", () => {
    const h = history([[2025, 900, 90], [2024, 1000, 90], [2023, 1200, 90], [2021, 800, 90], [2020, 700, 90]]);
    expect(applicationsSentence(h)).toBe(
      "Applications peaked at 1,200 for fall 2023 in the years shown and fell 10.0% for fall 2025, to 900.",
    );
    const low = history([[2025, 100, 30], [2024, 100, 20], [2022, 100, 5], [2021, 100, 25]]);
    expect(leadSentences("X College", low)[1]).toBe(
      "That is up from a low of 5.0% for fall 2022 (the lowest in the years shown) and up from 25.0% for fall 2021.",
    );
  });

  it("says 'were N, up x%' when the latest change moves back toward the peak", () => {
    // Georgetown: peak 27,506 (fall 2021), 26,131 -> 26,822 for fall 2025.
    const h = history([[2025, 26822, 3618], [2024, 26131, 3374], [2023, 25485, 3334], [2022, 26638, 3257], [2021, 27506, 3301], [2020, 21190, 3561]]);
    expect(applicationsSentence(h)).toBe(
      "Applications peaked at 27,506 for fall 2021 and were 26,822 for fall 2025, up 2.6% from fall 2024.",
    );
  });

  it("never names a peak that is not the maximum", () => {
    const h = history([[2025, 2000, 90], [2024, 1500, 90], [2023, 1800, 90], [2022, 1000, 90]]);
    expect(applicationsSentence(h)).toBe("Applications rose from 1,000 to 2,000 over that span.");
  });
});

describe("missing years", () => {
  it("lists every missing fall between the first and latest usable year", () => {
    expect(gapSentence(duke)).toBe("Usable figures for fall 2021 and fall 2022 are not in our archive.");
    const one = history([[2025, 100, 10], [2024, 100, 10], [2022, 100, 10]]);
    expect(gapSentence(one)).toBe("Usable figures for fall 2023 are not in our archive.");
    expect(gapSentence(brown)).toBeNull();
  });

  it("labels gap rows by what the archive holds", () => {
    expect(gapLabel(true)).toBe("Report on file; counts not usable");
    expect(gapLabel(false)).toBe("No report in our archive");
  });

  it("keeps the applications sentence off when years are not consecutive at the end", () => {
    const h = history([[2025, 200, 10], [2023, 100, 10], [2022, 100, 10], [2021, 100, 10]]);
    expect(applicationsSentence(h)).toBe("Applications rose from 100 to 200 over that span.");
  });
});

describe("labels, title, and metadata", () => {
  it("maps each report to the fall class it counts", () => {
    const latest = brown.years[0];
    expect(latest.year).toBe("2025-26");
    expect(fallLabel(latest)).toBe("Fall 2025");
    expect(reportLabel("2024-25")).toBe("2024–25 report");
    expect(shortFall(2018)).toBe("’18");
    expect(sectionHeading("Duke University", duke)).toBe("Duke University’s acceptance rate, fall 2018–2024");
    expect(sectionHeading("Virginia Tech", vt)).toBe("Virginia Tech first-year admissions, fall 2023–2025");
  });

  it("uses one title pattern, falling back only for long names", () => {
    expect(acceptanceTitle("Brown University", brown)).toBe("Brown University Acceptance Rate: 6.3% for Fall 2025");
    expect(acceptanceTitle("Virginia Tech", vt)).toBe("Virginia Tech Acceptance Rate: 54.6% for Fall 2025");
    const long = "Virginia Polytechnic Institute and State University";
    expect(acceptanceTitle(long, vt)).toBe(`${long} Acceptance Rate by Year`);
    for (const name of PILOT_NAMES) {
      expect(acceptanceTitle(name, brown)).toBe(`${name} Acceptance Rate: 6.3% for Fall 2025`);
      expect(acceptanceTitle(name, brown).length).toBeLessThanOrEqual(TITLE_MAX);
    }
  });

  it("describes with the answer and how far back the figures go", () => {
    expect(acceptanceDescription("Brown University", brown)).toBe(
      "Brown University admitted 6.3% of first-year applicants for fall 2025 (2,710 of 42,774). Figures for each year since fall 2018, with source files.",
    );
    expect(acceptanceDescription("Duke University", duke)).toBe(
      "Duke University admitted 5.7% of first-year applicants for fall 2024 (2,957 of 51,795). Figures back to fall 2018, with source files.",
    );
    expect(possessive("Williams")).toBe("Williams’");
  });

  it("caps descriptions at 155 characters, cutting whole sentences only", () => {
    const names = [
      ...PILOT_NAMES,
      "Virginia Polytechnic Institute and State University",
      "The University of North Carolina at Chapel Hill and Affiliated Professional Programs",
      "A".repeat(140),
    ];
    for (const name of names) {
      for (const h of [duke, brown, vt, northeastern, haverford]) {
        const text = acceptanceDescription(name, h);
        expect(text.length).toBeLessThanOrEqual(DESCRIPTION_MAX);
        expect(text.endsWith(".")).toBe(true);
        const latest = h.years[0];
        expect(text).toContain(pct(latest.rate));
      }
    }
  });

  it("names related links plainly", () => {
    expect(relatedLinks("Duke University", "2024-25")).toEqual({
      hub: "Duke University overview",
      latest: "Duke University’s 2024–25 Common Data Set",
    });
  });

  it("never uses banned, advice, odds, or causal wording", () => {
    const copy = [
      ...[duke, brown, vt, northeastern].flatMap((h) => [
        acceptanceTitle("Duke University", h),
        acceptanceDescription("Duke University", h),
        ...leadSentences("Duke University", h),
        sectionHeading("Duke University", h),
      ]),
      KICKER,
      sourceNote("Duke University"),
      gapLabel(true),
      gapLabel(false),
      degradedNote(),
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
