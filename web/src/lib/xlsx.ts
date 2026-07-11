import { deflateRawSync } from "node:zlib";

// Minimal XLSX writer. An .xlsx file is a zip archive of small XML parts;
// this module emits exactly the parts Excel, Sheets, LibreOffice, and
// openpyxl require — no dependency on SheetJS (stale on npm) or exceljs.
// Strings are written as inline strings (no shared-string table), numbers
// as native number cells so formulas work on the result. Output is
// deterministic: fixed zip timestamps, no random IDs.

export type CellValue = string | number | null | undefined;

export interface Sheet {
  name: string;
  rows: CellValue[][];
  // Leading rows rendered with the bold header style.
  headerRows?: number;
  // Column widths in Excel width units (approx. character count).
  colWidths?: number[];
}

const XLSX_EPOCH = { year: 2026, month: 1, day: 1 };

export function buildXlsx(sheets: Sheet[]): Buffer {
  if (sheets.length === 0) {
    throw new Error("buildXlsx requires at least one sheet");
  }
  const names = uniqueSheetNames(sheets.map((s) => s.name));

  const entries: Array<{ name: string; data: Buffer }> = [
    { name: "[Content_Types].xml", data: Buffer.from(contentTypesXml(sheets.length)) },
    { name: "_rels/.rels", data: Buffer.from(rootRelsXml()) },
    { name: "xl/workbook.xml", data: Buffer.from(workbookXml(names)) },
    { name: "xl/_rels/workbook.xml.rels", data: Buffer.from(workbookRelsXml(sheets.length)) },
    { name: "xl/styles.xml", data: Buffer.from(stylesXml()) },
    ...sheets.map((sheet, i) => ({
      name: `xl/worksheets/sheet${i + 1}.xml`,
      data: Buffer.from(worksheetXml(sheet)),
    })),
  ];

  return buildZip(entries);
}

// Excel rejects workbooks whose tab names exceed 31 characters, contain
// \ / ? * [ ] :, or collide case-insensitively.
export function sanitizeSheetName(name: string): string {
  const cleaned = name
    .replace(/[\\/?*[\]:]/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .slice(0, 31)
    .trim();
  return cleaned || "Sheet";
}

function uniqueSheetNames(names: string[]): string[] {
  const seen = new Set<string>();
  return names.map((raw) => {
    let name = sanitizeSheetName(raw);
    let n = 2;
    while (seen.has(name.toLowerCase())) {
      const suffix = ` ${n++}`;
      name = `${sanitizeSheetName(raw).slice(0, 31 - suffix.length)}${suffix}`;
    }
    seen.add(name.toLowerCase());
    return name;
  });
}

function escapeXml(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    // Control characters are not representable in XML 1.0; Excel treats
    // them as corruption. Tab/newline/CR are fine.
    .replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, "");
}

// 0-based column index → A1-style letters (0 → A, 26 → AA).
export function columnRef(index: number): string {
  let ref = "";
  let n = index;
  while (n >= 0) {
    ref = String.fromCharCode(65 + (n % 26)) + ref;
    n = Math.floor(n / 26) - 1;
  }
  return ref;
}

function worksheetXml(sheet: Sheet): string {
  const headerRows = sheet.headerRows ?? 0;
  const parts: string[] = [
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
    '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">',
  ];
  if (sheet.colWidths && sheet.colWidths.length > 0) {
    parts.push("<cols>");
    sheet.colWidths.forEach((width, i) => {
      parts.push(`<col min="${i + 1}" max="${i + 1}" width="${width}" customWidth="1"/>`);
    });
    parts.push("</cols>");
  }
  parts.push("<sheetData>");
  sheet.rows.forEach((row, r) => {
    parts.push(`<row r="${r + 1}">`);
    const style = r < headerRows ? ' s="1"' : "";
    row.forEach((value, c) => {
      if (value == null || value === "") return;
      const ref = `${columnRef(c)}${r + 1}`;
      if (typeof value === "number" && Number.isFinite(value)) {
        parts.push(`<c r="${ref}"${style}><v>${value}</v></c>`);
      } else {
        parts.push(
          `<c r="${ref}"${style} t="inlineStr"><is><t xml:space="preserve">${escapeXml(String(value))}</t></is></c>`,
        );
      }
    });
    parts.push("</row>");
  });
  parts.push("</sheetData></worksheet>");
  return parts.join("");
}

