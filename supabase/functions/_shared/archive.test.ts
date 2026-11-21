import { assertEquals, assertFalse, assertRejects } from "jsr:@std/assert";
import { PDFDocument } from "npm:pdf-lib@1.17.1";
import {
  buildPdfBundle,
  type DownloadResult,
  downloadThroughPdfViewer,
  isShrinkingRefresh,
  pdfPageCount,
  PermanentError,
  archiveOnePerYear,
  sectionPartsMatchSourceNotes,
} from "./archive.ts";

async function pdfWithPageSizes(
  sizes: [number, number][],
): Promise<Uint8Array> {
  const pdf = await PDFDocument.create({ updateMetadata: false });
  for (const [width, height] of sizes) {
    pdf.addPage([width, height]);
  }
  return await pdf.save();
}

async function bundleParts() {
  return [
    {
      section: "A",
      final_url: "https://example.edu/a.pdf",
      bytes: await pdfWithPageSizes([[101, 201], [102, 202]]),
    },
    {
      section: "B",
      final_url: "https://example.edu/b.pdf",
      bytes: await pdfWithPageSizes([[301, 401]]),
    },
  ];
}

async function sha256Hex(bytes: Uint8Array): Promise<string> {
  const copy = new Uint8Array(bytes.byteLength);
  copy.set(bytes);
  const digest = await crypto.subtle.digest(
    "SHA-256",
    copy.buffer as ArrayBuffer,
  );
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, "0"))
    .join("");
}

Deno.test("section package bundling produces repeatable bytes and SHA", async () => {
  const parts = await bundleParts();
  const first = await buildPdfBundle(parts);

  // pdf-lib metadata timestamps have one-second precision. Crossing that
  // boundary ensures this catches accidental metadata generation.
  await new Promise((resolve) => setTimeout(resolve, 1_100));
  const second = await buildPdfBundle(parts);

  assertEquals(second, first);
  assertEquals(await sha256Hex(second), await sha256Hex(first));
});

Deno.test("section package bundling preserves page order and count", async () => {
  const bundled = await buildPdfBundle(await bundleParts());
  const pdf = await PDFDocument.load(bundled, { updateMetadata: false });

  assertEquals(pdf.getPageCount(), 3);
  assertEquals(
    pdf.getPages().map((page) => [page.getWidth(), page.getHeight()]),
    [[101, 201], [102, 202], [301, 401]],
  );
});

Deno.test("section package bundle omits generated PDF dates", async () => {
  const bundled = await buildPdfBundle(await bundleParts());
  const pdf = await PDFDocument.load(bundled, { updateMetadata: false });
  const raw = new TextDecoder().decode(bundled);

  assertEquals(pdf.getCreationDate(), undefined);
  assertEquals(pdf.getModificationDate(), undefined);
  assertFalse(raw.includes("CreationDate"));
  assertFalse(raw.includes("ModDate"));
});

function packageNotes(parts: { sort_order: number; sha256: string }[]) {
  return {
    source_package: {
      kind: "section_package",
      assembled_at: "2026-10-05T02:47:38.715Z",
      bundle_sha256: "bundle-built-with-dated-metadata",
      parts,
    },
  };
}

Deno.test("section package with identical ordered parts matches prior source", () => {
  const notes = packageNotes([
    { sort_order: 2, sha256: "bbb" },
    { sort_order: 1, sha256: "aaa" },
  ]);

  assertEquals(
    sectionPartsMatchSourceNotes(notes, [{ sha256: "aaa" }, { sha256: "bbb" }]),
    true,
  );
});

Deno.test("section package with changed, reordered, or extra parts does not match", () => {
  const notes = packageNotes([
    { sort_order: 1, sha256: "aaa" },
    { sort_order: 2, sha256: "bbb" },
  ]);

  assertFalse(
    sectionPartsMatchSourceNotes(notes, [{ sha256: "aaa" }, { sha256: "ccc" }]),
  );
  assertFalse(
    sectionPartsMatchSourceNotes(notes, [{ sha256: "bbb" }, { sha256: "aaa" }]),
  );
  assertFalse(
    sectionPartsMatchSourceNotes(notes, [
      { sha256: "aaa" },
      { sha256: "bbb" },
      { sha256: "ccc" },
    ]),
  );
});

