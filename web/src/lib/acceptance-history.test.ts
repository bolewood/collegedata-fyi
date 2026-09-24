import { describe, expect, it } from "vitest";
import {
  ACCEPTANCE_HISTORY_MIN_YEAR_START,
  acceptanceEligibility,
  buildAcceptanceHistory,
  hasEarlyDecision,
  isHistoryCandidate,
  readAcceptanceYear,
  type HistoryDocument,
  type HistoryExtract,
} from "./acceptance-history";
import { c1MarkdownRows, readC1Totals } from "./c1-headline-totals";
import type { FieldValue } from "./types";

function doc(year: string, overrides: Partial<HistoryDocument> = {}): HistoryDocument {
  return {
    document_id: `doc-${year}`,
    canonical_year: year,
    extraction_status: "extracted",
    data_quality_flag: null,
    sub_institutional: null,
    source_storage_path: `school/${year}/file.pdf`,
    source_format: "pdf_flat",
    ...overrides,
  };
}

function vals(entries: Record<string, number | string>): Record<string, FieldValue> {
  return Object.fromEntries(
    Object.entries(entries).map(([id, value]) => [id, { value: String(value) }]),
  );
}

/** Legacy Tier 4 extract: no schema_version, 2025-26 ids. */
function legacy(entries: Record<string, number | string>, markdown?: string): HistoryExtract {
  return { values: vals(entries), schemaVersion: null, producer: "tier4_docling", markdown };
}

// Real shapes from production (see docs/prd/assets/031/m0-lite-validation.md).
const DUKE_2018 = legacy({
  "C.101": 17270, "C.102": 18497, "C.104": 1578, "C.105": 1611, "C.107": 836, "C.108": 909,
}, "| Total full-time, first-time, first-year (freshman) men who enrolled | 836 |\n| Total full-time, first-time, first-year (freshman) women who enrolled | 909 |");
const COLORADO_MINES_SHAPE = legacy({
  // More men than women: the old default spec returned men only.
  "C.101": 8726, "C.102": 3935, "C.104": 3888, "C.105": 2340,
}, "| Total first-time, first-year (freshman) men who applied | 8726 |");
const UCLA_2022_MD = [
  "| Total first-time, first-year men who applied | 65852 |",
  "| Total first-time, first-year women who applied | 78381 |",
  "| Total first-time, first-year of another gender who applied | 5582 |",
  "| Total first-time, first-year men who were admitted | 4910 |",
  "| Total first-time, first-year women who were admitted | 7593 |",
  "| Total first-time, first-year of another gender who were admitted | 341 |",
  "| Total full-time, first-time, first-year men who enrolled | 2371 |",
  "| Total part-time, first-time, first-year men who enrolled | 2 |",
  "| Total full-time, first-time, first-year women who enrolled | 4001 |",
  "| Total part-time, first-time, first-year women who enrolled | 11 |",
  "| Total full-time, first-time, first-year of another gender who enrolled | 77 |",
  "| Total part-time, first-time, first-year of another gender who enrolled | 0 |",
].join("\n");
const UCLA_2022 = legacy({
  "C.101": 65852, "C.102": 78381, "C.104": 4910, "C.105": 7593, "C.107": 2371, "C.108": 4001,
  "C.110": 2371, "C.111": 2, "C.112": 4001, "C.113": 11,
}, UCLA_2022_MD);

