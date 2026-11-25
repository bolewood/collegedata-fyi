import fs from "node:fs";
import path from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FIXTURE_SNAPSHOT } from "@/lib/__fixtures__/data-quality-snapshot";
import { DATA_QUALITY_LAUNCH_DATE } from "@/lib/data-quality";

const mocks = vi.hoisted(() => ({
  loadLatestSnapshot: vi.fn(),
  loadReportsFor: vi.fn(),
}));

vi.mock("@/lib/data-quality-snapshots", () => ({ loadLatestSnapshot: mocks.loadLatestSnapshot, loadReportsFor: mocks.loadReportsFor }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

import DataQualityPage, { generateMetadata } from "./page";

afterEach(() => {
  vi.useRealTimers();
  mocks.loadLatestSnapshot.mockReset();
  mocks.loadReportsFor.mockReset();
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
});

describe("/data-quality list of reports behind each count", () => {
  const realReports = () => {
    const dir = path.join(process.cwd(), "src", "data", "data-quality", "reports");
    return JSON.parse(fs.readFileSync(path.join(dir, fs.readdirSync(dir).filter((n) => n.endsWith(".json")).sort().at(-1)!), "utf8"));
  };
  const LAUNCH = Date.parse(`${DATA_QUALITY_LAUNCH_DATE}T00:00:00Z`);
  const renderAt = (ms: number, reports: unknown) => {
    mocks.loadLatestSnapshot.mockReturnValue(FIXTURE_SNAPSHOT);
    mocks.loadReportsFor.mockReturnValue(reports);
    vi.useFakeTimers();
    vi.setSystemTime(ms);
    return renderToStaticMarkup(<DataQualityPage />);
  };

  it("makes no count a button before launch, and builds the page with the reports file loaded (so the build checks it)", () => {
    const html = renderAt(LAUNCH - 1000, realReports());
    expect(html).not.toContain("dq-count");
    expect(mocks.loadReportsFor).toHaveBeenCalledWith(FIXTURE_SNAPSHOT);
  });

  it("makes counts buttons once launched, only when the snapshot has a reports file", () => {
    expect(renderAt(LAUNCH, realReports())).toContain('class="dq-count"');
    expect(renderAt(LAUNCH, null)).not.toContain("dq-count");
  });

  it("does not put the reports in the page: no report id, school name or school link of the file is in its HTML", () => {
    const reports = realReports();
    const html = renderAt(LAUNCH, reports);
    const sample = Object.values(reports.years as Record<string, { id: string; school: string | null }[]>).flatMap((rows) => rows.slice(0, 40));
    expect(sample.length).toBeGreaterThan(100);
    for (const r of sample) {
      expect(html).not.toContain(r.id);
      if (r.school) expect(html).not.toContain(`/schools/${r.school}/`);
    }
    for (const name of Object.values(reports.schools as Record<string, string>).slice(0, 40)) expect(html).not.toContain(name);
  });
});
