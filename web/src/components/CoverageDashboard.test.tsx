import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

let currentParams = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useSearchParams: () => currentParams,
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/coverage",
}));

import { FIXTURE_SNAPSHOT } from "@/lib/__fixtures__/data-quality-snapshot";
import { renewalTile } from "@/lib/data-quality";
import type { InstitutionCoverage } from "@/lib/types";
import { CoverageDashboard } from "./CoverageDashboard";

function row(over: Partial<InstitutionCoverage> & { school_id: string }): InstitutionCoverage {
  return {
    ipeds_id: "100000",
    school_name: over.school_id,
    city: null,
    state: "NY",
    website_url: null,
    undergraduate_enrollment: 1000,
    coverage_status: "cds_available_current",
    coverage_label: "CDS available",
    coverage_summary: "",
    latest_available_cds_year: "2025-26",
    latest_found_cds_year: "2025-26",
    last_checked_at: "2026-11-20T00:00:00Z",
    can_submit_source: false,
    ...over,
  };
}

const ROWS = [
  row({ school_id: "a", undergraduate_enrollment: 3000 }),
  row({ school_id: "b", undergraduate_enrollment: 1000, coverage_status: "extract_failed", coverage_label: "Extract failed", latest_available_cds_year: null }),
  row({ school_id: "c", undergraduate_enrollment: null, coverage_status: "not_checked", latest_available_cds_year: null }),
];

const RENEWAL = { renewal: FIXTURE_SNAPSHOT.renewal, snapshotOf: FIXTURE_SNAPSHOT.snapshot_of };

function render(search = "", renewal: typeof RENEWAL | null = RENEWAL) {
  currentParams = new URLSearchParams(search);
  return renderToStaticMarkup(<CoverageDashboard rows={ROWS} renewal={renewal} />);
}

afterEach(() => {
  currentParams = new URLSearchParams();
});

describe("renewal tile", () => {
  it("is the first tile in the strip and equals renewal.both over renewal.previous", () => {
    const html = render();
    const tile = renewalTile(FIXTURE_SNAPSHOT.renewal);
    expect(tile.share).toBeCloseTo(FIXTURE_SNAPSHOT.renewal.both / FIXTURE_SNAPSHOT.renewal.previous, 10);
    const at = html.indexOf('data-testid="renewal-tile"');
    expect(at).toBeGreaterThan(-1);
    // before every other tile of the strip
    expect(at).toBeLessThan(html.indexOf("Colleges tracked"));
    expect(at).toBeLessThan(html.indexOf('data-testid="weighted-share-tile"'));
    const body = html.slice(at, html.indexOf("Colleges tracked"));
    expect(body).toContain(`${tile.percent}%`);
    expect(body).toContain("Of the 479 schools with a 2024-25 report on file, 364 also have a 2025-26 report on file.");
    expect(body).toContain("Snapshot of November 24, 2026");
    // The label names the year the tile counts (this tile is public). The tile stays short: the definition of "on file" is not in it.
    expect(body).toContain("2025-26 reports on file");
    expect(body).not.toContain("This year");
    expect(body).not.toContain("The earlier-year count");
    expect(body.length).toBeLessThan(900);
    // It is a short note directly under the strip, in normal-case small text.
    const strip = html.indexOf('aria-label="Coverage summary"');
    const note = html.indexOf('data-testid="renewal-definition"');
    expect(note).toBeGreaterThan(html.indexOf('</section>', strip));
    expect(html.slice(note, note + 700).replace(/<[^>]*>/g, "")).toContain(
      "2025-26 reports on file: The earlier-year count includes any report we hold for that year, including ones we set aside or couldn’t read. A school counts as renewed only if its current-year report is one we have not set aside; a report we couldn’t read still counts.",
    );
    // The opening tag of the note itself: normal-case small text, never the `.meta` label style.
    const tag = html.slice(html.lastIndexOf("<p", note), html.indexOf(">", note) + 1);
    expect(tag.startsWith("<p ")).toBe(true);
    expect(tag).not.toMatch(/class(Name)?="[^"]*\bmeta\b/);
  });

  it("is left out, not shown as zero, when the dashboard is given no renewal block", () => {
    expect(render("", null)).not.toContain("renewal-tile");
    expect(render("", null)).not.toContain("renewal-definition");
  });
});

