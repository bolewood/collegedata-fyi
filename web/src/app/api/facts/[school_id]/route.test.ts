import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  fetchCanonicalSchoolId: vi.fn(),
  fetchSchoolDocuments: vi.fn(),
  fetchExtract: vi.fn(),
  fetchSchoolYearFacts: vi.fn(),
}));

vi.mock("@/lib/queries", () => ({
  fetchCanonicalSchoolId: mocks.fetchCanonicalSchoolId,
  fetchSchoolDocuments: mocks.fetchSchoolDocuments,
  fetchExtract: mocks.fetchExtract,
  fetchSchoolYearFacts: mocks.fetchSchoolYearFacts,
}));

import { GET } from "./route";

const v = (value: string) => ({ value });

// Regression for #267. The legacy endpoint used to read C.116/C.117/C.120 from
// the raw extract for every year, but those question numbers mean different
// things in different CDS template years.
const AMHERST_2024 = {
  doc: { document_id: "d-amh", extraction_status: "extracted", school_name: "Amherst College", canonical_year: "2024-25", source_format: "pdf_flat", source_url: "https://x/amh.pdf" },
  schemaVersion: "2024-25",
  // 2024-25 numbering: C.117 applied, C.118 admitted, C.119 enrolled;
  // C.116 is an unrelated cell and C.120 is a different applied cell.
  values: { "C.116": v("0"), "C.117": v("13,743"), "C.118": v("1,000"), "C.119": v("450"), "C.120": v("7"), "B.101": v("200"), "B.126": v("210") },
  row: { document_id: "d-amh", canonical_year: "2024-25", dataQualityFlag: null, applied: 13743, admitted: 1000, enrolledFirstYear: 450 },
};
const PRINCETON_2025 = {
  doc: { document_id: "d-pri", extraction_status: "extracted", school_name: "Princeton University", canonical_year: "2025-26", source_format: "pdf_flat", source_url: "https://x/pri.pdf" },
  schemaVersion: "2025-26",
  // 2025-26 numbering: C.116 applied, C.117 admitted, C.118 enrolled; C.120 is
  // a different admitted cell, which the old code called "enrolled".
  values: { "C.116": v("40,000"), "C.117": v("2,000"), "C.118": v("1,300"), "C.120": v("229"), "B.101": v("700"), "B.126": v("650") },
  row: { document_id: "d-pri", canonical_year: "2025-26", dataQualityFlag: null, applied: 40000, admitted: 2000, enrolledFirstYear: 1300 },
};

type Row = typeof AMHERST_2024.row;
type Fixture = {
  doc: typeof AMHERST_2024.doc;
  schemaVersion: string;
  values: Record<string, { value: string }>;
  row: Row;
};

function setup(f: Fixture, row: Row | null = f.row) {
  mocks.fetchSchoolDocuments.mockResolvedValue([f.doc]);
  mocks.fetchExtract.mockResolvedValue({
    canonical: { notes: { schema_version: f.schemaVersion } },
    fallback: null,
    mergedValues: f.values,
  });
  mocks.fetchSchoolYearFacts.mockResolvedValue(row ? [row] : []);
}

async function get(id: string) {
  mocks.fetchCanonicalSchoolId.mockResolvedValue(id);
  const res = await GET(new Request(`https://www.collegedata.fyi/api/facts/${id}`), {
    params: Promise.resolve({ school_id: id }),
  });
  return { res, body: await res.json() };
}

