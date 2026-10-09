import { beforeEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

const supabaseMocks = vi.hoisted(() => ({
  from: vi.fn(),
}));

vi.mock("./supabase", () => ({
  supabase: { from: supabaseMocks.from },
  STORAGE_BASE_URL: "https://example.test/storage/v1/object/public/sources",
}));

import { fetchMatchBuilderSchools } from "./queries";

type QueryResult = { data: unknown[] | null; error: { message: string } | null };
type RecordedQuery = { table: string; ins: Array<[string, unknown]> };

function mockMatchQueries(results: Record<string, QueryResult>) {
  const recorded: RecordedQuery[] = [];
  supabaseMocks.from.mockImplementation((table: string) => {
    const call: RecordedQuery = { table, ins: [] };
    recorded.push(call);
    const result = results[table] ?? { data: [], error: null };
    const query = {
      select: () => query,
      range: () => query,
      gte: () => query,
      is: () => query,
      in: (col: string, vals: unknown) => {
        call.ins.push([col, vals]);
        return query;
      },
      order: () => query,
      then: (
        onFulfilled: (value: QueryResult) => unknown,
        onRejected?: (reason: unknown) => unknown,
      ) => Promise.resolve(result).then(onFulfilled, onRejected),
    };
    return query;
  });
  return recorded;
}

const browserRow = {
  document_id: "doc-1",
  school_id: "alpha",
  school_name: "Alpha College",
  canonical_year: "2025-26",
  year_start: 2025,
  acceptance_rate: 0.4,
  sat_submit_rate: 0.55,
  act_submit_rate: 0.2,
  sat_composite_p25: 1200,
  sat_composite_p50: 1300,
  sat_composite_p75: 1400,
  act_composite_p25: 26,
  act_composite_p50: 29,
  act_composite_p75: 32,
  data_quality_flag: null,
  archive_url: "https://example.test/alpha.pdf",
  ipeds_id: "100001",
};

const enrichment = {
  institution_directory: {
    data: [{ school_id: "alpha", state: "IL", control: 2 }],
    error: null,
  },
  scorecard_summary: {
    data: [{ ipeds_id: "100001", carnegie_basic: 21 }],
    error: null,
  },
} satisfies Record<string, QueryResult>;

describe("fetchMatchBuilderSchools", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.spyOn(console, "warn").mockImplementation(() => {});
  });

  it("loads GPA rows without a school_id IN list", async () => {
    const recorded = mockMatchQueries({
      school_browser_rows: { data: [browserRow], error: null },
      ...enrichment,
      cds_fields: {
        data: [
          { school_id: "alpha", field_id: "C.1201", value_num: 3.86, value_text: null, year_start: 2025 },
          { school_id: "alpha", field_id: "C.1202", value_num: 0.72, value_text: null, year_start: 2025 },
        ],
        error: null,
      },
    });

    await expect(fetchMatchBuilderSchools()).resolves.toEqual([
      expect.objectContaining({
        schoolId: "alpha",
        avgHsGpa: 3.86,
        hsGpaSubmitRate: 0.72,
        state: "IL",
      }),
    ]);
    expect(recorded.find((call) => call.table === "cds_fields")?.ins).toEqual([
      ["field_id", ["C.1201", "C.1202"]],
    ]);
  });

  it("keeps /match usable when cds_fields times out", async () => {
    mockMatchQueries({
      school_browser_rows: { data: [browserRow], error: null },
      ...enrichment,
      cds_fields: {
        data: null,
        error: { message: "canceling statement due to statement timeout" },
      },
    });

    await expect(fetchMatchBuilderSchools()).resolves.toEqual([
      expect.objectContaining({ schoolId: "alpha", avgHsGpa: null }),
    ]);
  });

  it("returns an empty list when browser rows fail", async () => {
    mockMatchQueries({
      school_browser_rows: {
        data: null,
        error: { message: "canceling statement due to statement timeout" },
      },
    });

    await expect(fetchMatchBuilderSchools()).resolves.toEqual([]);
  });
});

describe("/match page rendering contract", () => {
  it("stays on hourly ISR and does not read searchParams on the server", () => {
    const page = readFileSync(fileURLToPath(new URL("../app/match/page.tsx", import.meta.url)), "utf8");
    expect(page).toContain("export const revalidate = 3600");
    expect(page).toContain("export default async function MatchPage()");
    expect(page).not.toMatch(/searchParams:/);
    expect(page).not.toMatch(/initialCode=/);
  });
});
