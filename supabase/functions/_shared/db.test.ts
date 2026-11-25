import { assertEquals } from "jsr:@std/assert";
import type { SupabaseClient } from "jsr:@supabase/supabase-js@2";
import {
  fetchDirectoryIpedsId,
  fetchMostRecentDocumentForSchool,
  pickMostRecentDocument,
  resolveInsertIpedsId,
} from "./db.ts";
import type { SchoolEntry } from "./schools.ts";

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
  assertEquals(await resolveInsertIpedsId(fakeClient(TABLES), "bethel-university", "219718", null, []), "173160");
});

Deno.test("missing schools.yaml id is filled from the directory, not a sibling", async () => {
  assertEquals(await resolveInsertIpedsId(fakeClient(TABLES), "caltech", null, null, []), "110404");
  assertEquals(await resolveInsertIpedsId(fakeClient(TABLES), "unknown", null, null, []), null);
  assertEquals(await resolveInsertIpedsId(fakeClient(TABLES), "unknown", "134130", null, []), "134130");
});

const e = (id: string, ipeds_id: string, domain: string) =>
  ({ id, name: id, ipeds_id, domain, scrape_policy: "unknown" }) as SchoolEntry;

// Shared slugs as they stand in schools.yaml. The directory owner of each slug
// is NOT always the institution whose files arrive.
const SHARED: SchoolEntry[] = [
  e("bethel-university", "150145", "betheluniversity.edu"),
  e("bethel-university", "173160", "bethel.edu"),
  e("bethel-university", "219718", "bethelu.edu"),
  e("columbia-college", "177065", "ccis.edu"),
  e("columbia-college", "217934", "columbiasc.edu"),
  e("westminster-college", "179946", "wcmo.edu"),
  e("westminster-college", "216807", "westminster.edu"),
  e("university-of-st-thomas", "174914", "stthomas.edu"),
  e("university-of-st-thomas", "227863", "stthom.edu"),
];
const SHARED_TABLES: Rows = {
  institution_directory: [
    { school_id: "bethel-university", ipeds_id: "173160" },
    { school_id: "columbia-college", ipeds_id: "177065" },
    { school_id: "westminster-college", ipeds_id: "216807" },
    { school_id: "university-of-st-thomas", ipeds_id: "174914" },
  ],
};

Deno.test("shared slugs are stamped by the source domain, not the directory owner", async () => {
  const c = fakeClient(SHARED_TABLES);
  const id = (slug: string, url: string) => resolveInsertIpedsId(c, slug, null, url, SHARED);
  assertEquals(await id("bethel-university", "https://www.bethel.edu/x/cds-2425.xlsx"), "173160");
  assertEquals(await id("columbia-college", "https://www.ccis.edu/_files/cds.pdf"), "177065");
  assertEquals(await id("westminster-college", "https://www.wcmo.edu/cds.pdf"), "179946");
  assertEquals(await id("university-of-st-thomas", "https://it.stthom.edu/wp-content/cds.pdf"), "227863");
  // Archive.org capture unwraps to the original host.
  assertEquals(
    await id("westminster-college", "https://web.archive.org/web/20250101000000id_/https://www.wcmo.edu/cds.pdf"),
    "179946",
  );
});

Deno.test("shared slug with no domain match writes NULL, never the directory owner", async () => {
  const c = fakeClient(SHARED_TABLES);
  assertEquals(
    await resolveInsertIpedsId(c, "westminster-college", null, "https://drive.google.com/file/d/abc", SHARED),
    null,
  );
  assertEquals(await resolveInsertIpedsId(c, "westminster-college", null, null, SHARED), null);
  // stthomas.edu must not match stthom.edu or the reverse by suffix accident.
  assertEquals(
    await resolveInsertIpedsId(c, "university-of-st-thomas", null, "https://www.notstthom.edu/x.pdf", SHARED),
    null,
  );
});

Deno.test("directory lookup returning an error falls back to the yaml id without throwing", async () => {
  const failing = {
    from: () => {
      const q = {
        select: () => q,
        eq: () => q,
        neq: () => q,
        limit: () => Promise.resolve({ data: null, error: { message: "boom" } }),
      };
      return q;
    },
  } as unknown as SupabaseClient;
  assertEquals(await resolveInsertIpedsId(failing, "caltech", "110404", null, []), "110404");
});

Deno.test("pickMostRecentDocument: dated year beats unknown (text sort puts unknown first)", () => {
  const rows = [
    { id: "u", cds_year: "unknown" },
    { id: "a", cds_year: "2024-25" },
    { id: "b", cds_year: "2025-26" },
  ];
  assertEquals(pickMostRecentDocument(rows)?.id, "b");
});

Deno.test("pickMostRecentDocument: falls back to undated only when no dated row exists", () => {
  assertEquals(pickMostRecentDocument([{ id: "u", cds_year: "unknown" }])?.id, "u");
  assertEquals(pickMostRecentDocument([]), null);
});

Deno.test("fetchMostRecentDocumentForSchool: skips removed rows and picks newest dated", async () => {
  const rows = [
    { id: "u", school_id: "s", cds_year: "unknown", removed_at: null, sub_institutional: null },
    { id: "old", school_id: "s", cds_year: "2023-24", removed_at: null, sub_institutional: null },
    { id: "taken", school_id: "s", cds_year: "2025-26", removed_at: "2026-01-01", sub_institutional: null },
    { id: "other", school_id: "other-school", cds_year: "2026-27", removed_at: null, sub_institutional: null },
    { id: "sub", school_id: "s", cds_year: "2026-27", removed_at: null, sub_institutional: "law" },
    { id: "bad1", school_id: "s", cds_year: "5024-25", removed_at: null, sub_institutional: null },
    { id: "bad2", school_id: "s", cds_year: "2025-27", removed_at: null, sub_institutional: null },
  ];
  const client = {
    from() {
      const filters: Array<(r: Record<string, unknown>) => boolean> = [];
      const q: Record<string, unknown> = {
        select: () => q,
        eq: (c: string, v: unknown) => (filters.push((r) => r[c] === v), q),
        is: (c: string, v: unknown) => (filters.push((r) => r[c] === v), q),
        order: () => q,
        then: (res: (v: unknown) => void) =>
          res({ data: rows.filter((r) => filters.every((f) => f(r))), error: null }),
      };
      return q;
    },
  } as unknown as SupabaseClient;
  assertEquals((await fetchMostRecentDocumentForSchool(client, "s"))?.id, "old");
});

Deno.test("pickMostRecentDocument: malformed years are ignored", () => {
  const rows = [
    { id: "a", cds_year: "5024-25" },
    { id: "b", cds_year: "2025-27" },
    { id: "c", cds_year: "2023-24" },
  ];
  assertEquals(pickMostRecentDocument(rows)?.id, "c");
});
