import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { FIXTURE_SNAPSHOT } from "@/lib/__fixtures__/data-quality-snapshot";
import { DATA_LICENSE_LINK_HEADER } from "@/lib/data-license";
import { setLaunchGate } from "@/lib/__fixtures__/data-quality-gate";
import { SNAPSHOT_DIR } from "@/lib/data-quality-snapshots";
import { snapshotDay } from "@/lib/data-quality";

// The real loaders, pointed at a temp directory instead of src/data/data-quality.
const dirs = vi.hoisted(() => ({ current: "" }));
vi.mock("@/lib/data-quality-snapshots", async (importOriginal) => {
  const real = await importOriginal<typeof import("@/lib/data-quality-snapshots")>();
  return {
    ...real,
    loadLatestSnapshot: () => real.loadLatestSnapshot(dirs.current),
    loadReportsFor: (snapshot: Parameters<typeof real.loadReportsFor>[0]) => real.loadReportsFor(snapshot, dirs.current),
  };
});

import { GET, generateStaticParams } from "./route";

// The latest committed snapshot, copied to a temp directory with its reports file; nothing here names a date.
const realSnapshots = await vi.importActual<typeof import("@/lib/data-quality-snapshots")>("@/lib/data-quality-snapshots");
const LATEST = realSnapshots.loadLatestSnapshot();
const DAY = snapshotDay(LATEST);
const realFile = (rel: string) => fs.readFileSync(path.join(SNAPSHOT_DIR, rel.replace("DAY", DAY)), "utf8");

beforeEach(() => {
  dirs.current = fs.mkdtempSync(path.join(os.tmpdir(), "dq-reports-route-"));
});
afterEach(() => {
  fs.rmSync(dirs.current, { recursive: true, force: true });
});

/** The committed snapshot and its reports file, copied to the temp directory. */
function writeReal(withReports = true) {
  fs.writeFileSync(path.join(dirs.current, `${DAY}.json`), realFile("DAY.json"));
  if (withReports) {
    fs.mkdirSync(path.join(dirs.current, "reports"));
    fs.writeFileSync(path.join(dirs.current, "reports", `${DAY}.json`), realFile("reports/DAY.json"));
  }
}
const open = () => setLaunchGate(true);
const get = (date: string) => GET(new Request("https://collegedata.fyi/x"), { params: Promise.resolve({ date }) });

describe("/data-quality/reports/[date]", () => {
  it("is a 404 before the launch date, builds no static page, and never reads the directory", async () => {
    setLaunchGate(false);
    writeReal();
    fs.rmSync(dirs.current, { recursive: true });
    expect((await get(DAY)).status).toBe(404);
    expect(generateStaticParams()).toEqual([]);
  });

  it("serves the file for the latest snapshot's date with the Link header, once launched", async () => {
    open();
    writeReal();
    expect(generateStaticParams()).toEqual([{ date: DAY }]);
    const res = await get(DAY);
    expect(res.status).toBe(200);
    expect(res.headers.get("Content-Type")).toBe("application/json; charset=utf-8");
    expect(res.headers.get("Link")).toBe(DATA_LICENSE_LINK_HEADER);
    const body = await res.json();
    expect(body.snapshot_of).toBe(LATEST.snapshot_of);
    expect(Object.keys(body.years).sort()).toEqual(["2023-24", "2024-25", "2025-26"]);
  });

  it("is a 404 for another date, and for a snapshot with no reports file", async () => {
    open();
    writeReal();
    expect((await get("2000-01-01")).status).toBe(404);
    expect((await get("nope")).status).toBe(404);
    fs.rmSync(path.join(dirs.current, "reports"), { recursive: true });
    expect((await get(DAY)).status).toBe(404);
    expect(generateStaticParams()).toEqual([]);
  });

  it("fails the build, not the page, when the file disagrees with the snapshot", async () => {
    open();
    writeReal();
    const file = path.join(dirs.current, "reports", `${DAY}.json`);
    const broken = JSON.parse(fs.readFileSync(file, "utf8"));
    broken.years["2024-25"].pop();
    fs.writeFileSync(file, JSON.stringify(broken));
    expect(() => generateStaticParams()).toThrow(/disagrees with its snapshot/);
    await expect(get(DAY)).rejects.toThrow(/disagrees with its snapshot/);
  });

  it("has no use for the fixture snapshot: a snapshot is only ever served with its own file", () => {
    open();
    fs.writeFileSync(path.join(dirs.current, "2026-11-24.json"), JSON.stringify(FIXTURE_SNAPSHOT));
    expect(generateStaticParams()).toEqual([]);
  });
});
