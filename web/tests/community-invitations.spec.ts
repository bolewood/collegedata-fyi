import { expect, test } from "@playwright/test";

test("usage references have sources and keep stats separate from stories", async ({
  page,
}) => {
  await page.goto("/usage");
  await expect(
    page.getByRole("heading", { name: "How are you using the data?" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Share how you use it", exact: true }),
  ).toHaveAttribute("href", "/feedback?from=usage&kind=story");
  await expect(
    page.getByRole("heading", { name: "Projects using the data" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Supporting source" }),
  ).toHaveCount(4);
  await expect(
    page.getByRole("heading", { name: "Stories shared with us" }),
  ).toHaveCount(0);
  await expect(
    page.getByRole("link", { name: "Star on GitHub" }),
  ).toHaveAttribute("href", "https://github.com/bolewood/collegedata-fyi");
  await expect(
    page.getByRole("link", { name: "Feedback", exact: true }),
  ).toHaveAttribute("href", "/feedback?from=footer&kind=feedback");
});
test("API invitation uses a story link without requiring an account", async ({
  page,
}) => {
  await page.goto("/api");
  await expect(
    page.getByRole("heading", { name: "Building something with this data?" }),
  ).toBeVisible();
  await expect(
    page.getByRole("link", { name: "Tell us what you're building" }),
  ).toHaveAttribute("href", "/feedback?from=api&kind=story");
});
test("school and report invitations carry only safe school and year context", async ({
  page,
}) => {
  await page.goto("/schools/mit");
  await expect(
    page.getByRole("link", { name: "Found a problem? Send feedback" }),
  ).toHaveAttribute("href", "/feedback?from=school&kind=data_issue&school=mit");
  await page.goto("/schools/mit/2024-25");
  await expect(
    page.getByRole("link", { name: "Found a problem? Send feedback" }),
  ).toHaveAttribute(
    "href",
    "/feedback?from=school_year&kind=data_issue&school=mit&year=2024-25",
  );
});
