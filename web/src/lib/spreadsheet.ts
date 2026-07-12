import type { FieldValue } from "./types";
import { groupBySection } from "./sections";
import { getFieldDisplayLabel, getFieldValueType } from "./schema-labels";
import { buildXlsx, type CellValue, type Sheet } from "./xlsx";

// Builds the per-school CDS spreadsheet (XLSX + CSV) served from
// /schools/{school_id}/{year}/cds.xlsx and .csv (PRD 025). Rows come from
// the same groupBySection / schema-labels path FieldsView renders, so the
// download always matches what the page shows.

export interface SpreadsheetDocument {
  // sub_institutional label, null for the main institution document.
  variant: string | null;
  schemaVersion: string | null;
  sourceUrl: string | null;
  values: Record<string, FieldValue>;
}

export interface SpreadsheetInput {
  schoolId: string;
  schoolName: string;
  year: string;
  generatedAt: string; // ISO date
  documents: SpreadsheetDocument[];
}

export interface SpreadsheetFieldRow {
  variant: string | null;
  sectionLetter: string;
  sectionName: string;
  tableCode: string | null;
  subsection: string;
  fieldId: string;
  label: string;
  raw: string;
  numeric: number | null;
  valueType: string | null;
  source: string;
}

// value_type buckets that describe numbers. Mirrors formatFieldValue's
// switch — anything else ("Text", "YesNo", "URL", …) stays a string.
const NUMERIC_VALUE_TYPES = new Set([
  "Nearest $1",
  "Nearest 1%",
  "Round to Nearest Hundredths",
  "Whole Number or Round to Nearest Hundredths",
  "Whole Number or Round to Nearest Tenth",
  "Number",
  "Numbers",
]);

// Convert an as-published string into a spreadsheet number when it is
// unambiguously one. Strict on purpose: phone numbers, "Required for some",
// and date-ish strings stay strings, and leading zeros (zip codes) are
// preserved by refusing the conversion.
export function toSpreadsheetNumber(
  raw: string,
  valueType: string | null | undefined,
): number | null {
  if (!valueType || !NUMERIC_VALUE_TYPES.has(valueType)) return null;
  const value = raw.trim();
  if (!/^\$?\s?[\d,]+(\.\d+)?%?$/.test(value)) return null;
  if (/^0\d/.test(value)) return null; // leading zero: identifier, not a number
  const numeric = parseFloat(value.replace(/[$,%\s]/g, ""));
  return Number.isFinite(numeric) ? numeric : null;
}

export function buildFieldRows(input: SpreadsheetInput): SpreadsheetFieldRow[] {
  const rows: SpreadsheetFieldRow[] = [];
  for (const doc of input.documents) {
    const sections = groupBySection(doc.values, doc.schemaVersion);
    for (const sec of sections) {
      for (const sub of sec.subsections) {
        for (const { id, field } of sub.fields) {
          const raw = (field.value_decoded ?? field.value ?? "").trim();
          const valueType = getFieldValueType(id, field, doc.schemaVersion) ?? null;
          rows.push({
            variant: doc.variant,
            sectionLetter: sec.letter,
            sectionName: sec.name,
            tableCode: sub.code,
            subsection: sub.name,
            fieldId: id,
            label: getFieldDisplayLabel(id, field, doc.schemaVersion),
            raw,
            numeric: toSpreadsheetNumber(raw, valueType),
            valueType,
            source: field.source ?? "parser",
          });
        }
      }
    }
  }
  return rows;
}

export function spreadsheetFilename(
  schoolId: string,
  year: string,
  ext: "xlsx" | "csv",
): string {
  // The parts land inside a quoted Content-Disposition filename. Slugs and
  // canonical years are [a-z0-9-] in practice; sanitizing here keeps the
  // header valid even if slug provenance ever changes.
  const safe = (s: string) => s.replace(/[^A-Za-z0-9._-]/g, "-");
  return `${safe(schoolId)}-cds-${safe(year)}.${ext}`;
}

// --- XLSX workbook -------------------------------------------------------

