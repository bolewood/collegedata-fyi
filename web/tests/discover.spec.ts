import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

// PRD 026 §13 accessibility acceptance for the slice-1 discovery flow:
// keyboard-operable sort with no dragging, live-region announcements,
// field-associated validation errors that never erase input, and automated
// WCAG checks on every step.

const WCAG_TAGS = ["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"];

// Scoped to the flow container: the surrounding nav/footer chrome carries
// tracked pre-existing contrast debt (see docs/backlog.md); the discovery UI
// itself must be violation-free.
async function expectAxeClean(page: Page) {
  const results = await new AxeBuilder({ page })
    .include("#discover-flow")
    .withTags(WCAG_TAGS)
    .analyze();
  expect(results.violations).toEqual([]);
}

test("discover flow: boundaries → card sort → ledger", async ({ page }) => {
  await page.goto("/discover");

  // Intro
  await expect(
    page.getByRole("heading", { name: /find what you value/i }),
  ).toBeVisible();
  await expectAxeClean(page);
  await page.getByRole("button", { name: /start sorting/i }).click();

  // Boundaries: preferred > maximum must block with an associated error
  // and preserve the typed values (PRD failure state).
  await expect(page.getByRole("heading", { name: /how far from home/i })).toBeVisible();
  await page.getByLabel(/prefer within/i).fill("500");
  await page.getByRole("textbox", { name: /never beyond/i }).fill("200");
  await page.getByRole("button", { name: /continue to the cards/i }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: /larger than/i }),
  ).toBeVisible();
  await expect(page.getByLabel(/prefer within/i)).toHaveValue("500");

  await page.getByLabel(/home zip/i).fill("30060");
  await page.getByLabel(/prefer within/i).fill("150");
  await page.getByRole("textbox", { name: /never beyond/i }).fill("400");
  await page.getByRole("checkbox", { name: /occasional wildcard/i }).check();
  await expectAxeClean(page);
  await page.getByRole("button", { name: /continue to the cards/i }).click();

  // Card sort: 24 cards, one at a time, four buttons, no dragging.
  await expect(page.getByText("Card 1 of 24")).toBeVisible();
  await expectAxeClean(page);

  const buckets = [/^Essential/, /^Interesting/, /^Not important/, /^Not for me/];
  for (let i = 0; i < 24; i++) {
    // Keyboard operation: focus the bucket button and press Enter.
    const button = page.getByRole("button", { name: buckets[i % 4] });
    await button.focus();
    await page.keyboard.press("Enter");
  }

  // The live region announced the final sort.
  await expect(page.locator('[aria-live="polite"]')).toContainText(/sorted/i);

  await page.getByRole("button", { name: /see my preference profile/i }).click();

  // Ledger: boundary summary, bucket sections, evidence transparency.
  await expect(
    page.getByRole("heading", { name: /what you told us/i }),
  ).toBeVisible();
  await expect(page.getByText(/starting near 30060/)).toBeVisible();
  await expect(page.getByText(/never beyond ~400 miles/)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Essential" })).toBeVisible();
  await expect(page.getByText("evidence-backed").first()).toBeVisible();
  await expectAxeClean(page);

  // The session survives a reload (browser-local persistence).
  await page.reload();
  await expect(
    page.getByRole("heading", { name: /what you told us/i }),
  ).toBeVisible();

  // "Change" reopens the sort at that card, and the ledger is reachable again.
  await page.getByRole("button", { name: "Change", exact: true }).first().click();
  await expect(page.getByText(/Card \d+ of 24/)).toBeVisible();
});

test("discover card sort reflows at 320px without horizontal scroll", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await page.goto("/discover");
  await page.getByRole("button", { name: /start sorting/i }).click();
  await page.getByRole("button", { name: /skip — no distance limits/i }).click();
  await expect(page.getByText("Card 1 of 24")).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);
});
