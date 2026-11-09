import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { afterEach, describe, expect, it } from "vitest";
import {
  SENTRY_DENY_URLS,
  SENTRY_DSN,
  SENTRY_IGNORE_ERRORS,
  SENTRY_ORG,
  SENTRY_PRODUCTION_TRACES_SAMPLE_RATE,
  SENTRY_PROJECT,
  SENTRY_READER_SELF_NOISE,
  isHeadlessReaderNoise,
  isJsonLdContextExtensionNoise,
  isSentryVerifyAllowed,
  sentryBeforeSend,
  sentryBeforeSendTransaction,
  sentryBeforeBreadcrumb,
  scrubSensitiveUrl,
  sentryEnabled,
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
    expect(options.denyUrls).toBe(SENTRY_DENY_URLS);
    expect(options.enabled).toBe(true);
    expect(options.beforeSend).toBe(sentryBeforeSend);
    expect(SENTRY_IGNORE_ERRORS).toContain("Object Not Found Matching Id");
    expect(SENTRY_IGNORE_ERRORS).toContain(SENTRY_READER_SELF_NOISE);
    expect(SENTRY_READER_SELF_NOISE.test("TypeError: Failed to fetch via reader.self")).toBe(true);
    expect(SENTRY_DENY_URLS.some((p) => p.test("/49d0ab2abf43d524/script.js"))).toBe(true);
    expect(SENTRY_DENY_URLS.some((p) => p.test("/_vercel/insights/view"))).toBe(true);
    expect(sentryEnabled({ CI: "true", NODE_ENV: "production" })).toBe(false);
    expect(sentryEnabled({ NODE_ENV: "ci" })).toBe(false);
    expect(sentryBeforeSend({ request: { url: "http://localhost:3000/" } })).toBeNull();
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
    expect(source).toContain("process.env.CI");
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

describe("isHeadlessReaderNoise", () => {
  it("drops reader.self messages and magicRPC frames, but keeps first-party fetch errors", () => {
    expect(isHeadlessReaderNoise({ exception: { values: [{ value: "Failed to fetch via reader.self" }] } })).toBe(
      true,
    );
    expect(
      sentryBeforeSend({
        exception: { values: [{ value: "Failed to fetch", stacktrace: { frames: [{ function: "magicRPC" }] } }] },
      }),
    ).toBeNull();
    expect(
      sentryBeforeSend({
        exception: { values: [{ value: "Failed to fetch", stacktrace: { frames: [{ function: "loadSchoolFacts" }] } }] },
      }),
    ).not.toBeNull();
  });
});

describe("sentry URL scrubbing", () => {
  it("filters code and q values but keeps other params", () => {
    expect(scrubSensitiveUrl("https://x.test/match?code=abc123&tab=1")).toBe(
      "https://x.test/match?code=[Filtered]&tab=1",
    );
    expect(scrubSensitiveUrl("/api/schools/search?limit=5&q=mit")).toBe(
      "/api/schools/search?limit=5&q=[Filtered]",
    );
    expect(scrubSensitiveUrl("/schools?query=x&decode=y")).toBe("/schools?query=x&decode=y");
  });

  it("scrubs request, breadcrumbs, spans, and transaction name in beforeSend", () => {
    const event = sentryBeforeSend({
      request: { url: "https://x.test/match?code=SECRET", query_string: "code=SECRET&a=1" },
      transaction: "GET /match?code=SECRET",
      breadcrumbs: [{ category: "navigation", data: { to: "/match?code=SECRET", from: "/?q=harvard" } }],
      spans: [{ description: "GET /api/schools/search?q=harvard" }],
    } as never) as unknown as Record<string, any>;
    const json = JSON.stringify(event);
    expect(json).not.toContain("SECRET");
    expect(json).not.toContain("harvard");
    expect(event.request.url).toBe("https://x.test/match?code=[Filtered]");
    expect(event.request.query_string).toBe("code=[Filtered]&a=1");
  });

  it("scrubs transactions and breadcrumbs", () => {
    const tx = sentryBeforeSendTransaction({
      transaction: "/match?code=SECRET",
      request: { url: "https://x.test/match?code=SECRET" },
      contexts: { trace: { data: { "url.full": "https://x.test/match?code=SECRET" } } },
    }) as unknown as Record<string, unknown>;
    expect(JSON.stringify(tx)).not.toContain("SECRET");
    const crumb = sentryBeforeBreadcrumb({
      category: "fetch",
      data: { url: "/api/schools/search?q=mit", status_code: 200 },
    }) as unknown as { data: { url: string; status_code: number } };
    expect(crumb.data.url).toBe("/api/schools/search?q=[Filtered]");
    expect(crumb.data.status_code).toBe(200);
  });
});
