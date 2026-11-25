import { expect, test, type Page } from "@playwright/test";

// PRD 040: a count on /data-quality is a button that lists the reports behind it. These cover what the unit tests cannot
// without a DOM: focus moving into the list, Escape and Close giving it back, aria-expanded/aria-controls, the file being
// fetched on the first click only, and the list closing on a year change.
//
// The counts are buttons only when the page was built launched (DATA_QUALITY_LAUNCH_DATE in the past). Against a build with
// the gate closed this spec skips, saying so. To run it before launch: set the date in src/lib/data-quality.ts to a past day
// locally (do not commit it), start `npm run dev` with dummy NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY, and
//   PLAYWRIGHT_BASE_URL=http://localhost:<port> npx playwright test tests/data-quality-drill.spec.ts --project=chromium

/** The open list: the one region with a Close button under a table (other regions are the page's sections and scrollers). */
const list = (page: Page) => page.locator(".dq-drill");

const REPORTS = /\/data-quality\/reports\/\d{4}-\d{2}-\d{2}$/;

async function openPage(page: Page, year = "2023-24") {
  await page.goto(`/data-quality?year=${year}`);
  const counts = page.locator("button.dq-count");
  test.skip(
    (await counts.count()) === 0,
    "The built launch gate is closed, so the counts are not buttons. Run this against a launched build (see the comment at the top).",
  );
  // A production build prerenders the page for the default year and applies ?year= after hydration, so wait until the
  // buttons are for the requested year before touching them (otherwise a click can land on a count that is then replaced).
  await expect(counts.first()).toHaveAttribute("aria-label", new RegExp(`\\(${year}\\)$`));
  await expect(page.locator("button.dq-count[aria-label$='(" + year + ")']")).toHaveCount(await counts.count());
  return counts;
}

