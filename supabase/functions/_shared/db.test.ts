import { assertEquals } from "jsr:@std/assert";
import type { SupabaseClient } from "jsr:@supabase/supabase-js@2";
import { fetchDirectoryIpedsId, resolveInsertIpedsId } from "./db.ts";

type Rows = Record<string, Array<Record<string, unknown>>>;

// Minimal PostgREST stand-in: from(table).select().eq(col, v).neq(col, v).limit(n).
function fakeClient(tables: Rows): SupabaseClient {
  return {
    from(table: string) {
      const filters: Array<(r: Record<string, unknown>) => boolean> = [];
      const q = {
        select: () => q,
        eq: (col: string, v: unknown) => {
          filters.push((r) => r[col] === v);
          return q;
        },
        neq: (col: string, v: unknown) => {
          filters.push((r) => r[col] !== v);
          return q;
        },
        limit: () =>
          Promise.resolve({
            data: (tables[table] ?? []).filter((r) => filters.every((f) => f(r))),
            error: null,
          }),
      };
      return q;
    },
  } as unknown as SupabaseClient;
}

const TABLES: Rows = {
  institution_directory: [
    { school_id: "bethel-university", ipeds_id: "173160" },
    { school_id: "bethel-university-tn", ipeds_id: "219718" },
    { school_id: "caltech", ipeds_id: "110404" },
    { school_id: "twin", ipeds_id: "1" },
    { school_id: "twin", ipeds_id: "2" },
  ],
  institution_slug_crosswalk: [
    { alias: "california-institute-of-technology", source: "scorecard", ipeds_id: "110404" },
    { alias: "gone", source: "redirect", ipeds_id: "999999" },
  ],
};

Deno.test("directory lookup keys each institution to its own slug", async () => {
  const c = fakeClient(TABLES);
  assertEquals(await fetchDirectoryIpedsId(c, "bethel-university"), "173160");
  assertEquals(await fetchDirectoryIpedsId(c, "bethel-university-tn"), "219718");
});

Deno.test("directory lookup follows live aliases, skips redirects, refuses ambiguity", async () => {
  const c = fakeClient(TABLES);
  assertEquals(await fetchDirectoryIpedsId(c, "california-institute-of-technology"), "110404");
  assertEquals(await fetchDirectoryIpedsId(c, "gone"), null);
  assertEquals(await fetchDirectoryIpedsId(c, "twin"), null);
  assertEquals(await fetchDirectoryIpedsId(c, "unknown"), null);
});

Deno.test("a wrong schools.yaml id never beats the directory", async () => {
  // The old path took the last duplicate slug (Tennessee) for Minnesota's files.
  assertEquals(await resolveInsertIpedsId(fakeClient(TABLES), "bethel-university", "219718"), "173160");
});

Deno.test("missing schools.yaml id is filled from the directory, not a sibling", async () => {
  assertEquals(await resolveInsertIpedsId(fakeClient(TABLES), "caltech", null), "110404");
  assertEquals(await resolveInsertIpedsId(fakeClient(TABLES), "unknown", null), null);
  assertEquals(await resolveInsertIpedsId(fakeClient(TABLES), "unknown", "134130"), "134130");
});
