import { describe, expect, it } from "vitest";
import { getOfficialCdsPage } from "./official-cds-page";

describe("getOfficialCdsPage", () => {
  it("uses the curated Virginia Tech HTML gate, not the DAM PDF seed", () => {
    const page = getOfficialCdsPage("virginia-tech", "233921");
    expect(page?.access).toBe("request");
    expect(page?.url).toBe(
      "https://aie.vt.edu/analytics-and-ai/common-data-set.html",
    );
    expect(page?.url.toLowerCase().endsWith(".pdf")).toBe(false);
  });

  it("points Harvey Mudd at the live IR listing", () => {
    const page = getOfficialCdsPage("harvey-mudd", "115409");
    expect(page?.access).toBe("public");
    expect(page?.url).toContain("institutional-statistics/common-data-set");
  });

  it("returns null when no HTML landing page is known", () => {
    expect(getOfficialCdsPage("no-such-school")).toBeNull();
  });
});
