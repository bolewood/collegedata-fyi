import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";

let currentParams = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useSearchParams: () => currentParams,
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  usePathname: () => "/data-quality",
}));

import { FIXTURE_SNAPSHOT } from "@/lib/__fixtures__/data-quality-snapshot";
import { DATA_LICENSE_NAME, DATA_LICENSE_URL } from "@/lib/data-license";
import {
  AID_CANT_CHECK_SAMPLE,
  DATA_QUALITY_LAUNCH_DATE,
  FEDERAL_DIFFERS_SAMPLE,
  aidCantCheckNote,
  federalDiffersNote,
} from "@/lib/data-quality";
import { secondaryNavLinks, isActive } from "@/lib/nav-links";
import { ArchiveStatusHeader, visibleArchiveTabs } from "./ArchiveStatusHeader";
import { DataQualityView, yearNotices } from "./DataQualityView";

function render(search = "") {
  currentParams = new URLSearchParams(search);
  return renderToStaticMarkup(<DataQualityView snapshot={FIXTURE_SNAPSHOT} />);
}

/** The text of one table's HTML, by its id. */
function table(html: string, id: string): string {
  const start = html.indexOf(`id="${id}"`);
  expect(start).toBeGreaterThan(-1);
  return html.slice(start, html.indexOf("</table>", start));
}

// A rendered rate: "(87%)" in Table C cells, ">87%<" in the match-rate cell.
const PCT = /\(\d+%\)|>\d+%</;

afterEach(() => {
  currentParams = new URLSearchParams();
});

describe("year selection", () => {
  it("defaults to the newest year and shows the year picker newest first", () => {
    const html = render();
    expect(html).toContain("Table A, 2025-26");
    const order = ["2025-26", "2024-25", "2023-24"].map((y) => html.indexOf(`/data-quality?year=${y}`));
    expect(order.every((i) => i > 0)).toBe(true);
    expect([...order].sort((a, b) => a - b)).toEqual(order);
  });

  it("follows ?year= (back and forward restore it from the URL)", () => {
    expect(render("year=2023-24")).toContain("Table A, 2023-24");
    expect(render("year=2024-25")).toContain("Table A, 2024-25");
    expect(render("year=nonsense")).toContain("Table A, 2025-26");
  });

  it("marks the selected year in the picker", () => {
    const html = render("year=2024-25");
    expect(html).toMatch(/aria-current="true"[^>]*>2024-25</);
  });
});

describe("notices", () => {
  it("shows the different-form-numbering notice only for a year that has it", () => {
    expect(render("year=2023-24")).toContain("numbered by a different year");
    expect(render("year=2024-25")).not.toContain("numbered by a different year");
  });

  it("explains the empty-federal year instead of showing zeros", () => {
    const html = render("year=2025-26");
    expect(html).toContain("No federal admissions figures for fall 2025 yet.");
    const b = table(html, "dq-table-b");
    // every data cell of every row is a dash
    const cells = [...b.matchAll(/<td[^>]*>([^<]*)</g)].map((m) => m[1]);
    expect(cells.length).toBeGreaterThan(0);
    expect(cells.every((c) => c === "–")).toBe(true);
    expect(yearNotices(FIXTURE_SNAPSHOT.years.find((y) => y.cds_year === "2024-25")!)).toEqual([]);
  });

  it("names an older form only for a year without a full field schema", () => {
    const year = { ...FIXTURE_SNAPSHOT.years[0], form: { ...FIXTURE_SNAPSHOT.years[0].form, full_field_schema: false } };
    expect(yearNotices(year)).toContain("Older form: tables mapped, not every question.");
    expect(render()).not.toContain("Older form");
  });
});

