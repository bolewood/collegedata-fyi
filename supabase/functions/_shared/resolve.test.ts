import { assertEquals, assertExists } from "jsr:@std/assert";
import { extractCdsAnchors, findBestSourceAnchor } from "./resolve.ts";

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
