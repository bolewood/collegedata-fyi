import { describe, expect, it } from "vitest";
import {
  buildHubRibbonCells,
  buildYearPageRibbonBands,
  parsePercentField,
} from "./SchoolFactRibbon";
import { parseCatalogQuery } from "@/lib/catalog-query";
import type { FieldValue, SchoolFactUnifiedRow, ScorecardSummary } from "@/lib/types";
import type { SchoolYearFacts } from "@/lib/school-summary";

function fv(value: string): FieldValue {
  return { value };
}

describe("parsePercentField", () => {
  it("normalizes fractions and percentages consistently", () => {
    const values: Record<string, FieldValue> = {
      "C.901": fv("0.68"),
      "C.902": fv("24%"),
      "B.2203": fv("97.5"),
    };
    expect(parsePercentField(values, "C.901")).toBeCloseTo(68);
    expect(parsePercentField(values, "C.902")).toBeCloseTo(24);
    expect(parsePercentField(values, "B.2203")).toBeCloseTo(97.5);
  });
});

describe("buildYearPageRibbonBands", () => {
  it("builds admissions + retention band and testing band with submit rates and medians", () => {
    const values: Record<string, FieldValue> = {
      "C.901": fv("72%"),
      "C.902": fv("0.24"),
      "C.905": fv("1480"),
      "C.906": fv("1530"),
      "C.907": fv("1570"),
      "C.908": fv("730"),
      "C.909": fv("760"),
      "C.910": fv("780"),
      "C.911": fv("750"),
      "C.912": fv("770"),
      "C.913": fv("800"),
      "C.914": fv("33"),
      "C.915": fv("34"),
      "C.916": fv("35"),
      "B.2203": fv("98%"),
    };

    const priorFacts: SchoolYearFacts = {
      document_id: "doc-prior",
      school_id: "bowdoin",
      ipeds_id: "161004",
      canonical_year: "2023-24",
      sub_institutional: null,
      yearStart: 2023,
      dataQualityFlag: null,
      applied: 10000,
      admitted: 800,
      enrolledFirstYear: 500,
      acceptanceRate: 0.08,
      satCompositeP25: 1460,
      satCompositeP75: 1550,
      actCompositeP25: 33,
      actCompositeP75: 35,
      edApplicants: null,
      edAdmitted: null,
      waitListOffered: null,
      waitListAccepted: null,
      waitListAdmitted: null,
    };

    const bands = buildYearPageRibbonBands({
      values,
      schemaVersion: "2024-25",
      c1: { applied: 10000, admitted: 700, enrolled: 504 },
      priorFacts,
      currentYearStart: 2024,
    });

    expect(bands).toHaveLength(2);
    const adm = bands[0];
    expect(adm.key).toBe("c1-admissions");
    const acceptCell = adm.cells.find((c) => c.key === "acceptance-rate");
    expect(acceptCell?.value).toBe("7.0%");
    expect(acceptCell?.deltaText).toBe("−1.0 pts YoY");
    expect(acceptCell?.sourceHref).toBe("#sec-c1");

    const yieldCell = adm.cells.find((c) => c.key === "yield-rate");
    expect(yieldCell?.value).toBe("72.0%");
    expect(yieldCell?.deltaText).toBe("+9.5 pts YoY");

    const retentionCell = adm.cells.find((c) => c.key === "retention-rate");
    expect(retentionCell?.value).toBe("98%");
    expect(retentionCell?.sourceLabel).toBe("§B22");

    const testing = bands[1];
    expect(testing.key).toBe("c9-testing");
    const satCell = testing.cells.find((c) => c.key === "sat-composite");
    expect(satCell?.value).toBe("1480–1570");
    expect(satCell?.subCaption).toBe("72% SUB · MED 1530");
    expect(satCell?.rangeBar?.median).toBe(1530);

    const actCell = testing.cells.find((c) => c.key === "act-composite");
    expect(actCell?.value).toBe("33–35");
    expect(actCell?.subCaption).toBe("24% SUB · MED 34");
  });

  it("prints SUB % N/A when score ranges exist without submit rates", () => {
    const values: Record<string, FieldValue> = {
      "C.905": fv("1400"),
      "C.907": fv("1520"),
    };
    const bands = buildYearPageRibbonBands({
      values,
      c1: { applied: null, admitted: null, enrolled: null },
    });
    expect(bands).toHaveLength(1);
    expect(bands[0].cells[0].subCaption).toBe("SUB % N/A");
  });
});

describe("buildHubRibbonCells", () => {
  it("computes 3-year sparklines and separates CDS and federal sources", () => {
    const makeYear = (
      year: string,
      yearStart: number,
      applied: number,
      admitted: number,
      enrolled: number,
    ): SchoolYearFacts => ({
      document_id: `doc-${year}`,
      school_id: "mit",
      ipeds_id: "166683",
      canonical_year: year,
      sub_institutional: null,
      yearStart,
      dataQualityFlag: null,
      applied,
      admitted,
      enrolledFirstYear: enrolled,
      acceptanceRate: admitted / applied,
      satCompositeP25: 1520,
      satCompositeP75: 1580,
      actCompositeP25: 35,
      actCompositeP75: 36,
      edApplicants: null,
      edAdmitted: null,
      waitListOffered: null,
      waitListAccepted: null,
      waitListAdmitted: null,
    });

    const shownFacts = [
      makeYear("2025-26", 2025, 29000, 1280, 1100),
      makeYear("2024-25", 2024, 28000, 1275, 1102),
      makeYear("2023-24", 2023, 26900, 1291, 1096),
    ];

    const scorecard = {
      avg_net_price: 21400,
      retention_rate_ft: 0.99,
      scorecard_data_year: "2022-23",
    } as ScorecardSummary;

    const federalFacts = [
      { field_key: "retention_rate_full_time", data_year: 2022, value_numeric: 98 },
      { field_key: "retention_rate_full_time", data_year: 2023, value_numeric: 99 },
      { field_key: "retention_rate_full_time", data_year: 2024, value_numeric: 99 },
    ] as SchoolFactUnifiedRow[];

    const cells = buildHubRibbonCells({
      schoolId: "mit",
      latestFacts: shownFacts[0],
      shownFacts,
      scorecard,
      federalFacts,
    });

    expect(cells.length).toBe(6);
    const accept = cells.find((c) => c.key === "hub-acceptance");
    expect(accept?.sparkline?.data).toHaveLength(3);
    expect(accept?.sparkline?.yearSpan).toBe("2023–2025");
    expect(accept?.sourceHref).toBe("/schools/mit/2025-26#sec-c1");

    const netPrice = cells.find((c) => c.key === "hub-net-price");
    expect(netPrice?.sourceLabel).toBe("SCORECARD");
    expect(netPrice?.sourceHref).toBe("#outcomes");
  });
});

describe("parseCatalogQuery", () => {
  it("parses compound school + year + section call numbers", () => {
    const q1 = parseCatalogQuery("bowdoin 2024 §c9");
    expect(q1.schoolQuery).toBe("bowdoin");
    expect(q1.year).toBe("2024-25");
    expect(q1.sectionTarget?.code).toBe("§C9");
    expect(q1.sectionTarget?.anchor).toBe("#testing");

    const q2 = parseCatalogQuery("yale aid");
    expect(q2.schoolQuery).toBe("yale");
    expect(q2.sectionTarget?.code).toBe("§H2");

    const q3 = parseCatalogQuery("mit C.905");
    expect(q3.schoolQuery).toBe("mit");
    expect(q3.fieldId).toBe("C.905");
  });
});
