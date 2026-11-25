import { assertEquals, assertStringIncludes } from "jsr:@std/assert@1";
import { canonicalSchoolId, RETIRED_SCHOOL_ALIASES } from "./retired_aliases.ts";

Deno.test("a retired legal-name slug is stored as its canonical id", () => {
  assertEquals(
    canonicalSchoolId("virginia-polytechnic-institute-and-state-university"),
    "virginia-tech",
  );
  assertEquals(canonicalSchoolId("tufts-university"), "tufts");
  assertEquals(canonicalSchoolId("university-of-chicago"), "uchicago");
});

Deno.test("canonical, ambiguous, unknown and prototype-key slugs are unchanged", () => {
  for (
    const slug of [
      "virginia-tech",
      "bethel-university",
      "union-college",
      "columbia-college",
      "not-a-school",
      "constructor",
      "__proto__",
    ]
  ) {
    assertEquals(canonicalSchoolId(slug), slug);
  }
});

Deno.test("every canonical target is itself not a retired alias (no chains)", () => {
  for (const target of Object.values(RETIRED_SCHOOL_ALIASES)) {
    assertEquals(target in RETIRED_SCHOOL_ALIASES, false);
  }
});

// The handlers call Deno.serve at import time and build a live Supabase
// client, so they can't be driven here. This pins the wiring in the source:
// each write boundary must canonicalize the request's school_id before use.
async function source(path: string): Promise<string> {
  return await Deno.readTextFile(new URL(path, import.meta.url));
}

Deno.test("archive-upload canonicalizes school_id before lookup, storage path and insert", async () => {
  const src = await source("../archive-upload/index.ts");
  assertStringIncludes(src, "const schoolId = canonicalSchoolId(rawSchoolId);");
  assertEquals(src.includes('const schoolId = form.get("school_id")'), false);
});

Deno.test("archive-process canonicalizes force_urls and queued school_id", async () => {
  const src = await source("../archive-process/index.ts");
  assertStringIncludes(src, "canonicalSchoolId(body.school_id)");
  assertStringIncludes(src, "const queuedSchoolId = canonicalSchoolId(row.school_id);");
  assertStringIncludes(src, "school_id: queuedSchoolId,");
  assertEquals(src.includes("resolveSchoolIpedsId(row.school_id)"), false);
});
