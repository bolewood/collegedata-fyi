import { expect, test } from "@playwright/test";

test("school page renders positioning card and persists profile locally", async ({ page }) => {
  await page.goto("/schools/bowdoin");
  await expect(page.getByText("§ Academic profile")).toBeVisible();
  await expect(page.getByText("SAT composite").first()).toBeVisible();
  await expect(page.getByText(/FROM THE .* OF ADMITS WHO SUBMITTED SCORES/).first()).toBeVisible();

  await page.getByRole("spinbutton", { name: "GPA" }).fill("3.85");
  await page.getByRole("spinbutton", { name: "SAT composite" }).fill("1500");
  await page.getByRole("button", { name: "Show my position" }).click();

  await expect(page.getByText(/Your SAT is within the middle 50%/)).toBeVisible();
  await expect(page.getByText(/TIER SUPPRESSED|TIER ·/)).toBeVisible();

  await page.goto("/schools/mit");
  await expect(page.getByText("Your entered GPA 3.85")).toBeVisible();
});
