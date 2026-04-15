// URL-hint year normalizer. Canonical form is `YYYY-YY`.
//
// **Not authoritative for document year.** Per ADR 0007, the academic year
// of each archived document is derived from page 1 content by the extraction
// worker (`detect_year_from_pdf_bytes`) and written to
// `cds_documents.detected_year`. Consumers should read the `canonical_year`
// column on `cds_manifest`, which prefers `detected_year` and falls back to
// `cds_year` only when detection was inconclusive.
//
// This module still exists because the resolver needs a best-effort year
// guess to do two things at archive time, both of which run before extraction:
//
//   1. `pickCandidates` in `resolve.ts` uses URL years as a partitioning
//      signal — anchors with parseable years are preferred over anchors
//      without, and a multi-candidate landing page can be fanned out into
//      distinct `cds_documents` rows only if each candidate carries a
//      distinct year. Without a year signal at archive time, `pickCandidates`
//      conservatively fails the school rather than colliding on the NOT NULL
//      `(school_id, sub_institutional, cds_year)` unique constraint.
//   2. The `cds_year` column on `cds_documents` is NOT NULL at the schema
//      layer; resolver output populates it with either the parsed year or
//      `UNKNOWN_YEAR_SENTINEL`. Extraction later overwrites the canonical
//      year via `detected_year`, but the row cannot be inserted without
//      *some* value in `cds_year`.
//
// The long-term fix is to drop `cds_year` from the unique constraint and
// delete this module entirely — tracked in the backlog as "Retire cds_year
// as discovery output." Until that migration lands, `normalizeYear` is the
// minimum viable URL-side guesser.
//
// The critical property this module still gives us is that `normalizeYear`
// validates y2 = y1 + 1 before accepting a match. This prevents URLs like
// `/sites/default/files/2020-04/CDS2009_2010.pdf` (a real Brown CDS URL
// where `2020-04` is a Drupal upload-month path segment) from being misread
// as a 2020-2004 academic span. The span validation rejects 2020-04 because
// 04 != (2020+1) % 100, and the scanner continues to the next candidate,
// which correctly finds 2009-10.

const YEAR_PATTERNS: RegExp[] = [
  /(20\d{2})[\s_\-–—]+(20\d{2})/g,
  /(20\d{2})[\s_\-–—]+(\d{2})(?=\D|$)/g,
  /(?:^|[^0-9])(\d{2})[\s_\-–—]+(\d{2})(?=\D|$)/g,
  /(?:^|[^0-9])(\d{2})(\d{2})(?=\D|$)/g,
];

export function normalizeYear(raw: string | null | undefined): string | null {
  if (!raw) return null;
  for (let patternIndex = 0; patternIndex < YEAR_PATTERNS.length; patternIndex++) {
    const pattern = YEAR_PATTERNS[patternIndex];
    pattern.lastIndex = 0;
    for (const m of raw.matchAll(pattern)) {
      const rawA = parseInt(m[1], 10);
      const rawB = parseInt(m[2], 10);

      // Pattern 4 false-positive guard: "2021" would otherwise parse as
      // span 20-21. Any 4-digit string starting with "19" or "20" is almost
      // always a full year reference, not a compressed span.
      if (patternIndex === 3 && (m[1] === "19" || m[1] === "20")) continue;

      let y1: number;
      let y2Partial: number;

      if (rawA >= 1990 && rawA <= 2099) {
        y1 = rawA;
        y2Partial = rawB >= 100 ? rawB % 100 : rawB;
      } else if (rawA >= 0 && rawA <= 99 && rawB >= 0 && rawB <= 99) {
        // Millennium boundary: 9X-0Y spans into 2000s; 8X stays in 1900s;
        // everything else is 2000s.
        if (rawA >= 90 && rawB <= 9) {
          y1 = 1900 + rawA;
        } else if (rawA >= 80 && rawA <= 89) {
          y1 = 1900 + rawA;
        } else {
          y1 = 2000 + rawA;
        }
        y2Partial = rawB;
      } else {
        continue;
      }

      const expectedY2 = (y1 + 1) % 100;
      if (y2Partial !== expectedY2) continue;

      if (y1 < 1990 || y1 > 2035) continue;

      return `${y1}-${expectedY2.toString().padStart(2, "0")}`;
    }
  }
  return null;
}
