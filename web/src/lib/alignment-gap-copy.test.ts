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

  it("writes the lede as debt burden, then an alignment gap, then two panels", () => {
    const page = src("app/recipes/alignment-gap/page.tsx");
    expect(page).toContain("Debt burden, aid, and");
    expect(page).toContain("financial resources");
    expect(page).toContain("College affordability data lives in several different places.");
    expect(page).toContain("The starting point is");
    expect(page).toContain("debt burden");
    expect(page).toContain("alignment gap");
    expect(page).toContain("expressed per year of college");
    expect(page).toContain("completer");
    expect(page).not.toContain("how much net price would have to fall");
    expect(page).not.toContain("or could rise");
    expect(page).not.toContain("already leaving the building");
    expect(page).not.toContain("students who don");
    expect(page).not.toContain("What a school charges, against what it");
    expect(page).not.toMatch(/Recipe 1B/);
    expect(page).not.toMatch(/IPERS/);
    expect(page).not.toMatch(/Naming it would be accurate and unfair/);

    const chart = src("components/AlignmentGapChart.tsx");
    expect(chart).toContain("testId=\"alignment-gap-tooltip\"");
    expect(chart).toContain("{hover.schoolName}");
    expect(chart).toContain("Compare debt burden with endowment per student");
    expect(chart).toContain("Hover over any dot to see the");
    expect(chart).toContain("var(--ochre)");
    expect(chart).toContain("○ 90% and over");
    expect(chart).toContain("ChartHoverTooltip");
    expect(chart).not.toContain("Could they afford to?");
    expect(chart).not.toContain("var(--forest-2)");
    expect(chart).not.toContain("var(--forest-ink)");
    expect(chart).not.toMatch(/best\.nm \?/);

    const merit = src("components/AlignmentGapMeritChart.tsx");
    expect(merit).toContain("Compare the debt gap with merit aid");
    expect(merit).toContain("merit spend = annual gap");
    expect(merit).toContain("{hover.schoolName}");
    expect(merit).toContain("CDS H2A");
    expect(merit).toContain("var(--ochre)");
    expect(merit).toContain("var(--forest)");
    expect(merit).toContain("○ ");
    expect(merit).toContain("NO MERIT AID");
    expect(merit).toContain("AT OR BELOW MEDIAN");
    expect(merit).toContain("LARGER THAN THE GAP");
    expect(merit).toContain("SMALLER THAN THE GAP");
    expect(merit).toContain("alignment-gap-zero-rail");
    expect(merit).toContain("The vertical axis shows the alignment gap");
    expect(merit).toContain("ChartHoverTooltip");
    expect(merit).not.toContain("Are they already spending it?");
    expect(merit).not.toContain("NO GAP TO CLOSE");
    expect(merit).not.toContain("GENUINELY CONSTRAINED");
    expect(merit).not.toContain("ALREADY SPENDING IT");
    expect(merit).not.toContain("endowmentTercile");
    expect(merit).not.toContain("var(--forest-ink)");

    const tooltip = src("components/ChartHoverTooltip.tsx");
    expect(tooltip).toContain("placeTooltipAwayFromPointer");
    expect(tooltip).toContain("data-tooltip-side");
    expect(tooltip).toContain("pointerEvents: \"none\"");

    const analysis = src("lib/alignment-gap-recipe-analysis.ts");
    expect(analysis).toContain('fill: "none"');
    expect(analysis).toContain('fill: "var(--ochre)"');
    expect(analysis).toContain('fill: "var(--forest)"');
  });

  it("keeps the method notes and drops the old punchy panel names", () => {
    const page = src("app/recipes/alignment-gap/page.tsx").replace(/\s+/g, " ");
    expect(page).toContain("instructional spending equal to about");
    expect(page).toContain("% of its average net price.");
    expect(page).not.toContain("already spending most of net price on instruction");
    expect(page).toContain(
      "reported instructional spending per student exceeds average net price",
    );
    expect(page).not.toContain("because the endowment, not tuition, is paying");
    expect(page).toContain("federal aggregate borrowing");
    expect(page).toContain("dependent undergraduates");
    expect(page).toContain("An example: Bard and Grinnell");
    expect(page).toContain("Those numbers do");
    expect(page).not.toContain("whether an applicant should be able to see both numbers before");
    expect(page).not.toContain("Same students, same outcomes, opposite prices");
    expect(page).toContain("CDS H2A");
    expect(page).toContain("College Scorecard");
    expect(page).toContain("Some awards that combine need and merit may not appear");
    expect(page).toContain("limit=1000&offset=1000");
    expect(page).toContain("limit=1000&offset=2000");
    expect(page).toContain("Content-Range: 0-999/2158");
    expect(page).toContain("[0, 80000]");
    expect(page).toContain("institution_directory.undergraduate_enrollment");
    expect(page).toContain("undergrad_enrollment_scorecard");
    expect(page).toContain("A published $0 grant is kept");
    expect(page).toContain("Merit aid is larger than the gap");
    expect(page).toContain("Merit aid is smaller than the gap");
    expect(page).not.toContain("Already spending it");
    expect(page).not.toContain("Genuinely constrained");
    expect(page).not.toContain("which is why its n is larger");
    expect(page).not.toContain("land far below what those scores predict");
    expect(page).not.toContain("Each panel uses the median burden of the sample it plots");
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
    expect(Math.round(ALIGNMENT_GAP_MERIT_META.coversShare * 100)).toBe(61);
    const recipesIndex = src("app/recipes/page.tsx");
    expect(recipesIndex).toContain(
      "Compare the alignment gap with merit aid, then with endowment per student. Hover any school.",
    );
    expect(recipesIndex).not.toContain("61% already spend more per first-year");
    expect(recipesIndex).not.toContain("63% already spend more per first-year");
  });

  it("keeps published $0 merit aid and shares one median with Panel B", () => {
    expect(ALIGNMENT_GAP_MERIT_META.medianBurden).toBe(
      ALIGNMENT_GAP_META.medianBurden,
    );
    expect(ALIGNMENT_GAP_MERIT_META.endowmentHighCut).toBe(
      ALIGNMENT_GAP_META.medianEndowmentPerStudent,
    );
    expect(ALIGNMENT_GAP_MERIT_META.zeroMeritCount).toBe(5);
    expect(ALIGNMENT_GAP_MERIT_META.exclusions.rangeGrant).toBe(1);
    const zeros = ALIGNMENT_GAP_MERIT_SCHOOLS.filter(
      (row) => row.meritPerFirstYear === 0,
    );
    expect(zeros.map((row) => row.schoolId).sort()).toEqual([
      "amherst",
      "barnard",
      "colgate-university",
      "haverford-college",
      "university-of-the-incarnate-word",
    ]);
    const incarnate = zeros.find(
      (row) => row.schoolId === "university-of-the-incarnate-word",
    );
    expect(incarnate).toBeDefined();
    expect(incarnate!.gap).toBeGreaterThan(0);
    expect(meritRegion(incarnate!.gap, incarnate!.meritPerFirstYear)).toBe(
      "constrained",
    );
    const endowmentById = new Map(
      ALIGNMENT_GAP_SCHOOLS.map((row) => [row.schoolId, row]),
    );
    for (const id of ["hollins-university", "beloit-college", "pratt-institute-main"]) {
      const merit = ALIGNMENT_GAP_MERIT_SCHOOLS.find((row) => row.schoolId === id);
      const endowment = endowmentById.get(id);
      expect(merit).toBeDefined();
      expect(endowment).toBeDefined();
      expect(Math.abs(merit!.gap - endowment!.gap)).toBeLessThan(0.05);
    }
    const ex = ALIGNMENT_GAP_MERIT_META.exclusions;
    expect(
      ex.qualityLimited +
        ex.qualityMissing +
        ex.missingH2a +
        ex.rangeShare +
        ex.rangeGrant +
        ex.missingScorecard +
        ALIGNMENT_GAP_MERIT_META.schoolCount,
    ).toBe(ex.universe);
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
    expect(meritGrantInRange(0)).toBe(true);
    expect(meritGrantInRange(27_587)).toBe(true);
  });
});