test.describe("Data quality: list the reports behind a count", () => {
  test("opens a labelled list, moves focus into it and says so with aria-expanded and aria-controls", async ({ page }) => {
    const counts = await openPage(page);
    const button = counts.first();
    await expect(button).toHaveAttribute("aria-expanded", "false");
    await expect(button).not.toHaveAttribute("aria-controls", /.+/);
    const name = await button.getAttribute("aria-label");
    expect(name).toMatch(/^List the [\d,]+ .*\(2023-24\)$/);
    await button.click();
    const panel = list(page);
    await expect(panel).toHaveAccessibleName(name!.replace(/^List the /, ""));
    await expect(panel).toBeVisible();
    await expect(panel).toBeFocused();
    await expect(button).toHaveAttribute("aria-expanded", "true");
    const controls = await button.getAttribute("aria-controls");
    expect(controls).toBeTruthy();
    expect(await panel.getAttribute("id")).toBe(controls);
    await expect(panel.getByRole("status")).toContainText(/\d+ reports?/);
    await expect(panel.getByRole("link").first()).toHaveAttribute("href", /^\/schools\/[^/]+\/2023-24$/);
  });

  test("Escape closes the list and puts focus back on the count", async ({ page }) => {
    const button = (await openPage(page)).first();
    await button.click();
    await expect(list(page)).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(page.getByRole("button", { name: "Close", exact: true })).toHaveCount(0);
    await expect(button).toBeFocused();
    await expect(button).toHaveAttribute("aria-expanded", "false");
  });

  test("the Close button closes it and returns focus to the count", async ({ page }) => {
    const button = (await openPage(page)).first();
    await button.click();
    await page.getByRole("button", { name: "Close", exact: true }).click();
    await expect(page.getByRole("button", { name: "Close", exact: true })).toHaveCount(0);
    await expect(button).toBeFocused();
  });

  test("works from the keyboard alone: Enter opens, Tab reaches Close, Escape closes", async ({ page }) => {
    const button = (await openPage(page)).first();
    await button.focus();
    await page.keyboard.press("Enter");
    await expect(list(page)).toBeFocused();
    await page.keyboard.press("Tab");
    await expect(page.getByRole("button", { name: "Close", exact: true })).toBeFocused();
    await page.keyboard.press("Escape");
    await expect(button).toBeFocused();
  });

  test("fetches the reports file on the first click only", async ({ page }) => {
    const requests: string[] = [];
    page.on("request", (r) => {
      if (REPORTS.test(new URL(r.url()).pathname)) requests.push(r.url());
    });
    const counts = await openPage(page);
    await page.waitForLoadState("networkidle");
    expect(requests).toHaveLength(0);
    await counts.nth(0).click();
    await expect(list(page).getByRole("status").filter({ hasText: /reports?/ })).toBeVisible();
    await counts.nth(1).click();
    await expect(list(page).getByRole("status").filter({ hasText: /reports?/ })).toBeVisible();
    expect(requests).toHaveLength(1);
  });

  test("switching to another count shows its list; the same count again closes it", async ({ page }) => {
    const counts = await openPage(page);
    await counts.nth(0).click();
    const first = await list(page).getByRole("heading").textContent();
    await counts.nth(1).click();
    const second = await list(page).getByRole("heading").textContent();
    expect(second).not.toBe(first);
    await counts.nth(1).click();
    await expect(page.getByRole("button", { name: "Close", exact: true })).toHaveCount(0);
  });

  test("closes when the year changes, and stays closed when you come back to that year", async ({ page }) => {
    const counts = await openPage(page, "2023-24");
    const button = counts.first();
    await button.click();
    await expect(page.getByRole("button", { name: "Close", exact: true })).toBeVisible();
    await page.getByRole("group", { name: "Choose a year" }).getByRole("link", { name: "2024-25", exact: true }).click();
    await expect(page).toHaveURL(/year=2024-25/);
    await expect(page.getByRole("button", { name: "Close", exact: true })).toHaveCount(0);
    // Back to the year it was opened for (the page keeps its state across the year picker): the list must not reappear.
    await page.getByRole("group", { name: "Choose a year" }).getByRole("link", { name: "2023-24", exact: true }).click();
    await expect(page).toHaveURL(/year=2023-24/);
    await expect(page.getByRole("button", { name: "Close", exact: true })).toHaveCount(0);
    await expect(page.locator("button.dq-count").first()).toHaveAttribute("aria-expanded", "false");
  });

  test("other controls still work while a list is open: every year chip, Back, a CSV download and Close", async ({ page }) => {
    const counts = await openPage(page, "2023-24");
    const chip = (year: string) => page.getByRole("group", { name: "Choose a year" }).getByRole("link", { name: year, exact: true });
    await counts.first().click();
    await expect(list(page)).toBeVisible();
    // The other year chips (tapped one after another, each with a list open for the year just left).
    for (const year of ["2024-25", "2025-26", "2023-24"]) {
      await chip(year).click();
      await expect(page).toHaveURL(new RegExp(`year=${year}$`));
      await expect(chip(year)).toHaveAttribute("aria-current", "true");
      await expect(page.getByRole("button", { name: "Close", exact: true })).toHaveCount(0);
      await page.locator("button.dq-count").first().click();
      await expect(list(page)).toBeVisible();
    }
    // Tapping the year already shown adds no history entry: one Back goes to the year before it.
    await chip("2023-24").click();
    await page.goBack();
    await expect(page).toHaveURL(/year=2025-26$/);
    // Back and Forward restore the year, and the open list closes with the year change.
    await expect(chip("2025-26")).toHaveAttribute("aria-current", "true");
    await expect(page.getByRole("button", { name: "Close", exact: true })).toHaveCount(0);
    await page.goForward();
    await expect(page).toHaveURL(/year=2023-24$/);
    await expect(chip("2023-24")).toHaveAttribute("aria-current", "true");
    await expect(page.getByRole("region", { name: "Table A, 2023-24" })).toBeVisible();
    // A CSV download from the page while a list is open: the file is the selected year's.
    await page.locator("button.dq-count").first().click();
    await expect(list(page)).toBeVisible();
    const download = page.waitForEvent("download");
    await page.locator('a[href^="/data-quality/csv/reports/"]').first().click();
    expect((await download).suggestedFilename()).toMatch(/2023-24.*\.csv$/);
    // Close.
    await page.getByRole("button", { name: "Close", exact: true }).click();
    await expect(page.getByRole("button", { name: "Close", exact: true })).toHaveCount(0);
  });

  test("shows an error with Try again when the file can't be loaded, then the list once it can", async ({ page }) => {
    const counts = await openPage(page);
    await page.route(REPORTS, (route) => route.abort());
    await counts.first().click();
    await expect(list(page).getByRole("alert")).toContainText("We couldn’t load the list");
    await page.unroute(REPORTS);
    await page.getByRole("button", { name: "Try again" }).click();
    await expect(list(page).getByRole("status")).toContainText(/\d+ reports?/);
  });
});
