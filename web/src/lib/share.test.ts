import { describe, expect, it } from "vitest";
import {
  buildSharePayload,
  buildShareUrl,
  isShareCancellation,
  matchSharePath,
  shareEventProperties,
} from "./share";

const ORIGIN = "https://www.collegedata.fyi";

describe("buildShareUrl", () => {
  it("joins origin and path", () => {
    expect(buildShareUrl(ORIGIN, "/schools/yale")).toBe(`${ORIGIN}/schools/yale`);
  });
  it("tolerates a trailing slash on the origin and a missing leading slash", () => {
    expect(buildShareUrl(`${ORIGIN}/`, "schools/yale")).toBe(`${ORIGIN}/schools/yale`);
  });
  it("keeps the query string exactly as given", () => {
    expect(buildShareUrl(ORIGIN, "/coverage?state=CA&size=large")).toBe(
      `${ORIGIN}/coverage?state=CA&size=large`,
    );
  });
  it("appends a section hash", () => {
    expect(buildShareUrl(ORIGIN, "/schools/yale", "merit-profile")).toBe(
      `${ORIGIN}/schools/yale#merit-profile`,
    );
  });
  it("replaces an existing hash with the section id, or drops it", () => {
    expect(buildShareUrl(ORIGIN, "/schools/yale#old", "documents")).toBe(
      `${ORIGIN}/schools/yale#documents`,
    );
    expect(buildShareUrl(ORIGIN, "/schools/yale#old")).toBe(`${ORIGIN}/schools/yale`);
  });
  it("ignores an invalid section id", () => {
    expect(buildShareUrl(ORIGIN, "/schools/yale", "a b#c")).toBe(`${ORIGIN}/schools/yale`);
  });
});

describe("buildSharePayload", () => {
  it("carries title, optional text and the absolute URL", () => {
    expect(
      buildSharePayload({ title: "T", text: "X", origin: ORIGIN, path: "/match?code=A" }),
    ).toEqual({ title: "T", text: "X", url: `${ORIGIN}/match?code=A` });
  });
  it("omits text when not given", () => {
    expect(buildSharePayload({ title: "T", origin: ORIGIN, path: "/coverage" })).toEqual({
      title: "T",
      url: `${ORIGIN}/coverage`,
    });
  });
});

describe("isShareCancellation", () => {
  it("is true only for AbortError", () => {
    expect(isShareCancellation(Object.assign(new Error("x"), { name: "AbortError" }))).toBe(true);
    expect(isShareCancellation(new Error("x"))).toBe(false);
    expect(isShareCancellation(null)).toBe(false);
  });
});

describe("shareEventProperties", () => {
  it("is limited to surface, variant, has_section and method", () => {
    const props = shareEventProperties({ surface: "match", variant: "header", method: "clipboard" });
    expect(Object.keys(props).sort()).toEqual(["has_section", "method", "surface", "variant"]);
    expect(props).toEqual({ surface: "match", variant: "header", has_section: false, method: "clipboard" });
  });
  it("omits method when absent and reports sections as a boolean", () => {
    const props = shareEventProperties({ surface: "school_section", variant: "icon", sectionId: "documents" });
    expect(props).toEqual({ surface: "school_section", variant: "icon", has_section: true });
  });
  it("cannot carry a URL or code: extra inputs are ignored", () => {
    const props = shareEventProperties({
      surface: "match",
      variant: "header",
      url: "https://x/match?code=ABC-123",
      code: "ABC-123",
    } as never);
    expect(JSON.stringify(props)).not.toMatch(/ABC|http|code/);
  });
});

describe("matchSharePath", () => {
  it("is exactly /match?code=<encoded>", () => {
    expect(matchSharePath("K9F-3XQ")).toBe("/match?code=K9F-3XQ");
    expect(matchSharePath("a b&c")).toBe("/match?code=a%20b%26c");
  });
});
