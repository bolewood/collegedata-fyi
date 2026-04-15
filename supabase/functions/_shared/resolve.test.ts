import { assertEquals, assertExists } from "jsr:@std/assert";
import {
  extractCdsAnchors,
  findBestSourceAnchor,
  findDownloadLinks,
} from "./resolve.ts";

const BASE = "https://example.edu/ir/cds/";

Deno.test("extractCdsAnchors: single direct PDF with year", () => {
  const html = `
    <html><body>
      <a href="https://example.edu/files/cds2024-25.pdf">Common Data Set 2024-25</a>
    </body></html>
  `;
  const anchors = extractCdsAnchors(html, BASE);
  assertEquals(anchors.length, 1);
  assertEquals(anchors[0].kind, "document");
  assertEquals(anchors[0].year, "2024-25");
  assertEquals(anchors[0].is_section_file, false);
});

Deno.test("extractCdsAnchors: relative href resolved", () => {
  // BASE = https://example.edu/ir/cds/
  // "../files/cds-2024-2025.pdf" resolves one level up from /ir/cds/ → /ir/files/
  const html = `<a href="../files/cds-2024-2025.pdf">CDS 2024-2025</a>`;
  const anchors = extractCdsAnchors(html, BASE);
  assertEquals(anchors.length, 1);
  assertEquals(anchors[0].url, "https://example.edu/ir/files/cds-2024-2025.pdf");
});

Deno.test("extractCdsAnchors: ignores non-CDS anchors", () => {
  const html = `
    <a href="/about.html">About</a>
    <a href="/files/strategic-plan.pdf">Strategic Plan</a>
    <a href="/files/cds2024-25.pdf">Common Data Set</a>
  `;
  const anchors = extractCdsAnchors(html, BASE);
  assertEquals(anchors.length, 1);
  assertEquals(anchors[0].filename, "cds2024-25.pdf");
});

Deno.test("extractCdsAnchors: hostname CDS keywords do not match alone", () => {
  // commondataset.org in the href hostname must not match without CDS
  // keywords in the filename, link text, or path.
  const html = `<a href="https://commondataset.org/brochure.pdf">Publisher Brochure</a>`;
  const anchors = extractCdsAnchors(html, BASE);
  assertEquals(anchors.length, 0);
});

Deno.test("extractCdsAnchors: commondataset.org documents are excluded even when filename matches CDS keywords", () => {
  // Regression for the tier probe finding: stanford/georgetown/davidson
  // were all archiving the same CDS Initiative Summary-of-Changes docx
  // because it had "CDS" in the filename, a 2025-26 year, and ranked
  // above each school's own 2024-25 CDS on recency.
  const html = `
    <a href="https://commondataset.org/wp-content/uploads/2025/11/CDS-2025-2026-Summary-of-Changes-1.docx">CDS 2025-26 Summary of Changes</a>
    <a href="https://example.edu/files/cds2024-25.pdf">Common Data Set 2024-25</a>
  `;
  const anchors = extractCdsAnchors(html, BASE);
  assertEquals(anchors.length, 1);
  assertEquals(anchors[0].url, "https://example.edu/files/cds2024-25.pdf");
});

Deno.test("extractCdsAnchors: section marker detected", () => {
  const html = `<a href="/files/cds-section-d-2024-25.pdf">Common Data Set Section D 2024-25</a>`;
  const anchors = extractCdsAnchors(html, BASE);
  assertEquals(anchors.length, 1);
  assertEquals(anchors[0].is_section_file, true);
});

Deno.test("extractCdsAnchors: HTML subpage categorized", () => {
  const html = `<a href="/ir/cds/2024-2025/">Common Data Set 2024-2025</a>`;
  const anchors = extractCdsAnchors(html, BASE);
  assertEquals(anchors.length, 1);
  assertEquals(anchors[0].kind, "subpage");
});

Deno.test("extractCdsAnchors: malformed HTML returns empty, not crash", () => {
  // deno-dom is lenient; "malformed" for our purposes means no matching
  // anchors rather than a parse crash.
  const html = `<not valid <<<<`;
  const anchors = extractCdsAnchors(html, BASE);
  assertEquals(anchors.length, 0);
});

Deno.test("findBestSourceAnchor: prefers full CDS over section file", () => {
  const anchors = [
    {
      url: "https://example.edu/files/cds-section-d-2024-25.pdf",
      filename: "cds-section-d-2024-25.pdf",
      link_text: "CDS Section D 2024-25",
      year: "2024-25",
      year_source: "filename" as const,
      kind: "document" as const,
      is_section_file: true,
    },
    {
      url: "https://example.edu/files/cds2024-25.pdf",
      filename: "cds2024-25.pdf",
      link_text: "Common Data Set 2024-25",
      year: "2024-25",
      year_source: "filename" as const,
      kind: "document" as const,
      is_section_file: false,
    },
  ];
  const best = findBestSourceAnchor(anchors);
  assertExists(best);
  assertEquals(best.filename, "cds2024-25.pdf");
});

