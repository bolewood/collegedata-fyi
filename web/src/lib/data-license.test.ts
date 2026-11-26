import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it, vi } from "vitest";

vi.mock("./supabase", () => ({ supabase: {}, STORAGE_BASE_URL: "https://example.test/storage" }));
vi.mock("./supabase-friendly-api", () => ({ friendlyApiSupabase: {} }));
import {
  DATA_ATTRIBUTION,
  DATA_LICENSE_EFFECTIVE_DATE,
  DATA_LICENSE_LINK_HEADER,
  DATA_LICENSE_SCOPE,
  DATA_LICENSE_URL,
  dataLicenseFields,
} from "./data-license";
import { setLaunchGate } from "./__fixtures__/data-quality-gate";
import { TABLE_TITLES } from "./data-quality";

const repo = (path: string) => readFileSync(resolve(__dirname, "../../..", path), "utf8");

describe("data license wording", () => {
  it("pins the credit line and effective date to DATA_LICENSE.md", () => {
    const doc = repo("DATA_LICENSE.md");
    expect(doc).toContain(`**Effective date:** ${DATA_LICENSE_EFFECTIVE_DATE}`);
    expect(doc).toContain(DATA_ATTRIBUTION);
  });

  it("puts the license link in the credit line, as CC BY requires", () => {
    expect(DATA_ATTRIBUTION).toContain(DATA_LICENSE_URL);
    expect(DATA_LICENSE_LINK_HEADER).toBe(`<${DATA_LICENSE_URL}>; rel="license"`);
  });

  it("keeps the CLI and the snapshot builder in step with the web constants", () => {
    expect(repo("packages/cli/bin/collegedata.js")).toContain(JSON.stringify(DATA_ATTRIBUTION));
    const builder = repo("tools/snapshots/build_public_snapshots.mjs");
    expect(builder).toContain(JSON.stringify(DATA_ATTRIBUTION));
    expect(builder).toContain(JSON.stringify(DATA_LICENSE_SCOPE));
    expect(builder).toContain(`applies_to: "${dataLicenseFields().data_license.applies_to}"`);
    expect(builder).toContain(`license: "${dataLicenseFields().data_license.license}"`);
    expect(builder).toContain(`license_url: "${DATA_LICENSE_URL}"`);
  });

  it("says what the license does not cover", () => {
    expect(DATA_LICENSE_SCOPE).toContain("Does not cover the schools' Common Data Set documents");
    expect(DATA_LICENSE_SCOPE).toContain("federal IPEDS, College Scorecard and FSA facts");
  });
});

describe("machine-readable license surfaces", () => {
  it("declares CC BY 4.0 in OpenAPI info with name and SPDX identifier only", async () => {
    const { GET } = await import("../app/openapi.json/route");
    const spec = await (await GET()).json();
    expect(spec.info.license).toEqual({ name: "CC BY 4.0", identifier: "CC-BY-4.0" });
    expect(spec.info.description).toContain(DATA_ATTRIBUTION);
    expect(spec.info.description).toContain("The code is MIT-licensed.");
  });

  it("asks MCP clients to carry the credit line", async () => {
    const { MCP_INSTRUCTIONS } = await import("./mcp/tools");
    expect(MCP_INSTRUCTIONS).toContain(DATA_ATTRIBUTION);
  });

  // PRD 040: the Data quality CSV and reports routes are licensed surfaces once launched.
  it("carries the license Link header on every Data quality CSV table the build serves, once launched", async () => {
    setLaunchGate(true);
    const route = await import("../app/data-quality/csv/[table]/[year]/route");
    const params = route.generateStaticParams();
    expect(params.length).toBeGreaterThan(0);
    // Every table the route can serve appears, so a seventh table (or a dropped one) is noticed here.
    expect([...new Set(params.map((p) => p.table))].sort()).toEqual(Object.keys(TABLE_TITLES).sort());
    for (const { table, year } of params) {
      const res = await route.GET(new Request("https://collegedata.fyi/x"), { params: Promise.resolve({ table, year }) });
      expect(res.status, `${table} ${year}`).toBe(200);
      expect(res.headers.get("Link"), `${table} ${year}`).toBe(DATA_LICENSE_LINK_HEADER);
    }
  });

  it("carries it on the Data quality reports file once launched, and serves nothing before", async () => {
    const route = await import("../app/data-quality/reports/[date]/route");
    setLaunchGate(true);
    const params = route.generateStaticParams();
    expect(params).toHaveLength(1);
    const res = await route.GET(new Request("https://collegedata.fyi/x"), { params: Promise.resolve(params[0]) });
    expect(res.status).toBe(200);
    expect(res.headers.get("Link")).toBe(DATA_LICENSE_LINK_HEADER);
    setLaunchGate(false);
    expect(route.generateStaticParams()).toEqual([]);
    expect((await route.GET(new Request("https://collegedata.fyi/x"), { params: Promise.resolve(params[0]) })).status).toBe(404);
  });
});
