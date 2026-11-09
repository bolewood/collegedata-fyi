import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "@playwright/test";

test("feedback has a quiet accessible form, safe URL context and permanent fallback", async ({
  page,
}, testInfo) => {
  await page.goto(
    "/feedback?from=match&kind=data_issue&school=unknown&year=private&match=student-code&email=canary%40example.test",
  );
  await expect(
    page.getByRole("heading", { name: "A note to the maintainer." }),
  ).toBeVisible();
  await expect(page.locator('input[id="feedback-school"]')).toHaveValue("");
  await expect(page.locator('input[id="feedback-year"]')).toHaveValue("");
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute(
    "content",
    /noindex/,
  );
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
    "href",
    /\/feedback$/,
  );
  await expect(
    page.getByRole("link", { name: "contact@bolewood.com", exact: true }),
  ).toHaveAttribute("href", "mailto:contact@bolewood.com");
  await expect(page.locator("main")).not.toContainText("student-code");
  await expect(page.locator("input[type=email]")).toHaveValue("");
  await page.setViewportSize({ width: 320, height: 720 });
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= window.innerWidth,
      ),
    )
    .toBe(true);
  expect(
    (
      await new AxeBuilder({ page })
        .include("main")
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
  await page.screenshot({
    path: `../scratch/community-feedback/form-${testInfo.project.name}.png`,
    fullPage: true,
  });
});

test("without JavaScript the form cannot pretend to send and email stays available", async ({
  browser,
  baseURL,
}) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto(`${baseURL}/feedback`);
  await expect(
    page.getByRole("button", { name: "Send message" }),
  ).toBeDisabled();
  expect(
    await page.locator("noscript").evaluate((element) => element.textContent),
  ).toContain("The website form needs JavaScript.");
  await expect(
    page.getByRole("link", { name: "contact@bolewood.com", exact: true }),
  ).toHaveAttribute("href", "mailto:contact@bolewood.com");
  await context.close();
});

test("keyboard users can send, hear a failure and keep the draft at 200 percent zoom geometry", async ({
  page,
}) => {
  await page.goto("/feedback");
  await page.route("https://formspree.io/f/**", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: '{"error":"unavailable"}',
    }),
  );
  for (
    let i = 0;
    i < 35 &&
    !(await page
      .locator("#feedback-message")
      .evaluate((element) => element === document.activeElement));
    i++
  )
    await page.keyboard.press("Tab");
  await expect(page.locator("#feedback-message")).toBeFocused();
  await page.keyboard.type("A keyboard-only private note");
  for (
    let i = 0;
    i < 15 &&
    !(await page
      .getByRole("button", { name: "Send message" })
      .evaluate((element) => element === document.activeElement));
    i++
  )
    await page.keyboard.press("Tab");
  await expect(
    page.getByRole("button", { name: "Send message" }),
  ).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("main").getByRole("alert")).toBeFocused();
  await expect(page.locator("#feedback-message")).toHaveValue(
    "A keyboard-only private note",
  );
  const cdp = await page.context().newCDPSession(page);
  await cdp.send("Emulation.setDeviceMetricsOverride", {
    width: 640,
    height: 400,
    deviceScaleFactor: 2,
    mobile: false,
  });
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= window.innerWidth,
    ),
  ).toBe(true);
});

test("browser posts FormData directly to Formspree and shows thank-you confirmation", async ({
  page,
}) => {
  let submittedBody = "";
  let acceptHeader = "";
  await page.route("https://formspree.io/f/**", async (route) => {
    submittedBody = route.request().postData() ?? "";
    acceptHeader = route.request().headers()["accept"] ?? "";
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: '{"ok":true,"next":"https://formspree.io/thanks"}',
    });
  });
  await page.goto("/feedback?from=footer");
  const message = "BROWSER FORMSPREE CANARY " + crypto.randomUUID();
  await page.getByLabel("What would you like us to know?").fill(message);
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(
    page.getByRole("heading", { name: "Thanks. Your message reached us." }),
  ).toBeVisible();
  expect(acceptHeader).toBe("application/json");
  expect(submittedBody).toContain("[Feedback] collegedata.fyi");
  expect(submittedBody).toContain(message);
  expect(await page.evaluate(() => ({ ...localStorage }))).toEqual({});
});

test("errors retain drafts, editing clears field error, and approval interest requires email", async ({
  page,
}) => {
  await page.goto("/feedback?kind=story&from=api");
  await page
    .getByLabel("How are you using the data?")
    .fill("A private research notebook");
  await page
    .getByLabel("I'm interested in being featured on the site.")
    .check();
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.locator("main").getByRole("alert")).toBeFocused();
  await expect(page.locator("main").getByRole("alert")).toContainText(
    "Add an email",
  );
  await page
    .getByLabel("Email", { exact: true })
    .fill("browser-canary@example.test");
  await expect(page.locator("input[type=email]")).toHaveAttribute(
    "aria-invalid",
    "false",
  );
  let status = 429;
  await page.route("https://formspree.io/f/**", async (route) => {
    await route.fulfill({
      status,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        error: status === 429 ? "limited" : "unavailable",
      }),
    });
  });
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText(
    "You've sent several messages recently",
  );
  status = 503;
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText(
    "We couldn't send your message",
  );
  await expect(page.getByLabel("How are you using the data?")).toHaveValue(
    "A private research notebook",
  );
  await page.unroute("https://formspree.io/f/**");
  await page.route("https://formspree.io/f/**", (route) =>
    route.abort("timedout"),
  );
  await page.getByRole("button", { name: "Send message" }).click();
  await expect(page.locator("main").getByRole("alert")).toContainText(
    "couldn't confirm whether your message arrived",
  );
  expect(
    (
      await new AxeBuilder({ page })
        .include("main")
        .withTags(["wcag2a", "wcag2aa", "wcag21aa", "wcag22aa"])
        .analyze()
    ).violations,
  ).toEqual([]);
});