describe("readC1Totals: year-aware C1 mapping", () => {
  it("sums men and women for legacy extracts instead of returning one sex", () => {
    const reading = readC1Totals({ ...COLORADO_MINES_SHAPE, yearStart: 2018 });
    expect(reading.totals).toEqual({ applied: 12661, admitted: 6228, enrolled: null });
  });

  it("uses the 2023-24 numbering (totals at C.117-C.119)", () => {
    const reading = readC1Totals({
      values: vals({
        "C.101": 17373, "C.102": 21249, "C.103": 9, "C.105": 994, "C.106": 855, "C.107": 0,
        "C.109": 885, "C.111": 741, "C.117": 38631, "C.118": 1849, "C.119": 1626,
      }),
      schemaVersion: "2023-24",
      producer: "tier4_docling",
      yearStart: 2023,
    });
    expect(reading.totals).toEqual({ applied: 38631, admitted: 1849, enrolled: 1626 });
  });

  it("excludes older XLSX files read with the 2025-26 cell map", () => {
    const reading = readC1Totals({
      values: vals({ "C.101": 12583, "C.102": 11163, "C.105": 2972 }),
      schemaVersion: "2025-26",
      producer: "tier1_xlsx",
      yearStart: 2021,
    });
    expect(reading.template).toBeNull();
  });

  it("recovers another-gender and part-time rows the label map missed (UCLA 2022-23)", () => {
    const reading = readC1Totals({ ...UCLA_2022, yearStart: 2022 });
    // Source file: 65,852 + 78,381 + 5,582; 4,910 + 7,593 + 341; 2,373 + 4,012 + 77.
    expect(reading.totals).toEqual({ applied: 149815, admitted: 12844, enrolled: 6462 });
  });

  it("reads the value column, not a trailing subtotal", () => {
    const rows = c1MarkdownRows(
      "| Total part-time, first-time, first-year (freshman) men who enrolled | - | 2,051 |\n" +
        "| Total part-time, first-time, first-year (freshman) women who enrolled | - | 2,051 |",
    );
    expect(rows.partTimeMen).toBeNull();
    expect(rows.partTimeRows).toEqual({ men: true, women: true });
  });

  it("does not trust the residency table's in-state row as the college total", () => {
    const reading = readC1Totals({
      ...legacy({
        "C.101": 26221, "C.102": 28526, "C.103": 1003, "C.104": 16968, "C.105": 21505,
        "C.106": 696, "C.116": 48180, "C.117": 33004, "C.119": 48180, "C.120": 33004,
      }),
      yearStart: 2023,
    });
    expect(reading.totals?.applied).toBe(55750);
    expect(reading.totals?.admitted).toBe(39169);
  });

  it("drops a sum when one sex is missing (UT Austin 2018-19 shape)", () => {
    const reading = readC1Totals({
      ...legacy({ "C.102": 25681, "C.104": 8597, "C.105": 10885 }, "| x |"),
      yearStart: 2018,
    });
    expect(reading.totals?.applied).toBeNull();
  });

  it("drops sums where one column was read twice (women's-college shape)", () => {
    const reading = readC1Totals({
      ...legacy({ "C.101": 6395, "C.102": 6395, "C.104": 1379, "C.105": 1379 }, "| x |"),
      yearStart: 2019,
    });
    expect(reading.totals?.applied).toBeNull();
    expect(reading.totals?.admitted).toBeNull();
  });

  it("drops enrolled when the table lost its last part-time row", () => {
    const reading = readC1Totals({
      ...legacy(
        { "C.101": 9187, "C.102": 13685, "C.104": 1446, "C.105": 1874, "C.107": 694, "C.108": 924, "C.111": 0 },
        "| Total part-time, first-time, first-year (freshman) men who enrolled | 0 |",
      ),
      yearStart: 2018,
    });
    expect(reading.totals).toEqual({ applied: 22872, admitted: 3320, enrolled: null });
  });

  it("does not show a legacy sum with no markdown to confirm it is complete", () => {
    const reading = readC1Totals({ ...legacy({ "C.101": 100, "C.102": 120, "C.104": 10, "C.105": 12 }), yearStart: 2019 });
    expect(reading.totals).toEqual({ applied: null, admitted: null, enrolled: null });
  });

  it("does not show an AcroForm sum whose other-gender cells were never read", () => {
    const reading = readC1Totals({
      values: vals({ "C.101": 8224, "C.102": 10498, "C.105": 1919, "C.106": 2137, "C.117": 0 }),
      schemaVersion: "2024-25",
      producer: "tier2_acroform",
      yearStart: 2024,
    });
    expect(reading.totals?.applied).toBeNull();
  });
});

