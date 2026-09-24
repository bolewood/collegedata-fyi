import { describe, expect, it } from "vitest";
import fixture from "./__fixtures__/acceptance-2024-plus.json";
import pilotFixture from "./__fixtures__/acceptance-pilot-histories.json";
import { buildAcceptanceHistory, readAcceptanceYear, type HistoryDocument } from "./acceptance-history";
import { auditLead } from "./acceptance-lead-audit";
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
  rateShape,
  firstYearSentence,
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

function historyWithEd(rows: [number, number, number, number | null, number | null][]) {
  return buildAcceptanceHistory(
    [...rows]
      .sort((a, b) => b[0] - a[0])
      .map(([start, applied, admitted, edApplied, edAdmitted]) => {
        const values: Record<string, FieldValue> = {
          "C.117": { value: String(applied) },
          "C.118": { value: String(admitted) },
        };
        if (edApplied != null) values["C.2106"] = { value: String(edApplied) };
        if (edAdmitted != null) values["C.2107"] = { value: String(edAdmitted) };
        return {
          doc: doc(label(start)),
          extract: { values, schemaVersion: "2024-25", producer: "tier4_docling" },
        };
      }),
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

// Hub display names that fit the short title pattern (newest report's name).
const PILOT_NAMES = [
  "Virginia Tech", "Haverford College", "Brown University", "Northeastern University", "Duke University",
  "University of Pennsylvania", "Harvard University", "Princeton University", "Johns Hopkins University",
  "Northwestern University", "Emory University", "Rice University", "University of Notre Dame",
  "Georgetown University", "New York University", "Bowdoin College", "Amherst College", "Hamilton College",
  "University of Richmond", "Bates College",
  "University of Florida", "Stanford University", "Wellesley College", "Lafayette College",
];

const EXTRA_BANNED = ["odds", "chance", "selective", "best ", "top ", "easy to get", "hard to get", "parsed", "projection", "because", "due to", "driven by", "after ", "as a result", "led to", "thanks to"];

function fromFixture(id: string) {
  const school = pilotFixture.find((row) => row.school === id)!;
  return history(school.years.map(([start, applied, admitted]) => [start, applied, admitted] as [number, number, number]));
}
const georgetown = fromFixture("georgetown");
const jhu = fromFixture("johns-hopkins");

describe("lead: answer first, then history", () => {
  it("Duke: latest year is a record low; long-run start in its own sentence", () => {
    expect(leadSentences("Duke University", duke)).toEqual([
      "Duke University admitted 5.7% of first-year applicants for fall 2024 (2,957 of 51,795), the lowest in the five years with figures, down from 6.8% for fall 2023.",
      "It was 8.9% for fall 2018.",
      "Applications rose from 35,767 to 51,795 over that span.",
      "Usable figures for fall 2021 and fall 2022 are not in our archive.",
    ]);
  });

  it("Brown: the most recent low the series has moved away from, then the start", () => {
    expect(leadSentences("Brown University", brown)).toEqual([
      "Brown University admitted 6.3% of first-year applicants for fall 2025 (2,710 of 42,774), up from 5.4% for fall 2024 and from a low of 5.1% for fall 2022.",
      "It was 7.7% for fall 2018.",
      "Applications fell 12.5% for fall 2025, to 42,774 from 48,904; the most in the years shown was 51,316, for fall 2023.",
    ]);
  });

  it("Georgetown: the recent low, not the one-year 2020 spike", () => {
    expect(leadSentences("Georgetown University", georgetown)).toEqual([
      "Georgetown University admitted 13.5% of first-year applicants for fall 2025 (3,618 of 26,822), up from 12.9% for fall 2024 and from a low of 12.0% for fall 2021.",
      "The high was 16.8%, for fall 2020.",
      "It was 14.5% for fall 2018.",
      "Applications rose 2.6% for fall 2025, to 26,822 from 26,131; the most in the years shown was 27,506, for fall 2021.",
    ]);
  });

  it("Virginia Tech (3 years, monotone): answer plus the plain year-over-year change", () => {
    expect(leadSentences("Virginia Tech", vt)).toEqual([
      "Virginia Tech admitted 54.6% of first-year applicants for fall 2025 (31,515 of 57,755), the lowest in the three years shown, down from 57.0% for fall 2023.",
      "Applications rose 10.4% for fall 2025, to 57,755 from 52,296.",
    ]);
  });

  it("Northeastern: monotone, with the dominant year last and both counts", () => {
    expect(leadSentences("Northeastern University", northeastern)).toEqual([
      "Northeastern University admitted 5.2% of first-year applicants for fall 2024 (5,133 of 98,425), the lowest in the five years shown, down from 20.5% for fall 2020.",
      "Applications rose from 64,459 to 98,425 over that span.",
      "Most of the drop came in one year, from 18.4% for fall 2021 to 6.8% for fall 2022, when applications rose from 75,244 to 91,000 and admits fell from 13,829 to 6,191.",
    ]);
  });

  it("Johns Hopkins: admits that rose in the drop year read as 'went from', beside applications", () => {
    const lead = leadSentences("Johns Hopkins University", jhu);
    expect(lead[lead.length - 1]).toBe(
      "Most of the drop came in one year, from 7.5% for fall 2023 to 6.4% for fall 2024, when applications rose from 38,893 to 45,895 and admits went from 2,923 to 2,954.",
    );
  });

  it("Haverford: a low in the previous year reads as part of the answer", () => {
    expect(leadSentences("Haverford College", haverford)).toEqual([
      "Haverford College admitted 13.3% of first-year applicants for fall 2025 (896 of 6,730), up from 12.4% for fall 2024, the lowest in the eight years shown.",
      "It was 18.8% for fall 2018.",
      "Applications fell 8.3% for fall 2025, to 6,730 from 7,341.",
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

describe("early decision in the lead", () => {
  it("names the latest ED rate after the overall answer", () => {
    const h = historyWithEd([
      [2025, 10000, 800, 900, 180],
      [2024, 9000, 810, 850, 170],
      [2023, 8000, 900, null, null],
    ]);
    const lead = leadSentences("Duke University", h);
    expect(lead[0]).toContain("Duke University admitted 8.0%");
    expect(lead[1]).toBe("Early decision admitted 20.0% for fall 2025 (180 of 900).");
    expect(lead.join(" ").toLowerCase()).not.toContain("early action");
  });

  it("drops the applications sentence when adding ED would overflow the lede cap", () => {
    const lead = leadSentences(
      "Northwestern University",
      historyWithEd(
        fromFixture("northwestern").years.map((row) => [
          row.yearStart,
          row.applied,
          row.admitted,
          row.yearStart === 2024 ? 2500 : null,
          row.yearStart === 2024 ? 500 : null,
        ]),
      ),
    );
    expect(lead[1]).toBe("Early decision admitted 20.0% for fall 2024 (500 of 2,500).");
    expect(lead.length).toBeLessThanOrEqual(5);
    expect(lead.join(" ").split(/\s+/).length).toBeLessThanOrEqual(75);
    expect(lead.some((s) => s.startsWith("Applications "))).toBe(false);
  });

  it("re-derives the ED sentence from C21 counts", () => {
    const rows = [
      { yearStart: 2025, applied: 10000, admitted: 800, edApplied: 900, edAdmitted: 180 },
      { yearStart: 2024, applied: 9000, admitted: 810 },
      { yearStart: 2023, applied: 8000, admitted: 900 },
    ];
    const text = leadSentences(
      "Duke University",
      historyWithEd(rows.map((r) => [r.yearStart, r.applied, r.admitted, r.edApplied ?? null, r.edAdmitted ?? null])),
    ).join(" ");
    expect(auditLead(text, rows)).toEqual([]);
  });
});

describe("rate shape: the most recent extreme the series moved away from", () => {
  it("monotone series: no turn, compare with the first year only", () => {
    expect(rateShape(northeastern)).toEqual({ kind: "monotone" });
    expect(rateShape(vt)).toEqual({ kind: "monotone" });
    expect(firstYearSentence(northeastern)).toBeNull();
  });

  it("latest year is itself the extreme: a record", () => {
    expect(rateShape(duke)).toEqual({ kind: "record", extreme: "low" });
    const high = history([[2025, 100, 40], [2024, 100, 30], [2023, 100, 35], [2022, 100, 20]]);
    expect(rateShape(high)).toEqual({ kind: "record", extreme: "high" });
    expect(leadSentences("X College", high)[0]).toBe(
      "X College admitted 40.0% of first-year applicants for fall 2025 (40 of 100), the highest in the four years shown, up from 30.0% for fall 2024.",
    );
  });

  it("picks the recent low over an older spike (Georgetown)", () => {
    expect(rateShape(georgetown)).toMatchObject({ kind: "turn", extreme: "low", row: { yearStart: 2021 }, global: true });
    expect(rateShape(brown)).toMatchObject({ kind: "turn", extreme: "low", row: { yearStart: 2022 }, global: true });
  });

  it("falling latest: the most recent high", () => {
    const h = history([[2025, 100, 15], [2024, 100, 20], [2023, 100, 30], [2022, 100, 12]]);
    expect(rateShape(h)).toMatchObject({ kind: "turn", extreme: "high", row: { yearStart: 2023 }, global: true });
    expect(leadSentences("X College", h).slice(0, 2)).toEqual([
      "X College admitted 15.0% of first-year applicants for fall 2025 (15 of 100), down from 20.0% for fall 2024 and from a high of 30.0% for fall 2023.",
      "It was 12.0% for fall 2022.",
    ]);
  });

  it("a local extreme says 'since' instead of claiming a low of all years", () => {
    // 50 -> 10 -> 40 -> 20 -> 30: rising latest; last year at or above 30.0% is fall 2023 (40.0%).
    const h = history([[2025, 100, 30], [2024, 100, 20], [2023, 100, 40], [2022, 100, 10], [2021, 100, 50]]);
    expect(rateShape(h)).toMatchObject({ kind: "turn", row: { yearStart: 2024 }, global: false, since: { yearStart: 2023 } });
    expect(leadSentences("X College", h)[0]).toBe(
      "X College admitted 30.0% of first-year applicants for fall 2025 (30 of 100), up from 20.0% for fall 2024.",
    );
    const two = history([[2025, 100, 35], [2024, 100, 25], [2023, 100, 20], [2022, 100, 40], [2021, 100, 10]]);
    expect(leadSentences("X College", two)[0]).toBe(
      "X College admitted 35.0% of first-year applicants for fall 2025 (35 of 100), up from 25.0% for fall 2024 and from 20.0% for fall 2023, the lowest since fall 2021 (10.0%).",
    );
  });

  it("ties at one decimal go to the most recent tied year", () => {
    // 11.8% for both fall 2022 and fall 2023 (Hamilton): the turn is fall 2023.
    const h = history([[2024, 1000, 136], [2023, 1000, 118], [2022, 1000, 118], [2021, 1000, 141], [2020, 1000, 184]]);
    expect(rateShape(h)).toMatchObject({ kind: "turn", row: { yearStart: 2023 } });
  });

  it("a latest year that prints the same says unchanged", () => {
    const h = history([[2025, 10000, 1001], [2024, 10000, 1000], [2023, 10000, 1200], [2022, 10000, 900]]);
    expect(rateShape(h)).toEqual({ kind: "flat" });
    expect(leadSentences("X College", h)[0]).toContain("unchanged from 10.0% for fall 2024");
  });
});

describe("dominant single-year change", () => {
  it("fires at >= 60% of the span's change, consecutive years only", () => {
    expect(dominantChange(northeastern)).toMatchObject({ from: { yearStart: 2021 }, to: { yearStart: 2022 } });
    expect(dominantChange(duke)).toBeNull();
    expect(dominantChange(vt)).toBeNull();
    // 40.0% -> 30.0% -> 20.0% -> 10.0%: each step is a third of the change.
    expect(dominantChange(history([[2025, 100, 10], [2024, 100, 20], [2023, 100, 30], [2022, 100, 40]]))).toBeNull();
    // The big step spans a gap year, so it is not one year.
    const gapped = history([[2025, 100, 10], [2024, 100, 11], [2022, 100, 40], [2021, 100, 41]]);
    expect(dominantChange(gapped)).toBeNull();
  });

  it("does not fire when the series turns", () => {
    expect(rateShape(brown).kind).toBe("turn");
    expect(dominantChange(brown)).toBeNull();
  });

  it("phrases a rise the same way, with both counts", () => {
    const h = history([[2025, 1000, 400], [2024, 1000, 380], [2023, 1000, 150], [2022, 1000, 140]]);
    const lead = leadSentences("X College", h);
    expect(lead[lead.length - 1]).toBe(
      "Most of the rise came in one year, from 15.0% for fall 2023 to 38.0% for fall 2024, when applications held at 1,000 and admits rose from 150 to 380.",
    );
  });
});

describe("peaks and lows are true extremes of the years shown", () => {
  it("says 'in the years shown' when the history has gaps", () => {
    const h = history([[2025, 900, 90], [2024, 1000, 90], [2023, 1200, 90], [2021, 800, 90], [2020, 700, 90]]);
    expect(applicationsSentence(h)).toBe(
      "Applications fell 10.0% for fall 2025, to 900 from 1,000; the most in the years with figures was 1,200, for fall 2023.",
    );
    const low = history([[2025, 100, 30], [2024, 100, 20], [2022, 100, 5], [2021, 100, 25]]);
    expect(leadSentences("X College", low)[0]).toBe(
      "X College admitted 30.0% of first-year applicants for fall 2025 (30 of 100), the highest in the four years with figures, up from 20.0% for fall 2024.",
    );
  });

  it("names the base year when the latest change moves back toward the peak", () => {
    // Georgetown: peak 27,506 (fall 2021), 26,131 -> 26,822 for fall 2025.
    const h = history([[2025, 26822, 3618], [2024, 26131, 3374], [2023, 25485, 3334], [2022, 26638, 3257], [2021, 27506, 3301], [2020, 21190, 3561]]);
    expect(applicationsSentence(h)).toBe(
      "Applications rose 2.6% for fall 2025, to 26,822 from 26,131; the most in the years shown was 27,506, for fall 2021.",
    );
  });

  it("never names a peak that is not the maximum", () => {
    const h = history([[2025, 2000, 200], [2024, 1500, 150], [2023, 1800, 180], [2022, 1000, 100]]);
    expect(applicationsSentence(h)).toBe("Applications rose from 1,000 to 2,000 over that span.");
  });
});

describe("all pilot schools", () => {
  const schools = pilotFixture.map((school) => ({
    ...school,
    history: history(school.years.map(([start, applied, admitted]) => [start, applied, admitted] as [number, number, number])),
  }));

  it("names the base-year count for every percent change, with matching arithmetic", () => {
    const change = /\b(rose|fell) (\d+\.\d)%/g;
    const based = /\b(rose|fell) (\d+\.\d)% for fall (\d{4}), to ([\d,]+) from ([\d,]+)/;
    let checked = 0;
    for (const school of schools) {
      for (const sentence of leadSentences(school.name, school.history)) {
        for (const match of sentence.matchAll(change)) {
          const rest = sentence.slice(match.index);
          const full = based.exec(rest);
          expect(full, `${school.school}: ${sentence}`).not.toBeNull();
          if (!full) continue;
          const to = Number(full[4].replace(/,/g, ""));
          const from = Number(full[5].replace(/,/g, ""));
          expect(((Math.abs(to - from) / from) * 100).toFixed(1)).toBe(full[2]);
          expect(full[1]).toBe(to > from ? "rose" : "fell");
          const years = school.years.map(([start, applied]) => ({ start, applied }));
          expect(years.find((y) => y.start === Number(full[3]))?.applied).toBe(to);
          expect(years.find((y) => y.start === Number(full[3]) - 1)?.applied).toBe(from);
          checked += 1;
        }
      }
    }
    expect(checked).toBeGreaterThanOrEqual(8);
  });

  it("puts the dominant-year sentence last (before missing years), with both counts for both years", () => {
    for (const school of schools) {
      const lead = leadSentences(school.name, school.history);
      const at = lead.findIndex((sentence) => sentence.startsWith("Most of the"));
      if (at < 0) continue;
      const dominant = dominantChange(school.history)!;
      for (const row of [dominant.from, dominant.to]) {
        expect(lead[at]).toContain(row.applied.toLocaleString("en-US"));
        expect(lead[at]).toContain(row.admitted.toLocaleString("en-US"));
      }
      expect(lead[at]).not.toMatch(/\b(because|after|as a result|due to|led to|driven by)\b/i);
      expect(lead.slice(at + 1).every((sentence) => sentence.startsWith("Usable figures"))).toBe(true);
    }
  });

  it("keeps every description within 155 characters", () => {
    for (const school of schools) {
      expect(acceptanceDescription(school.name, school.history).length).toBeLessThanOrEqual(DESCRIPTION_MAX);
    }
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

  it("adds a C21 clause to the source note only when a year has early decision", () => {
    const withEd = historyWithEd([
      [2025, 10000, 800, 900, 180],
      [2024, 9000, 810, null, null],
      [2023, 8000, 900, null, null],
    ]);
    expect(sourceNote("Duke University")).not.toContain("C21");
    expect(sourceNote("Duke University", duke)).not.toContain("C21");
    expect(sourceNote("Duke University", withEd)).toContain("section C21");
    expect(sourceNote("Duke University", withEd).toLowerCase()).not.toContain("early action");
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
