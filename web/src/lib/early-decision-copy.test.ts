import { describe, expect, it } from "vitest";
import { buildAcceptanceHistory, type HistoryDocument, type HistoryExtract } from "./acceptance-history";
import {
  LEDE_MAX_SENTENCES,
  LEDE_MAX_TOTAL_WORDS,
  LEDE_MAX_WORDS,
  edAnswerSentence,
  edLeadSentences,
  earlyDecisionDescription,
  earlyDecisionTitle,
} from "./early-decision-copy";
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

function year(
  label: string,
  applied: number,
  admitted: number,
  edApplied: number,
  edAdmitted: number,
  note: string,
): { doc: HistoryDocument; extract: HistoryExtract } {
  const start = Number(label.slice(0, 4));
  const schema = start >= 2025 ? "2025-26" : start >= 2024 ? "2024-25" : "2023-24";
  const values: Record<string, number | string> =
    start >= 2025
      ? { "C.116": applied, "C.117": admitted, "C.2110": edApplied, "C.2111": edAdmitted }
      : { "C.117": applied, "C.118": admitted, "C.119": 200, "C.2106": edApplied, "C.2107": edAdmitted };
  return {
    doc: doc(label),
    extract: {
      values: vals(values),
      schemaVersion: schema,
      producer: "tier4_docling",
      markdown: `Please provide significant details about your early decision plan:
${note}
## C22. Early action
No
`,
    },
  };
}

const NOTE = "Applicants must state in writing that they will enroll if admitted.";

const history = buildAcceptanceHistory([
  year("2025-26", 14000, 900, 1985, 296, NOTE),
  year("2024-25", 13000, 950, 2005, 270, NOTE),
  year("2023-24", 12000, 1000, 1009, 267, NOTE),
]);

describe("early-decision copy", () => {
  it("names early-decision applicants, not first-year, and stays inside the lead caps", () => {
    const answer = edAnswerSentence("Bowdoin College", history);
    expect(answer).toContain("early-decision applicants");
    expect(answer).not.toContain("first-year applicants");
    expect(answer).not.toMatch(/odds|chances/i);
    const lead = edLeadSentences("Bowdoin College", history);
    expect(lead.length).toBeGreaterThan(0);
    expect(lead.length).toBeLessThanOrEqual(LEDE_MAX_SENTENCES);
    expect(lead.every((s) => s.trim().split(/\s+/).length <= LEDE_MAX_WORDS)).toBe(true);
    expect(lead.join(" ").trim().split(/\s+/).length).toBeLessThanOrEqual(LEDE_MAX_TOTAL_WORDS);
  });

  it("titles the latest ED rate and describes the span", () => {
    expect(earlyDecisionTitle("Bowdoin College", history)).toBe(
      "Bowdoin College Early Decision Rate: 14.9% for Fall 2025",
    );
    expect(earlyDecisionDescription("Bowdoin College", history)).toContain("early-decision applicants");
    expect(earlyDecisionDescription("Bowdoin College", history).length).toBeLessThanOrEqual(155);
  });
});
