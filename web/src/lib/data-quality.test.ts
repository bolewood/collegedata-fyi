import { describe, expect, it } from "vitest";
import { FIXTURE_SNAPSHOT } from "./__fixtures__/data-quality-snapshot";
import {
  DATA_QUALITY_LAUNCH_DATE,
  MIN_REPORTS_FOR_RATE,
  SnapshotError,
  buildQualityCsv,
  compareYearsDesc,
  isDataQualityLaunched,
  liveCount,
  publishedTotal,
  qualityLede,
  renewalTile,
  resolveYear,
  rowPercent,
  selectSnapshot,
  yearGlance,
  yearsNewestFirst,
  type QualitySnapshot,
} from "./data-quality";
import { formatLabel } from "./format-labels";

const clone = (): QualitySnapshot => JSON.parse(JSON.stringify(FIXTURE_SNAPSHOT));
const withDate = (iso: string): QualitySnapshot => ({ ...clone(), snapshot_of: iso });

describe("launch gate", () => {
  it("is closed the instant before the launch date and open at it", () => {
    const at = Date.parse(`${DATA_QUALITY_LAUNCH_DATE}T00:00:00Z`);
    expect(isDataQualityLaunched(new Date(at - 1))).toBe(false);
    expect(isDataQualityLaunched(new Date(at))).toBe(true);
  });
});

describe("shared format labels", () => {
  it("uses one public vocabulary", () => {
    expect(formatLabel("pdf_flat")).toBe("standard PDF");
    expect(formatLabel("pdf_fillable")).toBe("fillable PDF");
    expect(formatLabel("pdf_scanned")).toBe("scanned PDF");
    expect(formatLabel("xlsx")).toBe("spreadsheet");
    expect(formatLabel("html")).toBe("web page");
    expect(formatLabel("docx")).toBe("Word");
  });

  it("sends other, unknown, null and new values to one label, never an internal key", () => {
    for (const v of ["other", "unknown", null, undefined, "", "toString", "pdf_weird"]) {
      expect(formatLabel(v)).toBe("other or unknown format");
    }
  });
});

describe("snapshot selection", () => {
  it("takes the newest snapshot_of", () => {
    const files = [
      { name: "2026-11-17.json", json: withDate("2026-11-17T10:00:00Z") },
      { name: "2026-11-24.json", json: withDate("2026-11-24T12:25:03Z") },
      { name: "2026-11-03.json", json: withDate("2026-11-03T09:00:00Z") },
    ];
    expect(selectSnapshot(files, true)?.snapshot_of).toBe("2026-11-24T12:25:03Z");
  });

  it("fails on two files with the same date", () => {
    const files = [
      { name: "a.json", json: withDate("2026-11-24T01:00:00Z") },
      { name: "b.json", json: withDate("2026-11-24T23:00:00Z") },
    ];
    expect(() => selectSnapshot(files, false)).toThrow(/same date 2026-11-24/);
  });

  it("fails on an empty directory once the page is launched, and returns null before", () => {
    expect(() => selectSnapshot([], true)).toThrow(SnapshotError);
    expect(selectSnapshot([], false)).toBeNull();
  });

  it("fails on a public_format the page doesn't know, even before launch", () => {
    const bad = { ...clone(), public_format: 2 };
    expect(() => selectSnapshot([{ name: "x.json", json: bad }], false)).toThrow(/public_format/);
  });

  it("fails on a snapshot with no renewal block or an empty renewal denominator", () => {
    const noBlock: Record<string, unknown> = { ...clone() };
    delete noBlock.renewal;
    expect(() => selectSnapshot([{ name: "x.json", json: noBlock }], false)).toThrow(/renewal/);
    const zero = clone();
    zero.renewal.previous = 0;
    zero.renewal.both = 0;
    expect(() => selectSnapshot([{ name: "x.json", json: zero }], false)).toThrow(/denominator/);
  });
});