Deno.test("source without package notes never matches section parts", () => {
  assertFalse(sectionPartsMatchSourceNotes(null, [{ sha256: "aaa" }]));
  assertFalse(sectionPartsMatchSourceNotes({}, [{ sha256: "aaa" }]));
  assertFalse(sectionPartsMatchSourceNotes(packageNotes([]), []));
});

Deno.test("invalid section input maps to wrong_content_type", async () => {
  const error = await assertRejects(
    () =>
      buildPdfBundle([{
        section: "A",
        final_url: "https://example.edu/not-a-pdf.pdf",
        bytes: new TextEncoder().encode("not a PDF"),
      }]),
    PermanentError,
  );

  assertEquals(error.category, "wrong_content_type");
});

Deno.test("isShrinkingRefresh holds a section file replacing a full CDS", () => {
  // Utah 2022-23: complete 29-page CDS vs 2-page Section A / D files.
  assertEquals(isShrinkingRefresh(29, 2), true);
  assertEquals(isShrinkingRefresh(29, 11), true);
});

Deno.test("isShrinkingRefresh allows normal re-publications", () => {
  assertEquals(isShrinkingRefresh(29, 28), false); // minor edit
  assertEquals(isShrinkingRefresh(29, 12), false); // at the 40% line
  assertEquals(isShrinkingRefresh(29, 45), false); // grew
  assertEquals(isShrinkingRefresh(6, 1), false); // current file too small to judge
  assertEquals(isShrinkingRefresh(null, 2), false); // unknown current pages
  assertEquals(isShrinkingRefresh(29, null), false); // new file not a readable PDF
});

Deno.test("pdfPageCount counts pages and returns null for non-PDF bytes", async () => {
  const sizes: [number, number][] = [[100, 100], [100, 100], [100, 100]];
  assertEquals(await pdfPageCount(await pdfWithPageSizes(sizes)), 3);
  assertEquals(await pdfPageCount(new TextEncoder().encode("<html></html>")), null);
});

// ── archiveOnePerYear: a second candidate for a year is a fallback ──────────

function yearDoc(url: string, year: string) {
  return {
    candidate_kind: "single_document" as const,
    url,
    cds_year: year,
    filename: url.split("/").pop() ?? "",
    is_section_file: false,
    is_test_artifact: false,
    discovered_via: "landing" as const,
  };
}

Deno.test("archiveOnePerYear: the second file for a year is not fetched once the first archived", async () => {
  const docs = [yearDoc("https://e.edu/page-2024.pdf", "2024-25"), yearDoc("https://e.edu/hint-2024.pdf", "2024-25"), yearDoc("https://e.edu/2023.pdf", "2023-24")];
  const fetched: string[] = [];
  const outcomes = await archiveOnePerYear(docs, (d) => { fetched.push(d.url); return Promise.resolve(d.url); }, () => {});
  assertEquals(fetched, ["https://e.edu/page-2024.pdf", "https://e.edu/2023.pdf"]);
  assertEquals(outcomes, fetched);
});

Deno.test("archiveOnePerYear: the second file is the fallback when the first fails permanently", async () => {
  const docs = [yearDoc("https://e.edu/page-2024.pdf", "2024-25"), yearDoc("https://e.edu/hint-2024.pdf", "2024-25")];
  const failed: string[] = [];
  const outcomes = await archiveOnePerYear(
    docs,
    (d) => d.url.includes("page") ? Promise.reject(new PermanentError("404")) : Promise.resolve(d.url),
    (d) => failed.push(d.url),
  );
  assertEquals(outcomes, ["https://e.edu/hint-2024.pdf"]);
  assertEquals(failed, ["https://e.edu/page-2024.pdf"]);
});

