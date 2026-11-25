import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import {
  buildYearKeyFacts,
  DESCRIPTION_MAX,
  hubMetadataDescription,
  hubMetadataTitle,
  TITLE_MAX,
  yearMetadataDescription,
  yearMetadataTitle,
} from "./school-seo";
import type { SchoolYearFacts } from "./school-summary";

function facts(overrides: Partial<SchoolYearFacts> = {}): SchoolYearFacts {
  return {
    document_id: "doc-1",
    school_id: "example",
    ipeds_id: "100000",
    canonical_year: "2025-26",
    sub_institutional: null,
    yearStart: 2025,
    dataQualityFlag: null,
    applied: 52340,
    admitted: 28787,
    enrolledFirstYear: 7200,
    acceptanceRate: 0.55,
    satCompositeP25: 1210,
    satCompositeP75: 1410,
    actCompositeP25: 27,
    actCompositeP75: 32,
    edApplicants: null,
    edAdmitted: null,
    waitListOffered: null,
    waitListAccepted: null,
    waitListAdmitted: null,
    ...overrides,
  };
}

describe("hub vs year SEO metadata (#518)", () => {
  it("keeps hub titles un-yeared and differentiates hub vs year descriptions", () => {
    const vtFacts = facts({
      school_id: "virginia-tech",
      applied: 52340,
      admitted: 28787,
      acceptanceRate: 0.55,
    });
    const hubTitle = hubMetadataTitle("Virginia Tech");
    const yearTitle = yearMetadataTitle({
      schoolName: "Virginia Tech",
      year: "2025-26",
      facts: vtFacts,
    });
    const hubDesc = hubMetadataDescription({
      schoolName: "Virginia Tech",
      years: ["2016-17", "2024-25", "2025-26"],
    });
    const yearDesc = yearMetadataDescription({
      schoolName: "Virginia Tech",
      year: "2025-26",
      facts: vtFacts,
    });

    expect(hubTitle).toBe("Virginia Tech Common Data Set");
    expect(hubTitle).not.toContain("2025-26");
    expect(yearTitle).toBe("Virginia Tech Common Data Set 2025-26: 55% admit rate");
    expect(yearTitle.length).toBeLessThanOrEqual(TITLE_MAX);
    expect(hubDesc).not.toContain("55% acceptance rate");
    expect(hubDesc.length).toBeLessThanOrEqual(DESCRIPTION_MAX);
    expect(yearDesc).toMatch(/^2025-26 \(2025-2026\) Common Data Set for Virginia Tech: 55% acceptance rate/);
    expect(yearDesc.length).toBeLessThanOrEqual(DESCRIPTION_MAX);
  });

  it("caps long school names like WashU cleanly without inventing nicknames", () => {
    const washuFacts = facts({
      school_id: "washington-university-in-st-louis",
      applied: 33283,
      admitted: 4000,
      acceptanceRate: 0.12,
      satCompositeP25: 1500,
      satCompositeP75: 1570,
    });
    const yearTitle = yearMetadataTitle({
      schoolName: "Washington University in St. Louis",
      year: "2025-26",
      facts: washuFacts,
    });
    const hubDesc = hubMetadataDescription({
      schoolName: "Washington University in St. Louis",
      years: ["2024-25", "2025-26"],
    });
    const yearDesc = yearMetadataDescription({
      schoolName: "Washington University in St. Louis",
      year: "2025-26",
      facts: washuFacts,
    });

    expect(yearTitle).toBe("Washington University in St. Louis Common Data Set 2025-26");
    expect(yearTitle).not.toContain("WashU");
    expect(yearTitle.length).toBeLessThanOrEqual(TITLE_MAX);
    expect(hubDesc.length).toBeLessThanOrEqual(DESCRIPTION_MAX);
    expect(hubDesc).toContain("2 years, 2024–2025");
    expect(yearDesc).toContain("12% acceptance rate");
    expect(yearDesc.length).toBeLessThanOrEqual(DESCRIPTION_MAX);
  });

  it("includes both admit rate and applicants on short school names when within TITLE_MAX", () => {
    const mitTitle = yearMetadataTitle({
      schoolName: "MIT",
      year: "2025-26",
      facts: facts({
        applied: 28232,
        admitted: 1275,
        acceptanceRate: 0.045,
      }),
    });
    expect(mitTitle).toBe("MIT Common Data Set 2025-26: 4.5% admit rate, 28,232 applicants");
    expect(mitTitle.length).toBeLessThanOrEqual(TITLE_MAX);
  });

  it("handles single-year schools and missing/flagged facts cleanly", () => {
    const singleHubDesc = hubMetadataDescription({
      schoolName: "Thin College",
      years: ["2023-24"],
    });
    expect(singleHubDesc).toContain("2023-24 on file");
    expect(singleHubDesc.length).toBeLessThanOrEqual(DESCRIPTION_MAX);

    const noFactsTitle = yearMetadataTitle({
      schoolName: "Brown University",
      year: "2025-26",
      facts: null,
    });
    expect(noFactsTitle).toBe("Brown University Common Data Set 2025-26");

    const flaggedTitle = yearMetadataTitle({
      schoolName: "Brown University",
      year: "2025-26",
      facts: facts({ dataQualityFlag: "wrong_file" }),
    });
    expect(flaggedTitle).toBe("Brown University Common Data Set 2025-26");

    const noFactsDesc = yearMetadataDescription({
      schoolName: "Brown University",
      year: "2025-26",
      facts: null,
    });
    expect(noFactsDesc).toMatch(/^2025-26 \(2025-2026\) Common Data Set for Brown University:/);
  });
});

describe("buildYearKeyFacts", () => {
  it("builds quotable key facts matching gated numbers and omits flagged rows", () => {
    expect(buildYearKeyFacts(facts())).toEqual([
      { label: "Acceptance rate", value: "55%" },
      { label: "First-year applicants", value: "52,340" },
      { label: "Admitted", value: "28,787" },
      { label: "Enrolled", value: "7,200 (25% yield)" },
      { label: "SAT middle 50%", value: "1210–1410" },
      { label: "ACT middle 50%", value: "27–32" },
    ]);
    expect(buildYearKeyFacts(facts({ dataQualityFlag: "low_coverage" }))).toEqual([]);
    expect(buildYearKeyFacts(null)).toEqual([]);
  });
});

describe("page structure invariants (#518 & /pipeline-observation)", () => {
  const src = (rel: string) => readFileSync(join(process.cwd(), "src", rel), "utf8");

  it("hub renders the year nav for all multi/single-year archives and does not duplicate year summary prose", () => {
    const hub = src("app/schools/[school_id]/page.tsx");
    expect(hub).not.toContain("yearSummarySentences");
    expect(hub).not.toContain("metaFactFragment");
    expect(hub).not.toContain("uniqueYears.length > 3");
    expect(hub).toContain("uniqueYears.length > 0");
  });

  it("year page includes year in H1 and renders the compact key-facts block", () => {
    const yearPage = src("app/schools/[school_id]/[year]/page.tsx");
    expect(yearPage).toContain("yearMetadataTitle");
    expect(yearPage).toContain("yearMetadataDescription");
    expect(yearPage).toContain("<YearKeyFacts");
    expect(yearPage).toContain("{year} Common Data Set");
  });

  it("pipeline status page uses a plain operational heading without metaphor slop or double site name", () => {
    const pipeline = src("app/pipeline-observation/page.tsx");
    expect(pipeline).toContain('title: "Pipeline status"');
    expect(pipeline).toContain("Pipeline status");
    expect(pipeline).not.toMatch(/The clocks|locked doors|next slice/i);
  });
});
