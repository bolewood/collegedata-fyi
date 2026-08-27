import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const src = (rel: string) => readFileSync(join(process.cwd(), "src", rel), "utf8");

describe("Wave 2 product copy", () => {
  it("keeps Compare chrome free of browser/primary/queryable", () => {
    const browse = src("app/browse/page.tsx");
    expect(browse).toContain('title: "Compare schools"');
    expect(browse).toMatch(/as the school published it/);
    expect(browse).toContain("side by side");
    expect(browse).toContain('label="Reports"');
    expect(browse).toContain("2024-25 and newer");
    expect(browse).not.toMatch(/Queryable/);
    expect(browse).not.toMatch(/PRIMARY ROWS/);
    expect(browse).not.toMatch(/§ BROWSER/);

    const browser = src("components/SchoolBrowser.tsx");
    expect(browser).toContain("Building a list? Use Match.");
    expect(browser).toContain("Couldn&apos;t load");
    expect(browser).toContain("Try again in a moment.");
    expect(browser).not.toMatch(/Browser query failed/);
    expect(browser).not.toMatch(/Looking for fit ranking/);
    expect(browser).not.toMatch(/primary school-year rows/);
  });

  it("points the schools directory at Coverage and restyles off gray/blue", () => {
    const page = src("app/schools/page.tsx");
    expect(page).toContain('title: "Schools"');
    expect(page).toContain("Common Data Set on file");
    expect(page).toContain("Every school we have a report from");
    expect(page).toContain('href="/coverage"');
    expect(page).not.toMatch(/School Directory/);
    expect(page).not.toMatch(/text-gray-900/);

    const table = src("components/SchoolTable.tsx");
    expect(table).toContain("Try the site search");
    expect(table).not.toMatch(/text-blue-600/);
    expect(table).not.toMatch(/focus:border-blue-500/);
    expect(table).not.toMatch(/No schools found matching/);
  });

  it("keeps Common Data Set in school and year SEO without extract language", () => {
    const school = src("app/schools/[school_id]/page.tsx");
    expect(school).toContain("${name} Common Data Set");
    expect(school).not.toMatch(/\(CDS\) Archive/);
    expect(school).not.toMatch(/extracted by collegedata/);
    expect(school).not.toMatch(/1,105-field schema/);
    expect(school).toContain("directoryOnlyLead");

    const year = src("app/schools/[school_id]/[year]/page.tsx");
    expect(year).toContain("The numbers, as published");
    expect(year).not.toMatch(/All extracted fields/);
    expect(year).not.toMatch(/Structured data coming soon/);
    expect(year).not.toMatch(/plus extracted admissions/);
  });

  it("rewrites Match and Coverage in product voice", () => {
    const match = src("app/match/page.tsx");
    expect(match).toContain('title: "Match"');
    expect(match).toContain("No student profile stored");
    expect(match).toContain("school&apos;s own numbers");
    expect(match).toContain("Enter scores and GPA");
    expect(match).not.toMatch(/source-backed/);
    expect(match).not.toMatch(/corpus/);

    const coverage = src("app/coverage/page.tsx");
    expect(coverage).toContain('title: "Coverage"');
    expect(coverage).toContain("takes federal student aid");
    expect(coverage).toContain("haven&rsquo;t checked this");
    expect(coverage).toContain("Federal numbers stay labeled as federal");
    expect(coverage).not.toMatch(/Title-IV institution in the/);
    expect(coverage).not.toMatch(/resolver has not scanned/);
    expect(coverage).not.toMatch(/labeled separately so readers can tell/);
    expect(coverage).not.toMatch(/resolver's last attempt/);
  });
});