describe("acceptance history", () => {
  it("keeps only whole-institution, extracted, unflagged, canonical years in the checked window", () => {
    expect(isHistoryCandidate(doc("2020-21"))).toBe(true);
    expect(isHistoryCandidate(doc("2020-21", { sub_institutional: "Law" }))).toBe(false);
    expect(isHistoryCandidate(doc("2020-21", { data_quality_flag: "wrong_file" }))).toBe(false);
    expect(isHistoryCandidate(doc("2020-21", { data_quality_flag: "low_coverage" }))).toBe(false);
    expect(isHistoryCandidate(doc("2020-21", { data_quality_flag: "blank_template" }))).toBe(false);
    expect(isHistoryCandidate(doc("2020-21", { extraction_status: "pending" }))).toBe(false);
    expect(isHistoryCandidate(doc("2020-22"))).toBe(false);
    expect(isHistoryCandidate(doc(`${ACCEPTANCE_HISTORY_MIN_YEAR_START - 1}-18`))).toBe(false);
  });

  it("applies the sanity bounds", () => {
    const bad = (entries: Record<string, number>) =>
      readAcceptanceYear(doc("2019-20"), legacy(entries, "| x |"));
    expect(bad({ "C.116": 0, "C.117": 0 }).ok).toBe(false);
    expect(bad({ "C.116": 100, "C.117": 150 })).toEqual({ ok: false, reason: "admitted exceeds applied" });
    expect(bad({ "C.116": 100, "C.117": 50, "C.118": 60 })).toEqual({
      ok: false,
      reason: "enrolled exceeds admitted",
    });
    const good = bad({ "C.116": 100, "C.117": 50, "C.118": 20 });
    expect(good.ok && good.row.rate).toBe(0.5);
    expect(good.ok && good.row.yieldRate).toBe(0.4);
  });

  it("shows the school's printed total when it disagrees with the projection (Amherst 2024-25)", () => {
    const reading = readAcceptanceYear(
      doc("2024-25"),
      { values: vals({ "C.117": 13743, "C.118": 1238, "C.119": 480 }), schemaVersion: "2024-25", producer: "tier4_docling" },
      { applied: 13742, admitted: 1238, enrolled: 480 },
    );
    expect(reading.ok && reading.row.applied).toBe(13743);
    expect(reading.ok && reading.row.source).toBe("2024-25");
  });

  it("uses the projection only when the extract can't be read", () => {
    const reading = readAcceptanceYear(
      doc("2024-25"),
      { values: {}, schemaVersion: "2024-25", producer: "tier4_docling" },
      { applied: 1000, admitted: 100, enrolled: 40 },
    );
    expect(reading.ok && reading.row.source).toBe("projection");
  });

  it("falls back to the extract when the projected row is empty", () => {
    const reading = readAcceptanceYear(
      doc("2024-25"),
      { values: vals({ "C.117": 57326, "C.118": 2067, "C.119": 1693 }), schemaVersion: "2024-25", producer: "tier4_docling" },
      { applied: null, admitted: null, enrolled: null },
    );
    expect(reading.ok && [reading.row.applied, reading.row.admitted, reading.row.enrolled]).toEqual([
      57326, 2067, 1693,
    ]);
  });

  it("builds one row per year, newest first, and names gaps", () => {
    const history = buildAcceptanceHistory([
      { doc: doc("2024-25"), extract: legacy({ "C.116": 51795, "C.117": 2957 }, "| x |") },
      { doc: doc("2024-25", { document_id: "dup" }), extract: legacy({ "C.116": 1, "C.117": 1 }, "| x |") },
      { doc: doc("2023-24"), extract: legacy({ "C.116": 46366, "C.117": 3145 }, "| x |") },
      { doc: doc("2021-22"), extract: legacy({}, "") },
      { doc: doc("2018-19"), extract: DUKE_2018 },
    ]);
    expect(history.years.map((row) => row.year)).toEqual(["2024-25", "2023-24", "2018-19"]);
    expect(history.years[0].applied).toBe(51795);
    expect(history.gaps).toEqual(["2022-23", "2021-22", "2020-21", "2019-20"]);
    expect(history.excluded.map((row) => row.year)).toEqual(["2021-22"]);
    expect(history.years[2]).toMatchObject({ applied: 35767, admitted: 3189, enrolled: 1745 });
  });

  it("is eligible with 3+ usable years ending 2023-24 or later", () => {
    const years = (starts: number[]) =>
      buildAcceptanceHistory(
        starts.map((start) => ({
          doc: doc(`${start}-${String((start + 1) % 100).padStart(2, "0")}`),
          extract: legacy({ "C.116": 1000, "C.117": 100 }, "| x |"),
        })),
      );
    expect(acceptanceEligibility(years([2025, 2024, 2023])).eligible).toBe(true);
    expect(acceptanceEligibility(years([2025, 2024])).eligible).toBe(false);
    expect(acceptanceEligibility(years([2022, 2021, 2020, 2019])).eligible).toBe(false);
  });

  it("attaches C21 early-decision counts from the extract, re-checked against overall admits", () => {
    const reading = readAcceptanceYear(
      doc("2024-25"),
      {
        values: vals({ "C.117": 10000, "C.118": 1200, "C.119": 400, "C.2106": 800, "C.2107": 200 }),
        schemaVersion: "2024-25",
        producer: "tier4_docling",
      },
    );
    expect(reading.ok && reading.row.ed).toEqual({ applied: 800, admitted: 200, rate: 0.25 });
  });

  it("drops extract ED admits that exceed overall admits, then uses a sane 2024+ projection", () => {
    const reading = readAcceptanceYear(
      doc("2024-25"),
      {
        values: vals({ "C.117": 1000, "C.118": 100, "C.119": 40, "C.2106": 200, "C.2107": 150 }),
        schemaVersion: "2024-25",
        producer: "tier4_docling",
      },
      { applied: 1000, admitted: 100, enrolled: 40, edApplicants: 180, edAdmitted: 40 },
    );
    expect(reading.ok && reading.row.ed).toEqual({ applied: 180, admitted: 40, rate: 40 / 180 });
  });

  it("does not use projected ED counts before 2024-25", () => {
    const reading = readAcceptanceYear(
      doc("2023-24"),
      {
        values: vals({ "C.117": 1000, "C.118": 100, "C.119": 40 }),
        schemaVersion: "2023-24",
        producer: "tier4_docling",
      },
      { applied: 1000, admitted: 100, enrolled: 40, edApplicants: 180, edAdmitted: 40 },
    );
    expect(reading.ok && reading.row.ed).toBeNull();
  });

  it("uses 2024+ projected ED when the extract has C1 but no C21 counts", () => {
    const reading = readAcceptanceYear(
      doc("2024-25"),
      {
        values: vals({ "C.117": 1000, "C.118": 100, "C.119": 40 }),
        schemaVersion: "2024-25",
        producer: "tier4_docling",
      },
      { applied: 1000, admitted: 100, enrolled: 40, edApplicants: 180, edAdmitted: 40 },
    );
    expect(reading.ok && reading.row.ed).toEqual({ applied: 180, admitted: 40, rate: 40 / 180 });
  });

  it("hasEarlyDecision is true only when a usable C21 year is attached", () => {
    const withEd = buildAcceptanceHistory([
      {
        doc: doc("2024-25"),
        extract: {
          values: vals({ "C.117": 1000, "C.118": 100, "C.119": 40, "C.2106": 80, "C.2107": 20 }),
          schemaVersion: "2024-25",
          producer: "tier4_docling",
        },
      },
      { doc: doc("2023-24"), extract: { values: vals({ "C.117": 900, "C.118": 110, "C.119": 40 }), schemaVersion: "2023-24", producer: "tier4_docling" } },
      { doc: doc("2022-23"), extract: legacy({ "C.116": 800, "C.117": 120 }, "| x |") },
    ]);
    expect(hasEarlyDecision(withEd)).toBe(true);
    const none = buildAcceptanceHistory([
      { doc: doc("2024-25"), extract: { values: vals({ "C.117": 1000, "C.118": 100, "C.119": 40 }), schemaVersion: "2024-25", producer: "tier4_docling" } },
      { doc: doc("2023-24"), extract: { values: vals({ "C.117": 900, "C.118": 110, "C.119": 40 }), schemaVersion: "2023-24", producer: "tier4_docling" } },
      { doc: doc("2022-23"), extract: legacy({ "C.116": 800, "C.117": 120 }, "| x |") },
    ]);
    expect(hasEarlyDecision(none)).toBe(false);
  });
});
