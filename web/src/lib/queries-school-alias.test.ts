import { beforeEach, describe, expect, it, vi } from "vitest";

const supabaseMocks = vi.hoisted(() => ({
  from: vi.fn(),
}));

vi.mock("./supabase", () => ({
  supabase: { from: supabaseMocks.from },
  STORAGE_BASE_URL: "https://example.test/storage/v1/object/public/sources",
}));

import {
  fetchAdmissionStrategyBySchoolId,
  fetchBrowserRowBySchoolId,
  fetchCanonicalSchoolId,
  fetchInstitutionCoverage,
  fetchSchoolFederalBaselineIndex,
  fetchSchoolSlugResolver,
  fetchSchoolYearFacts,
  fetchScorecardByIpedsIds,
  resetSchoolQueryCachesForTests,
} from "./queries";

function pageQuery(result: unknown) {
  const query = { order: vi.fn(), range: vi.fn().mockResolvedValue(result) };
  query.order.mockReturnValue(query);
  supabaseMocks.from.mockReturnValue({ select: vi.fn(() => query) });
  return query;
}

function inQuery(result: unknown) {
  const query = { in: vi.fn(), order: vi.fn(), range: vi.fn().mockResolvedValue(result) };
  query.in.mockReturnValue(query);
  query.order.mockReturnValue(query);
  supabaseMocks.from.mockReturnValue({ select: vi.fn(() => query) });
  return query;
}

function coverageQuery(...results: unknown[]) {
  const maybeSingle = vi.fn();
  for (const result of results) {
    maybeSingle.mockResolvedValueOnce(result);
  }
  const eq = vi.fn(() => ({ maybeSingle }));
  const select = vi.fn(() => ({ eq }));
  supabaseMocks.from.mockReturnValue({ select });
  return { select, eq, maybeSingle };
}

describe("fetchCanonicalSchoolId", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetSchoolQueryCachesForTests();
  });

  it("resolves a reviewed retired alias without trusting live crosswalk state", async () => {
    await expect(fetchCanonicalSchoolId("tufts-university")).resolves.toBe("tufts");
    expect(supabaseMocks.from).not.toHaveBeenCalled();
  });

  it("resolves another unique alias from the cached crosswalk snapshot", async () => {
    const query = pageQuery({
      data: [
        {
          school_id: "bucknell",
          alias: "bucknell-university",
          is_primary: false,
          ipeds_id: "211440",
        },
      ],
      error: null,
    });

    await expect(fetchCanonicalSchoolId("bucknell-university")).resolves.toBe("bucknell");
    expect(supabaseMocks.from).toHaveBeenCalledWith("institution_slug_crosswalk");
    expect(query.range).toHaveBeenCalled();
  });

  it("returns null for an empty result", async () => {
    pageQuery({ data: [], error: null });
    await expect(fetchCanonicalSchoolId("missing-alias")).resolves.toBeNull();
  });

  it("throws when PostgREST reports an error", async () => {
    pageQuery({ data: null, error: { message: "crosswalk unavailable" } });
    await expect(fetchCanonicalSchoolId("errored-alias")).rejects.toThrow(
      "Failed to fetch school aliases: crosswalk unavailable",
    );
  });

  it("throws when the Supabase query throws", async () => {
    supabaseMocks.from.mockImplementation(() => {
      throw new Error("network failure");
    });
    await expect(fetchCanonicalSchoolId("throwing-alias")).rejects.toThrow("network failure");
  });
});

describe("crosswalk pagination", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetSchoolQueryCachesForTests();
  });

  it("throws if a later page errors so a truncated snapshot is never cached", async () => {
    const fullPage = Array.from({ length: 1000 }, (_, i) => ({
      school_id: "school",
      alias: `alias-${i}`,
      is_primary: true,
      ipeds_id: String(i),
    }));
    const query = {
      order: vi.fn(),
      range: vi
        .fn()
        .mockResolvedValueOnce({ data: fullPage, error: null })
        .mockResolvedValueOnce({ data: null, error: { message: "page 2 failed" } }),
    };
    query.order.mockReturnValue(query);
    supabaseMocks.from.mockReturnValue({ select: vi.fn(() => query) });

    await expect(fetchCanonicalSchoolId("alias-0")).rejects.toThrow(
      "Failed to fetch school aliases: page 2 failed",
    );
    expect(query.range).toHaveBeenCalledTimes(2);
  });
});

