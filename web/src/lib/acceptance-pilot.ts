// PRD 031 M2 pilot: which schools get /schools/{id}/acceptance-rate, and
// whether search engines may index it. Public URLs use the name people
// search (`virginia-tech`), not the legal federal slug.

import type { MetadataRoute } from "next";
import { acceptanceEligibility, type AcceptanceHistory } from "./acceptance-history";
import urls from "../data/acceptance-rate-urls.json";
import { SITE_URL } from "./sitemap-static";
import { contrast, type DerivedInks } from "./derive-inks";

export const ACCEPTANCE_PILOT_INDEXABLE: boolean = true;

/**
 * Searchable public school ids. Expansion is a reviewed code change
 * (PRD 031 M2); each school's years are checked against its original files
 * in docs/prd/assets/031/m0-lite-validation.md.
 */
export const ACCEPTANCE_PILOT_SCHOOLS: readonly string[] = [
  "virginia-tech",
  "haverford-college",
  "brown",
  "northeastern",
  "duke",
  "upenn",
  "harvard",
  "princeton",
  "johns-hopkins",
  "northwestern",
  "emory",
  "rice",
  "university-of-notre-dame",
  "georgetown",
  "nyu",
  "bowdoin",
  "amherst",
  "hamilton",
  "university-of-richmond",
  "bates",
];

/** URLs ever listed in a sitemap. They must keep returning 200 or an explicit 410. */
export const ACCEPTANCE_RATE_SUBMITTED_PATHS: readonly string[] = urls.submitted;
/** Submitted URLs retired after a human decision; the proxy answers 410. */
export const ACCEPTANCE_RATE_GONE_PATHS: readonly string[] = urls.gone;

export function acceptanceRatePath(schoolId: string): string {
  return `/schools/${schoolId}/acceptance-rate`;
}

/** Legal-name slugs that still resolve to a searchable pilot URL. */
const ACCEPTANCE_PILOT_LIVE_ALIASES: Record<string, string> = {
  "virginia-polytechnic-institute-and-state-university": "virginia-tech",
};

export function publicAcceptanceSchoolId(schoolId: string): string {
  return ACCEPTANCE_PILOT_LIVE_ALIASES[schoolId] ?? schoolId;
}

export function isAcceptancePilotSchool(schoolId: string): boolean {
  return ACCEPTANCE_PILOT_SCHOOLS.includes(publicAcceptanceSchoolId(schoolId));
}

export function isAcceptanceRateGone(pathname: string): boolean {
  return ACCEPTANCE_RATE_GONE_PATHS.includes(pathname.replace(/\/$/, ""));
}

export type AcceptancePageDecision =
  | { kind: "serve" }
  /** Submitted URL that no longer meets eligibility: keep serving with a note. */
  | { kind: "serve-degraded"; reason: string }
  | { kind: "not-found"; reason: string };

export function acceptancePageDecision(
  schoolId: string,
  history: AcceptanceHistory,
): AcceptancePageDecision {
  if (!isAcceptancePilotSchool(schoolId)) {
    return { kind: "not-found", reason: "not on the pilot allowlist" };
  }
  const eligibility = acceptanceEligibility(history);
  if (eligibility.eligible) return { kind: "serve" };
  if (ACCEPTANCE_RATE_SUBMITTED_PATHS.includes(acceptanceRatePath(schoolId))) {
    return { kind: "serve-degraded", reason: eligibility.reason };
  }
  return { kind: "not-found", reason: eligibility.reason };
}

/**
 * The italic accent in the header uses the school's bright plate only when
 * it clears 4.5:1 on the dark plate; below that it falls back to paper.
 * (The site-wide rule is 3:1, the large-text minimum.)
 */
export const HEADER_ACCENT_MIN_CONTRAST = 4.5;

export function headerAccentReadable(inks: Pick<DerivedInks, "a" | "b" | "bTypeOnA">): boolean {
  return inks.bTypeOnA && contrast(inks.b, inks.a) >= HEADER_ACCENT_MIN_CONTRAST;
}

export function acceptanceRobots(indexable: boolean = ACCEPTANCE_PILOT_INDEXABLE) {
  return { index: indexable, follow: true };
}

/** Sitemap rows for served pilot pages; empty while the pilot is noindex. */
export function acceptanceSitemapEntries(
  servedSchoolIds: string[],
  indexable: boolean = ACCEPTANCE_PILOT_INDEXABLE,
): MetadataRoute.Sitemap {
  if (!indexable) return [];
  return servedSchoolIds
    .filter((id) => isAcceptancePilotSchool(id))
    .map((id) => acceptanceRatePath(publicAcceptanceSchoolId(id)))
    .filter((path, index, paths) => paths.indexOf(path) === index)
    .filter((path) => !isAcceptanceRateGone(path))
    .map((path) => ({
      url: `${SITE_URL}${path}`,
      changeFrequency: "monthly" as const,
      priority: 0.6,
    }));
}
