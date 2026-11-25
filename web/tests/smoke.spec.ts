import { expect, test, type Page, type Request } from "@playwright/test";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { TABLE_TITLES, hasFederalChecks, hasSections, type QualityTableId } from "../src/lib/data-quality";
import { loadLatestSnapshot } from "../src/lib/data-quality-snapshots";

function isSchoolPagePrefetch(req: Request): boolean {
  let url: URL;
  try {
    url = new URL(req.url());
  } catch {
    return false;
  }
  if (!/^\/schools\/.+/.test(url.pathname)) return false;
  if (req.resourceType() === "document") return false;
  const headers = req.headers();
  return (
    headers["next-router-prefetch"] === "1" ||
    headers["rsc"] === "1" ||
    url.searchParams.has("_rsc")
  );
}

async function schoolPrefetchesDuring(
  page: Page,
  run: () => Promise<void>,
): Promise<string[]> {
  const paths: string[] = [];
  const onRequest = (req: Request) => {
    if (isSchoolPagePrefetch(req)) {
      paths.push(new URL(req.url()).pathname);
    }
  };
  page.on("request", onRequest);
  try {
    await run();
  } finally {
    page.off("request", onRequest);
  }
  return paths;
}

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
    .getByPlaceholder(/Search any U\.S\. college by name or city/i)
    .fill("Rice");
  const result = page.getByText("Rice University").first();
  await expect(result).toBeVisible();
  await result.click();

  await expect(page).toHaveURL(/\/schools\/rice/);
  await expect(
    page.getByRole("heading", { name: "Rice University", exact: true, level: 1 }),
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
    page.getByRole("heading", { name: /Archive coverage/i }),
  ).toBeVisible();
  await expect(page.getByText("No public CDS found").first()).toBeVisible();
  await expect(page.getByText("Methodology")).toBeVisible();
});

// PRD 040 launch gate, decided once per build in next.config.ts and inlined as
// env.DATA_QUALITY_LAUNCHED. The built server is the thing under test, so the
// expected state is read from that build's own output, `.next/required-server-files.json`
// (config.env), which Next writes at `next build`. It is not recomputed from the
// date at test time, so a build made before midnight and tested after still
// matches. `next dev` writes no such file: run these against `next build` +
// `next start` (CI does). With PLAYWRIGHT_BASE_URL, point it at the matching build.
function builtGate(): boolean {
  const file = resolve(__dirname, "../.next/required-server-files.json");
  let value: unknown;
  try {
    value = JSON.parse(readFileSync(file, "utf8")).config?.env?.DATA_QUALITY_LAUNCHED;
  } catch {
    throw new Error(`Cannot read the built launch gate from ${file}. Run \`next build\` and test against \`next start\`.`);
  }
  if (value !== "0" && value !== "1") throw new Error(`DATA_QUALITY_LAUNCHED in ${file} is ${JSON.stringify(value)}, expected "0" or "1".`);
  return value === "1";
}

// A year with federal figures, so the page shows every table and its CSV link (2025-26 has no federal table yet).
const dqYearRow = loadLatestSnapshot().years.find((y) => y.federal_fall_loaded)!;
const dqYear = dqYearRow.cds_year;
// The tables the page links for that year: the same rules the page and the CSV route use, not a hand-kept list.
const CSV_TABLES = (Object.keys(TABLE_TITLES) as QualityTableId[]).filter((t) =>
  t === "sections" ? hasSections(dqYearRow) : t === "enrollment" || t === "tuition" ? hasFederalChecks(dqYearRow) : true,
);

test.describe("Data quality gate (matches the build)", () => {
  let launched = false;
  test.beforeAll(() => {
    launched = builtGate();
  });

  test("/coverage tab, CSV buttons and nav label", async ({ page }) => {
    const res = await page.goto("/coverage");
    expect(res?.status()).toBe(200);
    // The header is there in both states; only the Data quality tab depends on the gate.
    const header = page.getByRole("navigation", { name: "Archive status" });
    await expect(header).toBeVisible();
    await expect(header.getByRole("link", { name: "Coverage by school" })).toBeVisible();
    await expect(header.getByRole("link", { name: "Data quality" })).toHaveCount(launched ? 1 : 0);
    await expect(page.getByRole("button", { name: /\(CSV\)/ })).toHaveCount(launched ? 2 : 0);
    // The More menu is a closed <details>, so its links are in the markup but not in the accessibility tree.
    const labels = (await page.locator('nav a[href="/coverage"], footer a[href="/coverage"]').allTextContents())
      .map((t) => t.trim())
      .filter((t) => !t.startsWith("Coverage by"));
    expect(labels.length).toBeGreaterThanOrEqual(2);
    for (const t of labels) expect(t).toBe(launched ? "Archive status" : "Coverage");
  });

  test("/data-quality page: indexing, canonical and CSV links", async ({ page, request }) => {
    const res = await page.goto(`/data-quality?year=${dqYear}`);
    expect(res?.status()).toBe(200);
    await expect(page.getByRole("heading", { name: "Data quality", level: 1 })).toBeVisible();
    const robots = await page.evaluate(() => document.querySelector('meta[name="robots"]')?.getAttribute("content") ?? null);
    const canonical = await page.evaluate(() => document.querySelector('link[rel="canonical"]')?.getAttribute("href") ?? null);
    expect(canonical).toMatch(/\/data-quality$/);
    const links = page.locator('a[href^="/data-quality/csv/"]');
    if (launched) {
      expect(robots).toBeNull();
      await expect(links).toHaveCount(CSV_TABLES.length);
      const hrefs = await links.evaluateAll((as) => as.map((a) => a.getAttribute("href")!));
      expect(hrefs.map((h) => h.split("/")[3]).sort()).toEqual([...CSV_TABLES].sort());
      for (const href of hrefs) {
        const csv = await request.get(href);
        expect(csv.status(), href).toBe(200);
        expect(csv.headers()["link"], href).toContain('rel="license"');
      }
    } else {
      expect(robots).toMatch(/noindex/);
      await expect(links).toHaveCount(0);
    }
  });

  test("CSV routes", async ({ request }) => {
    for (const table of CSV_TABLES) {
      const res = await request.get(`/data-quality/csv/${table}/${dqYear}`);
      expect(res.status(), table).toBe(launched ? 200 : 404);
      if (launched) expect(res.headers()["link"], table).toContain('rel="license"');
    }
  });

  test("reports route", async ({ request }) => {
    const day = loadLatestSnapshot().snapshot_of.slice(0, 10);
    const res = await request.get(`/data-quality/reports/${day}`);
    expect(res.status()).toBe(launched ? 200 : 404);
    if (launched) expect(res.headers()["link"]).toContain('rel="license"');
  });

  test("sitemap and methodology", async ({ request }) => {
    test.setTimeout(120_000);
    const sitemap = await request.get("/sitemap.xml", { timeout: 100_000 });
    expect(sitemap.status()).toBe(200);
    expect(/<loc>[^<]*\/data-quality<\/loc>/.test(await sitemap.text())).toBe(launched);
    const methodology = await request.get("/methodology");
    expect(methodology.status()).toBe(200);
    expect((await methodology.text()).includes('href="/data-quality"')).toBe(launched);
  });
});