export function buildCdsWorkbook(input: SpreadsheetInput): Buffer {
  const rows = buildFieldRows(input);
  const multiVariant = new Set(rows.map((r) => r.variant)).size > 1;

  const sheets: Sheet[] = [readmeSheet(input, rows)];

  const letters = [...new Set(rows.map((r) => r.sectionLetter))].sort();
  for (const letter of letters) {
    const sectionRows = rows.filter((r) => r.sectionLetter === letter);
    const sectionName = sectionRows[0].sectionName;
    const header: CellValue[] = [
      ...(multiVariant ? ["Variant"] : []),
      "Table",
      "Field ID",
      "Field",
      "Value",
      "As published",
      "Value type",
      "Source",
    ];
    const body: CellValue[][] = sectionRows.map((r) => [
      ...(multiVariant ? [r.variant ?? "Main"] : []),
      r.tableCode,
      r.fieldId,
      r.label,
      r.numeric ?? r.raw,
      r.raw,
      r.valueType,
      r.source,
    ]);
    sheets.push({
      name: `${letter} ${sectionName}`,
      rows: [header, ...body],
      headerRows: 1,
      colWidths: [
        ...(multiVariant ? [18] : []),
        8, 10, 64, 18, 18, 26, 16,
      ],
    });
  }

  return buildXlsx(sheets);
}

function readmeSheet(
  input: SpreadsheetInput,
  rows: SpreadsheetFieldRow[],
): Sheet {
  const pageUrl = `https://www.collegedata.fyi/schools/${input.schoolId}/${input.year}`;
  // Deterministic cleaner rows carry their producer name (tier2_cleaner,
  // tier4_cleaner, …); LLM gap-fill rows carry tier4_llm_fallback.
  const hasFallback = rows.some((r) => r.source.includes("llm"));

  const lines: CellValue[][] = [
    [`${input.schoolName} — Common Data Set ${input.year}`],
    [],
    ["School", input.schoolName],
    ["School ID", input.schoolId],
    ["CDS year", input.year],
    ["Fields extracted", rows.length],
    ["Generated", input.generatedAt],
    ["Page", pageUrl],
  ];

  for (const doc of input.documents) {
    const label = doc.variant ? `Source document (${doc.variant})` : "Source document";
    if (doc.sourceUrl) lines.push([label, doc.sourceUrl]);
    if (doc.schemaVersion) lines.push(["Schema version", doc.schemaVersion]);
  }

  lines.push(
    [],
    ["How to read this workbook"],
    [
      "Each tab mirrors one section of the Common Data Set (A General Information, B Enrollment, …).",
    ],
    [
      "“Value” is a real number wherever the published value parses cleanly; “As published” always keeps the exact string from the source document.",
    ],
    [
      "Percent-type values are written as published (98.5 for “98.5%”), not rescaled to fractions.",
    ],
  );
  if (hasFallback) {
    lines.push([
      "Rows whose Source column mentions “llm” were filled by the LLM fallback pipeline (gap-fill mode) — the deterministic parser always wins on conflicts.",
    ]);
  }
  lines.push(
    [],
    ["Data & attribution"],
    [
      `Data originates from ${input.schoolName}'s published Common Data Set; the transcription is provided freely by collegedata.fyi (MIT).`,
    ],
    [
      "Please attribute collegedata.fyi and link the school's source document when republishing.",
    ],
    [],
    ["Same data over the API"],
    [
      `https://api.collegedata.fyi/rest/v1/cds_fields?school_id=eq.${input.schoolId}&canonical_year=eq.${input.year}`,
    ],
  );

  return { name: "README", rows: lines, headerRows: 1, colWidths: [40, 90] };
}

// --- CSV -----------------------------------------------------------------

const CSV_COLUMNS = [
  "school_id",
  "school_name",
  "cds_year",
  "variant",
  "section",
  "section_name",
  "table",
  "subsection",
  "field_id",
  "field_label",
  "value",
  "value_type",
  "source",
] as const;

function csvEscape(value: string | null): string {
  let s = value ?? "";
  // Neutralize spreadsheet formula injection (CWE-1236): cells starting
  // with =, @, tab, or a +/- expression execute as formulas when the CSV
  // is opened in Excel, and values here come from third-party school
  // documents. Plain signed numbers ("-5", "+3.2") stay as published;
  // the sibling XLSX path is immune (typed inline strings).
  if (/^[=@\t]/.test(s) || (/^[+-]/.test(s) && !/^[+-]\d*\.?\d+$/.test(s))) {
    s = `'${s}`;
  }
  return /[",\r\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

export function buildCdsCsv(input: SpreadsheetInput): string {
  const rows = buildFieldRows(input);
  const lines = [CSV_COLUMNS.join(",")];
  for (const r of rows) {
    lines.push(
      [
        input.schoolId,
        input.schoolName,
        input.year,
        r.variant,
        r.sectionLetter,
        r.sectionName,
        r.tableCode,
        r.subsection,
        r.fieldId,
        r.label,
        r.raw,
        r.valueType,
        r.source,
      ]
        .map((v) => csvEscape(v ?? null))
        .join(","),
    );
  }
  // BOM so Excel detects UTF-8; CRLF per RFC 4180.
  return `\uFEFF${lines.join("\r\n")}\r\n`;
}
