import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const src = (rel: string) => readFileSync(join(process.cwd(), "src", rel), "utf8");

describe("Wave 2 product copy", () => {
  it("keeps Compare chrome free of browser/primary/queryable", () => {
    const browse = src("app/browse/page.tsx");
    expect(browse).toContain('title: "Compare schools"');
    expect(browse).toMatch(/as\s+the school published it/);
    expect(browse).toContain("side by side");
    expect(browse).toContain('label="Reports"');
    expect(browse).toMatch(/2024[–-]25 and newer/);
    expect(browse).not.toMatch(/Queryable/);
    expect(browse).not.toMatch(/PRIMARY ROWS/);
    expect(browse).not.toMatch(/§ BROWSER/);
    // queryable_field_count is a corpus total over 2024+ cds_fields, never a per-report count or metric-definition count
    expect(browse).not.toMatch(/per report/i);
    expect(browse).not.toContain('label="Metrics"');

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
    expect(page).toContain('href="/coverage"');
    expect(page).toMatch(/federal data/i);
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
    expect(match).toMatch(/no stored student profile|never save a\s+student profile/i);
    expect(match).toMatch(/published numbers|published admissions/i);
    expect(match).not.toMatch(/source-backed/);
    expect(match).not.toMatch(/corpus/);
    // MatchListBuilder has no size or cost filters (those live on /browse)
    const matchBuilder = src("components/MatchListBuilder.tsx");
    if (!/name="(size|cost|netPrice)"/.test(matchBuilder)) {
      expect(match).not.toMatch(/\b(size|cost)\b/i);
    }

    const coverage = src("app/coverage/page.tsx");
    expect(coverage).toContain('title: "Coverage"');
    expect(coverage).toMatch(/federal student aid/i);
    expect(coverage).toContain("haven&rsquo;t checked this");
    expect(coverage).toContain("Federal numbers stay labeled as federal");
    expect(coverage).not.toMatch(/Title-IV/);
    expect(coverage).not.toMatch(/resolver has not scanned/);
    expect(coverage).not.toMatch(/labeled separately so readers can tell/);
    expect(coverage).not.toMatch(/resolver's last attempt/);
  });

  it("keeps homepage stats and lede truthful to the underlying counts and directory pages", () => {
    const home = src("app/page.tsx");
    // total_schools counts schools, not reports, and scorecard_institution_count includes CDS schools
    expect(home).toContain('label="Schools" value={schoolsValue}');
    expect(home).not.toMatch(/plus\s+\$\{stats\.scorecard_institution_count/);
    // queryable_field_count is a corpus total, never a per-report count
    expect(home).not.toMatch(/per report/i);
    // Federal-only directory school pages have no archived CDS file to link
    expect(home).not.toMatch(/Every page links/i);
  });
});
