// PRD 031 M3: which schools get /schools/{id}/early-decision.
// Distinctive names first. Harvard/Princeton/Yale/Stanford are REA/SCEA
// and are not on this list. Dartmouth, Vanderbilt, and Cornell do not yet
// have three usable C21 years plus a school-written details note.

import type { MetadataRoute } from "next";
import { edEligibility, type AcceptanceHistory } from "./acceptance-history";
import urls from "../data/early-decision-urls.json";
import { SITE_URL } from "./sitemap-static";
import { publicAcceptanceSchoolId } from "./acceptance-pilot";

export const EARLY_DECISION_INDEXABLE: boolean = true;

/**
 * Searchable public school ids. Expansion is a reviewed code change
 * (PRD 031 M3); each school has ≥3 usable C21 years, latest 2023-24+,
 * and a school-written C21 details note in the extract.
 */
export const EARLY_DECISION_SCHOOLS: readonly string[] = [
  "bowdoin",
  "rice",
  "lafayette-college",
];

export const EARLY_DECISION_SUBMITTED_PATHS: readonly string[] = urls.submitted;
export const EARLY_DECISION_GONE_PATHS: readonly string[] = urls.gone;

export function earlyDecisionPath(schoolId: string): string {
  return `/schools/${schoolId}/early-decision`;
}

export function publicEarlyDecisionSchoolId(schoolId: string): string {
  return publicAcceptanceSchoolId(schoolId);
}

export function isEarlyDecisionSchool(schoolId: string): boolean {
  return EARLY_DECISION_SCHOOLS.includes(publicEarlyDecisionSchoolId(schoolId));
}

export function isEarlyDecisionGone(pathname: string): boolean {
  return EARLY_DECISION_GONE_PATHS.includes(pathname.replace(/\/$/, ""));
}

export type EarlyDecisionPageDecision =
  | { kind: "serve" }
  | { kind: "serve-degraded"; reason: string }
  | { kind: "not-found"; reason: string };

export function earlyDecisionPageDecision(
  schoolId: string,
  history: AcceptanceHistory,
): EarlyDecisionPageDecision {
  if (!isEarlyDecisionSchool(schoolId)) {
    return { kind: "not-found", reason: "not on the early-decision allowlist" };
  }
  const eligibility = edEligibility(history);
  if (eligibility.eligible) return { kind: "serve" };
  if (EARLY_DECISION_SUBMITTED_PATHS.includes(earlyDecisionPath(schoolId))) {
    return { kind: "serve-degraded", reason: eligibility.reason };
  }
  return { kind: "not-found", reason: eligibility.reason };
}

export function earlyDecisionRobots(indexable: boolean = EARLY_DECISION_INDEXABLE) {
  return { index: indexable, follow: true };
}

export function earlyDecisionSitemapEntries(
  servedSchoolIds: string[],
  indexable: boolean = EARLY_DECISION_INDEXABLE,
): MetadataRoute.Sitemap {
  if (!indexable) return [];
  return servedSchoolIds
    .filter((id) => isEarlyDecisionSchool(id))
    .map((id) => earlyDecisionPath(publicEarlyDecisionSchoolId(id)))
    .filter((path, index, paths) => paths.indexOf(path) === index)
    .filter((path) => !isEarlyDecisionGone(path))
    .map((path) => ({
      url: `${SITE_URL}${path}`,
      changeFrequency: "monthly" as const,
      priority: 0.6,
    }));
}
