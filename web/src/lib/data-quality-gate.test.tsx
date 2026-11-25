// PRD 040 launch gate, tested through the real consumers in both states. The
// only thing faked is the clock: removing the gate from any consumer (nav,
// footer, methodology, sitemap, page metadata, the snapshot loader) must fail
// a test here.

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { renderToStaticMarkup } from "react-dom/server";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FIXTURE_SNAPSHOT } from "./__fixtures__/data-quality-snapshot";
import { DATA_QUALITY_LAUNCH_DATE } from "./data-quality";

vi.mock("next/navigation", () => ({
  usePathname: () => "/data-quality",
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  notFound: () => {
    throw new Error("NEXT_NOT_FOUND");
  },
}));
// The search box pulls in the Supabase client; the gate doesn't touch it.
vi.mock("@/components/HeaderSchoolSearch", () => ({ HeaderSchoolSearch: () => null }));
vi.mock("@/components/CmdKCatalog", () => ({ CmdKCatalog: () => null }));
vi.mock("@/lib/queries", () => ({
  fetchManifest: async () => [],
  aggregateSchools: () => [],
  fetchSchoolSlugResolver: async () => (slug: string) => slug,
}));
vi.mock("@/lib/acceptance-history-data", () => ({
  acceptanceRateSitemap: async () => [],
  earlyDecisionSitemap: async () => [],
  gpaSitemap: async () => [],
}));

import { Nav } from "@/components/Nav";
import { Footer } from "@/components/Footer";
import { ArchiveStatusHeader } from "@/components/ArchiveStatusHeader";
import MethodologyIndexPage from "@/app/methodology/page";
import sitemap from "@/app/sitemap";
import { generateMetadata } from "@/app/data-quality/page";
import { CoverageDashboard } from "@/components/CoverageDashboard";
import { DataQualityBody, DataQualityView } from "@/components/DataQualityView";
import { loadLatestSnapshot } from "./data-quality-snapshots";

const LAUNCH_MS = Date.parse(`${DATA_QUALITY_LAUNCH_DATE}T00:00:00Z`);
const CLOSED = new Date(LAUNCH_MS - 1000);
const OPEN = new Date(LAUNCH_MS);

function at(when: Date) {
  vi.useFakeTimers();
  vi.setSystemTime(when);
}

afterEach(() => {
  vi.useRealTimers();
});

describe("gate: nav and footer", () => {
  // The nav's More menu lists its links in the markup whether or not it is open.
  it("says Coverage before launch and Archive status after, in the nav", () => {
    at(CLOSED);
    const before = renderToStaticMarkup(<Nav />);
    expect(before).toContain(">Coverage<");
    expect(before).not.toContain("Archive status");
    at(OPEN);
    const after = renderToStaticMarkup(<Nav />);
    expect(after).toContain(">Archive status<");
    expect(after).not.toContain(">Coverage<");
  });

  it("says Coverage before launch and Archive status after, in the footer", () => {
    at(CLOSED);
    const before = renderToStaticMarkup(<Footer />);
    expect(before).toContain('<a href="/coverage">Coverage</a>');
    at(OPEN);
    const after = renderToStaticMarkup(<Footer />);
    expect(after).toContain('<a href="/coverage">Archive status</a>');
  });

  it("shows the Data quality tab in the header only after launch", () => {
    at(CLOSED);
    expect(renderToStaticMarkup(<ArchiveStatusHeader active="coverage" />)).not.toContain("/data-quality");
    at(OPEN);
    expect(renderToStaticMarkup(<ArchiveStatusHeader active="coverage" />)).toContain('href="/data-quality"');
  });
});

describe("gate: methodology page", () => {
  it("links the Data quality page only after launch, and always links the Has a CDS preset", () => {
    at(CLOSED);
    const before = renderToStaticMarkup(<MethodologyIndexPage />);
    expect(before).not.toContain('href="/data-quality"');
    expect(before).toContain('href="/coverage?status=cds_available_current,cds_available_stale"');
    at(OPEN);
    const after = renderToStaticMarkup(<MethodologyIndexPage />);
    expect(after).toContain('href="/data-quality"');
    expect(after).toContain('href="/coverage?status=cds_available_current,cds_available_stale"');
  });
});

