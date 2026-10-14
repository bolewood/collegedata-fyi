import { beforeEach, describe, expect, it, vi } from "vitest";

const supabaseMocks = vi.hoisted(() => ({
  from: vi.fn(),
}));

vi.mock("./supabase", () => ({
  supabase: { from: supabaseMocks.from },
  STORAGE_BASE_URL: "https://example.test/storage/v1/object/public/sources",
}));

import {
  fetchCanonicalSchoolId,
  fetchSchoolFederalBaselineIndex,
  fetchSchoolSlugResolver,
  fetchScorecardByIpedsIds,
} from "./queries";

function aliasQueryResult(result: unknown) {
  const order = vi.fn().mockResolvedValue(result);
  const eq = vi.fn(() => ({ order }));
  const select = vi.fn(() => ({ eq }));
  supabaseMocks.from.mockReturnValue({ select });
  return { select, eq, order };
}

function inQuery(result: unknown) {
  const query = { in: vi.fn(), order: vi.fn(), range: vi.fn().mockResolvedValue(result) };
  query.in.mockReturnValue(query);
  query.order.mockReturnValue(query);
  supabaseMocks.from.mockReturnValue({ select: vi.fn(() => query) });
  return query;
}

function pageQuery(result: unknown) {
  const query = { order: vi.fn(), range: vi.fn().mockResolvedValue(result) };
  query.order.mockReturnValue(query);
  supabaseMocks.from.mockReturnValue({ select: vi.fn(() => query) });
  return query;
}

describe("fetchCanonicalSchoolId", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("resolves a reviewed retired alias without trusting live crosswalk state", async () => {
    await expect(fetchCanonicalSchoolId("tufts-university")).resolves.toBe("tufts");
    expect(supabaseMocks.from).not.toHaveBeenCalled();
  });

  it("queries the public crosswalk and resolves another unique alias", async () => {
    const query = aliasQueryResult({
      data: [
        {
          school_id: "bucknell",
          alias: "bucknell-university",
          is_primary: false,
        },
      ],
      error: null,
    });

    await expect(fetchCanonicalSchoolId("bucknell-university")).resolves.toBe("bucknell");
    expect(supabaseMocks.from).toHaveBeenCalledWith("institution_slug_crosswalk");
    expect(query.select).toHaveBeenCalledWith("school_id, alias, is_primary");
    expect(query.eq).toHaveBeenCalledWith("alias", "bucknell-university");
    expect(query.order).toHaveBeenCalledWith("is_primary", { ascending: false });
  });

  it("returns null for an empty result", async () => {
    aliasQueryResult({ data: [], error: null });
    await expect(fetchCanonicalSchoolId("missing-alias")).resolves.toBeNull();
  });

  it("returns null when PostgREST reports an error", async () => {
    aliasQueryResult({ data: null, error: { message: "crosswalk unavailable" } });
    await expect(fetchCanonicalSchoolId("errored-alias")).resolves.toBeNull();
  });

  it("returns null when the Supabase query throws", async () => {
    supabaseMocks.from.mockImplementation(() => {
      throw new Error("network failure");
    });
    await expect(fetchCanonicalSchoolId("throwing-alias")).resolves.toBeNull();
  });
});

describe("fetchSchoolSlugResolver", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("resolves aliases from a paged crosswalk read, not one request per alias", async () => {
    const query = pageQuery({
      data: [
        { school_id: "amherst", alias: "amherst-college", is_primary: false },
        { school_id: "bowdoin", alias: "bowdoin-college", is_primary: false },
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
