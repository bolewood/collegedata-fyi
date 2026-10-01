const BUILD_ID = process.env.NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA?.slice(0, 7) || "dev";

// Gateway logs record X-Client-Info but not custom headers; the PRD 032 usage
// ingest classifies first-party traffic by these tokens. The key must keep
// supabase-js's exact casing so it replaces the default value instead of
// being merged into a second, comma-joined value.
export const SITE_CLIENT_INFO = `collegedata-web/${BUILD_ID}`;
export const FRIENDLY_API_CLIENT_INFO = `collegedata-friendly-api/${BUILD_ID}`;

export function clientInfoHeaders(clientInfo: string = SITE_CLIENT_INFO): Record<string, string> {
  return { "X-Client-Info": clientInfo };
}

const ARCHIVE_FILE_PATH = "/storage/v1/object/public/sources/";

export function isArchiveFileUrl(href: string | null | undefined): boolean {
  if (!href) return false;
  try {
    const url = new URL(href);
    const host = url.hostname.toLowerCase();
    const ownHost = host === "api.collegedata.fyi" || host.endsWith(".supabase.co");
    return ownHost && url.pathname.startsWith(ARCHIVE_FILE_PATH);
  } catch {
    return false;
  }
}

// Archived-file links keep the default Referer (origin only) so the usage
// ingest can tell our visitors' downloads apart from links shared elsewhere.
// Every other external link stays noreferrer.
export function externalLinkRel(href: string | null | undefined): string {
  return isArchiveFileUrl(href) ? "noopener" : "noopener noreferrer";
}
