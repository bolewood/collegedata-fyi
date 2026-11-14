// Pure helpers for the Share button (PRD 024, M1). No DOM access here so the
// logic is unit-testable under vitest's node environment.

export type ShareSurface =
  | "school"
  | "school_year"
  | "school_section"
  | "match"
  | "coverage"
  | "recipe"
  | "api";

export type SharePayload = {
  title: string;
  text?: string;
  url: string;
};

const SECTION_ID = /^[A-Za-z][A-Za-z0-9_-]*$/;

/**
 * Build an absolute URL from an origin, a path (may include a query string)
 * and an optional section id appended as a hash. Any hash already on `path`
 * is replaced by the section id, or dropped when none is given. An invalid
 * section id is ignored rather than producing a broken link.
 */
export function buildShareUrl(origin: string, path: string, sectionId?: string): string {
  const base = origin.replace(/\/+$/, "");
  const withoutHash = path.split("#")[0];
  const rooted = withoutHash.startsWith("/") ? withoutHash : `/${withoutHash}`;
  const hash = sectionId && SECTION_ID.test(sectionId) ? `#${sectionId}` : "";
  return `${base}${rooted}${hash}`;
}

/** The payload handed to `navigator.share`. The URL is the shared text. */
export function buildSharePayload(args: {
  title: string;
  text?: string;
  origin: string;
  path: string;
  sectionId?: string;
}): SharePayload {
  const payload: SharePayload = {
    title: args.title,
    url: buildShareUrl(args.origin, args.path, args.sectionId),
  };
  if (args.text) payload.text = args.text;
  return payload;
}

/** True when the error is the user dismissing the native share sheet. */
export function isShareCancellation(error: unknown): boolean {
  return (
    typeof error === "object" &&
    error !== null &&
    (error as { name?: unknown }).name === "AbortError"
  );
}
