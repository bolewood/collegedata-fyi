import { isPrivateFeedback, communityBreadcrumb } from "./community-privacy";
/**
 * Single source of truth for Sentry project identity and runtime options.
 *
 * Keep the project slug here (or override with SENTRY_PROJECT) so a rename
 * does not require hunting through init files and next.config.
 *
 * Client bundles only see env vars that Next.js can statically replace.
 * Always read `process.env.NEXT_PUBLIC_*` and `process.env.NODE_ENV` as
 * member expressions — `env.NEXT_PUBLIC_VERCEL_ENV` via a passed object
 * stays undefined in the browser and used to tag production as development.
 */

export const SENTRY_DSN =
  process.env.NEXT_PUBLIC_SENTRY_DSN ??
  "https://d46ac96e29069711756ecf044a8e04b8@o4510665526673408.ingest.us.sentry.io/4512221498441728";

export const SENTRY_ORG = process.env.SENTRY_ORG ?? "bolewood";

export const SENTRY_PROJECT = process.env.SENTRY_PROJECT ?? "collegedata-fyi";

/** Production/preview sample rate for a low-traffic site. Dev always uses 1.0. */
export const SENTRY_PRODUCTION_TRACES_SAMPLE_RATE = 0.2;

/**
 * Safari reports this from injected SEO/schema scrapers that walk JSON-LD
 * and call `obj["@context"].toLowerCase()`. Our pages emit `@context` as
 * inert `application/ld+json` data and never execute that access.
 */
export const SENTRY_JSONLD_CONTEXT_NOISE = /\["@context"\]\.toLowerCase/;

/** Headless “reader.self” bots (Sentry FYI-E / FYI-A). */
export const SENTRY_READER_SELF_NOISE = /reader\.self/;

export const SENTRY_IGNORE_ERRORS = [
  SENTRY_JSONLD_CONTEXT_NOISE,
  SENTRY_READER_SELF_NOISE,
  "Object Not Found Matching Id",
];

export const SENTRY_DENY_URLS = [
  /\/49d0ab2abf43d524\/script\.js/,
  /\/_vercel\/insights\//,
];

type EnvLookup = Record<string, string | undefined>;

export function sentryEnvironment(override?: EnvLookup): string {
  if (override) {
    return (
      override.NEXT_PUBLIC_VERCEL_ENV ??
      override.VERCEL_ENV ??
      override.NODE_ENV ??
      "development"
    );
  }
  return (
    process.env.NEXT_PUBLIC_VERCEL_ENV ??
    process.env.VERCEL_ENV ??
    process.env.NODE_ENV ??
    "development"
  );
}

export function sentryRelease(override?: EnvLookup): string | undefined {
  if (override) {
    return override.NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA ?? override.VERCEL_GIT_COMMIT_SHA;
  }
  return (
    process.env.NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA ?? process.env.VERCEL_GIT_COMMIT_SHA
  );
}

export function sentryTracesSampleRate(
  nodeEnv: string | undefined = process.env.NODE_ENV,
): number {
  return nodeEnv === "development" ? 1.0 : SENTRY_PRODUCTION_TRACES_SAMPLE_RATE;
}

export function sentrySourceMapsEnabled(
  authToken: string | undefined = process.env.SENTRY_AUTH_TOKEN,
): boolean {
  return Boolean(authToken);
}

export function isSentryVerifyAllowed(
  vercelEnv: string | undefined = process.env.VERCEL_ENV,
): boolean {
  return vercelEnv !== "production";
}

export function isJsonLdContextExtensionNoise(
  message: string | undefined,
): boolean {
  return Boolean(message && SENTRY_JSONLD_CONTEXT_NOISE.test(message));
}

export function sentryEnabled(override?: EnvLookup): boolean {
  const ci = override ? override.CI : process.env.CI;
  return !ci && sentryEnvironment(override) !== "ci";
}

type SentryEventLike = {
  message?: string;
  request?: { url?: string };
  exception?: {
    values?: Array<{
      value?: string;
      stacktrace?: { frames?: Array<{ function?: string; filename?: string; abs_path?: string }> };
    }>;
  };
};

