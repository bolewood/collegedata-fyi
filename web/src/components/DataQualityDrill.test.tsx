import fs from "node:fs";
import path from "node:path";
import { buildTrend } from "@/lib/data-quality-trend";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FIXTURE_SNAPSHOT, FIXTURE_SNAPSHOT_V3 } from "@/lib/__fixtures__/data-quality-snapshot";
import { setLaunchGate } from "@/lib/__fixtures__/data-quality-gate";
import type { QualitySnapshot } from "@/lib/data-quality";
import { cellLabel, snapshotCells, type CellRef, type ReportsFile } from "@/lib/data-quality-reports";
import { DrillPanelView, cachedReports, loadReports } from "./DataQualityDrill";

let currentParams = new URLSearchParams();
// These tests render the page as the browser shows it after hydration, when ?year= is read.
vi.mock("@/lib/use-hydrated", () => ({ useHydrated: () => true }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => currentParams,
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/data-quality",
}));

import { DataQualityView } from "./DataQualityView";

afterEach(() => {
  currentParams = new URLSearchParams();
});

function render(year: string, reportsUrl: string | null, snapshot: QualitySnapshot = FIXTURE_SNAPSHOT) {
  currentParams = new URLSearchParams(`year=${year}`);
  setLaunchGate(true);
  return renderToStaticMarkup(<DataQualityView snapshot={snapshot} trend={buildTrend([snapshot])} reportsUrl={reportsUrl} />);
}

const buttons = (html: string) => [...html.matchAll(/<button type="button" class="dq-count" aria-expanded="false" aria-label="([^"]*)">([^<]*)<\/button>/g)].map((m) => ({ label: m[1].replace(/&#x27;|&#39;/g, "'"), text: m[2] }));

