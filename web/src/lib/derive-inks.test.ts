import { describe, expect, it } from "vitest";
import {
  HOUSE_A,
  HOUSE_B,
  INK_LAB_PRESETS,
  MIN_B_ON_A,
  MIN_B_ON_CREAM,
  PAPER,
  TARGET_A,
  TARGET_ON_B,
  UNKNOWN_GLYPH_A,
  UNKNOWN_GLYPH_B,
  contrast,
  deriveInks,
  glyphInks,
  glyphSearchFields,
} from "./derive-inks";

describe("deriveInks", () => {
  it("returns production forest and ochre unchanged when no brand colours exist", () => {
    const inks = deriveInks([]);
    expect(inks.house).toBe(true);
    expect(inks.a).toBe(HOUSE_A);
    expect(inks.b).toBe(HOUSE_B);
    expect(inks.a).toBe("#3f5b3a");
    expect(inks.b).toBe("#8a6a2b");
    expect(inks.bTypeOnA).toBe(false);
  });

  it("treats a grey-only palette as house inks instead of inventing a hue", () => {
    const inks = deriveInks(["#3B3B3B"]);
    expect(inks.house).toBe(true);
    expect(inks.a).toBe(HOUSE_A);
    expect(inks.b).toBe(HOUSE_B);
  });

  it("leaves Michigan maize untouched on production paper", () => {
    const inks = deriveInks(["#00274C", "#FFCB05"]);
    expect(inks.house).toBe(false);
    expect(inks.b).toBe("#ffcb05");
    expect(inks.contrast.bOnCream).toBeGreaterThanOrEqual(MIN_B_ON_CREAM);
    expect(inks.bTypeOnA).toBe(true);
    expect(inks.rule.startsWith("ideal pair")).toBe(true);
  });

  it("does not walk B to pass the type-on-A gate", () => {
    const inks = deriveInks(["#003A63", "#E51937"]);
    expect(inks.bTypeOnA).toBe(false);
    expect(inks.contrast.bOnA).toBeLessThan(MIN_B_ON_A);
    expect(inks.rule).toMatch(/type on A stays cream/);
  });

  it("pulls a near-paper yellow down so the plate is still an area colour", () => {
    const inks = deriveInks(["#FFF9C4"]);
    expect(inks.b).not.toBe("#fff9c4");
    expect(inks.contrast.bOnCream).toBeGreaterThanOrEqual(MIN_B_ON_CREAM);
    expect(inks.rule).toMatch(/pulled down/);
  });

  it("clears reading gates for every lab preset without raising the cream floor", () => {
    for (const [name, hexes] of INK_LAB_PRESETS) {
      const inks = deriveInks(hexes);
      expect(inks.contrast.textOnB, name).toBeGreaterThanOrEqual(TARGET_ON_B);
      expect(inks.contrast.bOnCream, name).toBeGreaterThanOrEqual(MIN_B_ON_CREAM);
      if (inks.house) {
        expect(inks.a, name).toBe(HOUSE_A);
        expect(inks.b, name).toBe(HOUSE_B);
      } else {
        expect(inks.contrast.aOnCream, name).toBeGreaterThanOrEqual(TARGET_A);
      }
    }
  });

  it("keeps production paper as the cream the gates are measured against", () => {
    expect(PAPER).toBe("#f1ece1");
    expect(contrast(HOUSE_A, PAPER)).toBeLessThan(TARGET_A);
    expect(contrast("#ffcb05", PAPER)).toBeGreaterThanOrEqual(MIN_B_ON_CREAM);
    expect(contrast("#ffcb05", PAPER)).toBeLessThan(1.3);
  });
});

describe("glyphInks", () => {
  it("returns grey plus a hollow B when no colours are on file", () => {
    expect(glyphInks(null)).toEqual({
      a: UNKNOWN_GLYPH_A,
      b: UNKNOWN_GLYPH_B,
      hollowB: true,
      unknown: true,
    });
    expect(glyphInks([])).toEqual(glyphInks(null));
  });

  it("does not use house forest and ochre for an unknown school", () => {
    const inks = glyphInks(null);
    expect(inks.a).not.toBe(HOUSE_A);
    expect(inks.b).not.toBe(HOUSE_B);
  });

  it("keeps Michigan maize as the B dot", () => {
    const inks = glyphInks(["#00274C", "#FFCB05"]);
    expect(inks.unknown).toBe(false);
    expect(inks.hollowB).toBe(false);
    expect(inks.a).toBe("#00274c");
    expect(inks.b).toBe("#ffcb05");
  });

  it("treats a lone dark as A and derives a bright B", () => {
    const inks = glyphInks(["#18453B"]);
    expect(inks.unknown).toBe(false);
    expect(inks.a).toBe("#18453b");
    expect(inks.b).toBe("#159c84");
  });

  it("rejects black as a plate and keeps the gold", () => {
    const inks = glyphInks(["#000000", "#FFCC00"]);
    expect(inks.unknown).toBe(false);
    expect(inks.a).toBe("#333f48");
    expect(inks.b).toBe("#ffcc00");
  });

  it("ships a, b, and hollow_b for the search payload", () => {
    expect(glyphSearchFields(null)).toEqual({
      a: UNKNOWN_GLYPH_A,
      b: UNKNOWN_GLYPH_B,
      hollow_b: true,
    });
    expect(glyphSearchFields(["#00274C", "#FFCB05"])).toEqual({
      a: "#00274c",
      b: "#ffcb05",
      hollow_b: false,
    });
  });

  it("keeps scouted Michigan A plates as given", () => {
    expect(glyphInks(["#6C4023", "#B5A167"]).a).toBe("#6c4023");
    expect(glyphInks(["#6A0032"]).a).toBe("#6a0032");
    expect(glyphInks(["#005841", "#FFB600"])).toMatchObject({
      a: "#005841",
      b: "#ffb600",
      unknown: false,
    });
  });
});
