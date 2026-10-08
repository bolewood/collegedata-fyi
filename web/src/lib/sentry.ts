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
export const SENTRY_IGNORE_ERRORS = [/\["@context"\]\.toLowerCase/];

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
  return Boolean(message && SENTRY_IGNORE_ERRORS[0].test(message));
}

export function sentryInitOptions(override?: EnvLookup) {
  const release = sentryRelease(override);
  return {
    dsn: override?.NEXT_PUBLIC_SENTRY_DSN ?? SENTRY_DSN,
    environment: sentryEnvironment(override),
    tracesSampleRate: sentryTracesSampleRate(override?.NODE_ENV),
    ignoreErrors: SENTRY_IGNORE_ERRORS,
    ...(release ? { release } : {}),
    debug: (override?.SENTRY_DEBUG ?? process.env.SENTRY_DEBUG) === "true",
  };
}
