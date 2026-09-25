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

import AcceptanceRatePage, { generateMetadata } from "./schools/[school_id]/acceptance-rate/page";
import {
  ACCEPTANCE_PILOT_INDEXABLE,
  ACCEPTANCE_PILOT_SCHOOLS,
  ACCEPTANCE_RATE_GONE_PATHS,
  ACCEPTANCE_RATE_SUBMITTED_PATHS,
  acceptancePageDecision,
  acceptanceRatePath,
  acceptanceSitemapEntries,
  headerAccentReadable,
  isAcceptancePilotSchool,
} from "@/lib/acceptance-pilot";
import { acceptanceRateSitemap, fetchAcceptancePageServed } from "@/lib/acceptance-history-data";
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

function extractFor(applied: number, admitted: number) {
  return {
    canonical: { producer: "tier4_docling", notes: { schema_version: null, markdown: "| x |" } },
    fallback: null,
    mergedValues: { "C.116": { value: String(applied) }, "C.117": { value: String(admitted) } },
  };
}

const params = (school_id: string) => ({ params: Promise.resolve({ school_id }) });

beforeEach(() => {
  vi.clearAllMocks();
  mocks.fetchCanonicalSchoolId.mockImplementation(async (id: string) => id);
  mocks.fetchSchoolDocuments.mockResolvedValue([]);
  mocks.fetchSchoolYearFacts.mockResolvedValue([]);
  mocks.fetchSchoolBrandColors.mockResolvedValue(null);
  mocks.fetchExtract.mockImplementation(async (documentId: string) =>
    extractFor(10000, documentId.endsWith("2025-26") ? 500 : 800),
  );
  mocks.permanentRedirect.mockImplementation(() => {
    throw redirectSentinel;
  });
  mocks.notFound.mockImplementation(() => {
    throw notFoundSentinel;
  });
});

describe("acceptance-rate route", () => {
  it("is a static segment that wins over the [year] route", () => {
    const dir = resolve(__dirname, "schools/[school_id]");
    expect(existsSync(resolve(dir, "acceptance-rate/page.tsx"))).toBe(true);
    const sorted = getSortedRoutes([
      "/schools/[school_id]/[year]",
      "/schools/[school_id]/acceptance-rate",
    ]);
    expect(sorted[0]).toBe("/schools/[school_id]/acceptance-rate");
  });

  it("redirects the legal-name slug to the searchable acceptance-rate URL", async () => {
    mocks.fetchCanonicalSchoolId.mockResolvedValue("virginia-tech");
    await expect(
      AcceptanceRatePage(params("virginia-polytechnic-institute-and-state-university")),
    ).rejects.toBe(redirectSentinel);
    expect(mocks.permanentRedirect).toHaveBeenCalledWith(
      "/schools/virginia-tech/acceptance-rate",
    );
    expect(mocks.fetchSchoolDocuments).not.toHaveBeenCalled();
  });

  it("404s schools that are not on the allowlist without reading their data", async () => {
    await expect(AcceptanceRatePage(params("cornell"))).rejects.toBe(notFoundSentinel);
    expect(mocks.fetchSchoolDocuments).not.toHaveBeenCalled();
    const metadata = await generateMetadata(params("cornell"));
    expect(metadata.robots).toEqual({ index: false, follow: true });
  });

  it("keeps serving a submitted URL that no longer has three usable years", async () => {
    mocks.fetchSchoolDocuments.mockResolvedValue(manifest("duke", "Duke University", ["2025-26", "2024-25"]));
    await expect(AcceptanceRatePage(params("duke"))).resolves.toBeTruthy();
  });

  it("keeps serving a submitted URL whose latest usable year is before 2023-24", async () => {
    mocks.fetchSchoolDocuments.mockResolvedValue(
      manifest("duke", "Duke University", ["2022-23", "2021-22", "2020-21", "2019-20"]),
    );
    await expect(AcceptanceRatePage(params("duke"))).resolves.toBeTruthy();
  });

  it("serves an eligible pilot school as indexable with a self canonical and the usable span in the title", async () => {
    mocks.fetchSchoolDocuments.mockResolvedValue(
      manifest("duke", "Duke University", ["2025-26", "2024-25", "2023-24"]),
    );
    const metadata = await generateMetadata(params("duke"));
    expect(metadata.title).toBe("Duke University Acceptance Rate: 5.0% for Fall 2025");
    expect(metadata.robots).toEqual({ index: true, follow: true });
    expect(metadata.alternates).toEqual({ canonical: "/schools/duke/acceptance-rate" });
    await expect(AcceptanceRatePage(params("duke"))).resolves.toBeTruthy();
  });
});

describe("header accent contrast", () => {
  it("falls back to paper when the bright plate is under 4.5:1 on the dark plate", () => {
    expect(headerAccentReadable({ a: "#1c1e1b", b: "#f1ece1", bTypeOnA: true })).toBe(true);
    expect(headerAccentReadable({ a: "#4e3629", b: "#c00404", bTypeOnA: true })).toBe(false);
    expect(headerAccentReadable({ a: "#1c1e1b", b: "#f1ece1", bTypeOnA: false })).toBe(false);
  });
});

