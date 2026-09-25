// PRD 031 M3: which schools get /schools/{id}/gpa.
// Distinctive names first. Yale left C11 blank. Dartmouth, Vanderbilt,
// Cornell, Duke, and Brown do not yet have three usable C11 years.

import type { MetadataRoute } from "next";
import { gpaEligibility, type GpaHistory } from "./c11-gpa";
import urls from "../data/gpa-urls.json";
import { SITE_URL } from "./sitemap-static";
import { publicAcceptanceSchoolId } from "./acceptance-pilot";

export const GPA_INDEXABLE: boolean = true;

/**
 * Searchable public school ids. Expansion is a reviewed code change
 * (PRD 031 / #195); each school has ≥3 usable C11 years, latest 2023-24+.
 */
export const GPA_SCHOOLS: readonly string[] = ["harvard", "princeton", "stanford"];

export const GPA_SUBMITTED_PATHS: readonly string[] = urls.submitted;
export const GPA_GONE_PATHS: readonly string[] = urls.gone;

export function gpaPath(schoolId: string): string {
  return `/schools/${schoolId}/gpa`;
}

export function publicGpaSchoolId(schoolId: string): string {
  return publicAcceptanceSchoolId(schoolId);
}

export function isGpaSchool(schoolId: string): boolean {
  return GPA_SCHOOLS.includes(publicGpaSchoolId(schoolId));
}

export function isGpaGone(pathname: string): boolean {
  return GPA_GONE_PATHS.includes(pathname.replace(/\/$/, ""));
}

export type GpaPageDecision =
  | { kind: "serve" }
  | { kind: "serve-degraded"; reason: string }
  | { kind: "not-found"; reason: string };

export function gpaPageDecision(schoolId: string, history: GpaHistory): GpaPageDecision {
  if (!isGpaSchool(schoolId)) {
    return { kind: "not-found", reason: "not on the GPA allowlist" };
  }
  const eligibility = gpaEligibility(history);
  if (eligibility.eligible) return { kind: "serve" };
  if (GPA_SUBMITTED_PATHS.includes(gpaPath(schoolId))) {
    return { kind: "serve-degraded", reason: eligibility.reason };
  }
  return { kind: "not-found", reason: eligibility.reason };
}

export function gpaRobots(indexable: boolean = GPA_INDEXABLE) {
  return { index: indexable, follow: true };
}

export function gpaSitemapEntries(
  servedSchoolIds: string[],
  indexable: boolean = GPA_INDEXABLE,
): MetadataRoute.Sitemap {
  if (!indexable) return [];
  return servedSchoolIds
    .filter((id) => isGpaSchool(id))
    .map((id) => gpaPath(publicGpaSchoolId(id)))
    .filter((path, index, paths) => paths.indexOf(path) === index)
    .filter((path) => !isGpaGone(path))
    .map((path) => ({
      url: `${SITE_URL}${path}`,
      changeFrequency: "monthly" as const,
      priority: 0.6,
    }));
}
