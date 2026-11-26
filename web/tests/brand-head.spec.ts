import { expect, test } from "@playwright/test";

// Cutover-blocking: the rendered <head> and JSON-LD of the main page types must carry the new
// name and origin and no trace of the old name or a `.fyi` host (title, meta, og:site_name,
// og:url, og:image, icons, canonical, JSON-LD).
const ORIGIN = "https://www.quadfile.org";

// `seo`: the page sets a canonical (the static design-system page does not).
// `requireOg`: the page must carry og:url and og:image; `requireSiteName`: og:site_name too. On the
// other pages the tags are checked when present, because several pages override `openGraph`
// without a siteName or image (a pre-existing gap, not part of the rename).
const PAGES = [
  { label: "home", path: "/", seo: true, requireOg: true, requireSiteName: true },
  { label: "school page", path: "/schools/mit", seo: true, requireOg: true },
  { label: "school-year page", path: "/schools/mit/2024-25", seo: true, requireOg: true },
  { label: "api docs", path: "/api", seo: true, requireOg: false },
  { label: "about", path: "/about", seo: true },
  { label: "privacy", path: "/privacy", seo: true },
  { label: "scholarships", path: "/scholarships", seo: true },
  { label: "data quality", path: "/data-quality", seo: true },
  { label: "design system", path: "/design-system/", seo: false },
];

const expectedUrl = (path: string) => (path === "/" ? ORIGIN : `${ORIGIN}${path}`.replace(/\/$/, ""));
const onNewOrigin = (url: string | null) => url !== null && (url === ORIGIN || url.startsWith(`${ORIGIN}/`) || url.startsWith("/"));

for (const { label, path, seo, requireOg, requireSiteName } of PAGES as Array<{ label: string; path: string; seo: boolean; requireOg?: boolean; requireSiteName?: boolean }>) {
  test(`head and JSON-LD of ${label} carry Quadfile and no old name`, async ({ page }) => {
    const res = await page.goto(path);
    expect(res?.status()).toBe(200);

    const head = await page.evaluate(() => document.head.innerHTML);
    expect(head.length, "found a <head>").toBeGreaterThan(200);
    expect(head).not.toMatch(/collegedata/i);
    expect(head).not.toMatch(/\.fyi/i);
    await expect(page).toHaveTitle(/Quadfile/);

    // App pages carry at least one icon, none pointing at another host (the static page relies on /favicon.ico).
    const icons = await page.locator('head link[rel~="icon"]').evaluateAll((els) => els.map((e) => e.getAttribute("href")));
    if (seo) expect(icons.length).toBeGreaterThan(0);
    for (const href of icons) expect(onNewOrigin(href)).toBe(true);

    if (seo) {
      const canonical = await page.locator('head link[rel="canonical"]').getAttribute("href");
      expect(canonical).toBe(expectedUrl(path));
      const og = async (name: string) => {
        const tag = page.locator(`head meta[property="${name}"]`);
        return (await tag.count()) ? tag.first().getAttribute("content") : null;
      };
      const [siteName, ogUrl, ogImage] = [await og("og:site_name"), await og("og:url"), await og("og:image")];
      if (requireSiteName) expect(siteName).toBe("Quadfile");
      if (requireOg) {
        expect(ogUrl).toBe(expectedUrl(path));
        expect(ogImage, "og:image present").toBeTruthy();
      }
      if (siteName !== null) expect(siteName).toBe("Quadfile");
      if (ogUrl !== null) expect(onNewOrigin(ogUrl), `og:url ${ogUrl}`).toBe(true);
      if (ogImage !== null) expect(onNewOrigin(ogImage), `og:image ${ogImage}`).toBe(true);
    }

    // Every JSON-LD block, in the head or the body.
    const blocks = await page.locator('script[type="application/ld+json"]').evaluateAll((els) => els.map((e) => e.textContent ?? ""));
    for (const block of blocks) {
      expect(block).not.toMatch(/collegedata/i);
      expect(block).not.toMatch(/\.fyi/i);
      // Our own URLs use the canonical host; third-party links (a school's own CDS page) are left alone.
      for (const url of block.match(/https?:\/\/[^"\s),]+/g) ?? []) {
        if (/quadfile/i.test(new URL(url).hostname)) expect(new URL(url).hostname, `JSON-LD url ${url}`).toBe("www.quadfile.org");
      }
    }
  });
}
