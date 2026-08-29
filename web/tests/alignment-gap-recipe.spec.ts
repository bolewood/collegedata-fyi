import { expect, test } from "@playwright/test";

test("alignment-gap merit panel names the school on every dot", async ({ page }) => {
  await page.goto("/recipes/alignment-gap");

  await expect(
    page.getByRole("heading", { name: /what a school charges, against what it delivers/i }),
  ).toBeVisible();
  await expect(page.locator("header p.serif")).toContainText(
    /completer debt a school would have to shed/i,
  );
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

  await page.getByLabel("Find a school in the merit join").fill("University of the Incarnate Word");
  await expect(tooltip).toContainText("University of the Incarnate Word");
  await expect(tooltip).toContainText("$0 · no merit aid");
  await expect(tooltip).toContainText("genuinely constrained");

  await page.getByLabel("Find a school in the merit join").fill("Amherst College");
  await expect(tooltip).toContainText("Amherst College");
  await expect(tooltip).toContainText("$0 · no merit aid");
  await expect(tooltip).toContainText("gap ≤ 0");

  await expect(meritChart.getByTestId("alignment-gap-zero-rail")).toBeAttached();
  await expect(meritChart.locator("svg").getByText("NO MERIT AID")).toBeVisible();
  await expect(meritChart.locator("svg").getByText(/GAP ≤ 0/)).toBeVisible();
});

test("alignment-gap panels share one gap number for Pratt", async ({ page }) => {
  await page.goto("/recipes/alignment-gap");

  await page.getByLabel("Find a school in the merit join").fill("Pratt Institute-Main");
  const meritTooltip = page.getByTestId("alignment-gap-merit-tooltip");
  await expect(meritTooltip).toContainText("Pratt Institute-Main");
  const meritGap = (await meritTooltip.textContent())?.match(/Gap ([+$−\d,]+)/)?.[1];
  expect(meritGap).toBeTruthy();

  await page.getByLabel("Find a school in the endowment join").fill("Pratt Institute-Main");
  const endowmentTooltip = page.getByTestId("alignment-gap-tooltip");
  await expect(endowmentTooltip).toContainText("Pratt Institute-Main");
  await expect(endowmentTooltip).toContainText(`Gap ${meritGap}`);
});

test("alignment-gap reproducibility curl does not silently truncate Panel B", async ({ page }) => {
  await page.goto("/recipes/alignment-gap");
  await expect(page.locator("pre")).toContainText("limit=5000");
  await expect(page.locator("pre")).toContainText("silently truncates");
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
  await expect(card.getByText(/already spend more per first-year/i)).toBeVisible();
  await expect(card.getByRole("link", { name: "Open demo →" })).toHaveAttribute(
    "href",
    "/recipes/alignment-gap",
  );
});
