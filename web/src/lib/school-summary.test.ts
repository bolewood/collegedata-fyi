import { describe, expect, it } from "vitest";
import { leadContainsBannedCopy } from "./archive-lead";
import {
  factsForYear,
  longYear,
  metaFactFragment,
  servedFacts,
  yearOverYearSentence,
  yearSummarySentences,
  type SchoolYearFacts,
} from "./school-summary";

function facts(overrides: Partial<SchoolYearFacts>): SchoolYearFacts {
  return {
    document_id: null,
    school_id: "cornell",
    ipeds_id: "190415",
    canonical_year: "2025-26",
    sub_institutional: null,
    yearStart: 2025,
    dataQualityFlag: null,
    applied: null,
    admitted: null,
    enrolledFirstYear: null,
    acceptanceRate: null,
    satCompositeP25: null,
    satCompositeP75: null,
    actCompositeP25: null,
    actCompositeP75: null,
    edApplicants: null,
    edAdmitted: null,
    waitListOffered: null,
    waitListAccepted: null,
    waitListAdmitted: null,
    ...overrides,
  };
}

const cornell2025 = facts({
  applied: 72523,
  admitted: 6077,
  enrolledFirstYear: 3760,
  satCompositeP25: 1490,
  satCompositeP75: 1560,
  actCompositeP25: 33,
  actCompositeP75: 35,
  edApplicants: 10000,
  edAdmitted: 2000,
  waitListOffered: 7000,
  waitListAccepted: 4000,
  waitListAdmitted: 100,
});

const cornell2024 = facts({
  canonical_year: "2024-25",
  yearStart: 2024,
  applied: 69681,
  admitted: 6062,
  edApplicants: 9600,
  edAdmitted: 1920,
});

describe("yearSummarySentences", () => {
  it("states the reported numbers in plain English", () => {
    expect(yearSummarySentences("Cornell University", cornell2025)).toEqual([
      "In its 2025-26 report, Cornell University says 72,523 first-year students applied and 6,077 were admitted, an acceptance rate of 8.4%.",
      "3,760 admitted students enrolled (62% yield).",
      "Enrolled students who sent scores had a middle-50% SAT of 1490–1560 and ACT of 33–35.",
      "Early decision: 2,000 of 10,000 applicants admitted (20%).",
      "Waitlist: 7,000 offered a spot, 4,000 accepted one, and 100 admitted from it.",
    ]);
  });

  it("omits sentences whose inputs are missing or impossible", () => {
    const sentences = yearSummarySentences(
      "Example College",
      facts({ applied: 100, admitted: 150, satCompositeP25: 1500, satCompositeP75: 1300 }),
    );
    expect(sentences).toEqual([]);
  });

  it("says nothing for rows hidden by data quality flags", () => {
    expect(
      yearSummarySentences("Cornell University", { ...cornell2025, dataQualityFlag: "wrong_file" }),
    ).toEqual([]);
  });

  it("never uses banned lead copy", () => {
    const text = yearSummarySentences("Cornell University", cornell2025).join(" ");
    expect(leadContainsBannedCopy(text)).toBe(false);
  });
});

describe("yearOverYearSentence", () => {
  it("compares consecutive years", () => {
    expect(yearOverYearSentence(cornell2025, cornell2024)).toBe(
      "Compared with 2024-25, applications rose 4.1% (69,681 to 72,523), the acceptance rate went from 8.7% to 8.4%, and the early decision admit rate held at 20%.",
    );
  });

  it("stays silent across a gap year", () => {
    expect(
      yearOverYearSentence(cornell2025, { ...cornell2024, yearStart: 2023, canonical_year: "2023-24" }),
    ).toBeNull();
  });
});

describe("metadata helpers", () => {
  it("builds a compact description fragment", () => {
    expect(metaFactFragment(cornell2025)).toBe(
      "8.4% acceptance rate, 72,523 applicants, SAT 1490–1560, 20% early decision admit rate",
    );
  });

  it("prints the template's long year form", () => {
    expect(longYear("2025-26")).toBe("2025-2026");
    expect(longYear("unknown")).toBeNull();
  });

  it("keeps only rows for served documents", () => {
    const rows = [
      { ...cornell2025, document_id: "shown" },
      { ...cornell2025, document_id: "duplicate-file", applied: 1 },
    ];
    expect(servedFacts(rows, ["shown"]).map((row) => row.document_id)).toEqual(["shown"]);
  });

  it("finds the current and prior year rows", () => {
    const { current, prior } = factsForYear([cornell2025, cornell2024], "2025-26");
    expect(current?.canonical_year).toBe("2025-26");
    expect(prior?.canonical_year).toBe("2024-25");
  });
});