Deno.test("archiveOnePerYear: files with no known year are all tried, and other errors propagate", async () => {
  const unknown = [yearDoc("https://e.edu/a.pdf", "unknown"), yearDoc("https://e.edu/b.pdf", "unknown")];
  assertEquals(await archiveOnePerYear(unknown, (d) => Promise.resolve(d.url), () => {}), ["https://e.edu/a.pdf", "https://e.edu/b.pdf"]);
  await assertRejects(() => archiveOnePerYear(unknown, () => Promise.reject(new Error("timeout")), () => {}), Error, "timeout");
});

const VIEWER_PAGE = `<!doctype html>
<html dir="ltr"><head><title>PDF.js viewer</title>
<script src="/src/pdfjs/build/pdf.mjs" type="module"></script>
<script>
  const PDF_URL = "https://archive.example.edu/files/ir/cds2014.pdf?__raw=1";
</script></head><body></body></html>`;

function downloaded(url: string, body: string, contentType: string): DownloadResult {
  return {
    bytes: new TextEncoder().encode(body),
    sha256: `sha-of-${url}`,
    contentType,
    finalUrl: url,
    httpLastModified: null,
  };
}

Deno.test("downloadThroughPdfViewer: a viewer page is replaced by the file it names, under the page's URL", async () => {
  const fetched: string[] = [];
  const result = await downloadThroughPdfViewer(
    "https://archive.example.edu/files/ir/cds2014.pdf",
    (url) => {
      fetched.push(url);
      return Promise.resolve(
        url.endsWith("__raw=1")
          ? downloaded(url, "%PDF-1.4 body", "application/pdf")
          : downloaded(url, VIEWER_PAGE, "text/html; charset=utf-8"),
      );
    },
  );
  assertEquals(fetched, [
    "https://archive.example.edu/files/ir/cds2014.pdf",
    "https://archive.example.edu/files/ir/cds2014.pdf?__raw=1",
  ]);
  assertEquals(result.finalUrl, "https://archive.example.edu/files/ir/cds2014.pdf");
  assertEquals(result.contentType, "application/pdf");
  assertEquals(result.sha256, "sha-of-https://archive.example.edu/files/ir/cds2014.pdf?__raw=1");
});

Deno.test("downloadThroughPdfViewer: a real PDF is returned as downloaded, with one fetch", async () => {
  let fetches = 0;
  const result = await downloadThroughPdfViewer(
    "https://www.example.edu/cds.pdf",
    (url) => {
      fetches++;
      return Promise.resolve(downloaded(url, "%PDF-1.7 const PDF_URL = \"x.pdf\"; pdfjs", "application/pdf"));
    },
  );
  assertEquals(fetches, 1);
  assertEquals(result.sha256, "sha-of-https://www.example.edu/cds.pdf");
});

Deno.test("downloadThroughPdfViewer: refuses a named file that redirects off the page's host or to a login", async () => {
  const landing = async (finalUrl: string) =>
    await assertRejects(
      () =>
        downloadThroughPdfViewer(
          "https://archive.example.edu/files/ir/cds2014.pdf",
          (url) =>
            Promise.resolve(
              url.endsWith("__raw=1")
                ? { ...downloaded(url, "%PDF-1.4 body", "application/pdf"), finalUrl }
                : downloaded(url, VIEWER_PAGE, "text/html"),
            ),
        ),
      PermanentError,
    );
  assertEquals((await landing("https://cdn.example.com/cds2014.pdf")).category, "wrong_content_type");
  assertEquals(
    (await landing("https://login.microsoftonline.com/common/oauth2/authorize")).category,
    "auth_walled_microsoft",
  );
});

Deno.test("downloadThroughPdfViewer: follows one hop only, and refuses a named file that is not a PDF", async () => {
  let fetches = 0;
  const error = await assertRejects(
    () =>
      downloadThroughPdfViewer(
        "https://archive.example.edu/files/ir/cds2014.pdf",
        (url) => {
          fetches++;
          return Promise.resolve(downloaded(url, VIEWER_PAGE, "text/html"));
        },
      ),
    PermanentError,
  );
  assertEquals(fetches, 2);
  assertEquals(error.category, "wrong_content_type");
});
