import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";
import {
  SENTRY_DSN,
  SENTRY_IGNORE_ERRORS,
  SENTRY_ORG,
  SENTRY_PRODUCTION_TRACES_SAMPLE_RATE,
  SENTRY_PROJECT,
  isJsonLdContextExtensionNoise,
  isSentryVerifyAllowed,
  sentryEnvironment,
  sentryInitOptions,
  sentryRelease,
  sentrySourceMapsEnabled,
  sentryTracesSampleRate,
} from "./sentry";

const ORIGINAL_ENV = { ...process.env };

afterEach(() => {
  process.env = { ...ORIGINAL_ENV };
});

describe("sentry project identity", () => {
  it("defaults the project slug to collegedata-fyi in one config module", () => {
    expect(SENTRY_PROJECT).toBe("collegedata-fyi");
    expect(SENTRY_ORG).toBe("bolewood");
    expect(SENTRY_DSN).toContain("o4510665526673408.ingest.us.sentry.io");
  });
});

describe("sentryEnvironment", () => {
  it("prefers VERCEL_ENV over NODE_ENV so preview is distinct from production", () => {
    expect(
      sentryEnvironment({
        NEXT_PUBLIC_VERCEL_ENV: "preview",
        VERCEL_ENV: "preview",
        NODE_ENV: "production",
      }),
    ).toBe("preview");
    expect(
      sentryEnvironment({
        VERCEL_ENV: "production",
        NODE_ENV: "production",
      }),
    ).toBe("production");
    expect(sentryEnvironment({ NODE_ENV: "development" })).toBe("development");
  });

  it("reads process.env on the no-arg path used by client/server/edge init", () => {
    process.env.NEXT_PUBLIC_VERCEL_ENV = "production";
    process.env.VERCEL_ENV = "production";
    expect(sentryEnvironment()).toBe("production");
    expect(sentryInitOptions().environment).toBe("production");

    process.env.NEXT_PUBLIC_VERCEL_ENV = "preview";
    process.env.VERCEL_ENV = "preview";
    expect(sentryEnvironment()).toBe("preview");
  });
});

describe("sentryRelease", () => {
  it("uses the Vercel git SHA when present", () => {
    expect(
      sentryRelease({
        NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA: "abc1234deadbeef",
      }),
    ).toBe("abc1234deadbeef");
    expect(sentryRelease({})).toBeUndefined();
  });
});

describe("sentryTracesSampleRate", () => {
  it("samples every trace in development and 20% otherwise", () => {
    expect(sentryTracesSampleRate("development")).toBe(1.0);
    expect(sentryTracesSampleRate("production")).toBe(
      SENTRY_PRODUCTION_TRACES_SAMPLE_RATE,
    );
    expect(SENTRY_PRODUCTION_TRACES_SAMPLE_RATE).toBe(0.2);
  });
});

describe("sentrySourceMapsEnabled", () => {
  it("is on only when an auth token is present", () => {
    expect(sentrySourceMapsEnabled("sntrys_example")).toBe(true);
    expect(sentrySourceMapsEnabled(undefined)).toBe(false);
    expect(sentrySourceMapsEnabled("")).toBe(false);
  });
});

describe("isSentryVerifyAllowed", () => {
  it("blocks only Vercel production", () => {
    expect(isSentryVerifyAllowed("production")).toBe(false);
    expect(isSentryVerifyAllowed("preview")).toBe(true);
    expect(isSentryVerifyAllowed("development")).toBe(true);
    expect(isSentryVerifyAllowed(undefined)).toBe(true);
  });
});

describe("sentryInitOptions", () => {
  it("sets environment, release, and sample rate together", () => {
    const options = sentryInitOptions({
      NEXT_PUBLIC_VERCEL_ENV: "production",
      VERCEL_ENV: "production",
      NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA: "deadbeef",
      NODE_ENV: "production",
    });
    expect(options.environment).toBe("production");
    expect(options.release).toBe("deadbeef");
    expect(options.tracesSampleRate).toBe(0.2);
    expect(options.dsn).toBe(SENTRY_DSN);
    expect(options.debug).toBe(false);
    expect(options.ignoreErrors).toBe(SENTRY_IGNORE_ERRORS);
  });
});

describe("client env inlining", () => {
  it("reads Vercel env via static process.env members the bundler can replace", () => {
    const source = readFileSync(
      join(dirname(fileURLToPath(import.meta.url)), "sentry.ts"),
      "utf8",
    );
    expect(source).toContain("process.env.NEXT_PUBLIC_VERCEL_ENV");
    expect(source).toContain("process.env.VERCEL_ENV");
    expect(source).toContain("process.env.NODE_ENV");
    expect(source).toContain("process.env.NEXT_PUBLIC_VERCEL_GIT_COMMIT_SHA");
  });
});

describe("isJsonLdContextExtensionNoise", () => {
  it("matches the Safari @context scraper TypeError and ignores first-party errors", () => {
    expect(
      isJsonLdContextExtensionNoise(
        "undefined is not an object (evaluating 'r[\"@context\"].toLowerCase')",
      ),
    ).toBe(true);
    expect(
      isJsonLdContextExtensionNoise("TypeError: Cannot read properties of undefined"),
    ).toBe(false);
    expect(isJsonLdContextExtensionNoise(undefined)).toBe(false);
  });
});
