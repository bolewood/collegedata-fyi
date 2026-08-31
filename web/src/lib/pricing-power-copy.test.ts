import { describe, expect, it } from "vitest";
import { readFileSync } from "node:fs";
import { join } from "node:path";

const src = (rel: string) => readFileSync(join(process.cwd(), "src", rel), "utf8");

const page = src("app/recipes/acceptance-vs-yield/page.tsx");
const chartA = src("components/AcceptanceYieldChart.tsx");
const chartB = src("components/YieldDebtBurdenChart.tsx");
const sources = [page, chartA, chartB].join("\n");
const folded = sources.replace(/\s+/g, " ");

const BANNED = [
  "smoking gun",
  "with teeth",
  "second-choice",
  "safety-school",
  "desperate",
  "wasting money",
  "bloated administration",
  "students don't want",
  "students don’t want",
  "bad deal",
  "good deal",
  "overpriced",
  "best quadrant",
  "worst quadrant",
  "percent spent on teaching",
  "citeturn",
  "fileciteturn",
] as const;

describe("pricing-power copy", () => {
  it("never uses the banned analytical voice in the page or charts", () => {
    const lower = sources.toLowerCase();
    for (const phrase of BANNED) {
      expect(lower, `banned phrase present: ${phrase}`).not.toContain(phrase.toLowerCase());
    }
    expect(sources).not.toMatch(/on paper/i);
    expect(sources).not.toMatch(/in practice/i);
    expect(sources).not.toMatch(/selective on paper/i);
    expect(sources).not.toMatch(/selective in practice/i);
  });

  it("keeps the load-bearing caveats on the page and both median-divider captions", () => {
    expect(folded).toContain(
      "This page does not estimate how enrollment would change if a college changed its price",
    );
    expect(folded).toContain("does not estimate elasticity");
    expect(folded).toContain(
      "The admissions figures on this page are from the fall 2024 entering class",
    );
    expect(folded).toContain("fall 2025 class");
    expect(folded).toContain("academic year that began in August 2026");
    expect(folded).toContain("could have pulled from its wait list");
    expect(folded).toContain("maintain academic standards");
    expect(folded).toContain("Federal data for 2023");
    expect(folded).toContain("NCES");
    expect(folded).toContain("not a budget share");
    expect(chartA).toContain("Dividers are this sample");
    expect(chartA).toContain("not 50% lines");
    expect(chartB).toContain("Dividers are this sample");
    expect(chartB).toContain("debt burden among");
  });

  it("titles the recipe College Pricing Power and keeps the existing route", () => {
    expect(page).toContain('title: "College Pricing Power"');
    expect(page).toContain("College Pricing Power");
    expect(page).toContain("Acceptance, yield, price, and student outcomes.");
    expect(page).toContain('canonical: "/recipes/acceptance-vs-yield"');
    expect(page).toContain("COLLEGE PRICING POWER");
    expect(page).toContain("recipe_writeup_opened");
    expect(page).toContain("download_clicked");
    expect(page).toContain("docs/recipes/acceptance-vs-yield.md");
    expect(page).toContain("/recipes/acceptance-vs-yield-starter.xlsx");
  });

  it("renders dots without per-circle mouse handlers and hit-tests on pointermove", () => {
    expect(chartA).toContain("nearestPoint");
    expect(chartA).toContain("onPointerMove");
    expect(chartA).toContain("dangerouslySetInnerHTML");
    expect(chartA).not.toContain("onMouseEnter");
    expect(chartA).not.toContain("onPointerEnter");
    expect(chartB).toContain("nearestPoint");
    expect(chartB).toContain("onPointerMove");
    expect(chartB).toContain("dangerouslySetInnerHTML");
    expect(chartB).toContain("sizeEncoding = false");
    expect(chartB).not.toContain("onMouseEnter");
    expect(chartB).not.toContain("onPointerEnter");
  });
});
