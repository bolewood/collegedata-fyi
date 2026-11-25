import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { cdsFreshnessFloor } from "./freshness";

// Shared with SQL cds_freshness_floor() and tools/finder/stuck_pdf_seeds.default_min_fresh_year
// (tools/finder/test_freshness_floor_cases.py reads the same file).
const CASES: { date: string; floor: string }[] = JSON.parse(
  readFileSync(join(process.cwd(), "..", "tests", "fixtures", "freshness_floor_cases.json"), "utf8"),
).cases;

describe("cdsFreshnessFloor", () => {
  it("has the shared cases", () => {
    expect(CASES.length).toBeGreaterThanOrEqual(10);
  });

  it.each(CASES.map((c) => [c.date, c.floor] as const))("%s gives %s", (date, floor) => {
    expect(cdsFreshnessFloor(new Date(`${date}T12:00:00Z`))).toBe(floor);
  });
});
