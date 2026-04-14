import { assertEquals } from "jsr:@std/assert";
import { normalizeYear } from "./year.ts";

Deno.test("normalizeYear: long-long hyphen", () => {
  assertEquals(normalizeYear("cds2024-2025.pdf"), "2024-25");
});

Deno.test("normalizeYear: long-long en-dash", () => {
  assertEquals(normalizeYear("CDS 2024–2025 Final"), "2024-25");
});

Deno.test("normalizeYear: long-long underscore", () => {
  assertEquals(normalizeYear("cds_2024_2025_final.pdf"), "2024-25");
});

Deno.test("normalizeYear: long-long space", () => {
  assertEquals(normalizeYear("Common Data Set 2024 2025"), "2024-25");
});

Deno.test("normalizeYear: long-short", () => {
  assertEquals(normalizeYear("cds-2024-25.pdf"), "2024-25");
});

Deno.test("normalizeYear: short-short", () => {
  assertEquals(normalizeYear("cds 13-14 final.pdf"), "2013-14");
});

Deno.test("normalizeYear: millennium boundary 99-00", () => {
  assertEquals(normalizeYear("cds99-00.pdf"), "1999-00");
});

Deno.test("normalizeYear: no-separator 4-digit", () => {
  assertEquals(normalizeYear("cds2425.pdf"), "2024-25");
});

Deno.test("normalizeYear: 2021 is NOT a span", () => {
  // 2021 would parse as span 20-21 under pattern 4, but the guard rejects
  // any match whose first digits are 19 or 20. Falls through to null.
  assertEquals(normalizeYear("page-2021-refresh"), null);
});

Deno.test("Brown 2020-04 path trap (codex finding #6 regression)", () => {
  // Real Brown URL. 2020-04 is a Drupal upload-month path segment, not a
  // span. The scanner must reject 2020-04 and then find 2009_2010.
  const url = "https://oir.brown.edu/sites/default/files/2020-04/CDS2009_2010.pdf";
  assertEquals(normalizeYear(url), "2009-10");
});

Deno.test("normalizeYear: invalid span returns null", () => {
  // 2020-04 alone is not a valid academic span (4 != 21 % 100).
  assertEquals(normalizeYear("2020-04"), null);
});

Deno.test("normalizeYear: implausibly old year rejected", () => {
  // Lower bound is 1990 (CMU has 1999-00 as their deepest archive).
  assertEquals(normalizeYear("cds1970-71.pdf"), null);
});

Deno.test("normalizeYear: implausibly future year rejected", () => {
  assertEquals(normalizeYear("cds2050-51.pdf"), null);
});

Deno.test("normalizeYear: null input", () => {
  assertEquals(normalizeYear(null), null);
});

Deno.test("normalizeYear: empty input", () => {
  assertEquals(normalizeYear(""), null);
});

Deno.test("normalizeYear: no year at all", () => {
  assertEquals(normalizeYear("common-data-set.pdf"), null);
});