describe("fetchInstitutionCoverage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetSchoolQueryCachesForTests();
  });

  it("returns null only for a successful empty result", async () => {
    coverageQuery({ data: null, error: null });
    await expect(fetchInstitutionCoverage("missing-school")).resolves.toBeNull();
  });

  it("retries a statement timeout once and returns the row", async () => {
    coverageQuery(
      { data: null, error: { message: "canceling statement due to statement timeout" } },
      {
        data: {
          ipeds_id: "199032",
          school_id: "bard-college",
          school_name: "Bard College",
        },
        error: null,
      },
    );
    await expect(fetchInstitutionCoverage("bard-college")).resolves.toMatchObject({
      school_id: "bard-college",
    });
    expect(supabaseMocks.from).toHaveBeenCalledTimes(2);
  });

  it("throws after a repeated timeout so directory-only schools are not cached as 404s", async () => {
    coverageQuery(
      { data: null, error: { message: "canceling statement due to statement timeout" } },
      { data: null, error: { message: "canceling statement due to statement timeout" } },
    );
    await expect(fetchInstitutionCoverage("bard-college")).rejects.toThrow(
      "Failed to fetch institution coverage",
    );
    expect(supabaseMocks.from).toHaveBeenCalledTimes(2);
  });

  it("throws on a non-timeout PostgREST error without retrying", async () => {
    coverageQuery({
      data: null,
      error: { message: "TimeoutError: The operation was aborted" },
    });
    await expect(fetchInstitutionCoverage("bard-college")).rejects.toThrow(
      "Failed to fetch institution coverage",
    );
    expect(supabaseMocks.from).toHaveBeenCalledTimes(1);
  });
});

describe("fetchSchoolSlugResolver", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetSchoolQueryCachesForTests();
  });

  it("resolves aliases from a paged crosswalk read, not one request per alias", async () => {
    const query = pageQuery({
      data: [
        { school_id: "amherst", alias: "amherst-college", is_primary: false, ipeds_id: "164465" },
        { school_id: "bowdoin", alias: "bowdoin-college", is_primary: false, ipeds_id: "161004" },
      ],
      error: null,
    });
    const resolve = await fetchSchoolSlugResolver(["amherst-college", "bowdoin-college"]);
    expect(supabaseMocks.from).toHaveBeenCalledTimes(1);
    expect(supabaseMocks.from).toHaveBeenCalledWith("institution_slug_crosswalk");
    expect(query.range).toHaveBeenCalledTimes(1);
    expect(resolve("amherst-college")).toBe("amherst");
    expect(resolve("bowdoin-college")).toBe("bowdoin");
  });
});

