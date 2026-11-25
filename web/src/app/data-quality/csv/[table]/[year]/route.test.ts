import { afterEach, describe, expect, it, vi } from "vitest";
import { FIXTURE_SNAPSHOT } from "@/lib/__fixtures__/data-quality-snapshot";
import { DATA_LICENSE_LINK_HEADER } from "@/lib/data-license";
import { DATA_QUALITY_LAUNCH_DATE, buildQualityCsv } from "@/lib/data-quality";

const mocks = vi.hoisted(() => ({ loadLatestSnapshot: vi.fn() }));
vi.mock("@/lib/data-quality-snapshots", () => ({ loadLatestSnapshot: mocks.loadLatestSnapshot }));

import { GET, generateStaticParams } from "./route";

const LAUNCH_MS = Date.parse(`${DATA_QUALITY_LAUNCH_DATE}T00:00:00Z`);

function open() {
  vi.useFakeTimers();
  vi.setSystemTime(LAUNCH_MS);
  mocks.loadLatestSnapshot.mockReturnValue(FIXTURE_SNAPSHOT);
}

const get = (table: string, year: string) =>
  GET(new Request("https://collegedata.fyi/x"), { params: Promise.resolve({ table, year }) });

/** The body as sent: Response.text() would drop the BOM. */
const raw = async (res: Response) => new TextDecoder("utf-8", { ignoreBOM: true }).decode(await res.arrayBuffer());

afterEach(() => {
  vi.useRealTimers();
  mocks.loadLatestSnapshot.mockReset();
});

describe("/data-quality/csv/[table]/[year]", () => {
  it("is a 404 before the launch date, and builds no static pages", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(LAUNCH_MS - 1000);
    mocks.loadLatestSnapshot.mockReturnValue(FIXTURE_SNAPSHOT);
    expect((await get("reports", "2024-25")).status).toBe(404);
    expect(generateStaticParams()).toEqual([]);
  });

  it("serves the table with the Link header, filename and a BOM, header on row 1", async () => {
    open();
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
    expect(text.slice(1)).toBe(buildQualityCsv("totals", year, FIXTURE_SNAPSHOT));
  });

  it("has one line per format plus the total", async () => {
    open();
    const year = FIXTURE_SNAPSHOT.years.find((y) => y.cds_year === "2023-24")!;
    const lines = (await raw(await get("reports", "2023-24"))).split("\r\n").filter(Boolean);
    expect(lines).toHaveLength(1 + year.rows.length + 1);
  });

  it("is a 404 for an unknown table, an unknown year, or no snapshot", async () => {
    open();
    expect((await get("nope", "2024-25")).status).toBe(404);
    expect((await get("constructor", "2024-25")).status).toBe(404);
    expect((await get("reports", "1999-00")).status).toBe(404);
    mocks.loadLatestSnapshot.mockReturnValue(null);
    expect((await get("reports", "2024-25")).status).toBe(404);
  });

  it("lists every table and year for the static build once launched", () => {
    open();
    expect(generateStaticParams()).toHaveLength(3 * FIXTURE_SNAPSHOT.years.length);
  });
});
