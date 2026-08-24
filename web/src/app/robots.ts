import type { MetadataRoute } from "next";

const SITE_URL = "https://www.collegedata.fyi";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/", disallow: "/ink-lab" },
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
