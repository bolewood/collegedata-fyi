import { afterEach, describe, expect, it, vi } from "vitest";
import { DATA_LICENSE_LINK_HEADER } from "@/lib/data-license";
import { DATA_QUALITY_LAUNCH_DATE } from "@/lib/data-quality";
import type { InstitutionCoverage } from "@/lib/types";

const mocks = vi.hoisted(() => ({ fetchCoverageRows: vi.fn() }));
vi.mock("@/lib/queries", () => ({ fetchCoverageRows: mocks.fetchCoverageRows }));

import { GET } from "./route";

const LAUNCH_MS = Date.parse(`${DATA_QUALITY_LAUNCH_DATE}T00:00:00Z`);

function row(over: Partial<InstitutionCoverage> & { school_id: string; school_name: string }): InstitutionCoverage {
  return {
    ipeds_id: "100000",
    city: null,
    state: "NY",
    website_url: null,
    undergraduate_enrollment: 1000,
    coverage_status: "no_public_cds_found",
    coverage_label: "",
    coverage_summary: "",
    latest_available_cds_year: null,
    latest_found_cds_year: null,
    last_checked_at: "2026-11-20T00:00:00Z",
    can_submit_source: false,
    ...over,
  };
}

const ROWS = [
  row({ school_id: "a", school_name: "Alpha College", undergraduate_enrollment: 500 }),
  row({ school_id: "b", school_name: 'St. John\'s, "Great Books" College', undergraduate_enrollment: 9000, state: "NM" }),
  row({ school_id: "c", school_name: "Universidad de Río Piedras", undergraduate_enrollment: null, state: "PR" }),
  row({ school_id: "d", school_name: "Delta Tech", undergraduate_enrollment: 2000, coverage_status: "cds_available_current", latest_available_cds_year: "2025-26", latest_found_cds_year: "2025-26" }),
];

function open() {
  vi.useFakeTimers();
  vi.setSystemTime(LAUNCH_MS);
  mocks.fetchCoverageRows.mockResolvedValue(ROWS);
}

async function get(qs = "") {
  return GET(new Request(`https://collegedata.fyi/coverage.csv${qs}`));
}

/** Minimal RFC 4180 reader, enough to check the file round-trips. */
function parse(text: string): string[][] {
  const out: string[][] = [];
  let cell = "", rowCells: string[] = [], quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (quoted) {
      if (ch === '"' && text[i + 1] === '"') { cell += '"'; i++; }
      else if (ch === '"') quoted = false;
      else cell += ch;
    } else if (ch === '"') quoted = true;
    else if (ch === ",") { rowCells.push(cell); cell = ""; }
    else if (ch === "\r") { /* CRLF */ }
    else if (ch === "\n") { rowCells.push(cell); out.push(rowCells); rowCells = []; cell = ""; }
    else cell += ch;
  }
  return out;
}

/** The body as sent: Response.text() would drop the BOM. */
const raw = async (res: Response) => new TextDecoder("utf-8", { ignoreBOM: true }).decode(await res.arrayBuffer());

afterEach(() => {
  vi.useRealTimers();
  mocks.fetchCoverageRows.mockReset();
});

describe("/coverage.csv", () => {
  it("is a 404 before the launch date and reads no rows", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(LAUNCH_MS - 1000);
    const res = await get();
    expect(res.status).toBe(404);
    expect(mocks.fetchCoverageRows).not.toHaveBeenCalled();
  });

  it("sends the license Link header, an attachment filename, and a BOM", async () => {
    open();
    const res = await get("?all=1");
    expect(res.status).toBe(200);
    expect(res.headers.get("Link")).toBe(DATA_LICENSE_LINK_HEADER);
    expect(res.headers.get("Content-Type")).toBe("text/csv; charset=utf-8");
    expect(res.headers.get("Content-Disposition")).toMatch(/^attachment; filename="collegedata-coverage-all-colleges-\d{4}-\d{2}-\d{2}\.csv"$/);
    expect((await raw(res)).charCodeAt(0)).toBe(0xfeff);
  });

  it("has the header on row 1 and no comment lines", async () => {
    open();
    const text = (await raw(await get("?all=1"))).slice(1);
    expect(text.startsWith("ipeds_id,school_id,school_name,")).toBe(true);
    expect(text.split("\r\n").some((l) => l.startsWith("#"))).toBe(false);
  });

  it("has exactly the rows of the filtered view", async () => {
    open();
    // Default view = missing only: everything but "cds_available_current".
    const view = parse((await raw(await get())).slice(1));
    expect(view).toHaveLength(1 + 3);
    const ny = parse((await raw(await get("?all=1&state=NM"))).slice(1));
    expect(ny).toHaveLength(1 + 1);
    const all = parse((await raw(await get("?all=1"))).slice(1));
    expect(all).toHaveLength(1 + 4);
  });

  it("applies the sort and dir it is given", async () => {
    open();
    const ids = async (qs: string) => parse((await raw(await get(qs))).slice(1)).slice(1).map((r) => r[1]);
    expect(await ids("?all=1&sort=enrollment&dir=desc")).toEqual(["b", "d", "a", "c"]);
    expect(await ids("?all=1&sort=enrollment&dir=asc")).toEqual(["a", "d", "b", "c"]);
    expect(await ids("?all=1")).toEqual(["a", "d", "b", "c"].sort((x, y) => ROWS.find((r) => r.school_id === x)!.school_name.localeCompare(ROWS.find((r) => r.school_id === y)!.school_name)));
  });

  it("round-trips a name with a comma, a quote and non-ASCII letters", async () => {
    open();
    const rows = parse((await raw(await get("?all=1"))).slice(1));
    const names = rows.slice(1).map((r) => r[2]);
    expect(names).toContain('St. John\'s, "Great Books" College');
    expect(names).toContain("Universidad de Río Piedras");
    expect(rows.every((r) => r.length === 9)).toBe(true);
  });
});
