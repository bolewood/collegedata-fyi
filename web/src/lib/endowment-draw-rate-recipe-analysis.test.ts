import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  ENDOWMENT_DRAW_RATE_META,
  ENDOWMENT_DRAW_RATE_SCHOOLS,
  ENDOWMENT_DRAW_RATE_YEAR_SUMMARIES,
  type EndowmentDrawRatePoint,
} from "./endowment-draw-rate-recipe-data";
import {
  ENDOWMENT_DRAW_RATE_BUCKET_THRESHOLDS,
  DEFAULT_ENDOWMENT_RECIPE_SCHOOL_ID,
  bucketMembers,
  endowmentSchoolHistory,
  endowmentSchoolLabel,
  unpackEndowmentDrawRatePoint,
} from "./endowment-draw-rate-recipe-analysis";

describe("endowment draw-rate recipe analysis", () => {
  it("keeps the public default selection-neutral", () => {
    expect(DEFAULT_ENDOWMENT_RECIPE_SCHOOL_ID).toBeNull();
  });

  it("keeps the documented dataset version in sync with the generated artifact", () => {
    const methodology = readFileSync(
      new URL("../../../docs/recipes/endowment-draw-rate.md", import.meta.url),
      "utf8",
    );
    expect(methodology).toContain(`Dataset version: \`${ENDOWMENT_DRAW_RATE_META.datasetVersion}\``);
  });

  it("unpacks the generated tuple contract without shifting fields", () => {
    const point = [
      2024,
      100,
      110,
      -5,
      0.05,
      null,
      "provisional",
      "F2324_F2",
    ] as const satisfies EndowmentDrawRatePoint;

    expect(unpackEndowmentDrawRatePoint(point)).toEqual({
      year: 2024,
      beginningValue: 100,
      endingValue: 110,
      spendingDistribution: -5,
      drawRate: 0.05,
      exclusionReason: null,
      releaseType: "provisional",
      sourceTable: "F2324_F2",
    });
  });

  it("matches generated counts, formulas, and threshold summaries", () => {
    const allPoints = ENDOWMENT_DRAW_RATE_SCHOOLS.flatMap((school) =>
      school.history.map((point) => ({
        school,
        point: unpackEndowmentDrawRatePoint(point),
      })),
    );
    expect(allPoints).toHaveLength(ENDOWMENT_DRAW_RATE_META.rowCount);
    expect(ENDOWMENT_DRAW_RATE_SCHOOLS).toHaveLength(ENDOWMENT_DRAW_RATE_META.schoolCount);

    for (const summary of ENDOWMENT_DRAW_RATE_YEAR_SUMMARIES) {
      const yearPoints = allPoints.filter(({ point }) => point.year === summary.year);
      const eligible = yearPoints.filter(
        ({ point }) => point.drawRate !== null && point.exclusionReason === null,
      );
      expect(yearPoints).toHaveLength(summary.reporters);
      expect(eligible).toHaveLength(summary.eligible);
      expect(summary.excluded).toBe(summary.reporters - summary.eligible);
    }

    for (const { point } of allPoints) {
      if (
        point.drawRate == null ||
        point.beginningValue == null ||
        point.spendingDistribution == null
      ) {
        continue;
      }
      expect(point.drawRate).toBeCloseTo(
        Math.abs(point.spendingDistribution) / point.beginningValue,
        7,
      );
    }
  });

  it("derives every cumulative threshold bucket from eligible school-year points", () => {
    for (const summary of ENDOWMENT_DRAW_RATE_YEAR_SUMMARIES) {
      const expectedCounts = {
        0.05: summary.above5Count,
        0.07: summary.above7Count,
        0.15: summary.above15Count,
      } as const;
      const membersByThreshold = ENDOWMENT_DRAW_RATE_BUCKET_THRESHOLDS.map((threshold) => {
        const members = bucketMembers(summary.year, threshold);
        expect(members, `FY${summary.year} above ${threshold * 100}%`).toHaveLength(
          expectedCounts[threshold],
        );
        expect(
          members.every(
            (member) =>
              member.year === summary.year &&
              member.drawRate !== null &&
              member.exclusionReason === null &&
              member.drawRate > threshold,
          ),
        ).toBe(true);
        expect(members.map((member) => member.drawRate)).toEqual(
          [...members].sort((a, b) => b.drawRate - a.drawRate).map((member) => member.drawRate),
        );
        return [threshold, new Set(members.map((member) => member.ipedsId))] as const;
      });

      const memberIds = new Map(membersByThreshold);
      for (const ipedsId of memberIds.get(0.15)!) {
        expect(memberIds.get(0.07)!.has(ipedsId)).toBe(true);
        expect(memberIds.get(0.05)!.has(ipedsId)).toBe(true);
      }
      for (const ipedsId of memberIds.get(0.07)!) {
        expect(memberIds.get(0.05)!.has(ipedsId)).toBe(true);
      }
    }
  });

  it("labels schools and sorts their history", () => {
    const school = ENDOWMENT_DRAW_RATE_SCHOOLS.find((row) => row.state != null);
    expect(school).toBeDefined();
    expect(endowmentSchoolLabel(school!)).toContain(school!.ipedsId);
    expect(endowmentSchoolLabel(school!)).toContain(`· ${school!.state}`);
    const years = endowmentSchoolHistory(school!).map((point) => point.year);
    expect(years).toEqual([...years].sort((a, b) => a - b));
  });
});
