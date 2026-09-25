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

import EarlyDecisionPage, { generateMetadata } from "./schools/[school_id]/early-decision/page";
import {
  EARLY_DECISION_INDEXABLE,
  EARLY_DECISION_SCHOOLS,
  EARLY_DECISION_GONE_PATHS,
  EARLY_DECISION_SUBMITTED_PATHS,
  earlyDecisionPageDecision,
  earlyDecisionPath,
  earlyDecisionSitemapEntries,
  isEarlyDecisionSchool,
} from "@/lib/early-decision-pilot";
import { earlyDecisionSitemap, fetchEarlyDecisionPageServed } from "@/lib/acceptance-history-data";
import { buildAcceptanceHistory } from "@/lib/acceptance-history";
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
  const year = documentId.slice(-7);
  const start = Number(year.slice(0, 4));
  const applied = 10000;
  const admitted = documentId.endsWith("2025-26") ? 500 : 800;
  const edApplied = 1000;
  const edAdmitted = 200;
  const c1 =
    start >= 2025
      ? { "C.116": { value: String(applied) }, "C.117": { value: String(admitted) } }
      : { "C.117": { value: String(applied) }, "C.118": { value: String(admitted) }, "C.119": { value: "200" } };
  const c21 =
    start >= 2025
      ? { "C.2110": { value: String(edApplied) }, "C.2111": { value: String(edAdmitted) } }
      : { "C.2106": { value: String(edApplied) }, "C.2107": { value: String(edAdmitted) } };
  const schema = start >= 2025 ? "2025-26" : start >= 2024 ? "2024-25" : "2023-24";
  return {
    canonical: {
      producer: "tier4_docling",
      notes: {
        schema_version: schema,
        markdown: `Please provide significant details about your early decision plan:
Applicants must state in writing that they will enroll if admitted.
## C22. Early action
No
`,
      },
    },
    fallback: null,
    mergedValues: { ...c1, ...c21 },
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

describe("early-decision route", () => {
  it("is a static segment that wins over the [year] route", () => {
    const dir = resolve(__dirname, "schools/[school_id]");
    expect(existsSync(resolve(dir, "early-decision/page.tsx"))).toBe(true);
    const sorted = getSortedRoutes([
      "/schools/[school_id]/[year]",
      "/schools/[school_id]/early-decision",
    ]);
    expect(sorted[0]).toBe("/schools/[school_id]/early-decision");
  });

  it("404s schools that are not on the allowlist without reading their data", async () => {
    await expect(EarlyDecisionPage(params("dartmouth"))).rejects.toBe(notFoundSentinel);
    expect(mocks.fetchSchoolDocuments).not.toHaveBeenCalled();
    const metadata = await generateMetadata(params("harvard"));
    expect(metadata.robots).toEqual({ index: false, follow: true });
  });

  it("keeps serving a submitted URL that no longer has three usable ED years", async () => {
    mocks.fetchSchoolDocuments.mockResolvedValue(manifest("bowdoin", "Bowdoin College", ["2025-26", "2024-25"]));
    await expect(EarlyDecisionPage(params("bowdoin"))).resolves.toBeTruthy();
  });

  it("serves an eligible allowlisted school as indexable with a self canonical", async () => {
    mocks.fetchSchoolDocuments.mockResolvedValue(
      manifest("bowdoin", "Bowdoin College", ["2025-26", "2024-25", "2023-24"]),
    );
    const metadata = await generateMetadata(params("bowdoin"));
    expect(metadata.title).toBe("Bowdoin College Early Decision Rate: 20.0% for Fall 2025");
    expect(metadata.robots).toEqual({ index: true, follow: true });
    expect(metadata.alternates).toEqual({ canonical: "/schools/bowdoin/early-decision" });
    await expect(EarlyDecisionPage(params("bowdoin"))).resolves.toBeTruthy();
  });
});

describe("early-decision gating", () => {
  it("indexes the pages and lists distinctive names first", () => {
    expect(EARLY_DECISION_INDEXABLE).toBe(true);
    expect(EARLY_DECISION_SCHOOLS).toEqual(["bowdoin", "rice", "lafayette-college"]);
    expect(isEarlyDecisionSchool("bowdoin")).toBe(true);
    expect(isEarlyDecisionSchool("dartmouth")).toBe(false);
    expect(isEarlyDecisionSchool("harvard")).toBe(false);
    expect(isEarlyDecisionSchool("cornell")).toBe(false);
  });

  it("lists served pages in the sitemap", () => {
    expect(earlyDecisionSitemapEntries(["bowdoin", "dartmouth"])).toEqual([
      {
        url: "https://www.collegedata.fyi/schools/bowdoin/early-decision",
        changeFrequency: "monthly",
        priority: 0.6,
      },
    ]);
  });

  it("lists submitted pages in the live sitemap", async () => {
    mocks.fetchSchoolDocuments.mockImplementation(async (id: string) =>
      manifest(id, id, ["2025-26", "2024-25", "2023-24"]),
    );
    const entries = await earlyDecisionSitemap();
    expect(entries).toHaveLength(EARLY_DECISION_SCHOOLS.length);
    expect(entries.map((entry) => entry.url)).toContain(
      "https://www.collegedata.fyi/schools/bowdoin/early-decision",
    );
  });

  it("tells the hub the page is served only for eligible or submitted schools", async () => {
    await expect(fetchEarlyDecisionPageServed("dartmouth")).resolves.toBe(false);
    expect(mocks.fetchSchoolDocuments).not.toHaveBeenCalled();
    mocks.fetchSchoolDocuments.mockResolvedValue(
      manifest("bowdoin", "Bowdoin College", ["2025-26", "2024-25", "2023-24"]),
    );
    await expect(fetchEarlyDecisionPageServed("bowdoin")).resolves.toBe(true);
  });
});

describe("submitted early-decision URLs never silently 404", () => {
  const empty = buildAcceptanceHistory([]);

  it("every submitted URL is an allowlisted page or an explicit 410", () => {
    for (const path of EARLY_DECISION_SUBMITTED_PATHS) {
      const id = path.split("/")[2];
      const gone = EARLY_DECISION_GONE_PATHS.includes(path);
      expect(path).toBe(earlyDecisionPath(id));
      expect(gone || EARLY_DECISION_SCHOOLS.includes(id)).toBe(true);
      if (!gone) expect(earlyDecisionPageDecision(id, empty).kind).not.toBe("not-found");
    }
  });

  it("the proxy answers 410 only for retired URLs", () => {
    const event = { waitUntil: vi.fn() } as never;
    const res = proxy(new NextRequest("https://www.collegedata.fyi/schools/bowdoin/early-decision"), event);
    expect(res.status).not.toBe(410);
  });
});
