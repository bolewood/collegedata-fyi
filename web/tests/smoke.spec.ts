import { expect, test, type Page } from "@playwright/test";

async function expectNoBodyOverflow(page: Page) {
  const overflow = await page.evaluate(() => {
    const body = document.body;
    const html = document.documentElement;
    return Math.max(body.scrollWidth, html.scrollWidth) - window.innerWidth;
  });
  expect(overflow).toBeLessThanOrEqual(2);
}

test("homepage search opens an institution page", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByRole("heading", { name: /college data/i }),
  ).toBeVisible();

  await page
    .getByPlaceholder("Search schools by name, alias, or city...")
    .fill("Rice");
  const result = page.getByText("Rice University").first();
  await expect(result).toBeVisible();
  await result.click();

  await expect(page).toHaveURL(/\/schools\/rice/);
  await expect(
    page.getByRole("heading", { name: /Rice University/i }),
  ).toBeVisible();
});

test("coverage page renders filterable accountability data", async ({ page }) => {
  await page.goto("/coverage");
  await expect(
    page.getByRole("heading", { name: /What we have/i }),
  ).toBeVisible();
  await expect(page.getByText("No public CDS found").first()).toBeVisible();
  await expect(page.getByText("Methodology")).toBeVisible();
});

test("browser loads live rows and source links resolve", async ({ page, request }) => {
  await page.goto("/browse");
  await expect(
    page.getByRole("heading", { name: /Queryable school browser/i }),
  ).toBeVisible();
  await expect(page.getByText("Browser query failed")).toHaveCount(0);
  await expect(page.getByText(/Showing 1-/)).toBeVisible();

  const source = page.locator('[data-testid="browser-source-link"]:visible').first();
  await expect(source).toBeVisible();
  const href = await source.getAttribute("href");
  expect(href).toBeTruthy();
  const response = await request.get(href!);
  expect(response.status()).toBeLessThan(400);
});

test("facts endpoint returns flat JSON", async ({ request }) => {
  const response = await request.get("/api/facts/mit");
  expect(response.ok()).toBeTruthy();
  const body = await response.json();
  expect(body.school_id).toBe("mit");
  expect(body.school_name).toContain("Massachusetts Institute of Technology");
  expect(typeof body.raw).toBe("object");
});

test("mobile launch surfaces do not overflow", async ({ page, isMobile }) => {
  test.skip(!isMobile, "mobile project only");

  for (const path of ["/", "/coverage", "/browse"]) {
    await page.goto(path);
    await expectNoBodyOverflow(page);
  }
});
