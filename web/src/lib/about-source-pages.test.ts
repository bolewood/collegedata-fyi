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
