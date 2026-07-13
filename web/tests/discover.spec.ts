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

const BUCKETS = [/^Essential/, /^Interesting/, /^Not important/, /^Not for me/];

// Shared funnel: fresh session → sorted deck → interests → first round.
// The mixed sort (buckets cycling across all 24 cards) guarantees strong,
// gentle, away, tension-free, and recorded entries all exist.
async function reachFirstRound(
  page: Page,
  opts: { zip?: { zip: string; preferred: string; maximum: string } } = {},
) {
  await page.goto("/discover");
  await page.getByRole("button", { name: /start sorting/i }).click();
  if (opts.zip) {
    await page.getByLabel(/home zip/i).fill(opts.zip.zip);
    await page.getByLabel(/prefer within/i).fill(opts.zip.preferred);
    await page.getByRole("textbox", { name: /never beyond/i }).fill(opts.zip.maximum);
    await page.getByRole("checkbox", { name: /occasional wildcard/i }).check();
    await page.getByRole("button", { name: /continue to the cards/i }).click();
  } else {
    await page.getByRole("button", { name: /skip — no distance limits/i }).click();
  }
  for (let i = 0; i < 24; i++) {
    await page.getByRole("button", { name: BUCKETS[i % 4] }).press("Enter");
  }
  await page.getByRole("button", { name: /see my preference profile/i }).click();
  await page.getByRole("button", { name: /continue to discovery rounds/i }).click();
  await page.getByRole("button", { name: /environment & climate/i }).click();
  await page.getByRole("button", { name: /see my first round/i }).click();
  await expect(page.locator("ol > li.cd-card").first()).toBeVisible();
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

  for (let i = 0; i < 24; i++) {
    // Keyboard operation: focus the bucket button and press Enter.
    // press() is keyboard-operated AND actionability-checked, so a swallowed
    // keystroke fails at the card that stalled instead of 5 lines later.
    await page.getByRole("button", { name: BUCKETS[i % 4] }).press("Enter");
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
  await expect(page.getByText("Card 1 of 24", { exact: false })).toBeVisible();
});

// Revision affordances and honest-guidance states. The conflicted-key
// "Tensions" panel is intentionally not exercised: deck opening-v1 gives every
// card a unique preference key (pinned in signals.test.ts), so a seek+avoid
// conflict cannot be produced from the sort alone — the panel becomes
// reachable when reflection/edit signals ship.
test("discover flow: wildcard note, revision mid-sort, essential nudge, restart", async ({
  page,
}) => {
  await page.goto("/discover");
  await page.getByRole("button", { name: /start sorting/i }).click();

  // Wildcards without a preferred radius explain themselves instead of
  // erroring — and the note clears once a radius exists.
  await page.getByRole("checkbox", { name: /occasional wildcard/i }).check();
  await expect(page.getByText(/this setting is ignored/i)).toBeVisible();
  await page.getByLabel(/prefer within/i).fill("150");
  await expect(page.getByText(/this setting is ignored/i)).toBeHidden();
  // A radius without an origin is unenforceable: continuing demands a ZIP.
  await page.getByRole("button", { name: /continue to the cards/i }).click();
  await expect(page.getByRole("alert").filter({ hasText: /starting point/i })).toBeVisible();
  await page.getByLabel(/home zip/i).fill("60601");
  await page.getByRole("button", { name: /continue to the cards/i }).click();

  // Back-navigation mid-sort: revising an earlier card resumes at the next
  // unanswered card rather than replaying already-sorted ones.
  // (the "· N sorted" suffix pins the progress line, not the live region)
  await expect(page.getByText("Card 1 of 24")).toBeVisible();
  await page.getByRole("button", { name: /^Essential/ }).click();
  await expect(page.getByText(/Card 2 of 24 · \d+ sorted/)).toBeVisible();
  await page.getByRole("button", { name: /^Interesting/ }).click();
  await expect(page.getByText(/Card 3 of 24 · \d+ sorted/)).toBeVisible();
  await page.getByRole("button", { name: /previous card/i }).click();
  await expect(page.getByText(/Card 2 of 24 · \d+ sorted/)).toBeVisible();
  await page.getByRole("button", { name: /^Not important/ }).click();
  await expect(page.getByText(/Card 3 of 24 · \d+ sorted/)).toBeVisible();

  // Everything-else-essential: 23 of 24 essential must trigger the nudge.
  for (let i = 2; i < 24; i++) {
    await page.getByRole("button", { name: /^Essential/ }).click();
  }
  await page.getByRole("button", { name: /see my preference profile/i }).click();
  await expect(page.getByText(/nothing can stand out/i)).toBeVisible();

  // Boundary edit from the ledger round-trips with the form prefilled and
  // every card response intact.
  await page.getByRole("button", { name: /change boundaries/i }).click();
  await expect(page.getByLabel(/prefer within/i)).toHaveValue("150");
  await page.getByLabel(/prefer within/i).fill("200");
  // With the sort complete, saving boundaries returns straight to the ledger.
  await page.getByRole("button", { name: /save boundaries/i }).click();
  await expect(
    page.getByRole("heading", { name: /what you told us/i }),
  ).toBeVisible();
  await expect(page.getByText(/prefer within ~200 miles/)).toBeVisible();

  // Start over wipes the stored session and lands on a blank boundaries form;
  // a reload proves nothing lingered in localStorage.
  await page.getByRole("button", { name: /start over/i }).click();
  await expect(page.getByRole("heading", { name: /how far from home/i })).toBeVisible();
  await expect(page.getByLabel(/prefer within/i)).toHaveValue("");
  expect(
    await page.evaluate(() => window.localStorage.getItem("cdfyi.discovery.session.v1")),
  ).toBeNull();
  await page.reload();
  await expect(
    page.getByRole("heading", { name: /find what you value/i }),
  ).toBeVisible();
});

