import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import {
  ALIGNMENT_GAP_MERIT_META,
  ALIGNMENT_GAP_MERIT_SCHOOLS,
  ALIGNMENT_GAP_META,
  ALIGNMENT_GAP_SCHOOLS,
} from "./alignment-gap-recipe-data";
import {
  computeMeritPerFirstYear,
  coversGap,
  formatEndowmentPerStudent,
  formatInstructionShare,
  meritGrantInRange,
  meritRegion,
  meritShareInRange,
} from "./alignment-gap-recipe-analysis";

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

  it("writes the lede as burden, then a debt gap, then two panels", () => {
    const page = src("app/recipes/alignment-gap/page.tsx");
    expect(page).toContain("What a school charges, against what it");
    expect(page).toContain("Debt burden is the share of median 10-year earnings");
    expect(page).toContain("expressed per year of enrollment");
    expect(page).toContain("completer");
    expect(page).toContain("corpus median burden");
    expect(page).not.toContain("how much net price would have to fall");
    expect(page).not.toContain("or could rise");
    expect(page).toContain("Hover any dot");
    expect(page).not.toMatch(/Recipe 1B/);
    expect(page).not.toMatch(/IPERS/);
    expect(page).not.toMatch(/Naming it would be accurate and unfair/);

    const chart = src("components/AlignmentGapChart.tsx");
    expect(chart).toContain("data-testid=\"alignment-gap-tooltip\"");
    expect(chart).toContain("{hover.schoolName}");
    expect(chart).toContain("Could they afford to?");
    expect(chart).toContain("Hover any dot — every school is named");
    expect(chart).not.toMatch(/best\.nm \?/);

    const merit = src("components/AlignmentGapMeritChart.tsx");
    expect(merit).toContain("Are they already spending it?");
    expect(merit).toContain("merit spend = annual gap");
    expect(merit).toContain("{hover.schoolName}");
    expect(merit).toContain("CDS H2A");
  });

  it("applies the seven copy fixes", () => {
    const page = src("app/recipes/alignment-gap/page.tsx");
    expect(page).toContain(
      "the lowest instruction-to-net-price ratio of its peer group at 0.76",
    );
    expect(page).not.toContain("already spending most of net price on instruction");
    expect(page).toContain(
      "Instruction often exceeds net price — at these endowment levels, tuition is not what pays for the classroom.",
    );
    expect(page).not.toContain("because the endowment, not tuition, is paying");
    expect(page).toContain("federal aggregate borrowing");
    expect(page).toContain("dependent undergraduates");
    expect(page).toContain("Bard and Grinnell enroll students with almost identical median SATs");
    expect(page).toContain("whether an applicant should be able to see both numbers before");
    expect(page).toContain("CDS H2A");
    expect(page).toContain("The vertical axis is");
    expect(page).toContain("College Scorecard");
    expect(page).toContain("excludes some mixed-need merit awards");
  });

  it("recomputes merit-join region counts against the plotted sample", () => {
    expect(ALIGNMENT_GAP_MERIT_SCHOOLS.length).toBe(
      ALIGNMENT_GAP_MERIT_META.schoolCount,
    );
    const { covers, constrained, none } = ALIGNMENT_GAP_MERIT_META.regions;
    expect(covers + constrained + none).toBe(ALIGNMENT_GAP_MERIT_SCHOOLS.length);
    expect(covers + constrained).toBe(ALIGNMENT_GAP_MERIT_META.positiveGap);

    let liveCovers = 0;
    let liveConstrained = 0;
    let liveNone = 0;
    for (const row of ALIGNMENT_GAP_MERIT_SCHOOLS) {
      expect(meritShareInRange(row.meritShare)).toBe(true);
      expect(meritGrantInRange(row.avgMeritGrant)).toBe(true);
      const region = meritRegion(row.gap, row.meritPerFirstYear);
      if (region === "covers") liveCovers += 1;
      else if (region === "constrained") liveConstrained += 1;
      else liveNone += 1;
    }
    expect(liveCovers).toBe(covers);
    expect(liveConstrained).toBe(constrained);
    expect(liveNone).toBe(none);
    expect(covers / ALIGNMENT_GAP_MERIT_META.positiveGap).toBeCloseTo(
      ALIGNMENT_GAP_MERIT_META.coversShare,
      3,
    );
    expect(Math.round(ALIGNMENT_GAP_MERIT_META.coversShare * 100)).toBe(63);
  });

  it("keeps Bard and Grinnell on the endowment panel and out of the merit join", () => {
    const endowmentIds = new Set(ALIGNMENT_GAP_SCHOOLS.map((row) => row.schoolId));
    const meritIds = new Set(ALIGNMENT_GAP_MERIT_SCHOOLS.map((row) => row.schoolId));
    for (const id of [
      "bard-college",
      "grinnell-college",
      "bennington-college",
      "sarah-lawrence-college",
      "oberlin",
      "earlham-college",
    ]) {
      expect(endowmentIds.has(id)).toBe(true);
      expect(meritIds.has(id)).toBe(false);
    }
  });
});

describe("alignment-gap merit arithmetic", () => {
  it("matches Quincy: every first-year receives the average grant", () => {
    const merit = computeMeritPerFirstYear(1, 27_587);
    expect(merit).toBe(27_587);
    expect(coversGap(merit, 1_545)).toBe(true);
    expect(meritRegion(1_545, merit)).toBe("covers");
    expect(meritRegion(3_267, 330)).toBe("constrained");
    expect(meritRegion(-1_000, 5_000)).toBe("none");
  });

  it("rejects H2A range violations the quality flag misses", () => {
    expect(meritShareInRange(120.87)).toBe(false);
    expect(meritShareInRange(1.045)).toBe(false);
    expect(meritShareInRange(0.193)).toBe(true);
    expect(meritGrantInRange(85_600)).toBe(false);
    expect(meritGrantInRange(0)).toBe(false);
    expect(meritGrantInRange(27_587)).toBe(true);
  });
});
