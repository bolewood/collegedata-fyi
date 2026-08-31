import { describe, expect, it } from "vitest";
import {
  PRICING_POWER_ANNOTATION_IPEDS_ID,
  PRICING_POWER_ANNOTATION_SCHOOL_ID,
  PRICING_POWER_META,
  PRICING_POWER_SCHOOLS,
} from "./pricing-power-recipe-data";
import {
  PRICING_POWER_ANNOTATION_IPEDS_ID as ANALYSIS_IPEDS_ID,
  PRICING_POWER_ANNOTATION_SCHOOL_ID as ANALYSIS_SCHOOL_ID,
  computeAcceptanceRate,
  computeBurden,
  computeInstructionNetPriceRatio,
  computeYieldRate,
  formatBurdenPercent,
  formatInstructionRatio,
  formatRatePercent,
  formatUsd,
  formatUsdCents,
  isPanelBSchool,
  median,
  panelAQuadrant,
  panelBQuadrant,
  panelBSchools,
} from "./pricing-power-recipe-analysis";

describe("pricing-power guard rails", () => {
  it("throws on non-positive denominators instead of returning Infinity/NaN", () => {
    expect(() => computeAcceptanceRate(100, 0)).toThrow(/positive applicant/);
    expect(() => computeAcceptanceRate(100, -5)).toThrow(/positive applicant/);
    expect(() => computeYieldRate(50, 0)).toThrow(/positive admitted/);
    expect(() => computeBurden(0, 60000)).toThrow(/positive/);
    expect(() => computeBurden(250, 0)).toThrow(/positive/);
    expect(() => computeInstructionNetPriceRatio(0, 30000)).toThrow(/positive/);
    expect(() => computeInstructionNetPriceRatio(20000, 0)).toThrow(/positive/);
    expect(() => median([])).toThrow(/empty/);
  });

  it("keeps the page's worked-example anchors in Panel B of the dataset", () => {
    // The page throws at build time (requirePanelB) if a dataset regen drops
    // any of these schools; this catches that in the test run instead.
    const anchors = [
      PRICING_POWER_ANNOTATION_SCHOOL_ID,
      "fordham-university",
      "american-university",
      "southern-methodist-university",
    ];
    for (const schoolId of anchors) {
      const row = PRICING_POWER_SCHOOLS.find((s) => s.schoolId === schoolId);
      expect(row, schoolId).toBeDefined();
      expect(isPanelBSchool(row!), `${schoolId} must have Panel B fields`).toBe(
        true,
      );
    }
  });
});

describe("pricing-power prose claims stay true under dataset regen", () => {
  const panelB = panelBSchools(PRICING_POWER_SCHOOLS);
  const grab = (schoolId: string) => {
    const row = panelB.find((s) => s.schoolId === schoolId);
    expect(row, schoolId).toBeDefined();
    return row!;
  };

  it("keeps Fordham, American, and SMU below both Panel B medians with above-median net price", () => {
    // page.tsx: "Fordham, American, and SMU also sit below both Panel B
    // medians on yield and burden while posting above-median Title IV net
    // prices." Nothing else guards this relational claim against a regen.
    const medianNetPrice = median(panelB.map((s) => s.avgNetPrice));
    for (const schoolId of [
      "fordham-university",
      "american-university",
      "southern-methodist-university",
    ]) {
      const row = grab(schoolId);
      expect(row.yieldRate, `${schoolId} yield`).toBeLessThan(
        PRICING_POWER_META.medianYieldB,
      );
      expect(row.burden, `${schoolId} burden`).toBeLessThan(
        PRICING_POWER_META.medianBurden,
      );
      expect(row.avgNetPrice, `${schoolId} net price`).toBeGreaterThan(
        medianNetPrice,
      );
    }
  });

  it("keeps Northeastern, BU, and NYU yields above Syracuse's", () => {
    // page.tsx: "each has a much higher fall 2024 yield" than Syracuse.
    const syracuse = grab(PRICING_POWER_ANNOTATION_SCHOOL_ID);
    for (const schoolId of ["northeastern", "boston-university", "nyu"]) {
      expect(grab(schoolId).yieldRate, schoolId).toBeGreaterThan(
        syracuse.yieldRate,
      );
    }
  });

  it("keeps every Panel B burden inside Figure 2's 0-16% axis window", () => {
    // YieldDebtBurdenChart clamps burden to BURDEN_MAX = 0.16; a regen
    // that exceeds it would silently pin dots to the top gridline.
    for (const row of panelB) {
      expect(row.burden, row.schoolId).toBeLessThanOrEqual(0.16);
    }
  });

  it("keeps the Figure 2 drop-count arithmetic consistent", () => {
    // page.tsx renders panelACount - panelBCount as the join drop; this
    // pins that difference to the builder's own tallies.
    expect(
      PRICING_POWER_META.panelACount - PRICING_POWER_META.panelBCount,
    ).toBe(
      PRICING_POWER_META.exclusions.missingNonpositiveScorecard +
        PRICING_POWER_META.joinMisses.scorecard,
    );
  });
});

