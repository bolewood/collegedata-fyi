// One place for the site name and origins. Every code literal for the site
// name, host or origin reads from here, so changing them is a one-file edit.
// Keep tools/common/site.py in step with these values.

/** Prose, titles, metadata, JSON-LD, Open Graph. */
export const SITE_NAME = "Quadfile";

/** The name the site used before any rename. */
export const FORMER_NAME = "collegedata.fyi";

/** Canonical (www) origin; the apex redirects here. */
export const SITE_ORIGIN = "https://www.quadfile.org";
export const SITE_HOST = "www.quadfile.org";
export const APEX_HOST = "quadfile.org";

/**
 * Display origin of the PostgREST API, used in docs, examples and OpenAPI.
 * Runtime data fetches read NEXT_PUBLIC_SUPABASE_URL instead.
 */
export const API_ORIGIN = "https://api.quadfile.org";
export const API_HOST = "api.quadfile.org";

/**
 * Runtime default only; display uses API_ORIGIN. A runtime call that falls back
 * to this never depends on a redirect from the custom API host.
 */
export const PROJECT_ORIGIN = "https://isduwmygvmdozhpvzaix.supabase.co";

/** Server name the hosted MCP endpoint reports. */
export const MCP_SERVER_NAME = "quadfile";
