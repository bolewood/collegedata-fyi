import { assertEquals, assertThrows } from "jsr:@std/assert";
import { parseContentRange } from "./reprobe_resolver_cohort.ts";

Deno.test("parseContentRange accepts empty PostgREST relations", () => {
  assertEquals(parseContentRange("*/0"), {
    start: null,
    end: null,
    total: 0,
  });
});

Deno.test("parseContentRange preserves bounded page metadata", () => {
  assertEquals(parseContentRange("1000-1999/2848"), {
    start: 1000,
    end: 1999,
    total: 2848,
  });
});

Deno.test("parseContentRange rejects malformed metadata", () => {
  assertThrows(() => parseContentRange("0/10"), Error, "invalid Content-Range");
});