describe("small groups", () => {
  it("shows counts but no percentage for a format under 5 reports, and a rate for the others", () => {
    const html = render("year=2024-25");
    const c = table(html, "dq-table-c");
    // the spreadsheet row has 3 published reports
    const row = c.slice(c.indexOf("spreadsheet"), c.indexOf("</tr>", c.indexOf("spreadsheet")));
    expect(row).toContain(">3<");
    expect(row).not.toMatch(PCT);
    const flatRow = c.slice(c.indexOf("standard PDF"), c.indexOf("</tr>", c.indexOf("standard PDF")));
    expect(flatRow).toMatch(PCT);

    const b = table(html, "dq-table-b");
    const bRow = b.slice(b.indexOf("spreadsheet"), b.indexOf("</tr>", b.indexOf("spreadsheet")));
    expect(bRow).not.toMatch(PCT);
    expect(b.slice(b.indexOf("standard PDF"), b.indexOf("</tr>", b.indexOf("standard PDF")))).toMatch(PCT);
  });

  it("always shows the year total in full", () => {
    const c = table(render("year=2024-25"), "dq-table-c");
    const total = c.slice(c.indexOf("All formats"));
    expect(total).toMatch(PCT);
  });
});

describe("tables", () => {
  it("lists every format under its public label and never an internal key", () => {
    const html = render("year=2023-24");
    expect(html).toContain("standard PDF");
    expect(html).toContain("fillable PDF");
    expect(html).toContain("spreadsheet");
    expect(html).not.toContain("pdf_flat");
  });

  it("states how fields stored is counted for a year that isn't projected", () => {
    expect(render("year=2023-24")).toContain('id="dq-note-counting"');
    expect(render("year=2024-25")).not.toContain('id="dq-note-counting"');
    expect(render("year=2025-26")).not.toContain('id="dq-note-counting"');
  });

  it("puts the trend in the all-years table, without fields stored", () => {
    const html = render();
    const glance = table(html, "dq-glance");
    expect(glance).not.toContain("Fields stored");
    expect(glance.indexOf("2025-26")).toBeLessThan(glance.indexOf("2023-24"));
  });
});

describe("launch gate: header, nav and methodology link", () => {
  it("omits the Data quality tab before launch and shows both after", () => {
    expect(visibleArchiveTabs(false).map((t) => t.id)).toEqual(["coverage"]);
    expect(visibleArchiveTabs(true).map((t) => t.id)).toEqual(["coverage", "quality"]);
    const before = renderToStaticMarkup(<ArchiveStatusHeader active="coverage" launched={false} />);
    expect(before).not.toContain("/data-quality");
    const after = renderToStaticMarkup(<ArchiveStatusHeader active="quality" launched />);
    expect(after).toContain('href="/coverage"');
    expect(after).toMatch(/aria-current="page"[^>]*>Data quality</);
  });

  it("keeps 'Coverage' in the nav before launch, and 'Archive status' lit on both routes after", () => {
    expect(secondaryNavLinks(false).find((l) => l.href === "/coverage")?.label).toBe("Coverage");
    const after = secondaryNavLinks(true).find((l) => l.href === "/coverage")!;
    expect(after.label).toBe("Archive status");
    expect(isActive("/coverage", after.href, after.alsoActiveOn)).toBe(true);
    expect(isActive("/data-quality", after.href, after.alsoActiveOn)).toBe(true);
    expect(isActive("/data-quality", "/coverage")).toBe(false);
  });
});

const Y = (y: string) => FIXTURE_SNAPSHOT.years.find((x) => x.cds_year === y)!;

