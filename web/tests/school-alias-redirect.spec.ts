import { expect, test } from "@playwright/test";

test.describe("retired school aliases", () => {
  test("preserves scalar and repeated query values on the school page", async ({
    page,
  }) => {
    const response = await page.goto(
      "/schools/tufts-university?tab=sources&compare=cost&compare=aid",
    );

    expect(response?.ok()).toBeTruthy();
    const url = new URL(page.url());
    expect(url.pathname).toBe("/schools/tufts");
    expect(url.searchParams.get("tab")).toBe("sources");
    expect(url.searchParams.getAll("compare")).toEqual(["cost", "aid"]);
    await expect(
      page.getByRole("heading", { name: /Tufts University/i }),
    ).toBeVisible();
  });

  test("preserves the year and query on a school-year page", async ({ page }) => {
    const response = await page.goto(
      "/schools/tufts-university/2024-25?download=1",
    );

    expect(response?.ok()).toBeTruthy();
    const url = new URL(page.url());
    expect(url.pathname).toBe("/schools/tufts/2024-25");
    expect(url.searchParams.get("download")).toBe("1");
    await expect(
      page.getByRole("heading", { name: /Tufts University/i }),
    ).toBeVisible();
  });

  test("does not add a dangling query delimiter when none was requested", async ({
    page,
  }) => {
    const response = await page.goto("/schools/tufts-university");

    expect(response?.ok()).toBeTruthy();
    expect(page.url()).toMatch(/\/schools\/tufts$/);
  });
});
