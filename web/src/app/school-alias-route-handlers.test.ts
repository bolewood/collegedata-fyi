import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  fetchCanonicalSchoolId: vi.fn(),
  fetchSchoolDocuments: vi.fn(),
  fetchExtract: vi.fn(),
  getSchoolFacts: vi.fn(),
  getSchoolSources: vi.fn(),
  fetchSpreadsheetInput: vi.fn(),
  notFoundResponse: vi.fn(),
  buildCdsCsv: vi.fn(),
  buildCdsWorkbook: vi.fn(),
  spreadsheetFilename: vi.fn(),
}));

vi.mock("@/lib/queries", () => ({
  fetchCanonicalSchoolId: mocks.fetchCanonicalSchoolId,
  fetchSchoolDocuments: mocks.fetchSchoolDocuments,
  fetchExtract: mocks.fetchExtract,
}));

vi.mock("@/lib/public-data", () => ({
  getSchoolFacts: mocks.getSchoolFacts,
  getSchoolSources: mocks.getSchoolSources,
}));

vi.mock("@/lib/spreadsheet-source", () => ({
  fetchSpreadsheetInput: mocks.fetchSpreadsheetInput,
  notFoundResponse: mocks.notFoundResponse,
  SPREADSHEET_CACHE_CONTROL: "public, max-age=3600",
}));

vi.mock("@/lib/spreadsheet", () => ({
  buildCdsCsv: mocks.buildCdsCsv,
  buildCdsWorkbook: mocks.buildCdsWorkbook,
  spreadsheetFilename: mocks.spreadsheetFilename,
}));

import { GET as getFlatFacts } from "./api/facts/[school_id]/route";
import { GET as getSchoolFacts } from "./api/schools/[school_id]/facts/route";
import { GET as getSchoolSources } from "./api/schools/[school_id]/sources/route";
import { GET as getCsv } from "./schools/[school_id]/[year]/cds.csv/route";
import { GET as getXlsx } from "./schools/[school_id]/[year]/cds.xlsx/route";

const schoolParams = { params: Promise.resolve({ school_id: "tufts-university" }) };
const yearParams = {
  params: Promise.resolve({ school_id: "tufts-university", year: "2024-25" }),
};

