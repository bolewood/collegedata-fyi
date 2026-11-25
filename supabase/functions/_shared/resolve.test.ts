import { assertEquals, assertExists } from "jsr:@std/assert";
import {
  applyPinnedUrls,
  capSubpages,
  resolveCdsForSchool,
  mergeHintWithPageDocs,
  pickCandidates,
  type ResolvedCandidate,
  type ResolvedDocument,
  UNKNOWN_YEAR_SENTINEL,
  extractCdsAnchors,
  extractSubpageDocuments,
  findBestSourceAnchor,
  findDownloadLinks,
  rewriteGoogleDriveUrl,
  rewriteBoxUrl,
  rewriteWaybackUrl,
  parentLandingCandidates,
  wellKnownPathUrls,
  extractIrHubLinks,
  extractAboutLinks,
  wellKnownIrHubUrls,
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

Deno.test("extractCdsAnchors: SharePoint :x: link with CDS title is a document", () => {
  const html = `
    <a href="https://catmailohio.sharepoint.com/:x:/s/PRO-IeaWebdocs2/IQC__vQsqLFdQ732wvQ8Z4M2Af3jwIEccxlwEDYLMr8U6r8">2025 Common Data Set</a>
  `;
  const anchors = extractCdsAnchors(html, "https://www.ohio.edu/iea/university-data");
  assertEquals(anchors.length, 1);
  assertEquals(anchors[0].kind, "document");
  assertEquals(
    anchors[0].url,
    "https://catmailohio.sharepoint.com/:x:/s/PRO-IeaWebdocs2/IQC__vQsqLFdQ732wvQ8Z4M2Af3jwIEccxlwEDYLMr8U6r8",
  );
});

Deno.test("extractCdsAnchors: section marker detected", () => {
  const html = `
    <a href="/files/cds-section-d-2024-25.pdf">Common Data Set Section D 2024-25</a>
    <a href="/files/CDS_C_2526_0.pdf">Admissions</a>
    <a href="/ira/CDS/pdf/cds_2025_26/cds-2025-a-general-information.pdf">General Information</a>
    <a href="/CDS/2025-2026/J.pdf">Degrees Conferred</a>
  `;
  const anchors = extractCdsAnchors(html, BASE);
  assertEquals(anchors.length, 4);
  assertEquals(anchors.every((a) => a.is_section_file), true);
});

Deno.test("extractCdsAnchors: Regent-style section filenames (underscore-prefixed CDS, four-digit end year)", () => {
  // Regent publishes one PDF per section. The resolver archived only
  // Section A for 2012-13..2020-21 because `\bcds` has no word boundary
  // after `_` and the year-section pattern only allowed a 2-digit end
  // year, so these were treated as full CDS documents.
  const cases: Array<[string, string]> = [
    ["/ir/cds/08-09/CDS_A_Regent_2008_09.pdf", "A"],
    ["/ir/cds/12-13/Regent_CDS_A_2012-2013.pdf", "A"],
    ["/ir/cds/12-13/Regent_CDS_J_2012-2013.pdf", "J"],
    ["/ir/cds/13-14/Regent_CDS_2013-2014_A.pdf", "A"],
    ["/ir/cds/15-16/Regent%20CDS_2015-2016_C.pdf", "C"],
    ["/uploads/2021/01/Regent-IR-CDS-2020-2021-A.pdf", "A"],
  ];
  for (const [href, section] of cases) {
    const anchors = extractCdsAnchors(`<a href="${href}">Common Data Set</a>`, BASE);
    assertEquals(anchors.length, 1, href);
    assertEquals(anchors[0].is_section_file, true, `${href} should be section ${section}`);
  }
});

Deno.test("extractCdsAnchors: full-CDS filenames with four-digit end years stay full documents", () => {
  const fullDocs = [
    "/uploads/2023/02/Regent_CDS_2022-2023.pdf",
    "/uploads/2025/08/Regent-University-Common-Data-Set-2024-2025.pdf",
    "/files/CDS_2024-2025_Final.pdf",
    "/files/CDS-2024-2025-Draft.pdf",
    "/files/University_CDS_2023-2024_FINAL.pdf",
    "/files/cds2024-25.pdf",
    "/files/CDS2025-2026.pdf",
    "/files/Lafayette_CDS_Data_2024.pdf",
  ];
  for (const href of fullDocs) {
    const anchors = extractCdsAnchors(`<a href="${href}">Common Data Set</a>`, BASE);
    assertEquals(anchors.length, 1, href);
    assertEquals(anchors[0].is_section_file, false, `${href} is a full CDS`);
  }
});

Deno.test("pickCandidates: Regent-style section-only year becomes a package, not Section A alone", () => {
  const html = "ABCDEFGHIJ".split("").map((s) =>
    `<a href="/ir/cds/15-16/Regent%20CDS_2015-2016_${s}.pdf">Section ${s}</a>`
  ).join("\n");
  const anchors = extractCdsAnchors(html, "https://www.regent.edu/academics/academic_affairs/ir/cds/");
  const result = pickCandidates(anchors, "landing");
  assertExists(result);
  assertEquals(result.length, 1);
  assertEquals(result[0].candidate_kind, "section_package");
  if (result[0].candidate_kind === "section_package") {
    assertEquals(result[0].parts.map((p) => p.section).join(""), "ABCDEFGHIJ");
  }
});

Deno.test("pickCandidates: William & Mary year prefers the full workbook over digit-suffixed sections", () => {
  // Live wm.edu listing, 2025-26. Before the fix, `_a1` etc. were not
  // section files, so they counted as full CDS docs and a1 won on order.
  const files = [
    "cds_2025-26_a1.pdf", "cds_2025-26_b3.pdf", "cds_2025-26_c1.pdf", "cds_2025-26_d.pdf",
    "cds_2025-26_e1.pdf", "cds_2025-26_f.pdf", "cds_2025-26_g.pdf", "cds_2025-26_h.pdf",
    "cds_2025-26_i4.pdf", "cds_2025-26_j.pdf", "wm-2025-2026-cds1.xlsx",
  ];
  const html = files.map((f) => `<a href="/offices/ir/${f}">Common Data Set 2025-26</a>`).join("\n");
  const anchors = extractCdsAnchors(html, "https://www.wm.edu/offices/ir/university_data/cds/");
  assertEquals(anchors.filter((a) => a.is_section_file).length, 10);
  const result = pickCandidates(anchors, "landing");
  assertExists(result);
  assertEquals(result.length, 1);
  assertEquals(result[0].filename, "wm-2025-2026-cds1.xlsx");
});

Deno.test("pickCandidates: a lone year file with a trailing letter suffix is kept as the year's CDS", () => {
  // A trailing letter after the year is ambiguous: Regent uses it for
  // sections, but Fitchburg's IRP-CDS20252026-A.pdf (493 fields) and
  // Ferrum's CDS_2020-2021F.pdf are the whole CDS. With no lettered
  // siblings in the same year, keep the file instead of dropping the year.
  for (const href of [
    "/documents/2026-05/IRP-CDS20252026-A.pdf",
    "/institutionalresearch/CDS_2020-2021F.pdf",
    "/getattachment/x/CDS_2022-2023a.pdf",
  ]) {
    const anchors = extractCdsAnchors(`<a href="${href}">Common Data Set</a>`, BASE);
    const result = pickCandidates(anchors, "landing");
    assertExists(result, href);
    assertEquals(result.length, 1, href);
    assertEquals(result[0].candidate_kind, "single_document", href);
    assertEquals(result[0].is_section_file, false, href);
  }
});

Deno.test("pickCandidates: a lone explicit section file still does not stand in for the year", () => {
  const anchors = extractCdsAnchors(
    `<a href="/files/cds-section-d-2024-25.pdf">Common Data Set Section D 2024-25</a>`,
    BASE,
  );
  assertEquals(pickCandidates(anchors, "landing"), []);
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
      is_test_artifact: false,
    },
    {
      url: "https://example.edu/files/cds2024-25.pdf",
      filename: "cds2024-25.pdf",
      link_text: "Common Data Set 2024-25",
      year: "2024-25",
      year_source: "filename" as const,
      kind: "document" as const,
      is_section_file: false,
      is_test_artifact: false,
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
      is_test_artifact: false,
    },
    {
      url: "b.pdf",
      filename: "cds2024-25.pdf",
      link_text: "CDS 2024-25",
      year: "2024-25",
      year_source: "filename" as const,
      kind: "document" as const,
      is_section_file: false,
      is_test_artifact: false,
    },
    {
      url: "c.pdf",
      filename: "cds2021-22.pdf",
      link_text: "CDS 2021-22",
      year: "2021-22",
      year_source: "filename" as const,
      kind: "document" as const,
      is_section_file: false,
      is_test_artifact: false,
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
      is_test_artifact: false,
    },
  ];
  const best = findBestSourceAnchor(anchors);
  assertExists(best);
  assertEquals(best.is_section_file, true);
});

