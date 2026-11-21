import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"];

// label-content-name-mismatch (WCAG 2.5.3) is experimental and off by
// default. `.options()` replaces every option set before it, so it must come
// before `.withTags()`.
function wcagScan(page: Page) {
  return new AxeBuilder({ page })
    .options({ rules: { "label-content-name-mismatch": { enabled: true } } })
    .withTags(WCAG_TAGS);
}

test("reconstructed CDS tables have no automated WCAG violations", async ({ page }) => {
  await page.goto("/schools/bowdoin/2024-25");
  await expect(
    page.getByRole("table", { name: /B1 undergraduate enrollment/i }),
  ).toBeVisible();

  const results = await new AxeBuilder({ page })
    .include(".cd-reconstructed")
    .withTags(WCAG_TAGS)
    .analyze();

  expect(results.violations).toEqual([]);
});

test.describe("whole pages have no automated WCAG violations", () => {
  // Desktop only: the palette trigger shows its INDEX label above 640px,
  // which is where a name/label mismatch would surface.
  test.skip(({ isMobile }) => isMobile, "desktop viewport scan");
  test.use({ viewport: { width: 1280, height: 900 } });

  test("home page", async ({ page }) => {
    await page.goto("/");
    await expect(page.getByTestId("cmdk-trigger")).toBeVisible();
    expect((await wcagScan(page).analyze()).violations).toEqual([]);
  });

  // Two schools with different header inks; the share popover opens inside
  // the inked header, so scan it open as well.
  for (const slug of ["university-of-wisconsin-madison", "bowdoin"]) {
    test(`school page: ${slug}`, async ({ page }) => {
      await page.goto(`/schools/${slug}`);
      const header = page.locator(".cd-school-header").first();
      await expect(header).toBeVisible();
      expect((await wcagScan(page).analyze()).violations).toEqual([]);

      await header.getByRole("button", { expanded: false }).first().click();
      await expect(header.getByRole("group", { name: "Share options" })).toBeVisible();
      const open = await wcagScan(page).include(".cd-school-header").analyze();
      expect(open.violations).toEqual([]);
    });
  }

  // Wait on markup that predates the fixes, so a regression fails in axe
  // rather than on a locator.
  test("coverage dashboard", async ({ page }) => {
    await page.goto("/coverage");
    await expect(page.locator('[aria-label="Coverage table"] [role="row"]').nth(1)).toBeVisible();
    expect((await wcagScan(page).analyze()).violations).toEqual([]);
  });

  test("browse table", async ({ page }) => {
    await page.goto("/browse");
    await expect(page.locator(".browser-row").first()).toBeVisible();
    expect((await wcagScan(page).analyze()).violations).toEqual([]);
  });

  test("school year page", async ({ page }) => {
    await page.goto("/schools/bowdoin/2024-25");
    await expect(page.locator(".cd-fields__gutter-sub").first()).toBeVisible();
    expect((await wcagScan(page).analyze()).violations).toEqual([]);
  });
});
