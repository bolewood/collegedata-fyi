// Test-only snapshot that follows the PRD 040 public JSON shape. The real
// snapshots live in web/src/data/data-quality/ and are committed after each
// scoreboard run. These numbers are invented for tests.

import type {
  QualityFormatRow,
  QualityRow,
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
    },
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
    federal: { reports: 0, values: 0, matches: 0, no_value: 0, differs: 0 },
    totals: {
      reports: 0,
      B1: { adds_up: 0, under_2pct: 0, off_more: 0, cant_check: 0 },
      C1: { adds_up: 0, under_2pct: 0, off_more: 0, cant_check: 0 },
      H1: { adds_up: 0, doesnt: 0, cant_check: 0 },
    },
  };
  for (const r of rows) {
    for (const k of Object.keys(total.status) as (keyof typeof total.status)[]) total.status[k] += r.status[k];
    for (const k of Object.keys(total.federal) as (keyof typeof total.federal)[]) total.federal[k] += r.federal[k];
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

function year(
  cds_year: string,
  rows: QualityFormatRow[],
  extra: Partial<QualityYear> & { form: QualityYear["form"] },
): QualityYear {
  return {
    cds_year,
    federal_fall_loaded: true,
    other_form_numbering: 0,
    removed: 2,
    no_file: 0,
    set_aside_reasons: { blank_form: 1, too_little_read: 1, wrong_file: 0 },
    federal_left_out: { single_campus: 1, no_federal_figures: 2 },
    rows,
    total: sumRows(rows),
    ...extra,
  };
}

const flat = (published: number, extra: Partial<RowSpec> = {}) =>
  row({
    format: "pdf_flat", label: "standard PDF", published, median: 700, p10: 400,
    federal: [published - 1, (published - 1) * 3 - 12, 6, 6],
    b1: [published - 10, 4, 3, 3], c1: [published - 8, 3, 2, 3], h1: [published - 20, 4, 16],
    ...extra,
  });

const fillable = (published: number) =>
  row({
    format: "pdf_fillable", label: "fillable PDF", published, median: 900, p10: 650,
    federal: [published, published * 3 - 3, 2, 1],
    b1: [published - 2, 1, 0, 1], c1: [published - 1, 0, 1, 0], h1: [published - 3, 1, 2],
  });

/** Three reports in a spreadsheet: a group under the floor of 5. */
const sheets = () =>
  row({
    format: "xlsx", label: "spreadsheet", published: 3, median: 1000, p10: 950,
    federal: [3, 8, 1, 0], b1: [2, 1, 0, 0], c1: [3, 0, 0, 0], h1: [3, 0, 0],
  });

export const FIXTURE_SNAPSHOT: QualitySnapshot = {
  public_format: 1,
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
    year("2023-24", [flat(60, { set_aside: 3, couldnt_read: 4 }), fillable(30), sheets()], {
      form: { form_year: "2023-24", full_field_schema: true, questions: 1053 },
      other_form_numbering: 12,
      removed: 4,
    }),
    year("2025-26", [flat(40, { not_read_yet: 1 }), fillable(20)], {
      form: { form_year: "2025-26", full_field_schema: true, questions: 1105 },
      federal_fall_loaded: false,
      federal_left_out: { single_campus: 0, no_federal_figures: 0 },
    }),
    year("2024-25", [flat(50, { set_aside: 2 }), fillable(25), sheets()], {
      form: { form_year: "2024-25", full_field_schema: true, questions: 1083 },
    }),
  ],
};
