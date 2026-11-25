import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FIXTURE_SNAPSHOT } from "@/lib/__fixtures__/data-quality-snapshot";
import { DATA_QUALITY_LAUNCH_DATE } from "@/lib/data-quality";

const mocks = vi.hoisted(() => ({
  loadLatestSnapshot: vi.fn(),
}));

vi.mock("@/lib/data-quality-snapshots", () => ({ loadLatestSnapshot: mocks.loadLatestSnapshot }));
vi.mock("next/navigation", () => ({
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

  it("whole page, gate closed and open: no operator words and at most one em dash in any spelling, metadata included", () => {
    mocks.loadLatestSnapshot.mockReturnValue(FIXTURE_SNAPSHOT);
    const banned =
      /\b(extract(ed|or|ion|s)?|docling|tier ?\d?|drain(ed)?|manifest|projection|pipeline|overlay|acroform|served|scoreboard|base reading|parse error|live (report|reports|count))\b/i;
    const em = /\u2014|&mdash;|&#8212;|&#x2014;/gi;
    vi.useFakeTimers();
    for (const t of [Date.parse(`${DATA_QUALITY_LAUNCH_DATE}T00:00:00Z`) - 1000, Date.parse(`${DATA_QUALITY_LAUNCH_DATE}T00:00:00Z`)]) {
      vi.setSystemTime(t);
      const meta = generateMetadata();
      const page = renderToStaticMarkup(<DataQualityPage />);
      // The source line names the run's file (PRD: the numbers equal the run named on the page). It is the one element
      // allowed to say "scoreboard", and nothing else about it is exempt: every other banned word is checked in it too.
      const source = page.match(/<p id="dq-source"[\s\S]*?<\/p>/)![0];
      const rest = page.replace(source, "");
      expect(source.replace(/<[^>]*>/g, " ").replace(/scoreboard/gi, "")).not.toMatch(banned);
      const text = (rest + String(meta.title) + String(meta.description)).replace(/<[^>]*>/g, " ");
      expect(text).not.toMatch(banned);
      expect(((page + String(meta.title) + String(meta.description)).match(em) ?? []).length).toBeLessThanOrEqual(1);
    }
  });

  it("names the run plainly, in normal case, with the date and time from the snapshot and the file name", () => {
    mocks.loadLatestSnapshot.mockReturnValue(FIXTURE_SNAPSHOT);
    const html = renderToStaticMarkup(<DataQualityPage />);
    const line = html.match(/<p id="dq-source"[^>]*>([\s\S]*?)<\/p>/)![1].replace(/<[^>]*>/g, "");
    expect(line).toContain("November 24, 2026");
    expect(line).toContain("12:25 UTC");
    expect(line).toContain(FIXTURE_SNAPSHOT.scoreboard_run);
    expect(html).not.toMatch(/class="meta"[^>]*>\s*Numbers from/);
  });

  it("lets the loader's error through when no snapshot exists, rather than showing an empty page", () => {
    mocks.loadLatestSnapshot.mockImplementation(() => {
      throw new Error("no snapshot");
    });
    expect(() => renderToStaticMarkup(<DataQualityPage />)).toThrow("no snapshot");
  });
});
