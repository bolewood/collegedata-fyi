import type { ReactElement, ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { COVERAGE_CSV_LICENSED_LEAD, buildCoverageCsv, coverageViewRows } from "@/lib/coverage-model";
import { DATA_LICENSE_URL } from "@/lib/data-license";
import { setLaunchGate } from "@/lib/__fixtures__/data-quality-gate";
import { CSV_BOM } from "@/lib/data-quality";
import type { InstitutionCoverage } from "@/lib/types";

let currentParams = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useSearchParams: () => currentParams,
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/coverage",
}));

import { CoverageDashboard } from "./CoverageDashboard";
import { CoverageDownloads } from "./CoverageDownloads";

// Records the props the dashboard hands to the buttons, then renders the real thing.
const seen = vi.hoisted(() => ({ props: null as null | { viewRows: unknown[]; allRows: unknown[] } }));
vi.mock("./CoverageDownloads", async (importOriginal) => {
  const real = await importOriginal<typeof import("./CoverageDownloads")>();
  return {
    ...real,
    CoverageDownloads: (props: { viewRows: unknown[]; allRows: unknown[] }) => {
      seen.props = props;
      return real.CoverageDownloads(props as never);
    },
  };
});

// The sort lives in dashboard state and can't be clicked in a static render, so start it on a
// non-default sort: the dashboard's two sort useState calls start at "name" and "asc".
const sortStart = vi.hoisted(() => ({ on: false }));
vi.mock("react", async (importOriginal) => {
  const real = await importOriginal<typeof import("react")>();
  return {
    ...real,
    useState: ((init: unknown) =>
      real.useState(sortStart.on && init === "name" ? "enrollment" : sortStart.on && init === "asc" ? "desc" : init)) as typeof real.useState,
  };
});

function row(over: Partial<InstitutionCoverage> & { school_id: string; school_name: string }): InstitutionCoverage {
  return {
    ipeds_id: "100000",
    city: null,
    state: "NY",
    website_url: null,
    undergraduate_enrollment: 1000,
    coverage_status: "no_public_cds_found",
    coverage_label: "",
    coverage_summary: "",
    latest_available_cds_year: null,
    latest_found_cds_year: null,
    last_checked_at: "2026-11-20T00:00:00Z",
    can_submit_source: false,
    ...over,
  };
}

const ROWS = [
  row({ school_id: "a", school_name: "Alpha College", undergraduate_enrollment: 500 }),
  row({ school_id: "b", school_name: 'St. John\'s, "Great Books" College', undergraduate_enrollment: 9000, state: "NM" }),
  row({ school_id: "c", school_name: "Universidad de Río Piedras", undergraduate_enrollment: null, state: "PR" }),
  row({ school_id: "d", school_name: "Delta Tech", undergraduate_enrollment: 2000, coverage_status: "cds_available_current", latest_available_cds_year: "2025-26", latest_found_cds_year: "2025-26" }),
];

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  sortStart.on = false;
  seen.props = null;
  currentParams = new URLSearchParams();
});

/** Find the onClick of the button whose text starts with `label`, in an element tree. */
function clickHandler(node: ReactNode, label: string): (() => void) | null {
  if (!node || typeof node !== "object") return null;
  if (Array.isArray(node)) {
    for (const n of node) {
      const f = clickHandler(n, label);
      if (f) return f;
    }
    return null;
  }
  const el = node as ReactElement<{ children?: ReactNode; onClick?: () => void }>;
  const kids = el.props?.children;
  if (el.type === "button" && el.props.onClick && String(Array.isArray(kids) ? kids.join("") : kids).startsWith(label)) {
    return el.props.onClick;
  }
  return clickHandler(kids, label);
}

/** Click a download button with the browser's file-saving calls stubbed; return what was saved. */
async function download(el: ReactElement, label: string) {
  let blob: Blob | null = null;
  const link = { href: "", download: "", click: vi.fn() };
  vi.spyOn(URL, "createObjectURL").mockImplementation((b) => ((blob = b as Blob), "blob:x"));
  vi.spyOn(URL, "revokeObjectURL").mockImplementation(() => {});
  vi.stubGlobal("document", { createElement: () => link, body: { appendChild: vi.fn() } });
  (link as unknown as { remove: () => void }).remove = vi.fn();
  const handler = clickHandler(el, label);
  expect(handler).not.toBeNull();
  handler!();
  const text = new TextDecoder("utf-8", { ignoreBOM: true }).decode(await blob!.arrayBuffer());
  return { text, filename: link.download };
}

