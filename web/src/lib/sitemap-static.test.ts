import { describe, expect, it } from "vitest";
import { SITEMAP_STATIC_PATHS, SITE_URL, staticSitemapEntries } from "./sitemap-static";

describe("static sitemap entries", () => {
  it("includes browse, public recipes, and the About source pages", () => {
    expect(SITEMAP_STATIC_PATHS).toContain("/browse");
    expect(SITEMAP_STATIC_PATHS).toContain("/recipes/waitlist-odds");
    expect(SITEMAP_STATIC_PATHS).toContain("/recipes/endowment-draw-rate");
    expect(SITEMAP_STATIC_PATHS).toContain("/about/common-data-set");
    expect(SITEMAP_STATIC_PATHS).toContain("/about/college-scorecard");
    expect(SITEMAP_STATIC_PATHS).toContain("/about/ipeds");
    expect(SITEMAP_STATIC_PATHS).not.toContain("/methodology/common-data-set");
    expect(SITEMAP_STATIC_PATHS).not.toContain("/discover");
  });

  it("emits www canonical URLs", () => {
    const urls = staticSitemapEntries().map((entry) => entry.url);
    expect(urls[0]).toBe(SITE_URL);
    expect(urls).toContain(`${SITE_URL}/browse`);
    expect(urls).toContain(`${SITE_URL}/about/common-data-set`);
  });
});
