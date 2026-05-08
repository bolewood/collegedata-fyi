import { describe, expect, it } from "vitest";
import { buildReconstructedTables } from "./reconstructed-tables";
import type { FieldValue } from "./types";

function field(value: string, question = "Question", value_type = "Number"): FieldValue {
  return { value, question, value_type };
}

describe("buildReconstructedTables", () => {
  it("builds 2025-style B1 undergraduate, graduate, and overall enrollment tables", () => {
    const tables = buildReconstructedTables({
      "B.101": field("100", "Degree-seeking, first-time first-year students: males"),
      "B.126": field("140", "Degree-seeking, first-time first-year students: females"),
      "B.151": field("5", "Degree-seeking, first-time first-year students: Unknown"),
      "B.113": field("500", "Total undergraduate students: males"),
      "B.138": field("600", "Total undergraduate students: females"),
      "B.163": field("10", "Total undergraduate students: Unknown"),
      "B.176": field("1110", "Total all undergraduates"),
      "B.125": field("800", "Total All Students: males"),
      "B.150": field("900", "Total All Students: females"),
      "B.175": field("12", "Total All Students: Unknown"),
      "B.178": field("1712", "Grand Total All Students"),
    });

    const undergrad = tables.find((table) => table.key === "b1-undergraduate");
    const overall = tables.find((table) => table.key === "b1-overall");

    expect(undergrad?.columns).toEqual(["Males", "Females", "Unknown", "Total"]);
    expect(undergrad?.rows[0].cells.map((cell) => cell.display)).toEqual([
      "100",
      "140",
      "5",
      "Not reported",
    ]);
    expect(undergrad?.rows.at(-1)?.cells.map((cell) => cell.display)).toEqual([
      "500",
      "600",
      "10",
      "1,110",
    ]);
    expect(overall?.rows.at(-1)?.cells.map((cell) => cell.display)).toEqual([
      "800",
      "900",
      "12",
      "1,712",
    ]);
    expect(undergrad?.usedFieldIds).toContain("B.176");
  });

  it("builds 2024-style B1 tables with another gender columns", () => {
    const tables = buildReconstructedTables({
      "B.101": field("100", "Degree-seeking, first-time first-year students: men"),
      "B.102": field("120", "Degree-seeking, first-time first-year students: women"),
      "B.103": field("2", "Degree-seeking, first-time first-year students: another gender"),
      "B.104": field("3", "Degree-seeking, first-time first-year students: unknown"),
      "B.149": field("500", "Total undergraduate students: men"),
      "B.150": field("600", "Total undergraduate students: women"),
      "B.151": field("4", "Total undergraduate students: another gender"),
      "B.152": field("5", "Total undergraduate students: unknown"),
      "B.193": field("1109", "Total all undergraduates"),
    });

    const undergrad = tables.find((table) => table.key === "b1-undergraduate");

    expect(undergrad?.columns).toEqual([
      "Men",
      "Women",
      "Another gender",
      "Unknown",
      "Total",
    ]);
    expect(undergrad?.rows[0].cells.map((cell) => cell.display)).toEqual([
      "100",
      "120",
      "2",
      "3",
      "Not reported",
    ]);
    expect(undergrad?.rows.at(-1)?.cells.map((cell) => cell.display)).toEqual([
      "500",
      "600",
      "4",
      "5",
      "1,109",
    ]);
  });

  it("builds B2 as a race and ethnicity cohort table", () => {
    const tables = buildReconstructedTables({
      "B.201": field("25", "Nonresidents"),
      "B.202": field("80", "Hispanic/Latino"),
      "B.211": field("120", "Nonresidents"),
      "B.212": field("420", "Hispanic/Latino"),
      "B.221": field("150", "Nonresidents"),
      "B.222": field("500", "Hispanic/Latino"),
      "B.230": field("2500", "TOTAL"),
    });

    const b2 = tables.find((table) => table.key === "b2-race-ethnicity");

    expect(b2?.columns).toEqual([
      "First-time first-year",
      "Degree-seeking undergraduates",
      "Total undergraduates",
    ]);
    expect(b2?.rows[0].cells.map((cell) => cell.display)).toEqual([
      "25",
      "120",
      "150",
    ]);
    expect(b2?.rows[1].cells.map((cell) => cell.display)).toEqual([
      "80",
      "420",
      "500",
    ]);
    expect(b2?.rows.at(-1)?.cells.map((cell) => cell.display)).toEqual([
      "Not reported",
      "Not reported",
      "2,500",
    ]);
    expect(b2?.usedFieldIds).toContain("B.230");
  });

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

  it("builds C7 as a selected-choice matrix", () => {
    const tables = buildReconstructedTables({
      "C.701": field("Very Important", "Rigor of secondary school record", "Text"),
      "C.703": field("Considered", "Academic GPA", "Text"),
    });

    const c7 = tables.find((table) => table.key === "c7-factors");
    expect(c7?.columns).toEqual([
      "Very important",
      "Important",
      "Considered",
      "Not considered",
    ]);
    expect(c7?.rows[0].cells.map((cell) => cell.display)).toEqual([
      "Yes",
      "—",
      "—",
      "—",
    ]);
    expect(c7?.rows[2].cells.map((cell) => cell.display)).toEqual([
      "—",
      "—",
      "Yes",
      "—",
    ]);
    expect(c7?.usedFieldIds).toEqual(["C.701", "C.703"]);
  });

  it("builds H2 as a need-based aid cohort grid", () => {
    const tables = buildReconstructedTables({
      "H.201": field("500", "A. Number of degree-seeking undergraduate students", "Number"),
      "H.202": field("320", "B. Number of students in line a who applied for need-based financial aid", "Number"),
      "H.209": field("95", "I. On average, the percentage of need that was met", "Nearest 1%"),
      "H.210": field("72000", "J. The average financial aid package", "Nearest $1"),
      "H.214": field("1800", "A. Number of degree-seeking undergraduate students", "Number"),
      "H.222": field("90", "I. On average, the percentage of need that was met", "Nearest 1%"),
      "H.223": field("65000", "J. The average financial aid package", "Nearest $1"),
      "H.227": field("50", "A. Number of degree-seeking undergraduate students", "Number"),
    });

    const h2 = tables.find((table) => table.key === "h2-aid-awarded");

    expect(h2?.columns).toEqual([
      "First-year full-time",
      "All undergraduates full-time",
      "All undergraduates less-than-full-time",
    ]);
    expect(h2?.rows[0].cells.map((cell) => cell.display)).toEqual([
      "500",
      "1,800",
      "50",
    ]);
    expect(h2?.rows[8].cells.map((cell) => cell.display)).toEqual([
      "95%",
      "90%",
      "Not reported",
    ]);
    expect(h2?.rows[9].cells.map((cell) => cell.display)).toEqual([
      "$72,000",
      "$65,000",
      "Not reported",
    ]);
  });

  it("builds H2A as a cohort grid", () => {
    const tables = buildReconstructedTables({
      "H.2A01": field("120", "N. Number of students...", "Number"),
      "H.2A02": field("18000", "O. Average dollar amount...", "Nearest $1"),
      "H.2A05": field("400", "N. Number of students...", "Number"),
      "H.2A06": field("12500", "O. Average dollar amount...", "Nearest $1"),
    });

    const h2a = tables.find((table) => table.key === "h2a-non-need-aid");
    expect(h2a?.columns).toEqual([
      "First-year full-time",
      "All undergraduates full-time",
      "All undergraduates less-than-full-time",
    ]);
    expect(h2a?.rows[0].cells.map((cell) => cell.display)).toEqual([
      "120",
      "400",
      "Not reported",
    ]);
    expect(h2a?.rows[1].cells.map((cell) => cell.display)).toEqual([
      "$18,000",
      "$12,500",
      "Not reported",
    ]);
  });
});
