import { describe, expect, it } from "vitest";
import {
  buildRetiredSchoolRedirects,
  resolveCanonicalSchoolId,
  resolveRetiredSchoolAlias,
  schoolRedirectUrl,
} from "./school-alias";

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

describe("buildRetiredSchoolRedirects", () => {
  it("creates query-preserving framework redirects for page and year routes", () => {
    expect(
      buildRetiredSchoolRedirects([
        { alias: "tufts-university", school_id: "tufts" },
      ]),
    ).toEqual([
      {
        source: "/schools/tufts-university",
        destination: "/schools/tufts",
        permanent: true,
      },
      {
        source: "/schools/tufts-university/:year",
        destination: "/schools/tufts/:year",
        permanent: true,
      },
    ]);
  });

  it("rejects ambiguous and malformed redirect entries", () => {
    expect(() =>
      buildRetiredSchoolRedirects([
        { alias: "shared-alias", school_id: "one" },
        { alias: "shared-alias", school_id: "two" },
      ]),
    ).toThrow("Ambiguous retired school redirect");
    expect(() =>
      buildRetiredSchoolRedirects([
        { alias: "Tufts University", school_id: "tufts" },
      ]),
    ).toThrow("Invalid retired school redirect");
  });

  it("deduplicates repeated identical entries", () => {
    expect(
      buildRetiredSchoolRedirects([
        { alias: "tufts-university", school_id: "tufts" },
        { alias: "tufts-university", school_id: "tufts" },
      ]),
    ).toHaveLength(2);
  });
});

describe("resolveRetiredSchoolAlias", () => {
  it("uses the reviewed manifest as the authority for durable aliases", () => {
    expect(
      resolveRetiredSchoolAlias("tufts-university", [
        { alias: "tufts-university", school_id: "tufts" },
      ]),
    ).toBe("tufts");
    expect(resolveRetiredSchoolAlias("missing", [])).toBeNull();
  });

  it("refuses ambiguous manifest entries", () => {
    expect(
      resolveRetiredSchoolAlias("shared", [
        { alias: "shared", school_id: "one" },
        { alias: "shared", school_id: "two" },
      ]),
    ).toBeNull();
  });
});
