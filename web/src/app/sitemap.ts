import type { MetadataRoute } from "next";
import { fetchManifest, aggregateSchools, fetchSchoolSlugResolver } from "@/lib/queries";
import { SITE_URL, staticSitemapEntries } from "@/lib/sitemap-static";
import { canonicalizeSchoolRows } from "@/lib/school-alias";
import type { ManifestRow } from "@/lib/types";
import { acceptanceRateSitemap, earlyDecisionSitemap } from "@/lib/acceptance-history-data";

function isAcademicYear(value: string | null | undefined): value is string {
  if (!value) return false;
  const match = /^(\d{4})-(\d{2})$/.exec(value);
  if (!match) return false;
  return Number(match[2]) === (Number(match[1]) + 1) % 100;
}

function rowUpdatedAt(row: ManifestRow): string | null {
  return row.extracted_at ?? row.discovered_at ?? null;
}

function latest(dates: (string | null)[]): Date | undefined {
  const times = dates
    .map((value) => (value ? Date.parse(value) : Number.NaN))
    .filter((time) => Number.isFinite(time));
  return times.length > 0 ? new Date(Math.max(...times)) : undefined;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const rawManifest = await fetchManifest();
  const resolve = await fetchSchoolSlugResolver(
    rawManifest.map((row) => row.school_id ?? ""),
  );
  // Only list URLs that serve a 200: alias slugs redirect, so their rows are
  // listed under the canonical slug that now serves them.
  const manifest = canonicalizeSchoolRows(rawManifest, resolve);
  const schools = aggregateSchools(manifest);
  const updatedBySchool = new Map<string, (string | null)[]>();
  const updatedByYear = new Map<string, (string | null)[]>();
  for (const row of manifest) {
    if (!row.school_id) continue;
    const updated = rowUpdatedAt(row);
    updatedBySchool.set(row.school_id, [...(updatedBySchool.get(row.school_id) ?? []), updated]);
    if (row.extraction_status === "extracted" && isAcademicYear(row.canonical_year)) {
      const key = `${row.school_id}/${row.canonical_year}`;
      updatedByYear.set(key, [...(updatedByYear.get(key) ?? []), updated]);
    }
  }

  const staticPages = staticSitemapEntries();

  const schoolPages: MetadataRoute.Sitemap = schools.map((s) => ({
    url: `${SITE_URL}/schools/${s.school_id}`,
    lastModified: latest(updatedBySchool.get(s.school_id) ?? []),
    changeFrequency: "weekly" as const,
    priority: 0.8,
  }));

  // Exclude malformed year slugs from the sitemap until the upstream
  // manifest rows are corrected. Google should only see stable canonicals.
  const yearPages: MetadataRoute.Sitemap = [...updatedByYear].map(([path, dates]) => ({
    url: `${SITE_URL}/schools/${path}`,
    lastModified: latest(dates),
    changeFrequency: "monthly" as const,
    priority: 0.7,
  }));

  // PRD 031 pilot: empty until ACCEPTANCE_PILOT_INDEXABLE flips.
  const acceptancePages = await acceptanceRateSitemap();
  const earlyDecisionPages = await earlyDecisionSitemap();

  return [...staticPages, ...schoolPages, ...yearPages, ...acceptancePages, ...earlyDecisionPages].filter((entry, index, entries) =>
    entries.findIndex((candidate) => candidate.url === entry.url) === index
  );
}
