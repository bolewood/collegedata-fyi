// Year normalizer. Canonical form is `YYYY-YY` (the format used in
// cds_documents.cds_year and documented in docs/ARCHITECTURE.md). Extracted
// unchanged from the original discover/index.ts so existing test coverage of
// the regex semantics carries over.
//
// The critical property this module gives us is that `normalizeYear` validates
// y2 = y1 + 1 before accepting a match. This is what prevents URLs like
// `/sites/default/files/2020-04/CDS2009_2010.pdf` (a real Brown CDS URL where
// `2020-04` is a Drupal upload-month path segment) from being misread as a
// 2020-2004 academic span. The span validation rejects 2020-04 because
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
