import { describe, expect, it } from "vitest";
import {
  classifyTier,
  interpolatePercentile,
  scorePosition,
  type SchoolAcademicProfile,
} from "./positioning";

const baseSchool: SchoolAcademicProfile = {
  schoolId: "fixture",
  schoolName: "Fixture College",
  cdsYear: "2024-25",
  acceptanceRate: 0.3,
  satSubmitRate: 0.6,
  actSubmitRate: 0.4,
  satCompositeP25: 1200,
  satCompositeP50: 1300,
  satCompositeP75: 1400,
  actCompositeP25: 26,
  actCompositeP50: 29,
  actCompositeP75: 32,
  avgHsGpa: 3.8,
  hsGpaSubmitRate: 0.8,
  dataQualityFlag: null,
};

describe("interpolatePercentile", () => {
  it("anchors scores at 25/50/75", () => {
    expect(interpolatePercentile(1200, 1200, 1300, 1400)).toBe(25);
    expect(interpolatePercentile(1300, 1200, 1300, 1400)).toBe(50);
    expect(interpolatePercentile(1400, 1200, 1300, 1400)).toBe(75);
  });

  it("interpolates between anchors and clamps tails", () => {
    expect(interpolatePercentile(1250, 1200, 1300, 1400)).toBe(37.5);
    expect(interpolatePercentile(1350, 1200, 1300, 1400)).toBe(62.5);
    expect(interpolatePercentile(400, 1200, 1300, 1400)).toBe(5);
    expect(interpolatePercentile(1600, 1200, 1300, 1400)).toBe(95);
  });

  it("returns NaN for non-monotonic anchors", () => {
    expect(Number.isNaN(interpolatePercentile(1300, 1400, 1300, 1200))).toBe(true);
  });
});

describe("classifyTier", () => {
  it("uses admit-rate boundaries with mid-band scores", () => {
    expect(classifyTier(60, null, 0.55)).toBe("likely");
    expect(classifyTier(60, null, 0.3)).toBe("strong_fit");
    expect(classifyTier(60, null, 0.15)).toBe("possible");
  });

  it("marks very selective schools and low-score cases conservatively", () => {
    expect(classifyTier(80, null, 0.08)).toBe("long_shot");
    expect(classifyTier(20, null, 0.2)).toBe("long_shot");
    expect(classifyTier(20, null, 0.4)).toBe("unlikely");
  });

  it("returns unknown when scores or admit rate are missing", () => {
    expect(classifyTier(null, null, 0.3)).toBe("unknown");
    expect(classifyTier(60, null, null)).toBe("unknown");
  });
});

describe("scorePosition", () => {
  it("scores SAT and emits a positional sentence", () => {
    const result = scorePosition({ sat: 1350, gpa: 3.7 }, baseSchool);
    expect(result.satPercentile).toBe(63);
    expect(result.tier).toBe("strong_fit");
    expect(result.positionalSentence).toContain("within the middle 50%");
    expect(result.positionalSentence).toContain("admits 30%");
  });

  it("suppresses tier when admit rate is under 15% and score is mid-band", () => {
    const result = scorePosition(
      { sat: 1300 },
      { ...baseSchool, acceptanceRate: 0.12 },
    );
    expect(result.tier).toBe("unknown");
    expect(result.caveats).toContain("sub_15_admit_rate_suppression");
  });

  it("still returns long shot for admit rate under 10% even above band", () => {
    const result = scorePosition(
      { sat: 1500 },
      { ...baseSchool, acceptanceRate: 0.08 },
    );
    expect(result.tier).toBe("long_shot");
  });

  it("guards non-monotonic SAT data", () => {
    const result = scorePosition(
      { sat: 1300 },
      { ...baseSchool, satCompositeP25: 1400, satCompositeP50: 1300 },
    );
    expect(result.satPercentile).toBeNull();
    expect(result.caveats).toContain("data_incomplete");
  });

  it("adds test-optional caveats when submit rates are low or no score is entered", () => {
    const result = scorePosition(
      { gpa: 3.9 },
      { ...baseSchool, satSubmitRate: 0.31 },
    );
    expect(result.caveats).toContain("low_sat_submit_rate");
    expect(result.caveats).toContain("student_not_submitting");
  });

  it("adds stale CDS caveat for old source years", () => {
    const result = scorePosition(
      { sat: 1350 },
      { ...baseSchool, cdsYear: "2020-21" },
    );
    expect(result.caveats).toContain("stale_cds");
  });
});
