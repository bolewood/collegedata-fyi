import { describe, expect, it } from "vitest";
import { readC21Counts, saneEdCounts } from "./c21-ed-counts";
import type { FieldValue } from "./types";

function vals(entries: Record<string, number>): Record<string, FieldValue> {
  return Object.fromEntries(
    Object.entries(entries).map(([id, value]) => [id, { value: String(value) }]),
  );
}

describe("saneEdCounts", () => {
  it("returns the rate when both counts are positive and admits do not exceed applicants", () => {
    expect(saneEdCounts(1942, 829)).toEqual({ applied: 1942, admitted: 829, rate: 829 / 1942 });
  });

  it("drops zeros, inverted counts, date-part leaks, and ED admits above the overall admitted total", () => {
    expect(saneEdCounts(0, 10)).toBeNull();
    expect(saneEdCounts(100, 0)).toBeNull();
    expect(saneEdCounts(100, 120)).toBeNull();
    expect(saneEdCounts(6013, 1)).toBeNull();
    expect(saneEdCounts(400, 200, 150)).toBeNull();
    expect(saneEdCounts(400, 200, 250)).toEqual({ applied: 400, admitted: 200, rate: 0.5 });
  });
});

describe("readC21Counts", () => {
  it("reads 2023-24 / 2024-25 counts at C.2106 / C.2107", () => {
    const counts = readC21Counts({
      values: vals({ "C.2106": 1942, "C.2107": 829 }),
      schemaVersion: "2024-25",
      producer: "tier4_docling",
      yearStart: 2024,
    });
    expect(counts).toEqual({ applied: 1942, admitted: 829, rate: 829 / 1942 });
  });

  it("reads 2025-26 counts at C.2110 / C.2111, not the date parts that took 2106/2107", () => {
    const counts = readC21Counts({
      values: vals({
        "C.2106": 11,
        "C.2107": 1,
        "C.2110": 2100,
        "C.2111": 400,
      }),
      schemaVersion: "2025-26",
      producer: "tier4_docling",
      yearStart: 2025,
    });
    expect(counts).toEqual({ applied: 2100, admitted: 400, rate: 400 / 2100 });
  });

  it("reads older files that the cleaner labeled 2025-26 at C.2106 / C.2107", () => {
    const counts = readC21Counts({
      values: vals({ "C.2106": 980, "C.2107": 410 }),
      schemaVersion: null,
      producer: "tier4_docling",
      yearStart: 2023,
    });
    expect(counts).toEqual({ applied: 980, admitted: 410, rate: 410 / 980 });
  });

  it("does not treat 2025-26 date parts as early-decision counts", () => {
    expect(
      readC21Counts({
        values: vals({ "C.2201": 1, "C.2204": 1 }),
        schemaVersion: "2024-25",
        producer: "tier4_docling",
        yearStart: 2024,
      }),
    ).toBeNull();
  });

  it("returns null when the extract has no C1 mapping", () => {
    expect(
      readC21Counts({
        values: vals({ "C.2106": 100, "C.2107": 20 }),
        schemaVersion: null,
        producer: "tier2_acroform",
        yearStart: 2024,
      }),
    ).toBeNull();
  });

  it("recovers counts printed next to the C21 labels in markdown", () => {
    expect(
      readC21Counts({
        values: {},
        schemaVersion: null,
        producer: "tier4_docling",
        yearStart: 2022,
        markdown: `Number of early decision applications received by your institution: 1,009
Number of applicants admitted under early decision plan: 267
Please provide significant details about your early decision plan:
Applicants must state in writing that they will enroll if admitted.
## C22. Early action
`,
      }),
    ).toEqual({ applied: 1009, admitted: 267, rate: 267 / 1009 });
  });

  it("reads two numbers after both labels when the values sit on later lines", () => {
    expect(
      readC21Counts({
        values: {},
        schemaVersion: null,
        producer: "tier4_docling",
        yearStart: 2023,
        markdown: `Number of early decision applications received by your institution: Number of applicants admitted under early decision plan:
| 833 |
| 363 |
Please provide significant details about your early decision plan:
Early Decision applicants must meet the 1/15 application deadline.
`,
      }),
    ).toEqual({ applied: 833, admitted: 363, rate: 363 / 833 });
  });

  it("prefers markdown when the field pair is a date-part leak", () => {
    expect(
      readC21Counts({
        values: vals({ "C.2106": 6013, "C.2107": 1 }),
        schemaVersion: "2024-25",
        producer: "tier4_docling",
        yearStart: 2024,
        markdown: `Number of early decision applications received by your institution
6013
Number of applicants admitted under early decision plan
1042
Please provide significant details about your early decision plan:
`,
      }),
    ).toEqual({ applied: 6013, admitted: 1042, rate: 1042 / 6013 });
  });
});
