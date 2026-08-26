import { readdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { metadata as aboutMetadata } from "../app/about/page";
import { metadata as cdsMetadata } from "../app/about/common-data-set/page";
import { metadata as scorecardMetadata } from "../app/about/college-scorecard/page";
import { metadata as ipedsMetadata } from "../app/about/ipeds/page";

describe("About source-story metadata", () => {
  it("gives each source page a unique title and /about canonical", () => {
    const pages = [cdsMetadata, scorecardMetadata, ipedsMetadata];
    const titles = new Set(pages.map((page) => page.title));
    const canonicals = pages.map((page) => page.alternates?.canonical);
    expect(titles.size).toBe(3);
    expect(canonicals).toEqual([
      "/about/common-data-set",
      "/about/college-scorecard",
      "/about/ipeds",
    ]);
    expect(aboutMetadata.alternates?.canonical).toBe("/about");
    expect(canonicals).not.toContain("/methodology/common-data-set");
    expect(String(cdsMetadata.description)).toMatch(/yearly report a college publishes/i);
    expect(String(aboutMetadata.description)).toMatch(/most comprehensive free college data/i);
  });
});

describe("Wave 1 product copy", () => {
  const src = (rel: string) =>
    readFileSync(join(process.cwd(), "src", rel), "utf8");

  it("keeps API in the header and demotes GitHub off the hero", () => {
    const nav = src("components/Nav.tsx");
    expect(nav).toMatch(/href: "\/api", label: "API"/);
    expect(nav).toMatch(/href: "\/browse", label: "Compare"/);
    expect(nav).not.toMatch(/label: "Browser"/);
    expect(nav).not.toMatch(/pipeline-observation/);

    const home = src("app/page.tsx");
    expect(home).toContain('href="/api"');
    expect(home).toContain("Compare schools");
    expect(home).toContain("Recently added");
    expect(home).not.toContain("Latest drain");
    expect(home).not.toContain("github.com/bolewood/collegedata-fyi");
    expect(home).not.toMatch(/\bextracted\b/);
    expect(home).not.toMatch(/field schema/);
    expect(home).not.toMatch(/Browser rows/);
  });

  it("keeps extractor narrative and takedowns off the CDS explainer", () => {
    const cds = src("app/about/common-data-set/page.tsx");
    expect(cds).toContain("It's called the Common Data Set");
    expect(cds).not.toMatch(/Docling/);
    expect(cds).not.toMatch(/AcroForm/);
    expect(cds).not.toMatch(/AP_RECD_1ST_MEN_N/);
    expect(cds).not.toMatch(/taken down/);
    expect(cds).not.toMatch(/harvey-mudd-2025-26\.md/);

    const about = src("app/about/page.tsx");
    expect(about).toMatch(/you still get the federal numbers/);
    expect(about).not.toMatch(/Docling/);
    expect(about).not.toMatch(/Reducto/);
  });
});

describe("About story figures", () => {
  it("checks in UTF-8 SVG that XML parsers can decode", () => {
    const dir = join(process.cwd(), "public/about");
    const files = readdirSync(dir).filter((name) => name.endsWith(".svg"));
    expect(files.length).toBeGreaterThanOrEqual(10);
    for (const name of files) {
      const bytes = readFileSync(join(dir, name));
      const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
      expect(text.startsWith('<?xml version="1.0" encoding="UTF-8"?>')).toBe(true);
      expect(text).toMatch(/<svg[^>]+xmlns="http:\/\/www.w3.org\/2000\/svg"/);
      expect(text).not.toMatch(/[\u0000-\u0008\u000B\u000C\u000E-\u001F]/);
    }
  });
});
