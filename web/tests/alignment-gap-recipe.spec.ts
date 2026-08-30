import { expect, test } from "@playwright/test";

test("alignment-gap merit panel names the school on every dot", async ({ page }) => {
  await page.goto("/recipes/alignment-gap");

  await expect(
    page.getByRole("heading", { name: /debt burden, aid, and financial resources/i }),
  ).toBeVisible();
  await expect(page.locator("header + div p.serif")).toContainText(
    /college affordability data lives in several different places/i,
  );
  await expect(page.getByText(/compare the debt gap with merit aid/i)).toBeVisible();
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
  await expect(tooltip).toContainText("merit aid smaller than the gap");

  await page.getByLabel("Find a school in the merit join").fill("Amherst College");
  await expect(tooltip).toContainText("Amherst College");
  await expect(tooltip).toContainText("$0 · no merit aid");
  await expect(tooltip).toContainText("debt burden at or below the median");

  await expect(meritChart.getByTestId("alignment-gap-zero-rail")).toBeAttached();
  await expect(meritChart.locator("svg").getByText("NO MERIT AID")).toBeVisible();
  await expect(meritChart.locator("svg").getByText(/AT OR BELOW MEDIAN/)).toBeVisible();
});

test("alignment-gap fig 1 tooltip stays off the pointer on the right side", async ({ page }) => {
  await page.goto("/recipes/alignment-gap");

  const meritChart = page.getByTestId("alignment-gap-merit-chart");
  const quincy = meritChart.locator("circle[data-school-id='quincy-university']").first();
  await quincy.scrollIntoViewIfNeeded();
  await quincy.hover();

  const tooltip = page.getByTestId("alignment-gap-merit-tooltip");
  await expect(tooltip).toBeVisible();
  await expect(tooltip).toContainText("Quincy University");
  await expect(tooltip).toHaveAttribute("data-tooltip-side", "left");

  const pointer = await quincy.boundingBox();
  const box = await tooltip.boundingBox();
  expect(pointer).toBeTruthy();
  expect(box).toBeTruthy();
  const cx = pointer!.x + pointer!.width / 2;
  const cy = pointer!.y + pointer!.height / 2;
  const pad = 8;
  const coversPointer =
    cx > box!.x - pad &&
    cx < box!.x + box!.width + pad &&
    cy > box!.y - pad &&
    cy < box!.y + box!.height + pad;
  expect(coversPointer).toBe(false);
  expect(box!.x + box!.width).toBeLessThan(cx);
  expect(Math.abs(box!.y + box!.height / 2 - cy)).toBeLessThan(120);
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

test("alignment-gap reproducibility curl pages Panel B past the 1,000-row cap", async ({ page }) => {
  await page.goto("/recipes/alignment-gap");
  const recipe = page.locator("pre");
  await expect(recipe).toContainText("offset=0");
  await expect(recipe).toContainText("offset=1000");
  await expect(recipe).toContainText("offset=2000");
  await expect(recipe).toContainText("Content-Range: 0-999/2158");
  await expect(recipe).toContainText("limit=5000 and Range: 0-4999 are both capped");
});

test("alignment-gap endowment panel still names Bard and Grinnell", async ({ page }) => {
  await page.goto("/recipes/alignment-gap");
  await expect(page.getByText(/compare debt burden with endowment per student/i)).toBeVisible();

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
  await expect(card.getByText(/compare the alignment gap with merit aid/i)).toBeVisible();
  await expect(card.getByRole("link", { name: "Open demo →" })).toHaveAttribute(
    "href",
    "/recipes/alignment-gap",
  );
});
