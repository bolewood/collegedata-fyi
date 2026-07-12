// Evidence-bundle loader: one fetch per page lifetime, concurrent callers
// share the in-flight promise, and a failed load never poisons the cache —
// the next call retries.

import { afterEach, describe, expect, it, vi } from "vitest";

const FAKE_BUNDLE = { bundle_version: "evidence-v1", school_count: 0, schools: [] };

async function freshModule() {
  vi.resetModules();
  return import("./bundle");
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("loadBundle", () => {
  it("dedupes concurrent calls into a single fetch and caches the result", async () => {
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => FAKE_BUNDLE,
    });
    vi.stubGlobal("fetch", fetchMock);
    const { loadBundle, getCachedBundle } = await freshModule();

    expect(getCachedBundle()).toBeNull();
    const [a, b] = await Promise.all([loadBundle(), loadBundle()]);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    expect(fetchMock).toHaveBeenCalledWith("/discovery/evidence-v1.json");
    expect(a).toBe(b);
    expect(getCachedBundle()).toBe(a);

    // Later calls serve the cache without another network trip.
    await expect(loadBundle()).resolves.toBe(a);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it("rejects on HTTP errors, leaves the cache empty, and lets a retry succeed", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 503 })
      .mockResolvedValueOnce({ ok: true, json: async () => FAKE_BUNDLE });
    vi.stubGlobal("fetch", fetchMock);
    const { loadBundle, getCachedBundle } = await freshModule();

    await expect(loadBundle()).rejects.toThrow(/HTTP 503/);
    expect(getCachedBundle()).toBeNull();

    // The failed in-flight promise was cleared: retrying refetches instead of
    // replaying the rejection forever.
    await expect(loadBundle()).resolves.toMatchObject({
      bundle_version: "evidence-v1",
    });
    expect(fetchMock).toHaveBeenCalledTimes(2);
  });

  it("propagates network failures to every concurrent caller, then recovers", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new Error("offline"))
      .mockResolvedValueOnce({ ok: true, json: async () => FAKE_BUNDLE });
    vi.stubGlobal("fetch", fetchMock);
    const { loadBundle } = await freshModule();

    const p1 = loadBundle();
    const p2 = loadBundle();
    await expect(p1).rejects.toThrow("offline");
    await expect(p2).rejects.toThrow("offline");
    expect(fetchMock).toHaveBeenCalledTimes(1); // shared in-flight promise

    await expect(loadBundle()).resolves.toMatchObject({
      bundle_version: "evidence-v1",
    });
  });
});
