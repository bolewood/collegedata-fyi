import { afterEach, describe, expect, it, vi } from "vitest";
import { DATA_QUALITY_LAUNCH_DATE, dataQualityLaunched, isDataQualityLaunched } from "./data-quality";

// The gate is decided once per build, in next.config.ts. The only faked thing
// here is the clock the config reads when the build starts.
const LAUNCH_MS = Date.parse(`${DATA_QUALITY_LAUNCH_DATE}T00:00:00Z`);

async function buildEnv(now: number) {
  vi.resetModules();
  vi.useFakeTimers();
  vi.setSystemTime(now);
  // The default export is the Sentry-wrapped config Next actually loads.
  const mod = await import("../../next.config");
  return mod.default.env?.DATA_QUALITY_LAUNCHED;
}

afterEach(() => {
  vi.useRealTimers();
});

describe("build-time launch gate", () => {
  it("is the pure rule at the date boundary", () => {
    expect(isDataQualityLaunched(new Date(LAUNCH_MS - 1))).toBe(false);
    expect(isDataQualityLaunched(new Date(LAUNCH_MS))).toBe(true);
  });

  it("the default next.config export inlines 0 for a build before the date and 1 for a build on it", async () => {
    expect(await buildEnv(LAUNCH_MS - 1000)).toBe("0");
    expect(await buildEnv(LAUNCH_MS)).toBe("1");
  });

  it("every consumer reads the inlined value, not the clock", () => {
    vi.stubEnv("DATA_QUALITY_LAUNCHED", "0");
    vi.useFakeTimers();
    vi.setSystemTime(LAUNCH_MS + 365 * 86_400_000);
    expect(dataQualityLaunched()).toBe(false);
    vi.stubEnv("DATA_QUALITY_LAUNCHED", "1");
    vi.setSystemTime(LAUNCH_MS - 365 * 86_400_000);
    expect(dataQualityLaunched()).toBe(true);
  });

  it("is closed when the build left it unset", () => {
    vi.stubEnv("DATA_QUALITY_LAUNCHED", undefined as unknown as string);
    expect(dataQualityLaunched()).toBe(false);
  });
});
