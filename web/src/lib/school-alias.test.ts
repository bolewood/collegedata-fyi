import { describe, expect, it } from "vitest";
import { resolveCanonicalSchoolId, schoolRedirectUrl } from "./school-alias";

describe("resolveCanonicalSchoolId", () => {
  it("resolves the retired Tufts slug to the canonical school", () => {
    expect(
      resolveCanonicalSchoolId("tufts-university", [
        {
          school_id: "tufts",
          alias: "tufts-university",
          is_primary: false,
        },
      ]),
    ).toBe("tufts");
  });

  it("leaves a canonical slug on its own school", () => {
    expect(
      resolveCanonicalSchoolId("tufts", [
        { school_id: "tufts", alias: "tufts", is_primary: true },
      ]),
    ).toBe("tufts");
  });

  it("prefers the one primary claim over demoted aliases", () => {
    expect(
      resolveCanonicalSchoolId("bethel-university", [
        {
          school_id: "bethel-university",
          alias: "bethel-university",
          is_primary: true,
        },
        {
          school_id: "bethel-university-in",
          alias: "bethel-university",
          is_primary: false,
        },
      ]),
    ).toBe("bethel-university");
  });

  it("refuses to guess when multiple non-primary aliases conflict", () => {
    expect(
      resolveCanonicalSchoolId("shared-alias", [
        { school_id: "one", alias: "shared-alias", is_primary: false },
        { school_id: "two", alias: "shared-alias", is_primary: false },
      ]),
    ).toBeNull();
  });

  it("returns null when no alias matches", () => {
    expect(resolveCanonicalSchoolId("missing-school", [])).toBeNull();
  });

  it("returns null when multiple primary claims conflict", () => {
    expect(
      resolveCanonicalSchoolId("shared-primary", [
        { school_id: "one", alias: "shared-primary", is_primary: true },
        { school_id: "two", alias: "shared-primary", is_primary: true },
      ]),
    ).toBeNull();
  });

  it("preserves API query parameters when replacing a retired school path", () => {
    expect(
      schoolRedirectUrl(
        "https://www.collegedata.fyi/api/schools/tufts-university/facts?categories=admissions",
        "/api/schools/tufts/facts",
      ).toString(),
    ).toBe(
      "https://www.collegedata.fyi/api/schools/tufts/facts?categories=admissions",
    );
  });
});