describe("copy invariants (PRD 040 M3, VOICE.md)", () => {
  const years = ["2025-26", "2024-25", "2023-24"];
  /** Visible text of one rendered year, tags dropped. */
  const text = (y: string) => render(`year=${y}`).replace(/<[^>]*>/g, " ");
  const BANNED = /\b(extract(ed|or|ion|s)?|docling|tier ?\d?|drain(ed)?|manifest|projection|pipeline|overlay|acroform)\b/i;

  it("uses no operator words on any year", () => {
    for (const y of years) expect(text(y)).not.toMatch(BANNED);
  });

  it("has at most one em dash on any year", () => {
    for (const y of years) expect((render(`year=${y}`).match(/\u2014|&mdash;|&#8212;/g) ?? []).length).toBeLessThanOrEqual(1);
  });

  it("shows the 2023-24 financial aid sample only for the year it covered, with its sample size", () => {
    const sample = AID_CANT_CHECK_SAMPLE;
    expect(render("year=2023-24")).toContain('id="dq-note-aid-sample"');
    const note = aidCantCheckNote(Y("2023-24"))!;
    expect(note).toContain(String(sample.checked));
    expect(note).toContain(String(sample.ours));
    expect(note).not.toContain("217");
    expect(render("year=2024-25")).not.toContain('id="dq-note-aid-sample"');
    expect(render("year=2025-26")).not.toContain('id="dq-note-aid-sample"');
    expect(aidCantCheckNote(Y("2024-25"))).toBeNull();
    // no can't-check reports left (after the fix lands): nothing to describe
    const fixed = Y("2023-24");
    expect(aidCantCheckNote({ ...fixed, total: { ...fixed.total, totals: { ...fixed.total.totals, H1: { ...fixed.total.totals.H1, cant_check: 0 } } } })).toBeNull();
  });

  it("shows the admissions 'differs' sample only for the years it covered, never for the empty-federal year", () => {
    expect(render("year=2023-24")).toContain('id="dq-differs-sample"');
    expect(render("year=2024-25")).toContain('id="dq-differs-sample"');
    expect(render("year=2025-26")).not.toContain('id="dq-differs-sample"');
    const note = federalDiffersNote(Y("2024-25"))!;
    expect(note).toContain(String(FEDERAL_DIFFERS_SAMPLE.checked));
    expect(note).toContain(String(FEDERAL_DIFFERS_SAMPLE.sameInFile));
    expect(federalDiffersNote(Y("2025-26"))).toBeNull();
    const y = Y("2024-25");
    expect(federalDiffersNote({ ...y, total: { ...y.total, federal: { ...y.total.federal, differs: 0 } } })).toBeNull();
  });

  it("the sample counts add up", () => {
    expect(AID_CANT_CHECK_SAMPLE.ours).toBeLessThanOrEqual(AID_CANT_CHECK_SAMPLE.checked);
    expect(FEDERAL_DIFFERS_SAMPLE.sameInFile + FEDERAL_DIFFERS_SAMPLE.ours).toBe(FEDERAL_DIFFERS_SAMPLE.checked);
  });

  it("renders the licence note beside the downloads only when launched, built from the license constants", () => {
    vi.useFakeTimers();
    try {
      vi.setSystemTime(Date.parse(`${DATA_QUALITY_LAUNCH_DATE}T00:00:00Z`) - 1000);
      const before = render("year=2024-25");
      expect(before).not.toContain(DATA_LICENSE_URL);
      expect(before).not.toContain("Download 2024-25 table as CSV");
      vi.setSystemTime(Date.parse(`${DATA_QUALITY_LAUNCH_DATE}T00:00:00Z`));
      const after = render("year=2024-25");
      expect(after).toContain(`href="${DATA_LICENSE_URL}"`);
      expect(after).toContain(`>${DATA_LICENSE_NAME}</a>`);
      expect(after).toContain("Download 2024-25 table as CSV");
    } finally {
      vi.useRealTimers();
    }
  });

  // Seen under `next dev` (Turbopack): the space before a text run containing an HTML entity was dropped
  // after an inline element or a {expression} ("No value</strong>means"). A production build wasn't checked.
  // Vitest compiles differently and can't see it, so keep entities out of this file; write the characters.
  it("writes curly quotes as characters, not entities, so no space is lost in the real build", () => {
    expect(readFileSync(resolve(__dirname, "DataQualityView.tsx"), "utf8")).not.toMatch(/&(r|l)(s|d)quo;/);
  });
});
