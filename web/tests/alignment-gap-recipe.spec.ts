import { expect, test } from "@playwright/test";

test("alignment-gap hover names the school on every dot", async ({ page }) => {
  await page.goto("/recipes/alignment-gap");

  await expect(
    page.getByRole("heading", { name: /what a school charges, against what it delivers/i }),
  ).toBeVisible();
  await expect(
    page.getByText(/debt burden is the share of median 10-year earnings/i),
  ).toBeVisible();
  await expect(page.getByText(/hover any dot — every school is named/i)).toBeVisible();

  const unlabeled = page.locator("circle[data-school-id]:not([data-school-id='stanford'])").first();
  const unlabeledId = await unlabeled.getAttribute("data-school-id");
  expect(unlabeledId).toBeTruthy();

  await unlabeled.hover({ force: true });
  const tooltip = page.getByTestId("alignment-gap-tooltip");
  await expect(tooltip).toBeVisible();
  await expect(tooltip.locator(".serif")).not.toHaveText(/^$/);
  await expect(tooltip).toContainText(/Gap /);
  await expect(tooltip).toContainText(/Endowment /);

  await page.getByLabel("Find a school").fill("Hollins University");
  await expect(tooltip).toContainText("Hollins University");
});

test("recipes index exposes the alignment-gap recipe", async ({ page }) => {
  await page.goto("/recipes");
  const card = page.locator("article", { hasText: "Alignment gap" });
  await expect(card.getByText("CDS C9 · Scorecard · IPEDS")).toBeVisible();
  await expect(card.getByRole("link", { name: "Open demo →" })).toHaveAttribute(
    "href",
    "/recipes/alignment-gap",
  );
});