test("discovery rounds: interests → round with reasons → reactions → shelf", async ({ page }) => {
  await page.goto("/discover");
  await page.getByRole("button", { name: /start sorting/i }).click();
  await page.getByLabel(/home zip/i).fill("30060");
  await page.getByLabel(/prefer within/i).fill("300");
  await page.getByRole("textbox", { name: /never beyond/i }).fill("800");
  await page.getByRole("button", { name: /continue to the cards/i }).click();
  for (let i = 0; i < 24; i++) {
    await page.getByRole("button", { name: BUCKETS[i % 4] }).press("Enter");
  }
  await page.getByRole("button", { name: /see my preference profile/i }).click();

  // Ledger → interests (pilot lake chips) → first round.
  await page.getByRole("button", { name: /continue to discovery rounds/i }).click();
  await expect(page.getByRole("heading", { name: /pulling you back/i })).toBeVisible();
  await expectAxeClean(page);
  await page.getByRole("button", { name: /environment & climate/i }).click();
  await page.getByRole("button", { name: /see my first round/i }).click();

  // The round: schools with role chips, reasons, source & limits disclosure,
  // approximate distance under the hard cap.
  await expect(page.getByRole("heading", { name: /with receipts/i })).toBeVisible();
  const cards = page.locator("ol > li.cd-card");
  await expect(cards).toHaveCount(6);
  await expect(cards.first().getByText(/mi straight-line/)).toBeVisible();
  await cards.first().getByText("source & limits").first().click();
  await expect(cards.first().getByText(/data, \d{4}/).first()).toBeVisible();
  await expectAxeClean(page);
  const firstSchool = await cards.first().getByRole("heading").textContent();

  // Profile strip: collapsed bar is present with steering counts, and every
  // reason that traces to a preference carries its attribution gloss.
  const strip = page.getByTestId("profile-strip");
  await expect(strip.getByText(/Steering: \d+ strong/)).toBeVisible();
  await expect(page.getByText(/Because you (said|asked)/).first()).toBeVisible();

  // Expand the drawer, spotlight a preference, and verify the round is a
  // pure render under it: same schools, same order.
  const orderBefore = await page.locator("ol > li.cd-card h2").allTextContents();
  await strip.getByRole("button", { name: /your answers/i }).click();
  const drawer = page.getByRole("region", { name: /your answers/i });
  await expect(drawer.getByText(/steering strongly/i)).toBeVisible();
  await expectAxeClean(page);
  // Deterministic spotlight: derive the toggle from a rendered gloss, so the
  // highlight branch always exercises real matches (a regression that makes
  // every toggle match zero can't slip through the zero-match copy).
  const glossText = await page
    .getByText(/^Because you said: “/)
    .first()
    .textContent();
  const statement = glossText!.slice("Because you said: “".length).replace(/”$/, "");
  const toggle = drawer
    .locator("button[aria-pressed]", { hasText: statement.slice(0, 30) })
    .first();
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-pressed", "true");
  const spotlitCount = await page.locator("[data-spotlit]").count();
  expect(spotlitCount).toBeGreaterThan(0);
  const announcement = await strip.locator("[aria-live]").textContent();
  expect(announcement).toMatch(new RegExp(`Highlighting ${spotlitCount} reason`));
  const orderAfter = await page.locator("ol > li.cd-card h2").allTextContents();
  expect(orderAfter).toEqual(orderBefore);
  await expectAxeClean(page);
  // Non-toggle entries explain themselves instead of pretending to be
  // spotlights: away entries carry their copy, and non-actionable keys sit
  // in the disclosed "Recorded, not yet matching" group (never inflating
  // the steering counts).
  await expect(
    drawer.getByText(/shapes scoring, not the reasons shown/).first(),
  ).toBeVisible();
  await expect(drawer.getByText(/recorded, not yet matching/i)).toBeVisible();
  // Toggling the same chip off clears the spotlight and announces it.
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-pressed", "false");
  await expect(page.locator("[data-spotlit]")).toHaveCount(0);
  expect(await strip.locator("[aria-live]").textContent()).toBe("Highlight cleared.");
  // Re-arm so Escape below demonstrably clears an active spotlight.
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-pressed", "true");
  // Escape closes the drawer and clears the spotlight (one rule).
  await page.keyboard.press("Escape");
  await expect(drawer).toBeHidden();
  await expect(page.locator("[data-spotlit]")).toHaveCount(0);
  await expect(strip.getByRole("button", { name: /your answers/i })).toBeFocused();

  // Research next: must pick a reason and answer familiarity (PRD §10).
  await cards.first().getByRole("button", { name: /research next/i }).click();
  await expect(page.getByText(/which reason are you saving/i)).toBeVisible();
  await cards.first().getByRole("radio").first().check();
  await page.getByRole("radio", { name: "No", exact: true }).check();
  await cards.first().getByRole("button", { name: /save to shelf/i }).click();
  await expect(page.getByRole("button", { name: /research shelf \(1\)/i })).toBeVisible();

  // Not for me on the second card (skip reason via "Something else").
  const second = cards.nth(1);
  await second.getByRole("button", { name: /not for me/i }).click();
  await second.getByRole("radio", { name: /something else/i }).check();
  await second.getByRole("button", { name: /set it aside/i }).click();

  // Advancing rounds clears any active spotlight — a highlight surviving the
  // transition would describe the previous round. Inline collapsed-bar chips
  // exist only at sm+ widths, so this leg runs on the desktop project.
  const inlineChip = strip.locator(".cd-chip[aria-pressed]").first();
  const inlineChipVisible = await inlineChip.isVisible();
  if (inlineChipVisible) {
    await inlineChip.click();
    await expect(inlineChip).toHaveAttribute("aria-pressed", "true");
  }

  // Next round: saved + rejected schools never reappear.
  await page.getByRole("button", { name: /next round/i }).click();
  if (inlineChipVisible) {
    await expect(page.locator("[data-spotlit]")).toHaveCount(0);
    await expect(inlineChip).toHaveAttribute("aria-pressed", "false");
  }
  await expect(
    page.locator("ol > li.cd-card h2", { hasText: firstSchool ?? "" }),
  ).toHaveCount(0);
  const roundTwoNames = await page
    .locator("ol > li.cd-card h2")
    .allTextContents();
  expect(roundTwoNames).not.toContain(firstSchool);
  await expectAxeClean(page);

  // Shelf holds the saved school with the student's own reason.
  await page.getByRole("button", { name: /research shelf/i }).click();
  await expect(page.getByRole("heading", { name: /shortlist/i })).toBeVisible();
  await expect(page.getByText(/saved because:/i)).toBeVisible();
  if (firstSchool) {
    await expect(page.getByRole("heading", { name: firstSchool })).toBeVisible();
  }
  await expectAxeClean(page);

  // Session (with rounds state) survives a reload.
  await page.reload();
  await expect(page.getByRole("heading", { name: /shortlist/i })).toBeVisible();
});

test("discovery rounds with profile strip reflow at 320px", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 800 });
  await reachFirstRound(page);

  const strip = page.getByTestId("profile-strip");
  await expect(strip.getByText(/Steering: \d+ strong/)).toBeVisible();
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBeLessThanOrEqual(1);

  // The fixed strip must not obscure the reaction buttons: the last card's
  // panel still opens from a real click.
  const lastCard = page.locator("ol > li.cd-card").last();
  await lastCard.getByRole("button", { name: /not for me/i }).scrollIntoViewIfNeeded();
  await lastCard.getByRole("button", { name: /not for me/i }).click();
  await expect(lastCard.getByText(/not for you because of/i)).toBeVisible();
  await expectAxeClean(page);

  // "Edit profile" in the drawer routes back to the ledger — the strip is
  // read-only by design and the ledger stays the only editing surface.
  await strip.getByRole("button", { name: /your answers/i }).click();
  await page
    .getByRole("region", { name: /your answers/i })
    .getByRole("button", { name: /edit profile/i })
    .click();
  await expect(
    page.getByRole("button", { name: /continue to discovery rounds/i }),
  ).toBeVisible();
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