function contentTypesXml(sheetCount: number): string {
  const overrides = Array.from(
    { length: sheetCount },
    (_, i) =>
      `<Override PartName="/xl/worksheets/sheet${i + 1}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>`,
  ).join("");
  return (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
    '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">' +
    '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>' +
    '<Default Extension="xml" ContentType="application/xml"/>' +
    '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>' +
    '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>' +
    overrides +
    "</Types>"
  );
}

function rootRelsXml(): string {
  return (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
    '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>' +
    "</Relationships>"
  );
}

function workbookXml(names: string[]): string {
  const sheets = names
    .map(
      (name, i) =>
        `<sheet name="${escapeXml(name)}" sheetId="${i + 1}" r:id="rId${i + 1}"/>`,
    )
    .join("");
  return (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">' +
    `<sheets>${sheets}</sheets>` +
    "</workbook>"
  );
}

function workbookRelsXml(sheetCount: number): string {
  const rels = Array.from(
    { length: sheetCount },
    (_, i) =>
      `<Relationship Id="rId${i + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet${i + 1}.xml"/>`,
  ).join("");
  return (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
    '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">' +
    rels +
    `<Relationship Id="rId${sheetCount + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>` +
    "</Relationships>"
  );
}

// Two cell formats: 0 = default, 1 = bold (header rows). The two leading
// fills are mandatory Excel built-ins; dropping them shifts style indices.
function stylesXml(): string {
  return (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>' +
    '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">' +
    '<fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="11"/><name val="Calibri"/></font></fonts>' +
    '<fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills>' +
    '<borders count="1"><border/></borders>' +
    '<cellStyleXfs count="1"><xf/></cellStyleXfs>' +
    '<cellXfs count="2"><xf/><xf fontId="1" applyFont="1"/></cellXfs>' +
    '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>' +
    "</styleSheet>"
  );
}

// --- zip container -------------------------------------------------------

const CRC_TABLE = (() => {
  const table = new Uint32Array(256);
  for (let n = 0; n < 256; n++) {
    let c = n;
    for (let k = 0; k < 8; k++) {
      c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
    }
    table[n] = c >>> 0;
  }
  return table;
})();

export function crc32(data: Buffer): number {
  let crc = 0xffffffff;
  for (let i = 0; i < data.length; i++) {
    crc = CRC_TABLE[(crc ^ data[i]) & 0xff] ^ (crc >>> 8);
  }
  return (crc ^ 0xffffffff) >>> 0;
}

function dosDateTime(): { time: number; date: number } {
  const { year, month, day } = XLSX_EPOCH;
  return { time: 0, date: ((year - 1980) << 9) | (month << 5) | day };
}

function buildZip(entries: Array<{ name: string; data: Buffer }>): Buffer {
  const { time, date } = dosDateTime();
  const localParts: Buffer[] = [];
  const centralParts: Buffer[] = [];
  let offset = 0;

  for (const entry of entries) {
    const nameBytes = Buffer.from(entry.name, "ascii");
    const crc = crc32(entry.data);
    const compressed = deflateRawSync(entry.data, { level: 9 });

    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4); // version needed
    local.writeUInt16LE(0, 6); // flags
    local.writeUInt16LE(8, 8); // method: deflate
    local.writeUInt16LE(time, 10);
    local.writeUInt16LE(date, 12);
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(compressed.length, 18);
    local.writeUInt32LE(entry.data.length, 22);
    local.writeUInt16LE(nameBytes.length, 26);
    local.writeUInt16LE(0, 28); // extra length
    localParts.push(local, nameBytes, compressed);

    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50, 0);
    central.writeUInt16LE(20, 4); // version made by
    central.writeUInt16LE(20, 6); // version needed
    central.writeUInt16LE(0, 8); // flags
    central.writeUInt16LE(8, 10); // method
    central.writeUInt16LE(time, 12);
    central.writeUInt16LE(date, 14);
    central.writeUInt32LE(crc, 16);
    central.writeUInt32LE(compressed.length, 20);
    central.writeUInt32LE(entry.data.length, 24);
    central.writeUInt16LE(nameBytes.length, 28);
    // extra, comment, disk, internal attrs, external attrs all zero
    central.writeUInt32LE(offset, 42);
    centralParts.push(central, nameBytes);

    offset += 30 + nameBytes.length + compressed.length;
  }

  const centralSize = centralParts.reduce((sum, part) => sum + part.length, 0);
  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0);
  eocd.writeUInt16LE(entries.length, 8);
  eocd.writeUInt16LE(entries.length, 10);
  eocd.writeUInt32LE(centralSize, 12);
  eocd.writeUInt32LE(offset, 16);

  return Buffer.concat([...localParts, ...centralParts, eocd]);
}
