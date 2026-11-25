// Test-only snapshot that follows the PRD 040 public JSON shape. The real
// snapshots live in web/src/data/data-quality/ and are committed after each
// scoreboard run. These numbers are invented for tests.

import type {
  CheckCounts,
  CheckInfo,
  CheckName,
  ChecksBlock,
  QualityFormatRow,
  QualityRow,
  QualitySections,
  QualitySnapshot,
  QualityYear,
} from "../data-quality";

type RowSpec = {
  format: string;
  label: string;
  published: number;
  set_aside?: number;
  couldnt_read?: number;
  not_read_yet?: number;
  median: number;
  p10: number;
  federal: [reports: number, matches: number, no_value: number, differs: number];
  b1: [number, number, number, number];
  c1: [number, number, number, number];
  h1: [number, number, number];
};

const ZERO_CHECK: CheckCounts = { reports: 0, matches: 0, no_value: 0, differs: 0, differs_2_to_10pct: 0, differs_over_10pct: 0 };

/**
 * Invented counts for one extra check, one value per report, over the reports Table B checked (`compared`): of `reports` checked, a fifth (rounded down) have no
 * value and a tenth differ (rounded down), 60% of those differing 2% to 10% off (rounded down), the rest over 10%.
 * Tuition is checked on 9 of 10 reports (rounded down), with 30% no value and 20% differing.
 */
function checkCounts(check: CheckName, compared: number): CheckCounts {
  const reports = check === "enrollment" ? compared : Math.floor(compared * 0.9);
  const noValue = Math.floor(reports * (check === "enrollment" ? 0.2 : 0.3));
  const differs = Math.floor(reports * (check === "enrollment" ? 0.1 : 0.2));
  const small = Math.floor(differs * 0.6);
  return { reports, matches: reports - noValue - differs, no_value: noValue, differs, differs_2_to_10pct: small, differs_over_10pct: differs - small };
}

function row(s: RowSpec): QualityFormatRow {
  return {
    format: s.format,
    label: s.label,
    status: {
      published: s.published,
      set_aside: s.set_aside ?? 0,
      couldnt_read: s.couldnt_read ?? 0,
      not_read_yet: s.not_read_yet ?? 0,
    },
    fields_stored: { median: s.median, p10: s.p10 },
    federal: {
      reports: s.federal[0],
      values: s.federal[1] + s.federal[2] + s.federal[3],
      matches: s.federal[1],
      no_value: s.federal[2],
      differs: s.federal[3],
      // About 60% of the differences are 2% to 10% off, the rest over 10%.
      differs_2_to_10pct: Math.floor(s.federal[3] * 0.6),
      differs_over_10pct: s.federal[3] - Math.floor(s.federal[3] * 0.6),
    },
    checks: { enrollment: checkCounts("enrollment", s.federal[0]), tuition: checkCounts("tuition", s.federal[0]) },
    totals: {
      reports: s.published,
      B1: { adds_up: s.b1[0], under_2pct: s.b1[1], off_more: s.b1[2], cant_check: s.b1[3] },
      C1: { adds_up: s.c1[0], under_2pct: s.c1[1], off_more: s.c1[2], cant_check: s.c1[3] },
      H1: { adds_up: s.h1[0], doesnt: s.h1[1], cant_check: s.h1[2] },
    },
  };
}

