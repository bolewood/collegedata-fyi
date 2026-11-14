import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const state = vi.hoisted(() => ({
  mode: "ok" as "ok" | "missing_relation" | "throws" | "garbage",
  calls: [] as string[],
  memo: new Map<string, Promise<unknown>>(),
}));

// A memoizing unstable_cache: same key, one run; a rejection is never kept.
vi.mock("next/cache", () => ({
  unstable_cache: (fn: () => Promise<unknown>, key: string[]) => () => {
    const k = key.join("|");
    const hit = state.memo.get(k);
    if (hit) return hit;
    const p = fn();
    state.memo.set(k, p);
    p.catch(() => state.memo.delete(k));
    return p;
  },
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
  state.memo.clear();
  vi.spyOn(console, "warn").mockImplementation(() => {});
});
afterEach(() => vi.restoreAllMocks());

describe("scholarship reads are empty on error", () => {
  it("returns no programs when the view does not exist (PostgREST error)", async () => {
    state.mode = "missing_relation";
    expect(await fetchScholarshipsBySchoolId("tulsa")).toEqual({ programs: [], names: {} });
    expect(await fetchScholarshipIndex()).toEqual({ rows: [], controls: {}, programs: [] });
  });

  it("returns no programs when the request throws (timeout, network)", async () => {
    state.mode = "throws";
    expect((await fetchScholarshipsBySchoolId("tulsa")).programs).toEqual([]);
    expect((await fetchScholarshipIndex()).rows).toEqual([]);
  });

  it("reads the view once for any number of school pages and the index", async () => {
    state.mode = "ok";
    await fetchScholarshipsBySchoolId("tulsa");
    await fetchScholarshipsBySchoolId("yale");
    await fetchScholarshipIndex();
    expect(state.calls.filter((t) => t === "scholarship_directory")).toHaveLength(1);
  });

  it("does not cache a failed read", async () => {
    state.mode = "missing_relation";
    await fetchScholarshipsBySchoolId("tulsa");
    state.mode = "ok";
    await fetchScholarshipsBySchoolId("tulsa");
    expect(state.calls.filter((t) => t === "scholarship_directory")).toHaveLength(2);
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
