import { SITE_URL } from "./sitemap-static";

/** Same allow/disallow/sitemap rules as the previous MetadataRoute robots.ts. */
export const ROBOTS_RULES = {
  userAgent: "*",
  allow: "/",
  disallow: "/ink-lab",
  sitemap: `${SITE_URL}/sitemap.xml`,
} as const;

export const ROBOTS_TXT = `# Automated clients: structured college data is available from the public API.
# Docs: ${SITE_URL}/api
# Machine-readable guide: ${SITE_URL}/llms.txt

User-Agent: ${ROBOTS_RULES.userAgent}
Allow: ${ROBOTS_RULES.allow}
Disallow: ${ROBOTS_RULES.disallow}

Sitemap: ${ROBOTS_RULES.sitemap}
`;
