import { assertEquals } from "jsr:@std/assert";
import { rejectableHtmlSourceOutcome } from "./html_source_guard.ts";

const encode = (html: string) => new TextEncoder().encode(html);

Deno.test("rejectableHtmlSourceOutcome: Microsoft sign-in body is auth-walled", () => {
  assertEquals(
    rejectableHtmlSourceOutcome(
      encode("<!-- Copyright (C) Microsoft Corporation. --><title>Sign in to your account</title>"),
      "https://fs.example.edu/adfs/ls/",
    ),
    "auth_walled_microsoft",
  );
});

Deno.test("rejectableHtmlSourceOutcome: WAF challenge is bot_challenge", () => {
  assertEquals(
    rejectableHtmlSourceOutcome(
      encode("<html><title>Just a moment...</title><script>__cf_chl_tk='x'</script></html>"),
      "https://example.edu/cds",
    ),
    "bot_challenge",
  );
});

Deno.test("rejectableHtmlSourceOutcome: non-CDS error page is wrong_content_type", () => {
  assertEquals(
    rejectableHtmlSourceOutcome(
      encode("<html><h1>Page not found</h1><p>The page you requested could not be found.</p></html>"),
      "https://example.edu/cds",
    ),
    "wrong_content_type",
  );
});

Deno.test("rejectableHtmlSourceOutcome: CDS landing page without tables is wrong_content_type", () => {
  assertEquals(
    rejectableHtmlSourceOutcome(
      encode("<html><h1>Common Data Set PDF downloads</h1><a href='/files/cds.pdf'>2025-26 PDF</a></html>"),
      "https://example.edu/common-data-set/pdf",
    ),
    "wrong_content_type",
  );
});

Deno.test("rejectableHtmlSourceOutcome: CDS-like HTML is accepted", () => {
  assertEquals(
    rejectableHtmlSourceOutcome(
      encode("<html><h1>Common Data Set 2025-2026</h1><table><tr><th>B1</th><th>Men</th><th>Women</th></tr></table></html>"),
      "https://example.edu/cds",
    ),
    null,
  );
});
