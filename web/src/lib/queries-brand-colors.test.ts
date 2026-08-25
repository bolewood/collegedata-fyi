import { beforeEach, describe, expect, it, vi } from "vitest";

const supabaseMocks = vi.hoisted(() => ({
  from: vi.fn(),
}));

vi.mock("./supabase", () => ({
  supabase: { from: supabaseMocks.from },
  STORAGE_BASE_URL: "https://example.test/storage/v1/object/public/sources",
}));

import { fetchBrandColorIndex } from "./queries";

type QueryResult = { data: unknown[] | null; error: unknown };

function mockBrandColorQueries(
  directoryResult: QueryResult,
  crosswalkResult: QueryResult,
) {
  const directoryRange = vi.fn().mockResolvedValue(directoryResult);
  const crosswalkRange = vi.fn().mockResolvedValue(crosswalkResult);
  const directoryOrder = vi.fn(() => ({ range: directoryRange }));
  const crosswalkQuery = {
    order: vi.fn(),
    range: crosswalkRange,
  };
  crosswalkQuery.order.mockReturnValue(crosswalkQuery);

  supabaseMocks.from.mockImplementation((table: string) => {
    if (table === "institution_directory") {
      return {
        select: vi.fn(() => ({ order: directoryOrder })),
      };
    }
    if (table === "institution_slug_crosswalk") {
      return { select: vi.fn(() => crosswalkQuery) };
    }
    throw new Error(`Unexpected table: ${table}`);
  });

  return { directoryRange, crosswalkRange, directoryOrder, crosswalkQuery };
}

describe("fetchBrandColorIndex", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("adds unambiguous aliases and gives a primary mapping precedence", async () => {
    mockBrandColorQueries(
      {
        data: [
          { school_id: "alpha", brand_colors: ["#111111"] },
          { school_id: "beta", brand_colors: ["#222222"] },
        ],
        error: null,
      },
      {
        data: [
          { school_id: "alpha", alias: "alpha-old", is_primary: false },
          { school_id: "alpha", alias: "shared-primary", is_primary: false },
          { school_id: "beta", alias: "shared-primary", is_primary: true },
        ],
        error: null,
      },
    );

    await expect(fetchBrandColorIndex()).resolves.toEqual({
      alpha: ["#111111"],
      beta: ["#222222"],
      "alpha-old": ["#111111"],
      "shared-primary": ["#222222"],
    });
  });

  it("does not guess ambiguous aliases or overwrite a direct directory ID", async () => {
    mockBrandColorQueries(
      {
        data: [
          { school_id: "alpha", brand_colors: ["#111111"] },
          { school_id: "beta", brand_colors: ["#222222"] },
          { school_id: "direct", brand_colors: ["#333333"] },
        ],
        error: null,
      },
      {
        data: [
          { school_id: "alpha", alias: "ambiguous", is_primary: false },
          { school_id: "beta", alias: "ambiguous", is_primary: false },
          { school_id: "alpha", alias: "direct", is_primary: true },
        ],
        error: null,
      },
    );

    const index = await fetchBrandColorIndex();
    expect(index.ambiguous).toBeUndefined();
    expect(index.direct).toEqual(["#333333"]);
  });

  it("does not overwrite a direct directory ID that has no colors", async () => {
    mockBrandColorQueries(
      {
        data: [
          { school_id: "alpha", brand_colors: ["#111111"] },
          { school_id: "direct", brand_colors: null },
        ],
        error: null,
      },
      {
        data: [
          { school_id: "alpha", alias: "direct", is_primary: true },
        ],
        error: null,
      },
    );

    const index = await fetchBrandColorIndex();
    expect(index.direct).toBeUndefined();
  });

  it("keeps direct colors when the crosswalk query fails", async () => {
    mockBrandColorQueries(
      {
        data: [{ school_id: "alpha", brand_colors: ["#111111"] }],
        error: null,
      },
      { data: null, error: { message: "crosswalk unavailable" } },
    );

    await expect(fetchBrandColorIndex()).resolves.toEqual({
      alpha: ["#111111"],
    });
  });

  it("does not resolve aliases from a partial crosswalk", async () => {
    const firstPage = Array.from({ length: 1000 }, (_, index) => ({
      school_id: "alpha",
      alias: index === 999 ? "shared" : `alpha-${index}`,
      is_primary: false,
    }));
    const { crosswalkRange } = mockBrandColorQueries(
      {
        data: [
          { school_id: "alpha", brand_colors: ["#111111"] },
          { school_id: "beta", brand_colors: ["#222222"] },
        ],
        error: null,
      },
      { data: firstPage, error: null },
    );
    crosswalkRange
      .mockResolvedValueOnce({ data: firstPage, error: null })
      .mockResolvedValueOnce({
        data: null,
        error: { message: "crosswalk page unavailable" },
      });

    const index = await fetchBrandColorIndex();
    expect(index).toEqual({
      alpha: ["#111111"],
      beta: ["#222222"],
    });
    expect(index.shared).toBeUndefined();
  });

  it("paginates through the full crosswalk", async () => {
    const firstPage = Array.from({ length: 1000 }, (_, index) => ({
      school_id: "alpha",
      alias: `alpha-${index}`,
      is_primary: false,
    }));
    const { crosswalkRange, directoryOrder, crosswalkQuery } = mockBrandColorQueries(
      {
        data: [{ school_id: "alpha", brand_colors: ["#111111"] }],
        error: null,
      },
      { data: firstPage, error: null },
    );
    crosswalkRange
      .mockResolvedValueOnce({ data: firstPage, error: null })
      .mockResolvedValueOnce({
        data: [
          { school_id: "alpha", alias: "alpha-last", is_primary: false },
        ],
        error: null,
      });

    const index = await fetchBrandColorIndex();
    expect(index["alpha-999"]).toEqual(["#111111"]);
    expect(index["alpha-last"]).toEqual(["#111111"]);
    expect(directoryOrder).toHaveBeenCalledWith("school_id");
    expect(crosswalkQuery.order).toHaveBeenNthCalledWith(1, "alias");
    expect(crosswalkQuery.order).toHaveBeenNthCalledWith(2, "ipeds_id");
    expect(crosswalkRange).toHaveBeenNthCalledWith(1, 0, 999);
    expect(crosswalkRange).toHaveBeenNthCalledWith(2, 1000, 1999);
  });
});
