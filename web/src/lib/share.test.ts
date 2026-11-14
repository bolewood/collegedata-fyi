import { describe, expect, it } from "vitest";
import { buildSharePayload, buildShareUrl, isShareCancellation } from "./share";

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
