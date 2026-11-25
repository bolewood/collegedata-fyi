import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";

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
import { DATA_QUALITY_LAUNCH_DATE } from "./data-quality";
import { loadLatestSnapshot } from "./data-quality-snapshots";

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

  // PRD 040: the Data quality CSV route is a licensed surface once launched.
  // Faked clock, so this passes on both sides of the launch date.
  it("carries the license Link header on the Data quality CSV once launched", async () => {
    vi.useFakeTimers();
    vi.setSystemTime(Date.parse(`${DATA_QUALITY_LAUNCH_DATE}T00:00:00Z`));
    const { GET } = await import("../app/data-quality/csv/[table]/[year]/route");
    const year = loadLatestSnapshot().years[0].cds_year;
    const res = await GET(new Request("https://collegedata.fyi/x"), { params: Promise.resolve({ table: "reports", year }) });
    expect(res.status).toBe(200);
    expect(res.headers.get("Link")).toBe(DATA_LICENSE_LINK_HEADER);
  });
});

afterEach(() => {
  vi.useRealTimers();
});
