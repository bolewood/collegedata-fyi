import { expect, test, type Page } from "@playwright/test";

// React hydration error #418 means the browser's first render differed from the server's HTML. On /data-quality it was
// caused by reading ?year= on the first render of a statically built page. A production build logs it as
// "Minified React error #418"; this fails on any hydration error, for every year, at phone and desktop widths.
//
// The page is only reachable when the build's launch gate is open; against a closed build the /data-quality cases skip,
// saying so. /coverage is public and always runs.

const YEARS = ["2025-26", "2024-25", "2023-24"];
const WIDTHS = [375, 1280];

async function hydrationErrors(page: Page, url: string): Promise<string[]> {
  const found: string[] = [];
  page.on("pageerror", (e) => found.push(e.message));
  page.on("console", (m) => {
    if (m.type() === "error") found.push(m.text());
  });
  await page.goto(url, { waitUntil: "networkidle" });
  await page.waitForTimeout(500);
  return found.filter((t) => /hydrat|react\.dev\/errors\/(418|423|425)|#418|did not match/i.test(t));
}

// The server formats in UTC and en-US; a browser in another locale or time zone must still hydrate the same markup.
const ENVIRONMENTS = [
  { name: "default", use: {} },
  { name: "de-DE, Auckland", use: { locale: "de-DE", timezoneId: "Pacific/Auckland" } },
];

for (const env of ENVIRONMENTS) for (const width of WIDTHS) {
  test.describe(`hydration at ${width}px (${env.name})`, () => {
    test.use({ viewport: { width, height: 900 }, ...env.use });

    test("/coverage hydrates cleanly", async ({ page }) => {
      expect(await hydrationErrors(page, "/coverage")).toEqual([]);
    });

    for (const year of YEARS) {
      test(`/data-quality?year=${year} hydrates cleanly`, async ({ page }) => {
        const probe = await page.request.get(`/data-quality/csv/reports/${year}`);
        test.skip(probe.status() !== 200, "The built launch gate is closed, so /data-quality is not public. Run this against a launched build.");
        expect(await hydrationErrors(page, `/data-quality?year=${year}`)).toEqual([]);
      });
    }
  });
}
