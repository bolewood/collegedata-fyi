import { assertEquals, assertRejects } from "jsr:@std/assert";
import {
  normalizeSchoolToken,
  resolveSchoolName,
  suggestCanonicalSchool,
  UnknownSchoolError,
} from "./schools.ts";

// Minimal SchoolEntry fixture — only the fields the resolver touches.
type E = { id: string; name: string; ipeds_id: string; scrape_policy: string };
const entries: E[] = [
  { id: "uf", name: "University of Florida", ipeds_id: "1", scrape_policy: "active" },
  { id: "unc", name: "University of North Carolina at Chapel Hill", ipeds_id: "2", scrape_policy: "active" },
  { id: "mit", name: "Massachusetts Institute of Technology", ipeds_id: "3", scrape_policy: "active" },
  { id: "bowdoin", name: "Bowdoin College", ipeds_id: "4", scrape_policy: "active" },
  { id: "claremont-mckenna", name: "Claremont McKenna College", ipeds_id: "5", scrape_policy: "active" },
];

Deno.test("normalizeSchoolToken strips structural noise", () => {
  assertEquals(normalizeSchoolToken("University of Florida"), "florida");
  assertEquals(normalizeSchoolToken("university-of-florida"), "florida");
  assertEquals(normalizeSchoolToken("University of North Carolina at Chapel Hill"), "northcarolinachapelhill");
  assertEquals(normalizeSchoolToken("university-of-north-carolina-at-chapel-hill"), "northcarolinachapelhill");
  assertEquals(normalizeSchoolToken("Bowdoin College"), "bowdoin");
  assertEquals(normalizeSchoolToken("bowdoin-college"), "bowdoin");
});

Deno.test("suggestCanonicalSchool matches slug form against canonical name", () => {
  // deno-lint-ignore no-explicit-any
  const s = (id: string) => suggestCanonicalSchool(id, entries as any);
  assertEquals(s("university-of-florida"), { id: "uf", name: "University of Florida" });
  assertEquals(s("university-of-north-carolina-at-chapel-hill"), {
    id: "unc",
    name: "University of North Carolina at Chapel Hill",
  });
  assertEquals(s("bowdoin-college"), { id: "bowdoin", name: "Bowdoin College" });
  assertEquals(s("claremont-mckenna-college"), {
    id: "claremont-mckenna",
    name: "Claremont McKenna College",
  });
});

Deno.test("suggestCanonicalSchool returns null for genuinely unknown ids", () => {
  // deno-lint-ignore no-explicit-any
  const s = (id: string) => suggestCanonicalSchool(id, entries as any);
  assertEquals(s("hogwarts"), null);
  assertEquals(s(""), null);
});

Deno.test("resolveSchoolName trusts explicit name (does not touch schools.yaml)", async () => {
  // No fetch happens because explicitName short-circuits. If fetchSchoolsYaml
  // were invoked, this test would fail because SCHOOLS_YAML_URL points at GitHub.
  const name = await resolveSchoolName("brand-new-school", "Brand New School");
  assertEquals(name, "Brand New School");
});

Deno.test("resolveSchoolName trims whitespace on explicit name", async () => {
  const name = await resolveSchoolName("x", "   Some School   ");
  assertEquals(name, "Some School");
});

Deno.test("UnknownSchoolError carries the suggestion on the error instance", () => {
  const e = new UnknownSchoolError("boom", "uf");
  assertEquals(e.suggestion, "uf");
  assertEquals(e.code, "unknown_school");
  assertEquals(e.name, "UnknownSchoolError");
});

// resolveSchoolName's fail-closed behavior when the id is unknown cannot be
// tested here without stubbing fetch — done in an integration test against
// a local schools.yaml fixture, or left to manual QA. The fuzzy suggester
// (the part with actual logic) is covered above.
