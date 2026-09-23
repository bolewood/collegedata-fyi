import { describe, expect, it } from "vitest";
import pilotFixture from "./__fixtures__/acceptance-pilot-histories.json";
import { buildAcceptanceHistory, type HistoryDocument } from "./acceptance-history";
import { leadSentences } from "./acceptance-rate-copy";
import { auditLead, type AuditRow } from "./acceptance-lead-audit";
import type { FieldValue } from "./types";

function label(start: number): string {
  return `${start}-${String((start + 1) % 100).padStart(2, "0")}`;
}

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

function lead(name: string, rows: AuditRow[]): string {
  const history = buildAcceptanceHistory(
    [...rows]
      .sort((a, b) => b.yearStart - a.yearStart)
      .map((row) => {
        const values: Record<string, FieldValue> = {
          "C.116": { value: String(row.applied) },
          "C.117": { value: String(row.admitted) },
        };
        return {
          doc: doc(label(row.yearStart)),
          extract: { values, schemaVersion: null, producer: "tier4_docling", markdown: "| fixture |" },
        };
      }),
  );
  return leadSentences(name, history).join(" ");
}

const pilots = pilotFixture.map((school) => ({
  ...school,
  rows: school.years.map(([yearStart, applied, admitted]) => ({ yearStart, applied, admitted })),
}));

function rows(spec: [number, number, number][]): AuditRow[] {
  return spec.map(([yearStart, applied, admitted]) => ({ yearStart, applied, admitted }));
}

describe("lead audit", () => {
  it.each(pilots.map((school) => [school.school, school] as const))("%s: every claim checks out", (_, school) => {
    const text = lead(school.name, school.rows);
    expect(auditLead(text, school.rows), text).toEqual([]);
  });

  it("keeps every pilot lead to at most four sentences", () => {
    for (const school of pilots) {
      const history = buildAcceptanceHistory(
        [...school.rows].sort((a, b) => b.yearStart - a.yearStart).map((row) => ({
          doc: doc(label(row.yearStart)),
          extract: {
            values: { "C.116": { value: String(row.applied) }, "C.117": { value: String(row.admitted) } },
            schemaVersion: null,
            producer: "tier4_docling",
            markdown: "| fixture |",
          },
        })),
      );
      expect(leadSentences(school.name, history).length, school.school).toBeLessThanOrEqual(4);
    }
  });

  const synthetic: [string, [number, number, number][]][] = [
    ["monotone fall", [[2021, 1000, 400], [2022, 1000, 300], [2023, 1000, 200], [2024, 1000, 100]]],
    ["monotone rise", [[2021, 1000, 100], [2022, 1000, 200], [2023, 1000, 300], [2024, 1000, 400]]],
    ["record low after a bump", [[2020, 1000, 90], [2021, 1000, 80], [2022, 1000, 85], [2023, 1000, 70]]],
    ["record low tied at display", [[2020, 10000, 900], [2021, 10000, 721], [2022, 10000, 800], [2023, 10000, 722]]],
    ["turn low tied in previous year", [[2019, 1000, 85], [2020, 1000, 93], [2021, 10000, 721], [2022, 10000, 722], [2023, 1000, 77]]],
    ["local low since", [[2018, 1000, 178], [2019, 1000, 121], [2020, 1000, 141], [2021, 1000, 173], [2022, 1000, 137], [2023, 1000, 130], [2024, 1000, 133], [2025, 1000, 148]]],
    ["falling above a low", [[2019, 1000, 113], [2021, 1000, 87], [2022, 1000, 73], [2023, 1000, 98], [2024, 1000, 90]]],
    ["rising below a high", [[2018, 1000, 145], [2019, 1000, 144], [2020, 1000, 168], [2021, 1000, 120], [2022, 1000, 122], [2023, 1000, 131], [2024, 1000, 129], [2025, 1000, 135]]],
    ["unchanged at display", [[2021, 10000, 1200], [2022, 10000, 900], [2023, 10000, 1000], [2024, 10000, 1004]]],
    ["with a gap", [[2018, 1000, 100], [2019, 1000, 90], [2022, 1000, 95], [2023, 1000, 80]]],
    ["applications peak and low", [[2020, 900, 90], [2021, 700, 70], [2022, 1200, 110], [2023, 1000, 100], [2024, 950, 99]]],
  ];

  it.each(synthetic)("synthetic %s: every claim checks out", (_, spec) => {
    const text = lead("X College", rows(spec));
    expect(auditLead(text, rows(spec)), text).toEqual([]);
  });

  describe("fails on the round-5 leads", () => {
    const find = (id: string) => pilots.find((school) => school.school === id)!.rows;

    it("Bates: wrong 'since' year", () => {
      const round5 =
        "Bates College admitted 14.8% of first-year applicants for fall 2025 (1,433 of 9,660), up from 13.3% for fall 2024 and from 13.0% for fall 2023, the lowest since fall 2021. It was 17.8% for fall 2018. Applications fell 3.7% for fall 2025, to 9,660 from 10,027.";
      expect(auditLead(round5, find("bates")).join(" ")).toContain("fall 2021 is not lower");
    });

    it("Amherst: hides the 7.3% low (and used the projection's count)", () => {
      const round5 =
        "Amherst College admitted 9.0% of first-year applicants for fall 2024 (1,238 of 13,742), down from 9.8% for fall 2023. It was 11.3% for fall 2019. Applications rose 8.0% for fall 2024, to 13,742 from 12,727; they peaked at 14,864 for fall 2022 in the years shown. Usable figures for fall 2020 are not in our archive.";
      const problems = auditLead(round5, find("amherst")).join(" ");
      expect(problems).toContain("series low of 7.3% is not named");
      expect(problems).toContain("answer counts do not match");
    });

    it("Northwestern: a display tie shown as a record, and 'years shown' with a gap", () => {
      const round5 =
        "Northwestern University admitted 7.7% of first-year applicants for fall 2024 (3,806 of 49,474), up from 7.2% for fall 2023, the lowest in the six years shown. It was 8.5% for fall 2018. Applications fell 4.4% for fall 2024, to 49,474 from 51,769. Usable figures for fall 2021 are not in our archive.";
      const problems = auditLead(round5, find("northwestern")).join(" ");
      expect(problems).toContain("tied years not all named");
      expect(problems).toContain('"years shown" with gaps');
    });
  });
});