test("browser loads live rows and source links resolve", async ({ page, request }) => {
  await page.goto("/browse");
  await expect(
    page.getByRole("heading", { name: /Compare schools/i }),
  ).toBeVisible();
  await expect(page.getByText("Couldn't load")).toHaveCount(0);
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

test("hosted MCP Streamable HTTP handshake and search", async ({ request }) => {
  const probe = await request.get("/api/mcp");
  expect(probe.ok()).toBeTruthy();
  const descriptor = await probe.json();
  expect(descriptor.transport).toBe("streamable-http");
  expect(descriptor.tools).toEqual([
    "search_schools",
    "get_school_facts",
    "compare_schools",
    "get_source_documents",
    "get_field_dictionary",
  ]);

  const init = await request.post("/api/mcp", {
    headers: {
      Accept: "application/json, text/event-stream",
      "Content-Type": "application/json",
    },
    data: {
      jsonrpc: "2.0",
      id: 0,
      method: "initialize",
      params: {
        protocolVersion: "2025-03-26",
        capabilities: {},
        clientInfo: { name: "playwright", version: "test" },
      },
    },
  });
  expect(init.ok()).toBeTruthy();
  const initBody = await init.json();
  expect(initBody.result.serverInfo.name).toBe("collegedata-fyi");
  expect(initBody.result.capabilities.tools).toBeTruthy();

  const listed = await request.post("/api/mcp", {
    data: { jsonrpc: "2.0", id: 1, method: "tools/list" },
  });
  expect(listed.ok()).toBeTruthy();
  const listedBody = await listed.json();
  expect(listedBody.result.tools.map((tool: { name: string }) => tool.name)).toEqual(
    descriptor.tools,
  );

  const search = await request.post("/api/mcp", {
    data: {
      jsonrpc: "2.0",
      id: 2,
      method: "tools/call",
      params: { name: "search_schools", arguments: { query: "Carleton College" } },
    },
  });
  expect(search.ok()).toBeTruthy();
  const searchBody = await search.json();
  expect(searchBody.result.isError).toBeFalsy();
  expect(searchBody.result.content[0].text).toMatch(/carleton-college/i);
});

test("school-year page renders reconstructed CDS tables", async ({ page }) => {
  await page.goto("/schools/bowdoin/2024-25");
  await expect(
    page.getByRole("heading", { name: "Bowdoin College 2024-25 Common Data Set", exact: true, level: 1 }),
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

test("scrolling /schools does not viewport-prefetch school pages", async ({ page }) => {
  const paths = await schoolPrefetchesDuring(page, async () => {
    await page.goto("/schools");
    await expect(page.getByRole("heading", { name: "Schools", exact: true })).toBeVisible();
    await expect(page.locator("table a").first()).toBeVisible();
    for (let i = 0; i < 20; i++) {
      await page.evaluate(() => window.scrollBy(0, 800));
      await page.waitForTimeout(80);
    }
    await page.waitForTimeout(400);
  });
  expect(paths, `unexpected school prefetches: ${[...new Set(paths)].slice(0, 8).join(", ")}`).toEqual([]);
});

test("opening a school hub does not prefetch every year page", async ({ page }) => {
  const paths = await schoolPrefetchesDuring(page, async () => {
    await page.goto("/schools/carnegie-mellon");
    await expect(page.getByRole("heading", { name: /Carnegie Mellon/ })).toBeVisible();
    await page.waitForTimeout(800);
  });
  const uniqueYears = [
    ...new Set(paths.filter((path) => /\/schools\/carnegie-mellon\/\d{4}-\d{2}$/.test(path))),
  ];
  // Latest-year ribbon links may still prefetch once. The WAF failure was
  // every archived year (1999-00 through 2012-13) at once.
  expect(uniqueYears.length, `year prefetches: ${uniqueYears.join(", ")}`).toBeLessThanOrEqual(2);
  expect(uniqueYears.some((path) => /\/19\d{2}-\d{2}$/.test(path))).toBe(false);
});

test("mobile launch surfaces do not overflow", async ({ page, isMobile }) => {
  test.skip(!isMobile, "mobile project only");

  for (const path of ["/", "/coverage", "/browse", "/schools/bowdoin/2024-25"]) {
    await page.goto(path);
    await expectNoBodyOverflow(page);
  }
});