describe("pricing-power arithmetic", () => {
  it("reproduces Syracuse rates, burden, and instruction/net-price from raw inputs", () => {
    expect(computeAcceptanceRate(20427, 44480)).toBeCloseTo(0.4592, 4);
    expect(computeYieldRate(3835, 20427)).toBeCloseTo(0.1877, 4);
    expect(computeBurden(275.64, 79164)).toBeCloseTo(0.0418, 4);
    expect(computeInstructionNetPriceRatio(20551, 38793)).toBeCloseTo(0.5298, 4);
  });

  it("assigns Panel A quadrants with medians as inclusive higher-side dividers", () => {
    expect(panelAQuadrant(0.4, 0.3, 0.5, 0.25)).toBe("lowerAcceptanceHigherYield");
    expect(panelAQuadrant(0.5, 0.25, 0.5, 0.25)).toBe("higherAcceptanceHigherYield");
    expect(panelAQuadrant(0.4, 0.2, 0.5, 0.25)).toBe("lowerAcceptanceLowerYield");
    expect(panelAQuadrant(0.6, 0.2, 0.5, 0.25)).toBe("higherAcceptanceLowerYield");
  });

  it("assigns Panel B quadrants with medians as inclusive higher-side dividers", () => {
    expect(panelBQuadrant(0.3, 0.05, 0.25, 0.04)).toBe("higherYieldHigherBurden");
    expect(panelBQuadrant(0.2, 0.05, 0.25, 0.04)).toBe("lowerYieldHigherBurden");
    expect(panelBQuadrant(0.3, 0.03, 0.25, 0.04)).toBe("higherYieldLowerBurden");
    expect(panelBQuadrant(0.2, 0.03, 0.25, 0.04)).toBe("lowerYieldLowerBurden");
  });

  it("formats rates, burden, and dollars for chart copy", () => {
    expect(formatRatePercent(0.4592, 2)).toBe("45.92%");
    expect(formatRatePercent(0.1877, 2)).toBe("18.77%");
    expect(formatBurdenPercent(0.0418)).toBe("4.18%");
    expect(formatUsd(38793)).toBe("$38,793");
    expect(formatUsdCents(275.64)).toBe("$275.64");
    expect(formatInstructionRatio(0.5298)).toBe("53% of net price");
    expect(formatInstructionRatio(2.4)).toBe("2.4× net price");
    expect(median([0.1, 0.2, 0.3])).toBe(0.2);
    expect(median([0.1, 0.2])).toBeCloseTo(0.15, 10);
  });
});

