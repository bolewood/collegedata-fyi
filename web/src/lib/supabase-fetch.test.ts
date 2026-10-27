import { afterEach, describe, expect, it, vi } from "vitest";
import { createTimedFetch } from "./supabase-fetch";

describe("createTimedFetch", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("merges a caller AbortSignal with the timeout signal", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response("ok"));
    vi.stubGlobal("fetch", fetchMock);
    const caller = new AbortController();
    caller.abort();
    const timedFetch = createTimedFetch(5_000);
    await timedFetch("https://example.test/rest", { signal: caller.signal });
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(init.signal?.aborted).toBe(true);
  });

  it("aborts a hung request when the timeout fires", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
      return new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => {
          reject(Object.assign(new Error("Aborted"), { name: "TimeoutError" }));
        });
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    const timedFetch = createTimedFetch(20);
    const pending = timedFetch("https://example.test/rest");
    await vi.advanceTimersByTimeAsync(25);
    await expect(pending).rejects.toMatchObject({ name: "TimeoutError" });
  });

  it("does not retry after abort", async () => {
    vi.useFakeTimers();
    const fetchMock = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
      return new Promise((_resolve, reject) => {
        init?.signal?.addEventListener("abort", () => {
          reject(Object.assign(new Error("Aborted"), { name: "TimeoutError" }));
        });
      });
    });
    vi.stubGlobal("fetch", fetchMock);
    const timedFetch = createTimedFetch(20);
    const pending = timedFetch("https://example.test/rest");
    await vi.advanceTimersByTimeAsync(25);
    await pending.catch(() => undefined);
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });
});
