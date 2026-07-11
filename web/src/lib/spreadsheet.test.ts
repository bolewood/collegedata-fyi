import { describe, expect, it } from "vitest";
import { inflateRawSync } from "node:zlib";
import type { FieldValue } from "./types";
import {
  buildCdsCsv,
  buildCdsWorkbook,
  buildFieldRows,
  spreadsheetFilename,
  toSpreadsheetNumber,
  type SpreadsheetInput,
} from "./spreadsheet";

function field(value: string, extra: Partial<FieldValue> = {}): FieldValue {
  return { value, ...extra };
}

function input(overrides: Partial<SpreadsheetInput> = {}): SpreadsheetInput {
  return {
    schoolId: "harvard",
    schoolName: "Harvard University",
    year: "2024-25",
    generatedAt: "2026-07-11",
    documents: [
      {
        variant: null,
        schemaVersion: "2024-25",
        sourceUrl: "https://example.com/harvard.pdf",
        values: {
          // Men applied — valueType "Number" per 2024-25 labels
          "C.101": field("54,008", { word_tag: "c1_men_applied" }),
          // Email — non-numeric valueType, stays a string
          "A.008": field("cds@harvard.edu"),
          // Unknown id: label falls back to the extracted question text,
          // and the value carries CSV-hostile characters
          "A.999": field('Yes, "posted"', { question: "Posted, on web?" }),
        },
        totalKnownFields: 900,
      },
    ],
    ...overrides,
  };
}

describe("toSpreadsheetNumber", () => {
  it("converts money, percents, and counts", () => {
    expect(toSpreadsheetNumber("$45,612", "Nearest $1")).toBe(45612);
    expect(toSpreadsheetNumber("98.5%", "Nearest 1%")).toBe(98.5);
    expect(toSpreadsheetNumber("54,008", "Number")).toBe(54008);
    expect(toSpreadsheetNumber("3.65", "Whole Number or Round to Nearest Hundredths")).toBe(3.65);
  });

  it("refuses non-numeric value types", () => {
    expect(toSpreadsheetNumber("54008", "Text")).toBeNull();
    expect(toSpreadsheetNumber("54008", null)).toBeNull();
  });

  it("refuses ambiguous strings even under numeric types", () => {
    expect(toSpreadsheetNumber("617-495-1551", "Numbers")).toBeNull();
    expect(toSpreadsheetNumber("Required for some", "Number")).toBeNull();
    expect(toSpreadsheetNumber("02138", "Numbers")).toBeNull(); // zip code
    expect(toSpreadsheetNumber("1,200 - 1,400", "Number")).toBeNull();
    expect(toSpreadsheetNumber("", "Number")).toBeNull();
  });
});

describe("buildFieldRows", () => {
  it("labels, groups, and types rows the way the page renders them", () => {
    const rows = buildFieldRows(input());
    const applied = rows.find((r) => r.fieldId === "C.101");
    expect(applied).toBeDefined();
    expect(applied!.sectionLetter).toBe("C");
    expect(applied!.numeric).toBe(54008);
    expect(applied!.raw).toBe("54,008");
    expect(applied!.tableCode).toBe("C1");
    expect(applied!.source).toBe("parser");

    const email = rows.find((r) => r.fieldId === "A.008");
    expect(email!.numeric).toBeNull();
    expect(email!.label).toBe("E-mail Address:");

    const fallbackLabel = rows.find((r) => r.fieldId === "A.999");
    expect(fallbackLabel!.label).toBe("Posted, on web?");
  });

  it("passes through the LLM fallback source marker", () => {
    const rows = buildFieldRows(
      input({
        documents: [
          {
            variant: null,
            schemaVersion: "2024-25",
            sourceUrl: null,
            values: {
              "C.101": field("54,008", { source: "tier4_llm_fallback" }),
            },
          },
        ],
      }),
    );
    expect(rows[0].source).toBe("tier4_llm_fallback");
  });
});

describe("buildCdsCsv", () => {
  it("emits BOM, CRLF, a header, and one row per field", () => {
    const csv = buildCdsCsv(input());
    expect(csv.startsWith("﻿school_id,")).toBe(true);
    const lines = csv.slice(1).trimEnd().split("\r\n");
    expect(lines).toHaveLength(1 + 3);
    expect(lines[0]).toBe(
      "school_id,school_name,cds_year,variant,section,section_name,table,subsection,field_id,field_label,value,value_type,source",
    );
  });

  it("escapes quotes and commas per RFC 4180", () => {
    const csv = buildCdsCsv(input());
    expect(csv).toContain('"Yes, ""posted"""');
    expect(csv).toContain('"Posted, on web?"');
  });
});

describe("buildCdsWorkbook", () => {
  function sheetNames(workbook: Buffer): string[] {
    const xml = readZipEntry(workbook, "xl/workbook.xml");
    return [...xml.matchAll(/<sheet name="([^"]+)"/g)].map((m) => m[1]);
  }

  function readZipEntry(buffer: Buffer, wanted: string): string {
    let offset = 0;
    while (buffer.readUInt32LE(offset) === 0x04034b50) {
      const compressedSize = buffer.readUInt32LE(offset + 18);
      const nameLength = buffer.readUInt16LE(offset + 26);
      const extraLength = buffer.readUInt16LE(offset + 28);
      const name = buffer
        .subarray(offset + 30, offset + 30 + nameLength)
        .toString("ascii");
      const dataStart = offset + 30 + nameLength + extraLength;
      if (name === wanted) {
        return inflateRawSync(
          buffer.subarray(dataStart, dataStart + compressedSize),
        ).toString("utf-8");
      }
      offset = dataStart + compressedSize;
    }
    throw new Error(`entry not found: ${wanted}`);
  }

  it("builds README plus one tab per extracted section", () => {
    const workbook = buildCdsWorkbook(input());
    expect(sheetNames(workbook)).toEqual([
      "README",
      "A General Information",
      "C First-Time, First-Year Admiss",
    ]);
  });

  it("writes numeric values as numbers and keeps the as-published string", () => {
    const workbook = buildCdsWorkbook(input());
    const sheet = readZipEntry(workbook, "xl/worksheets/sheet3.xml");
    expect(sheet).toContain("<v>54008</v>");
    expect(sheet).toContain("54,008");
  });

  it("adds a Variant column only for multi-variant schools", () => {
    const single = readZipEntry(
      buildCdsWorkbook(input()),
      "xl/worksheets/sheet2.xml",
    );
    expect(single).not.toContain(">Variant<");

    const doc = input().documents[0];
    const multi = buildCdsWorkbook(
      input({
        documents: [
          { ...doc, variant: null },
          { ...doc, variant: "School of Engineering" },
        ],
      }),
    );
    const sheet = readZipEntry(multi, "xl/worksheets/sheet2.xml");
    expect(sheet).toContain("Variant");
    expect(sheet).toContain("School of Engineering");
    expect(sheet).toContain("Main");
  });

  it("mentions the LLM fallback note only when fallback rows exist", () => {
    const readme = readZipEntry(
      buildCdsWorkbook(input()),
      "xl/worksheets/sheet1.xml",
    );
    expect(readme).not.toContain("LLM fallback");
    expect(readme).toContain("Data &amp; attribution");
    expect(readme).toContain("api.collegedata.fyi");
  });
});

describe("spreadsheetFilename", () => {
  it("names files school-cds-year", () => {
    expect(spreadsheetFilename("harvard", "2024-25", "xlsx")).toBe(
      "harvard-cds-2024-25.xlsx",
    );
  });
});