describe("pilot gating", () => {
  it("indexes the pilot after the searchable-slug freeze", () => {
    expect(ACCEPTANCE_PILOT_INDEXABLE).toBe(true);
  });

  it("lists the named pilot schools by searchable public id", () => {
    for (const id of [
      "virginia-tech",
      "haverford-college",
      "brown",
      "northeastern",
      "duke",
    ]) {
      expect(ACCEPTANCE_PILOT_SCHOOLS).toContain(id);
    }
    expect(ACCEPTANCE_PILOT_SCHOOLS).not.toContain(
      "virginia-polytechnic-institute-and-state-university",
    );
    expect(ACCEPTANCE_PILOT_SCHOOLS).toContain("uf");
    expect(ACCEPTANCE_PILOT_SCHOOLS).toContain("stanford");
    expect(ACCEPTANCE_PILOT_SCHOOLS).not.toContain("washington-university-in-st-louis");
    expect(ACCEPTANCE_PILOT_SCHOOLS).not.toContain("uw");
    expect(ACCEPTANCE_PILOT_SCHOOLS).not.toContain("umich");
    expect(ACCEPTANCE_PILOT_SCHOOLS).toContain("georgia-tech");
    expect(ACCEPTANCE_PILOT_SCHOOLS).toContain("yale");
    expect(ACCEPTANCE_PILOT_SCHOOLS).not.toContain("uva");
    expect(ACCEPTANCE_PILOT_SCHOOLS).not.toContain("cornell");
    expect(ACCEPTANCE_PILOT_SCHOOLS).toContain("davidson-college");
    expect(ACCEPTANCE_PILOT_SCHOOLS).toContain("howard-university");
    expect(ACCEPTANCE_PILOT_SCHOOLS).not.toContain("elon-university");
    expect(ACCEPTANCE_PILOT_SCHOOLS).not.toContain("barnard");
    expect(ACCEPTANCE_PILOT_SCHOOLS).not.toContain("penn-state");
    expect(ACCEPTANCE_PILOT_SCHOOLS).not.toContain("colorado");
    expect(ACCEPTANCE_PILOT_SCHOOLS).not.toContain("stony-brook-university");
    expect(ACCEPTANCE_PILOT_SCHOOLS.length).toBeLessThanOrEqual(50);
  });

  it("treats the legal-name slug as the same pilot school", () => {
    expect(isAcceptancePilotSchool("virginia-tech")).toBe(true);
    expect(
      isAcceptancePilotSchool("virginia-polytechnic-institute-and-state-university"),
    ).toBe(true);
    expect(isAcceptancePilotSchool("uf")).toBe(true);
    expect(isAcceptancePilotSchool("university-of-florida")).toBe(true);
    expect(isAcceptancePilotSchool("stanford-university")).toBe(true);
    expect(isAcceptancePilotSchool("the-university-of-texas-at-austin")).toBe(true);
    expect(isAcceptancePilotSchool("georgia-tech")).toBe(true);
    expect(isAcceptancePilotSchool("georgia-institute-of-technology-main-campus")).toBe(true);
    expect(isAcceptancePilotSchool("yale-university")).toBe(true);
  });

  it("lists served pilot pages in the sitemap", () => {
    expect(acceptanceSitemapEntries(["duke", "cornell"])).toEqual([
      {
        url: "https://www.collegedata.fyi/schools/duke/acceptance-rate",
        changeFrequency: "monthly",
        priority: 0.6,
      },
    ]);
    expect(
      acceptanceSitemapEntries(["virginia-polytechnic-institute-and-state-university"]),
    ).toEqual([
      {
        url: "https://www.collegedata.fyi/schools/virginia-tech/acceptance-rate",
        changeFrequency: "monthly",
        priority: 0.6,
      },
    ]);
  });

  it("lists submitted pilot pages in the live sitemap", async () => {
    const entries = await acceptanceRateSitemap();
    expect(entries).toHaveLength(ACCEPTANCE_PILOT_SCHOOLS.length);
    expect(entries.map((entry) => entry.url)).toContain(
      "https://www.collegedata.fyi/schools/virginia-tech/acceptance-rate",
    );
  });

  it("tells the hub the page is served only for eligible or submitted pilot schools", async () => {
    await expect(fetchAcceptancePageServed("cornell")).resolves.toBe(false);
    expect(mocks.fetchSchoolDocuments).not.toHaveBeenCalled();
    mocks.fetchSchoolDocuments.mockResolvedValue(
      manifest("brown", "Brown University", ["2025-26", "2024-25", "2023-24"]),
    );
    await expect(fetchAcceptancePageServed("brown")).resolves.toBe(true);
  });
});

describe("submitted URLs never silently 404", () => {
  const empty = buildAcceptanceHistory([]);

  it("every submitted URL is a pilot page or an explicit 410", () => {
    for (const path of ACCEPTANCE_RATE_SUBMITTED_PATHS) {
      const id = path.split("/")[2];
      const gone = ACCEPTANCE_RATE_GONE_PATHS.includes(path);
      expect(path).toBe(acceptanceRatePath(id));
      expect(gone || ACCEPTANCE_PILOT_SCHOOLS.includes(id)).toBe(true);
      if (!gone) expect(acceptancePageDecision(id, empty).kind).not.toBe("not-found");
    }
  });

  it("retired URLs must have been submitted first", () => {
    for (const path of ACCEPTANCE_RATE_GONE_PATHS) {
      expect(ACCEPTANCE_RATE_SUBMITTED_PATHS).toContain(path);
    }
  });

  it("the proxy answers 410 only for retired URLs", () => {
    const event = { waitUntil: vi.fn() } as never;
    const res = proxy(new NextRequest("https://www.collegedata.fyi/schools/duke/acceptance-rate"), event);
    expect(res.status).toBe(200);
    for (const path of ACCEPTANCE_RATE_GONE_PATHS) {
      expect(proxy(new NextRequest(`https://www.collegedata.fyi${path}`), event).status).toBe(410);
    }
  });
});
