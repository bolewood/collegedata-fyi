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
import { DATA_QUALITY_LAUNCH_DATE, aidCantCheckNote, federalDiffersNote, formatSnapshotDate, selectSnapshot } from "./data-quality";

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
  fetchCoverageRows: async () => [],
  fetchBrandColorIndex: async () => ({}),
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
import { SNAPSHOT_DIR, loadLatestSnapshot } from "./data-quality-snapshots";
import DataQualityPage from "@/app/data-quality/page";
import CoveragePage from "@/app/coverage/page";

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
    // 2025-26 has no federal figures, so Table B has no download: Table A, Table A by section and Table C, three links.
    expect(dqOpen.match(/as CSV/g)).toHaveLength(3);
    // Plain links to the route, for the selected year, one per table.
    expect(dqOpen).toContain('href="/data-quality/csv/reports/2025-26"');
    expect(dqOpen).not.toContain('href="/data-quality/csv/federal/2025-26"');
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

const text = (html: string) => html.replace(/<[^>]*>/g, " ").replace(/\s+/g, " ");

describe("the real pages against the committed snapshot", () => {
  it("/coverage: the renewal tile is the first cell of the summary strip and carries the snapshot's numbers", async () => {
    for (const when of [CLOSED, OPEN]) {
      at(when);
      const snap = loadLatestSnapshot();
      const r = snap.renewal;
      const html = renderToStaticMarkup(await CoveragePage());
      const strip = html.slice(html.indexOf('aria-label="Coverage summary"'));
      expect(strip.indexOf('data-testid="renewal-tile"')).toBeGreaterThan(-1);
      // First test id after the strip opens is the renewal tile.
      expect(strip.match(/data-testid="([^"]+)"/)![1]).toBe("renewal-tile");
      const from = strip.indexOf('data-testid="renewal-tile"');
      const rest = strip.slice(from + 1);
      const next = rest.indexOf("data-testid=");
      const tile = text(next === -1 ? rest : rest.slice(0, next));
      expect(tile).toContain(`${Math.round((r.both / r.previous) * 100)}%`);
      expect(tile).toContain(
        `Of the ${r.previous.toLocaleString("en-US")} schools with a ${r.previous_year} report on file, ${r.both.toLocaleString("en-US")} also have a ${r.current_year} report on file.`,
      );
      expect(tile).toContain(`Snapshot of ${formatSnapshotDate(snap.snapshot_of)}.`);
    }
  });

  it("/data-quality renders the newest year with no throw and shows the no-federal state for a year without figures", () => {
    at(OPEN);
    const snap = loadLatestSnapshot();
    const html = renderToStaticMarkup(<DataQualityPage />);
    expect(html).toContain("Data quality");
    const noFederal = snap.years.find((y) => !y.federal_fall_loaded);
    expect(noFederal).toBeDefined();
    const body = text(renderToStaticMarkup(<DataQualityBody snapshot={snap} year={noFederal!} />));
    expect(body).toContain("No federal admissions figures for fall");
    expect(renderToStaticMarkup(<DataQualityBody snapshot={snap} year={noFederal!} />)).not.toContain(
      `/data-quality/csv/federal/${noFederal!.cds_year}`,
    );
  });

  it("a format row with no published reports shows dashes for its field counts", () => {
    at(OPEN);
    const snap = loadLatestSnapshot();
    const found = snap.years.flatMap((y) => y.rows.filter((r) => r.status.published === 0).map((r) => ({ y, r })))[0];
    expect(found).toBeDefined();
    const html = renderToStaticMarkup(<DataQualityBody snapshot={snap} year={found.y} />);
    const row = html.match(new RegExp(`<tr[^>]*><th[^>]*>${found.r.label}</th>.*?</tr>`))![0];
    expect(row.match(/>–</g)).toHaveLength(2);
  });

  // The sample notes sit behind count windows tied to the 2026-11-25 numbers, so this one test is pinned to that file.
  it("the two hand-check sample notes render for the 2026-11-25 snapshot", () => {
    at(OPEN);
    const json = JSON.parse(fs.readFileSync(path.join(SNAPSHOT_DIR, "2026-11-25.json"), "utf8"));
    const snap = selectSnapshot([{ name: "2026-11-25.json", json }]);
    const aid = snap.years.filter((y) => aidCantCheckNote(y));
    const differs = snap.years.filter((y) => federalDiffersNote(y, snap));
    expect(aid.map((y) => y.cds_year)).toEqual(["2023-24"]);
    expect(differs.map((y) => y.cds_year)).toEqual(["2023-24", "2024-25"]);
    expect(renderToStaticMarkup(<DataQualityBody snapshot={snap} year={aid[0]} />)).toContain('id="dq-note-aid-sample"');
    for (const y of differs) {
      expect(renderToStaticMarkup(<DataQualityBody snapshot={snap} year={y} />)).toContain('id="dq-differs-sample"');
    }
  });
});

