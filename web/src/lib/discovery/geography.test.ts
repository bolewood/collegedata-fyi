import { describe, expect, it } from "vitest";
import { describeGeography, validateGeography } from "./geography";

const base = { zip: "", preferredMiles: "", maximumMiles: "", allowWildcards: false };

describe("validateGeography", () => {
  it("accepts everything blank — distance settings are optional", () => {
    const v = validateGeography(base);
    expect(v.ok).toBe(true);
    expect(v.value).toEqual({
      zip: null,
      preferred_miles: null,
      maximum_miles: null,
      allow_wildcards: false,
    });
  });

  it("rejects malformed ZIPs without erasing intent", () => {
    const v = validateGeography({ ...base, zip: "1234" });
    expect(v.ok).toBe(false);
    expect(v.errors.zip).toMatch(/five digits/);
  });

  it("blocks continuation when preferred exceeds maximum (PRD failure state)", () => {
    const v = validateGeography({ ...base, preferredMiles: "500", maximumMiles: "200" });
    expect(v.ok).toBe(false);
    expect(v.errors.relation).toMatch(/larger than/);
  });

  it("allows preferred equal to maximum", () => {
    const v = validateGeography({
      ...base,
      zip: "30060",
      preferredMiles: "200",
      maximumMiles: "200",
    });
    expect(v.ok).toBe(true);
  });

  it("requires a ZIP once any radius is set — boundaries need an origin", () => {
    const v = validateGeography({ ...base, maximumMiles: "400" });
    expect(v.ok).toBe(false);
    expect(v.errors.zip).toMatch(/starting point/);
    // No radius, no requirement.
    expect(validateGeography(base).ok).toBe(true);
  });

  it("rejects non-numeric and zero mile values", () => {
    expect(validateGeography({ ...base, preferredMiles: "1,200" }).errors.preferred).toBeTruthy();
    expect(validateGeography({ ...base, maximumMiles: "0" }).errors.maximum).toBeTruthy();
  });

  it("explains that wildcards are ignored without a preferred radius", () => {
    const v = validateGeography({ ...base, allowWildcards: true });
    expect(v.ok).toBe(true);
    expect(v.wildcardNote).toMatch(/ignored/);
    expect(v.value?.allow_wildcards).toBe(true);
  });

  it("shows no wildcard note once a preferred radius exists", () => {
    const v = validateGeography({ ...base, allowWildcards: true, preferredMiles: "150" });
    expect(v.wildcardNote).toBeNull();
  });

  it("suppresses the wildcard note while the preferred value is invalid", () => {
    // The field error already owns the user's attention; a simultaneous
    // "ignored" note would contradict it.
    const v = validateGeography({ ...base, allowWildcards: true, preferredMiles: "abc" });
    expect(v.errors.preferred).toBeTruthy();
    expect(v.wildcardNote).toBeNull();
  });

  it("rejects mile values longer than five digits", () => {
    const v = validateGeography({ ...base, preferredMiles: "123456" });
    expect(v.ok).toBe(false);
    expect(v.errors.preferred).toMatch(/whole number/);
  });

  it("trims surrounding whitespace instead of rejecting it", () => {
    const v = validateGeography({
      ...base,
      zip: " 30060 ",
      preferredMiles: " 150 ",
    });
    expect(v.ok).toBe(true);
    expect(v.value).toMatchObject({ zip: "30060", preferred_miles: 150 });
  });

  it("returns no value when validation fails", () => {
    const v = validateGeography({ ...base, zip: "abcde" });
    expect(v.ok).toBe(false);
    expect(v.value).toBeNull();
  });
});

describe("describeGeography", () => {
  it("summarizes settings in plain language", () => {
    expect(
      describeGeography({
        zip: "30060",
        preferred_miles: 150,
        maximum_miles: 400,
        allow_wildcards: true,
      }),
    ).toBe(
      "starting near 30060 · prefer within ~150 miles · never beyond ~400 miles · occasional wildcards welcome",
    );
    expect(describeGeography(null)).toMatch(/anywhere/);
  });

  it("treats an all-empty geography (the skip path) as anywhere", () => {
    expect(
      describeGeography({
        zip: null,
        preferred_miles: null,
        maximum_miles: null,
        allow_wildcards: false,
      }),
    ).toMatch(/anywhere/);
  });

  it("omits the wildcard clause when no preferred radius exists", () => {
    // allow_wildcards without a preferred radius is ignored by policy; the
    // ledger summary must not advertise it.
    const text = describeGeography({
      zip: null,
      preferred_miles: null,
      maximum_miles: 400,
      allow_wildcards: true,
    });
    expect(text).toBe("never beyond ~400 miles");
  });
});
