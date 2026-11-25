import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FIXTURE_SNAPSHOT } from "@/lib/__fixtures__/data-quality-snapshot";
import { DATA_QUALITY_LAUNCH_DATE } from "@/lib/data-quality";

const mocks = vi.hoisted(() => ({
  loadLatestSnapshot: vi.fn(),
  notFound: vi.fn(() => {
    throw new Error("NEXT_NOT_FOUND");
  }),
}));

vi.mock("@/lib/data-quality-snapshots", () => ({ loadLatestSnapshot: mocks.loadLatestSnapshot }));
vi.mock("next/navigation", () => ({
  notFound: mocks.notFound,
  useSearchParams: () => new URLSearchParams(),
}));

import DataQualityPage, { generateMetadata } from "./page";

afterEach(() => {
  vi.useRealTimers();
  mocks.loadLatestSnapshot.mockReset();
});

describe("/data-quality launch gate", () => {
  it("is noindex before launch and indexable after, with the same canonical", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(`${DATA_QUALITY_LAUNCH_DATE}T00:00:00Z`).getTime() - 1000);
    const before = generateMetadata();
    expect(before.robots).toEqual({ index: false, follow: false });
    expect(before.alternates?.canonical).toBe("/data-quality");

    vi.setSystemTime(new Date(`${DATA_QUALITY_LAUNCH_DATE}T00:00:00Z`));
    const after = generateMetadata();
    expect(after.robots).toBeUndefined();
    expect(after.alternates?.canonical).toBe("/data-quality");
  });

  it("renders the lede and the archive header from the snapshot", () => {
    mocks.loadLatestSnapshot.mockReturnValue(FIXTURE_SNAPSHOT);
    const html = renderToStaticMarkup(<DataQualityPage />);
    expect(html).toContain("Snapshot of November 24, 2026");
    expect(html).toContain('aria-label="Archive status"');
    expect(html).toContain("<h1");
  });

  it("is a 404, not an empty page, when no snapshot exists", () => {
    mocks.loadLatestSnapshot.mockReturnValue(null);
    expect(() => renderToStaticMarkup(<DataQualityPage />)).toThrow("NEXT_NOT_FOUND");
  });
});
