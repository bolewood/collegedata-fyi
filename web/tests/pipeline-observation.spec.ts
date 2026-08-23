import { expect, test } from "@playwright/test";

test("dispatch tiles explain themselves on hover and focus", async ({
  page,
  isMobile,
}) => {
  await page.goto("/pipeline-observation");
  await expect(
    page.getByRole("heading", { name: /The clocks/i }),
  ).toBeVisible();

  const finder = page.getByRole("article", { name: /Finder:/ });
  const finderTip = page.locator("#po-tip-finder_brave");
  const scorecard = page.getByRole("article", { name: /Scorecard:/ });
  const scorecardTip = page.locator("#po-tip-scorecard_load");
  await expect(finderTip).toBeHidden();

  if (isMobile) {
    await finder.tap();
    await expect(finderTip).toBeVisible();
    await expect(finderTip).toContainText("Brave Search");
    await scorecard.tap();
    await expect(scorecardTip).toBeVisible();
    await expect(scorecardTip).toContainText("College Scorecard");
    return;
  }

  await finder.hover();
  await expect(finderTip).toBeVisible();
  await expect(finderTip).toContainText("Brave Search");
  await expect(finderTip).toContainText("What this does");

  await page.getByRole("heading", { name: /The clocks/i }).hover();
  await expect(finderTip).toBeHidden();

  await scorecard.focus();
  await expect(scorecardTip).toBeVisible();
  await expect(scorecardTip).toContainText("College Scorecard");
});
