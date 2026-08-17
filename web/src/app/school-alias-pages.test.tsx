import { beforeEach, describe, expect, it, vi } from "vitest";

const mocks = vi.hoisted(() => ({
  fetchCanonicalSchoolId: vi.fn(),
  fetchSchoolDocuments: vi.fn(),
  fetchDocumentsBySchoolAndYear: vi.fn(),
  fetchExtract: vi.fn(),
  fetchScorecardByIpedsId: vi.fn(),
  fetchInstitutionCoverage: vi.fn(),
  fetchBrowserRowBySchoolId: vi.fn(),
  fetchAvgGpaBySchoolId: vi.fn(),
  fetchAdmissionStrategyBySchoolId: vi.fn(),
  fetchAdmissionStrategyByDocumentId: vi.fn(),
  fetchMeritProfileBySchoolId: vi.fn(),
  fetchChangeEventsBySchoolId: vi.fn(),
  fetchSchoolFederalFacts: vi.fn(),
  permanentRedirect: vi.fn(),
  notFound: vi.fn(),
  imageResponse: vi.fn(),
}));

vi.mock("@/lib/queries", () => ({
  fetchCanonicalSchoolId: mocks.fetchCanonicalSchoolId,
  fetchSchoolDocuments: mocks.fetchSchoolDocuments,
  fetchDocumentsBySchoolAndYear: mocks.fetchDocumentsBySchoolAndYear,
  fetchExtract: mocks.fetchExtract,
  fetchScorecardByIpedsId: mocks.fetchScorecardByIpedsId,
  fetchInstitutionCoverage: mocks.fetchInstitutionCoverage,
  fetchBrowserRowBySchoolId: mocks.fetchBrowserRowBySchoolId,
  fetchAvgGpaBySchoolId: mocks.fetchAvgGpaBySchoolId,
  fetchAdmissionStrategyBySchoolId: mocks.fetchAdmissionStrategyBySchoolId,
  fetchAdmissionStrategyByDocumentId: mocks.fetchAdmissionStrategyByDocumentId,
  fetchMeritProfileBySchoolId: mocks.fetchMeritProfileBySchoolId,
  fetchChangeEventsBySchoolId: mocks.fetchChangeEventsBySchoolId,
  fetchSchoolFederalFacts: mocks.fetchSchoolFederalFacts,
}));

vi.mock("next/navigation", () => ({
  permanentRedirect: mocks.permanentRedirect,
  notFound: mocks.notFound,
}));

vi.mock("next/og", () => ({
  ImageResponse: mocks.imageResponse,
}));

import SchoolPage, {
  generateMetadata as generateSchoolMetadata,
} from "./schools/[school_id]/page";
import SchoolYearPage, {
  generateMetadata as generateSchoolYearMetadata,
} from "./schools/[school_id]/[year]/page";
import SchoolOgImage from "./schools/[school_id]/opengraph-image";
import SchoolYearOgImage from "./schools/[school_id]/[year]/opengraph-image";

const redirectSentinel = new Error("NEXT_REDIRECT");

