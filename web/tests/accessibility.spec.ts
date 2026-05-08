import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

test("reconstructed CDS tables have no automated WCAG violations", async ({ page }) => {
  await page.goto("/schools/bowdoin/2024-25");
  await expect(
    page.getByRole("table", { name: /B1 undergraduate enrollment/i }),
  ).toBeVisible();

  const results = await new AxeBuilder({ page })
    .include(".cd-reconstructed")
    .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
    .analyze();

  expect(results.violations).toEqual([]);
});