describe("count buttons", () => {
  it("make every count above zero a button, in every table, and nothing else (every year of the fixture)", () => {
    for (const year of FIXTURE_SNAPSHOT.years) {
      const html = render(year.cds_year, "/data-quality/reports/2026-11-24");
      const expected = snapshotCells(FIXTURE_SNAPSHOT).filter((c) => c.year === year.cds_year && c.count > 0);
      expect(buttons(html), year.cds_year).toHaveLength(expected.length);
      expect(html.match(/class="dq-count"/g) ?? []).toHaveLength(expected.length);
    }
  });

  it("name each button for how many, which reports and what, with the year, and show the number as its text", () => {
    const html = render("2023-24", "/x");
    const names = buttons(html);
    const byLabel = new Map(names.map((b) => [b.label, b.text]));
    // Hand-written from the fixture (2023-24 standard PDF: 300 published, 4 couldn't read, 3 set aside).
    expect(byLabel.get("List the 300 standard PDF reports published (2023-24)")).toBe("300");
    expect(byLabel.get("List the 4 standard PDF reports that couldn’t be read (2023-24)")).toBe("4");
    expect(byLabel.get("List the 3 standard PDF reports set aside (2023-24)")).toBe("3");
    expect(byLabel.get("List the 75 standard PDF reports where the financial aid table adds up (2023-24)")).toBe("75");
    expect(byLabel.get("List the 269 standard PDF reports checked against federal tuition figures (2023-24)")).toBe("269");
    expect(byLabel.get("List the 22 tuition values that differ by over 10%, from standard PDF reports (2023-24)")).toBe("22");
    // Every name starts the same way, names a format or all formats, and ends with the year.
    for (const { label } of names) expect(label).toMatch(/^List the [\d,]+ .*\(2023-24\)$/);
    // The visible number is the number in the name.
    for (const { label, text } of names) expect(label.startsWith(`List the ${text} `)).toBe(true);
  });

  it("leave a count of 0 as plain text, and are not buttons without a reports file (the server decides, not the browser's clock)", () => {
    const html = render("2024-25", "/x");
    // The fixture's 2024-25 tuition table is not loaded (dashes); a zero count never becomes a button.
    expect(buttons(html).filter((b) => b.text === "0")).toEqual([]);
    expect(html).not.toMatch(/aria-label="List the 0 /);
    expect(render("2024-25", null)).not.toContain("dq-count");
    // A count is a button whatever the gate says: the page decides by passing a reports URL or not.
    for (const launched of [false, true]) {
      setLaunchGate(launched);
      currentParams = new URLSearchParams("year=2023-24");
      expect(renderToStaticMarkup(<DataQualityView snapshot={FIXTURE_SNAPSHOT} trend={buildTrend([FIXTURE_SNAPSHOT])} reportsUrl="/x" />)).toContain("dq-count");
    }
  });

  it("are real buttons that say whether their list is open and control no panel until it is", () => {
    const html = render("2023-24", "/x");
    for (const m of html.matchAll(/<button type="button" class="dq-count"[^>]*>/g)) {
      expect(m[0]).toContain('aria-expanded="false"');
      expect(m[0]).not.toContain("aria-controls");
      expect(m[0]).toMatch(/aria-label="List the /);
    }
    expect(html).not.toContain('class="dq-drill"');
  });

  it("works for snapshots from before the new tables (older formats have fewer cells, same rules)", () => {
    const html = render("2024-25", "/x", FIXTURE_SNAPSHOT_V3);
    const expected = snapshotCells(FIXTURE_SNAPSHOT_V3).filter((c) => c.year === "2024-25" && c.count > 0);
    expect(buttons(html)).toHaveLength(expected.length);
  });
});

const HAND: ReportsFile = {
  reports_format: 1, snapshot_of: "2026-11-25T00:00:00Z", scoreboard_run: "x.json", codes: {},
  schools: { alpha: "Alpha College", beta: "Beta University" },
  years: {
    "2024-25": [
      { id: "a", school: "alpha", format: "pdf_flat", status: "published", fed: ["m", "l", null], sums: ["adds_up", "off_more", "doesnt"], checks: ["s", null] },
      { id: "b", school: "beta", format: "xlsx", status: "published", fed: ["l", "l", "n"], sums: ["adds_up", "adds_up", "adds_up"], checks: [null, "m"] },
      { id: "doc-9", school: null, format: "pdf_flat", status: "couldnt_read" },
    ],
  },
};
const cell = (table: CellRef["table"], column: string, row = "total"): CellRef => ({ table, row, column });
const view = (c: CellRef, count: number, load: Parameters<typeof DrillPanelView>[0]["load"]) =>
  renderToStaticMarkup(<DrillPanelView cell={c} year="2024-25" count={count} load={load} onClose={() => {}} onRetry={() => {}} />);

describe("the list", () => {
  it("is a labelled region that takes focus, with a heading, a Close button and the reports as links to school pages", () => {
    const html = view(cell("federal", "differs_over_10pct"), 3, { status: "ready", reports: HAND });
    expect(html).toContain('role="region"');
    expect(html).toContain('aria-labelledby="dq-drill-federal-heading"');
    expect(html).toContain('tabindex="-1"');
    expect(html).toContain('id="dq-drill-federal-heading"');
    expect(html).toContain("3 admissions values that differ by over 10%, from reports in all formats (2024-25)");
    expect(html).toMatch(/<button type="button"[^>]*>Close<\/button>/);
    expect(html).toContain('<a href="/schools/alpha/2024-25">Alpha College</a>');
    expect(html).toContain('<a href="/schools/beta/2024-25">Beta University</a>');
    // The note counts reports and values, because a report can hold up to three values.
    expect(html).toContain("2 reports, 3 values (a report can hold up to three). Press Escape to close.");
    expect(html).toContain("2 values");
    expect(html).toContain("applied: matches; admitted: differs by over 10%");
  });

  it("says 'report' for one, lists a report with no school without a link, and names its document", () => {
    const html = view(cell("status", "couldnt_read"), 1, { status: "ready", reports: HAND });
    expect(html).toContain("1 report. Press Escape to close.");
    expect(html).toContain("School not recorded in this run");
    expect(html).toContain("document doc-9");
    expect(html).not.toContain("<a ");
  });

  it("shows a polite loading state and an error with a way to try again", () => {
    expect(view(cell("status", "published"), 2, { status: "loading" })).toContain('<div role="status" class="dq-drill-note">Loading the list…</div>');
    const error = view(cell("status", "published"), 2, { status: "error", message: "HTTP 500" });
    expect(error).toContain('role="alert"');
    expect(error).toContain("We couldn’t load the list (HTTP 500).");
    expect(error).toMatch(/<button type="button" class="dq-drill-link">Try again<\/button>/);
    expect(error).not.toContain("<ul");
  });

  it("matches the label of the button that opens it, minus 'List the'", () => {
    const c = cell("totals", "H1.adds_up", "pdf_flat");
    const html = view(c, 46, { status: "ready", reports: HAND });
    expect(cellLabel(c, "2024-25", 46)).toBe("List the 46 standard PDF reports where the financial aid table adds up (2024-25)");
    expect(html).toContain("46 standard PDF reports where the financial aid table adds up (2024-25)");
  });
});

describe("the list's rows and accessibility", () => {
  const rowsOf = (html: string) => [...html.matchAll(/<li>([\s\S]*?)<\/li>/g)].map((m) => m[1]);
  const file = (rows: ReportsFile["years"][string], schools: ReportsFile["schools"]): ReportsFile => ({ ...HAND, schools, years: { "2024-25": rows } });
  const cd = (id: string, school: string | null, extra: object = {}) => ({ id, school, format: "pdf_flat" as const, status: "set_aside" as const, ...extra });

  it("links a school only where its year page exists: a row with no page is named, not linked, and says so", () => {
    const f = file([cd("1", "alpha"), cd("2", "beta", { nopage: true as const })], { alpha: "Alpha College", beta: "Beta University" });
    const [linked, unlinked] = rowsOf(view(cell("status", "set_aside"), 2, { status: "ready", reports: f }));
    expect(linked).toContain('<a href="/schools/alpha/2024-25">Alpha College</a>');
    expect(unlinked).not.toContain("<a ");
    expect(unlinked).toContain("Beta University");
    expect(unlinked).toContain("no school page for this year");
  });

  it("never renders an empty link: a school the file lacks is shown by its id, unlinked or linked with text", () => {
    const f = file([cd("1", "ghost")], {});
    const [item] = rowsOf(view(cell("status", "set_aside"), 1, { status: "ready", reports: f }));
    expect(item).toContain(">ghost<");
    expect(item).not.toMatch(/<a [^>]*><\/a>/);
  });

  it("tells two documents of one school and year apart, with the id in a title", () => {
    const f = file([cd("doc-a", "alpha"), cd("doc-b", "alpha", { format: "xlsx" }), cd("doc-c", "beta")], { alpha: "Alpha College", beta: "Beta University" });
    const items = rowsOf(view(cell("status", "set_aside"), 3, { status: "ready", reports: f }));
    expect(items[0]).toContain("document 1 of 2");
    expect(items[0]).toContain('title="document doc-a"');
    expect(items[1]).toContain("document 2 of 2");
    expect(items[1]).toContain('title="document doc-b"');
    expect(items[2]).not.toContain("document 1 of");
    expect(items[2]).not.toContain("title=");
  });

  it("keeps one live status region in every state, so a change from loading to the count is announced", () => {
    for (const load of [{ status: "loading" }, { status: "ready", reports: HAND }, { status: "error", message: "x" }] as const) {
      expect(view(cell("status", "published"), 2, load), load.status).toContain('<div role="status" class="dq-drill-note">');
    }
    expect(view(cell("status", "published"), 2, { status: "ready", reports: HAND })).toContain('<div role="status" class="dq-drill-note">2 reports');
  });

  it("makes the scrolling list keyboard-focusable and named, so it scrolls with the arrow keys in every browser", () => {
    const html = view(cell("status", "published"), 2, { status: "ready", reports: HAND });
    expect(html).toMatch(/<ul class="dq-drill-list" tabindex="0" aria-label="Reports in this list: 2 reports in all formats published \(2024-25\)">/);
  });

  it("uses the design system's card, not a raw colour", () => {
    expect(view(cell("status", "published"), 2, { status: "loading" })).toContain('class="dq-drill cd-card"');
    const css = fs.readFileSync(path.join(process.cwd(), "src/app/data-quality/data-quality.css"), "utf8");
    expect(css).not.toMatch(/#faf6ec/i);
    // Every control in the list shows the same forest focus ring, including the scrolling list itself.
    expect(css).toMatch(/\.dq-drill-list:focus-visible[^{]*\{ outline: 2px solid var\(--forest\)/);
  });
});

describe("loading the reports file", () => {
  const ok = (body: unknown) => vi.fn(async () => new Response(JSON.stringify(body), { status: 200 }));

  it("fetches once however many cells are opened, and checks what it got", async () => {
    const fetcher = ok(HAND);
    const a = await loadReports("/once", fetcher as unknown as typeof fetch);
    const b = await loadReports("/once", fetcher as unknown as typeof fetch);
    expect(a).toBe(b);
    expect(fetcher).toHaveBeenCalledTimes(1);
    expect(a.years["2024-25"]).toHaveLength(3);
  });

  it("remembers a loaded file so a later click can show it at once", async () => {
    const fetcher = ok(HAND);
    expect(cachedReports("/remembered")).toBeNull();
    await loadReports("/remembered", fetcher as unknown as typeof fetch);
    expect(cachedReports("/remembered")?.years["2024-25"]).toHaveLength(3);
  });

  it("is not fetched until asked: loading the module fetches nothing", () => {
    const fetcher = vi.fn();
    vi.stubGlobal("fetch", fetcher);
    try {
      render("2023-24", "/never");
      expect(fetcher).not.toHaveBeenCalled();
    } finally {
      vi.unstubAllGlobals();
    }
  });

  it("does not remember a failure, so Try again fetches again", async () => {
    const fail = vi.fn(async () => new Response("no", { status: 503 }));
    await expect(loadReports("/flaky", fail as unknown as typeof fetch)).rejects.toThrow("HTTP 503");
    const good = ok(HAND);
    await expect(loadReports("/flaky", good as unknown as typeof fetch)).resolves.toBeTruthy();
    expect(good).toHaveBeenCalledTimes(1);
  });

  it("refuses a file that is not a reports file", async () => {
    await expect(loadReports("/bad", ok({ nonsense: true }) as unknown as typeof fetch)).rejects.toThrow(/reports_format/);
  });
});

describe("the page's source", () => {
  it("does not import the reports file or the reports module's data into the page bundle", () => {
    const read = (f: string) => fs.readFileSync(path.join(process.cwd(), "src", f), "utf8");
    for (const f of ["components/DataQualityView.tsx", "components/DataQualityDrill.tsx", "app/data-quality/page.tsx"]) {
      expect(read(f), f).not.toMatch(/data\/data-quality\/reports|from ["'][^"']*\.json["']/);
    }
    // The client fetches a URL on a click; it has no reference to the file's path.
    expect(read("components/DataQualityDrill.tsx")).toMatch(/fetcher\(url\)/);
  });
});