describe("GET /api/facts/{school_id} (legacy)", () => {
  beforeEach(() => vi.clearAllMocks());

  it("2024-25: counts come from the projection, not C.116/C.117/C.120", async () => {
    setup(AMHERST_2024);
    const { body } = await get("amherst");
    expect(body.applied).toBe(13743);
    expect(body.admitted).toBe(1000);
    expect(body.enrolled).toBe(450);
    expect(body.acceptance_rate_pct).toBe(7.3);
    expect(body.yield_rate_pct).toBe(45);
  });

  it("2024-25: raw never publishes a value under a key that means something else", async () => {
    setup(AMHERST_2024);
    const { body } = await get("amherst");
    expect(body.raw).toEqual({
      C_116_applied_total: null,
      C_117_admitted_total: null,
      C_120_enrolled_total: null,
      B_101_ft_men_enrolled: null,
      B_126_ft_women_enrolled: null,
    });
    expect(typeof body.raw_note).toBe("string");
    expect(body.raw_note).toContain("/api/schools/amherst/facts");
  });

  it("2025-26: counts come from the projection, C.120 is not enrolled", async () => {
    setup(PRINCETON_2025);
    const { body } = await get("princeton");
    expect(body.applied).toBe(40000);
    expect(body.admitted).toBe(2000);
    expect(body.enrolled).toBe(1300);
    expect(body.yield_rate_pct).toBe(65);
    expect(body.acceptance_rate_pct).toBe(5);
  });

  it("2025-26: raw keeps C.116/C.117 (they mean applied/admitted) and nulls the rest", async () => {
    setup(PRINCETON_2025);
    const { body } = await get("princeton");
    expect(body.raw.C_116_applied_total).toBe("40,000");
    expect(body.raw.C_117_admitted_total).toBe("2,000");
    expect(body.raw.C_120_enrolled_total).toBeNull();
    expect(body.raw.B_101_ft_men_enrolled).toBeNull();
    expect(body.raw.B_126_ft_women_enrolled).toBeNull();
  });

  it("2026-27: raw keeps C.116/C.117, which the 2026-27 template numbers the same way", async () => {
    setup({ ...PRINCETON_2025, schemaVersion: "2026-27" });
    const { body } = await get("princeton");
    expect(body.raw.C_116_applied_total).toBe("40,000");
    expect(body.raw.C_117_admitted_total).toBe("2,000");
    expect(body.raw.C_120_enrolled_total).toBeNull();
  });

  it("uses the extract's schema_version over canonical_year when they disagree", async () => {
    // A 2025-26 filing that used the 2024-25 template: C.116 is not applied.
    setup({ ...PRINCETON_2025, schemaVersion: "2024-25" });
    const { body } = await get("princeton");
    expect(body.raw.C_116_applied_total).toBeNull();
    expect(body.raw.C_117_admitted_total).toBeNull();
  });

  it("a missing projection row yields nulls and never falls back to question numbers", async () => {
    setup(PRINCETON_2025, null);
    const { body } = await get("princeton");
    expect(body.applied).toBeNull();
    expect(body.admitted).toBeNull();
    expect(body.enrolled).toBeNull();
    expect(body.acceptance_rate_pct).toBeNull();
    expect(body.yield_rate_pct).toBeNull();
  });

  it("prefers the newest dated filing over an unknown-year or wrong_file document", async () => {
    setup(AMHERST_2024);
    mocks.fetchSchoolDocuments.mockResolvedValue([
      { ...AMHERST_2024.doc, document_id: "d-unknown", canonical_year: "unknown" },
      { ...AMHERST_2024.doc, document_id: "d-wrong", canonical_year: "2025-26", data_quality_flag: "wrong_file" },
      { ...AMHERST_2024.doc, document_id: "d-sub", canonical_year: "2025-26", sub_institutional: "law" },
      AMHERST_2024.doc,
    ]);
    const { body } = await get("amherst");
    expect(body.cds_year).toBe("2024-25");
    expect(body.applied).toBe(AMHERST_2024.row.applied);
    expect(body.archive_url).toBe("https://www.collegedata.fyi/schools/amherst/2024-25");
  });

  it("falls back to the first extracted document when none is a dated whole-institution filing", async () => {
    setup(AMHERST_2024, null);
    mocks.fetchSchoolDocuments.mockResolvedValue([{ ...AMHERST_2024.doc, document_id: "d-unknown", canonical_year: "unknown" }]);
    const { res, body } = await get("amherst");
    expect(res.status).toBe(200);
    expect(body.cds_year).toBe("unknown");
    expect(body.applied).toBeNull();
  });

  it("a zero count gives no rate", async () => {
    setup(PRINCETON_2025, { ...PRINCETON_2025.row, enrolledFirstYear: 0 });
    const { body } = await get("princeton");
    expect(body.enrolled).toBe(0);
    expect(body.yield_rate_pct).toBeNull();
  });

  it("ignores projection rows for other documents", async () => {
    setup(PRINCETON_2025, { ...PRINCETON_2025.row, document_id: "other-doc" });
    const { body } = await get("princeton");
    expect(body.applied).toBeNull();
  });

  it("withholds counts that are internally inconsistent, like the newer endpoint", async () => {
    setup(AMHERST_2024, { ...AMHERST_2024.row, applied: 100, admitted: 500 });
    const { body } = await get("amherst");
    expect(body.applied).toBeNull();
    expect(body.admitted).toBeNull();
    expect(body.acceptance_rate_pct).toBeNull();
  });

  it("signals deprecation in the body and keeps the existing note and shape", async () => {
    setup(AMHERST_2024);
    const { res, body } = await get("amherst");
    expect(body.deprecated).toBe(true);
    expect(body.replacement).toBe("/api/schools/amherst/facts");
    expect(body.note).toContain("Pipeline source");
    expect(body.school_id).toBe("amherst");
    expect(body.cds_year).toBe("2024-25");
    expect(res.headers.get("Cache-Control")).toContain("s-maxage=3600");
  });
});