describe("snapshot validation", () => {
  const bad = (mutate: (s: QualitySnapshot) => void, why: RegExp) => {
    const snap = clone();
    mutate(snap);
    expect(() => selectSnapshot([{ name: "x.json", json: snap }], false)).toThrow(why);
  };
  const anyRec = (v: unknown) => v as Record<string, unknown>;

  it("fails on a missing or non-boolean federal_fall_loaded", () => {
    bad((s) => delete anyRec(s.years[0]).federal_fall_loaded, /federal_fall_loaded/);
    bad((s) => (anyRec(s.years[0]).federal_fall_loaded = "yes"), /federal_fall_loaded/);
  });

  it("fails on a missing or non-boolean form.full_field_schema", () => {
    bad((s) => delete anyRec(s.years[0].form).full_field_schema, /full_field_schema/);
    bad((s) => (anyRec(s.years[0].form).full_field_schema = 1), /full_field_schema/);
  });

  it("fails on a non-count value in a row, the total, the form, set_aside_reasons or federal_left_out", () => {
    bad((s) => (s.years[0].rows[0].status.published = -1), /row .*published/);
    bad((s) => (s.years[0].rows[0].totals.B1.cant_check = 1.5), /cant_check/);
    bad((s) => (anyRec(s.years[0].rows[0].federal).matches = "3"), /matches/);
    bad((s) => (s.years[0].total.fields_stored.median = NaN), /total: .*median/);
    bad((s) => delete anyRec(s.years[0].total.totals.H1).doesnt, /total: .*doesnt/);
    bad((s) => (s.years[0].form.questions = -5), /form\.questions/);
    bad((s) => (s.years[0].set_aside_reasons.blank_form = 0.5), /blank_form/);
    bad((s) => delete anyRec(s.years[0].federal_left_out).single_campus, /single_campus/);
    bad((s) => (s.years[0].removed = -1), /removed/);
  });

  it("fails on a duplicate cds_year", () => {
    bad((s) => (s.years[1].cds_year = s.years[0].cds_year), /duplicate cds_year/);
  });

  it("fails when renewal years aren't consecutive", () => {
    bad((s) => (s.renewal.current_year = "2026-27"), /year after/);
    bad((s) => (s.renewal.previous_year = "2025-26"), /year after/);
  });

  it("fails when renewal.both exceeds previous, or a renewal count is negative or not an integer", () => {
    bad((s) => (s.renewal.both = s.renewal.previous + 1), /exceeds/);
    bad((s) => (s.renewal.both = -1), /renewal/);
    bad((s) => (s.renewal.current = 10.5), /renewal/);
    bad((s) => (s.renewal.previous = 479.2), /renewal/);
  });
});

describe("years", () => {
  it("sorts by integer start year, newest first, with non-years last", () => {
    expect(["2023-24", "unknown", "2025-26", "2024-25"].sort(compareYearsDesc)).toEqual([
      "2025-26",
      "2024-25",
      "2023-24",
      "unknown",
    ]);
  });

  it("selects the newest year by default and for an unknown ?year=", () => {
    expect(yearsNewestFirst(FIXTURE_SNAPSHOT).map((y) => y.cds_year)).toEqual(["2025-26", "2024-25", "2023-24"]);
    expect(resolveYear(FIXTURE_SNAPSHOT, null).cds_year).toBe("2025-26");
    expect(resolveYear(FIXTURE_SNAPSHOT, "2099-00").cds_year).toBe("2025-26");
    expect(resolveYear(FIXTURE_SNAPSHOT, "2023-24").cds_year).toBe("2023-24");
  });
});

describe("fixture follows the PRD invariants", () => {
  it.each(FIXTURE_SNAPSHOT.years.map((y) => [y.cds_year, y] as const))("%s: rows sum to the total", (_, y) => {
    const sum = y.rows.reduce((n, r) => n + liveCount(r.status), 0);
    expect(sum).toBe(liveCount(y.total.status));
    for (const r of y.rows) {
      expect(r.federal.matches + r.federal.no_value + r.federal.differs).toBe(r.federal.values);
      expect(r.federal.values).toBeLessThanOrEqual(3 * r.federal.reports);
      expect(r.totals.reports).toBe(r.status.published);
    }
  });
});

describe("rates and small groups", () => {
  it("shows no percentage under the floor of 5 reports, and one at the floor", () => {
    expect(rowPercent(4, 4, MIN_REPORTS_FOR_RATE - 1)).toBeNull();
    expect(rowPercent(4, 5, MIN_REPORTS_FOR_RATE)).toBe(80);
    expect(rowPercent(0, 0, 50)).toBeNull();
  });

  it("year totals are always shown in full, even when a year is tiny", () => {
    const tiny = clone();
    const y = tiny.years[0];
    y.total.totals.reports = 3;
    y.total.totals.H1 = { adds_up: 3, doesnt: 0, cant_check: 0 };
    expect(yearGlance(y).h1).toBe(100);
  });

  it("gives the glance row a dash (null), not zero, for a year with no federal figures", () => {
    const y2526 = FIXTURE_SNAPSHOT.years.find((y) => y.cds_year === "2025-26")!;
    expect(y2526.federal_fall_loaded).toBe(false);
    expect(yearGlance(y2526).matchRate).toBeNull();
    const y2425 = FIXTURE_SNAPSHOT.years.find((y) => y.cds_year === "2024-25")!;
    expect(yearGlance(y2425).matchRate).toBeGreaterThan(0);
  });
});

describe("lede", () => {
  it("states the snapshot date and the published population from the snapshot", () => {
    const lede = qualityLede(FIXTURE_SNAPSHOT);
    expect(lede.populations).toContain("November 24, 2026");
    expect(lede.populations).toContain(`${publishedTotal(FIXTURE_SNAPSHOT)} reports published`);
    expect(lede.populations).toContain("three years");
  });
});

