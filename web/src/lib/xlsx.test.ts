import { describe, expect, it } from "vitest";
import { inflateRawSync } from "node:zlib";
import { buildXlsx, columnRef, crc32, sanitizeSheetName } from "./xlsx";

// Walk the local file entries of a zip produced by buildXlsx. We wrote the
// sizes into the local headers (no data descriptors), so a sequential parse
// is enough to recover and integrity-check every part.
function readZip(buffer: Buffer): Map<string, string> {
  const entries = new Map<string, string>();
  let offset = 0;
  while (buffer.readUInt32LE(offset) === 0x04034b50) {
    const method = buffer.readUInt16LE(offset + 8);
    const expectedCrc = buffer.readUInt32LE(offset + 14);
    const compressedSize = buffer.readUInt32LE(offset + 18);
    const uncompressedSize = buffer.readUInt32LE(offset + 22);
    const nameLength = buffer.readUInt16LE(offset + 26);
    const extraLength = buffer.readUInt16LE(offset + 28);
    const name = buffer
      .subarray(offset + 30, offset + 30 + nameLength)
      .toString("ascii");
    const dataStart = offset + 30 + nameLength + extraLength;
    const compressed = buffer.subarray(dataStart, dataStart + compressedSize);
    expect(method).toBe(8);
    const data = inflateRawSync(compressed);
    expect(data.length).toBe(uncompressedSize);
    expect(crc32(data)).toBe(expectedCrc);
    entries.set(name, data.toString("utf-8"));
    offset = dataStart + compressedSize;
  }
  // End of local entries should be the first central directory record.
  expect(buffer.readUInt32LE(offset)).toBe(0x02014b50);
  return entries;
}

describe("buildXlsx", () => {
  const workbook = buildXlsx([
    {
      name: "First",
      rows: [
        ["Field", "Value"],
        ["Total <applied> & \"admitted\"", 54008],
        ["Rate", 3.65],
        ["Note", "line1\nline2"],
        [null, ""],
      ],
      headerRows: 1,
      colWidths: [40, 12],
    },
    { name: "Second", rows: [["only cell"]] },
  ]);
  const parts = readZip(workbook);

  it("emits every required package part with valid zip integrity", () => {
    expect([...parts.keys()]).toEqual([
      "[Content_Types].xml",
      "_rels/.rels",
      "xl/workbook.xml",
      "xl/_rels/workbook.xml.rels",
      "xl/styles.xml",
      "xl/worksheets/sheet1.xml",
      "xl/worksheets/sheet2.xml",
    ]);
  });

  it("registers both sheets in the workbook and content types", () => {
    expect(parts.get("xl/workbook.xml")).toContain(
      '<sheet name="First" sheetId="1" r:id="rId1"/>',
    );
    expect(parts.get("xl/workbook.xml")).toContain(
      '<sheet name="Second" sheetId="2" r:id="rId2"/>',
    );
    expect(parts.get("[Content_Types].xml")).toContain(
      'PartName="/xl/worksheets/sheet2.xml"',
    );
    expect(parts.get("xl/_rels/workbook.xml.rels")).toContain(
      'Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles"',
    );
  });

  it("writes numbers as number cells and strings as escaped inline strings", () => {
    const sheet = parts.get("xl/worksheets/sheet1.xml")!;
    expect(sheet).toContain('<c r="B2"><v>54008</v></c>');
    expect(sheet).toContain('<c r="B3"><v>3.65</v></c>');
    expect(sheet).toContain(
      "Total &lt;applied&gt; &amp; &quot;admitted&quot;",
    );
    expect(sheet).toContain("line1\nline2");
  });

  it("styles header rows bold and skips empty cells", () => {
    const sheet = parts.get("xl/worksheets/sheet1.xml")!;
    expect(sheet).toContain('<c r="A1" s="1" t="inlineStr">');
    // Row 5 has no renderable cells.
    expect(sheet).toContain('<row r="5"></row>');
  });

  it("emits column widths", () => {
    expect(parts.get("xl/worksheets/sheet1.xml")).toContain(
      '<col min="1" max="1" width="40" customWidth="1"/>',
    );
  });

  it("strips XML-invalid control characters from cell text", () => {
    const parts2 = readZip(
      buildXlsx([{ name: "S", rows: [["bad\u0000\u0007char"]] }]),
    );
    expect(parts2.get("xl/worksheets/sheet1.xml")).toContain("badchar");
  });

  it("strips the U+FFFE/U+FFFF non-characters from cell text", () => {
    const parts2 = readZip(
      buildXlsx([{ name: "S", rows: [["bad\ufffe\uffffchar"]] }]),
    );
    expect(parts2.get("xl/worksheets/sheet1.xml")).toContain("badchar");
  });

  it("writes a valid end-of-central-directory record", () => {
    const eocd = workbook.subarray(workbook.length - 22);
    expect(eocd.readUInt32LE(0)).toBe(0x06054b50);
    expect(eocd.readUInt16LE(8)).toBe(parts.size); // entries on this disk
    expect(eocd.readUInt16LE(10)).toBe(parts.size); // entries total
  });

  it("throws on an empty sheet list", () => {
    expect(() => buildXlsx([])).toThrow(/at least one sheet/);
  });

  it("writes non-finite numbers as inline strings, never as number cells", () => {
    const parts4 = readZip(
      buildXlsx([{ name: "S", rows: [[NaN, Infinity, -Infinity]] }]),
    );
    const sheet = parts4.get("xl/worksheets/sheet1.xml")!;
    expect(sheet).not.toContain("<v>NaN</v>");
    expect(sheet).not.toContain("<v>Infinity</v>");
    expect(sheet).toContain('t="inlineStr"><is><t xml:space="preserve">NaN</t>');
  });

  it("deduplicates and truncates sheet names", () => {
    const parts3 = readZip(
      buildXlsx([
        { name: "B. Enrollment [and] Persistence: 2024", rows: [[1]] },
        { name: "B. Enrollment [and] Persistence: 2024", rows: [[2]] },
      ]),
    );
    const wb = parts3.get("xl/workbook.xml")!;
    const names = [...wb.matchAll(/<sheet name="([^"]+)"/g)].map((m) => m[1]);
    expect(names[0]).toHaveLength(31);
    expect(names[0]).not.toMatch(/[\\/?*[\]:]/);
    expect(names[1]).not.toBe(names[0]);
    expect(names[1].length).toBeLessThanOrEqual(31);
  });
});

describe("sanitizeSheetName", () => {
  it("replaces forbidden characters and trims to 31", () => {
    expect(sanitizeSheetName("C: First-Time/First-Year")).toBe(
      "C First-Time First-Year",
    );
    expect(sanitizeSheetName("x".repeat(40))).toHaveLength(31);
    expect(sanitizeSheetName("///")).toBe("Sheet");
  });
});

describe("columnRef", () => {
  it("maps indexes to A1 letters", () => {
    expect(columnRef(0)).toBe("A");
    expect(columnRef(25)).toBe("Z");
    expect(columnRef(26)).toBe("AA");
    expect(columnRef(701)).toBe("ZZ");
    expect(columnRef(702)).toBe("AAA");
  });
});