Deno.test("findBestSourceAnchor: prefers recent year", () => {
  const anchors = [
    {
      url: "a.pdf",
      filename: "cds2019-20.pdf",
      link_text: "CDS 2019-20",
      year: "2019-20",
      year_source: "filename" as const,
      kind: "document" as const,
      is_section_file: false,
    },
    {
      url: "b.pdf",
      filename: "cds2024-25.pdf",
      link_text: "CDS 2024-25",
      year: "2024-25",
      year_source: "filename" as const,
      kind: "document" as const,
      is_section_file: false,
    },
    {
      url: "c.pdf",
      filename: "cds2021-22.pdf",
      link_text: "CDS 2021-22",
      year: "2021-22",
      year_source: "filename" as const,
      kind: "document" as const,
      is_section_file: false,
    },
  ];
  const best = findBestSourceAnchor(anchors);
  assertExists(best);
  assertEquals(best.year, "2024-25");
});

Deno.test("findBestSourceAnchor: falls back to section file if no full CDS", () => {
  const anchors = [
    {
      url: "sd.pdf",
      filename: "cds-section-d-2024-25.pdf",
      link_text: "Section D",
      year: "2024-25",
      year_source: "filename" as const,
      kind: "document" as const,
      is_section_file: true,
    },
  ];
  const best = findBestSourceAnchor(anchors);
  assertExists(best);
  assertEquals(best.is_section_file, true);
});

Deno.test("findBestSourceAnchor: empty input returns null", () => {
  assertEquals(findBestSourceAnchor([]), null);
});

Deno.test("findDownloadLinks: Digital Commons item page (Fairfield regression)", () => {
  // Regression for tonight's failed_permanent: Fairfield's Digital Commons
  // archive lists each CDS as an item page (archives-cds/19, /16, ...)
  // and each item page has a "Download" button that points at a CGI
  // endpoint with no file extension. extractCdsAnchors filters it out
  // because the filename is "viewcontent.cgi" and the link text is just
  // "Download" — neither matches the CDS keyword filter. findDownloadLinks
  // catches it via the DOWNLOAD_URL_RE / DOWNLOAD_TEXT_RE patterns.
  const itemPageHtml = `
    <div class="item">
      <h1>Common Data Set 2024-2025</h1>
      <a class="btn" id="alpha-pdf"
         href="https://digitalcommons.fairfield.edu/cgi/viewcontent.cgi?article=1018&amp;context=archives-cds"
         title="PDF (1.3 MB) opens in new window"
         target="_blank">Download</a>
      <ul class="sidebar">
        <li><a href="/content_policy.pdf">Faculty Policies</a></li>
      </ul>
    </div>
  `;
  const anchors = findDownloadLinks(
    itemPageHtml,
    "https://digitalcommons.fairfield.edu/archives-cds/19",
  );
  // Should find the viewcontent.cgi link. The sidebar policy PDF also
  // matches the DOWNLOAD_URL_RE (it ends in .pdf) — that's fine because
  // findDownloadLinks is only called as a fallback when the strict
  // extractCdsAnchors pass found nothing, and the parent subpage's CDS
  // context still anchors the year/labeling.
  const viewContentAnchor = anchors.find((a) => a.url.includes("viewcontent.cgi"));
  assertExists(viewContentAnchor);
  assertEquals(viewContentAnchor.kind, "document");
});

Deno.test("findDownloadLinks: skips anchors without download-pattern markers", () => {
  const html = `
    <a href="/about">About this archive</a>
    <a href="/contact">Contact</a>
    <a href="https://example.edu/unrelated-report.pdf">Annual Report</a>
  `;
  const anchors = findDownloadLinks(html, "https://example.edu/item/1");
  // "Annual Report" PDF matches DOWNLOAD_TEXT_RE via "pdf"? No, "Annual Report"
  // doesn't contain download/pdf/full-text. But the filename .pdf won't match
  // DOWNLOAD_URL_RE (no viewcontent/bitstream/etc). So this entry is also
  // correctly excluded.
  assertEquals(anchors.length, 0);
});

Deno.test("findDownloadLinks: commondataset.org excluded here too", () => {
  // Belt-and-suspenders: the excluded-host filter applies to the
  // fallback download-link scanner as well, not just the strict pass.
  const html = `<a href="https://commondataset.org/template.pdf">Download Template</a>`;
  const anchors = findDownloadLinks(html, "https://example.edu/item/1");
  assertEquals(anchors.length, 0);
});

Deno.test("findBestSourceAnchor: only subpages → null", () => {
  const anchors = [
    {
      url: "https://example.edu/ir/cds/2024/",
      filename: "2024",
      link_text: "CDS 2024-25",
      year: "2024-25",
      year_source: "filename" as const,
      kind: "subpage" as const,
      is_section_file: false,
    },
  ];
  assertEquals(findBestSourceAnchor(anchors), null);
});