describe("gate: the real snapshot loader", () => {
  it("throws on a directory with only a README, in both gate states", () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "dq-snap-"));
    try {
      fs.writeFileSync(path.join(dir, "README.md"), "not a snapshot");
      for (const when of [CLOSED, OPEN]) {
        at(when);
        expect(() => loadLatestSnapshot(dir)).toThrow(/no snapshot/);
      }
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });

  it("throws when the directory does not exist, in both gate states", () => {
    const parent = fs.mkdtempSync(path.join(os.tmpdir(), "dq-snap-"));
    try {
      for (const when of [CLOSED, OPEN]) {
        at(when);
        expect(() => loadLatestSnapshot(path.join(parent, "absent"))).toThrow(/no snapshot/);
      }
    } finally {
      fs.rmSync(parent, { recursive: true, force: true });
    }
  });

  it("loads the newest committed snapshot from the real directory in both states", () => {
    const files = fs
      .readdirSync(SNAPSHOT_DIR)
      .filter((n) => n.endsWith(".json"))
      .map((n) => JSON.parse(fs.readFileSync(path.join(SNAPSHOT_DIR, n), "utf8")) as { snapshot_of: string });
    const newest = files.map((f) => f.snapshot_of).sort((x, y) => Date.parse(y) - Date.parse(x))[0];
    for (const when of [CLOSED, OPEN]) {
      at(when);
      const snap = loadLatestSnapshot();
      expect(snap.snapshot_of).toBe(newest);
      expect(snap.public_format).toBe(4);
      expect(snap.scoreboard_run).toMatch(/^scoreboard-\d{8}T\d{6}Z\.json$/);
    }
  });

  it("pins the provenance of the 2026-11-25 snapshot", () => {
    const first = JSON.parse(fs.readFileSync(path.join(SNAPSHOT_DIR, "2026-11-25.json"), "utf8"));
    expect(first.scoreboard_run).toBe("scoreboard-20261125T140926Z.json");
    expect(first.renewal.both).toBe(373);
    expect(first.renewal.previous).toBe(498);
  });

  it("pins the committed snapshot's size of federal differences per year", () => {
    const first = JSON.parse(fs.readFileSync(path.join(SNAPSHOT_DIR, "2026-11-25.json"), "utf8"));
    const split = Object.fromEntries(
      first.years.map((y: { cds_year: string; total: { federal: Record<string, number> } }) => [
        y.cds_year,
        [y.total.federal.differs, y.total.federal.differs_2_to_10pct, y.total.federal.differs_over_10pct],
      ]),
    );
    // [differs, over 2% to 10%, over 10%], from scoreboard-20261125T140926Z.json. Pinned in two parts so a balanced
    // transcription error (one part up, the other down) fails here even though the arithmetic checks still pass.
    expect(split).toEqual({ "2023-24": [116, 70, 46], "2024-25": [120, 61, 59], "2025-26": [0, 0, 0] });
  });

  it("pins the committed snapshot's sections per year (reports, then section, questions, fields stored, usable answers)", () => {
    const first = JSON.parse(fs.readFileSync(path.join(SNAPSHOT_DIR, "2026-11-25.json"), "utf8"));
    const got = Object.fromEntries(
      first.years.map((y: { cds_year: string; sections: { reports: number; rows: { section: string; questions: number; stored_median: number; usable_median: number }[] } }) => [
        y.cds_year,
        [y.sections.reports, y.sections.rows.map((r) => [r.section, r.questions, r.stored_median, r.usable_median])],
      ]),
    );
    // From scoreboard-20261125T140926Z.json. Pinned for every year so a balanced transcription error fails here.
    expect(got).toEqual({
      "2023-24": [366, [["A", 51, 6, 6], ["B", 196, 143, 143], ["C", 274, 112, 112], ["D", 70, 15, 14], ["E", 32, 0, 0], ["F", 60, 16, 16], ["G", 47, 20, 20], ["H", 154, 52, 52], ["I", 49, 31, 31], ["J", 120, 27, 27]]],
      "2024-25": [491, [["A", 51, 11, 11], ["B", 219, 158, 156], ["C", 278, 123, 122], ["D", 73, 27, 25], ["E", 32, 19, 19], ["F", 60, 35, 35], ["G", 47, 23, 22], ["H", 154, 92, 91], ["I", 49, 41, 41], ["J", 120, 26, 26]]],
      "2025-26": [423, [["A", 63, 26, 23], ["B", 204, 152, 152], ["C", 278, 142, 141], ["D", 88, 27, 23], ["E", 34, 21, 21], ["F", 58, 37, 37], ["G", 46, 24, 23], ["H", 165, 108, 107], ["I", 49, 42, 42], ["J", 120, 27, 27]]],
    });
  });

  it("gives each committed year the question counts of its schema file, section by section", () => {
    const first = JSON.parse(fs.readFileSync(path.join(SNAPSHOT_DIR, "2026-11-25.json"), "utf8"));
    for (const y of first.years as { cds_year: string; sections: { rows: { section: string; questions: number }[] } }[]) {
      const schema = JSON.parse(fs.readFileSync(path.join(SNAPSHOT_DIR, "../../../../schemas", `cds_schema_${y.cds_year.replace("-", "_")}.json`), "utf8"));
      const counts: Record<string, number> = {};
      for (const f of schema.fields as { question_number: string }[]) {
        const letter = f.question_number.split(".")[0];
        counts[letter] = (counts[letter] ?? 0) + 1;
      }
      expect(Object.fromEntries(y.sections.rows.map((r) => [r.section, r.questions])), y.cds_year).toEqual(counts);
    }
  });

  it("pins the committed snapshot's enrollment and tuition checks per year", () => {
    const first = JSON.parse(fs.readFileSync(path.join(SNAPSHOT_DIR, "2026-11-25.json"), "utf8"));
    const got = Object.fromEntries(
      first.years.map((y: { cds_year: string; total: { checks: Record<string, Record<string, number>> }; federal_checks: Record<string, Record<string, unknown>> }) => [
        y.cds_year,
        Object.fromEntries(["enrollment", "tuition"].map((n) => [n, [y.federal_checks[n].loaded, y.federal_checks[n].data_year, ...Object.values(y.total.checks[n])]])),
      ]),
    );
    // [loaded, IPEDS year, reports, matches, no value, differs, over 2% to 10%, over 10%], from scoreboard-20261125T140926Z.json.
    expect(got).toEqual({
      "2023-24": { enrollment: [true, 2023, 431, 317, 82, 32, 21, 11], tuition: [true, 2024, 430, 201, 117, 112, 57, 55] },
      "2024-25": { enrollment: [true, 2024, 490, 378, 69, 43, 24, 19], tuition: [false, 2025, 0, 0, 0, 0, 0, 0] },
      "2025-26": { enrollment: [false, 2025, 0, 0, 0, 0, 0, 0], tuition: [false, 2026, 0, 0, 0, 0, 0, 0] },
    });
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
        expect(loadLatestSnapshot(dir).snapshot_of).toBe("2026-11-24T12:25:03Z");
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

  it("fails on invalid JSON and an unknown public_format in both gate states", () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), "dq-snap-"));
    try {
      for (const when of [CLOSED, OPEN]) {
        at(when);
        fs.writeFileSync(path.join(dir, "bad.json"), "{nope");
        expect(() => loadLatestSnapshot(dir)).toThrow(/not valid JSON/);
        fs.writeFileSync(path.join(dir, "bad.json"), JSON.stringify({ ...FIXTURE_SNAPSHOT, public_format: 9 }));
        expect(() => loadLatestSnapshot(dir)).toThrow(/public_format/);
      }
    } finally {
      fs.rmSync(dir, { recursive: true, force: true });
    }
  });
});
