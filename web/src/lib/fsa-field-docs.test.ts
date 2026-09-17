import { describe, expect, it } from "vitest";

process.env.NEXT_PUBLIC_SUPABASE_URL ??= "http://localhost:54321";
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ??= "test-anon-key";

const { FRIENDLY_FACT_FIELDS, publicFieldDefinitions, selectableFactKeys } =
  await import("./public-data");

describe("FSA nonpayment field docs", () => {
  it("documents nonpayment_rate as an FSA outcomes fact", () => {
    const field = FRIENDLY_FACT_FIELDS.find((item) => item.key === "nonpayment_rate");
    expect(field).toBeDefined();
    expect(field?.source_layer).toBe("fsa");
    expect(field?.category).toBe("outcomes");
    expect(field?.path).toBe("nonpayment.nonpayment_rate");
    expect(field?.caveat).toMatch(/cohort default rate/i);
  });

  it("appears in the public field dictionary", () => {
    const keys = new Set(publicFieldDefinitions().map((field) => field.key));
    expect(keys.has("nonpayment_rate")).toBe(true);
  });

  it("is selectable for the fields= API", () => {
    expect(selectableFactKeys()).toContain("nonpayment_rate");
  });
});
