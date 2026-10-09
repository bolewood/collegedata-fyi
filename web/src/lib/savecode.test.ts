import { describe, expect, it } from "vitest";
import { decodeProfileCode, encodeProfileCode, resolveMatchShareCode } from "./savecode";
import type { StudentProfile } from "./positioning";

describe("save-game profile codes", () => {
  it("round-trips a complete profile", () => {
    const profile: StudentProfile = {
      gpa: 3.86,
      sat: 1450,
      act: 33,
      gpaScale: "unweighted_4",
    };

    const code = encodeProfileCode(profile);
    expect(code).toMatch(/^[0-9A-HJKMNP-TV-Z]{3}-[0-9A-HJKMNP-TV-Z]{3}$/);
    expect(decodeProfileCode(code)).toEqual(profile);
  });

  it("round-trips missing scores without inventing values", () => {
    const code = encodeProfileCode({ gpaScale: "unknown" });
    expect(decodeProfileCode(code)).toEqual({ gpaScale: "unknown" });
  });

  it("rejects malformed codes", () => {
    expect(decodeProfileCode("TOO-LONG")).toBeNull();
    expect(decodeProfileCode("III-OOO")).toBeNull();
  });

  it("prefers an explicit share code over the query string", () => {
    expect(resolveMatchShareCode("ABC-DEF", "?code=ZZZ-YYY")).toBe("ABC-DEF");
    expect(resolveMatchShareCode(null, "?code=ABC-DEF")).toBe("ABC-DEF");
    expect(resolveMatchShareCode(undefined, "code=ABC-DEF&utm=1")).toBe("ABC-DEF");
    expect(resolveMatchShareCode(undefined, new URLSearchParams("code=ABC-DEF"))).toBe("ABC-DEF");
    expect(resolveMatchShareCode(undefined, "?other=1")).toBeUndefined();
  });

  it("round-trips randomized valid profile payloads", () => {
    const scales: StudentProfile["gpaScale"][] = ["unknown", "unweighted_4", "weighted"];
    for (let i = 0; i < 1000; i += 1) {
      const profile: StudentProfile = {
        gpa: Number((Math.floor(Math.random() * 501) / 100).toFixed(2)),
        sat: 400 + Math.floor(Math.random() * 121) * 10,
        act: 1 + Math.floor(Math.random() * 36),
        gpaScale: scales[Math.floor(Math.random() * scales.length)],
      };
      expect(decodeProfileCode(encodeProfileCode(profile))).toEqual(profile);
    }
  });
});
