import { describe, expect, it, vi } from "vitest";
import type { NextFetchEvent } from "next/server";
import { NextRequest } from "next/server";

const { recordApiUsageEvent } = vi.hoisted(() => ({ recordApiUsageEvent: vi.fn(async () => undefined) }));
vi.mock("@/lib/api-usage", () => ({
  buildApiUsageEvent: vi.fn(() => ({})),
  recordApiUsageEvent,
}));

import { isUnroutableSchoolPath, proxy } from "./proxy";

const event = { waitUntil: vi.fn() } as unknown as NextFetchEvent;
const call = (path: string) => proxy(new NextRequest(`https://www.collegedata.fyi${path}`), event);

// Sentry COLLEGEDATA-FYI-22: the last letter is a Cyrillic "о".
const CYRILLIC = "/schools/cal-poly-san-luis-obisp%D0%BE";

describe("proxy school path guard", () => {
  it("answers 404 for a school path with non-ASCII characters, on every nested route", () => {
    for (const path of [CYRILLIC, `${CYRILLIC}/2024-25`, `${CYRILLIC}/acceptance-rate`, `${CYRILLIC}/2024-25/cds.csv`, "/schools/a%20b", "/schools/%E0%A4%A"]) {
      expect(call(path).status, path).toBe(404);
    }
  });

  it("lets real school paths through and does not record them as API usage", () => {
    recordApiUsageEvent.mockClear();
    for (const path of ["/schools/yale", "/schools/yale/2024-25", "/schools/w&m", "/schools/yale/2024-25/cds.csv", "/schools/yale/feed.xml"]) {
      const res = call(path);
      expect(res.status, path).toBe(200);
      expect(res.headers.get("x-middleware-next"), path).toBe("1");
    }
    expect(recordApiUsageEvent).not.toHaveBeenCalled();
  });

  it("still records API routes", () => {
    recordApiUsageEvent.mockClear();
    expect(call("/api/schools/yale/facts").status).toBe(200);
    expect(recordApiUsageEvent).toHaveBeenCalledTimes(1);
  });

  it("classifies paths", () => {
    expect(isUnroutableSchoolPath("/schools/yale")).toBe(false);
    expect(isUnroutableSchoolPath("/schools/yalе")).toBe(true);
    expect(isUnroutableSchoolPath("/schools/yal%D0%B5")).toBe(true);
  });
});
