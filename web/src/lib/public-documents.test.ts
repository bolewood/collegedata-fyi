import { describe, expect, it } from "vitest";
import {
  excludeHiddenQualityDocuments,
  isPubliclyListedDocument,
} from "./public-documents";

describe("public document listing", () => {
  it("hides blank_template rows and keeps other flags", () => {
    expect(isPubliclyListedDocument({ data_quality_flag: "blank_template" })).toBe(false);
    expect(isPubliclyListedDocument({ data_quality_flag: "low_coverage" })).toBe(true);
    expect(isPubliclyListedDocument({ data_quality_flag: "wrong_file" })).toBe(true);
    expect(isPubliclyListedDocument({ data_quality_flag: null })).toBe(true);
  });

  it("drops only blank_template from a mixed school list", () => {
    const docs = [
      { document_id: "ok", canonical_year: "2025-26", data_quality_flag: null },
      { document_id: "thin", canonical_year: "2024-25", data_quality_flag: "low_coverage" },
      { document_id: "blank", canonical_year: "2026-27", data_quality_flag: "blank_template" },
    ];
    expect(excludeHiddenQualityDocuments(docs).map((doc) => doc.document_id)).toEqual([
      "ok",
      "thin",
    ]);
  });
});
