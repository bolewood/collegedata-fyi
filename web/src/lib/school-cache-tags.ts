/**
 * Cache-tag helpers shared by the cached school queries (queries.ts) and the
 * on-demand revalidation route (/api/revalidate). Kept free of server-only
 * imports so both sides and tests can use it.
 */

export const SCHOOL_DATA_TAG = "school-data";

/**
 * True when a requested school slug is printable ASCII with no spaces. Real
 * slugs are lowercase letters, digits and hyphens, and one legacy alias has an
 * ampersand ("w&m"). Anything else (for example a look-alike Cyrillic letter)
 * cannot name a school and is answered 404 before any data is read.
 */
export function isRoutableSchoolSlug(schoolId: string): boolean {
  return /^[\x21-\x7E]{1,120}$/.test(schoolId);
}

/**
 * Per-school tag attached to every cached query that is scoped to a school.
 * Tags travel in the `x-next-cache-tags` response header, which must be ASCII:
 * a raw non-ASCII slug there crashes the response, so it is percent-encoded.
 */
export function schoolCacheTag(schoolId: string): string {
  return `school:${isRoutableSchoolSlug(schoolId) ? schoolId : encodeURIComponent(schoolId).slice(0, 200)}`;
}

/**
 * Last-resort window for school pages and school-scoped queries. Pages are
 * refreshed when their data changes, not on a timer: the extraction worker and
 * the scholarship loader call /api/revalidate for the schools they touch, and a
 * daily sweep (tools/ops/revalidate_pages.py) does the same for every other
 * change. A shorter window only added load: with a 24 h window, a crawler that
 * returns at the same hour each day made every page it reads regenerate at once.
 * Route files must repeat this as a literal (`export const revalidate = 604800`)
 * because Next requires statically analyzable segment config; a test pins both.
 */
export const SCHOOL_DATA_REVALIDATE_SECONDS = 604800;

/** Tag on the cached scholarship directory read (PRD 036). Expired together with school tags by /api/revalidate. */
export const SCHOLARSHIP_INDEX_TAG = "scholarship-directory";
