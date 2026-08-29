import { describe, expect, it } from "vitest";
import {
  computeBurden,
  computeEndowmentPerStudent,
  computeGap,
  computeInstructionShare,
  computeMeritPerFirstYear,
  quadrantFor,
} from "./alignment-gap-recipe-analysis";

describe("alignment-gap arithmetic", () => {
  it("matches the Hollins worked example against a 4.42% median burden", () => {
    const burden = computeBurden(286.24, 40075);
    expect(burden).toBeCloseTo(0.08571, 4);
    const gap = computeGap(27000, burden, 0.0442);
    expect(Math.round(gap)).toBe(3269);
    expect(computeEndowmentPerStudent(303_839_322, 665)).toBeCloseTo(456_901, 0);
    expect(computeInstructionShare(19_506, 20_896)).toBeCloseTo(0.933, 3);
  });

  it("puts a high-burden, high-endowment school in capacity", () => {
    expect(quadrantFor(3286, 457_000, 64_000)).toBe("capacity");
    expect(quadrantFor(2040, 70_000, 64_000)).toBe("capacity");
    expect(quadrantFor(3190, 63_000, 64_000)).toBe("constrained");
    expect(quadrantFor(-7727, 4_982_000, 64_000)).toBe("absorbs");
    expect(quadrantFor(-5714, 50_000, 64_000)).toBe("earnings");
  });

  it("computes merit spend as share times average grant", () => {
    expect(computeMeritPerFirstYear(0.29, 45_857)).toBeCloseTo(13_298.53, 1);
  });
});
