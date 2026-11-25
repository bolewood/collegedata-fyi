import { describe, expect, it } from "vitest";
import { FIXTURE_SNAPSHOT, FIXTURE_SNAPSHOT_V1, FIXTURE_SNAPSHOT_V2, FIXTURE_SNAPSHOT_V3,
  FIXTURE_SNAPSHOT_V4, emptyYear } from "./__fixtures__/data-quality-snapshot";
import {
  DATA_QUALITY_LAUNCH_DATE,
  MIN_REPORTS_FOR_RATE,
  SnapshotError,
  buildQualityCsv,
  compareYearsDesc,
  hasDifferenceSplit,
  hasFederalChecks,
  hasSections,
  sectionUsableShare,
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
  type QualityRow,
  type SectionRow,
  type QualityYear,
  type QualitySnapshot,
} from "./data-quality";
import { formatLabel } from "./format-labels";

const anyRec = (v: unknown) => v as Record<string, unknown>;
const clone = (): QualitySnapshot => JSON.parse(JSON.stringify(FIXTURE_SNAPSHOT));
const withDate = (iso: string): QualitySnapshot => ({ ...clone(), snapshot_of: iso });

describe("size of federal differences (public_format 2)", () => {
  const clone1 = (): QualitySnapshot => JSON.parse(JSON.stringify(FIXTURE_SNAPSHOT_V1));
  const select = (snap: QualitySnapshot) => selectSnapshot([{ name: "x.json", json: snap }]);
  const KEYS = ["differs_2_to_10pct", "differs_over_10pct"] as const;

  it.each(KEYS)("requires %s on format 2, in a row and in the total", (key) => {
    for (const target of ["row", "total"] as const) {
      const snap = clone();
      const r = target === "row" ? snap.years[0].rows[0] : snap.years[0].total;
      delete r.federal[key];
      expect(() => select(snap)).toThrow(new RegExp(key));
    }
  });

  it.each(KEYS)("requires %s even where the count is zero (a no-federal year's row and total)", (key) => {
    for (const target of ["row", "total"] as const) {
      const snap = clone();
      const y = snap.years.find((x) => !x.federal_fall_loaded)!;
      const r = target === "row" ? y.rows[0] : y.total;
      expect(r.federal[key]).toBe(0);
      delete r.federal[key];
      expect(() => select(snap)).toThrow(new RegExp(`${key} must be a non-negative integer`));
    }
  });

  it.each(KEYS)("refuses %s on format 1", (key) => {
    const snap = clone1();
    snap.years[0].total.federal[key] = 0;
    expect(() => select(snap)).toThrow(/unexpected key/);
  });

  it("reads a format 1 snapshot that has no split", () => {
    expect(select(clone1()).years[0].total.federal.differs_over_10pct).toBeUndefined();
  });

  it("refuses a row whose parts don't add up to its differs, even when the total follows the row", () => {
    const row = clone();
    row.years[0].rows[0].federal.differs_over_10pct! += 1;
    row.years[0].total.federal.differs_over_10pct! += 1;
    expect(() => select(row)).toThrow(/row pdf_flat: federal differs_2_to_10pct \+ differs_over_10pct is not differs/);
  });

  it.each(KEYS)("refuses a total whose %s isn't the sum of the rows", (key) => {
    const snap = clone();
    snap.years[0].total.federal[key]! += 1;
    expect(() => select(snap)).toThrow(new RegExp(`total federal\\.${key}`));
  });

  it("requires the split to be zero in a year with no federal figures", () => {
    const snap = clone();
    const y = snap.years.find((x) => !x.federal_fall_loaded)!;
    y.total.federal.differs_over_10pct = 1;
    y.rows[0].federal.differs_over_10pct = 1;
    expect(() => select(snap)).toThrow(/no federal figures/);
  });

  it("is reported by hasDifferenceSplit", () => {
    expect(FIXTURE_SNAPSHOT.years.every(hasDifferenceSplit)).toBe(true);
    expect(FIXTURE_SNAPSHOT_V1.years.some(hasDifferenceSplit)).toBe(false);
  });
});

