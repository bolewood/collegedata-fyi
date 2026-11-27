import { SITE_ORIGIN } from "./site";

/**
 * Requests for the old site hosts, apex and www. Next anchors host values as
 * `^...$`, so this group does not match the old API host (that host is
 * handled by old-api-host.ts). Kept for the 12-month sunset of the old hosts.
 */
export const OLD_SITE_HOST_PATTERN = "(www\\.)?collegedata\\.fyi";

const has = [{ type: "host" as const, value: OLD_SITE_HOST_PATTERN }];

/**
 * Old host -> canonical host. `/api/*` is 308 so a client that follows the
 * redirect keeps its method and body; every other path is a permanent 301
 * (Next's `permanent: true` would emit 308). The `/api` rule comes first.
 */
export const OLD_SITE_REDIRECTS = [
  { source: "/api/:path*", has, destination: `${SITE_ORIGIN}/api/:path*`, statusCode: 308 },
  { source: "/", has, destination: `${SITE_ORIGIN}/`, statusCode: 301 },
  { source: "/:path*", has, destination: `${SITE_ORIGIN}/:path*`, statusCode: 301 },
];
