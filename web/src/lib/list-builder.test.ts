import { describe, expect, it } from "vitest";
import {
  applyMatchFilters,
  carnegieBucket,
  controlFromScorecard,
  rankMatchSchools,
  rankedSchoolsCsv,
  regionFromState,
  testPolicySignal,
  type MatchBuilderSchool,
} from "./list-builder";

const baseSchool: MatchBuilderSchool = {
  documentId: "doc",
  schoolId: "base",
  schoolName: "Base College",
  schoolUrl: "/schools/base",
  cdsYear: "2025-26",
  yearStart: 2025,
  archiveUrl: "https://example.com/base.pdf",
  acceptanceRate: 0.4,
  satSubmitRate: 0.6,
  actSubmitRate: 0.4,
  satCompositeP25: 1200,
  satCompositeP50: 1300,
  satCompositeP75: 1400,
  actCompositeP25: 26,
  actCompositeP50: 29,
  actCompositeP75: 32,
  avgHsGpa: null,
  hsGpaSubmitRate: null,
  dataQualityFlag: null,
  state: "IL",
  control: "private_nonprofit",
  region: "midwest",
  carnegieBasic: 21,
  carnegieBucket: "baccalaureate",
  testPolicySignal: "effective_optional",
};

describe("match list helpers", () => {
  it("maps public filter dimensions", () => {
    expect(controlFromScorecard(1)).toBe("public");
    expect(controlFromScorecard(2)).toBe("private_nonprofit");
    expect(regionFromState("CA")).toBe("west");
    expect(carnegieBucket(16)).toBe("doctoral");
    expect(carnegieBucket(21)).toBe("baccalaureate");
    expect(testPolicySignal(0.9, 0.82)).toBe("high_submit");
    expect(testPolicySignal(0.48, 0.2)).toBe("effective_optional");
    expect(testPolicySignal(0.08, null)).toBe("mostly_non_submitters");
  });

  it("filters by control, region, admit band, test signal, current year, and Carnegie", () => {
    const rows = [
      baseSchool,
      {
        ...baseSchool,
        schoolId: "older",
        schoolName: "Older University",
        yearStart: 2024,
        control: "public",
        region: "south",
        acceptanceRate: 0.7,
        carnegieBucket: "doctoral",
        testPolicySignal: "high_submit",
      },
    ] satisfies MatchBuilderSchool[];

    expect(
      applyMatchFilters(rows, {
        control: "private_nonprofit",
        region: "midwest",
        admitRate: "25_50",
        testPolicy: "effective_optional",
        currentOnly: true,
        carnegie: "baccalaureate",
        sort: "fit",
      }).map((school) => school.schoolId),
    ).toEqual(["base"]);
  });

  it("ranks schools into the same tier model as positioning", () => {
    const rows = rankMatchSchools({ sat: 1350 }, [
      { ...baseSchool, schoolId: "likely", schoolName: "Likely College", acceptanceRate: 0.65 },
      { ...baseSchool, schoolId: "possible", schoolName: "Possible College", acceptanceRate: 0.2 },
      { ...baseSchool, schoolId: "long", schoolName: "Long Shot College", acceptanceRate: 0.08 },
    ]);

    expect(rows.map((row) => row.schoolId)).toEqual(["likely", "possible", "long"]);
    expect(rows[0].result.tier).toBe("likely");
  });

  it("keeps schools with score bands even when admit rate is missing", () => {
    const rows = rankMatchSchools({ act: 36 }, [
      {
        ...baseSchool,
        schoolId: "missing-rate",
        schoolName: "Missing Rate Institute",
        acceptanceRate: null,
        actCompositeP25: 34,
        actCompositeP50: 35,
        actCompositeP75: 36,
      },
    ]);

    expect(rows.map((row) => row.schoolId)).toEqual(["missing-rate"]);
    expect(rows[0].result.tier).toBe("unknown");
    expect(rows[0].result.caveats).toContain("no_admit_rate");
  });

  it("puts strong-fit schools before likely schools by default", () => {
    const rows = rankMatchSchools({ sat: 1350 }, [
      { ...baseSchool, schoolId: "likely", schoolName: "Likely College", acceptanceRate: 0.65 },
      { ...baseSchool, schoolId: "strong", schoolName: "Strong Fit College", acceptanceRate: 0.35 },
    ]);

    expect(rows.map((row) => row.schoolId)).toEqual(["strong", "likely"]);
    expect(rows.map((row) => row.result.tier)).toEqual(["strong_fit", "likely"]);
  });

  it("sorts within a tier by admit rate or name", () => {
    const admitSorted = rankMatchSchools(
      { sat: 1350 },
      [
        { ...baseSchool, schoolId: "a", schoolName: "Alpha College", acceptanceRate: 0.3 },
        { ...baseSchool, schoolId: "b", schoolName: "Beta College", acceptanceRate: 0.45 },
      ],
      { ...DEFAULT_FILTERS_FOR_TEST, sort: "admit_rate" },
    );
    const nameSorted = rankMatchSchools(
      { sat: 1350 },
      [
        { ...baseSchool, schoolId: "z", schoolName: "Zeta College", acceptanceRate: 0.35 },
        { ...baseSchool, schoolId: "a", schoolName: "Alpha College", acceptanceRate: 0.35 },
      ],
      { ...DEFAULT_FILTERS_FOR_TEST, sort: "name" },
    );

    expect(admitSorted.map((row) => row.schoolId)).toEqual(["b", "a"]);
    expect(nameSorted.map((row) => row.schoolId)).toEqual(["a", "z"]);
  });

  it("exports counselor-friendly CSV rows", () => {
    const csv = rankedSchoolsCsv(rankMatchSchools({ sat: 1350 }, [baseSchool]));
    expect(csv.split("\n")[0]).toBe(
      "school_name,school_url,tier,best_percentile,admit_rate,cds_year,source_pdf_url",
    );
    expect(csv).toContain("Base College");
    expect(csv).toContain("strong_fit");
  });
});

const DEFAULT_FILTERS_FOR_TEST = {
  control: "all",
  region: "all",
  admitRate: "all",
  testPolicy: "all",
  currentOnly: false,
  carnegie: "all",
  sort: "fit",
} as const;
