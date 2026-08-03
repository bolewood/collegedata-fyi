import { expect, test, type Page } from "@playwright/test";

async function expectNoPageOverflow(page: Page) {
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - window.innerWidth,
  );
  expect(overflow).toBeLessThanOrEqual(2);
}

test("endowment draw-rate recipe stays neutral until a school is selected", async ({
  page,
}) => {
  await page.goto("/recipes/endowment-draw-rate");

  await expect(
    page.getByRole("heading", { name: /how much of the endowment is being spent/i }),
  ).toBeVisible();
  await expect(page.getByText("Selection-neutral default")).toBeVisible();
  await expect(page.getByText("§ School history")).toHaveCount(0);
  await expect(page.getByRole("link", { name: /read the methodology/i })).toHaveAttribute(
    "href",
    /docs\/recipes\/endowment-draw-rate\.md$/,
  );
  await expect(page.getByRole("link", { name: /explore the api/i })).toHaveAttribute(
    "href",
    "/api",
  );

  const picker = page.getByLabel("Institution");
  await picker.selectOption("152080");

  await expect(page.getByRole("heading", { name: "University of Notre Dame" })).toBeVisible();
  await expect(
    page.getByRole("img", {
      name: "Endowment value and draw-rate history for University of Notre Dame",
    }),
  ).toBeVisible();
  await expect(page.getByRole("link", { name: /open school page/i })).toHaveAttribute(
    "href",
    "/schools/university-of-notre-dame",
  );
  await expect(page.locator(".endowment-school-table-wrap tbody tr")).toHaveCount(5);

  await picker.selectOption("");
  await expect(page.getByText("Selection-neutral default")).toBeVisible();
  await expect(page.getByText("§ School history")).toHaveCount(0);
  await expectNoPageOverflow(page);
});

test("historical and small-endowment school states remain explicit", async ({ page }) => {
  await page.goto("/recipes/endowment-draw-rate");
  const picker = page.getByLabel("Institution");
  await picker.selectOption("457271");

  await expect(
    page.getByRole("heading", { name: "Academy for Jewish Religion California" }),
  ).toBeVisible();
  await expect(page.getByText("Historical/raw API only")).toBeVisible();
  await expect(page.getByText(/at least one beginning value is below \$5 million/i)).toBeVisible();
  await expect(page.getByRole("link", { name: /open school page/i })).toHaveCount(0);

  await picker.selectOption("155070");
  await expect(page.getByRole("heading", { name: "Barclay College" })).toBeVisible();
  await expect(page.locator('span[title="component identity mismatch"]')).toHaveText("n/a*");
});

test("recipes index exposes the endowment tracker", async ({ page }) => {
  await page.goto("/recipes");

  const card = page.locator("article", { hasText: "Endowment draw-rate tracker" });
  await expect(card.getByText("IPEDS F2 · PART H")).toBeVisible();
  await expect(card.getByRole("link", { name: "Open demo →" })).toHaveAttribute(
    "href",
    "/recipes/endowment-draw-rate",
  );
});