describe("renewal tile", () => {
  it("equals renewal.both over renewal.previous", () => {
    const tile = renewalTile(FIXTURE_SNAPSHOT.renewal);
    expect(tile.share).toBe(FIXTURE_SNAPSHOT.renewal.both / FIXTURE_SNAPSHOT.renewal.previous);
    expect(tile.percent).toBe(76);
    expect(tile.sentence).toBe(
      "Of the 479 schools with a 2024-25 report on file, 364 also have a 2025-26 report on file.",
    );
  });
});

describe("data quality CSV", () => {
  const y2324 = FIXTURE_SNAPSHOT.years.find((y) => y.cds_year === "2023-24")!;
  const y2526 = FIXTURE_SNAPSHOT.years.find((y) => y.cds_year === "2025-26")!;

  it("opens with the real header on row 1: no comment block, no notice", () => {
    for (const table of ["reports", "federal", "totals"] as const) {
      const csv = buildQualityCsv(table, y2324);
      expect(csv.startsWith("format,")).toBe(true);
      expect(csv).not.toContain("#");
    }
  });

  it("has one line per format plus the year total, with public labels", () => {
    const csv = buildQualityCsv("reports", y2324);
    const lines = csv.split("\r\n").filter(Boolean);
    expect(lines[0]).toBe(
      "format,published,set_aside,couldnt_read,not_read_yet,fields_stored_median,fields_stored_lowest_10pct",
    );
    expect(lines).toHaveLength(1 + y2324.rows.length + 1);
    expect(lines[1].startsWith("standard PDF,300,3,4,0,")).toBe(true);
    expect(lines.at(-1)!.startsWith("All formats,")).toBe(true);
    expect(csv).not.toContain("pdf_flat");
  });

  it("writes blank, not 0, for fields stored when a format has no published reports", () => {
    const year = JSON.parse(JSON.stringify(y2324));
    year.rows[0].status.published = 0;
    year.rows[0].fields_stored = { median: 0, p10: 0 };
    const lines = buildQualityCsv("reports", year).split("\r\n").filter(Boolean);
    expect(lines[1]).toBe("standard PDF,0,3,4,0,,");
  });

  it("labels formats from the shared map, not the label in the file", () => {
    const year = JSON.parse(JSON.stringify(y2324));
    year.rows[0].label = "STALE LABEL";
    const csv = buildQualityCsv("reports", year);
    expect(csv).not.toContain("STALE LABEL");
    expect(csv).toContain("\r\nstandard PDF,");
  });

  it("leaves federal cells blank, not zero, for a year with no federal figures", () => {
    const csv = buildQualityCsv("federal", y2526);
    const lines = csv.split("\r\n").filter(Boolean);
    expect(lines[1]).toBe("standard PDF,,,,,");
  });

  // Cells written by hand from the fixture's inputs (flat 50 / fillable 25 / sheets 3, 2024-25),
  // not read back from the builder. B1, C1 and H1 differ in every cell, so a swap shows.
  describe("exact cells, 2024-25", () => {
    const y2425 = FIXTURE_SNAPSHOT.years.find((y) => y.cds_year === "2024-25")!;
    const lines = (t: "reports" | "federal" | "totals") => buildQualityCsv(t, y2425).split("\r\n").filter(Boolean);

    it("reports", () => {
      expect(lines("reports")).toEqual([
        "format,published,set_aside,couldnt_read,not_read_yet,fields_stored_median,fields_stored_lowest_10pct",
        "standard PDF,50,2,0,0,700,400",
        "fillable PDF,25,0,0,0,900,650",
        "spreadsheet,3,0,0,0,1000,950",
        "All formats,78,2,0,0,776,501",
      ]);
    });

    it("federal", () => {
      expect(lines("federal")).toEqual([
        "format,reports_checked,values_up_to_3_per_report,matches,no_value,differs",
        "standard PDF,49,147,135,6,6",
        "fillable PDF,25,75,72,2,1",
        "spreadsheet,3,9,8,1,0",
        "All formats,77,231,215,9,7",
      ]);
    });

    it("totals: each of B1, C1 and H1 lands in its own columns", () => {
      expect(lines("totals")).toEqual([
        "format,reports,B1_adds_up,B1_off_by_under_2pct,B1_off_by_more,B1_cant_check,C1_adds_up,C1_off_by_under_2pct,C1_off_by_more,C1_cant_check,H1_adds_up,H1_doesnt_add_up,H1_cant_check",
        "standard PDF,50,40,4,3,3,42,3,2,3,30,4,16",
        "fillable PDF,25,23,1,0,1,24,0,1,0,22,1,2",
        "spreadsheet,3,2,1,0,0,3,0,0,0,3,0,0",
        "All formats,78,65,6,3,4,69,3,3,3,55,5,18",
      ]);
    });
  });
});
