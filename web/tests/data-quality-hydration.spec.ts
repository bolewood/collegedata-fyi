import { expect, test, type Page } from "@playwright/test";

// React hydration error #418 means the browser's first render differed from the server's HTML. On /data-quality it was
// caused by reading ?year= on the first render of a statically built page. A production build logs it as
// "Minified React error #418"; this fails on any hydration error, for every year, at phone and desktop widths, and
// also proves the year in the URL is the year that ends up on the page (so a gate that never switched would fail).
//
// Whether the build's launch gate is open is read from /data-quality itself (a closed build serves it `noindex`). The
// page must exist either way, so a missing route fails; only the launched-state checks skip on a closed build.

const YEARS = ["2025-26", "2024-25", "2023-24"];
const WIDTHS = [375, 1280];

// The server formats in UTC and en-US; a browser in another locale or time zone must still hydrate the same markup.
const ENVIRONMENTS = [
  { name: "default", use: {} },
  { name: "de-DE, Auckland", use: { locale: "de-DE", timezoneId: "Pacific/Auckland" } },
];

function watch(page: Page): string[] {
  const found: string[] = [];
  page.on("pageerror", (e) => found.push(e.message));
  page.on("console", (m) => {
    if (m.type() === "error") found.push(m.text());
  });
  return found;
}
const hydration = (errors: string[]) => errors.filter((t) => /hydrat|react\.dev\/errors\/(418|423|425)|#418|did not match/i.test(t));

async function gateIsOpen(page: Page): Promise<boolean> {
  const res = await page.goto("/data-quality", { waitUntil: "domcontentloaded" });
  expect(res?.status(), "/data-quality must exist whether or not the gate is open").toBe(200);
  const robots = await page.evaluate(() => document.querySelector('meta[name="robots"]')?.getAttribute("content") ?? "");
  return !/noindex/.test(robots);
}

for (const env of ENVIRONMENTS) for (const width of WIDTHS) {
  test.describe(`hydration at ${width}px (${env.name})`, () => {
    test.use({ viewport: { width, height: 900 }, ...env.use });

    test("/coverage hydrates cleanly with and without a query string", async ({ page }) => {
      for (const url of ["/coverage", "/coverage?q=a", "/coverage?all=1"]) {
        const errors = watch(page);
        const res = await page.goto(url, { waitUntil: "load" });
        expect(res?.status(), url).toBe(200);
        await page.waitForTimeout(1500);
        expect(hydration(errors), url).toEqual([]);
      }
    });

    for (const year of YEARS) {
      test(`/data-quality?year=${year} hydrates cleanly and shows ${year}`, async ({ page }) => {
        test.skip(!(await gateIsOpen(page)), "The built launch gate is closed, so there are no year links or CSV links to check. Run this against a launched build.");
        const errors = watch(page);
        const res = await page.goto(`/data-quality?year=${year}`, { waitUntil: "load" });
        expect(res?.status()).toBe(200);
        // After hydration the year in the URL is the year on the page: the selected chip, Table A and the CSV link.
        await expect(page.locator('a.cd-chip[aria-current="true"]')).toHaveText(year);
        await expect(page.getByRole("region", { name: `Table A, ${year}` })).toBeVisible();
        await expect(page.locator('a[href^="/data-quality/csv/reports/"]').first()).toHaveAttribute("href", `/data-quality/csv/reports/${year}`);
        await page.waitForTimeout(1500);
        expect(hydration(errors)).toEqual([]);
      });
    }

    test("a direct link to another year is marked busy before hydration, then announces the year", async ({ page }) => {
      test.skip(!(await gateIsOpen(page)), "The built launch gate is closed. Run this against a launched build.");
      // Hold the app's scripts back so the page stays as the server built it (the default year), as it is for a moment on
      // a slow phone, then check what the page says about it.
      await page.route(/\/_next\/static\/chunks\/.*\.js/, (route) => route.abort());
      await page.goto("/data-quality?year=2023-24", { waitUntil: "domcontentloaded" });
      const loading = page.locator('.dq-pending[data-year="2023-24"]');
      await expect(loading).toHaveText("Loading 2023-24\u2026");
      await expect(loading).toBeVisible();
      await expect(page.locator('.dq-pending[data-year="2024-25"]')).toBeHidden();
      await expect(page.locator("#dq-body")).toHaveAttribute("aria-busy", "true");
      expect(await page.locator("#dq-body").evaluate((el) => getComputedStyle(el).opacity)).toBe("0.5");
      await page.unroute(/\/_next\/static\/chunks\/.*\.js/);
      // With the scripts back: the busy state clears and a polite status line says which year is shown.
      await page.goto("/data-quality?year=2023-24", { waitUntil: "load" });
      await expect(page.locator("#dq-year-status")).toHaveText("Showing 2023-24");
      await expect(page.locator("#dq-body")).not.toHaveAttribute("aria-busy", "true");
      await expect(page.locator('.dq-pending[data-year="2023-24"]')).toBeHidden();
      expect(await page.locator("#dq-body").evaluate((el) => getComputedStyle(el).opacity)).toBe("1");
      // Changing the year in the page (back/forward or a chip) announces it too; Back is used here, a chip tap on a phone
      // is covered with the chip fix.
      await page.goto("/data-quality?year=2024-25", { waitUntil: "load" });
      await expect(page.locator("#dq-year-status")).toHaveText("Showing 2024-25");
      await page.goBack();
      await expect(page.locator("#dq-year-status")).toHaveText("Showing 2023-24");
    });
  });
}