export function isHeadlessReaderNoise(event: SentryEventLike): boolean {
  const message = event.exception?.values?.[0]?.value ?? event.message;
  if (typeof message === "string" && SENTRY_READER_SELF_NOISE.test(message)) return true;
  return (event.exception?.values ?? []).some((value) =>
    (value.stacktrace?.frames ?? []).some(
      (frame) =>
        frame.function === "magicRPC" ||
        frame.filename?.includes("reader.self") ||
        frame.abs_path?.includes("reader.self"),
    ),
  );
}

const FILTERED = "[Filtered]";
const SENSITIVE_PARAMS = new Set(["code", "q"]);
const SENSITIVE_QUERY_RE = /(^|[?&;])(code|q)=[^&#\s"'<>]*/gi;

/** Replace the value of `code` (Match share codes) and `q` (search text) query params. */
export function scrubSensitiveUrl(value: string): string {
  return value.replace(SENSITIVE_QUERY_RE, (_m, sep: string, key: string) => `${sep}${key}=${FILTERED}`);
}

function scrubDeep(value: unknown, depth = 0): unknown {
  if (depth > 8) return value;
  if (typeof value === "string") return scrubSensitiveUrl(value);
  if (Array.isArray(value)) {
    // Handles Sentry's [["code", "value"]] query_string shape.
    if (
      value.length === 2 &&
      typeof value[0] === "string" &&
      SENSITIVE_PARAMS.has(value[0].toLowerCase())
    ) {
      return [value[0], FILTERED];
    }
    return value.map((v) => scrubDeep(v, depth + 1));
  }
  if (value && typeof value === "object") {
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(value as Record<string, unknown>)) {
      out[k] = SENSITIVE_PARAMS.has(k.toLowerCase()) && typeof v === "string"
        ? FILTERED
        : scrubDeep(v, depth + 1);
    }
    return out;
  }
  return value;
}

/** Remove share codes and search text from URLs on an error or transaction event. */
export function scrubSentryEvent<E>(event: E): E {
  const e = event as Record<string, unknown>;
  for (const key of ["request", "breadcrumbs", "transaction", "spans", "contexts", "extra", "tags"]) {
    if (e[key] !== undefined) e[key] = scrubDeep(e[key]);
  }
  return event;
}

/** Same scrub for a single breadcrumb (url, to, from, message, data). */
export function scrubSentryBreadcrumb<B>(breadcrumb: B): B {
  const b = breadcrumb as Record<string, unknown>;
  for (const key of ["message", "data"]) {
    if (b[key] !== undefined) b[key] = scrubDeep(b[key]);
  }
  return breadcrumb;
}

export function sentryBeforeSend<E extends SentryEventLike>(event: E): E | null {
  if (isPrivateFeedback(event)) return null;
  if (typeof event.request?.url === "string" && event.request.url.startsWith("http://localhost")) {
    return null;
  }
  return isHeadlessReaderNoise(event) ? null : scrubSentryEvent(event);
}

export function sentryBeforeSendTransaction<T>(event: T): T | null {
  return isPrivateFeedback(event) ? null : scrubSentryEvent(event);
}

export function sentryBeforeBreadcrumb<B>(breadcrumb: B): B | null {
  const kept = communityBreadcrumb(breadcrumb);
  return kept === null ? null : scrubSentryBreadcrumb(kept);
}

export function sentryInitOptions(override?: EnvLookup) {
  const release = sentryRelease(override);
  return {
    dsn: override?.NEXT_PUBLIC_SENTRY_DSN ?? SENTRY_DSN,
    environment: sentryEnvironment(override),
    enabled: sentryEnabled(override),
    tracesSampleRate: sentryTracesSampleRate(override?.NODE_ENV),
    // SDK 11 defaults to streamed spans, which ignore beforeSendTransaction.
    // Static traces let the same private-route filter drop the entire trace.
    traceLifecycle: "static" as const,
    tracesSampler: (context: { inheritOrSampleWith: (rate: number) => number }) =>
      isPrivateFeedback(context)
        ? 0
        : context.inheritOrSampleWith(sentryTracesSampleRate(override?.NODE_ENV)),
    ignoreErrors: SENTRY_IGNORE_ERRORS,
    denyUrls: SENTRY_DENY_URLS,
    beforeSend: sentryBeforeSend,
    beforeBreadcrumb: sentryBeforeBreadcrumb,
    beforeSendTransaction: sentryBeforeSendTransaction,
    sendDefaultPii: false,
    ...(release ? { release } : {}),
    debug: (override?.SENTRY_DEBUG ?? process.env.SENTRY_DEBUG) === "true",
  };
}
