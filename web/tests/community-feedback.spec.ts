import AxeBuilder from "@axe-core/playwright";
import { test, expect } from "@playwright/test";
const isolated = process.env.COMMUNITY_E2E_ISOLATED === "true";

test("feedback has a quiet accessible form, safe URL context and permanent fallback", async ({
  page,
}, testInfo) => {
  await page.goto(
    "/feedback?from=match&kind=data_issue&school=unknown&year=private&match=student-code&email=canary%40example.test",
  );
  await expect(
    page.getByRole("heading", { name: "A note to the maintainer." }),
  ).toBeVisible();
  if (isolated) {
    await expect(page.locator('input[id="feedback-school"]')).toHaveValue("");
    await expect(page.locator('input[id="feedback-year"]')).toHaveValue("");
  }
  await expect(page.locator('meta[name="robots"]')).toHaveAttribute("content", /noindex/);
  await expect(page.locator('link[rel="canonical"]')).toHaveAttribute(
    "href",
    /\/feedback$/,
  );
  await expect(
    page.getByRole("link", { name: "contact@bolewood.com", exact: true }),
  ).toHaveAttribute("href", "mailto:contact@bolewood.com");
  await expect(page.locator("main")).not.toContainText("student-code");
  if (isolated) await expect(page.locator("input[type=email]")).toHaveValue("");
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
  if (!isolated)
    await expect(
      page.getByRole("button", { name: "Send message" }),
    ).toHaveCount(0);
});
test("without JavaScript the form cannot pretend to send and email stays available", async ({
  browser,
  baseURL,
}) => {
  const context = await browser.newContext({ javaScriptEnabled: false });
  const page = await context.newPage();
  await page.goto(`${baseURL}/feedback`);
  if (isolated) {
    await expect(
      page.getByRole("button", { name: "Send message" }),
    ).toBeDisabled();
    expect(
      await page.locator("noscript").evaluate((element) => element.textContent),
    ).toContain("The website form needs JavaScript.");
  } else
    await expect(
      page.getByText("The website form is unavailable right now.", {
        exact: false,
      }),
    ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "contact@bolewood.com", exact: true }),
  ).toHaveAttribute("href", "mailto:contact@bolewood.com");
  await context.close();
});
test.describe("isolated database flow", () => {
  test.skip(
    !isolated,
    "Requires tools/community/local_web_smoke.py with isolated PostgreSQL/PostgREST; never production storage",
  );
  test("keyboard users can send, hear a failure and keep the draft at 200 percent zoom geometry", async ({
    page,
  }) => {
    await page.goto("/feedback");
    await page.route("**/api/feedback", (route) =>
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
    // A 1280x800 display at 200% browser zoom has a 640x400 CSS viewport.
    // CSS body.zoom does not change media queries and is not browser zoom.
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
  test("anonymous feedback commits once and retry returns the same receipt", async ({
    page,
  }) => {
    const outbound: string[] = [];
    page.on("request", (request) => {
      if (
        request.method() === "POST" &&
        !request.url().includes("/api/feedback")
      )
        outbound.push(request.postData() ?? "");
    });
    await page.goto("/feedback?from=footer");
    const message = "PRIVATE BROWSER CANARY " + crypto.randomUUID();
    await page.getByLabel("What would you like us to know?").fill(message);
    const responsePromise = page.waitForResponse(
      (r) =>
        r.url().endsWith("/api/feedback") && r.request().method() === "POST",
    );
    await page.getByRole("button", { name: "Send message" }).click();
    const response = await responsePromise;
    expect(response.status()).toBe(201);
    const receipt = (await response.json()).receipt;
    await expect(
      page.getByRole("heading", { name: "Thanks. Your message reached us." }),
    ).toBeVisible();
    await expect(page.getByRole("status")).toContainText(receipt);
    const retry = await page.evaluate(
      async ({ body }) => {
        const r = await fetch("/api/feedback", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body,
        });
        return { status: r.status, value: await r.json() };
      },
      { body: response.request().postData()! },
    );
    expect(retry).toEqual({ status: 200, value: { receipt } });
    expect(outbound.join("\n")).not.toContain(message);
    expect(await page.evaluate(() => ({ ...localStorage }))).toEqual({});
  });
  test("errors retain drafts, identity rotates on edits, and approval interest requires email", async ({
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
    const ids: string[] = [];
    let status = 429;
    await page.route("**/api/feedback", async (route) => {
      ids.push(route.request().postDataJSON().requestId);
      await route.fulfill({
        status,
        headers: { "Content-Type": "application/json", "Retry-After": "60" },
        body: JSON.stringify({
          error: status === 429 ? "limited" : "unavailable",
        }),
      });
    });
    await page.getByRole("button", { name: "Send message" }).click();
    await expect(page.locator("main").getByRole("alert")).toContainText(
      "1 minutes",
    );
    status = 503;
    await page.getByRole("button", { name: "Send message" }).click();
    await expect(page.locator("main").getByRole("alert")).toContainText(
      "We couldn't send your message",
    );
    expect(ids[1]).toBe(ids[0]);
    await expect(page.getByLabel("How are you using the data?")).toHaveValue(
      "A private research notebook",
    );
    await page
      .getByLabel("How are you using the data?")
      .fill("Changed private notebook");
    await page.getByRole("button", { name: "Send message" }).click();
    await expect.poll(() => ids.length).toBe(3);
    expect(ids[2]).not.toBe(ids[0]);
    // A dropped response preserves the edited draft and uses fixed timeout copy.
    await page.unroute("**/api/feedback");
    await page.route("**/api/feedback", (route) => route.abort("timedout"));
    await page.getByRole("button", { name: "Send message" }).click();
    await expect(page.locator("main").getByRole("alert")).toContainText(
      "couldn't confirm whether your message arrived",
    );
    await expect(page.getByLabel("How are you using the data?")).toHaveValue(
      "Changed private notebook",
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
});
