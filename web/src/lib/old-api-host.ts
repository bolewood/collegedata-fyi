/**
 * Rename prep: requests that arrive at this app on the old API host.
 *
 * Today no request reaches the app with these hosts (api.collegedata.fyi is a
 * Supabase custom hostname). After the API host moves, its DNS points at this
 * project and `proxy.ts` uses this module to serve it. `api-test.quadfile.org`
 * is a throwaway host used to prove the handler before that happens.
 */

export const SUPABASE_ORIGIN = "https://isduwmygvmdozhpvzaix.supabase.co";

/** Where public storage objects are redirected to, by request host. */
const STORAGE_REDIRECT_ORIGINS: Record<string, string> = {
  "api.collegedata.fyi": "https://api.quadfile.org",
  "api-test.quadfile.org": SUPABASE_ORIGIN,
};

export const OLD_API_HOSTS = Object.keys(STORAGE_REDIRECT_ORIGINS);

const STORAGE_PUBLIC_PREFIX = "/storage/v1/object/public/";

/** Short on purpose: an intermediary must not keep the redirect for long. */
export const REDIRECT_CACHE_CONTROL = "public, max-age=3600";

export type OldApiHostAction =
  | { kind: "redirect"; location: string; headers: Record<string, string> }
  | { kind: "proxy"; url: string };

/** Lower-cased host without a port, as Next's own `has: host` matcher reads it. */
export function normalizeHost(host: string | null | undefined): string {
  return (host ?? "").split(":", 1)[0].toLowerCase();
}

/**
 * What to do with a request for an old API host, or null when the host is not
 * one (the request then behaves exactly as before).
 */
export function oldApiHostAction(
  host: string | null | undefined,
  method: string,
  pathname: string,
  search: string,
): OldApiHostAction | null {
  const hostname = normalizeHost(host);
  if (!Object.hasOwn(STORAGE_REDIRECT_ORIGINS, hostname)) return null;

  const upper = method.toUpperCase();
  if ((upper === "GET" || upper === "HEAD") && pathname.startsWith(STORAGE_PUBLIC_PREFIX)) {
    return {
      kind: "redirect",
      location: `${STORAGE_REDIRECT_ORIGINS[hostname]}${pathname}${search}`,
      headers: {
        "Access-Control-Allow-Origin": "*",
        "Cache-Control": REDIRECT_CACHE_CONTROL,
      },
    };
  }
  return { kind: "proxy", url: `${SUPABASE_ORIGIN}${pathname}${search}` };
}
