import { describe, expect, it } from "vitest";
import {
  federalCategory,
  parseCompareFactCategories,
  parsePublicFactCategories,
} from "./public-fact-category";

describe("public federal fact categories", () => {
  it("classifies Endowment facts as finance", () => {
    expect(
      federalCategory({
        display_group: "Endowment",
        field_key: "endowment_value_end",
        field_label: "Endowment net assets, end of fiscal year",
      }),
    ).toBe("finance");
  });

  it("accepts finance in the school-facts category filter", () => {
    expect(parsePublicFactCategories(" finance, outcomes,unknown ")).toEqual([
      "finance",
      "outcomes",
    ]);
    expect(parsePublicFactCategories("unknown")).toEqual([]);
    expect(parsePublicFactCategories("")).toEqual([]);
    expect(parsePublicFactCategories(null)).toBeUndefined();
  });

  it("marks finance as unsupported by the fixed-schema compare endpoint", () => {
    expect(parseCompareFactCategories("finance,admissions")).toEqual({
      categories: ["finance", "admissions"],
      unsupported: ["finance"],
    });
    expect(parseCompareFactCategories("admissions,cost")).toEqual({
      categories: ["admissions", "cost"],
      unsupported: [],
    });
  });
});
