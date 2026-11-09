/** Form URLs never carry query/hash data into analytics or error reporting. */
export function communityAnalyticsUrl(raw: string): string {
  try {
    const url = new URL(raw);
    if (/^\/(?:api\/)?feedback\/?$/.test(decodeURIComponent(url.pathname))) {
      url.search = "";
      url.hash = "";
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
