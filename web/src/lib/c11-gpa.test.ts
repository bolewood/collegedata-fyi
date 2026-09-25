import { describe, expect, it } from "vitest";
import {
  buildGpaHistory,
  c11MarkdownBands,
  gpaEligibility,
  readC11Gpa,
  saneAverage,
  saneBands,
} from "./c11-gpa";
import type { HistoryDocument, HistoryExtract } from "./acceptance-history";
import type { FieldValue } from "./types";

function vals(entries: Record<string, number | string>): Record<string, FieldValue> {
  return Object.fromEntries(Object.entries(entries).map(([id, value]) => [id, { value: String(value) }]));
}

function bands(offset: number, percents: number[]): Record<string, number> {
  const out: Record<string, number> = {};
  percents.forEach((n, i) => {
    out[`C.11${String(offset + i).padStart(2, "0")}`] = n;
  });
  return out;
}

const HARVARD = [74.2, 18.1, 5.4, 1.6, 0.5, 0.2, 0, 0, 0];

describe("saneAverage", () => {
  it("keeps a printed 4.0-scale GPA and rescales 386 → 3.86", () => {
    expect(saneAverage(3.86)).toBe(3.86);
    expect(saneAverage(386)).toBe(3.86);
    expect(saneAverage(0)).toBeNull();
    expect(saneAverage(12)).toBeNull();
  });
});

describe("saneBands", () => {
  it("accepts a column that sums to about 100", () => {
    const percents = {
      gpa4: 74.2,
      gpa375: 18.1,
      gpa350: 5.4,
      gpa325: 1.6,
      gpa300: 0.5,
      gpa250: 0.2,
      gpa200: 0,
      gpa100: 0,
      below1: 0,
    };
    const reading = saneBands(percents, "reported");
    expect(reading?.sum).toBeCloseTo(100, 5);
    expect(reading?.column).toBe("reported");
  });

  it("drops a column that does not add to about 100", () => {
    expect(
      saneBands(
        {
          gpa4: 10,
          gpa375: 10,
          gpa350: 0,
          gpa325: 0,
          gpa300: 0,
          gpa250: 0,
          gpa200: 0,
          gpa100: 0,
          below1: 0,
        },
        "reported",
      ),
    ).toBeNull();
  });
});

describe("readC11Gpa", () => {
  it("prefers the all-enrolled column (C.1121) over the reported table", () => {
    const reading = readC11Gpa({
      values: vals({
        ...bands(1, [90, 10, 0, 0, 0, 0, 0, 0, 0]),
        ...bands(21, HARVARD),
        "C.1201": 3.86,
        "C.1202": 99,
      }),
    });
    expect(reading?.bands.column).toBe("all-enrolled");
    expect(reading?.bands.percents.gpa4).toBe(74.2);
    expect(reading?.average).toBe(3.86);
    expect(reading?.submittedPct).toBe(99);
  });

  it("falls back to C.1101 when all-enrolled is empty", () => {
    const reading = readC11Gpa({ values: vals(bands(1, HARVARD)) });
    expect(reading?.bands.column).toBe("reported");
    expect(reading?.bands.percents.gpa4).toBe(74.2);
    expect(reading?.average).toBeNull();
  });

  it("scales a column stored as 0–1 fractions", () => {
    const reading = readC11Gpa({
      values: vals(bands(1, [0.742, 0.181, 0.054, 0.016, 0.005, 0.002, 0, 0, 0])),
    });
    expect(reading?.bands.percents.gpa4).toBeCloseTo(74.2, 5);
  });

  it("drops a 2% submitted share next to a full band table", () => {
    const reading = readC11Gpa({
      values: vals({ ...bands(1, HARVARD), "C.1202": 2 }),
    });
    expect(reading?.submittedPct).toBeNull();
  });
});

describe("c11MarkdownBands", () => {
  it("reads a single-column markdown table", () => {
    const md = `
| Percent who had GPA of 4.0 | 74.2 |
| Percent who had GPA between 3.75 and 3.99 | 18.1 |
| Percent who had GPA between 3.50 and 3.74 | 5.4 |
| Percent who had GPA between 3.25 and 3.49 | 1.6 |
| Percent who had GPA between 3.00 and 3.24 | 0.5 |
| Percent who had GPA between 2.50 and 2.99 | 0.2 |
| Percent who had GPA between 2.0 and 2.49 | 0 |
| Percent who had GPA between 1.0 and 1.99 | 0 |
| Percent who had GPA below 1.0 | 0 |
C12 Average high school GPA
`;
    expect(c11MarkdownBands(md)?.percents.gpa4).toBe(74.2);
  });

  it("takes the all-enrolled number from a three-column row", () => {
    const md = `
All enrolled students
| Percent who had GPA of 4.0 | 90 | 80 | 74.2 |
| Percent who had GPA between 3.75 and 3.99 | 8 | 15 | 18.1 |
| Percent who had GPA between 3.50 and 3.74 | 2 | 4 | 5.4 |
| Percent who had GPA between 3.25 and 3.49 | 0 | 1 | 1.6 |
| Percent who had GPA between 3.00 and 3.24 | 0 | 0 | 0.5 |
| Percent who had GPA between 2.50 and 2.99 | 0 | 0 | 0.2 |
| Percent who had GPA between 2.0 and 2.49 | 0 | 0 | 0 |
| Percent who had GPA between 1.0 and 1.99 | 0 | 0 | 0 |
| Percent who had GPA below 1.0 | 0 | 0 | 0 |
`;
    expect(c11MarkdownBands(md)?.percents.gpa4).toBe(74.2);
    expect(c11MarkdownBands(md)?.column).toBe("all-enrolled");
  });
});

function doc(year: string): HistoryDocument {
  return {
    document_id: `doc-${year}`,
    canonical_year: year,
    extraction_status: "extracted",
    data_quality_flag: null,
    sub_institutional: null,
    source_storage_path: `school/${year}/file.pdf`,
    source_format: "pdf_flat",
  };
}

function extract(percents: number[], average?: number): HistoryExtract {
  return {
    values: vals({ ...bands(1, percents), ...(average != null ? { "C.1201": average } : {}) }),
    schemaVersion: "2024-25",
    producer: "tier4_docling",
  };
}

describe("gpaEligibility", () => {
  it("requires three usable C11 years, latest 2023-24+", () => {
    const history = buildGpaHistory([
      { doc: doc("2024-25"), extract: extract(HARVARD, 3.9) },
      { doc: doc("2023-24"), extract: extract(HARVARD, 3.9) },
      { doc: doc("2022-23"), extract: extract(HARVARD) },
    ]);
    expect(gpaEligibility(history)).toEqual({ eligible: true });
    expect(history.years[0].average).toBe(3.9);
    expect(history.years[2].average).toBeNull();
  });

  it("rejects two years even when both have bands", () => {
    const history = buildGpaHistory([
      { doc: doc("2024-25"), extract: extract(HARVARD) },
      { doc: doc("2023-24"), extract: extract(HARVARD) },
    ]);
    expect(gpaEligibility(history).eligible).toBe(false);
  });
});