function sumRows(rows: QualityFormatRow[]): QualityRow {
  const total: QualityRow = {
    status: { published: 0, set_aside: 0, couldnt_read: 0, not_read_yet: 0 },
    fields_stored: { median: 0, p10: 0 },
    federal: { reports: 0, values: 0, matches: 0, no_value: 0, differs: 0, differs_2_to_10pct: 0, differs_over_10pct: 0 },
    checks: { enrollment: { ...ZERO_CHECK }, tuition: { ...ZERO_CHECK } },
    totals: {
      reports: 0,
      B1: { adds_up: 0, under_2pct: 0, off_more: 0, cant_check: 0 },
      C1: { adds_up: 0, under_2pct: 0, off_more: 0, cant_check: 0 },
      H1: { adds_up: 0, doesnt: 0, cant_check: 0 },
    },
  };
  for (const r of rows) {
    for (const name of ["enrollment", "tuition"] as const) {
      for (const k of Object.keys(ZERO_CHECK) as (keyof CheckCounts)[]) total.checks![name][k] += r.checks![name][k];
    }
    for (const k of Object.keys(total.status) as (keyof typeof total.status)[]) total.status[k] += r.status[k];
    for (const k of Object.keys(total.federal) as (keyof typeof total.federal)[]) total.federal[k] = (total.federal[k] ?? 0) + (r.federal[k] ?? 0);
    total.totals.reports += r.totals.reports;
    for (const t of ["B1", "C1"] as const) {
      for (const k of Object.keys(total.totals[t]) as (keyof typeof total.totals.B1)[]) total.totals[t][k] += r.totals[t][k];
    }
    for (const k of Object.keys(total.totals.H1) as (keyof typeof total.totals.H1)[]) total.totals.H1[k] += r.totals.H1[k];
  }
  // Pooled median is not meaningful for fixtures: weight by published reports.
  const pub = total.status.published || 1;
  total.fields_stored.median = Math.round(rows.reduce((n, r) => n + r.fields_stored.median * r.status.published, 0) / pub);
  total.fields_stored.p10 = Math.round(rows.reduce((n, r) => n + r.fields_stored.p10 * r.status.published, 0) / pub);
  return total;
}

// Questions per CDS section A to J on each form (schemas/cds_schema_<year>.json); they add up to the form's questions.
const SECTION_QUESTIONS: Record<string, number[]> = {
  "2023-24": [51, 196, 274, 70, 32, 60, 47, 154, 49, 120],
  "2024-25": [51, 219, 278, 73, 32, 60, 47, 154, 49, 120],
  "2025-26": [63, 204, 278, 88, 34, 58, 46, 165, 49, 120],
};

/**
 * Invented medians, easy to check by hand: half a section's questions are stored (rounded down), and usable answers
 * are that many minus the section's position in A to J (A none, B one, ... J nine), never below zero.
 */
function sections(cds_year: string, reports: number): QualitySections {
  return {
    reports,
    rows: SECTION_QUESTIONS[cds_year].map((questions, i) => {
      const stored = Math.floor(questions / 2);
      return { section: "ABCDEFGHIJ"[i], questions, stored_median: stored, usable_median: Math.max(0, stored - i) };
    }),
  };
}

/** Which extra checks have IPEDS figures loaded, by CDS year (as in the 2026-11-25 run): enrollment for the first two years, tuition for the first only. */
const CHECKS_LOADED: Record<string, Record<CheckName, boolean>> = {
  "2023-24": { enrollment: true, tuition: true },
  "2024-25": { enrollment: true, tuition: false },
  "2025-26": { enrollment: false, tuition: false },
};

