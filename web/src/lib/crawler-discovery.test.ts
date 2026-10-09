import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { GET as getLlmsTxt } from "../app/llms.txt/route";
import { GET as getRobotsTxt } from "../app/robots.txt/route";
import { LLMS_TXT } from "./llms-txt";
import { ROBOTS_RULES, ROBOTS_TXT } from "./robots-txt";
import { SITE_URL } from "./sitemap-static";

const src = (rel: string) => readFileSync(join(process.cwd(), "src", rel), "utf8");

describe("robots.txt", () => {
  it("keeps the existing allow, disallow, and sitemap rules", () => {
    expect(ROBOTS_RULES).toEqual({
      userAgent: "*",
      allow: "/",
      disallow: "/ink-lab",
      sitemap: `${SITE_URL}/sitemap.xml`,
    });
    expect(ROBOTS_TXT).toContain(`User-Agent: ${ROBOTS_RULES.userAgent}`);
    expect(ROBOTS_TXT).toContain(`Allow: ${ROBOTS_RULES.allow}`);
    expect(ROBOTS_TXT).toContain(`Disallow: ${ROBOTS_RULES.disallow}`);
    expect(ROBOTS_TXT).toContain(`Sitemap: ${ROBOTS_RULES.sitemap}`);
  });

  it("comments point automated clients at the API docs and llms.txt", () => {
    expect(ROBOTS_TXT).toContain(`# Docs: ${SITE_URL}/api`);
    expect(ROBOTS_TXT).toContain(`# Machine-readable guide: ${SITE_URL}/llms.txt`);
    expect(ROBOTS_TXT).not.toMatch(/^Disallow: \/$/m);
  });

  it("serves the same body from /robots.txt", async () => {
    const response = getRobotsTxt();
    expect(response.headers.get("Content-Type")).toBe("text/plain; charset=utf-8");
    await expect(response.text()).resolves.toBe(ROBOTS_TXT);
  });
});

describe("llms.txt", () => {
  it("follows the llmstxt.org heading and blockquote shape", () => {
    expect(LLMS_TXT.startsWith("# CollegeData.FYI\n\n> ")).toBe(true);
    expect(LLMS_TXT).toContain("## API");
    expect(LLMS_TXT).toContain("## Optional");
    expect(LLMS_TXT).toMatch(/- \[API docs\]\(https:\/\/www\.collegedata\.fyi\/api\)/);
  });

  it("lists only friendly endpoints that exist in OpenAPI", () => {
    const openapi = src("app/openapi.json/route.ts");
    const listed = [
      "/api/mcp",
      "/api/schools/search",
      "/api/schools/{school_id}/facts",
      "/api/schools/{school_id}/sources",
      "/api/compare",
      "/api/fields",
      "/api/snapshots",
    ];
    for (const path of listed) {
      expect(openapi).toContain(`"${path}"`);
    }
    expect(LLMS_TXT).toContain(`${SITE_URL}/api/mcp`);
    expect(LLMS_TXT).toContain(`${SITE_URL}/api/schools/search?q=mit`);
    expect(LLMS_TXT).toContain(`${SITE_URL}/api/schools/mit/facts`);
    expect(LLMS_TXT).toContain(`${SITE_URL}/api/schools/mit/sources`);
    expect(LLMS_TXT).toContain(`${SITE_URL}/api/compare?schools=mit,yale,university-of-chicago`);
    expect(LLMS_TXT).toContain(`${SITE_URL}/api/fields`);
    expect(LLMS_TXT).toContain(`${SITE_URL}/api/snapshots`);
    expect(LLMS_TXT).toContain(`${SITE_URL}/openapi.json`);
    expect(LLMS_TXT).not.toContain("/api/facts/");
    expect(LLMS_TXT).not.toContain("/rest/v1/");
  });

  it("asks agents to use the API and states the existing license", () => {
    expect(LLMS_TXT).toContain("Please use the API rather than scraping HTML school pages.");
    expect(LLMS_TXT).toContain("The dataset is MIT-licensed.");
    expect(LLMS_TXT).toContain("owned by their respective institutions");
  });

  it("serves the same body from /llms.txt", async () => {
    const response = await getLlmsTxt();
    expect(response.headers.get("Content-Type")).toBe("text/plain; charset=utf-8");
    await expect(response.text()).resolves.toBe(LLMS_TXT);
  });
});

describe("school-page API discovery", () => {
  it("renders a one-line API note from the school record layout", () => {
    const note = src("components/SchoolApiNote.tsx");
    const layout = src("app/schools/[school_id]/layout.tsx");
    expect(note).toContain("Building something with this data?");
    expect(note).toContain('href="/api"');
    expect(note).toContain("Use the free API");
    expect(layout).toContain("<SchoolApiNote />");
  });

  it("advertises the per-school facts JSON alternate on hub and year pages", () => {
    const hub = src("app/schools/[school_id]/page.tsx");
    const year = src("app/schools/[school_id]/[year]/page.tsx");
    expect(hub).toContain('"application/json": `/api/schools/${resolvedSchoolId}/facts`');
    expect(year).toContain('"application/json": `/api/schools/${resolvedSchoolId}/facts`');
  });
});
