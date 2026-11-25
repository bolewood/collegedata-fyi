import { vi } from "vitest";

/** Set the build-time launch gate for a test (vitest.config.ts restores it after each test). */
export function setLaunchGate(launched: boolean) {
  vi.stubEnv("DATA_QUALITY_LAUNCHED", launched ? "1" : "0");
}