describe("fields and usable answers by section (public_format 3)", () => {
  const select = (snap: QualitySnapshot) => selectSnapshot([{ name: "x.json", json: snap }]);
  const bad = (mutate: (s: QualitySnapshot) => void, why: RegExp) => {
    const snap = clone();
    mutate(snap);
    expect(() => select(snap)).toThrow(why);
  };
  const sec = (s: QualitySnapshot) => s.years[0].sections!;
  const y2425 = FIXTURE_SNAPSHOT.years.find((y) => y.cds_year === "2024-25")!;

  it("is required on format 3 and refused on formats 1 and 2", () => {
    bad((s) => delete s.years[0].sections, /sections is missing/);
    const two = JSON.parse(JSON.stringify(FIXTURE_SNAPSHOT_V2)) as QualitySnapshot;
    two.years[0].sections = sec(clone());
    expect(() => select(two)).toThrow(/unexpected key sections on public_format 2/);
    const one = JSON.parse(JSON.stringify(FIXTURE_SNAPSHOT_V1)) as QualitySnapshot;
    one.years[0].sections = sec(clone());
    expect(() => select(one)).toThrow(/unexpected key sections on public_format 1/);
    expect(select(FIXTURE_SNAPSHOT_V2).years[0].sections).toBeUndefined();
  });

  it("has exactly the keys it lists, with counts as integers", () => {
    bad((s) => ((sec(s) as unknown as Record<string, number>).extra = 1), /unexpected key extra/);
    bad((s) => ((sec(s).rows[0] as unknown as Record<string, number>).extra = 1), /unexpected key extra/);
    bad((s) => delete (sec(s).rows[0] as Partial<SectionRow>).usable_median, /usable_median must be a non-negative integer/);
    bad((s) => (sec(s).rows[0].usable_median = -1), /usable_median must be a non-negative integer/);
    bad((s) => ((sec(s).rows[0] as unknown as Record<string, unknown>).stored_median = "9"), /stored_median/);
    bad((s) => ((sec(s) as unknown as Record<string, unknown>).reports = 1.5), /reports/);
  });

  it("refuses a snapshot that leaves a section out, in the middle or at the end", () => {
    bad((s) => sec(s).rows.pop(), /9 sections, not all of A to J/);
    bad((s) => sec(s).rows.splice(3, 1), /9 sections, not all of A to J/);
  });

  it("refuses an unknown, repeated or out-of-order section", () => {
    bad((s) => (sec(s).rows[0].section = "Z"), /unknown section "Z"/);
    bad((s) => (sec(s).rows[1].section = "A"), /section A is out of order or listed twice/);
    bad((s) => ([sec(s).rows[0], sec(s).rows[1]] = [sec(s).rows[1], sec(s).rows[0]]), /out of order/);
  });

  it("holds each median between zero, usable <= stored <= questions", () => {
    bad((s) => (sec(s).rows[2].stored_median = sec(s).rows[2].questions + 1), /section C stores more fields than the form has questions/);
    bad((s) => (sec(s).rows[2].usable_median = sec(s).rows[2].stored_median + 1), /section C has more usable answers than fields stored/);
    bad((s) => (sec(s).rows[2].questions = 0), /section C has no questions/);
  });

  it("makes the sections' questions add up to the form's, and the reports to published minus other numbering", () => {
    bad((s) => (sec(s).rows[0].questions += 1), /questions add up to 1054, not the form's 1053/);
    // 2023-24 has 12 reports numbered by another form: 400 + 4 + 3 + ... published, none of those in sections.
    bad((s) => (sec(s).reports += 1), /sections\.reports is \d+, not published minus other_form_numbering/);
    bad((s) => (s.years[0].other_form_numbering += 1), /sections\.reports is/);
  });

  it("requires the section letter to be text, and zero medians when there are no reports", () => {
    bad((s) => ((sec(s).rows[0] as unknown as Record<string, unknown>).section = 7), /a section letter must be text/);
  });

  it("accepts a year with no full field schema and no rows, and a year with reports 0 and zero medians", () => {
    const none = clone();
    const y = none.years[0];
    y.form.full_field_schema = false;
    y.sections = { reports: 0, rows: [] };
    expect(select(none).years[0].sections!.rows).toEqual([]);
    const empty = clone();
    empty.years.push(emptyYear("2026-27"));
    expect(select(empty).years.at(-1)!.sections!.reports).toBe(0);
    const bad0 = clone();
    const e = emptyYear("2026-27");
    e.sections!.rows[0].stored_median = 1;
    bad0.years.push(e);
    expect(() => select(bad0)).toThrow(/section A has a median but no reports/);
  });

  it("has rows exactly when the form has a full field schema", () => {
    bad((s) => (sec(s).rows = []), /rows are present exactly when the form has a full field schema/);
    bad((s) => (s.years[0].form.full_field_schema = false), /rows are present exactly when/);
  });

  it("reports whether a year has the table, and hides the share under 5 reports", () => {
    expect(FIXTURE_SNAPSHOT.years.every(hasSections)).toBe(true);
    expect(FIXTURE_SNAPSHOT_V2.years.some(hasSections)).toBe(false);
    const row = { section: "B", questions: 200, stored_median: 100, usable_median: 50 };
    expect(sectionUsableShare(row, MIN_REPORTS_FOR_RATE)).toBe(25);
    expect(sectionUsableShare(row, MIN_REPORTS_FOR_RATE - 1)).toBeNull();
    expect(sectionUsableShare(row, 0)).toBeNull();
  });

  it("writes the by-section CSV from hand-worked cells (2024-25: half the questions stored, usable = stored minus the section's position)", () => {
    expect(buildQualityCsv("sections", y2425).split("\r\n").filter(Boolean)).toEqual([
      "section,section_name,questions,reports,fields_stored_median,usable_answers_median,usable_share_of_questions_pct",
      "A,General information,51,78,25,25,49",
      "B,Enrollment and persistence,219,78,109,108,49",
      "C,\"First-time, first-year admission\",278,78,139,137,49",
      "D,Transfer admission,73,78,36,33,45",
      "E,Academic offerings and policies,32,78,16,12,38",
      "F,Student life,60,78,30,25,42",
      "G,Annual expenses,47,78,23,17,36",
      "H,Financial aid,154,78,77,70,45",
      "I,Instructional faculty and class size,49,78,24,16,33",
      "J,Disciplinary areas of degrees conferred,120,78,60,51,43",
    ]);
  });

  it("leaves the medians and share blank, not zero, for a year with no reports, and the share blank under 5", () => {
    const empty = emptyYear("2026-27");
    expect(buildQualityCsv("sections", empty).split("\r\n")[1]).toBe("A,General information,51,0,,,");
    const small = JSON.parse(JSON.stringify(y2425)) as QualityYear;
    small.sections!.reports = 4;
    expect(buildQualityCsv("sections", small).split("\r\n")[1]).toBe("A,General information,51,4,25,25,");
  });
});

describe("enrollment and tuition against federal figures (public_format 4)", () => {
  const select = (snap: QualitySnapshot) => selectSnapshot([{ name: "x.json", json: snap }]);
  const bad = (mutate: (s: QualitySnapshot) => void, why: RegExp) => {
    const snap = clone();
    mutate(snap);
    expect(() => select(snap)).toThrow(why);
  };
  const y = (s: QualitySnapshot, year = "2023-24") => s.years.find((x) => x.cds_year === year)!;
  const NAMES = ["enrollment", "tuition"] as const;
  const KEYS = ["reports", "matches", "no_value", "differs", "differs_2_to_10pct", "differs_over_10pct"] as const;

  it("is required on format 4 and refused on formats 1 to 3, in rows, totals and years", () => {
    bad((s) => delete y(s).rows[0].checks, /checks is missing/);
    bad((s) => delete y(s).total.checks, /checks is missing/);
    bad((s) => delete y(s).federal_checks, /federal_checks is missing/);
    for (const snap of [FIXTURE_SNAPSHOT_V1, FIXTURE_SNAPSHOT_V2, FIXTURE_SNAPSHOT_V3]) {
      const withRow = JSON.parse(JSON.stringify(snap)) as QualitySnapshot;
      withRow.years[0].total.checks = clone().years[0].total.checks;
      expect(() => select(withRow)).toThrow(/unexpected key checks on public_format/);
      const withYear = JSON.parse(JSON.stringify(snap)) as QualitySnapshot;
      withYear.years[0].federal_checks = clone().years[0].federal_checks;
      expect(() => select(withYear)).toThrow(/unexpected key federal_checks on public_format/);
    }
    expect(select(FIXTURE_SNAPSHOT_V3).years.some(hasFederalChecks)).toBe(false);
  });

  it.each(NAMES.flatMap((n) => KEYS.map((k) => [n, k] as const)))("requires %s %s, even in a row whose count is zero", (name, key) => {
    for (const target of ["a counted row", "a zero row"] as const) {
      const snap = clone();
      const r = target === "a counted row" ? y(snap).rows[0] : y(snap, "2025-26").rows[0];
      delete (r.checks![name] as Partial<Record<string, number>>)[key];
      expect(() => select(snap)).toThrow(new RegExp(`checks\\.${name}: ${key} must be a non-negative integer`));
    }
  });

  it("has exactly the keys it lists", () => {
    bad((s) => ((y(s).total.checks!.enrollment as unknown as Record<string, number>).values = 1), /unexpected key values/);
    bad((s) => ((y(s).total.checks as unknown as Record<string, unknown>).other = {}), /checks: unexpected key other/);
    bad((s) => ((y(s).federal_checks!.tuition as unknown as Record<string, number>).extra = 1), /unexpected key extra/);
    bad((s) => ((y(s).federal_checks as unknown as Record<string, unknown>).other = {}), /federal_checks: unexpected key other/);
    bad((s) => ((y(s).federal_checks!.tuition as unknown as Record<string, unknown>).loaded = "yes"), /loaded must be a boolean/);
    bad((s) => delete (y(s).federal_checks as Partial<Record<string, unknown>>).tuition, /federal_checks\.tuition is missing/);
  });

  it("makes matches + no value + differs equal reports, and the split equal differs, in a row and the total", () => {
    for (const name of NAMES) {
      bad((s) => { y(s).rows[0].checks![name].reports += 1; y(s).total.checks![name].reports += 1; }, new RegExp(`${name} matches \\+ no_value \\+ differs is not reports`));
      bad((s) => { y(s).rows[0].checks![name].differs_over_10pct += 1; y(s).total.checks![name].differs_over_10pct += 1; }, new RegExp(`${name} differs_2_to_10pct \\+ differs_over_10pct is not differs`));
    }
  });

  it("makes each total the sum of its rows", () => {
    for (const name of NAMES) {
      for (const key of KEYS) {
        const snap = clone();
        y(snap).total.checks![name][key] += 1;
        expect(() => select(snap)).toThrow(new RegExp(`total checks\\.${name}\\.${key} is`));
      }
    }
  });

  it("keeps reports within published, and reports checked + left out equal to published when loaded", () => {
    bad((s) => {
      const r = y(s).rows[0].checks!.enrollment;
      const pub = y(s).rows[0].status.published;
      const d = pub + 1 - r.reports;
      r.reports += d; r.matches += d;
      y(s).total.checks!.enrollment.reports += d; y(s).total.checks!.enrollment.matches += d;
    }, /enrollment reports exceeds published/);
    bad((s) => (y(s).federal_checks!.enrollment.no_federal_figures += 1), /reports checked \+ left out don't add up/);
    bad((s) => (y(s).federal_checks!.tuition.single_campus += 1), /reports checked \+ left out don't add up/);
  });

  it("counts a shared file among the reports left out, and requires the format 5 keys (and refuses them before 5)", () => {
    bad((s) => (y(s).federal_checks!.enrollment.shared_file = 1), /reports checked \+ left out don't add up/);
    bad((s) => (y(s).federal_left_out.shared_file = 1), /federal reports checked \+ left out don't add up/);
    bad((s) => delete (y(s).federal_left_out as { shared_file?: number }).shared_file, /shared_file must be a non-negative integer/);
    bad((s) => delete y(s).federal_checks!.tuition.shared_file, /shared_file must be a non-negative integer/);
    bad((s) => delete y(s).duplicate_file, /duplicate_file must be a non-negative integer/);
    const v4 = () => JSON.parse(JSON.stringify(FIXTURE_SNAPSHOT_V4)) as QualitySnapshot;
    expect(() => select(v4())).not.toThrow();
    for (const mutate of [
      (s: QualitySnapshot) => (y(s).duplicate_file = 0),
      (s: QualitySnapshot) => (y(s).federal_left_out.shared_file = 0),
      (s: QualitySnapshot) => (y(s).federal_checks!.enrollment.shared_file = 0),
    ]) {
      const snap = v4();
      mutate(snap);
      expect(() => select(snap)).toThrow(/unexpected key/);
    }
  });

  it("requires zero counts in a year with no IPEDS figures for a check, and the right IPEDS year", () => {
    bad((s) => {
      for (const r of [y(s, "2024-25").rows[0], y(s, "2024-25").total]) { r.checks!.tuition.reports = 1; r.checks!.tuition.matches = 1; }
    }, /counts are not zero for a year with no IPEDS figures/);
    bad((s) => (y(s, "2024-25").federal_checks!.tuition.data_year = 2024), /data_year is 2024, not 2025/);
    bad((s) => (y(s).federal_checks!.enrollment.data_year = 2024), /data_year is 2024, not 2023/);
  });

  it("still checks who was left out where IPEDS figures aren't loaded, and that one campus can't exceed the published", () => {
    bad((s) => (y(s, "2024-25").federal_checks!.tuition.no_federal_figures = 1), /no_federal_figures must be 0 for a year with no IPEDS figures/);
    bad((s) => (y(s, "2025-26").federal_checks!.enrollment.single_campus = y(s, "2025-26").total.status.published + 1), /single_campus \+ shared_file exceeds the total's published/);
    // A shared file counts toward the bound too, in a year where nothing is loaded.
    bad((s) => (y(s, "2025-26").federal_checks!.enrollment.shared_file = y(s, "2025-26").total.status.published + 1), /single_campus \+ shared_file exceeds the total's published/);
    bad((s) => {
      const info = y(s, "2025-26").federal_checks!.enrollment;
      info.single_campus = y(s, "2025-26").total.status.published;
      info.shared_file = 1;
    }, /single_campus \+ shared_file exceeds the total's published/);
    // The fixture itself: a year with no IPEDS admissions figures leaves nobody out as one campus (as Table B).
    expect(y(FIXTURE_SNAPSHOT, "2025-26").federal_checks).toEqual({
      enrollment: { loaded: false, data_year: 2025, single_campus: 0, shared_file: 0, no_federal_figures: 0 },
      tuition: { loaded: false, data_year: 2026, single_campus: 0, shared_file: 0, no_federal_figures: 0 },
    });
  });

  it("reports which years have the checks", () => {
    expect(FIXTURE_SNAPSHOT.years.every(hasFederalChecks)).toBe(true);
    expect(y(FIXTURE_SNAPSHOT, "2024-25").federal_checks).toEqual({
      enrollment: { loaded: true, data_year: 2024, single_campus: 1, shared_file: 0, no_federal_figures: 0 },
      tuition: { loaded: false, data_year: 2025, single_campus: 1, shared_file: 0, no_federal_figures: 0 },
    });
  });

  it("writes the enrollment and tuition CSVs from hand-worked cells, and blanks, not zeros, where nothing is loaded", () => {
    const y2425 = y(FIXTURE_SNAPSHOT, "2024-25");
    const head = "format,reports_checked,matches,no_value,differs,differs_over_2pct_to_10pct,differs_over_10pct";
    // Fixture: of the reports Table B checked, a fifth have no value, a tenth differ, 60% of those 2% to 10% off (rounded down).
    expect(buildQualityCsv("enrollment", y2425).split("\r\n").filter(Boolean)).toEqual([
      head, "standard PDF,49,36,9,4,2,2", "fillable PDF,25,18,5,2,1,1", "spreadsheet,3,3,0,0,0,0", "All formats,77,57,14,6,3,3",
    ]);
    expect(buildQualityCsv("tuition", y2425).split("\r\n").filter(Boolean)).toEqual([
      head, "standard PDF,,,,,,", "fillable PDF,,,,,,", "spreadsheet,,,,,,", "All formats,,,,,,",
    ]);
    // 2023-24 (300 + 100 + 3 published; 299 + 100 + 3 checked by Table B; tuition on 90% of them, 30% no value, 20% differing).
    expect(buildQualityCsv("tuition", y(FIXTURE_SNAPSHOT)).split("\r\n").filter(Boolean)).toEqual([
      head, "standard PDF,269,136,80,53,31,22", "fillable PDF,90,45,27,18,10,8", "spreadsheet,2,2,0,0,0,0", "All formats,361,183,107,71,41,30",
    ]);
    expect(buildQualityCsv("enrollment", y(FIXTURE_SNAPSHOT)).split("\r\n").filter(Boolean)).toEqual([
      head, "standard PDF,299,211,59,29,17,12", "fillable PDF,100,70,20,10,6,4", "spreadsheet,3,3,0,0,0,0", "All formats,402,284,79,39,23,16",
    ]);
  });
});

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
    expect(selectSnapshot(files).snapshot_of).toBe("2026-11-24T12:25:03Z");
  });

  it("fails on two files with the same date", () => {
    const files = [
      { name: "a.json", json: withDate("2026-11-24T01:00:00Z") },
      { name: "b.json", json: withDate("2026-11-24T23:00:00Z") },
    ];
    expect(() => selectSnapshot(files)).toThrow(/same date 2026-11-24/);
  });

  it("fails on an empty directory", () => {
    expect(() => selectSnapshot([])).toThrow(SnapshotError);
  });

  it("fails on a public_format the page doesn't know, even before launch", () => {
    const bad = { ...clone(), public_format: 6 };
    expect(() => selectSnapshot([{ name: "x.json", json: bad }])).toThrow(/public_format/);
  });

  it("reads public_format 1 to 5", () => {
    expect(selectSnapshot([{ name: "one.json", json: FIXTURE_SNAPSHOT_V1 }]).public_format).toBe(1);
    expect(selectSnapshot([{ name: "two.json", json: FIXTURE_SNAPSHOT_V2 }]).public_format).toBe(2);
    expect(selectSnapshot([{ name: "three.json", json: FIXTURE_SNAPSHOT_V3 }]).public_format).toBe(3);
    expect(selectSnapshot([{ name: "four.json", json: FIXTURE_SNAPSHOT_V4 }]).public_format).toBe(4);
    expect(selectSnapshot([{ name: "five.json", json: FIXTURE_SNAPSHOT }]).public_format).toBe(5);
  });

  it("fails on a snapshot with no renewal block or an empty renewal denominator", () => {
    const noBlock: Record<string, unknown> = { ...clone() };
    delete noBlock.renewal;
    expect(() => selectSnapshot([{ name: "x.json", json: noBlock }])).toThrow(/renewal/);
    const zero = clone();
    zero.renewal.previous = 0;
    zero.renewal.both = 0;
    expect(() => selectSnapshot([{ name: "x.json", json: zero }])).toThrow(/denominator/);
  });
});

describe("snapshot validation", () => {
  const bad = (mutate: (s: QualitySnapshot) => void, why: RegExp) => {
    const snap = clone();
    mutate(snap);
    expect(() => selectSnapshot([{ name: "x.json", json: snap }])).toThrow(why);
  };

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

  it("fails when renewal.both exceeds previous even though current could hold it", () => {
    bad((s) => {
      s.renewal.both = s.renewal.previous + 1;
      s.renewal.current = s.renewal.both + 10;
    }, /renewal\.both exceeds/);
  });

  it("fails when renewal.both exceeds current even though previous could hold it", () => {
    bad((s) => {
      s.renewal.previous = s.renewal.current + 10;
      s.renewal.both = s.renewal.current + 1;
    }, /renewal\.both exceeds/);
  });

  it("fails when a renewal count is negative or not an integer", () => {
    bad((s) => (s.renewal.both = -1), /renewal/);
    bad((s) => (s.renewal.current = 10.5), /renewal/);
    bad((s) => (s.renewal.previous = 479.2), /renewal/);
  });
});

describe("snapshot arithmetic", () => {
  const bad = (mutate: (s: QualitySnapshot) => void, why: RegExp) => {
    const snap = clone();
    mutate(snap);
    expect(() => selectSnapshot([{ name: "x.json", json: snap }])).toThrow(why);
  };
  /** Apply the same change to a format row and to the year total, so only the rule under test is broken. */
  const both = (s: QualitySnapshot, change: (r: QualityRow) => void) => {
    change(s.years[0].rows[0]);
    change(s.years[0].total);
  };

  it("fails when a format row's statuses don't add up to the year's live count", () => {
    // The total's live count is the sum of the rows', so one row off alone makes the total's status wrong.
    bad((s) => (s.years[0].rows[0].status.set_aside += 1), /total status\.set_aside/);
    bad((s) => (s.years[0].total.status.published += 1), /total status\.published/);
  });

  it("fails when the total isn't the sum of the rows, in a status, federal or totals count", () => {
    bad((s) => {
      // Moves one report between two statuses, so the live count is right and only the split is wrong.
      s.years[0].total.status.couldnt_read += 1;
      s.years[0].total.status.set_aside -= 1;
    }, /total status\.(set_aside|couldnt_read)/);
    bad((s) => (s.years[0].total.federal.reports += 1), /total federal\.reports/);
    bad((s) => (s.years[0].total.totals.C1.off_more += 1), /total totals\.C1\.off_more/);
    bad((s) => (s.years[0].total.totals.H1.doesnt += 1), /total totals\.H1\.doesnt/);
  });

  it("fails when federal matches + no value + differs isn't values", () => {
    bad((s) => both(s, (r) => (r.federal.values += 1)), /matches \+ no_value \+ differs/);
  });

  it("fails when federal values exceed 3 per report", () => {
    bad((s) => {
      // Fewer reports checked, same values: moved in the row and the total by the same amount.
      const row = s.years[0].rows[0];
      const drop = row.federal.reports - 1;
      row.federal.reports -= drop;
      s.years[0].total.federal.reports -= drop;
    }, /3 per report/);
  });

  it("fails when more reports were checked against federal figures than are published", () => {
    bad((s) => both(s, (r) => (r.federal.reports = r.status.published + 1)), /federal\.reports exceeds published/);
  });

  it("fails when B1, C1 or H1 outcomes don't add up to the reports", () => {
    bad((s) => both(s, (r) => (r.totals.B1.adds_up += 1)), /B1 outcomes/);
    bad((s) => both(s, (r) => (r.totals.C1.cant_check += 1)), /C1 outcomes/);
    bad((s) => both(s, (r) => (r.totals.H1.cant_check += 1)), /H1 outcomes/);
  });

  it("fails when totals.reports isn't the published count (a glance rate could pass 100%)", () => {
    bad((s) => both(s, (r) => (r.totals.reports += 1)), /totals\.reports is not status\.published/);
  });


  it("fails when the set-aside reasons don't add up to the set-aside count", () => {
    bad((s) => (s.years[0].set_aside_reasons.wrong_file += 1), /set_aside_reasons/);
  });

  it("fails when, for a year with federal figures, checked + left out isn't the published count", () => {
    bad((s) => (s.years[0].federal_left_out.single_campus += 1), /checked \+ left out/);
  });

  it("doesn't ask a year with no federal figures to add up checked + left out", () => {
    const snap = clone();
    const y = snap.years.find((x) => !x.federal_fall_loaded)!;
    expect(y.federal_left_out.single_campus + y.federal_left_out.no_federal_figures + y.total.federal.reports).not.toBe(y.total.status.published);
    expect(() => selectSnapshot([{ name: "x.json", json: snap }])).not.toThrow();
  });

  it("refuses a key nothing reads, even when the named sums still add up", () => {
    // B1.typo = 1 with adds_up one lower: Object.values would still sum to the reports, so the key is refused by name.
    const typo = (r: QualityRow) => {
      r.totals.B1.adds_up -= 1;
      (r.totals.B1 as unknown as Record<string, number>).typo = 1;
    };
    bad((s) => both(s, typo), /unexpected key typo/);
    bad((s) => ((s.years[0].rows[0].status as unknown as Record<string, number>).extra = 0), /unexpected key extra/);
    bad((s) => ((s.years[0].rows[0].federal as unknown as Record<string, number>).extra = 0), /unexpected key extra/);
    bad((s) => ((s.years[0].total.federal as unknown as Record<string, number>).differs_over_20pct = 0), /unexpected key differs_over_20pct/);
    bad((s) => ((s.years[0].rows[0].totals.H1 as unknown as Record<string, number>).extra = 0), /unexpected key extra/);
  });

  describe("years the page can't show yet (#516)", () => {
    // The shape the producer writes for an earlier year (test_scoreboard.py test_public_for_a_year_with_no_checks):
    // no checked field mapping, so the sum tables can't be read, and federal figures are loaded but not compared.
    const earlierYear = (published: number) => {
      const row = {
        status: { published, set_aside: 0, couldnt_read: 0, not_read_yet: 0 },
        fields_stored: { median: 8, p10: 8 },
        federal: { reports: 0, values: 0, matches: 0, no_value: 0, differs: 0 },
        totals: {
          reports: published,
          B1: { adds_up: 0, under_2pct: 0, off_more: 0, cant_check: published },
          C1: { adds_up: 0, under_2pct: 0, off_more: 0, cant_check: published },
          H1: { adds_up: 0, doesnt: 0, cant_check: published },
        },
      };
      return {
        cds_year: "2022-23",
        form: { form_year: "2022-23", full_field_schema: false, questions: 0 },
        federal_fall_loaded: true,
        other_form_numbering: 0,
        removed: 0,
        no_file: 0,
        sum_checks_unavailable: ["B1", "C1", "H1"],
        set_aside_reasons: { blank_form: 0, too_little_read: 0, wrong_file: 0 },
        federal_left_out: { single_campus: 0, no_federal_figures: 0, not_compared: published },
        rows: [{ format: "pdf_flat", label: "standard PDF", ...row }],
        total: row,
      };
    };

    it("refuses a producer-shaped earlier year, naming #516", () => {
      bad((s) => s.years.push(earlierYear(3) as unknown as QualityYear), /#516/);
    });

    it("refuses sum_checks_unavailable on its own, and not_compared on its own", () => {
      bad((s) => ((anyRec(s.years[0]).sum_checks_unavailable = ["B1"])), /sum_checks_unavailable.*#516/);
      bad((s) => ((anyRec(s.years[0].federal_left_out).not_compared = 1)), /not_compared.*#516/);
    });

    it("accepts not_compared of 0 (the producer omits it, but it is a count)", () => {
      const snap = clone();
      anyRec(snap.years[0].federal_left_out).not_compared = 0;
      expect(() => selectSnapshot([{ name: "x.json", json: snap }])).not.toThrow();
    });
  });

  it("accepts a year with no documents: no rows, all-zero totals (the producer writes one for a new form year)", () => {
    const snap = clone();
    snap.years.push(emptyYear("2026-27"));
    const picked = selectSnapshot([{ name: "x.json", json: snap }]);
    expect(picked.years.find((y) => y.cds_year === "2026-27")!.rows).toEqual([]);
  });

  it("fails a year with no rows whose totals aren't zero", () => {
    const snap = clone();
    const y = emptyYear("2026-27");
    y.total.status.published = 1;
    y.total.totals.reports = 1;
    y.total.totals.B1.adds_up = 1;
    y.total.totals.C1.adds_up = 1;
    y.total.totals.H1.adds_up = 1;
    snap.years.push(y);
    expect(() => selectSnapshot([{ name: "x.json", json: snap }])).toThrow(/total status\.published is 1, but the rows add up to 0/);
  });

  it("requires every federal count to be zero in a year with no federal figures", () => {
    bad((s) => {
      // Same change in a row and the total, so only this rule is broken: one report "checked" against nothing.
      const y = s.years.find((x) => !x.federal_fall_loaded)!;
      for (const r of [y.rows[0], y.total]) {
        r.federal.reports += 1;
        r.federal.values += 1;
        r.federal.matches += 1;
      }
    }, /no federal figures/);
  });

  it("accepts the unmodified fixture", () => {
    expect(selectSnapshot([{ name: "x.json", json: clone() }]).years.length).toBeGreaterThan(0);
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
    expect(lines[0]).toBe("format,reports_checked,values_up_to_3_per_report,matches,no_value,differs,differs_over_2pct_to_10pct,differs_over_10pct");
    expect(lines[1]).toBe("standard PDF,,,,,,,");
  });

  it("writes the two size columns only for a public_format 2 year", () => {
    const y1 = FIXTURE_SNAPSHOT_V1.years.find((y) => y.cds_year === "2024-25")!;
    expect(buildQualityCsv("federal", y1).split("\r\n")[0]).toBe("format,reports_checked,values_up_to_3_per_report,matches,no_value,differs");
    expect(buildQualityCsv("federal", y1).split("\r\n")[1]).toBe("standard PDF,49,120,50,10,60");
    const y1blank = FIXTURE_SNAPSHOT_V1.years.find((y) => y.cds_year === "2025-26")!;
    expect(buildQualityCsv("federal", y1blank).split("\r\n")[1]).toBe("standard PDF,,,,,");
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
        "format,reports_checked,values_up_to_3_per_report,matches,no_value,differs,differs_over_2pct_to_10pct,differs_over_10pct",
        // The fixture puts floor(60%) of the differences in the 2% to 10% band: 36 of 60, 17 of 29, 0 of 0.
        "standard PDF,49,120,50,10,60,36,24",
        "fillable PDF,25,64,30,5,29,17,12",
        "spreadsheet,3,9,8,1,0,0,0",
        "All formats,77,193,88,16,89,53,36",
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
