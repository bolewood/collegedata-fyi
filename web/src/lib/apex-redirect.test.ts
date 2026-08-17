import { describe, expect, it } from "vitest";
import { APEX_TO_WWW_REDIRECTS, CANONICAL_ORIGIN } from "./apex-redirect";

describe("apex → www redirects", () => {
  it("issues a permanent 301 to the www host", () => {
    expect(APEX_TO_WWW_REDIRECTS.length).toBeGreaterThan(0);
    for (const redirect of APEX_TO_WWW_REDIRECTS) {
      expect(redirect.statusCode).toBe(301);
      expect(redirect.destination.startsWith(CANONICAL_ORIGIN)).toBe(true);
      expect(redirect.has).toEqual([
        { type: "host", value: "collegedata.fyi" },
      ]);
    }
  });
});
