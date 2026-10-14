import { beforeEach, describe, expect, it, vi } from "vitest";

const queryMocks = vi.hoisted(() => ({
  fetchInstitutionCoverage: vi.fn(),
  fetchSchoolBrandColors: vi.fn(),
  fetchSchoolDocuments: vi.fn(),
  fetchSchoolFederalBaselineIndex: vi.fn(),
  fetchSchoolFederalFacts: vi.fn(),
  fetchScorecardByIpedsId: vi.fn(),
  fetchScorecardByIpedsIds: vi.fn(),
  fetchFsaNonpaymentBySchoolId: vi.fn(),
}));

vi.mock("./queries", () => queryMocks);
vi.mock("./supabase-friendly-api", () => ({
  friendlyApiSupabase: {
    from: () => {
      const query: Record<string, unknown> = {};
      const self = () => query;
      for (const method of ["select", "eq", "gte", "is", "order", "limit", "in"]) {
        query[method] = self;
      }
      query.maybeSingle = async () => ({ data: null, error: null });
      return query;
    },
    rpc: vi.fn(),
  },
}));
vi.mock("./supabase", () => ({
  STORAGE_BASE_URL: "https://example.test/storage/v1/object/public/sources",
}));

import { compareSchools, getSchoolFacts } from "./public-data";

const scorecards = {
  "100001": { ipeds_id: "100001", avg_net_price: 11111, scorecard_data_year: 2023 },
  "100002": { ipeds_id: "100002", avg_net_price: 22222, scorecard_data_year: 2023 },
};

describe("compareSchools scorecard batching", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    queryMocks.fetchSchoolDocuments.mockResolvedValue([]);
    queryMocks.fetchSchoolFederalFacts.mockResolvedValue([]);
    queryMocks.fetchFsaNonpaymentBySchoolId.mockResolvedValue(null);
    queryMocks.fetchInstitutionCoverage.mockImplementation(async (schoolId: string) => ({
      school_id: schoolId,
      school_name: schoolId === "alpha" ? "Alpha College" : "Beta College",
      ipeds_id: schoolId === "alpha" ? "100001" : "100002",
    }));
    queryMocks.fetchScorecardByIpedsId.mockImplementation(async (ipedsId: string | null) =>
      ipedsId ? (scorecards[ipedsId as keyof typeof scorecards] ?? null) : null,
    );
    queryMocks.fetchScorecardByIpedsIds.mockImplementation(async (ipedsIds: Array<string | null>) => {
      const out = new Map();
      for (const id of ipedsIds) {
        if (id && id in scorecards) out.set(id, scorecards[id as keyof typeof scorecards]);
      }
      return out;
    });
  });

  it("fetches scorecard once for the set and keeps getSchoolFacts values", async () => {
    const compared = await compareSchools(["alpha", "beta"], { fields: ["avg_net_price"] });
    expect(queryMocks.fetchScorecardByIpedsIds).toHaveBeenCalledTimes(1);
    expect(queryMocks.fetchScorecardByIpedsIds).toHaveBeenCalledWith(["100001", "100002"]);
    expect(queryMocks.fetchScorecardByIpedsId).not.toHaveBeenCalled();

    const alpha = await getSchoolFacts("alpha", { fields: ["avg_net_price"] });
    expect(compared.rows[0].values.avg_net_price).toEqual(
      alpha?.facts.find((fact) => fact.key === "avg_net_price"),
    );
    expect(compared.rows[1].values.avg_net_price.value).toBe(22222);
  });
});
