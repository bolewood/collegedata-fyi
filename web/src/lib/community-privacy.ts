/**
 * Query parameters that must never reach analytics or error reporting:
 * `code` is a Match share code (reversible student profile), `q` is search
 * text. Single list, shared with sentry.ts.
 */
export const SENSITIVE_PARAMS: ReadonlySet<string> = new Set(["code", "q"]);

/** Form URLs never carry query/hash data into analytics or error reporting; every URL loses sensitive params. */
export function communityAnalyticsUrl(raw: string): string {
  try {
    const url = new URL(raw);
    if (/^\/(?:api\/)?feedback\/?$/.test(decodeURIComponent(url.pathname))) {
      url.search = "";
      url.hash = "";
    }
    for (const key of Array.from(new Set(url.searchParams.keys()))) {
      if (SENSITIVE_PARAMS.has(key.toLowerCase())) url.searchParams.delete(key);
    }
    return url.toString();
  } catch {
    return raw;
  }
}
export function isPrivateFeedback(value: unknown): boolean {
  try {
    if (
      typeof window !== "undefined" &&
      /^\/(?:api\/)?feedback\/?$/.test(
        decodeURIComponent(window.location.pathname),
      )
    )
      return true;
    return /\/(?:api\/)?feedback(?:[/?#"\s]|$)/i.test(
      decodeURIComponent(JSON.stringify(value)),
    );
  } catch {
    return true;
  }
}
export function communityBreadcrumb<T>(breadcrumb: T): T | null {
  return isPrivateFeedback(breadcrumb) ? null : breadcrumb;
}
