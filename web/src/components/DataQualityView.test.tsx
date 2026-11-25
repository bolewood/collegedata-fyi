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

import { FIXTURE_SNAPSHOT, FIXTURE_SNAPSHOT_V1, FIXTURE_SNAPSHOT_V2, FIXTURE_SNAPSHOT_V3, emptyYear } from "@/lib/__fixtures__/data-quality-snapshot";
import { DATA_LICENSE_NAME, DATA_LICENSE_URL } from "@/lib/data-license";
import {
  type QualitySnapshot,
  type QualityYear,
  FEDERAL_DIFFERS_SAMPLE,
  hasSections,
  aidPoolBounds,
  differsPoolBounds,
  pooledDiffers,
  AID_CANT_CHECK_SAMPLE,
  DATA_QUALITY_LAUNCH_DATE,
  aidCantCheckNote,
  federalDiffersNote,
} from "@/lib/data-quality";
import { HAS_CDS_HREF } from "@/lib/coverage-model";
import { secondaryNavLinks, isActive } from "@/lib/nav-links";
import { ArchiveStatusHeader, visibleArchiveTabs } from "./ArchiveStatusHeader";
import { DataQualityView, yearNotices } from "./DataQualityView";

function render(search = "", snapshot: QualitySnapshot = FIXTURE_SNAPSHOT) {
  currentParams = new URLSearchParams(search);
  return renderToStaticMarkup(<DataQualityView snapshot={snapshot} />);
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

  it("links the list of colleges we have a CDS for, one click from the page, to the same preset the Coverage tab offers", () => {
    const html = render();
    expect(html).toContain(`href="${HAS_CDS_HREF}"`);
    expect(html).toMatch(/<a href="[^"]*">colleges we have a CDS for<\/a>/);
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


const LAUNCH_MS = Date.parse(`${DATA_QUALITY_LAUNCH_DATE}T00:00:00Z`);
/** Every spelling of an em dash: the character, and the three entity forms. */
const EM_DASH = /\u2014|&mdash;|&#8212;|&#x2014;/gi;
const BANNED =
  /\b(extract(ed|or|ion|s)?|docling|tier ?\d?|drain(ed)?|manifest|projection|pipeline|overlay|acroform|served|scoreboard|base reading|parse error|live (report|reports|count))\b/i;

/** A copy of the fixture year with the 2023-24 financial aid "can't check" total set to n. */
const withCantCheck = (y: QualityYear, n: number): QualityYear => ({
  ...y,
  total: { ...y.total, totals: { ...y.total.totals, H1: { ...y.total.totals.H1, cant_check: n } } },
});
const withDiffers = (y: QualityYear, n: number): QualityYear => ({
  ...y,
  total: { ...y.total, federal: { ...y.total.federal, differs: n } },
});
const Y = (y: string) => FIXTURE_SNAPSHOT.years.find((x) => x.cds_year === y)!;

describe("copy invariants (PRD 040 M3, VOICE.md)", () => {
  const years = ["2025-26", "2024-25", "2023-24"];
  /** Rendered with the gate open, so the download buttons and licence lines are in the text too. */
  const openHtml = (y: string) => {
    vi.useFakeTimers();
    try {
      vi.setSystemTime(LAUNCH_MS);
      return render(`year=${y}`);
    } finally {
      vi.useRealTimers();
    }
  };
  const textOf = (html: string) => html.replace(/<[^>]*>/g, " ");

  it("uses no operator words on any year, gate closed or open", () => {
    for (const y of years) {
      expect(textOf(render(`year=${y}`))).not.toMatch(BANNED);
      expect(textOf(openHtml(y))).not.toMatch(BANNED);
    }
  });

  it("catches each banned phrase (so the list above is live)", () => {
    for (const w of ["parse error", "live reports", "live count", "served", "scoreboard", "overlay", "base reading", "manifest"]) {
      expect(`the ${w} here`).toMatch(BANNED);
    }
  });

  it("has at most one em dash on any year, in any spelling", () => {
    for (const y of years) expect((openHtml(y).match(EM_DASH) ?? []).length).toBeLessThanOrEqual(1);
    for (const f of ["\u2014", "&mdash;", "&#8212;", "&#x2014;", "&MDASH;"]) expect(f.match(EM_DASH)).not.toBeNull();
  });

  it("shows the 2023-24 financial aid sample only for the year it covered, and only while its pool is still about that size", () => {
    const pool = AID_CANT_CHECK_SAMPLE.population;
    expect(Y("2023-24").total.totals.H1.cant_check).toBe(pool);
    expect(render("year=2023-24")).toContain('id="dq-note-aid-sample"');
    expect(render("year=2024-25")).not.toContain('id="dq-note-aid-sample"');
    expect(render("year=2025-26")).not.toContain('id="dq-note-aid-sample"');
    expect(aidCantCheckNote(Y("2024-25"))).toBeNull();

    // The pool the sample described (217) shows it; so do both edges of 90% to 110% (196 and 238); a fix (~67) or a
    // pool that grew a lot (a regression) hides it.
    expect(aidPoolBounds()).toEqual({ low: 196, high: 238 });
    for (const n of [196, pool, 238]) expect(aidCantCheckNote(withCantCheck(Y("2023-24"), n))).not.toBeNull();
    for (const n of [0, 67, 195, 239, 500]) expect(aidCantCheckNote(withCantCheck(Y("2023-24"), n))).toBeNull();
    // The year guard on its own: a year the sample didn't cover stays hidden even with 217 can't-check reports.
    expect(aidCantCheckNote(withCantCheck(Y("2024-25"), pool))).toBeNull();
  });

  /** The fixture with 2024-25's differing values changed so the two covered years together hold n. */
  const withPooled = (n: number): QualitySnapshot => {
    const base = pooledDiffers(FIXTURE_SNAPSHOT);
    return {
      ...FIXTURE_SNAPSHOT,
      years: FIXTURE_SNAPSHOT.years.map((y) => (y.cds_year === "2024-25" ? withDiffers(y, y.total.federal.differs + (n - base)) : y)),
    };
  };
  const noteFor = (snap: QualitySnapshot, y: string) => federalDiffersNote(snap.years.find((x) => x.cds_year === y)!, snap);

  it("shows the admissions 'differs' sample only for the years it covered, with federal figures and differing values", () => {
    expect(render("year=2023-24")).toContain('id="dq-differs-sample"');
    expect(render("year=2024-25")).toContain('id="dq-differs-sample"');
    expect(render("year=2025-26")).not.toContain('id="dq-differs-sample"');
    expect(noteFor(FIXTURE_SNAPSHOT, "2024-25")).not.toBeNull();
    // No differing values left in the year: nothing to describe.
    expect(federalDiffersNote(withDiffers(Y("2024-25"), 0), withPooled(219))).toBeNull();
    // Year guard on its own: an uncovered year with federal figures and differing values stays hidden.
    const uncovered = { ...withDiffers(Y("2025-26"), 5), federal_fall_loaded: true };
    expect(federalDiffersNote(uncovered, FIXTURE_SNAPSHOT)).toBeNull();
    // Loaded guard on its own: a covered year with no federal figures but differing values stays hidden.
    const unloaded = { ...withDiffers(Y("2024-25"), 5), federal_fall_loaded: false };
    expect(federalDiffersNote(unloaded, FIXTURE_SNAPSHOT)).toBeNull();
  });

  it("hides the 'differs' sample once the two covered years together leave 90% to 110% of the 219 values it was drawn from", () => {
    expect(pooledDiffers(FIXTURE_SNAPSHOT)).toBe(FEDERAL_DIFFERS_SAMPLE.populationValues);
    expect(differsPoolBounds()).toEqual({ low: 198, high: 240 });
    for (const n of [198, 219, 240]) expect(noteFor(withPooled(n), "2024-25")).not.toBeNull();
    for (const n of [197, 241, 60, 500]) expect(noteFor(withPooled(n), "2024-25")).toBeNull();
    expect(noteFor(withPooled(219), "2023-24")).not.toBeNull();
  });

  it("with no federal figures, Table B says so under its heading and has no 'No value' or 'Differs' notes or download", () => {
    const html = openHtml("2025-26");
    expect(html).toContain('id="dq-no-federal"');
    expect(html.indexOf('id="dq-no-federal"')).toBeLessThan(html.indexOf('id="dq-table-b"'));
    // None of Table B's explanations apply with no federal figures: "No value", "Differs" and the left-out note.
    for (const id of ["dq-note-no-value", "dq-note-differs", "dq-note-left-out"]) expect(html).not.toContain(`id="${id}"`);
    expect(html).not.toContain("/data-quality/csv/federal/");
    const loaded = openHtml("2024-25");
    expect(loaded).not.toContain('id="dq-no-federal"');
    for (const id of ["dq-note-no-value", "dq-note-differs", "dq-note-left-out"]) expect(loaded).toContain(`id="${id}"`);
    expect(loaded).toContain("/data-quality/csv/federal/2024-25");
  });

  describe("by section (Table A, by section)", () => {
    const secHtml = (html: string) => html.match(/<section aria-labelledby="dq-sections-heading"[\s\S]*?<\/section>/)?.[0] ?? null;
    const cells = (html: string, name: string) => {
      const tr = html.match(new RegExp(`<tr[^>]*><th scope="row"[^>]*>${name}</th>([\\s\\S]*?)</tr>`))![1];
      return [...tr.matchAll(/<td[^>]*>([^<]*)<\/td>/g)].map((m) => m[1]);
    };

    it("sits after Table A and before Table B, with the section names and hand-worked cells (2024-25)", () => {
      const html = render("year=2024-25");
      expect(html.indexOf('id="dq-table-a"')).toBeLessThan(html.indexOf('id="dq-table-sections"'));
      expect(html.indexOf('id="dq-table-sections"')).toBeLessThan(html.indexOf('id="dq-table-b"'));
      const s = secHtml(html)!;
      const heads = [...s.matchAll(/<th scope="col"[^>]*>([^<]*)<\/th>/g)].map((m) => m[1]);
      expect(heads).toEqual(["Section", "Questions on the form", "Fields stored: median", "Usable answers: median", "Usable, as a share of questions"]);
      // Fixture: half the questions stored, usable = stored minus the section's position A to J.
      expect(cells(s, "A General information")).toEqual(["51", "25", "25", "49%"]);
      expect(cells(s, "B Enrollment and persistence")).toEqual(["219", "109", "108", "49%"]);
      expect(cells(s, "C First-time, first-year admission")).toEqual(["278", "139", "137", "49%"]);
      expect(cells(s, "J Disciplinary areas of degrees conferred")).toEqual(["120", "60", "51", "43%"]);
      expect(s.match(/<tr[^>]*><th scope="row"/g)).toHaveLength(10);
      expect(s).toContain("counting the 78 published 2024-25 reports numbered by that form");
    });

    it("says what usable means and that the table can't say why a number is low, without a claim about causes", () => {
      const note = secHtml(render("year=2024-25"))!.match(/<p id="dq-note-usable"[^>]*>[\s\S]*?<\/p>/)![0];
      expect(note).toMatch(/A usable answer is a value a reader can use/);
      expect(note).toMatch(/unreadable or as “not applicable” are stored\s+but not counted as usable/);
      expect(note).toMatch(/counting “not applicable” would raise some sections, transfer admission especially/);
      expect(note).not.toMatch(/empty/);
      expect(note).toMatch(/a share of 100% isn’t the goal/);
      expect(note).toMatch(/this table can’t say\s+which/);
      expect(note).not.toMatch(/\b(most|usually|always|typically)\b/i);
    });

    it("names the reports left out only when some are numbered by another year's form", () => {
      expect(secHtml(render("year=2023-24"))).toContain('id="dq-note-sections-left-out"');
      expect(secHtml(render("year=2023-24"))).toContain("12 reports numbered by");
      expect(secHtml(render("year=2024-25"))).not.toContain('id="dq-note-sections-left-out"');
    });

    it("carries the 2023-24 counting note only for a year counted that way", () => {
      expect(secHtml(render("year=2023-24"))).toContain('id="dq-note-counting-sections"');
      expect(secHtml(render("year=2024-25"))).not.toContain("dq-note-counting-sections");
    });

    it("shows dashes for a year with no reports and no share under 5 reports", () => {
      const none = { ...FIXTURE_SNAPSHOT, years: [emptyYear("2026-27")] };
      const s = secHtml(render("", none))!;
      expect(cells(s, "A General information")).toEqual(["51", "–", "–", "–"]);
      expect(s).not.toContain("dq-scroll-hint");
      const small = JSON.parse(JSON.stringify(FIXTURE_SNAPSHOT)) as QualitySnapshot;
      small.years.find((y) => y.cds_year === "2024-25")!.sections!.reports = 4;
      const t = secHtml(render("year=2024-25", small))!;
      expect(cells(t, "A General information")).toEqual(["51", "25", "25", "–"]);
      expect(t).toContain("Under 5 reports: no share");
    });

    it("links the CSV for the selected year, once launched, and says '1 report' for one", () => {
      expect(openHtml("2024-25")).toContain('href="/data-quality/csv/sections/2024-25"');
      expect(render("year=2024-25")).not.toContain("/data-quality/csv/sections/");
      const one = JSON.parse(JSON.stringify(FIXTURE_SNAPSHOT)) as QualitySnapshot;
      const y = one.years.find((x) => x.cds_year === "2024-25")!;
      y.sections!.reports = 1;
      const t = secHtml(render("year=2024-25", one))!;
      expect(t).toContain("counting the 1 published 2024-25 report numbered by that form");
      expect(t).toContain('id="dq-note-sections-small"');
      expect(t).toContain("Fewer than 5 reports, so no share is shown.");
      expect(secHtml(render("year=2024-25"))).not.toContain("dq-note-sections-small");
    });

    it("is absent, with no CSV link, for a year whose form has no full field schema (sections rows [])", () => {
      const none = JSON.parse(JSON.stringify(FIXTURE_SNAPSHOT)) as QualitySnapshot;
      const y = none.years.find((x) => x.cds_year === "2024-25")!;
      y.form.full_field_schema = false;
      y.sections = { reports: 0, rows: [] };
      expect(hasSections(y)).toBe(false);
      expect(render("year=2024-25", none)).not.toContain("dq-sections-heading");
      expect(render("year=2024-25", none)).not.toContain("dq-table-sections");
      vi.useFakeTimers();
      try {
        vi.setSystemTime(LAUNCH_MS);
        expect(render("year=2024-25", none)).not.toContain("/data-quality/csv/sections/");
      } finally {
        vi.useRealTimers();
      }
    });

    it("is absent for a snapshot written before public_format 3", () => {
      expect(render("year=2024-25", FIXTURE_SNAPSHOT_V2)).not.toContain("dq-table-sections");
      expect(render("year=2024-25", FIXTURE_SNAPSHOT_V1)).not.toContain("dq-sections-heading");
    });
  });

  describe("enrollment and tuition against federal figures (Table B, more checks)", () => {
    const b2 = (html: string) => html.match(/<section aria-labelledby="dq-b2-heading"[\s\S]*?<\/section>/)?.[0] ?? null;
    const cells = (html: string, id: string, name: string) => {
      const tbl = html.match(new RegExp(`<table[^>]*id="${id}"[\\s\\S]*?</table>`))![0];
      const tr = tbl.match(new RegExp(`<tr[^>]*><th scope="row"[^>]*>${name}</th>([\\s\\S]*?)</tr>`))![1];
      return [...tr.matchAll(/<td[^>]*>([^<]*)<\/td>/g)].map((m) => m[1]);
    };

    it("follows Table B and precedes Table C, with both checks and hand-worked cells (2024-25 enrollment)", () => {
      const html = render("year=2024-25");
      expect(html.indexOf('id="dq-table-b"')).toBeLessThan(html.indexOf('id="dq-table-enrollment"'));
      expect(html.indexOf('id="dq-table-tuition"')).toBeLessThan(html.indexOf('id="dq-table-c"'));
      const s = b2(html)!;
      const heads = [...s.matchAll(/<th scope="col"[^>]*>([^<]*)<\/th>/g)].map((m) => m[1]).slice(0, 8);
      expect(heads).toEqual(["Format", "Reports checked", "Matches", "No value", "Differs", "Differs by over 2% to 10%", "Differs by over 10%", "Match rate"]);
      // Reports, matches, no value, differs, 2-10%, over 10%, match rate.
      expect(cells(s, "dq-table-enrollment", "standard PDF")).toEqual(["49", "36", "9", "4", "2", "2", "73%"]);
      expect(cells(s, "dq-table-enrollment", "fillable PDF")).toEqual(["25", "18", "5", "2", "1", "1", "72%"]);
      expect(cells(s, "dq-table-enrollment", "spreadsheet")).toEqual(["3", "3", "0", "0", "0", "0", "–"]);   // 3 reports: no rate
      expect(cells(s, "dq-table-enrollment", "All formats")).toEqual(["77", "57", "14", "6", "3", "3", "74%"]);
    });

    it("names the IPEDS table, variable and year, and what can differ, in each note", () => {
      const html = b2(render("year=2023-24"))!;
      const text = (id: string) => html.match(new RegExp(`<p id="${id}"[^>]*>[\\s\\S]*?</p>`))![0].replace(/<[^>]+>/g, "").replace(/\s+/g, " ");
      const enr = text("dq-note-enrollment");
      expect(enr).toContain("DRVEF2023, variable EFUG, fall 2023");
      expect(enr).toMatch(/census date.*can differ/);
      // The release facts and the band rule are said once, for the section, not in each check's note.
      const shared = text("dq-note-b2-shared");
      expect(shared).toContain("This snapshot doesn’t record which IPEDS release (final or provisional), release date or imputation flag each figure came from.");
      expect(shared).toContain("Where a final and a provisional release both have a figure, the final one is used.");
      expect(shared).toContain("A school’s page shows the release and imputation for its latest federal figures, which can be a later year than the one compared here.");
      expect(shared).toContain("exactly 10% counts in the first");
      expect(shared).toContain("Matches means within 2%");
      for (const note of [enr, text("dq-note-tuition"), text("dq-note-enrollment-left-out"), text("dq-note-tuition-left-out")]) {
        expect(note).not.toContain("final or provisional");
        expect(note).not.toContain("exactly 10%");
      }
      expect(html.match(/final or provisional/g)).toHaveLength(1);
      const tui = text("dq-note-tuition");
      expect(tui).toContain("IC2024_AY, which our federal facts label COST1_2024, variable TUITION2");
      expect(tui).toContain("academic year 2024-25");
      expect(tui).toContain("CDS form for 2023-24 asks for that following year’s tuition");
      expect(tui).toMatch(/Neither includes required fees/);
      expect(tui).toMatch(/per-credit or program-specific pricing/);
      expect(tui).toMatch(/Out-of-state and first-year tuition aren’t compared/);
      for (const note of [enr, tui]) expect(note).not.toMatch(/\b(most|usually|always|typically)\b/i);
      expect(text("dq-note-enrollment-left-out")).toContain("Left out: 1 report we’ve marked as filed for one campus or unit and 0 whose school has no federal undergraduate enrollment figure");
      expect(text("dq-note-tuition-left-out")).toContain("whose school has no federal tuition figure");
    });

    it("renders the tuition table's own counts, not the enrollment table's, with hand-worked cells (2023-24)", () => {
      const s = b2(render("year=2023-24"))!;
      // Fixture, 2023-24 standard PDF (300 published, 299 checked by Table B): tuition on 90% of them, 30% no value, 20% differing.
      expect(cells(s, "dq-table-tuition", "standard PDF")).toEqual(["269", "136", "80", "53", "31", "22", "51%"]);
      expect(cells(s, "dq-table-enrollment", "standard PDF")).toEqual(["299", "211", "59", "29", "17", "12", "71%"]);
      expect(cells(s, "dq-table-tuition", "All formats")).not.toEqual(cells(s, "dq-table-enrollment", "All formats"));
      expect(cells(s, "dq-table-tuition", "spreadsheet")).toEqual(["2", "2", "0", "0", "0", "0", "–"]);   // 2 reports: no rate
    });

    it("says 'report' for one left out and 'reports' for more, and ends the left-out note with the open-cause No value", () => {
      const text = (html: string, id: string) => html.match(new RegExp(`<p id="${id}"[^>]*>[\\s\\S]*?</p>`))![0].replace(/<[^>]+>/g, "").replace(/\s+/g, " ");
      expect(text(b2(render("year=2023-24"))!, "dq-note-enrollment-left-out")).toContain("Left out: 1 report we’ve marked");
      const many = JSON.parse(JSON.stringify(FIXTURE_SNAPSHOT)) as QualitySnapshot;
      many.years.find((x) => x.cds_year === "2023-24")!.federal_checks!.enrollment.single_campus = 2;
      const note = text(b2(render("year=2023-24", many))!, "dq-note-enrollment-left-out");
      expect(note).toContain("Left out: 2 reports we’ve marked");
      expect(note).toContain("No value means no usable CDS number was available to compare: the school may have left it blank, or we may have missed it or set it aside.");
      expect(note).not.toContain("the report has no usable number");
    });

    it("hides the match rate under 5 reports, in the All formats row too", () => {
      const small = JSON.parse(JSON.stringify(FIXTURE_SNAPSHOT)) as QualitySnapshot;
      const y = small.years.find((x) => x.cds_year === "2024-25")!;
      for (const r of [...y.rows, y.total]) r.checks!.enrollment = { reports: 4, matches: 3, no_value: 1, differs: 0, differs_2_to_10pct: 0, differs_over_10pct: 0 };
      expect(cells(b2(render("year=2024-25", small))!, "dq-table-enrollment", "All formats").at(-1)).toBe("–");
    });

    it("shows dashes and a notice, no notes and no download, where IPEDS figures aren't loaded", () => {
      const html = openHtml("2024-25");
      const s = b2(html)!;
      expect(s).toContain('id="dq-no-tuition"');
      expect(s).toContain("No federal tuition figures for the 2025-26 academic year yet.");
      expect(s).not.toContain('id="dq-no-enrollment"');
      expect(s).not.toContain('id="dq-note-tuition"');
      expect(s).not.toContain("/data-quality/csv/tuition/");
      expect(cells(s, "dq-table-tuition", "standard PDF")).toEqual(["–", "–", "–", "–", "–", "–", "–"]);
      expect(s).toContain('href="/data-quality/csv/enrollment/2024-25"');
      const last = b2(openHtml("2025-26"))!;
      expect(last).toContain("No federal fall 2025 undergraduate enrollment figures yet.");
      expect(last).toContain("No federal tuition figures for the 2026-27 academic year yet.");
      expect(last).not.toContain("/data-quality/csv/");
    });

    it("is absent for a snapshot written before public_format 4", () => {
      expect(render("year=2024-25", FIXTURE_SNAPSHOT_V3)).not.toContain("dq-b2-heading");
    });
  });

  describe("size of federal differences", () => {
    const sizeNote = (html: string) => html.match(/<p id="dq-note-differs-size"[^>]*>[\s\S]*?<\/p>/)?.[0] ?? null;
    const bText = (html: string) => table(html, "dq-table-b");

    it("shows two size columns after Differs, with the fixture's counts in the right cells", () => {
      const html = bText(openHtml("2024-25"));
      const heads = [...html.matchAll(/<th scope="col"[^>]*>([^<]*)<\/th>/g)].map((m) => m[1]);
      expect(heads.indexOf("Differs by over 2% to 10%")).toBe(heads.indexOf("Differs") + 1);
      expect(heads.indexOf("Differs by over 10%")).toBe(heads.indexOf("Differs") + 2);
      // Standard PDF, 2024-25: 60 differ, 36 of them 2% to 10% off and 24 over 10%. All formats: 89, 53 and 36.
      const cells = (rowName: string) => {
        const tr = html.match(new RegExp(`<tr[^>]*><th scope="row"[^>]*>${rowName}</th>([\\s\\S]*?)</tr>`))![1];
        return [...tr.matchAll(/<td[^>]*>([^<]*)<\/td>/g)].map((m) => m[1]);
      };
      expect(cells("standard PDF").slice(4, 7)).toEqual(["60", "36", "24"]);
      expect(cells("All formats").slice(4, 7)).toEqual(["89", "53", "36"]);
    });

    it("marks the rendered table as the split one on format 2 and not on format 1", () => {
      const open = (html: string) => html.match(/<table[^>]*id="dq-table-b"[^>]*>/)![0];
      expect(open(openHtml("2024-25"))).toContain("dq-table--b-split");
      expect(open(render("year=2024-25", FIXTURE_SNAPSHOT_V1))).not.toContain("dq-table--b-split");
    });

    it("gives every row the same cell count as the header", () => {
      const html = bText(openHtml("2024-25"));
      const head = (html.match(/<thead>[\s\S]*?<\/thead>/)![0].match(/<th\b/g) ?? []).length;
      for (const tr of html.match(/<tbody>[\s\S]*<\/tbody>/)![0].match(/<tr[\s\S]*?<\/tr>/g)!) {
        expect((tr.match(/<t[hd]\b/g) ?? []).length).toBe(head);
      }
    });

    it("explains the size without overclaiming, and states the boundary rule", () => {
      const note = sizeNote(openHtml("2024-25"))!;
      expect(note).not.toBeNull();
      // The columns are named as in the header, not "first" and "second".
      expect(note).toContain("Differs by over 2% to 10%");
      expect(note).toContain("Differs by over 10%");
      expect(note).not.toMatch(/first column|second column/);
      expect(note).toMatch(/exactly\s+10% counts in “over 2% to 10%”/);
      expect(note).toMatch(/2% or less is a match/);
      expect(note).toMatch(/over 2% to 10% may come from a different count date/);
      expect(note).toMatch(/may be a real difference between the two filings, a scope mismatch/);
      expect(note).toMatch(/misreading; the size alone can’t say which/);
      expect(note).not.toMatch(/isn’t necessarily our error|some are real/);
      // No claim about how many large gaps are ours or the school's.
      expect(note).not.toMatch(/\b(most|usually|always|mostly|typically)\b/i);
      expect(note).not.toMatch(/\d+(\.\d+)?%\s+of/);
    });

    it("shows dashes and no size note for a year with no federal figures", () => {
      const html = openHtml("2025-26");
      expect(sizeNote(html)).toBeNull();
      const dashes = bText(html).match(/<tr[^>]*><th scope="row"[^>]*>standard PDF<\/th>[\s\S]*?<\/tr>/)![0];
      expect((dashes.match(/<td[^>]*>–<\/td>/g) ?? []).length).toBe(8);
    });

    it("renders a format 1 snapshot without the split: seven columns, no size note, same Differs count", () => {
      const html = render("year=2024-25", FIXTURE_SNAPSHOT_V1);
      const b = bText(html);
      expect(b).not.toContain("Differs by over");
      expect((b.match(/<thead>[\s\S]*?<\/thead>/)![0].match(/<th\b/g) ?? []).length).toBe(7);
      expect(sizeNote(html)).toBeNull();
      expect(b).toContain(">89<");
      expect(html).toContain('id="dq-note-differs"');
    });
  });

  it("renders the licence note beside the downloads only when launched, built from the license constants", () => {
    vi.useFakeTimers();
    try {
      vi.setSystemTime(LAUNCH_MS - 1000);
      const before = render("year=2024-25");
      expect(before).not.toContain(DATA_LICENSE_URL);
      expect(before).not.toContain("Download 2024-25 table as CSV");
      vi.setSystemTime(LAUNCH_MS);
      const after = render("year=2024-25");
      expect(after).toContain(`href="${DATA_LICENSE_URL}"`);
      expect(after).toContain(`>${DATA_LICENSE_NAME}</a>`);
      expect(after).toContain("Download 2024-25 table as CSV");
      // A sentence, not a label: not set in the uppercase `.meta` style.
      expect(after).not.toMatch(/class="meta"[^>]*>\s*This table is licensed/);
    } finally {
      vi.useRealTimers();
    }
  });

  it("states the rule for files that disagree with themselves as the condition it is (rows by sex when both read, else the printed total)", () => {
    const text = textOf(render()).replace(/\s+/g, " ");
    expect(text).toMatch(/rows by sex when both men and women were read/);
    expect(text).toMatch(/printed total otherwise/);
    expect(text).not.toMatch(/We use the table by sex\./);
  });

  it("puts a static, aria-hidden hint above each wide table (CSS decides when it shows) and no script-driven cue", () => {
    const html = render("year=2024-25");
    expect(html.match(/class="dq-scroll-hint acc-table-hint" aria-hidden="true"/g)).toHaveLength(6);
    expect(html.match(/dq-scroll--wide/g)).toHaveLength(1);
    expect(html).not.toContain("linear-gradient");
    // Every table's scroll region is still focusable and labelled.
    expect(html.match(/role="region" aria-label="[^"]+" tabindex="0"/g)).toHaveLength(7);
    const src = readFileSync(resolve(__dirname, "DataQualityView.tsx"), "utf8");
    expect(src).not.toMatch(/useState|useEffect|ResizeObserver|scrollWidth/);
  });

  it("leaves out the hint for Table B when the year has no federal figures (a table of dashes)", () => {
    const html = render("year=2025-26");
    expect(html.match(/dq-scroll-hint/g)).toHaveLength(4);
    const b = html.slice(html.indexOf('aria-label="Table B, 2025-26"') - 400, html.indexOf('aria-label="Table B, 2025-26"'));
    expect(b).not.toContain("dq-scroll-hint");
  });

  const css = () => readFileSync(resolve(__dirname, "../app/data-quality/data-quality.css"), "utf8");

  it("keeps the CSS hint's breakpoints one pixel under the tables' minimum widths", () => {
    const text = css();
    expect(text).toContain("container-type: inline-size");
    const min = (sel: string) => Number(new RegExp(`${sel} \\{[^}]*min-width: (\\d+)px`).exec(text)![1]);
    expect(text).toContain(`@container (max-width: ${min("\\.dq-table")  - 1}px) { .dq-scroll .dq-scroll-hint`);
    expect(text).toContain(`@container (max-width: ${min("\\.dq-table--c") - 1}px) { .dq-scroll--wide .dq-scroll-hint`);
  });

  // The scroll cut must land on a column edge (a half-shown "30" reads as "3"). On a phone each table's leading
  // columns are sized in cqw to add up to exactly one scroll box, and its trailing columns in px to add up to the
  // width the table adds on top, so the visible part is whole columns at any phone width.
  it.each([
    ["dq-glance", "glance"],
    ["dq-table-a", "a"],
    ["dq-table-b", "b"],
    ["dq-table-c", "c"],
  ])("renders %s with its phone class and one sized column per header cell", (id, name) => {
    const html = render("year=2024-25");
    const whole = html.match(new RegExp(`<table class="([^"]*)"[^>]*id="${id}"[\\s\\S]*?</table>`))!;
    expect(whole[1].split(" ")).toContain("dq-table");
    expect(whole[1].split(" ")).toContain(`dq-table--${name}`);
    const cols = whole[0].match(/<col\b/g) ?? [];
    const headerCells = whole[0].match(/<thead>[\s\S]*?<\/tr>/)![0].match(/<th\b/g) ?? [];
    expect(whole[0]).toContain("<colgroup>");
    expect(cols.length).toBe(headerCells.length);
    expect(cols.length).toBeGreaterThan(0);
  });

  it("renders a year with no documents as dashes, not 0%", () => {
    const snap: QualitySnapshot = JSON.parse(JSON.stringify(FIXTURE_SNAPSHOT));
    snap.years.push(emptyYear("2026-27"));
    currentParams = new URLSearchParams("year=2026-27");
    const html = renderToStaticMarkup(<DataQualityView snapshot={snap} />);
    expect(html).toContain("Table A, 2026-27");
    for (const id of ["dq-table-b", "dq-table-c"]) expect(table(html, id)).not.toMatch(PCT);
    expect(table(html, "dq-table-c")).toContain("(–)");
    // The glance row: match rate and the three adds-up rates are dashes (no reports, so no denominator).
    const row = html.match(/<tr><th scope="row"[^>]*>2026-27<\/th>[\s\S]*?<\/tr>/)![0];
    expect(row.match(/>–</g)).toHaveLength(4);
    expect(row).not.toMatch(/\d+%/);
    expect(html).toContain("1 removed, 1 with no file");
  });

  it("keeps each table's width out of its inline style, so the container rules can set it", () => {
    const html = render("year=2024-25");
    for (const id of ["dq-glance", "dq-table-a", "dq-table-b", "dq-table-c"]) {
      const open = html.match(new RegExp(`<table[^>]*id="${id}"[^>]*>`))![0];
      expect(open).not.toMatch(/width/);
    }
  });

  it.each([
    ["glance", "dq-glance", "\\.dq-table--glance"],
    ["a", "dq-table-a", "\\.dq-table--a"],
    ["a, by section", "dq-table-sections", "\\.dq-table--s"],
    ["b2 (enrollment and tuition)", "dq-table-enrollment", "\\.dq-table--x"],
    ["b (format 2, with the size columns)", "dq-table-b", "\\.dq-table--b-split"],
    ["b (format 1, without them)", "dq-table-b", "\\.dq-table--b", FIXTURE_SNAPSHOT_V1],
    ["c", "dq-table-c", "\\.dq-table--c"],
  ])("sizes Table %s's phone columns to end the first screen on a column edge", (_: string, id: string, sel: string, snap?: QualitySnapshot) => {
    // The column count is the rendered header's, so a new column without a CSS rule for it fails here.
    const whole = render("year=2024-25", snap).match(new RegExp(`<table[^>]*id="${id}"[\\s\\S]*?</table>`))![0];
    const cols = (whole.match(/<thead>[\s\S]*?<\/tr>/)![0].match(/<th\b/g) ?? []).length;
    expect(cols).toBeGreaterThan(0);
    const text = css();
    const width = new RegExp(`${sel} \\{[^}]*width: calc\\(100cqw \\+ (\\d+)px\\)`).exec(text);
    expect(width).not.toBeNull();
    const rules = [...text.matchAll(new RegExp(`${sel.replace("-split", "")} col:nth-child\\((n \\+ )?(\\d+)\\) \\{ width: (\\d+)(cqw|px)`, "g"))];
    let cqw = 0;
    let px = 0;
    let covered = 0;
    for (const m of rules) {
      const from = Number(m[2]);
      const count = m[1] ? cols - from + 1 : 1;
      covered += count;
      if (m[4] === "cqw") cqw += count * Number(m[3]);
      else px += count * Number(m[3]);
    }
    expect(covered).toBe(cols);
    expect(cqw).toBe(100);
    expect(px).toBe(Number(width![1]));
  });

  // Seen under `next dev` and in the production build: the space before a text run containing an HTML entity is
  // dropped after an inline element or a {expression} ("No value</strong>means"). Vitest compiles differently and
  // can't see it, so keep every entity out of this file and write the character (curly quotes, en dashes, &).
  it("uses no HTML entity of any kind in the view's or the two pages' source", () => {
    // The view and the two page files this work owns.
    for (const file of ["DataQualityView.tsx", "../app/data-quality/page.tsx", "../app/coverage/page.tsx"]) {
      const hits = readFileSync(resolve(__dirname, file), "utf8")
        .split("\n")
        .filter((l) => !/^\s*(\/\/|\*|\/\*)/.test(l) && /&(?:[a-zA-Z]+|#x?[0-9a-fA-F]+);/.test(l));
      expect(hits, file).toEqual([]);
    }
  });
});
