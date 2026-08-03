import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import {
  ENDOWMENT_DRAW_RATE_META,
  ENDOWMENT_DRAW_RATE_SCHOOLS,
  ENDOWMENT_DRAW_RATE_YEAR_SUMMARIES,
  type EndowmentDrawRatePoint,
} from "./endowment-draw-rate-recipe-data";
import {
  DEFAULT_ENDOWMENT_RECIPE_SCHOOL_ID,
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
      const eligible = yearPoints.filter(({ point }) => point.drawRate != null);
      expect(yearPoints).toHaveLength(summary.reporters);
      expect(eligible).toHaveLength(summary.eligible);
      expect(summary.excluded).toBe(summary.reporters - summary.eligible);
      expect(eligible.filter(({ point }) => point.drawRate! > 0.05)).toHaveLength(
        summary.above5Count,
      );
      expect(eligible.filter(({ point }) => point.drawRate! > 0.07)).toHaveLength(
        summary.above7Count,
      );
      expect(eligible.filter(({ point }) => point.drawRate! > 0.15)).toHaveLength(
        summary.above15Count,
      );
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

  it("labels schools and sorts their history", () => {
    const school = ENDOWMENT_DRAW_RATE_SCHOOLS.find((row) => row.state != null);
    expect(school).toBeDefined();
    expect(endowmentSchoolLabel(school!)).toContain(school!.ipedsId);
    expect(endowmentSchoolLabel(school!)).toContain(`· ${school!.state}`);
    const years = endowmentSchoolHistory(school!).map((point) => point.year);
    expect(years).toEqual([...years].sort((a, b) => a - b));
  });
});
