import { describe, expect, it } from "vitest";
import { buildGpaHistory, type GpaHistory } from "./c11-gpa";
import {
  LEDE_MAX_SENTENCES,
  LEDE_MAX_TOTAL_WORDS,
  LEDE_MAX_WORDS,
  gpaAnswerSentence,
  gpaDescription,
  gpaLeadSentences,
  gpaTitle,
} from "./gpa-copy";
import type { HistoryDocument, HistoryExtract } from "./acceptance-history";
import type { FieldValue } from "./types";

function doc(year: string): HistoryDocument {
  return {
    document_id: `doc-${year}`,
    canonical_year: year,
    extraction_status: "extracted",
    data_quality_flag: null,
    sub_institutional: null,
    source_storage_path: `school/${year}/file.pdf`,
    source_format: "pdf_flat",
  };
}

function vals(entries: Record<string, number | string>): Record<string, FieldValue> {
  return Object.fromEntries(Object.entries(entries).map(([id, value]) => [id, { value: String(value) }]));
}

const HARVARD = [74.2, 18.1, 5.4, 1.6, 0.5, 0.2, 0, 0, 0];

function year(label: string, average: number | null, percents: number[] = HARVARD): {
  doc: HistoryDocument;
  extract: HistoryExtract;
} {
  const values: Record<string, number | string> = {};
  percents.forEach((n, i) => {
    values[`C.11${String(1 + i).padStart(2, "0")}`] = n;
  });
  if (average != null) values["C.1201"] = average;
  return {
    doc: doc(label),
    extract: { values: vals(values), schemaVersion: "2024-25", producer: "tier4_docling" },
  };
}

const history: GpaHistory = buildGpaHistory([
  year("2025-26", 4.22),
  year("2024-25", 4),
  year("2022-23", 4),
]);

describe("gpa copy", () => {
  it("names enrolled first-years who reported a GPA and stays inside the lead caps", () => {
    const answer = gpaAnswerSentence("Harvard University", history);
    expect(answer).toContain("enrolled first-years who reported one");
    expect(answer).toContain("4.22");
    expect(answer).not.toMatch(/cutoff|minimum|odds|requirements/i);
    const lead = gpaLeadSentences("Harvard University", history);
    expect(lead.length).toBeGreaterThan(0);
    expect(lead.length).toBeLessThanOrEqual(LEDE_MAX_SENTENCES);
    expect(lead.every((s) => s.trim().split(/\s+/).length <= LEDE_MAX_WORDS)).toBe(true);
    expect(lead.join(" ").trim().split(/\s+/).length).toBeLessThanOrEqual(LEDE_MAX_TOTAL_WORDS);
  });

  it("titles the latest average and describes bands-only when C12 is blank", () => {
    expect(gpaTitle("Harvard University", history)).toBe(
      "Harvard University Average GPA: 4.22 for Fall 2025",
    );
    expect(gpaDescription("Harvard University", history)).toContain("4.22");
    const bandsOnly = buildGpaHistory([
      year("2025-26", null),
      year("2024-25", null),
      year("2023-24", null),
    ]);
    expect(gpaAnswerSentence("Yale University", bandsOnly)).toContain("had a 4.0");
    expect(gpaAnswerSentence("Yale University", bandsOnly)).not.toContain("average");
    expect(gpaTitle("Yale University", bandsOnly)).toContain("at 4.0");
  });
});
