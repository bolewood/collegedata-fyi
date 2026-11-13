import { describe, expect, it } from "vitest";
import { normalizeIpedsId } from "./ipeds-id";

describe("normalizeIpedsId", () => {
  it("accepts a six-digit unit id, trimming whitespace", () => {
    expect(normalizeIpedsId("166683")).toBe("166683");
    expect(normalizeIpedsId(" 166683 ")).toBe("166683");
  });

  it("rejects anything that is not exactly six digits", () => {
    for (const raw of ["", "16668", "1666830", "16668a", "166683;drop", "mit", null, undefined]) {
      expect(normalizeIpedsId(raw)).toBeNull();
    }
  });
});
