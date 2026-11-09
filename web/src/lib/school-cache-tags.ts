/**
 * Cache-tag helpers shared by the cached school queries (queries.ts) and the
 * on-demand revalidation route (/api/revalidate). Kept free of server-only
 * imports so both sides and tests can use it.
 */

export const SCHOOL_DATA_TAG = "school-data";

/** Per-school tag attached to every cached query that is scoped to a school. */
export function schoolCacheTag(schoolId: string): string {
  return `school:${schoolId}`;
}

/**
 * Daily safety net for school pages and school-scoped queries. Data changes at
 * most once a day; the extraction worker calls /api/revalidate for the schools
 * it touched, so shorter windows only add load (crawler sweeps of stale pages).
 * Route files must repeat this as a literal (`export const revalidate = 86400`)
 * because Next requires statically analyzable segment config; a test pins both.
 */
export const SCHOOL_DATA_REVALIDATE_SECONDS = 86400;