function year(
  cds_year: string,
  rows: QualityFormatRow[],
  extra: Partial<QualityYear> & { form: QualityYear["form"] },
): QualityYear {
  const loadedChecks = CHECKS_LOADED[cds_year];
  // A check with no IPEDS figures has zero counts everywhere.
  const zeroed = (c: ChecksBlock): ChecksBlock => ({
    enrollment: loadedChecks.enrollment ? c.enrollment : { ...ZERO_CHECK },
    tuition: loadedChecks.tuition ? c.tuition : { ...ZERO_CHECK },
  });
  rows = rows.map((r) => ({ ...r, checks: zeroed(r.checks!) }));
  const total = sumRows(rows);
  const federal = extra.federal_fall_loaded ?? true;
  return {
    cds_year,
    federal_fall_loaded: true,
    other_form_numbering: 0,
    removed: 2,
    no_file: 0,
    duplicate_file: 0,
    rows,
    total,
    // The reasons add up to the set-aside count, and Table B's reports checked plus the reports left out add up to
    // the published count (nothing is left out of a year with no federal figures).
    set_aside_reasons: {
      blank_form: Math.ceil(total.status.set_aside / 2),
      too_little_read: Math.floor(total.status.set_aside / 2),
      wrong_file: 0,
    },
    federal_left_out: { single_campus: federal ? total.status.published - total.federal.reports : 0, shared_file: 0, no_federal_figures: 0 },
    ...extra,
    // One campus or unit is left out of both checks, as of Table B; the rest of the published reports are checked or have no figure.
    federal_checks: Object.fromEntries(
      (["enrollment", "tuition"] as const).map((name): [CheckName, CheckInfo] => {
        // As Table B: one campus or unit is left out when IPEDS admissions figures are loaded, and nothing is when they are not.
        const single = federal ? total.status.published - total.federal.reports : 0;
        const loaded = loadedChecks[name];
        return [name, { loaded, data_year: Number(cds_year.slice(0, 4)) + (name === "tuition" ? 1 : 0), single_campus: single, shared_file: 0, no_federal_figures: loaded ? total.status.published - total.checks![name].reports - single : 0 }];
      }),
    ) as Record<CheckName, CheckInfo>,
    // The reports numbered by the year's own form: published minus those numbered by another form.
    sections: sections(cds_year, total.status.published - (extra.other_form_numbering ?? 0)),
  };
}

const flat = (published: number, extra: Partial<RowSpec> = {}) =>
  row({
    format: "pdf_flat", label: "standard PDF", published, median: 700, p10: 400,
    federal: [published - 1, (published - 1) * 3 - 12, 6, 6],
    b1: [published - 10, 4, 3, 3], c1: [published - 8, 3, 2, 3], h1: [published - 20, 4, 16],
    ...extra,
  });

const fillable = (published: number, extra: Partial<RowSpec> = {}) =>
  row({
    format: "pdf_fillable", label: "fillable PDF", published, median: 900, p10: 650,
    federal: [published, published * 3 - 3, 2, 1],
    b1: [published - 2, 1, 0, 1], c1: [published - 1, 0, 1, 0], h1: [published - 3, 1, 2],
    ...extra,
  });

/** Three reports in a spreadsheet: a group under the floor of 5. */
const sheets = () =>
  row({
    format: "xlsx", label: "spreadsheet", published: 3, median: 1000, p10: 950,
    federal: [3, 8, 1, 0], b1: [2, 1, 0, 0], c1: [3, 0, 0, 0], h1: [3, 0, 0],
  });

export const FIXTURE_SNAPSHOT: QualitySnapshot = {
  public_format: 5,
  snapshot_of: "2026-11-24T12:25:03Z",
  scoreboard_run: "scoreboard-20261124T122503Z.json",
  renewal: {
    current_year: "2025-26",
    previous_year: "2024-25",
    current: 372,
    previous: 479,
    both: 364,
  },
  years: [
    // 2023-24 is sized like the 2026-11-25 run's pools: 217 financial aid "can't check" reports, and with 2024-25 219
    // differing admissions values (130 + 89).
    year("2023-24", [flat(300, { set_aside: 3, couldnt_read: 4, h1: [75, 35, 190], federal: [299, 700, 60, 100] }), fillable(100, { h1: [60, 13, 27], federal: [100, 250, 20, 30] }), sheets()], {
      form: { form_year: "2023-24", full_field_schema: true, questions: 1053 },
      other_form_numbering: 12,
      removed: 4,
    }),
    // No federal figures for the year: every federal count is zero, as the producer writes it.
    year("2025-26", [flat(40, { not_read_yet: 1, federal: [0, 0, 0, 0] }), fillable(20, { federal: [0, 0, 0, 0] })], {
      form: { form_year: "2025-26", full_field_schema: true, questions: 1105 },
      federal_fall_loaded: false,
    }),
    year("2024-25", [flat(50, { set_aside: 2, federal: [49, 50, 10, 60] }), fillable(25, { federal: [25, 30, 5, 29] }), sheets()], {
      form: { form_year: "2024-25", full_field_schema: true, questions: 1083 },
    }),
  ],
};

