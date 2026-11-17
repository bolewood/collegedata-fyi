import { describe, expect, it } from "vitest";
import { mapWithConcurrency } from "./map-with-concurrency";

describe("mapWithConcurrency", () => {
  it("keeps input order and never runs more than the limit at once", async () => {
    let running = 0;
    let peak = 0;
    const out = await mapWithConcurrency([5, 1, 4, 2, 3, 0, 6], 3, async (n) => {
      running += 1;
      peak = Math.max(peak, running);
      await new Promise((r) => setTimeout(r, n * 3));
      running -= 1;
      return n * 10;
    });
    expect(out).toEqual([50, 10, 40, 20, 30, 0, 60]);
    expect(peak).toBe(3);
  });

  it("handles an empty list and a limit larger than the list", async () => {
    expect(await mapWithConcurrency([], 4, async (n: number) => n)).toEqual([]);
    expect(await mapWithConcurrency([1, 2], 10, async (n) => n + 1)).toEqual([2, 3]);
  });

  it("treats a bad limit as one at a time and rejects when a call rejects", async () => {
    expect(await mapWithConcurrency([1, 2, 3], 0, async (n) => n)).toEqual([1, 2, 3]);
    await expect(
      mapWithConcurrency([1, 2], 2, async (n) => {
        if (n === 2) throw new Error("boom");
        return n;
      }),
    ).rejects.toThrow("boom");
  });
});
