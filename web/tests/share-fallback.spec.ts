import { expect, test, type Page } from "@playwright/test";

// The Share popover's last resort is a selectable URL, shown when neither the
// async clipboard nor execCommand("copy") works. The execCommand path focuses
// a temporary textarea; when that sat outside the control, the focus move
// closed the popover and the fallback never appeared.

async function stubCopy(page: Page, execCommandResult: boolean) {
  await page.addInitScript((result) => {
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: () => Promise.reject(new Error("denied")) },
    });
    document.execCommand = () => result;
  }, execCommandResult);
}

// Touch devices with a native share sheet skip the popover on the first tap.
test.skip(({ isMobile }) => isMobile, "desktop popover");

test("a failed copy leaves the popover open with a selectable link", async ({ page }) => {
  await stubCopy(page, false);
  await page.goto("/coverage");

  await page.getByRole("button", { name: "Share" }).click();
  await page.getByRole("button", { name: "Copy link" }).click();

  const options = page.getByRole("group", { name: "Share options" });
  const fallback = options.getByLabel("Copy this link");
  await expect(fallback).toBeVisible();
  await expect(fallback).toBeFocused();
  await expect(fallback).toHaveValue(/\/coverage$/);
  await expect(page.locator("textarea")).toHaveCount(0);
});

test("the execCommand path copies, closes the popover and returns focus", async ({ page }) => {
  await stubCopy(page, true);
  await page.goto("/coverage");

  const trigger = page.getByRole("button", { name: /^(Share|Copied)$/ });
  await trigger.click();
  await page.getByRole("button", { name: "Copy link" }).click();

  await expect(page.getByRole("group", { name: "Share options" })).toHaveCount(0);
  await expect(page.getByRole("status").filter({ hasText: "Link copied" })).toHaveCount(1);
  await expect(trigger).toBeFocused();
  await expect(page.locator("textarea")).toHaveCount(0);
});
