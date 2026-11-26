import { APEX_HOST, SITE_ORIGIN } from "./site";
export { APEX_HOST };
export const CANONICAL_ORIGIN = SITE_ORIGIN;

/** Apex → www must be a 301. Next.js `permanent: true` would emit 308. */
export const APEX_TO_WWW_REDIRECTS = [
  {
    source: "/",
    has: [{ type: "host" as const, value: APEX_HOST }],
    destination: `${CANONICAL_ORIGIN}/`,
    statusCode: 301,
  },
  {
    source: "/:path*",
    has: [{ type: "host" as const, value: APEX_HOST }],
    destination: `${CANONICAL_ORIGIN}/:path*`,
    statusCode: 301,
  },
];