describe("pricing-power generated dataset", () => {
  it("keeps the Syracuse annotation constant aligned across data and analysis", () => {
    expect(PRICING_POWER_ANNOTATION_SCHOOL_ID).toBe("syracuse-university");
    expect(PRICING_POWER_ANNOTATION_IPEDS_ID).toBe("196413");
    expect(ANALYSIS_SCHOOL_ID).toBe(PRICING_POWER_ANNOTATION_SCHOOL_ID);
    expect(ANALYSIS_IPEDS_ID).toBe(PRICING_POWER_ANNOTATION_IPEDS_ID);
    expect(PRICING_POWER_META.annotationSchoolId).toBe(PRICING_POWER_ANNOTATION_SCHOOL_ID);
    expect(PRICING_POWER_META.annotationIpedsId).toBe(PRICING_POWER_ANNOTATION_IPEDS_ID);
  });

  it("includes Syracuse in both panels with the expected ADM2024 and Scorecard values", () => {
    const syracuse = PRICING_POWER_SCHOOLS.find(
      (row) => row.schoolId === PRICING_POWER_ANNOTATION_SCHOOL_ID,
    );
    expect(syracuse).toBeDefined();
    expect(syracuse).toMatchObject({
      ipedsId: PRICING_POWER_ANNOTATION_IPEDS_ID,
      applied: 44480,
      admitted: 20427,
      enrolled: 3835,
      acceptanceRate: 0.4592,
      yieldRate: 0.1877,
      medianDebt: 26000,
      monthlyPayment: 275.64,
      earnings10yr: 79164,
      avgNetPrice: 38793,
      instructionFte: 20551,
    });
    expect(syracuse!.burden).toBeCloseTo(0.0418, 4);
    expect(syracuse!.instructionNetPriceRatio).toBeCloseTo(0.5298, 4);
    expect(isPanelBSchool(syracuse!)).toBe(true);
    expect(syracuse).not.toHaveProperty("cdsAcceptanceRate");
  });

  it("keeps meta counts, medians, and quadrants internally consistent", () => {
    const panelB = panelBSchools(PRICING_POWER_SCHOOLS);
    expect(PRICING_POWER_SCHOOLS).toHaveLength(PRICING_POWER_META.panelACount);
    expect(panelB).toHaveLength(PRICING_POWER_META.panelBCount);
    expect(PRICING_POWER_META.panelACount).toBeGreaterThanOrEqual(1700);
    expect(PRICING_POWER_META.panelACount).toBeLessThanOrEqual(2000);
    expect(PRICING_POWER_META.panelBCount).toBeGreaterThanOrEqual(1500);
    expect(PRICING_POWER_META.panelBCount).toBeLessThanOrEqual(1750);

    const quadrantASum = Object.values(PRICING_POWER_META.quadrantsA).reduce(
      (sum, count) => sum + count,
      0,
    );
    const quadrantBSum = Object.values(PRICING_POWER_META.quadrantsB).reduce(
      (sum, count) => sum + count,
      0,
    );
    expect(quadrantASum).toBe(PRICING_POWER_META.panelACount);
    expect(quadrantBSum).toBe(PRICING_POWER_META.panelBCount);

    expect(PRICING_POWER_META.medianAcceptance).toBeGreaterThan(0);
    expect(PRICING_POWER_META.medianAcceptance).toBeLessThan(1);
    expect(PRICING_POWER_META.medianYield).toBeGreaterThan(0);
    expect(PRICING_POWER_META.medianYield).toBeLessThan(1);
    expect(PRICING_POWER_META.medianYieldB).toBeGreaterThan(0);
    expect(PRICING_POWER_META.medianYieldB).toBeLessThan(1);
    expect(PRICING_POWER_META.medianBurden).toBeGreaterThan(0);
    expect(PRICING_POWER_META.medianBurden).toBeLessThan(0.2);
    expect(PRICING_POWER_META.ipedsCycle).toBe("fall 2024 (ADM2024)");
    expect(PRICING_POWER_META.scorecardYears.length).toBeGreaterThan(0);

    const distinctYields = new Set(PRICING_POWER_SCHOOLS.map((row) => row.yieldRate));
    expect(distinctYields.size).toBeGreaterThan(100);

    const recomputedA = {
      lowerAcceptanceHigherYield: 0,
      higherAcceptanceHigherYield: 0,
      lowerAcceptanceLowerYield: 0,
      higherAcceptanceLowerYield: 0,
    };
    for (const row of PRICING_POWER_SCHOOLS) {
      recomputedA[
        panelAQuadrant(
          row.acceptanceRate,
          row.yieldRate,
          PRICING_POWER_META.medianAcceptance,
          PRICING_POWER_META.medianYield,
        )
      ] += 1;
    }
    expect(recomputedA).toEqual({ ...PRICING_POWER_META.quadrantsA });

    const recomputedB = {
      higherYieldHigherBurden: 0,
      lowerYieldHigherBurden: 0,
      higherYieldLowerBurden: 0,
      lowerYieldLowerBurden: 0,
    };
    for (const row of panelB) {
      recomputedB[
        panelBQuadrant(
          row.yieldRate,
          row.burden,
          PRICING_POWER_META.medianYieldB,
          PRICING_POWER_META.medianBurden,
        )
      ] += 1;
    }
    expect(recomputedB).toEqual({ ...PRICING_POWER_META.quadrantsB });
  });
});