describe("school browser hub collapse", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetSchoolQueryCachesForTests();
  });

  function mockCrosswalkAndBrowserRows(browserRows: unknown[]) {
    supabaseMocks.from.mockImplementation((table: string) => {
      if (table === "institution_slug_crosswalk") {
        const query = { order: vi.fn(), range: vi.fn().mockResolvedValue({ data: [], error: null }) };
        query.order.mockReturnValue(query);
        return { select: vi.fn(() => query) };
      }
      const query = {
        in: vi.fn(),
        is: vi.fn(),
        order: vi.fn(),
      };
      query.in.mockReturnValue(query);
      query.is.mockReturnValue(query);
      query.order.mockResolvedValue({ data: browserRows, error: null });
      return { select: vi.fn(() => query) };
    });
  }

  it("uses one school_browser_rows read and ignores pre-2024 rows for profile and strategy", async () => {
    mockCrosswalkAndBrowserRows([
      {
        document_id: "old",
        school_id: "bowdoin",
        school_name: "Bowdoin College",
        ipeds_id: "161004",
        canonical_year: "2023-24",
        year_start: 2023,
        sub_institutional: null,
        archive_url: null,
        data_quality_flag: null,
        applied: 10,
        admitted: 2,
        enrolled_first_year: 1,
        acceptance_rate: 0.2,
        sat_composite_p25: 1400,
        sat_composite_p75: 1520,
        act_composite_p25: 32,
        act_composite_p75: 35,
        ed_applicants: 9,
        ed_admitted: 3,
        wait_list_offered: null,
        wait_list_accepted: null,
        wait_list_admitted: null,
        admission_strategy_card_quality: "complete",
      },
      {
        document_id: "new",
        school_id: "bowdoin",
        school_name: "Bowdoin College",
        ipeds_id: "161004",
        canonical_year: "2024-25",
        year_start: 2024,
        sub_institutional: null,
        archive_url: "https://example.test/bowdoin",
        data_quality_flag: null,
        applied: 20,
        admitted: 4,
        enrolled_first_year: 2,
        acceptance_rate: 0.2,
        sat_composite_p25: 1410,
        sat_composite_p75: 1530,
        act_composite_p25: 33,
        act_composite_p75: 35,
        ed_applicants: 11,
        ed_admitted: 4,
        wait_list_offered: null,
        wait_list_accepted: null,
        wait_list_admitted: null,
        admission_strategy_card_quality: "complete",
      },
    ]);

    const facts = await fetchSchoolYearFacts("bowdoin");
    const profile = await fetchBrowserRowBySchoolId("bowdoin");
    const strategy = await fetchAdmissionStrategyBySchoolId("bowdoin");

    expect(facts.map((row) => row.yearStart)).toEqual([2024, 2023]);
    expect(profile?.documentId).toBe("new");
    expect(profile?.yearStart).toBe(2024);
    expect(strategy?.documentId).toBe("new");
    expect(strategy?.yearStart).toBe(2024);
  });
});

describe("fetchSchoolFederalBaselineIndex", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads every school in one school_facts_unified query", async () => {
    const query = inQuery({
      data: [
        { school_id: "mit", ipeds_id: "166683" },
        { school_id: "stanford", ipeds_id: "243744" },
      ],
      error: null,
    });
    const index = await fetchSchoolFederalBaselineIndex(["stanford", "mit", "stanford"]);
    expect(supabaseMocks.from).toHaveBeenCalledWith("school_facts_unified");
    expect(query.in).toHaveBeenCalledTimes(1);
    expect(query.in).toHaveBeenCalledWith("school_id", ["stanford", "mit"]);
    expect(index.get("mit")).toEqual({ ipeds_id: "166683" });
    expect(index.get("stanford")).toEqual({ ipeds_id: "243744" });
  });
});

describe("fetchScorecardByIpedsIds", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads every IPEDS id in one scorecard_summary query", async () => {
    const query = { in: vi.fn().mockResolvedValue({
      data: [
        { ipeds_id: "166683", avg_net_price: 19000 },
        { ipeds_id: "243744", avg_net_price: 21000 },
      ],
      error: null,
    }) };
    supabaseMocks.from.mockReturnValue({ select: vi.fn(() => query) });

    const index = await fetchScorecardByIpedsIds(["243744", "166683", "243744", null]);
    expect(supabaseMocks.from).toHaveBeenCalledTimes(1);
    expect(supabaseMocks.from).toHaveBeenCalledWith("scorecard_summary");
    expect(query.in).toHaveBeenCalledWith("ipeds_id", ["243744", "166683"]);
    expect(index.get("166683")).toEqual({ ipeds_id: "166683", avg_net_price: 19000 });
  });

  it("skips the network when no IPEDS ids are present", async () => {
    await expect(fetchScorecardByIpedsIds([null, undefined, ""])).resolves.toEqual(new Map());
    expect(supabaseMocks.from).not.toHaveBeenCalled();
  });
});
