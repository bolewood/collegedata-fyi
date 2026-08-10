import { beforeEach, describe, expect, it, vi } from "vitest";

const supabaseMocks = vi.hoisted(() => ({
  from: vi.fn(),
}));

vi.mock("./supabase", () => ({
  supabase: { from: supabaseMocks.from },
  STORAGE_BASE_URL: "https://example.test/storage/v1/object/public/sources",
}));

import { fetchCanonicalSchoolId } from "./queries";

function aliasQueryResult(result: unknown) {
  const order = vi.fn().mockResolvedValue(result);
  const eq = vi.fn(() => ({ order }));
  const select = vi.fn(() => ({ eq }));
  supabaseMocks.from.mockReturnValue({ select });
  return { select, eq, order };
}

describe("fetchCanonicalSchoolId", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("queries the public crosswalk and resolves a unique retired alias", async () => {
    const query = aliasQueryResult({
      data: [
        {
          school_id: "tufts",
          alias: "tufts-university",
          is_primary: false,
        },
      ],
      error: null,
    });

    await expect(fetchCanonicalSchoolId("tufts-university")).resolves.toBe("tufts");
    expect(supabaseMocks.from).toHaveBeenCalledWith("institution_slug_crosswalk");
    expect(query.select).toHaveBeenCalledWith("school_id, alias, is_primary");
    expect(query.eq).toHaveBeenCalledWith("alias", "tufts-university");
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
