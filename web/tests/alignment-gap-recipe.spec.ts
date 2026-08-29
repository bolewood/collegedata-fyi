import { expect, test } from "@playwright/test";

test("alignment-gap merit panel names the school on every dot", async ({ page }) => {
  await page.goto("/recipes/alignment-gap");

  await expect(
    page.getByRole("heading", { name: /what a school charges, against what it delivers/i }),
  ).toBeVisible();
  await expect(
    page.getByText(/the completer debt a school would have to shed to reach the corpus median burden/i),
  ).toBeVisible();
  await expect(page.getByText(/are they already spending it/i)).toBeVisible();
  await expect(page.getByText(/merit spend = annual gap/i)).toBeVisible();

  const meritChart = page.getByTestId("alignment-gap-merit-chart");
  const unlabeled = meritChart.locator("circle[data-school-id]:not([data-school-id='quincy-university'])").first();
  const unlabeledId = await unlabeled.getAttribute("data-school-id");
  expect(unlabeledId).toBeTruthy();

  await unlabeled.hover({ force: true });
  const tooltip = page.getByTestId("alignment-gap-merit-tooltip");
  await expect(tooltip).toBeVisible();
  await expect(tooltip.locator(".serif")).not.toHaveText(/^$/);
  await expect(tooltip).toContainText(/Gap /);
  await expect(tooltip).toContainText(/Merit spend /);

  await page.getByLabel("Find a school in the merit join").fill("Quincy University");
  await expect(tooltip).toContainText("Quincy University");
});

test("alignment-gap endowment panel still names Bard and Grinnell", async ({ page }) => {
  await page.goto("/recipes/alignment-gap");
  await expect(page.getByText(/could they afford to/i)).toBeVisible();

  const endowmentChart = page.getByTestId("alignment-gap-endowment-chart");
  await endowmentChart.locator("circle[data-school-id='bard-college']").hover({ force: true });
  const tooltip = page.getByTestId("alignment-gap-tooltip");
  await expect(tooltip).toContainText("Bard College");

  await page.getByLabel("Find a school in the endowment join").fill("Grinnell College");
  await expect(tooltip).toContainText("Grinnell College");
});

test("recipes index exposes the alignment-gap recipe as a three-source join", async ({ page }) => {
  await page.goto("/recipes");
  const card = page.locator("article", { hasText: "Alignment gap" });
  await expect(card.getByText("CDS H2A · Scorecard · IPEDS")).toBeVisible();
  await expect(card.getByRole("link", { name: "Open demo →" })).toHaveAttribute(
    "href",
    "/recipes/alignment-gap",
  );
});
