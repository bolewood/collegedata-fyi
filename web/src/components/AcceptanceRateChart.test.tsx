import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { AcceptanceRateChart } from "./AcceptanceRateChart";
import { AcceptanceRateTable, type AcceptanceTableRow } from "./AcceptanceRateTable";
import type { AcceptanceYear } from "@/lib/acceptance-history";

function year(
  start: number,
  rate: number,
  ed?: { applied: number; admitted: number; rate: number },
): AcceptanceYear {
  const applied = 1000;
  const admitted = Math.round(rate * applied);
  return {
    year: `${start}-${String((start + 1) % 100).padStart(2, "0")}`,
    yearStart: start,
    documentId: `doc-${start}`,
    sourceStoragePath: `x/${start}/x.pdf`,
    sourceFormat: "pdf_flat",
    source: "2024-25",
    applied,
    admitted,
    enrolled: 40,
    rate,
    yieldRate: 40 / admitted,
    ed: ed ?? null,
  };
}

describe("AcceptanceRateChart", () => {
  it("keeps a single series when no year has C21 counts", () => {
    const rows: AcceptanceTableRow[] = [2021, 2022, 2023, 2024].map((start) => ({
      kind: "year",
      row: year(start, 0.1),
    }));
    const html = renderToStaticMarkup(<AcceptanceRateChart schoolName="Duke University" rows={rows} />);
    expect(html).toContain("acc-chart__bar");
    expect(html).not.toContain("acc-chart__track--pair");
    expect(html).not.toContain("early decision");
    expect(html).toContain("Share of first-year applicants admitted");
  });

  it("pairs overall and ED bars, scales to the higher rate, and names both in the accessible label", () => {
    const rows: AcceptanceTableRow[] = [
      { kind: "year", row: year(2025, 0.08, { applied: 200, admitted: 80, rate: 0.4 }) },
      { kind: "year", row: year(2024, 0.09) },
      { kind: "gap", year: "2023-24", yearStart: 2023, hasReport: false },
      { kind: "year", row: year(2022, 0.1) },
      { kind: "year", row: year(2021, 0.11) },
    ];
    const html = renderToStaticMarkup(<AcceptanceRateChart schoolName="Duke University" rows={rows} />);
    expect(html).toContain("acc-chart__track--pair");
    expect(html).toContain("acc-chart__bar--ed");
    expect(html).toContain("acc-chart__bar--empty");
    expect(html).toContain("Olive bars show early decision");
    expect(html).toContain("early decision 40.0%");
    expect(html).toContain("fall 2023, not available");
    // 40% ED is the scale max; 8% overall is a fifth of that height.
    expect(html).toMatch(/height:27px/);
    expect(html).toMatch(/height:136px/);
  });
});

describe("AcceptanceRateTable", () => {
  it("puts the ED rate on a second line in the Rate cell, not a new column", () => {
    const rows: AcceptanceTableRow[] = [
      { kind: "year", row: year(2025, 0.08, { applied: 200, admitted: 80, rate: 0.4 }) },
      { kind: "year", row: year(2024, 0.09) },
    ];
    const html = renderToStaticMarkup(
      <AcceptanceRateTable schoolId="duke" schoolName="Duke University" rows={rows} />,
    );
    expect(html).toContain("40.0% ED");
    expect(html).toContain('class="acc-table__ed">—');
    expect(html).not.toContain("<th>Early decision</th>");
    expect(html).toContain("C21 counts");
  });

  it("still shows the ED line when the series is too short for a chart", () => {
    const rows: AcceptanceTableRow[] = [
      { kind: "year", row: year(2025, 0.08, { applied: 200, admitted: 80, rate: 0.4 }) },
      { kind: "year", row: year(2024, 0.09) },
      { kind: "year", row: year(2023, 0.1) },
    ];
    expect(renderToStaticMarkup(<AcceptanceRateChart schoolName="Duke University" rows={rows} />)).toBe("");
    const html = renderToStaticMarkup(
      <AcceptanceRateTable schoolId="duke" schoolName="Duke University" rows={rows} />,
    );
    expect(html).toContain("40.0% ED");
  });
});