describe("gate: CSV downloads on both tabs", () => {
  it("renders no CSV links before launch and all of them after", () => {
    at(CLOSED);
    const cov = renderToStaticMarkup(<CoverageDashboard rows={[]} />);
    const dq = renderToStaticMarkup(<DataQualityView snapshot={FIXTURE_SNAPSHOT} />);
    expect(cov).not.toContain("(CSV)");
    expect(dq).not.toContain("as CSV");
    at(OPEN);
    const covOpen = renderToStaticMarkup(<CoverageDashboard rows={[]} />);
    const dqOpen = renderToStaticMarkup(<DataQualityView snapshot={FIXTURE_SNAPSHOT} />);
    expect(covOpen).toContain("Download this view (CSV)");
    expect(covOpen).toContain("Download all colleges (CSV)");
    expect(dqOpen.match(/as CSV/g)).toHaveLength(3);
    // Plain links to the route, for the selected year, one per table.
    expect(dqOpen).toContain('href="/data-quality/csv/reports/2025-26"');
    expect(dqOpen).toContain('href="/data-quality/csv/federal/2025-26"');
    expect(dqOpen).toContain('href="/data-quality/csv/totals/2025-26"');
  });
});

describe("Data quality download links follow the selected year", () => {
  it("point each table's link at the year on screen", () => {
    at(OPEN);
    const html = renderToStaticMarkup(
      <DataQualityBody snapshot={FIXTURE_SNAPSHOT} year={FIXTURE_SNAPSHOT.years.find((y) => y.cds_year === "2023-24")!} />,
    );
    expect(html).toContain('href="/data-quality/csv/reports/2023-24"');
    expect(html).toContain('href="/data-quality/csv/federal/2023-24"');
    expect(html).toContain('href="/data-quality/csv/totals/2023-24"');
    expect(html).not.toContain("/data-quality/csv/reports/2025-26");
  });
});

describe("gate: sitemap", () => {
  it("lists /data-quality only after launch", async () => {
    at(CLOSED);
    expect((await sitemap()).map((e) => e.url)).not.toContain("https://www.collegedata.fyi/data-quality");
    at(OPEN);
    expect((await sitemap()).map((e) => e.url)).toContain("https://www.collegedata.fyi/data-quality");
  });
});

describe("gate: page metadata", () => {
  it("is noindex before launch and indexable after, canonical in both", () => {
    at(CLOSED);
    expect(generateMetadata().robots).toEqual({ index: false, follow: false });
    expect(generateMetadata().alternates?.canonical).toBe("/data-quality");
    at(OPEN);
    expect(generateMetadata().robots).toBeUndefined();
    expect(generateMetadata().alternates?.canonical).toBe("/data-quality");
  });
});

describe("gate: the real snapshot loader", () => {
  it("returns null for the committed directory (README only) before launch and throws after", () => {
    at(CLOSED);
    expect(loadLatestSnapshot()).toBeNull();
    at(OPEN);
    expect(() => loadLatestSnapshot()).toThrow(/no snapshot/);
  });

  it("reads real files, picks the newest, and fails on same-date files in both states", () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "dq-snap-"));
    try {
      const write = (name: string, snapshot_of: string) =>
        fs.writeFileSync(path.join(dir, name), JSON.stringify({ ...FIXTURE_SNAPSHOT, snapshot_of }));
      fs.writeFileSync(path.join(dir, "README.md"), "not a snapshot");
      write("2026-11-17.json", "2026-11-17T10:00:00Z");
      write("2026-11-24.json", "2026-11-24T12:25:03Z");
      for (const when of [CLOSED, OPEN]) {
        at(when);
        expect(loadLatestSnapshot(dir)?.snapshot_of).toBe("2026-11-24T12:25:03Z");
      }
      write("dup.json", "2026-11-24T23:00:00Z");
      for (const when of [CLOSED, OPEN]) {
        at(when);
        expect(() => loadLatestSnapshot(dir)).toThrow(/same date/);
      }
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });

  it("fails on invalid JSON and an unknown public_format even before launch", () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "dq-snap-"));
    try {
      at(CLOSED);
      fs.writeFileSync(path.join(dir, "bad.json"), "{nope");
      expect(() => loadLatestSnapshot(dir)).toThrow(/not valid JSON/);
      fs.writeFileSync(path.join(dir, "bad.json"), JSON.stringify({ ...FIXTURE_SNAPSHOT, public_format: 9 }));
      expect(() => loadLatestSnapshot(dir)).toThrow(/public_format/);
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });
});
