import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FIXTURE_SNAPSHOT } from "@/lib/__fixtures__/data-quality-snapshot";
import { DATA_LICENSE_LINK_HEADER } from "@/lib/data-license";
import { DATA_QUALITY_LAUNCH_DATE, TABLE_TITLES, buildQualityCsv, qualityCsvPath, type QualityTableId } from "@/lib/data-quality";

// The real loader, pointed at a temp directory instead of src/data/data-quality.
const dirs = vi.hoisted(() => ({ current: "" }));
vi.mock("@/lib/data-quality-snapshots", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/lib/data-quality-snapshots")>();
  return { ...real, loadLatestSnapshot: () => real.loadLatestSnapshot(dirs.current) };
});

import { GET, generateStaticParams } from "./route";

const LAUNCH_MS = Date.parse(`${DATA_QUALITY_LAUNCH_DATE}T00:00:00Z`);

beforeEach(() => {
  dirs.current = fs.mkdtempSync(path.join(os.tmpdir(), "dq-snap-"));
});

afterEach(() => {
  vi.useRealTimers();
  fs.rmSync(dirs.current, { recursive: true, force: true });
});

function writeSnapshot() {
  fs.writeFileSync(path.join(dirs.current, "2026-11-24.json"), JSON.stringify(FIXTURE_SNAPSHOT));
}

function at(ms: number) {
  vi.useFakeTimers();
  vi.setSystemTime(ms);
}

const open = () => at(LAUNCH_MS);

const get = (table: string, year: string) =>
  GET(new Request("https://collegedata.fyi/x"), { params: Promise.resolve({ table, year }) });

/** The body as sent: Response.text() would drop the BOM. */
const raw = async (res: Response) => new TextDecoder("utf-8", { ignoreBOM: true }).decode(await res.arrayBuffer());

describe("/data-quality/csv/[table]/[year]", () => {
  it("is a 404 before the launch date, builds no static pages, and never reads the directory", async () => {
    at(LAUNCH_MS - 1000);
    writeSnapshot();
    fs.rmSync(dirs.current, { recursive: true });
    expect((await get("reports", "2024-25")).status).toBe(404);
    expect(generateStaticParams()).toEqual([]);
  });

  it("serves the table with the Link header, filename and a BOM, header on row 1", async () => {
    open();
    writeSnapshot();
    const res = await get("totals", "2024-25");
    expect(res.status).toBe(200);
    expect(res.headers.get("Link")).toBe(DATA_LICENSE_LINK_HEADER);
    expect(res.headers.get("Content-Type")).toBe("text/csv; charset=utf-8");
    expect(res.headers.get("Content-Disposition")).toBe(
      'attachment; filename="collegedata-data-quality-totals-add-up-2024-25-2026-11-24.csv"',
    );
    const text = await raw(res);
    expect(text.charCodeAt(0)).toBe(0xfeff);
    expect(text.slice(1).startsWith("format,reports,B1_adds_up,")).toBe(true);
    expect(text).not.toContain("#");
    const year = FIXTURE_SNAPSHOT.years.find((y) => y.cds_year === "2024-25")!;
    expect(text.slice(1)).toBe(buildQualityCsv("totals", year));
  });

  it("has one line per format plus the total", async () => {
    open();
    writeSnapshot();
    const year = FIXTURE_SNAPSHOT.years.find((y) => y.cds_year === "2023-24")!;
    const lines = (await raw(await get("reports", "2023-24"))).split("\r\n").filter(Boolean);
    expect(lines).toHaveLength(1 + year.rows.length + 1);
  });

  it("is a 404 for an unknown table or year", async () => {
    open();
    writeSnapshot();
    expect((await get("nope", "2024-25")).status).toBe(404);
    expect((await get("constructor", "2024-25")).status).toBe(404);
    expect((await get("reports", "1999-00")).status).toBe(404);
  });

  it("throws, by design, when launched with no snapshot (the build fails rather than ship an empty page)", async () => {
    open();
    await expect(get("reports", "2024-25")).rejects.toThrow(/no snapshot/);
    expect(() => generateStaticParams()).toThrow(/no snapshot/);
  });

  it("lists exactly the unique (table, year) pairs once launched", () => {
    open();
    writeSnapshot();
    const pairs = generateStaticParams().map((p) => `${p.table}/${p.year}`).sort();
    const expected = (Object.keys(TABLE_TITLES) as QualityTableId[])
      .flatMap((t) => FIXTURE_SNAPSHOT.years.map((y) => `${t}/${y.cds_year}`))
      .sort();
    expect(pairs).toEqual(expected);
    expect(new Set(pairs).size).toBe(pairs.length);
  });

  it("answers for the path the page links to", async () => {
    open();
    writeSnapshot();
    for (const table of Object.keys(TABLE_TITLES) as QualityTableId[]) {
      const [, , , t, y] = qualityCsvPath(table, "2025-26").split("/");
      expect(qualityCsvPath(table, "2025-26")).toBe(`/data-quality/csv/${t}/${y}`);
      expect(generateStaticParams()).toContainEqual({ table: t, year: y });
      const res = await get(t, y);
      expect(res.status).toBe(200);
      expect(res.headers.get("Content-Disposition")).toContain(`-${y}-`);
    }
  });
});
