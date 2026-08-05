import { expect, test, type Page } from "@playwright/test";

const BUCKET_DISCLAIMER =
  "Many things put a school on these lists besides financial stress: board-approved spending of unrestricted quasi-endowment funds, drawing down a completed capital campaign, deploying a large one-time gift, or ordinary volatility in a small endowment, where a single transfer can swing the rate by whole percentage points. Appearing here is not evidence of fiscal irresponsibility. Rates come from each school's own federal IPEDS filing. Some states' UPMIFA statutes presume imprudence only above a 7% rate measured against a multi-year average value — a different measure than the single-year rate shown here.";

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
  await expect(
    page.getByText(/no school is preselected or highlighted/i),
  ).toBeVisible();
  await expect(page.getByText("§ School history")).toHaveCount(0);
  await expect(page.getByRole("link", { name: /read the methodology/i })).toHaveAttribute(
    "href",
    /docs\/recipes\/endowment-draw-rate\.md$/,
  );
  await expect(page.getByRole("link", { name: /explore the api/i })).toHaveAttribute(
    "href",
    "/api",
  );

  const picker = page.getByRole("combobox", { name: "School", exact: true });
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
  await expect(
    page.getByText(/no school is preselected or highlighted/i),
  ).toBeVisible();
  await expect(page.getByText("§ School history")).toHaveCount(0);
  await expectNoPageOverflow(page);
});

test("historical and small-endowment school states remain explicit", async ({ page }) => {
  await page.goto("/recipes/endowment-draw-rate");
  const picker = page.getByRole("combobox", { name: "School", exact: true });
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

test("threshold cells disclose their complete school membership", async ({ page }) => {
  await page.goto("/recipes/endowment-draw-rate");

  const bucketToggle = page.locator("#endowment-bucket-toggle-2024-15");
  await expect(bucketToggle).toBeVisible();
  await expect(bucketToggle).toHaveAccessibleName(
    /^Show schools above 15% in FY2024: [\d,]+ schools, \d+\.\d% of eligible schools$/,
  );
  await expect(page.getByText(BUCKET_DISCLAIMER, { exact: true })).toHaveCount(1);

  const countMatch = (await bucketToggle.textContent())?.match(/\(([\d,]+)\)/);
  expect(countMatch).not.toBeNull();
  const displayedCount = Number(countMatch![1].replaceAll(",", ""));

  await bucketToggle.focus();
  await page.keyboard.press("Enter");
  await expect(bucketToggle).toHaveAttribute("aria-expanded", "true");
  await expect(bucketToggle).toHaveAccessibleName(
    /^Hide schools above 15% in FY2024: [\d,]+ schools, \d+\.\d% of eligible schools$/,
  );

  const panel = page.getByRole("region", {
    name: "Schools above 15% in FY2024",
  });
  await expect(panel).toBeVisible();
  await expect(panel.getByText(BUCKET_DISCLAIMER, { exact: true })).toBeVisible();
  await expect(page.getByText(BUCKET_DISCLAIMER, { exact: true })).toHaveCount(2);

  const list = panel.getByRole("list", {
    name: "Schools above 15% in FY2024",
  });
  const rows = list.getByRole("listitem");
  await expect(rows).toHaveCount(displayedCount);
  const firstRow = rows.first();
  await expect(firstRow.locator(".endowment-bucket-row__rank")).toHaveText("1");
  await expect(firstRow.locator(".endowment-bucket-row__identity > :first-child")).not.toBeEmpty();
  await expect(firstRow.locator(".endowment-bucket-row__state")).toHaveText(
    /^(?:[A-Z]{2}|State unavailable)$/,
  );
  await expect(firstRow.locator(".endowment-bucket-row__rate")).toHaveText(/^\d+\.\d%$/);

  const closedSchoolRow = list
    .getByRole("listitem")
    .filter({ hasText: "not in directory (typically closed)" })
    .first();
  await expect(closedSchoolRow).toBeVisible();
  await expect(closedSchoolRow.getByRole("link")).toHaveCount(0);
  await expect(list.getByText("small endowment — rate is volatile").first()).toBeVisible();

  const linkedSchool = list.locator('a[href^="/schools/"]').first();
  await expect(linkedSchool).toBeVisible();
  const schoolHref = await linkedSchool.getAttribute("href");
  expect(schoolHref).toMatch(/^\/schools\/[a-z0-9-]+$/);

  await bucketToggle.focus();
  await page.keyboard.press("Enter");
  await expect(bucketToggle).toHaveAttribute("aria-expanded", "false");
  await expect(panel).toHaveCount(0);
  await expect(page.getByText(BUCKET_DISCLAIMER, { exact: true })).toHaveCount(1);

  const longBucketToggle = page.locator("#endowment-bucket-toggle-2024-5");
  const longCountMatch = (await longBucketToggle.textContent())?.match(/\(([\d,]+)\)/);
  expect(longCountMatch).not.toBeNull();
  const longDisplayedCount = Number(longCountMatch![1].replaceAll(",", ""));
  await longBucketToggle.focus();
  await page.keyboard.press("Enter");

  const longList = page.getByRole("list", {
    name: "Schools above 5% in FY2024",
  });
  const longRows = longList.getByRole("listitem");
  await expect(longRows).toHaveCount(longDisplayedCount);
  expect(await longList.evaluate((element) => element.scrollHeight > element.clientHeight)).toBe(
    true,
  );
  await expect(longRows.last()).toBeAttached();
  await longRows.last().scrollIntoViewIfNeeded();
  await expect(longRows.last()).toBeVisible();
  await expect(page.getByText(BUCKET_DISCLAIMER, { exact: true })).toHaveCount(2);
  await expectNoPageOverflow(page);
  const response = await page.goto(schoolHref!);
  expect(response?.ok()).toBe(true);
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
