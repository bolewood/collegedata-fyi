import type { MetadataRoute } from "next";
import { fetchManifest, aggregateSchools } from "@/lib/queries";

const SITE_URL = "https://www.collegedata.fyi";

function isAcademicYear(value: string | null | undefined): value is string {
  if (!value) return false;
  const match = /^(\d{4})-(\d{2})$/.exec(value);
  if (!match) return false;
  return Number(match[2]) === (Number(match[1]) + 1) % 100;
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const manifest = await fetchManifest();
  const schools = aggregateSchools(manifest);

  const staticPages: MetadataRoute.Sitemap = [
    { url: SITE_URL, changeFrequency: "daily", priority: 1 },
    {
      url: `${SITE_URL}/schools`,
      changeFrequency: "daily",
      priority: 0.9,
    },
    {
      url: `${SITE_URL}/about`,
      changeFrequency: "monthly",
      priority: 0.5,
    },
  ];

  const schoolPages: MetadataRoute.Sitemap = schools.map((s) => ({
    url: `${SITE_URL}/schools/${s.school_id}`,
    changeFrequency: "weekly" as const,
    priority: 0.8,
  }));

  // Exclude malformed year slugs from the sitemap until the upstream
  // manifest rows are corrected. Google should only see stable canonicals.
  const yearPages: MetadataRoute.Sitemap = manifest
    .filter(
      (doc) =>
        doc.extraction_status === "extracted" &&
        isAcademicYear(doc.canonical_year)
    )
    .map((doc) => ({
      url: `${SITE_URL}/schools/${doc.school_id}/${doc.canonical_year}`,
      changeFrequency: "monthly" as const,
      priority: 0.7,
    }));

  return [...staticPages, ...schoolPages, ...yearPages];
}
