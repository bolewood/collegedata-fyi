// Reviewed retired school slugs -> canonical school_id. The site 308s these
// (web/src/data/school-redirects.json) and hides documents filed under them,
// so every archive write must store the canonical id. This is a copy because
// Edge functions can't import from web/; tools/finder/school_redirect_guard.py
// fails CI when the two differ. Ambiguous or unknown slugs pass through.
export const RETIRED_SCHOOL_ALIASES: Readonly<Record<string, string>> = {
  "california-institute-of-technology": "caltech",
  "georgia-institute-of-technology-main-campus": "georgia-tech",
  "rutgers-university-new-brunswick": "rutgers",
  "texas-a-and-m-university-college-station": "texas-am",
  "tufts-university": "tufts",
  "tulane-university-of-louisiana": "tulane-university",
  "university-of-chicago": "uchicago",
  "university-of-virginia-main-campus": "uva",
  "university-of-washington-seattle-campus": "uw",
  "virginia-polytechnic-institute-and-state-university": "virginia-tech",
};

export function canonicalSchoolId(schoolId: string): string {
  return Object.hasOwn(RETIRED_SCHOOL_ALIASES, schoolId)
    ? RETIRED_SCHOOL_ALIASES[schoolId]
    : schoolId;
}
