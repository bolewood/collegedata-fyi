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