/** A full-schema year with no documents (test_scoreboard.py builds this 2026-27 shape): no rows, every count zero but removed and no_file. */
export const emptyYear = (cds_year: string): QualityYear => {
  const sums = { adds_up: 0, under_2pct: 0, off_more: 0, cant_check: 0 };
  return {
    cds_year,
    form: { form_year: cds_year, full_field_schema: true, questions: 1053 },
    federal_fall_loaded: false,
    other_form_numbering: 0,
    removed: 1,
    no_file: 1,
    duplicate_file: 0,
    set_aside_reasons: { blank_form: 0, too_little_read: 0, wrong_file: 0 },
    federal_left_out: { single_campus: 0, shared_file: 0, no_federal_figures: 0 },
    rows: [],
    federal_checks: {
      enrollment: { loaded: false, data_year: Number(cds_year.slice(0, 4)), single_campus: 0, shared_file: 0, no_federal_figures: 0 },
      tuition: { loaded: false, data_year: Number(cds_year.slice(0, 4)) + 1, single_campus: 0, shared_file: 0, no_federal_figures: 0 },
    },
    sections: { reports: 0, rows: SECTION_QUESTIONS["2023-24"].map((questions, i) => ({ section: "ABCDEFGHIJ"[i], questions, stored_median: 0, usable_median: 0 })) },
    total: {
      status: { published: 0, set_aside: 0, couldnt_read: 0, not_read_yet: 0 },
      fields_stored: { median: 0, p10: 0 },
      federal: { reports: 0, values: 0, matches: 0, no_value: 0, differs: 0, differs_2_to_10pct: 0, differs_over_10pct: 0 },
      checks: { enrollment: { ...ZERO_CHECK }, tuition: { ...ZERO_CHECK } },
      totals: { reports: 0, B1: { ...sums }, C1: { ...sums }, H1: { adds_up: 0, doesnt: 0, cant_check: 0 } },
    },
  };
};

/** The same snapshot as public_format 4 wrote it: no shared-file or duplicate-file counts. */
export const FIXTURE_SNAPSHOT_V4: QualitySnapshot = (() => {
  const v4: QualitySnapshot = JSON.parse(JSON.stringify(FIXTURE_SNAPSHOT));
  v4.public_format = 4;
  for (const y of v4.years) {
    delete y.duplicate_file;
    delete y.federal_left_out.shared_file;
    for (const info of Object.values(y.federal_checks!)) delete info.shared_file;
  }
  return v4;
})();

/** The same snapshot as public_format 3 wrote it: sections, no enrollment and tuition checks. */
export const FIXTURE_SNAPSHOT_V3: QualitySnapshot = (() => {
  const v3: QualitySnapshot = JSON.parse(JSON.stringify(FIXTURE_SNAPSHOT_V4));
  v3.public_format = 3;
  for (const y of v3.years) {
    delete y.federal_checks;
    for (const r of [...y.rows, y.total]) delete r.checks;
  }
  return v3;
})();

/** The same snapshot as public_format 2 wrote it: the size split, no sections. */
export const FIXTURE_SNAPSHOT_V2: QualitySnapshot = (() => {
  const v2: QualitySnapshot = JSON.parse(JSON.stringify(FIXTURE_SNAPSHOT_V3));
  v2.public_format = 2;
  for (const y of v2.years) delete y.sections;
  return v2;
})();

/** The same snapshot as public_format 1 wrote it: no size split and no sections. */
export const FIXTURE_SNAPSHOT_V1: QualitySnapshot = (() => {
  const v1: QualitySnapshot = JSON.parse(JSON.stringify(FIXTURE_SNAPSHOT_V2));
  v1.public_format = 1;
  for (const y of v1.years) {
    for (const r of [...y.rows, y.total]) {
      delete r.federal.differs_2_to_10pct;
      delete r.federal.differs_over_10pct;
    }
  }
  return v1;
})();
