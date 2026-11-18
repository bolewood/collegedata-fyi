/**
 * Helpers for the deprecated GET /api/facts/{school_id} endpoint (issue #267).
 *
 * CDS question numbers are renumbered between template years, so the endpoint
 * must not read C.116/C.117/C.120 from the raw extract for every year. Counts
 * come from the school_browser_rows projection (year-aware); the `raw` block is
 * kept for backward compatibility but only populated where the question number
 * means what the legacy key says.
 */

export type LegacyAdmissionsRow = {
  document_id: string | null;
  applied: number | null;
  admitted: number | null;
  enrolledFirstYear: number | null;
};

export type LegacyAdmissions = {
  applied: number | null;
  admitted: number | null;
  enrolled: number | null;
  acceptance_rate_pct: number | null;
  yield_rate_pct: number | null;
};

function pct(a: number | null, b: number | null): number | null {
  if (a === null || b === null || b === 0) return null;
  return Math.round((a / b) * 1000) / 10; // one decimal place
}

/**
 * Admissions counts for one document, from its projection row. Missing row or
 * null values give null. Counts that contradict each other (admitted >
 * applied, enrolled > admitted) are withheld, matching /api/schools/{id}/facts.
 * Rates are computed from the projected counts (the newer endpoint serves the
 * projection's stored fractions; these are the same ratio as a percent).
 */
export function legacyAdmissions(
  rows: LegacyAdmissionsRow[],
  documentId: string,
): LegacyAdmissions {
  const row = rows.find((r) => r.document_id === documentId);
  let applied = row?.applied ?? null;
  let admitted = row?.admitted ?? null;
  let enrolled = row?.enrolledFirstYear ?? null;
  const incoherent =
    (applied !== null && admitted !== null && admitted > applied) ||
    (admitted !== null && enrolled !== null && enrolled > admitted);
  if (incoherent) {
    applied = admitted = enrolled = null;
  }
  return {
    applied,
    admitted,
    enrolled,
    acceptance_rate_pct: pct(admitted, applied),
    yield_rate_pct: pct(enrolled, admitted),
  };
}

// Verified against schemas/cds_schema_{2023_24,2024_25,2025_26}.json: only in
// the 2025-26 template are C.116/C.117 applied/admitted. C.120 is never
// "enrolled" in any template, and B.101/B.126 are first-time first-year men and
// women, not total full-time enrollment, in every template. The schemas/ files
// are outside the web app bundle, so this stays a deliberately tiny rule.
const APPLIED_ADMITTED_AT_C116_C117 = new Set(["2025-26"]);

/**
 * The legacy `raw` block. Keys are unchanged; a value is published only when
 * the document's template year makes that question number mean what the key
 * says. Unknown template year publishes nothing.
 */
export function legacyRaw(
  templateYear: string | null,
  readValue: (questionNumber: string) => string | null,
) {
  const ok = templateYear !== null && APPLIED_ADMITTED_AT_C116_C117.has(templateYear);
  return {
    C_116_applied_total: ok ? readValue("C.116") : null,
    C_117_admitted_total: ok ? readValue("C.117") : null,
    C_120_enrolled_total: null,
    B_101_ft_men_enrolled: null,
    B_126_ft_women_enrolled: null,
  };
}

export function legacyRawNote(schoolId: string): string {
  return `CDS question numbers change between template years, so these keys are filled only when the number means what the key says for this document's year, and are otherwise null. Some keys are always null because no year matches their name. Use /api/schools/${schoolId}/facts for year-aware values with sources.`;
}
