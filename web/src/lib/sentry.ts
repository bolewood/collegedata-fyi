/**
 * Single source of truth for Sentry project identity and runtime options.
 *
 * Keep the project slug here (or override with SENTRY_PROJECT) so a rename
 * does not require hunting through init files and next.config.
 */

export const SENTRY_DSN =
  process.env.NEXT_PUBLIC_SENTRY_DSN ??
  "https://d46ac96e29069711756ecf044a8e04b8@o4510665526673408.ingest.us.sentry.io/4512221498441728";

export const SENTRY_ORG = process.env.SENTRY_ORG ?? "bolewood";

export const SENTRY_PROJECT = process.env.SENTRY_PROJECT ?? "collegedata-fyi";

/** Production/preview sample rate for a low-traffic site. Dev always uses 1.0. */
export const SENTRY_PRODUCTION_TRACES_SAMPLE_RATE = 0.2;

type EnvLookup = Record<string, string | undefined>;

export function sentryEnvironment(env: EnvLookup = process.env): string {
  return (
    env.NEXT_PUBLIC_VERCEL_ENV ??
    env.VERCEL_ENV ??
    env.NODE_ENV ??
    "development"
  );
}

export function sentryRelease(env: EnvLookup = process.env): string | undefined {
  return env.NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA ?? env.VERCEL_GIT_COMMIT_SHA;
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

export function sentryInitOptions(env: EnvLookup = process.env) {
  const release = sentryRelease(env);
  return {
    dsn: env.NEXT_PUBLIC_SENTRY_DSN ?? SENTRY_DSN,
    environment: sentryEnvironment(env),
    tracesSampleRate: sentryTracesSampleRate(env.NODE_ENV),
    ...(release ? { release } : {}),
    debug: env.SENTRY_DEBUG === "true",
  };
}
