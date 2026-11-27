// One place for the site name and origins. Every code literal for the site
// name, host or origin reads from here, so changing them is a one-file edit.
// Keep tools/common/site.py in step with these values.

// The site name is written three ways in shipped output. Each call site keeps
// its current spelling, so there is one constant per spelling.
/** Metadata, JSON-LD, Open Graph: "collegedata.fyi". */
export const SITE_NAME = "collegedata.fyi";
/** Share titles and match-list copy: "CollegeData.fyi". */
export const SITE_NAME_CAMEL = "CollegeData.fyi";
/** llms.txt, OpenAPI and MCP descriptions: "CollegeData.FYI". */
export const SITE_NAME_CAPS = "CollegeData.FYI";

/** The name the site used before any rename. */
export const FORMER_NAME = "collegedata.fyi";

/** Canonical (www) origin; the apex redirects here. */
export const SITE_ORIGIN = "https://www.collegedata.fyi";
export const SITE_HOST = "www.collegedata.fyi";
export const APEX_HOST = "collegedata.fyi";

/**
 * Display origin of the PostgREST API, used in docs, examples and OpenAPI.
 * Runtime data fetches read NEXT_PUBLIC_SUPABASE_URL instead.
 */
export const API_ORIGIN = "https://api.collegedata.fyi";
export const API_HOST = "api.collegedata.fyi";

/**
 * Runtime default only; display uses API_ORIGIN. A runtime call that falls back
 * to this never depends on a redirect from the custom API host.
 */
export const PROJECT_ORIGIN = "https://isduwmygvmdozhpvzaix.supabase.co";

/** Server name the hosted MCP endpoint reports. */
export const MCP_SERVER_NAME = "collegedata-fyi";
