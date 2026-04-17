import type { MetadataRoute } from "next";
import { fetchManifest, aggregateSchools } from "@/lib/queries";

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const manifest = await fetchManifest();
  const schools = aggregateSchools(manifest);

  const staticPages: MetadataRoute.Sitemap = [
    { url: "https://collegedata.fyi", changeFrequency: "daily", priority: 1 },
    {
      url: "https://collegedata.fyi/schools",
      changeFrequency: "daily",
      priority: 0.9,
    },
    {
      url: "https://collegedata.fyi/about",
      changeFrequency: "monthly",
      priority: 0.5,
    },
  ];

  const schoolPages: MetadataRoute.Sitemap = schools.map((s) => ({
    url: `https://collegedata.fyi/schools/${s.school_id}`,
    changeFrequency: "weekly" as const,
    priority: 0.8,
  }));

  // Year detail pages for extracted documents only
  const yearPages: MetadataRoute.Sitemap = manifest
    .filter(
      (doc) =>
        doc.extraction_status === "extracted" &&
        doc.canonical_year &&
        doc.canonical_year !== "unknown"
    )
    .map((doc) => ({
      url: `https://collegedata.fyi/schools/${doc.school_id}/${doc.canonical_year}`,
      changeFrequency: "monthly" as const,
      priority: 0.7,
    }));

  return [...staticPages, ...schoolPages, ...yearPages];
}
