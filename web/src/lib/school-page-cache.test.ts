import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

const files = {
  layout: "../app/schools/[school_id]/layout.tsx",
  hub: "../app/schools/[school_id]/page.tsx",
  year: "../app/schools/[school_id]/[year]/page.tsx",
  acceptance: "../app/schools/[school_id]/acceptance-rate/page.tsx",
  earlyDecision: "../app/schools/[school_id]/early-decision/page.tsx",
  gpa: "../app/schools/[school_id]/gpa/page.tsx",
  hubOg: "../app/schools/[school_id]/opengraph-image.tsx",
  yearOg: "../app/schools/[school_id]/[year]/opengraph-image.tsx",
  feed: "../app/schools/[school_id]/feed.xml/route.ts",
  facts: "../app/api/schools/[school_id]/facts/route.ts",
  sources: "../app/api/schools/[school_id]/sources/route.ts",
  compare: "../app/api/compare/route.ts",
  csv: "../app/schools/[school_id]/[year]/cds.csv/route.ts",
  xlsx: "../app/schools/[school_id]/[year]/cds.xlsx/route.ts",
} as const;

function read(rel: string): string {
  return readFileSync(fileURLToPath(new URL(rel, import.meta.url)), "utf8");
}

describe("school page ISR contract", () => {
  it("force-statics school pages, layout, and OG images", () => {
    for (const rel of [
      files.layout,
      files.hub,
      files.year,
      files.acceptance,
      files.earlyDecision,
      files.gpa,
      files.hubOg,
      files.yearOg,
    ]) {
      const source = read(rel);
      expect(source).toContain('export const dynamic = "force-static"');
      expect(source).toContain("export const revalidate = 3600");
    }
  });

  it("does not force-static route handlers that already set Cache-Control", () => {
    for (const rel of [files.feed, files.facts, files.sources, files.compare, files.csv, files.xlsx]) {
      expect(read(rel)).not.toMatch(/export const dynamic = ["']force-static["']/);
    }
  });
});
