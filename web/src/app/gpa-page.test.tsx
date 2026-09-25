import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { getSortedRoutes } from "next/dist/shared/lib/router/utils/sorted-routes";
import { NextRequest } from "next/server";

const mocks = vi.hoisted(() => ({
  fetchCanonicalSchoolId: vi.fn(),
  fetchSchoolDocuments: vi.fn(),
  fetchSchoolYearFacts: vi.fn(),
  fetchExtract: vi.fn(),
  fetchSchoolBrandColors: vi.fn(),
  permanentRedirect: vi.fn(),
  notFound: vi.fn(),
}));

vi.mock("@/lib/queries", () => ({
  fetchCanonicalSchoolId: mocks.fetchCanonicalSchoolId,
  fetchSchoolDocuments: mocks.fetchSchoolDocuments,
  fetchSchoolYearFacts: mocks.fetchSchoolYearFacts,
  fetchExtract: mocks.fetchExtract,
  fetchSchoolBrandColors: mocks.fetchSchoolBrandColors,
}));

vi.mock("next/navigation", () => ({
  permanentRedirect: mocks.permanentRedirect,
  notFound: mocks.notFound,
}));

import GpaPage, { generateMetadata } from "./schools/[school_id]/gpa/page";
import {
  GPA_INDEXABLE,
  GPA_SCHOOLS,
  GPA_GONE_PATHS,
  GPA_SUBMITTED_PATHS,
  gpaPageDecision,
  gpaPath,
  gpaSitemapEntries,
  isGpaSchool,
} from "@/lib/gpa-pilot";
import { fetchGpaPageServed } from "@/lib/acceptance-history-data";
import { buildGpaHistory } from "@/lib/c11-gpa";
import { proxy } from "@/proxy";

const redirectSentinel = new Error("NEXT_REDIRECT");
const notFoundSentinel = new Error("NEXT_NOT_FOUND");

function manifest(schoolId: string, name: string, years: string[]) {
  return years.map((year) => ({
    document_id: `${schoolId}-${year}`,
    school_id: schoolId,
    school_name: name,
    canonical_year: year,
    extraction_status: "extracted",
    data_quality_flag: null,
    sub_institutional: null,
    source_storage_path: `${schoolId}/${year}/file.pdf`,
    source_format: "pdf_flat",
  }));
}

function extractFor(documentId: string) {
  const bands = {
    "C.1101": { value: "74.2" },
    "C.1102": { value: "18.1" },
    "C.1103": { value: "5.4" },
    "C.1104": { value: "1.6" },
    "C.1105": { value: "0.5" },
    "C.1106": { value: "0.2" },
    "C.1107": { value: "0" },
    "C.1108": { value: "0" },
    "C.1109": { value: "0" },
    "C.1201": { value: documentId.endsWith("2025-26") ? "4.22" : "4.00" },
  };
  return {
    canonical: { producer: "tier4_docling", notes: { schema_version: "2024-25" } },
    fallback: null,
    mergedValues: bands,
  };
}

const params = (school_id: string) => ({ params: Promise.resolve({ school_id }) });

beforeEach(() => {
  vi.clearAllMocks();
  mocks.fetchCanonicalSchoolId.mockImplementation(async (id: string) => id);
  mocks.fetchSchoolDocuments.mockResolvedValue([]);
  mocks.fetchSchoolYearFacts.mockResolvedValue([]);
  mocks.fetchSchoolBrandColors.mockResolvedValue(null);
  mocks.fetchExtract.mockImplementation(async (documentId: string) => extractFor(documentId));
  mocks.permanentRedirect.mockImplementation(() => {
    throw redirectSentinel;
  });
  mocks.notFound.mockImplementation(() => {
    throw notFoundSentinel;
  });
});

describe("gpa route", () => {
  it("is a static segment that wins over the [year] route", () => {
    const dir = resolve(__dirname, "schools/[school_id]");
    expect(existsSync(resolve(dir, "gpa/page.tsx"))).toBe(true);
    const sorted = getSortedRoutes(["/schools/[school_id]/[year]", "/schools/[school_id]/gpa"]);
    expect(sorted[0]).toBe("/schools/[school_id]/gpa");
  });

  it("404s schools that are not on the allowlist without reading their data", async () => {
    await expect(GpaPage(params("yale"))).rejects.toBe(notFoundSentinel);
    expect(mocks.fetchSchoolDocuments).not.toHaveBeenCalled();
    const metadata = await generateMetadata(params("dartmouth"));
    expect(metadata.robots).toEqual({ index: false, follow: true });
  });

  it("keeps serving a submitted URL that no longer has three usable GPA years", async () => {
    mocks.fetchSchoolDocuments.mockResolvedValue(manifest("harvard", "Harvard University", ["2025-26", "2024-25"]));
    await expect(GpaPage(params("harvard"))).resolves.toBeTruthy();
  });

  it("serves an eligible allowlisted school as indexable with a self canonical", async () => {
    mocks.fetchSchoolDocuments.mockResolvedValue(
      manifest("harvard", "Harvard University", ["2025-26", "2024-25", "2023-24"]),
    );
    const metadata = await generateMetadata(params("harvard"));
    expect(metadata.title).toBe("Harvard University Average GPA: 4.22 for Fall 2025");
    expect(metadata.robots).toEqual({ index: true, follow: true });
    expect(metadata.alternates).toEqual({ canonical: "/schools/harvard/gpa" });
    await expect(GpaPage(params("harvard"))).resolves.toBeTruthy();
  });
});

describe("gpa gating", () => {
  it("indexes the pages and lists distinctive names first", () => {
    expect(GPA_INDEXABLE).toBe(true);
    expect(GPA_SCHOOLS).toEqual(["harvard", "princeton", "stanford"]);
    expect(isGpaSchool("harvard")).toBe(true);
    expect(isGpaSchool("yale")).toBe(false);
    expect(isGpaSchool("dartmouth")).toBe(false);
  });

  it("lists served pages in the sitemap", () => {
    expect(gpaSitemapEntries(["harvard", "yale"])).toEqual([
      {
        url: "https://www.collegedata.fyi/schools/harvard/gpa",
        changeFrequency: "monthly",
        priority: 0.6,
      },
    ]);
  });

  it("does not read extracts for schools off the allowlist", async () => {
    await expect(fetchGpaPageServed("yale")).resolves.toBe(false);
    expect(mocks.fetchSchoolDocuments).not.toHaveBeenCalled();
    mocks.fetchSchoolDocuments.mockResolvedValue(
      manifest("harvard", "Harvard University", ["2025-26", "2024-25", "2023-24"]),
    );
    await expect(fetchGpaPageServed("harvard")).resolves.toBe(true);
  });
});

describe("submitted GPA URLs never silently 404", () => {
  const empty = buildGpaHistory([]);

  it("every submitted URL is an allowlisted page or an explicit 410", () => {
    for (const path of GPA_SUBMITTED_PATHS) {
      const id = path.split("/")[2];
      const gone = GPA_GONE_PATHS.includes(path);
      expect(path).toBe(gpaPath(id));
      expect(gone || GPA_SCHOOLS.includes(id)).toBe(true);
      if (!gone) expect(gpaPageDecision(id, empty).kind).not.toBe("not-found");
    }
  });

  it("the proxy answers 410 only for retired URLs", () => {
    const event = { waitUntil: vi.fn() } as never;
    const res = proxy(new NextRequest("https://www.collegedata.fyi/schools/harvard/gpa"), event);
    expect(res.status).not.toBe(410);
  });
});
