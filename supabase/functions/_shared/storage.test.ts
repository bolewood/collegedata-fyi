import { assertEquals } from "jsr:@std/assert";
import { extForResponse } from "./storage.ts";

Deno.test("extForResponse: rejects HTML challenge bytes at PDF URL", () => {
  const bytes = new TextEncoder().encode(
    "<!DOCTYPE html><html><title>Just a moment...</title></html>",
  );

  assertEquals(
    extForResponse("text/html; charset=UTF-8", "https://example.edu/cds.pdf", bytes),
    null,
  );
});

Deno.test("extForResponse: bytes beat misleading content type", () => {
  const bytes = new TextEncoder().encode("%PDF-1.7\n");

  assertEquals(
    extForResponse("text/html; charset=UTF-8", "https://example.edu/cds.pdf", bytes),
    "pdf",
  );
});
