import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ALIGNMENT_GAP_META, ALIGNMENT_GAP_SCHOOLS } from "./alignment-gap-recipe-data";
import { formatEndowmentPerStudent, formatInstructionShare } from "./alignment-gap-recipe-analysis";

const src = (rel: string) => readFileSync(join(process.cwd(), "src", rel), "utf8");

describe("alignment-gap recipe", () => {
  it("names every school so unlabeled dots can still show a tooltip", () => {
    expect(ALIGNMENT_GAP_SCHOOLS.length).toBe(ALIGNMENT_GAP_META.schoolCount);
    expect(ALIGNMENT_GAP_SCHOOLS.length).toBeGreaterThan(300);
    for (const row of ALIGNMENT_GAP_SCHOOLS) {
      expect(row.schoolName.trim().length).toBeGreaterThan(2);
      expect(row.schoolId.length).toBeGreaterThan(1);
    }
    const ids = ALIGNMENT_GAP_SCHOOLS.map((row) => row.schoolId);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("formats instruction share above 100% as a multiple, not a truncated percent", () => {
    expect(formatInstructionShare(1.19)).toBe("119% of net price");
    expect(formatInstructionShare(11.19)).toBe("11.2× net price");
    expect(formatEndowmentPerStudent(64_403)).toBe("$64k");
    expect(formatEndowmentPerStudent(4_982_000)).toBe("$4.98M");
  });

  it("writes the lede as burden, then gap, then endowment", () => {
    const page = src("app/recipes/alignment-gap/page.tsx");
    expect(page).toContain("What a school charges, against what it");
    expect(page).toContain("Debt burden is the share of median 10-year earnings");
    expect(page).toContain("Hover any dot");
    expect(page).not.toMatch(/Recipe 1B/);
    expect(page).not.toMatch(/IPERS/);
    expect(page).not.toMatch(/Naming it would be accurate and unfair/);

    const chart = src("components/AlignmentGapChart.tsx");
    expect(chart).toContain("data-testid=\"alignment-gap-tooltip\"");
    expect(chart).toContain("{hover.schoolName}");
    expect(chart).toContain("Hover any dot — every school is named");
    expect(chart).not.toMatch(/best\.nm \?/);
  });
});
