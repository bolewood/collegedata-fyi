import { describe, expect, it } from "vitest";
import { buildReconstructedTables } from "./reconstructed-tables";
import type { FieldValue } from "./types";

function field(value: string, question = "Question", value_type = "Number"): FieldValue {
  return { value, question, value_type };
}

describe("buildReconstructedTables", () => {
  it("builds a 2025-style C1 table and leaves missing schema cells explicit", () => {
    const tables = buildReconstructedTables({
      "C.101": field("1200", "Total first-time, first-year males who applied"),
      "C.102": field("1300", "Total first-time, first-year females who applied"),
      "C.116": field("2500", "Total first-time, first-year students who applied"),
      "C.117": field("300", "Total first-time, first-year students who were admitted"),
    });

    const c1 = tables.find((table) => table.key === "c1-admissions");
    expect(c1?.columns).toEqual(["Males", "Females", "Unknown sex", "Total"]);
    expect(c1?.rows[0].cells.map((cell) => cell.display)).toEqual([
      "1,200",
      "1,300",
      "Not reported",
      "2,500",
    ]);
    expect(c1?.usedFieldIds).toContain("C.101");
    expect(c1?.usedFieldIds).toContain("C.117");
  });

  it("uses the 2024 C1 layout when the question text exposes another gender fields", () => {
    const tables = buildReconstructedTables({
      "C.101": field("1200", "Total first-time, first-year men who applied"),
      "C.103": field("3", "Total first-time, first-year another gender who applied"),
      "C.104": field("2", "Total first-time, first-year unknown gender who applied"),
      "C.117": field("2505", "Total first-time, first-year students who applied"),
    });

    const c1 = tables.find((table) => table.key === "c1-admissions");
    expect(c1?.columns).toEqual([
      "Men",
      "Women",
      "Another gender",
      "Unknown gender",
      "Total",
    ]);
    expect(c1?.rows[0].cells.map((cell) => cell.display)).toEqual([
      "1,200",
      "Not reported",
      "3",
      "2",
      "2,505",
    ]);
  });

  it("builds C9 submission and percentile tables", () => {
    const tables = buildReconstructedTables({
      "C.901": field("60.5", "Percent Submitting SAT Scores", "Whole Number or Round to Nearest Tenth"),
      "C.903": field("600", "Number Submitting SAT Scores"),
      "C.905": field("1400", "SAT Composite: 25th Percentile", "Whole Number or Round to Nearest Tenth"),
      "C.906": field("1500", "SAT Composite: 50th Percentile", "Whole Number or Round to Nearest Tenth"),
      "C.907": field("1560", "SAT Composite: 75th Percentile", "Whole Number or Round to Nearest Tenth"),
    });

    const submission = tables.find((table) => table.key === "c9-submission");
    const percentiles = tables.find((table) => table.key === "c9-percentiles");

    expect(submission?.rows[0].cells.map((cell) => cell.display)).toEqual([
      "60.5",
      "600",
    ]);
    expect(percentiles?.rows[0].cells.map((cell) => cell.display)).toEqual([
      "1,400",
      "1,500",
      "1,560",
    ]);
  });
});