describe("retired alias pages and Open Graph images", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.fetchCanonicalSchoolId.mockResolvedValue("tufts");
    mocks.permanentRedirect.mockImplementation(() => {
      throw redirectSentinel;
    });
    mocks.imageResponse.mockImplementation(function MockImageResponse(this: object) {
      return this;
    });
  });

  it("redirects the school page before stale alias documents can render", async () => {
    mocks.fetchSchoolDocuments.mockResolvedValue([
      { school_id: "tufts-university", school_name: "Stale Tufts" },
    ]);

    await expect(
      SchoolPage({
        params: Promise.resolve({ school_id: "tufts-university" }),
      }),
    ).rejects.toBe(redirectSentinel);

    expect(mocks.permanentRedirect).toHaveBeenCalledWith("/schools/tufts");
    expect(mocks.fetchSchoolDocuments).not.toHaveBeenCalled();
  });

  it("redirects the school-year page before stale alias documents can render", async () => {
    mocks.fetchDocumentsBySchoolAndYear.mockResolvedValue([
      { school_id: "tufts-university", school_name: "Stale Tufts" },
    ]);

    await expect(
      SchoolYearPage({
        params: Promise.resolve({
          school_id: "tufts-university",
          year: "2024-25",
        }),
      }),
    ).rejects.toBe(redirectSentinel);

    expect(mocks.permanentRedirect).toHaveBeenCalledWith(
      "/schools/tufts/2024-25",
    );
    expect(mocks.fetchDocumentsBySchoolAndYear).not.toHaveBeenCalled();
  });

  it("canonicalizes school and year metadata before reading stale alias data", async () => {
    mocks.fetchSchoolDocuments.mockResolvedValue([
      {
        school_id: "tufts",
        school_name: "Tufts University",
        canonical_year: "2024-25",
      },
    ]);
    mocks.fetchDocumentsBySchoolAndYear.mockResolvedValue([
      { school_id: "tufts", school_name: "Tufts University" },
    ]);
    mocks.fetchInstitutionCoverage.mockResolvedValue(null);

    const [schoolMetadata, yearMetadata] = await Promise.all([
      generateSchoolMetadata({
        params: Promise.resolve({ school_id: "tufts-university" }),
      }),
      generateSchoolYearMetadata({
        params: Promise.resolve({
          school_id: "tufts-university",
          year: "2024-25",
        }),
      }),
    ]);

    expect(mocks.fetchSchoolDocuments).toHaveBeenCalledWith("tufts");
    expect(mocks.fetchDocumentsBySchoolAndYear).toHaveBeenCalledWith(
      "tufts",
      "2024-25",
    );
    expect(schoolMetadata.alternates).toEqual({ canonical: "/schools/tufts" });
    expect(yearMetadata.alternates).toEqual({
      canonical: "/schools/tufts/2024-25",
    });
  });

  it("emits path-specific canonicals for Virginia Tech and Harvey Mudd year pages", async () => {
    mocks.fetchCanonicalSchoolId.mockImplementation(async (schoolId: string) => schoolId);
    mocks.fetchSchoolDocuments.mockImplementation(async (schoolId: string) => [
      {
        school_id: schoolId,
        school_name:
          schoolId === "virginia-tech" ? "Virginia Tech" : "Harvey Mudd College",
        canonical_year: "2025-26",
      },
    ]);
    mocks.fetchDocumentsBySchoolAndYear.mockImplementation(
      async (schoolId: string) => [
        {
          school_id: schoolId,
          school_name:
            schoolId === "virginia-tech"
              ? "Virginia Tech"
              : "Harvey Mudd College",
        },
      ],
    );
    mocks.fetchInstitutionCoverage.mockResolvedValue(null);

    const [vtHub, vtYear, hmcHub, hmcYear] = await Promise.all([
      generateSchoolMetadata({
        params: Promise.resolve({ school_id: "virginia-tech" }),
      }),
      generateSchoolYearMetadata({
        params: Promise.resolve({
          school_id: "virginia-tech",
          year: "2025-26",
        }),
      }),
      generateSchoolMetadata({
        params: Promise.resolve({ school_id: "harvey-mudd" }),
      }),
      generateSchoolYearMetadata({
        params: Promise.resolve({
          school_id: "harvey-mudd",
          year: "2025-26",
        }),
      }),
    ]);

    expect(vtHub.alternates).toEqual({ canonical: "/schools/virginia-tech" });
    expect(vtYear.alternates).toEqual({
      canonical: "/schools/virginia-tech/2025-26",
    });
    expect(hmcHub.alternates).toEqual({ canonical: "/schools/harvey-mudd" });
    expect(hmcYear.alternates).toEqual({
      canonical: "/schools/harvey-mudd/2025-26",
    });
    expect(vtHub.alternates).not.toEqual({ canonical: "/" });
    expect(vtYear.alternates).not.toEqual({ canonical: "/" });
  });

  it("loads the canonical school for the school-level Open Graph image", async () => {
    mocks.fetchSchoolDocuments.mockResolvedValue([
      {
        document_id: "canonical-document",
        school_id: "tufts",
        school_name: "Tufts University",
        canonical_year: "2024-25",
      },
    ]);

    await SchoolOgImage({
      params: Promise.resolve({ school_id: "tufts-university" }),
    });

    expect(mocks.fetchSchoolDocuments).toHaveBeenCalledTimes(1);
    expect(mocks.fetchSchoolDocuments).toHaveBeenCalledWith("tufts");
  });

  it("loads the canonical school and year for the year Open Graph image", async () => {
    mocks.fetchDocumentsBySchoolAndYear.mockResolvedValue([
      {
        document_id: "canonical-document",
        school_id: "tufts",
        school_name: "Tufts University",
        canonical_year: "2024-25",
        extraction_status: "pending",
      },
    ]);

    await SchoolYearOgImage({
      params: Promise.resolve({
        school_id: "tufts-university",
        year: "2024-25",
      }),
    });

    expect(mocks.fetchDocumentsBySchoolAndYear).toHaveBeenCalledTimes(1);
    expect(mocks.fetchDocumentsBySchoolAndYear).toHaveBeenCalledWith(
      "tufts",
      "2024-25",
    );
  });
});
