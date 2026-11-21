import { assertEquals } from "jsr:@std/assert";
import { pdfViewerRawUrl, rejectableHtmlSourceOutcome } from "./html_source_guard.ts";

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

// The page archive.swarthmore.edu serves, with the host changed.
const viewerPage = (pdfUrl: string) =>
  encode(`<!doctype html>
<html dir="ltr" mozdisallowselectionprint>
  <head><!-- Google Tag Manager -->
<script>(function(w,d,s,l,i){w[l]=w[l]||[];w[l].push({'gtm.start':
new Date().getTime(),event:'gtm.js'});var f=d.getElementsByTagName(s)[0],
j=d.createElement(s),dl=l!='dataLayer'?'&l='+l:'';j.async=true;j.src=
'https://www.googletagmanager.com/gtm.js?id='+i+dl;f.parentNode.insertBefore(j,f);
})(window,document,'script','dataLayer','GTM-XXXXXXXX');</script>
<!-- End Google Tag Manager -->
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1" />
    <meta name="google" content="notranslate" />
    <title>PDF.js viewer</title>
    <link rel="resource" type="application/l10n" href="/src/pdfjs/web/locale/locale.json" />
    <script src="/src/pdfjs/build/pdf.mjs" type="module"></script>
    <script>
      const PDF_URL = "${pdfUrl}";
    </script>
    <script src="/src/js/pdf-viewer-init.js"></script>
  </head>
  <body tabindex="0"></body>
</html>`);

const PAGE_URL = "https://archive.example.edu/files/ir/cds2014.pdf";

Deno.test("pdfViewerRawUrl: reads the file URL from a PDF.js viewer page at a .pdf URL", () => {
  assertEquals(
    pdfViewerRawUrl(viewerPage(`${PAGE_URL}?__raw=1`), PAGE_URL),
    `${PAGE_URL}?__raw=1`,
  );
  // A relative URL resolves against the page.
  assertEquals(
    pdfViewerRawUrl(viewerPage("/raw/cds2014.pdf"), PAGE_URL),
    "https://archive.example.edu/raw/cds2014.pdf",
  );
});

Deno.test("pdfViewerRawUrl: never leaves the page's host or scheme", () => {
  assertEquals(pdfViewerRawUrl(viewerPage("https://evil.example.com/cds2014.pdf"), PAGE_URL), null);
  assertEquals(pdfViewerRawUrl(viewerPage("http://archive.example.edu/files/ir/cds2014.pdf?__raw=1"), PAGE_URL), null);
  assertEquals(pdfViewerRawUrl(viewerPage("https://archive.example.edu:8443/files/ir/cds2014.pdf"), PAGE_URL), null);
});

Deno.test("pdfViewerRawUrl: null unless the page is a viewer at a .pdf URL naming a different .pdf", () => {
  // Not requested as a .pdf.
  assertEquals(
    pdfViewerRawUrl(viewerPage(`${PAGE_URL}?__raw=1`), "https://archive.example.edu/viewer"),
    null,
  );
  // Names something that is not a .pdf, or itself.
  assertEquals(pdfViewerRawUrl(viewerPage("https://archive.example.edu/login"), PAGE_URL), null);
  assertEquals(pdfViewerRawUrl(viewerPage(PAGE_URL), PAGE_URL), null);
  // An ordinary HTML page, a bot challenge, and a real PDF.
  assertEquals(
    pdfViewerRawUrl(encode("<html><title>Just a moment...</title></html>"), PAGE_URL),
    null,
  );
  assertEquals(
    pdfViewerRawUrl(encode(`<html><script>const PDF_URL = "${PAGE_URL}?__raw=1";</script></html>`), PAGE_URL),
    null,
  );
  assertEquals(
    pdfViewerRawUrl(encode(`%PDF-1.7 <html> pdfjs const PDF_URL = "${PAGE_URL}?__raw=1";`), PAGE_URL),
    null,
  );
});
