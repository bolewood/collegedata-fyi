import { assertEquals, assertExists } from "jsr:@std/assert";
import {
  pickCandidates,
  UNKNOWN_YEAR_SENTINEL,
  extractCdsAnchors,
  findBestSourceAnchor,
  findDownloadLinks,
  rewriteGoogleDriveUrl,
  parentLandingCandidates,
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
      link_text: "CDS 2024-25 (Test)",
      year: "2024-25",
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