describe("summary strip", () => {
  it("shows the weighted share with null enrollments left out of both sums, and says how many", () => {
    const html = render();
    const at = html.indexOf('data-testid="weighted-share-tile"');
    const tile = html.slice(at, at + 900);
    // a has numbers: 3000 of (3000 + 1000) known enrollment = 75%
    expect(tile).toContain("75%");
    expect(tile).toContain("1 college has no enrollment figure");
  });

  it("says nothing about colleges with no enrollment figure when there are none", () => {
    currentParams = new URLSearchParams();
    const html = renderToStaticMarkup(<CoverageDashboard rows={ROWS.filter((r) => r.undergraduate_enrollment !== null)} renewal={RENEWAL} />);
    const at = html.indexOf('data-testid="weighted-share-tile"');
    const tile = html.slice(at, at + 900);
    expect(tile).toContain("with CDS numbers on file.");
    expect(tile).not.toContain("no enrollment figure");
    expect(tile).not.toContain("0 colleges");
    expect(render()).toContain("1 college has no enrollment figure and is left out of both sums.");
  });

  it("puts every tile at the top of its row (a stretched button would centre its content and drop its label)", () => {
    const html = render();
    const at = html.indexOf('aria-label="Coverage summary"');
    const tag = html.slice(html.lastIndexOf("<section", at), html.indexOf(">", at) + 1);
    expect(tag.startsWith("<section")).toBe(true);
    expect(tag).toMatch(/align-items:\s*start/);
    expect(tag).toMatch(/display:\s*grid/);
  });

  it("uses 'Colleges tracked' and plain status words", () => {
    const html = render();
    expect(html).toContain("Colleges tracked");
    expect(html).not.toContain("In-scope total");
    expect(html).toContain("Report couldn&#x27;t be read".replace("&#x27;", "’"));
    expect(html).not.toContain("Extract failed");
  });

  it("breaks the latest year with numbers into buckets", () => {
    const html = render();
    expect(html).toContain("Latest year with numbers");
    expect(html).toMatch(/2025-26 <strong[^>]*>1</);
    expect(html).toMatch(/2024-25 <strong[^>]*>0</);
    expect(html).toMatch(/None <strong[^>]*>2</);
  });
});

describe("filters bar", () => {
  it("offers the Has a CDS preset as a link", () => {
    expect(render()).toContain('href="/coverage?status=cds_available_current,cds_available_stale"');
  });

  it("marks the preset when its statuses are the active view", () => {
    expect(render("status=cds_available_current,cds_available_stale")).toMatch(/aria-current="true"[^>]*>Has a CDS</);
    expect(render()).not.toMatch(/aria-current="true"[^>]*>Has a CDS</);
  });

  it("labels ?all=1 as all tracked colleges", () => {
    expect(render("all=1")).toContain("Showing all tracked colleges");
    expect(render()).toContain("Showing missing only");
  });

  it("restores the search box from ?q= (back and forward)", () => {
    expect(render("q=alpha")).toMatch(/type="search"[^>]*value="alpha"/);
    expect(render("")).toMatch(/type="search"[^>]*value=""/);
  });

  it("shows the two year columns, and no CSV links before launch", () => {
    const html = render();
    expect(html).not.toContain("(CSV)");
    expect(html).toContain("With numbers");
    expect(html).toContain("Found");
  });
});

describe("copy invariants (VOICE.md)", () => {
  it("has no operator words and at most one em dash, even with empty state and enrollment cells", () => {
    currentParams = new URLSearchParams("all=1");
    const html = renderToStaticMarkup(
      <CoverageDashboard rows={[...ROWS, row({ school_id: "d", state: null, undergraduate_enrollment: null })]} renewal={RENEWAL} />,
    );
    const text = html.replace(/<[^>]*>/g, " ");
    expect(text).not.toMatch(/\b(extract(ed|or|ion|s)?|docling|tier ?\d?|drain(ed)?|manifest|projection|pipeline)\b/i);
    expect((html.match(/\u2014|&mdash;|&#8212;|&#x2014;/gi) ?? []).length).toBeLessThanOrEqual(1);
  });

  // Table rows are virtualized, so a static render doesn't reach their empty-cell glyphs. Read the source:
  // an em dash there would repeat in every row and break the one-per-page rule.
  it("writes no em dash in the dashboard source (empty cells use an en dash)", () => {
    expect(readFileSync(resolve(__dirname, "CoverageDashboard.tsx"), "utf8")).not.toMatch(/\u2014|&mdash;|&#8212;|&#x2014;/i);
  });
});
