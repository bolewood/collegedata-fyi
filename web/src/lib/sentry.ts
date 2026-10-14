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

export function sentryBeforeSend<E extends SentryEventLike>(event: E): E | null {
  if (typeof event.request?.url === "string" && event.request.url.startsWith("http://localhost")) {
    return null;
  }
  return isHeadlessReaderNoise(event) ? null : event;
}

export function sentryInitOptions(override?: EnvLookup) {
  const release = sentryRelease(override);
  return {
    dsn: override?.NEXT_PUBLIC_SENTRY_DSN ?? SENTRY_DSN,
    environment: sentryEnvironment(override),
    enabled: sentryEnabled(override),
    tracesSampleRate: sentryTracesSampleRate(override?.NODE_ENV),
    ignoreErrors: SENTRY_IGNORE_ERRORS,
    denyUrls: SENTRY_DENY_URLS,
    beforeSend: sentryBeforeSend,
    ...(release ? { release } : {}),
    debug: (override?.SENTRY_DEBUG ?? process.env.SENTRY_DEBUG) === "true",
  };
}
