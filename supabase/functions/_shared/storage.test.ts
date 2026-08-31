import { assertEquals } from "jsr:@std/assert";
import { extForResponse, isTruncatedWaybackPdf, sniffBytesForExt } from "./storage.ts";

Deno.test("extForResponse: rejects HTML challenge bytes at PDF URL", () => {
  const bytes = new TextEncoder().encode(
    "<!DOCTYPE html><html><title>Just a moment...</title></html>",
  );

  assertEquals(
    extForResponse("text/html; charset=UTF-8", "https://example.edu/cds.pdf", bytes),
    null,
  );
});

Deno.test("sniffBytesForExt: detects HTML after leading comments", () => {
  const bytes = new TextEncoder().encode(
    "<!-- Copyright (C) Example. --><!DOCTYPE html><html><title>Sign in</title></html>",
  );

  assertEquals(sniffBytesForExt(bytes), "html");
});

Deno.test("extForResponse: rejects comment-prefixed HTML challenge bytes at PDF URL", () => {
  const bytes = new TextEncoder().encode(
    "<!-- Copyright (C) Example. --><!DOCTYPE html><html><title>Sign in</title></html>",
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

Deno.test("isTruncatedWaybackPdf: missing trailer on archive.org is truncated", () => {
  const bytes = new TextEncoder().encode("%PDF-1.7\n" + "x".repeat(100));
  const url =
    "https://web.archive.org/web/20220701041620id_/https://example.edu/cds.pdf";
  assertEquals(isTruncatedWaybackPdf(url, bytes), true);
  assertEquals(extForResponse("application/pdf", url, bytes), null);
});

Deno.test("isTruncatedWaybackPdf: complete Wayback PDF is kept", () => {
  const bytes = new TextEncoder().encode("%PDF-1.7\n1 0 obj\n%%EOF\n");
  const url =
    "https://web.archive.org/web/20221231221445id_/https://example.edu/cds.pdf";
  assertEquals(isTruncatedWaybackPdf(url, bytes), false);
  assertEquals(extForResponse("application/pdf", url, bytes), "pdf");
});

Deno.test("isTruncatedWaybackPdf: school-hosted prefix without EOF is not flagged", () => {
  const bytes = new TextEncoder().encode("%PDF-1.7\n");
  assertEquals(
    isTruncatedWaybackPdf("https://example.edu/cds.pdf", bytes),
    false,
  );
});
