import type { MetadataRoute } from "next";

export const SITE_URL = "https://www.collegedata.fyi";

type StaticEntry = {
  path: string;
  changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"];
  priority: number;
};

const STATIC_PAGES: StaticEntry[] = [
  { path: "/", changeFrequency: "daily", priority: 1 },
  { path: "/schools", changeFrequency: "daily", priority: 0.9 },
  { path: "/browse", changeFrequency: "daily", priority: 0.7 },
  { path: "/match", changeFrequency: "daily", priority: 0.8 },
  { path: "/coverage", changeFrequency: "daily", priority: 0.7 },
  { path: "/pipeline-observation", changeFrequency: "daily", priority: 0.7 },
  { path: "/about", changeFrequency: "monthly", priority: 0.5 },
  { path: "/about/common-data-set", changeFrequency: "monthly", priority: 0.6 },
  { path: "/about/college-scorecard", changeFrequency: "monthly", priority: 0.6 },
  { path: "/about/ipeds", changeFrequency: "monthly", priority: 0.6 },
  { path: "/api", changeFrequency: "monthly", priority: 0.6 },
  { path: "/privacy", changeFrequency: "yearly", priority: 0.4 },
  { path: "/methodology", changeFrequency: "monthly", priority: 0.6 },
  { path: "/methodology/positioning", changeFrequency: "monthly", priority: 0.5 },
  { path: "/methodology/admission-strategy", changeFrequency: "monthly", priority: 0.5 },
  { path: "/methodology/merit-profile", changeFrequency: "monthly", priority: 0.5 },
  { path: "/recipes", changeFrequency: "monthly", priority: 0.6 },
  { path: "/recipes/acceptance-vs-yield", changeFrequency: "monthly", priority: 0.5 },
  { path: "/recipes/test-optional-tracker", changeFrequency: "monthly", priority: 0.5 },
  { path: "/recipes/waitlist-odds", changeFrequency: "monthly", priority: 0.5 },
  { path: "/recipes/endowment-draw-rate", changeFrequency: "monthly", priority: 0.5 },
  { path: "/recipes/alignment-gap", changeFrequency: "monthly", priority: 0.5 },
];

export const SITEMAP_STATIC_PATHS = STATIC_PAGES.map((page) => page.path);

export function staticSitemapEntries(): MetadataRoute.Sitemap {
  return STATIC_PAGES.map((page) => ({
    url: page.path === "/" ? SITE_URL : `${SITE_URL}${page.path}`,
    changeFrequency: page.changeFrequency,
    priority: page.priority,
  }));
}
