import { assertEquals, assertFalse, assertRejects } from "jsr:@std/assert";
import { PDFDocument } from "npm:pdf-lib@1.17.1";
import { buildPdfBundle, PermanentError } from "./archive.ts";

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