Deno.test("findBestSourceAnchor: empty input returns null", () => {
  assertEquals(findBestSourceAnchor([]), null);
});

Deno.test("extractCdsAnchors: Lafayette-style CDS-digit filename with no separator matches", () => {
  // Regression for Stage B smoke test 2026-04-15. The previous
  // CDS_KEYWORDS_RE used `\bcds\b`, which requires a non-word
  // boundary between `s` and the following character. Both `s` and
  // the digit/underscore are word characters, so `\bcds\b` did not
  // fire and every Lafayette / Samford / similar cramped-filename
  // anchor was silently dropped at the keyword gate. The relaxed
  // `(?![a-z])` right guard still rejects `cdsomething.pdf` but
  // accepts `CDS2025-2026.pdf`, `cds_2022.pdf`, `cds-2024.pdf`, and
  // bare `cds.pdf`.
  const html = `
    <a href="https://example.edu/files/CDS2025-2026.pdf">2025-2026</a>
    <a href="https://example.edu/files/cds_2022.pdf">2022-23</a>
    <a href="https://example.edu/files/cds-2021.pdf">2021-22</a>
    <a href="https://example.edu/files/cdsomething.pdf">Budget Report</a>
    <a href="https://example.edu/files/CDSummit-notes.pdf">Summit notes</a>
  `;
  const anchors = extractCdsAnchors(html, BASE);
  const filenames = anchors.map((a) => a.filename).sort();
  assertEquals(filenames, [
    "CDS2025-2026.pdf",
    "cds-2021.pdf",
    "cds_2022.pdf",
  ]);
});

Deno.test("extractCdsAnchors: test artifact filenames flagged", () => {
  const html = `
    <a href="/files/cds_2015-2016_test.pdf">CDS 2015-2016</a>
    <a href="/files/cds_2024-25_draft.pdf">CDS 2024-25 Draft</a>
    <a href="/files/cds_2023-24_backup.pdf">CDS 2023-24</a>
    <a href="/files/cds-2022-23.pdf">CDS 2022-23</a>
  `;
  const anchors = extractCdsAnchors(html, BASE);
  assertEquals(anchors.length, 4);
  const byFilename = new Map(anchors.map((a) => [a.filename, a]));
  assertEquals(byFilename.get("cds_2015-2016_test.pdf")?.is_test_artifact, true);
  assertEquals(byFilename.get("cds_2024-25_draft.pdf")?.is_test_artifact, true);
  assertEquals(byFilename.get("cds_2023-24_backup.pdf")?.is_test_artifact, true);
  assertEquals(byFilename.get("cds-2022-23.pdf")?.is_test_artifact, false);
});

Deno.test("findBestSourceAnchor: non-test file wins over higher-year test artifact", () => {
  // CSULB regression (2026-04-15): landing page exposed
  // cds_2015-2016_test.pdf with two separate anchor labels. In the
  // real corpus this was the only file, but the rank must still
  // prefer a clean sibling when one exists — otherwise a school
  // with both a real 2023-24 PDF and a leftover 2024-25_draft
  // would archive the draft as canonical.
  const anchors = [
    {
      url: "https://example.edu/files/cds2024-25_draft.pdf",
      filename: "cds2024-25_draft.pdf",
      link_text: "CDS 2024-25 (Draft)",
      year: "2024-25",
      year_source: "filename" as const,
      kind: "document" as const,
      is_section_file: false,
      is_test_artifact: true,
    },
    {
      url: "https://example.edu/files/cds2023-24.pdf",
      filename: "cds2023-24.pdf",
      link_text: "CDS 2023-24",
      year: "2023-24",
      year_source: "filename" as const,
      kind: "document" as const,
      is_section_file: false,
      is_test_artifact: false,
    },
  ];
  const best = findBestSourceAnchor(anchors);
  assertExists(best);
  assertEquals(best.filename, "cds2023-24.pdf");
});