describe("retired school alias route handlers", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.fetchCanonicalSchoolId.mockResolvedValue("tufts");
    mocks.fetchSchoolDocuments.mockResolvedValue([]);
    mocks.getSchoolFacts.mockResolvedValue(null);
    mocks.getSchoolSources.mockResolvedValue(null);
    mocks.fetchSpreadsheetInput.mockResolvedValue(null);
    mocks.notFoundResponse.mockImplementation(
      (schoolId: string, year: string) =>
        Response.json({ school_id: schoolId, year }, { status: 404 }),
    );
  });

  it("redirects the flat facts endpoint and preserves its query string", async () => {
    const response = await getFlatFacts(
      new Request("https://www.collegedata.fyi/api/facts/tufts-university?format=flat"),
      schoolParams,
    );

    expect(response.status).toBe(308);
    expect(response.headers.get("location")).toBe(
      "https://www.collegedata.fyi/api/facts/tufts?format=flat",
    );
  });

  it("redirects the public facts endpoint with category and field filters", async () => {
    const response = await getSchoolFacts(
      new Request(
        "https://www.collegedata.fyi/api/schools/tufts-university/facts?categories=admissions&fields=C.116",
      ),
      schoolParams,
    );

    expect(response.status).toBe(308);
    expect(response.headers.get("location")).toBe(
      "https://www.collegedata.fyi/api/schools/tufts/facts?categories=admissions&fields=C.116",
    );
  });

  it("redirects the source ledger endpoint", async () => {
    const response = await getSchoolSources(
      new Request(
        "https://www.collegedata.fyi/api/schools/tufts-university/sources?format=json",
      ),
      schoolParams,
    );

    expect(response.status).toBe(308);
    expect(response.headers.get("location")).toBe(
      "https://www.collegedata.fyi/api/schools/tufts/sources?format=json",
    );
  });

  it("redirects the CSV export while preserving year and query parameters", async () => {
    const response = await getCsv(
      new Request(
        "https://www.collegedata.fyi/schools/tufts-university/2024-25/cds.csv?download=1",
      ),
      yearParams,
    );

    expect(response.status).toBe(308);
    expect(response.headers.get("location")).toBe(
      "https://www.collegedata.fyi/schools/tufts/2024-25/cds.csv?download=1",
    );
  });

  it("redirects the XLSX export while preserving year and query parameters", async () => {
    const response = await getXlsx(
      new Request(
        "https://www.collegedata.fyi/schools/tufts-university/2024-25/cds.xlsx?download=1",
      ),
      yearParams,
    );

    expect(response.status).toBe(308);
    expect(response.headers.get("location")).toBe(
      "https://www.collegedata.fyi/schools/tufts/2024-25/cds.xlsx?download=1",
    );
  });

  it("resolves the alias before stale direct-route data can return a 200", async () => {
    mocks.fetchSchoolDocuments.mockResolvedValue([
      {
        document_id: "stale-document",
        extraction_status: "extracted",
        school_id: "tufts-university",
      },
    ]);
    mocks.getSchoolFacts.mockResolvedValue({ school_id: "tufts-university" });
    mocks.getSchoolSources.mockResolvedValue({ school_id: "tufts-university" });
    mocks.fetchSpreadsheetInput.mockResolvedValue({ schoolId: "tufts-university" });

    const responses = await Promise.all([
      getFlatFacts(
        new Request("https://www.collegedata.fyi/api/facts/tufts-university"),
        schoolParams,
      ),
      getSchoolFacts(
        new Request("https://www.collegedata.fyi/api/schools/tufts-university/facts"),
        schoolParams,
      ),
      getSchoolSources(
        new Request("https://www.collegedata.fyi/api/schools/tufts-university/sources"),
        schoolParams,
      ),
      getCsv(
        new Request(
          "https://www.collegedata.fyi/schools/tufts-university/2024-25/cds.csv",
        ),
        yearParams,
      ),
      getXlsx(
        new Request(
          "https://www.collegedata.fyi/schools/tufts-university/2024-25/cds.xlsx",
        ),
        yearParams,
      ),
    ]);

    expect(responses.map((response) => response.status)).toEqual([
      308, 308, 308, 308, 308,
    ]);
    expect(mocks.fetchSchoolDocuments).not.toHaveBeenCalled();
    expect(mocks.getSchoolFacts).not.toHaveBeenCalled();
    expect(mocks.getSchoolSources).not.toHaveBeenCalled();
    expect(mocks.fetchSpreadsheetInput).not.toHaveBeenCalled();
  });

  it("keeps the existing 404 when an alias cannot be resolved", async () => {
    mocks.fetchCanonicalSchoolId.mockResolvedValue(null);

    const response = await getSchoolSources(
      new Request("https://www.collegedata.fyi/api/schools/missing/sources"),
      { params: Promise.resolve({ school_id: "missing" }) },
    );

    expect(response.status).toBe(404);
    await expect(response.json()).resolves.toMatchObject({
      error: "school_not_found",
      school_id: "missing",
    });
  });

  it("keeps a canonical slug on the direct API path after alias lookup", async () => {
    mocks.getSchoolFacts.mockResolvedValue({ school_id: "tufts", facts: [] });

    const response = await getSchoolFacts(
      new Request("https://www.collegedata.fyi/api/schools/tufts/facts"),
      { params: Promise.resolve({ school_id: "tufts" }) },
    );

    expect(response.status).toBe(200);
    expect(mocks.fetchCanonicalSchoolId).toHaveBeenCalledWith("tufts");
    expect(mocks.getSchoolFacts).toHaveBeenCalledWith("tufts", {
      categories: undefined,
      fields: undefined,
    });
  });
});
