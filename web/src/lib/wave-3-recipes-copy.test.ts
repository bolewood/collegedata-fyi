import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const src = (rel: string) => readFileSync(join(process.cwd(), "src", rel), "utf8");
const docs = (rel: string) =>
  readFileSync(join(process.cwd(), "..", "docs", rel), "utf8");

describe("Wave 3 Recipes copy", () => {
  it("rewrites the index for IR and analysts", () => {
    const page = src("app/recipes/page.tsx");
    expect(page).toContain(
      "Worked examples from Common Data Set filings and federal data",
    );
    expect(page).toContain("institutional researchers and analysts");
    expect(page).toContain("a chart you can operate");
    expect(page).toContain("Written for IR and analysts. Counselors are welcome.");
    expect(page).toContain(
      "IR and enrollment managers comparing peer yield and federal-loan burden; analysts joining IPEDS ADM counts to College Scorecard.",
    );
    expect(page).toContain(
      "IR and policy analysts reading effective policy from C9 submission rates; C8 is the written version.",
    );
    expect(page).toContain("Enrollment managers and IR. C2 offer / accept / admit, bucketed.");
    expect(page).toContain("IR, college-finance reporters, trustees. IPEDS F2 Part H estimate.");
    expect(page).toContain("Hover any school.");
    expect(page).toContain("CDS H2A merit aid to Scorecard earnings and debt");
    expect(page).toContain("C8 states the rule; C9 counts what enrolled first-years did.");
    expect(page).toContain("federal control, size, and Carnegie class");
    expect(page).not.toMatch(/PRs welcome/);
    expect(page).not.toMatch(/Counselors second/);
    expect(page).not.toMatch(/written disclosures lie/i);
    expect(page).not.toMatch(/emotionally invested/);
    expect(page).not.toMatch(/Audit your own school's extraction/);
  });

  it("retires the eighteen-school seed for the pricing-power rebuild", () => {
    // The full copy contract for the rebuilt page lives in
    // pricing-power-copy.test.ts; this suite only guards that the old
    // seed-era framing cannot come back.
    const page = src("app/recipes/acceptance-vs-yield/page.tsx");
    expect(page).toContain("College Pricing Power");
    expect(page).not.toMatch(/eighteen-school seed/);
    expect(page).not.toMatch(/three hand-checked anchors/);
    expect(page).not.toMatch(/Scale to all 697 schools/);

    const chart = src("components/AcceptanceYieldChart.tsx");
    expect(chart).toContain("Fig. 1 · Acceptance rate vs. yield");
    expect(chart).not.toMatch(/18-school seed/);
  });

  it("writes test-optional as effective policy from C9, not a parent wink", () => {
    const page = src("app/recipes/test-optional-tracker/page.tsx");
    expect(page).toContain("SAT submission as");
    expect(page).toContain("effective policy.");
    expect(page).toContain("seven well-documented schools");
    expect(page).toContain("Bands score");
    expect(page).toContain("combined SAT + ACT");
    expect(page).toContain("Written policy underdetermines practice");
    expect(page).not.toMatch(/Test-<span/);
    expect(page).not.toMatch(/written disclosures lie/i);
    expect(page).not.toMatch(/seven schools with a long series/);
  });

  it("heads wait-list with the C2 triplet and labels federal buckets", () => {
    const page = src("app/recipes/waitlist-odds/page.tsx");
    expect(page).toContain("Offered, accepted,");
    expect(page).toContain("admitted.");
    expect(page).toContain("bucketed by C1 selectivity and by federal");
    expect(page).toContain("from the filings, not the article");
    expect(page).toContain("admitted divided by accepted wait-list spots");
    expect(page).not.toMatch(/hopes up/);
    expect(page).not.toMatch(/matters to an applicant/);

    const explorer = src("components/WaitlistOddsExplorer.tsx");
    expect(explorer).not.toMatch(/extractor filled/);
    expect(explorer).toContain("published count does not match the source");
  });

  it("relabels the endowment ledger without a hardcoded five-year span", () => {
    const page = src("app/recipes/endowment-draw-rate/page.tsx");
    expect(page).toContain('className="meta">Rows</span>');
    expect(page).toContain("{fiscalYearRange}");
    expect(page).not.toMatch(/School-year rows/);
    expect(page).not.toMatch(/across five years/);
  });

  it("drops named extractor war stories from recipe write-ups", () => {
    expect(docs("recipes/acceptance-vs-yield.md")).not.toMatch(/Tier 4 flattened PDFs/);
    expect(docs("recipes/acceptance-vs-yield.md")).not.toMatch(/LLM fallback/);
    expect(docs("recipes/test-optional-tracker.md")).not.toMatch(/extraction-noise outlier/);
    expect(docs("recipes/test-optional-tracker.md")).not.toMatch(/flattened-PDF/);
    expect(docs("recipes/waitlist-odds.md")).not.toMatch(/over-filled by Tier 4 extraction/);
    expect(docs("recipes/README.md")).toContain("Audit your school’s numbers.");
    expect(docs("recipes/README.md")).not.toMatch(/Audit your own school's extraction/);
    expect(docs("recipes/README.md")).not.toMatch(/written disclosures lie/i);
  });
});
