import fs from "node:fs";
import path from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FIXTURE_SNAPSHOT } from "@/lib/__fixtures__/data-quality-snapshot";
import { setLaunchGate } from "@/lib/__fixtures__/data-quality-gate";

const mocks = vi.hoisted(() => ({
  earlier: [] as unknown[],
  loadLatestSnapshot: vi.fn(),
  loadReportsFor: vi.fn(),
}));

vi.mock("@/lib/data-quality-snapshots", () => ({ loadLatestSnapshot: mocks.loadLatestSnapshot, loadAllSnapshots: () => [...mocks.earlier, mocks.loadLatestSnapshot()], loadReportsFor: mocks.loadReportsFor }));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

import DataQualityPage, { generateMetadata } from "./page";

afterEach(() => {
  mocks.earlier = [];   // a failure in the middle of a loop must not leak snapshots into later tests
  mocks.loadLatestSnapshot.mockReset();
  mocks.loadReportsFor.mockReset();
});

describe("/data-quality launch gate", () => {
  it("is noindex before launch and indexable after, with the same canonical", () => {
    setLaunchGate(false);
    const before = generateMetadata();
    expect(before.robots).toEqual({ index: false, follow: false });
    expect(before.alternates?.canonical).toBe("/data-quality");

    setLaunchGate(true);
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
    // One snapshot, then three (so the several-snapshot labels, notes and cohort sentence are checked too).
    const older = (day: string, cohort: [string, string]) => {
      const c = JSON.parse(JSON.stringify(FIXTURE_SNAPSHOT));
      c.snapshot_of = `${day}T12:00:00Z`;
      c.scoreboard_run = `scoreboard-${day.replaceAll("-", "")}T120000Z.json`;
      [c.renewal.current_year, c.renewal.previous_year] = cohort;
      return c;
    };
    for (const earlier of [[], [older("2026-08-01", ["2024-25", "2023-24"]), older("2026-08-20", ["2025-26", "2024-25"])]]) {
      mocks.earlier = earlier;
      for (const launched of [false, true]) {
        setLaunchGate(launched);
        const meta = generateMetadata();
        const page = renderToStaticMarkup(<DataQualityPage />);
        // The source line names the run's file (PRD: the numbers equal the run named on the page). It is the one element
        // allowed to say "scoreboard", and nothing else about it is exempt: every other banned word is checked in it too.
        const source = page.match(/<p id="dq-source"[\s\S]*?<\/p>/)![0];
        // The trend labels each snapshot with its run's file name, the other element allowed to say "scoreboard".
        const runs = [...page.matchAll(/<span class="dq-trend-run"[^>]*>([^<]*)<\/span>/g)].map((m) => m[1]);
        expect(runs.length).toBe((earlier.length + 1) * 2);   // a header per snapshot in each of the two trend tables
        for (const run of runs) expect(run).toMatch(/^scoreboard-\d{8}T\d{6}Z\.json$/);
        const rest = page.replace(source, "").replace(/<span class="dq-trend-run"[^>]*>[^<]*<\/span>/g, "");
        expect(source.replace(/<[^>]*>/g, " ").replace(/scoreboard/gi, "")).not.toMatch(banned);
        const text = (rest + String(meta.title) + String(meta.description)).replace(/<[^>]*>/g, " ");
        expect(text).not.toMatch(banned);
        expect(text).toContain(earlier.length ? "so a new series starts there" : "A trend appears here once there are two snapshots");
        expect(((page + String(meta.title) + String(meta.description)).match(em) ?? []).length).toBeLessThanOrEqual(1);
      }
    }
    mocks.earlier = [];
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
  const renderAt = (launched: boolean, reports: unknown) => {
    mocks.loadLatestSnapshot.mockReturnValue(FIXTURE_SNAPSHOT);
    mocks.loadReportsFor.mockReturnValue(reports);
    setLaunchGate(launched);
    return renderToStaticMarkup(<DataQualityPage />);
  };

  it("makes no count a button before launch, and builds the page with the reports file loaded (so the build checks it)", () => {
    const html = renderAt(false, realReports());
    expect(html).not.toContain("dq-count");
    expect(mocks.loadReportsFor).toHaveBeenCalledWith(FIXTURE_SNAPSHOT);
  });

  it("makes counts buttons once launched, only when the snapshot has a reports file", () => {
    expect(renderAt(true, realReports())).toContain('class="dq-count"');
    expect(renderAt(true, null)).not.toContain("dq-count");
  });

  it("does not put the reports in the page: no report id, school name or school link of the file is in its HTML", () => {
    const reports = realReports();
    const html = renderAt(true, reports);
    const sample = Object.values(reports.years as Record<string, { id: string; school: string | null }[]>).flatMap((rows) => rows.slice(0, 40));
    expect(sample.length).toBeGreaterThan(100);
    for (const r of sample) {
      expect(html).not.toContain(r.id);
      if (r.school) expect(html).not.toContain(`/schools/${r.school}/`);
    }
    for (const name of Object.values(reports.schools as Record<string, string>).slice(0, 40)) expect(html).not.toContain(name);
  });
});

describe("/data-quality over time", () => {
  it("is part of the page, so it is gated with it: one snapshot gives the first-snapshot state, with no line", () => {
    mocks.loadLatestSnapshot.mockReturnValue(FIXTURE_SNAPSHOT);
    mocks.loadReportsFor.mockReturnValue(null);
    for (const launched of [false, true]) {
      setLaunchGate(launched);
      const html = renderToStaticMarkup(<DataQualityPage />);
      const section = html.match(/<section aria-labelledby="dq-trend-heading"[\s\S]*?<\/section>/)![0];
      expect(section).toContain("First snapshot, November 24, 2026");
      expect(section).toContain("A trend appears here once there are two snapshots.");
      expect(section).not.toContain("<svg");
    }
  });
});
