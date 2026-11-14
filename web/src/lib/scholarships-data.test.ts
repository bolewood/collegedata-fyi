import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  mode: "ok" as "ok" | "missing_relation" | "throws" | "garbage",
  calls: [] as string[],
}));

vi.mock("./supabase", () => {
  const chain = (table: string) => {
    const q: any = {
      select: () => q,
      order: () => q,
      range: () => q,
      eq: () => q,
      in: () => q,
      then: (resolve: (v: unknown) => unknown, reject: (e: unknown) => unknown) => {
        state.calls.push(table);
        if (state.mode === "throws") return Promise.reject(new Error("fetch failed")).then(resolve, reject);
        if (state.mode === "missing_relation") {
          return Promise.resolve({
            data: null,
            error: { code: "PGRST205", message: "Could not find the table 'public.scholarship_directory' in the schema cache" },
          }).then(resolve, reject);
        }
        if (state.mode === "garbage") return Promise.resolve({ data: [null, 5, { nope: true }], error: null }).then(resolve, reject);
        return Promise.resolve({ data: [], error: null }).then(resolve, reject);
      },
    };
    return q;
  };
  return { supabase: { from: chain }, STORAGE_BASE_URL: "" };
});

import { emptyOnError, fetchScholarshipIndex, fetchScholarshipsBySchoolId } from "./scholarships-data";

beforeEach(() => {
  state.calls = [];
  vi.spyOn(console, "warn").mockImplementation(() => {});
});
afterEach(() => vi.restoreAllMocks());

describe("scholarship reads are empty on error", () => {
  it("returns no programs when the view does not exist (PostgREST error)", async () => {
    state.mode = "missing_relation";
    expect(await fetchScholarshipsBySchoolId("tulsa")).toEqual({ programs: [], names: {} });
    expect(await fetchScholarshipIndex()).toEqual({ rows: [], controls: {} });
  });

  it("returns no programs when the request throws (timeout, network)", async () => {
    state.mode = "throws";
    expect((await fetchScholarshipsBySchoolId("tulsa")).programs).toEqual([]);
    expect((await fetchScholarshipIndex()).rows).toEqual([]);
  });

  it("returns no programs when the view is empty", async () => {
    state.mode = "ok";
    expect((await fetchScholarshipsBySchoolId("tulsa")).programs).toEqual([]);
  });

  it("drops malformed rows instead of crashing", async () => {
    state.mode = "garbage";
    expect((await fetchScholarshipIndex()).rows).toEqual([]);
  });

  it("warns once per failure and passes the fallback through emptyOnError", async () => {
    const out = await emptyOnError("label", [1], async () => {
      throw new Error("boom");
    });
    expect(out).toEqual([1]);
    expect(console.warn).toHaveBeenCalledWith("label: boom");
  });
});