Deno.test("findBestSourceAnchor: test artifact wins when it is the only candidate", () => {
  // The inverse: if the only archivable thing is a test file, we
  // still archive it (content detection downstream flags the year).
  // Dropping it outright would regress CSULB — the school's only
  // linked CDS is a `_test` upload and we still want those bytes.
  const anchors = [
    {
      url: "https://www.csulb.edu/sites/default/files/document/cds_2015-2016_test.pdf",
      filename: "cds_2015-2016_test.pdf",
      link_text: "CDS 2016 - 2017",
      year: "2016-17",
      year_source: "link_text" as const,
      kind: "document" as const,
      is_section_file: false,
      is_test_artifact: true,
    },
  ];
  const best = findBestSourceAnchor(anchors);
  assertExists(best);
  assertEquals(best.filename, "cds_2015-2016_test.pdf");
  assertEquals(best.is_test_artifact, true);
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

// Trimmed from https://kb.astate.edu/books/common-data-set/page/latest-cds
// (BookStack). The real CDS is an extension-less attachment linked from
// the page body; the export menu renders the wiki page itself to PDF.
const BOOKSTACK_LATEST_CDS_HTML = `
  <div class="page-content">
    <p><a href="https://kb.astate.edu/attachments/2113">View the latest CDS (25-26) &gt;&gt;</a></p>
  </div>
  <div id="page-attachments">
    <a href="https://kb.astate.edu/attachments/2113" class="icon-item"><span>Download</span></a>
  </div>
  <ul class="export-menu">
    <li><a href="https://kb.astate.edu/books/common-data-set/page/latest-cds/export/html">Contained Web File .html</a></li>
    <li><a href="https://kb.astate.edu/books/common-data-set/page/latest-cds/export/pdf">PDF File .pdf</a></li>
    <li><a href="https://kb.astate.edu/books/common-data-set/page/latest-cds/export/plaintext">Plain Text File .txt</a></li>
  </ul>
`;

Deno.test("findDownloadLinks: never returns page-export renders (BookStack /export/pdf)", () => {
  const anchors = findDownloadLinks(
    BOOKSTACK_LATEST_CDS_HTML,
    "https://kb.astate.edu/books/common-data-set/page/latest-cds",
  );
  assertEquals(anchors.some((a) => /\/export\//.test(a.url)), false);
  assertEquals(anchors.some((a) => a.url === "https://kb.astate.edu/attachments/2113"), true);
});

Deno.test("extractSubpageDocuments: BookStack attachment link becomes the year's document", () => {
  const docs = extractSubpageDocuments(
    BOOKSTACK_LATEST_CDS_HTML,
    "https://kb.astate.edu/books/common-data-set/page/latest-cds",
    { year: null, year_source: "unknown" },
  );
  assertEquals(docs.map((d) => d.url), ["https://kb.astate.edu/attachments/2113"]);
  assertEquals(docs[0].kind, "document");
  assertEquals(docs[0].year, "2025-26");
});

Deno.test("extractSubpageDocuments: a real PDF beats a same-year download-endpoint link", () => {
  const docs = extractSubpageDocuments(
    `<a href="/ir/cds-downloads/2024">Common Data Set 2024-25 downloads</a>
     <a href="/files/cds-2024-25.pdf">Common Data Set 2024-25</a>`,
    "https://example.edu/ir/cds/",
    { year: null, year_source: "unknown" },
  );
  assertEquals(docs.map((d) => d.url), ["https://example.edu/files/cds-2024-25.pdf"]);
});

Deno.test("extractCdsAnchors: page-export endpoints are not CDS anchors", () => {
  const anchors = extractCdsAnchors(
    `<a href="/books/common-data-set/export/pdf">PDF File</a>
     <a href="/books/common-data-set/page/latest-cds">Latest CDS</a>`,
    "https://kb.astate.edu/books/common-data-set",
  );
  assertEquals(anchors.map((a) => a.url), ["https://kb.astate.edu/books/common-data-set/page/latest-cds"]);
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

Deno.test("rewriteGoogleDriveUrl: /file/d/ID/view form", () => {
  // Stanford hosts every year of their CDS as Drive share links.
  const input =
    "https://drive.google.com/file/d/1GIPKgVj1d86dkmLkHI_mZVCk_iY6kiCp/view?usp=sharing";
  const expected =
    "https://drive.google.com/uc?export=download&id=1GIPKgVj1d86dkmLkHI_mZVCk_iY6kiCp&confirm=t";
  assertEquals(rewriteGoogleDriveUrl(input), expected);
});

Deno.test("rewriteGoogleDriveUrl: /open?id=ID form", () => {
  const input = "https://drive.google.com/open?id=abc123xyz";
  const expected =
    "https://drive.google.com/uc?export=download&id=abc123xyz&confirm=t";
  assertEquals(rewriteGoogleDriveUrl(input), expected);
});

Deno.test("rewriteGoogleDriveUrl: non-drive URL passes through", () => {
  const input = "https://example.edu/cds-2024-25.pdf";
  assertEquals(rewriteGoogleDriveUrl(input), input);
});

Deno.test("extractCdsAnchors: Wayback toolbar links rewritten to id_", () => {
  const html = `
    <a href="https://web.archive.org/web/20220701053930/https://example.edu/cds_2019-2020.pdf">CDS 2019-2020</a>
  `;
  const anchors = extractCdsAnchors(html, "https://example.edu/ir/");
  assertEquals(anchors.length, 1);
  assertEquals(
    anchors[0].url,
    "https://web.archive.org/web/20220701053930id_/https://example.edu/cds_2019-2020.pdf",
  );
  assertEquals(anchors[0].year, "2019-20");
});

Deno.test("extractCdsAnchors: Stanford-style Google Drive links rewritten", () => {
  const html = `
    <h2>Stanford Common Data Set Reports</h2>
    <a href="https://drive.google.com/file/d/1GIPKgVj1d86dkmLkHI_mZVCk_iY6kiCp/view?usp=sharing">Stanford CDS 2025-2026</a>
    <a href="https://drive.google.com/file/d/12MjIqdzzHiECf6hfRlbU3RmmIy14hl1H/view?usp=sharing">Stanford CDS 2024-2025</a>
  `;
  const anchors = extractCdsAnchors(html, "https://irds.stanford.edu/data-findings/cds");
  assertEquals(anchors.length, 2);
  // Both should be rewritten to direct-download URLs
  for (const a of anchors) {
    assertEquals(a.url.startsWith("https://drive.google.com/uc?export=download&id="), true);
  }
  // Year should still be parsed from link text
  const years = anchors.map((a) => a.year).sort();
  assertEquals(years, ["2024-25", "2025-26"]);
});

Deno.test("findDownloadLinks: commondataset.org excluded here too", () => {
  // Belt-and-suspenders: the excluded-host filter applies to the
  // fallback download-link scanner as well, not just the strict pass.
  const html = `<a href="https://commondataset.org/template.pdf">Download Template</a>`;
  const anchors = findDownloadLinks(html, "https://example.edu/item/1");
  assertEquals(anchors.length, 0);
});

// ─── pickCandidates (ADR 0007 Stage B) ─────────────────────────────────────

Deno.test("pickCandidates: Lafayette-style multi-year landing page returns every year", () => {
  // Real shape of Lafayette's IR page: N anchors, all pointing at
  // individual year-labeled PDFs. Stage B archives all of them as
  // separate cds_documents rows.
  const anchors = [2024, 2023, 2022, 2021].map((y) => ({
    url: `https://oir.lafayette.edu/files/CDS${y}-${y + 1}.pdf`,
    filename: `CDS${y}-${y + 1}.pdf`,
    link_text: `${y}-${y + 1}`,
    year: `${y}-${String((y + 1) % 100).padStart(2, "0")}`,
    year_source: "filename" as const,
    kind: "document" as const,
    is_section_file: false,
    is_test_artifact: false,
  }));
  const result = pickCandidates(anchors, "landing");
  assertExists(result);
  assertEquals(result.length, 4);
  assertEquals(
    result.map((r) => r.cds_year).sort(),
    ["2021-22", "2022-23", "2023-24", "2024-25"],
  );
  assertEquals(result.every((r) => r.discovered_via === "landing"), true);
});

Deno.test("pickCandidates: single year-less candidate returns UNKNOWN_YEAR_SENTINEL", () => {
  // Direct-doc hint case: the URL is a CDS PDF whose filename carries
  // no parseable year (Bowie State's common-data-set.pdf, West Texas
  // A&M's CDS.pdf). Year fills in when extraction runs.
  const anchors = [{
    url: "https://www.bowiestate.edu/academic/common-data-set.pdf",
    filename: "common-data-set.pdf",
    link_text: "Common Data Set",
    year: null,
    year_source: "unknown" as const,
    kind: "document" as const,
    is_section_file: false,
    is_test_artifact: false,
  }];
  const result = pickCandidates(anchors, "landing");
  assertExists(result);
  assertEquals(result.length, 1);
  assertEquals(result[0].cds_year, UNKNOWN_YEAR_SENTINEL);
});

Deno.test("pickCandidates: mixed year-labeled + year-less drops the year-less ones", () => {
  const anchors = [
    {
      url: "https://ex.edu/cds2024-25.pdf",
      filename: "cds2024-25.pdf",
      link_text: "CDS 2024-25",
      year: "2024-25",
      year_source: "filename" as const,
      kind: "document" as const,
      is_section_file: false,
      is_test_artifact: false,
    },
    {
      url: "https://ex.edu/cds-extras.pdf",
      filename: "cds-extras.pdf",
      link_text: "Supplemental",
      year: null,
      year_source: "unknown" as const,
      kind: "document" as const,
      is_section_file: false,
      is_test_artifact: false,
    },
  ];
  const result = pickCandidates(anchors, "landing");
  assertExists(result);
  assertEquals(result.length, 1);
  assertEquals(result[0].cds_year, "2024-25");
});

Deno.test("pickCandidates: multi-candidate all year-less returns null (Stage B limitation)", () => {
  // The edge case scoped out of Stage B. Two CDS-ish anchors, neither
  // has a year signal. Cannot disambiguate under the current unique
  // constraint without a per-candidate discriminator. pickCandidates
  // returns null; resolveCdsForSchool converts that to a specific
  // no_cds_found reason mentioning the limitation.
  const anchors = [
    {
      url: "https://ex.edu/cds.pdf",
      filename: "cds.pdf",
      link_text: "Common Data Set",
      year: null,
      year_source: "unknown" as const,
      kind: "document" as const,
      is_section_file: false,
      is_test_artifact: false,
    },
    {
      url: "https://ex.edu/common-data-set.pdf",
      filename: "common-data-set.pdf",
      link_text: "Common Data Set",
      year: null,
      year_source: "unknown" as const,
      kind: "document" as const,
      is_section_file: false,
      is_test_artifact: false,
    },
  ];
  const result = pickCandidates(anchors, "landing");
  assertEquals(result, null);
});

Deno.test("pickCandidates: clean beats demoted when a clean sibling exists", () => {
  const anchors = [
    {
      url: "https://ex.edu/cds2024-25_test.pdf",
      filename: "cds2024-25_test.pdf",
      link_text: "CDS 2023-24 (Test)",
      year: "2023-24",
      year_source: "filename" as const,
      kind: "document" as const,
      is_section_file: false,
      is_test_artifact: true,
    },
    {
      url: "https://ex.edu/cds2023-24.pdf",
      filename: "cds2023-24.pdf",
      link_text: "CDS 2023-24",
      year: "2023-24",
      year_source: "filename" as const,
      kind: "document" as const,
      is_section_file: false,
      is_test_artifact: false,
    },
  ];
  const result = pickCandidates(anchors, "landing");
  assertExists(result);
  assertEquals(result.length, 1);
  assertEquals(result[0].filename, "cds2023-24.pdf");
  assertEquals(result[0].is_test_artifact, false);
});

Deno.test("pickCandidates: section-only years become a section package", () => {
  const anchors = [
    {
      url: "https://aire.ku.edu/sites/aire/files/files/CDS/2025-2026/C.pdf",
      filename: "C.pdf",
      link_text: "C. First-Time, First-Year Admission",
      year: "2025-26",
      year_source: "url_path" as const,
      kind: "document" as const,
      is_section_file: true,
      is_test_artifact: false,
    },
    {
      url: "https://aire.ku.edu/sites/aire/files/files/CDS/2025-2026/J.pdf",
      filename: "J.pdf",
      link_text: "J. Degrees Conferred",
      year: "2025-26",
      year_source: "url_path" as const,
      kind: "document" as const,
      is_section_file: true,
      is_test_artifact: false,
    },
  ];
  const result = pickCandidates(anchors, "landing");
  assertExists(result);
  assertEquals(result.length, 1);
  assertEquals(result[0].candidate_kind, "section_package");
  assertEquals(result[0].filename, "cds-2025-26-sections-CJ.pdf");
  if (result[0].candidate_kind === "section_package") {
    assertEquals(result[0].parts.map((p) => p.section), ["C", "J"]);
  }
});

Deno.test("pickCandidates: older full CDS and current sectionized CDS can coexist", () => {
  const anchors = [
    {
      url: "https://www.oxy.edu/sites/default/files/assets/Institutional_Research/CDS_C_2526_0.pdf",
      filename: "CDS_C_2526_0.pdf",
      link_text: "Admissions",
      year: "2025-26",
      year_source: "filename" as const,
      kind: "document" as const,
      is_section_file: true,
      is_test_artifact: false,
    },
    {
      url: "https://www.oxy.edu/sites/default/files/assets/Institutional_Research/CDS_J_2526.pdf",
      filename: "CDS_J_2526.pdf",
      link_text: "Degrees Conferred",
      year: "2025-26",
      year_source: "filename" as const,
      kind: "document" as const,
      is_section_file: true,
      is_test_artifact: false,
    },
    {
      url: "https://www.oxy.edu/sites/default/files/assets/Institutional_Research/CDS%202023-24.pdf",
      filename: "CDS 2023-24.pdf",
      link_text: "CDS 2023-24",
      year: "2023-24",
      year_source: "filename" as const,
      kind: "document" as const,
      is_section_file: false,
      is_test_artifact: false,
    },
  ];
  const result = pickCandidates(anchors, "landing");
  assertExists(result);
  assertEquals(result.map((r) => r.filename).sort(), [
    "CDS 2023-24.pdf",
    "cds-2025-26-sections-CJ.pdf",
  ]);
});

Deno.test("pickCandidates: single section-only year preserves Section C fallback", () => {
  const anchors = [
    {
      url: "https://www.cmu.edu/ira/CDS/pdf/cds_2025_26/cds-2025-c-first-time-first-year-admission.pdf",
      filename: "cds-2025-c-first-time-first-year-admission.pdf",
      link_text: "First-Time, First-Year Admission",
      year: "2025-26",
      year_source: "url_path" as const,
      kind: "document" as const,
      is_section_file: true,
      is_test_artifact: false,
    },
  ];
  const result = pickCandidates(anchors, "landing");
  assertExists(result);
  assertEquals(result.length, 1);
  assertEquals(result[0].candidate_kind, "single_document");
  assertEquals(result[0].filename, "cds-2025-c-first-time-first-year-admission.pdf");
});

Deno.test("pickCandidates: reference-only documents are skipped", () => {
  const anchors = [{
    url: "https://ex.edu/CDS_2024-2025_Definitions_.pdf",
    filename: "CDS_2024-2025_Definitions_.pdf",
    link_text: "Common Data Set Definitions",
    year: "2024-25",
    year_source: "filename" as const,
    kind: "document" as const,
    is_section_file: false,
    is_test_artifact: false,
  }];
  assertEquals(pickCandidates(anchors, "landing"), []);
});

Deno.test("pickCandidates: falls back to demoted set when no clean siblings exist (CSULB)", () => {
  // CSULB regression: the school's only archivable files are both
  // test artifacts. Without a clean fallback, the school would be
  // skipped entirely. With fallback, it ships — content detection
  // downstream will surface the actual year.
  const anchors = [{
    url: "https://csulb.edu/cds_2015-2016_test.pdf",
    filename: "cds_2015-2016_test.pdf",
    link_text: "CDS 2015-2016",
    year: "2015-16",
    year_source: "filename" as const,
    kind: "document" as const,
    is_section_file: false,
    is_test_artifact: true,
  }];
  const result = pickCandidates(anchors, "landing");
  assertExists(result);
  assertEquals(result.length, 1);
  assertEquals(result[0].is_test_artifact, true);
});

Deno.test("pickCandidates: deduplicates by URL across subpage walk duplicates", () => {
  // When the two-hop walk discovers the same PDF via different
  // subpages, pickCandidates should fold them into one row.
  const anchors = [
    {
      url: "https://ex.edu/cds2024-25.pdf",
      filename: "cds2024-25.pdf",
      link_text: "2024-25",
      year: "2024-25",
      year_source: "filename" as const,
      kind: "document" as const,
      is_section_file: false,
      is_test_artifact: false,
    },
    {
      url: "https://ex.edu/cds2024-25.pdf",
      filename: "cds2024-25.pdf",
      link_text: "CDS",
      year: "2024-25",
      year_source: "filename" as const,
      kind: "document" as const,
      is_section_file: false,
      is_test_artifact: false,
    },
  ];
  const result = pickCandidates(anchors, "subpage");
  assertExists(result);
  assertEquals(result.length, 1);
});

Deno.test("pickCandidates: empty list returns empty array (caller's choice)", () => {
  assertEquals(pickCandidates([], "landing"), []);
});

Deno.test("parentLandingCandidates: Boston-College-style direct PDF returns CDS + IR ancestors", () => {
  const hint = "https://www.bc.edu/content/dam/bc1/offices/irp/ir/cds/BC-2022-2023-CDS.pdf";
  const candidates = parentLandingCandidates(hint);
  // Expect ancestors whose paths contain /ir/ or /cds/. Generic /dam/, /bc1/,
  // /offices/ ancestors are filtered out.
  assertEquals(candidates[0], "https://www.bc.edu/content/dam/bc1/offices/irp/ir/cds/");
  assertEquals(candidates[1], "https://www.bc.edu/content/dam/bc1/offices/irp/ir/");
});

Deno.test("parentLandingCandidates: OU DAM path keeps irr / common-data-sets ancestors", () => {
  const hint =
    "https://www.ou.edu/content/dam/irr/docs/common-data-sets/norman-campus-only/2023-24-nc/CDS%202023-2024%20Combined.pdf";
  const candidates = parentLandingCandidates(hint);
  const urls = new Set(candidates);
  assertEquals(
    urls.has(
      "https://www.ou.edu/content/dam/irr/docs/common-data-sets/norman-campus-only/2023-24-nc/",
    ),
    true,
  );
  assertEquals(
    urls.has(
      "https://www.ou.edu/content/dam/irr/docs/common-data-sets/norman-campus-only/",
    ),
    true,
  );
});

Deno.test("parentLandingCandidates: Drupal upload-dir path has no CDS-like segments, returns []", () => {
  const hint = "https://oir.brown.edu/sites/default/files/2020-04/CDS2009_2010.pdf";
  const candidates = parentLandingCandidates(hint);
  // Path segments are {sites, default, files, 2020-04}. None match the
  // CDS-like regex, so no ancestor is fetched. Pre-upgrade behavior
  // (archive the direct doc only) is preserved for this URL shape.
  assertEquals(candidates.length, 0);
});

Deno.test("parentLandingCandidates: keeps CDS-like segment even inside WP uploads", () => {
  const hint = "https://example.edu/wp-content/uploads/cds/CDS-2024-25.pdf";
  const candidates = parentLandingCandidates(hint);
  // The /cds/ segment makes this ancestor pass the filter.
  assertEquals(candidates[0], "https://example.edu/wp-content/uploads/cds/");
});

Deno.test("parentLandingCandidates: walks up through CDS-like path levels", () => {
  const hint = "https://example.edu/ir/annual/common-data-set/2024/cds.pdf";
  const candidates = parentLandingCandidates(hint);
  // /2024/ under /common-data-set/ — segments contain /ir/ and /common-data-set/
  // so all three ancestor levels are kept.
  const urls = new Set(candidates);
  assertEquals(urls.has("https://example.edu/ir/annual/common-data-set/2024/"), true);
  assertEquals(urls.has("https://example.edu/ir/annual/common-data-set/"), true);
  assertEquals(urls.has("https://example.edu/ir/annual/"), true);
});

Deno.test("parentLandingCandidates: rejects cross-scheme + malformed URLs", () => {
  assertEquals(parentLandingCandidates("not a url").length, 0);
  assertEquals(parentLandingCandidates("javascript:alert(1)").length, 0);
  assertEquals(parentLandingCandidates("ftp://example.edu/cds.pdf").length, 0);
  // Root-level file has no meaningful parent to walk to.
  assertEquals(parentLandingCandidates("https://example.edu/cds.pdf").length, 0);
});

Deno.test("wellKnownPathUrls: expands to host-rooted CDS landing paths", () => {
  const hint = "https://irp.dpb.cornell.edu/wp-content/uploads/2025/02/CDS-2024-2025-v1.pdf";
  const urls = wellKnownPathUrls(hint);
  // Check a few expected candidates — the exact list may evolve, so this
  // test is permissive. Covers both short (subdomain-root) and long
  // (site-root-with-IR-prefix) shapes so regressions on either family
  // surface here.
  const set = new Set(urls);
  assertEquals(set.has("https://irp.dpb.cornell.edu/common-data-set"), true);
  assertEquals(set.has("https://irp.dpb.cornell.edu/common-data-set/"), true);
  assertEquals(set.has("https://irp.dpb.cornell.edu/institutional-data/common-data-set"), true);
  assertEquals(set.has("https://irp.dpb.cornell.edu/institutional-research/common-data-set/"), true);
  assertEquals(set.has("https://irp.dpb.cornell.edu/ir/common-data-set/"), true);
  assertEquals(set.has("https://irp.dpb.cornell.edu/irr/other-reports"), true);
  assertEquals(set.has("https://irp.dpb.cornell.edu/iea/university-data"), true);
  // Origin is preserved without the hint's path.
  for (const u of urls) {
    assertEquals(u.startsWith("https://irp.dpb.cornell.edu"), true);
  }
});

Deno.test("extractIrHubLinks: Tulsa-style IR link on the homepage", () => {
  const html = `
    <html><body>
      <a href="/admissions">Apply now</a>
      <a href="/about-tcc">About TCC</a>
      <a href="/about-tcc/institutional-research">Institutional Research</a>
      <a href="https://other.edu/institutional-research">Someone else IR</a>
    </body></html>
  `;
  const links = extractIrHubLinks(html, "https://www.tulsacc.edu/");
  assertEquals(links, ["https://www.tulsacc.edu/about-tcc/institutional-research"]);
});

Deno.test("extractAboutLinks: one about hop toward an IR office", () => {
  const html = `
    <a href="/about-tcc">About TCC</a>
    <a href="/admissions">Admissions</a>
  `;
  assertEquals(
    extractAboutLinks(html, "https://www.tulsacc.edu/"),
    ["https://www.tulsacc.edu/about-tcc"],
  );
  const aboutHtml = `
    <a href="/about-tcc/leadership">Leadership</a>
    <a href="/about-tcc/institutional-research">Institutional Research</a>
  `;
  assertEquals(
    extractIrHubLinks(aboutHtml, "https://www.tulsacc.edu/about-tcc"),
    ["https://www.tulsacc.edu/about-tcc/institutional-research"],
  );
});

Deno.test("extractIrHubLinks: ira subdomain and short /ir path", () => {
  assertEquals(
    extractIrHubLinks(
      '<a href="https://ira.example.edu/">IRA</a>',
      "https://www.example.edu/",
    ),
    ["https://ira.example.edu/"],
  );
  assertEquals(
    extractIrHubLinks(
      '<a href="/first-year">First year</a><a href="/ir/">IR office</a>',
      "https://example.edu/",
    ),
    ["https://example.edu/ir/"],
  );
});

Deno.test("wellKnownIrHubUrls: conventional IR hubs on the landing origin", () => {
  const urls = wellKnownIrHubUrls("https://www.tulsacc.edu/");
  assertEquals(urls.includes("https://www.tulsacc.edu/institutional-research"), true);
  assertEquals(urls.includes("https://www.tulsacc.edu/ir"), true);
  for (const url of urls) {
    assertEquals(url.startsWith("https://www.tulsacc.edu/"), true);
  }
});

Deno.test("rewriteBoxUrl: subdomain share URL → direct static", () => {
  // UPenn's share URL shape — the main case this rewriter exists for.
  const got = rewriteBoxUrl("https://upenn.box.com/s/ckv4frz37rzxa4u6bdiv2h4yzykqm4ef");
  assertEquals(got, "https://upenn.box.com/shared/static/ckv4frz37rzxa4u6bdiv2h4yzykqm4ef");
});

Deno.test("rewriteBoxUrl: .app.box.com variant canonicalized", () => {
  // Some share URLs redirect to the .app. subdomain; rewrite should
  // canonicalize to the non-.app form, which reliably serves the file.
  const got = rewriteBoxUrl("https://upenn.app.box.com/s/abc123def456");
  assertEquals(got, "https://upenn.box.com/shared/static/abc123def456");
});

Deno.test("rewriteBoxUrl: bare app.box.com share", () => {
  const got = rewriteBoxUrl("https://app.box.com/s/xyz999");
  assertEquals(got, "https://app.box.com/shared/static/xyz999");
});

Deno.test("rewriteBoxUrl: non-box URL passes through", () => {
  const got = rewriteBoxUrl("https://example.edu/cds-2024.pdf");
  assertEquals(got, "https://example.edu/cds-2024.pdf");
});

Deno.test("rewriteBoxUrl: already-rewritten URL passes through", () => {
  // /shared/static/ form has no /s/ segment, so the rewrite doesn't fire.
  const got = rewriteBoxUrl("https://upenn.box.com/shared/static/abc");
  assertEquals(got, "https://upenn.box.com/shared/static/abc");
});

Deno.test("rewriteWaybackUrl: toolbar URL gets id_ flag", () => {
  const input =
    "https://web.archive.org/web/20220701053930/https://example.edu/cds.pdf";
  assertEquals(
    rewriteWaybackUrl(input),
    "https://web.archive.org/web/20220701053930id_/https://example.edu/cds.pdf",
  );
});

Deno.test("rewriteWaybackUrl: existing id_ is unchanged", () => {
  const input =
    "https://web.archive.org/web/20220701053930id_/https://example.edu/cds.pdf";
  assertEquals(rewriteWaybackUrl(input), input);
});

Deno.test("rewriteWaybackUrl: if_ flag becomes id_", () => {
  const input =
    "https://web.archive.org/web/20220701053930if_/https://example.edu/cds.pdf";
  assertEquals(
    rewriteWaybackUrl(input),
    "https://web.archive.org/web/20220701053930id_/https://example.edu/cds.pdf",
  );
});

Deno.test("rewriteWaybackUrl: non-wayback URL passes through", () => {
  const input = "https://example.edu/cds.pdf";
  assertEquals(rewriteWaybackUrl(input), input);
});

Deno.test("wellKnownPathUrls: rejects malformed/non-http URLs", () => {
  assertEquals(wellKnownPathUrls("not a url").length, 0);
  assertEquals(wellKnownPathUrls("javascript:alert(1)").length, 0);
  assertEquals(wellKnownPathUrls("ftp://example.edu/file.pdf").length, 0);
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
      is_test_artifact: false,
    },
  ];
  assertEquals(findBestSourceAnchor(anchors), null);
});


// ─── applyPinnedUrls ─────────────────────────────────────────────────────────

// A school that publishes one CDS per campus: several full, clean files for the
// same year. pickCandidates takes the first on the page.
const CAMPUS_PAGE = `
  <html><body>
    <a href="https://example.edu/files/CDS_2024_2025_Abington.pdf">Abington 2024-2025</a>
    <a href="https://example.edu/files/CDS_2024_2025_MainCampus.pdf">Main Campus 2024-2025</a>
    <a href="https://example.edu/files/CDS_2024_2025_York.pdf">York 2024-2025</a>
    <a href="https://example.edu/files/CDS_2023_2024_Abington.pdf">Abington 2023-2024</a>
    <a href="https://example.edu/files/CDS_2023_2024_MainCampus.pdf">Main Campus 2023-2024</a>
  </body></html>
`;
const MAIN_2024 = "https://example.edu/files/CDS_2024_2025_MainCampus.pdf";

Deno.test("applyPinnedUrls: a pin replaces the first-listed campus file for its year only", () => {
  const anchors = extractCdsAnchors(CAMPUS_PAGE, BASE).filter((a) => a.kind === "document");
  const picked = pickCandidates(anchors, "landing");
  assertExists(picked);
  // Without a pin the first file on the page wins: the wrong campus.
  assertEquals(picked.find((d) => d.cds_year === "2024-25")?.url, "https://example.edu/files/CDS_2024_2025_Abington.pdf");

  const pinned = applyPinnedUrls(picked, [{ url: MAIN_2024, year: "2024-25" }]);
  assertEquals(pinned.length, picked.length);
  const doc2024 = pinned.find((d) => d.cds_year === "2024-25");
  assertEquals(doc2024?.url, MAIN_2024);
  assertEquals(doc2024?.filename, "CDS_2024_2025_MainCampus.pdf");
  assertEquals(doc2024?.candidate_kind, "single_document");
  assertEquals(doc2024?.is_section_file, false);
  assertEquals(doc2024?.discovered_via, "direct");
  // The unpinned year keeps the resolver's choice.
  assertEquals(pinned.find((d) => d.cds_year === "2023-24")?.url, "https://example.edu/files/CDS_2023_2024_Abington.pdf");
});

Deno.test("applyPinnedUrls: a pinned year the page does not list is added", () => {
  const anchors = extractCdsAnchors(CAMPUS_PAGE, BASE).filter((a) => a.kind === "document");
  const picked = pickCandidates(anchors, "landing")!;
  const url = "https://example.edu/files/CDS_2022_2023_MainCampus.pdf";
  const pinned = applyPinnedUrls(picked, [{ url, year: "2022-23" }]);
  assertEquals(pinned.length, picked.length + 1);
  assertEquals(pinned.find((d) => d.cds_year === "2022-23")?.url, url);
});

Deno.test("applyPinnedUrls: one document per pinned year, even when the resolver returned two", () => {
  const anchors = extractCdsAnchors(CAMPUS_PAGE, BASE).filter((a) => a.kind === "document");
  const picked = pickCandidates(anchors, "landing")!;
  const doubled = [...picked, ...picked];
  const pinned = applyPinnedUrls(doubled, [{ url: MAIN_2024, year: "2024-25" }]);
  assertEquals(pinned.filter((d) => d.cds_year === "2024-25").map((d) => d.url), [MAIN_2024]);
});

Deno.test("applyPinnedUrls: no pins, an unsafe URL or a repeated year change nothing", () => {
  const anchors = extractCdsAnchors(CAMPUS_PAGE, BASE).filter((a) => a.kind === "document");
  const picked = pickCandidates(anchors, "landing")!;
  assertEquals(applyPinnedUrls(picked, []), picked);
  assertEquals(applyPinnedUrls(picked, [{ url: "http://169.254.169.254/latest", year: "2024-25" }]), picked);
  assertEquals(applyPinnedUrls(picked, [{ url: "not a url", year: "2024-25" }]), picked);
  // The first pin for a year is the one used.
  const twice = applyPinnedUrls(picked, [
    { url: MAIN_2024, year: "2024-25" },
    { url: "https://example.edu/files/CDS_2024_2025_York.pdf", year: "2024-25" },
  ]);
  assertEquals(twice.find((d) => d.cds_year === "2024-25")?.url, MAIN_2024);
});

// ── mergeHintWithPageDocs: the preferred file for a direct-file hint's year comes first ──

function hintDoc(url: string, year: string, flags: { section?: boolean; draft?: boolean } = {}): ResolvedDocument {
  return {
    candidate_kind: "single_document",
    url,
    cds_year: year,
    filename: url.split("/").pop() ?? "",
    is_section_file: flags.section ?? false,
    is_test_artifact: flags.draft ?? false,
    discovered_via: "direct",
  };
}

function pageDoc(url: string, year: string, flags: { section?: boolean; draft?: boolean } = {}): ResolvedCandidate {
  return { ...hintDoc(url, year, flags), discovered_via: "landing" };
}

const HINT_2024 = "https://example.edu/up/CDS-2024-2025.pdf";

Deno.test("mergeHintWithPageDocs: the page's file for the hint's year goes first, the hint after it", () => {
  // Worcester State 2024-25: the hint and the page name different files.
  const merged = mergeHintWithPageDocs(hintDoc(HINT_2024, "2024-25"), [
    pageDoc("https://example.edu/up/CDS-2025-2026.xlsx", "2025-26"),
    pageDoc("https://example.edu/up/CDS-2024-2025-w-Cost.pdf", "2024-25"),
    pageDoc("https://example.edu/up/CDS-2023-2024.pdf", "2023-24"),
  ]);
  assertEquals(merged.map((d) => d.url), [
    "https://example.edu/up/CDS-2024-2025-w-Cost.pdf",
    HINT_2024,
    "https://example.edu/up/CDS-2025-2026.xlsx",
    "https://example.edu/up/CDS-2023-2024.pdf",
  ]);
});

Deno.test("mergeHintWithPageDocs: the hint is listed once when the page links it or has no file for its year", () => {
  const hint = hintDoc(HINT_2024, "2024-25");
  const sameUrl = mergeHintWithPageDocs(hint, [
    pageDoc(HINT_2024 + "#page=1", "2024-25"),
    pageDoc("https://example.edu/up/CDS-2023-2024.pdf", "2023-24"),
  ]);
  assertEquals(sameUrl.map((d) => [d.url, d.discovered_via]), [
    [HINT_2024, "direct"],
    ["https://example.edu/up/CDS-2023-2024.pdf", "landing"],
  ]);
  const otherYears = mergeHintWithPageDocs(hint, [
    pageDoc("https://example.edu/up/CDS-2023-2024.pdf", "2023-24"),
  ]);
  assertEquals(otherYears.map((d) => d.url), [HINT_2024, "https://example.edu/up/CDS-2023-2024.pdf"]);
  assertEquals(mergeHintWithPageDocs(hint, []).map((d) => d.url), [HINT_2024]);
});

Deno.test("mergeHintWithPageDocs: a clean full-file hint stays ahead of a section file, a section package or a draft", () => {
  const hint = hintDoc(HINT_2024, "2024-25");
  const section = "https://example.edu/up/CDS-2024-2025-Section-C.pdf";
  assertEquals(
    mergeHintWithPageDocs(hint, [pageDoc(section, "2024-25", { section: true })]).map((d) => d.url),
    [HINT_2024, section],
  );
  const pkg: ResolvedCandidate = {
    candidate_kind: "section_package",
    url: "https://example.edu/up/CDS-2024-2025-A.pdf",
    cds_year: "2024-25",
    filename: "CDS-2024-2025-A.pdf",
    is_section_file: true,
    is_test_artifact: false,
    discovered_via: "landing",
    parts: [],
  };
  assertEquals(mergeHintWithPageDocs(hint, [pkg]).map((d) => d.url), [HINT_2024, pkg.url]);
  const draft = "https://example.edu/up/CDS-2024-2025-DRAFT.pdf";
  assertEquals(
    mergeHintWithPageDocs(hint, [pageDoc(draft, "2024-25", { draft: true })]).map((d) => d.url),
    [HINT_2024, draft],
  );
  // A section-file hint gives way to whatever the page has for that year.
  const sectionHint = hintDoc("https://example.edu/up/CDS-2024-2025-Section-A.pdf", "2024-25", { section: true });
  assertEquals(
    mergeHintWithPageDocs(sectionHint, [pageDoc(section, "2024-25", { section: true })]).map((d) => d.url),
    [section, sectionHint.url],
  );
});

Deno.test("mergeHintWithPageDocs: a hint with no year keeps its place beside every page document", () => {
  const hint = hintDoc("https://example.edu/up/cds_all.pdf", UNKNOWN_YEAR_SENTINEL);
  const merged = mergeHintWithPageDocs(hint, [pageDoc(HINT_2024, "2024-25")]);
  assertEquals(merged.map((d) => d.url), ["https://example.edu/up/cds_all.pdf", HINT_2024]);
});

Deno.test("applyPinnedUrls: a pin replaces both the page's file and the hint for its year", () => {
  const merged = mergeHintWithPageDocs(hintDoc(HINT_2024, "2024-25"), [
    pageDoc("https://example.edu/up/CDS-2024-2025-w-Cost.pdf", "2024-25"),
  ]);
  const pinned = applyPinnedUrls(merged, [{ url: "https://example.edu/up/pinned.pdf", year: "2024-25" }]);
  assertEquals(pinned.map((d) => d.url), ["https://example.edu/up/pinned.pdf"]);
});

// ── <base href> ───────────────────────────────────────────────────────────

const BASE_TAG_PAGE = "https://example.edu/institutional-research/common-data-set/";

Deno.test("extractCdsAnchors: relative links resolve against <base href>, not the page", () => {
  const html = `
    <html><head><base href="https://www.example.edu/" /></head><body>
      <a href="documents/offices/ir/2026/CDS-2025-26-Example-College.pdf">Common Data Set 2025-26</a>
      <a href="/documents/offices/ir/2025/CDS-2024-25-Example-College.pdf">Common Data Set 2024-25</a>
      <a href="https://files.example.edu/CDS-2023-24.pdf">Common Data Set 2023-24</a>
    </body></html>
  `;
  assertEquals(extractCdsAnchors(html, BASE_TAG_PAGE).map((a) => a.url), [
    "https://www.example.edu/documents/offices/ir/2026/CDS-2025-26-Example-College.pdf",
    "https://www.example.edu/documents/offices/ir/2025/CDS-2024-25-Example-College.pdf",
    "https://files.example.edu/CDS-2023-24.pdf",
  ]);
});

Deno.test("extractCdsAnchors: without a usable <base href> links resolve against the page", () => {
  const link = `<a href="files/CDS-2025-26.pdf">Common Data Set 2025-26</a>`;
  const onPage = [BASE_TAG_PAGE + "files/CDS-2025-26.pdf"];
  for (const head of ["", `<base target="_blank">`, `<base href="">`, `<base href="javascript:void(0)">`]) {
    const html = `<html><head>${head}</head><body>${link}</body></html>`;
    assertEquals(extractCdsAnchors(html, BASE_TAG_PAGE).map((a) => a.url), onPage, head);
  }
});

Deno.test("extractCdsAnchors: a relative <base href> is itself resolved against the page, and the first one wins", () => {
  const html = `
    <html><head><base href="/media/"><base href="https://other.example.org/"></head><body>
      <a href="cds/CDS-2025-26.pdf">Common Data Set 2025-26</a>
    </body></html>
  `;
  assertEquals(extractCdsAnchors(html, BASE_TAG_PAGE).map((a) => a.url), [
    "https://example.edu/media/cds/CDS-2025-26.pdf",
  ]);
});

Deno.test("findDownloadLinks and extractIrHubLinks: <base href> applies to them too", () => {
  const item = `
    <html><head><base href="https://www.example.edu/"></head><body>
      <a href="cgi/viewcontent.cgi?article=1017&amp;context=cds">Download</a>
    </body></html>
  `;
  assertEquals(findDownloadLinks(item, "https://example.edu/cds/17/").map((a) => a.url), [
    "https://www.example.edu/cgi/viewcontent.cgi?article=1017&context=cds",
  ]);
  const home = `
    <html><head><base href="https://www.example.edu/"></head><body>
      <a href="about/institutional-research">Institutional Research</a>
    </body></html>
  `;
  assertEquals(extractIrHubLinks(home, "https://www.example.edu/home/index.html"), [
    "https://www.example.edu/about/institutional-research",
  ]);
});

Deno.test("extractCdsAnchors: a <base href> in the body or after the first link still applies; one inside SVG does not", () => {
  const late = `
    <html><body>
      <a href="files/CDS-2025-26.pdf">Common Data Set 2025-26</a>
      <base href="https://www.example.edu/">
    </body></html>
  `;
  assertEquals(extractCdsAnchors(late, BASE_TAG_PAGE).map((a) => a.url), [
    "https://www.example.edu/files/CDS-2025-26.pdf",
  ]);
  const svg = `
    <html><body>
      <svg><base href="https://other.example.org/"></base></svg>
      <a href="files/CDS-2025-26.pdf">Common Data Set 2025-26</a>
    </body></html>
  `;
  assertEquals(extractCdsAnchors(svg, BASE_TAG_PAGE).map((a) => a.url), [
    BASE_TAG_PAGE + "files/CDS-2025-26.pdf",
  ]);
});

Deno.test("extractCdsAnchors: an in-page link with a leading space is still skipped under <base href>", () => {
  const html = `
    <html><head><base href="https://www.example.edu/"></head><body>
      <a href=" #cds">Common Data Set 2024-25</a>
      <a href=" files/CDS-2025-26.pdf ">Common Data Set 2025-26</a>
    </body></html>
  `;
  assertEquals(extractCdsAnchors(html, BASE_TAG_PAGE).map((a) => a.url), [
    "https://www.example.edu/files/CDS-2025-26.pdf",
  ]);
});

Deno.test("extractIrHubLinks: links that a <base href> sends to another host are dropped", () => {
  const home = `
    <html><head><base href="https://other.example.org/"></head><body>
      <a href="about/institutional-research">Institutional Research</a>
    </body></html>
  `;
  assertEquals(extractIrHubLinks(home, "https://www.example.edu/home/index.html"), []);
});

Deno.test("capSubpages: reports how many subpages the cap dropped", () => {
  const subs = Array.from({ length: 30 }, (_, i) => i);
  const r = capSubpages(subs, 25);
  assertEquals(r.kept.length, 25);
  assertEquals(r.dropped, 5);
  assertEquals(capSubpages([1, 2], 25), { kept: [1, 2], dropped: 0 });
});

Deno.test("resolveCdsForSchool: 30 qualifying subpages follow 25 and report 5 dropped", async () => {
  const links = Array.from(
    { length: 30 },
    (_, i) => `<a href="/cds/page${i}">Common Data Set page ${i}</a>`,
  ).join("\n");
  const html = (body: string, url: string) => {
    const resp = new Response(`<html><body>${body}</body></html>`, {
      status: 200,
      headers: { "content-type": "text/html" },
    });
    // A constructed Response has an empty url; fetchText re-checks it.
    Object.defineProperty(resp, "url", { value: url });
    return resp;
  };
  const childFetches: string[] = [];
  const realFetch = globalThis.fetch;
  globalThis.fetch = ((input: Request | URL | string) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    if (url.includes("/cds/page")) {
      childFetches.push(url);
      return Promise.resolve(html("nothing here", url));
    }
    return Promise.resolve(html(links, url));
  }) as typeof fetch;
  try {
    const r = await resolveCdsForSchool("https://example.edu/institutional-research/");
    assertEquals(childFetches.length, 25);
    assertEquals(r.kind === "blocked_url" ? undefined : r.probe?.subpagesDropped, 5);
  } finally {
    globalThis.fetch = realFetch;
  }
});
