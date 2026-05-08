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

test("homepage latest drain rows link to school pages", async ({ page }) => {
  await page.goto("/");

  const firstDrainRow = page.locator(".cd-drain-row").first();
  await expect(firstDrainRow).toBeVisible();
  await expect(firstDrainRow).toHaveAttribute("href", /\/schools\/[^/]+/);

  await firstDrainRow.click();
  await expect(page).toHaveURL(/\/schools\/[^/]+/);
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

test("school-year page renders reconstructed CDS tables", async ({ page }) => {
  await page.goto("/schools/bowdoin/2024-25");
  await expect(
    page.getByRole("heading", { name: /Bowdoin College/i }),
  ).toBeVisible();

  const b1 = page.getByRole("table", { name: /B1 undergraduate enrollment/i });
  await expect(b1).toBeVisible();
  await expect(b1.getByRole("columnheader", { name: /^(Males|Men)$/i })).toBeVisible();
  await expect(b1.getByRole("rowheader", { name: "Total undergraduates", exact: true })).toBeVisible();

  const b2 = page.getByRole("table", { name: /B2 enrollment by race and ethnicity/i });
  await expect(b2).toBeVisible();
  await expect(b2.getByRole("columnheader", { name: /Degree-seeking undergraduates/i })).toBeVisible();
  await expect(b2.getByRole("rowheader", { name: "Hispanic/Latino" })).toBeVisible();

  const b3 = page.getByRole("table", { name: /B3 degrees awarded/i });
  await expect(b3).toBeVisible();
  await expect(b3.getByRole("rowheader", { name: "Bachelor's degrees" })).toBeVisible();

  const b4 = page.getByRole("table", { name: /B4 current graduation-rate cohort/i });
  await expect(b4).toBeVisible();
  await expect(b4.getByRole("columnheader", { name: /Pell Grant/i })).toBeVisible();
  await expect(b4.getByRole("rowheader", { name: "Six-year graduation rate" })).toBeVisible();

  const b5 = page.getByRole("table", { name: /B5 previous graduation-rate cohort/i });
  await expect(b5).toBeVisible();
  await expect(b5.getByRole("rowheader", { name: "Initial cohort" })).toBeVisible();

  const c1 = page.getByRole("table", { name: /C1 first-year admissions/i });
  await expect(c1).toBeVisible();
  await expect(c1.getByRole("columnheader", { name: /^(Males|Men)$/i })).toBeVisible();
  await expect(c1.getByRole("rowheader", { name: "Applied" })).toBeVisible();

  const c9Submission = page.getByRole("table", { name: /C9 test-score submission/i });
  await expect(c9Submission).toBeVisible();
  await expect(c9Submission.getByRole("rowheader", { name: "SAT" })).toBeVisible();

  const c9Percentiles = page.getByRole("table", { name: /C9 test-score percentiles/i });
  await expect(c9Percentiles).toBeVisible();
  await expect(c9Percentiles.getByRole("columnheader", { name: /75th percentile/i })).toBeVisible();
  await expect(c9Percentiles.getByRole("rowheader", { name: "SAT composite" })).toBeVisible();

  const c7 = page.getByRole("table", { name: /C7 basis for selection/i });
  await expect(c7).toBeVisible();
  await expect(c7.getByRole("columnheader", { name: "Very important" })).toBeVisible();
  await expect(c7.getByRole("rowheader", { name: "Academic GPA" })).toBeVisible();

  const d2 = page.getByRole("table", { name: /D2 transfer admissions/i });
  await expect(d2).toBeVisible();
  await expect(d2.getByRole("rowheader", { name: "Enrolled" })).toBeVisible();

  const g1 = page.getByRole("table", { name: /G1 undergraduate costs/i });
  await expect(g1).toBeVisible();
  await expect(g1.getByRole("rowheader", { name: "Tuition", exact: true })).toBeVisible();

  const g5 = page.getByRole("table", { name: /G5 estimated expenses/i });
  await expect(g5).toBeVisible();
  await expect(g5.getByRole("columnheader", { name: /Commuters not living at home/i })).toBeVisible();

  const h2 = page.getByRole("table", { name: /H2 students awarded aid/i });
  await expect(h2).toBeVisible();
  await expect(h2.getByRole("columnheader", { name: /All undergraduates full-time/i })).toBeVisible();
  await expect(h2.getByRole("rowheader", { name: "Average financial aid package" })).toBeVisible();

  const h2a = page.getByRole("table", { name: /H2A non-need-based aid/i });
  await expect(h2a).toBeVisible();
  await expect(h2a.getByRole("columnheader", { name: /First-year full-time/i })).toBeVisible();
  await expect(h2a.getByRole("rowheader", { name: /Average institutional non-need grant/i })).toBeVisible();

  const h5 = page.getByRole("table", { name: /H5 student loans/i });
  await expect(h5).toBeVisible();
  await expect(h5.getByRole("columnheader", { name: /Average per borrower/i })).toBeVisible();

  const i1 = page.getByRole("table", { name: /I1 instructional faculty/i });
  await expect(i1).toBeVisible();
  await expect(i1.getByRole("rowheader", { name: "Total instructional faculty" })).toBeVisible();

  const i3 = page.getByRole("table", { name: /I3 undergraduate class size/i });
  await expect(i3).toBeVisible();
  await expect(i3.getByRole("rowheader", { name: "100+ students" })).toBeVisible();

  const j = page.getByRole("table", { name: /J degrees conferred by discipline/i });
  await expect(j).toBeVisible();
  await expect(j.getByRole("columnheader", { name: "Bachelor's" })).toBeVisible();
  await expect(j.getByRole("rowheader", { name: "Computer and information sciences" })).toBeVisible();
});

test("mobile launch surfaces do not overflow", async ({ page, isMobile }) => {
  test.skip(!isMobile, "mobile project only");

  for (const path of ["/", "/coverage", "/browse", "/schools/bowdoin/2024-25"]) {
    await page.goto(path);
    await expectNoBodyOverflow(page);
  }
});