describe("coverage CSV buttons", () => {
  it("'this view' saves exactly the table's rows, in the table's order, with a BOM and the header on row 1", async () => {
    const view = coverageViewRows(ROWS, "all=1&state=NY", "enrollment", "desc");
    expect(view.map((r) => r.school_id)).toEqual(["d", "a"]);
    const { text, filename } = await download(CoverageDownloads({ viewRows: view, allRows: ROWS }) as ReactElement, "Download this view");
    expect(text).toBe(CSV_BOM + buildCoverageCsv(view));
    expect(text.slice(1).startsWith("ipeds_id,school_id,school_name,")).toBe(true);
    expect(text.split("\r\n").filter(Boolean)).toHaveLength(1 + view.length);
    expect(filename).toMatch(/^quadfile-coverage-view-\d{4}-\d{2}-\d{2}\.csv$/);
  });

  it("'all colleges' saves every row and is the only one named all-colleges", async () => {
    const view = coverageViewRows(ROWS, "all=1&state=NM", "name", "asc");
    const { text, filename } = await download(CoverageDownloads({ viewRows: view, allRows: ROWS }) as ReactElement, "Download all colleges");
    expect(text.split("\r\n").filter(Boolean)).toHaveLength(1 + ROWS.length);
    expect(filename).toMatch(/^quadfile-coverage-all-colleges-/);
  });

  it("round-trips a name with a comma and a quote", async () => {
    const { text } = await download(CoverageDownloads({ viewRows: ROWS, allRows: ROWS }) as ReactElement, "Download this view");
    expect(text).toContain('"St. John\'s, ""Great Books"" College"');
    expect(text).toContain("Universidad de Río Piedras");
  });

  it("says which columns are federal, links the license, and defines the year columns", () => {
    const html = renderToStaticMarkup(<CoverageDownloads viewRows={[]} allRows={[]} />);
    expect(html).toContain("College Scorecard and IPEDS, which our license doesn");
    expect(html).toContain(`href="${DATA_LICENSE_URL}"`);
    // Small sentence-case text like the /data-quality licence line, not the uppercase .meta label, and it carries the credit.
    expect(html).toContain("Credit Quadfile.");
    expect(html).not.toContain('class="meta"');
    expect(html).toContain("latest_year_found is the latest year of any file we hold");
    // The licensed sentence names only our columns, and links the license.
    const licensed = html.match(/The school ID[^<]*<a [^>]*>[^<]*<\/a>/)?.[0] ?? "";
    expect(licensed).toContain(`${COVERAGE_CSV_LICENSED_LEAD} <a href="${DATA_LICENSE_URL}"`);
    expect(licensed).toContain(">CC BY 4.0</a>");
    expect(licensed).not.toMatch(/IPEDS|name|state|enrollment/i);
  });

  it("is on the page only after launch", () => {
    setLaunchGate(false);
    expect(renderToStaticMarkup(<CoverageDashboard rows={ROWS} />)).not.toContain("(CSV)");
    setLaunchGate(true);
    expect(renderToStaticMarkup(<CoverageDashboard rows={ROWS} />)).toContain("Download this view (CSV)");
  });

  it("the dashboard hands its own filtered, sorted rows to 'this view' and every row to 'all colleges'", async () => {
    setLaunchGate(true);
    sortStart.on = true; // sorted by undergraduates, largest first
    currentParams = new URLSearchParams("all=1&state=NY");
    const html = renderToStaticMarkup(<CoverageDashboard rows={ROWS} />);
    expect(html).toContain("SHOWING 2 OF 4 INSTITUTIONS");
    const props = seen.props!;
    const ids = (text: string) => text.slice(1).split("\r\n").filter(Boolean).slice(1).map((l) => l.split(",")[1]);

    const view = await download(CoverageDownloads(props as never) as ReactElement, "Download this view");
    expect(ids(view.text)).toEqual(["d", "a"]); // NY only, 2,000 before 500: not the row order, not name order
    const all = await download(CoverageDownloads(props as never) as ReactElement, "Download all colleges");
    expect(ids(all.text)).toEqual(["a", "b", "c", "d"]);
  });

});
