import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const src = (rel: string) => readFileSync(join(process.cwd(), "src", rel), "utf8");

describe("Wave 4 methodology and API copy", () => {
  it("aligns the methodology index with school-card kickers", () => {
    const page = src("app/methodology/page.tsx");
    expect(page).toContain("How the school-page cards read Common Data Set filings");
    expect(page).toContain("How the cards are");
    expect(page).toContain("The trail behind the school-page cards");
    expect(page).toContain("enrolled first-years. Not a chance-me.");
    expect(page).toContain("what CDS will not let you compute");
    expect(page).toContain("federal net-price and outcome context");
    expect(page).not.toMatch(/admitted-class bands/);
    expect(page).not.toMatch(/turns Common Data Set source documents into/);
  });

  it("writes academic profile as enrolled first-years, not admits", () => {
    const page = src("app/methodology/positioning/page.tsx");
    expect(page).toContain('title: "Academic profile methodology"');
    expect(page).toContain("Academic");
    expect(page).toContain("profile.");
    expect(page).toContain("enrolled first-years — the entering class, not the");
    expect(page).toContain("score bands describe all enrolled");
    expect(page).toContain("not the full entering class");
    expect(page).toContain("does not score rank");
    expect(page).toContain("the student&apos;s entered GPA");
    expect(page).not.toMatch(/PRD 016/);
    expect(page).not.toMatch(/your scores/);
    expect(page).not.toMatch(/admitted-class/);
    expect(page).not.toMatch(/v1 does not/);
    expect(page).not.toMatch(/v1 displays/);
  });

  it("renames admission strategy to admission rounds and drops operator notes", () => {
    const page = src("app/methodology/admission-strategy/page.tsx");
    expect(page).toContain('title: "Admission rounds methodology"');
    expect(page).toContain("Admission");
    expect(page).toContain("rounds.");
    expect(page).toContain("what Section C actually publishes");
    expect(page).toContain("We do not estimate a general-pool ED rate");
    expect(page).toContain("documented on the");
    expect(page).not.toMatch(/in v1 because/);
    expect(page).not.toMatch(/PRD 016B/);
    expect(page).not.toMatch(/Phase 0/);
  });

  it("keeps H2A caveats and drops the Tier 4 redrain coverage story", () => {
    const page = src("app/methodology/merit-profile/page.tsx");
    expect(page).toContain('title: "Merit and need aid methodology"');
    expect(page).toContain("federal College Scorecard");
    expect(page).toContain("335 of 488");
    expect(page).toContain("H.2A02");
    expect(page).not.toMatch(/Tier 4/);
    expect(page).not.toMatch(/redrain/);
    expect(page).not.toMatch(/effective first-year merit answerability/);
  });

  it("rewrites API docs off changelog, runbook, and extractor lore", () => {
    const page = src("app/api/page.tsx");
    expect(page).toContain("The ");
    expect(page).toContain("public");
    expect(page).toContain("API.");
    expect(page).toContain("Two ways in");
    expect(page).toContain("api.collegedata.fyi");
    expect(page).toContain("Start here");
    expect(page).toContain("https://www.collegedata.fyi/api/mcp");
    expect(page).toContain("Add custom connector");
    expect(page).toContain("claude_desktop_config.json");
    expect(page).toContain(
      "/absolute/path/to/collegedata-fyi/packages/mcp-server/bin/collegedata-mcp.js",
    );
    expect(page).not.toMatch(/"args": \["packages\/mcp-server\/bin\/collegedata-mcp\.js"\]/);
    expect(page).not.toMatch(/from the repository root/);
    expect(page).not.toMatch(/The MCP server is a single Node file in the repo/);
    expect(page).toContain("When a value is missing");
    expect(page).toContain("the school&apos;s filing leaves the field blank");
    expect(page).toContain("Search latest-per-school rows (Compare)");
    expect(page).toContain("Compare&apos;s latest-per-school ranking");
    expect(page).toContain("Fetch the canonical artifact for a document");
    expect(page).toContain("the canonical artifact is the one the site");
    expect(page).toContain("The curated serving layer behind Compare");
    expect(page).toContain(".eq(\"extraction_status\", \"extracted\")");
    expect(page).not.toMatch(/now exposes/);
    expect(page).not.toMatch(/Runbook/);
    expect(page).not.toMatch(/Smoke-test/);
    expect(page).not.toMatch(/Docling/);
    expect(page).not.toMatch(/Tier 4/);
    expect(page).not.toMatch(/website browser/);
    expect(page).not.toMatch(/text-gray-900/);
    expect(page).not.toMatch(/projected value/);
  });
});
