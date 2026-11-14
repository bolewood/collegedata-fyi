import { describe, expect, it } from "vitest";
import { countsFromGroups, formatMatchSummary, type MatchFitCounts } from "./match-share";

const EMPTY: MatchFitCounts = {
  strong_academic_fit: 0,
  above_range: 0,
  in_range: 0,
  below_range: 0,
  unknown: 0,
};

describe("formatMatchSummary", () => {
  it("empty result set", () => {
    expect(formatMatchSummary(EMPTY)).toMatchInlineSnapshot(`
      "CollegeData.fyi Match
      No schools ranked yet

      https://www.collegedata.fyi/match"
    `);
  });
  it("small result set", () => {
    expect(
      formatMatchSummary({ ...EMPTY, strong_academic_fit: 1, in_range: 2 }),
    ).toMatchInlineSnapshot(`
      "CollegeData.fyi Match
      3 schools ranked

      Strong fit   █████       1
      Above range              0
      In range     ██████████  2
      Below range              0
      Unknown                  0

      https://www.collegedata.fyi/match"
    `);
  });
  it("large result set", () => {
    expect(
      formatMatchSummary({
        strong_academic_fit: 8,
        above_range: 5,
        in_range: 15,
        below_range: 9,
        unknown: 5,
      }),
    ).toMatchInlineSnapshot(`
      "CollegeData.fyi Match
      42 schools ranked

      Strong fit   █████        8
      Above range  ███          5
      In range     ██████████  15
      Below range  ██████       9
      Unknown      ███          5

      https://www.collegedata.fyi/match"
    `);
  });
  it("singular school", () => {
    expect(formatMatchSummary({ ...EMPTY, in_range: 1 })).toContain("1 school ranked");
  });
  it("never carries a share code or profile values", () => {
    const text = formatMatchSummary({ ...EMPTY, in_range: 12, unknown: 3 });
    expect(text).not.toMatch(/code=/i);
    expect(text).not.toMatch(/\b[0-9A-Z]{3}-[0-9A-Z]{3}\b/);
    expect(text).not.toMatch(/GPA|SAT|ACT/);
  });
});

describe("countsFromGroups", () => {
  it("counts each bucket", () => {
    expect(
      countsFromGroups({
        strong_academic_fit: [1],
        above_range: [],
        in_range: [1, 2],
        below_range: [],
        unknown: [1, 2, 3],
      }),
    ).toEqual({ strong_academic_fit: 1, above_range: 0, in_range: 2, below_range: 0, unknown: 3 });
  });
});
