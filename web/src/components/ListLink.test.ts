import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const src = (rel: string) => readFileSync(join(process.cwd(), "src", rel), "utf8");

const DENSE_SCHOOL_LISTS = [
  "components/SchoolTable.tsx",
  "components/SchoolBrowser.tsx",
  "components/CoverageDashboard.tsx",
  "components/SchoolListItem.tsx",
  "components/DocumentCard.tsx",
  "components/AcceptanceRateTable.tsx",
  "components/EarlyDecisionTable.tsx",
  "components/GpaTable.tsx",
  "components/WaitlistOddsExplorer.tsx",
  "components/EndowmentDrawRateExplorer.tsx",
  "app/schools/[school_id]/page.tsx",
  "app/pipeline-observation/page.tsx",
  "app/changes/page.tsx",
] as const;

describe("ListLink", () => {
  it("forces prefetch={false} so viewport and hover do not fetch", () => {
    const link = src("components/ListLink.tsx");
    expect(link).toContain("prefetch={false}");
    expect(link).toContain('from "next/link"');
  });

  it("is used by dense school and year lists", () => {
    for (const rel of DENSE_SCHOOL_LISTS) {
      const source = src(rel);
      expect(source, rel).toMatch(/from ["']@\/components\/ListLink["']|from ["']\.\/ListLink["']/);
      expect(source, rel).toContain("<ListLink");
    }
  });

  it("keeps the schools directory free of viewport-prefetching next/link rows", () => {
    const table = src("components/SchoolTable.tsx");
    expect(table).not.toMatch(/from ["']next\/link["']/);
    expect(table).not.toMatch(/<Link[\s\S]*\/schools\//);
  });
});
