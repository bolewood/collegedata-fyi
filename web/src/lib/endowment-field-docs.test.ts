import { describe, expect, it } from "vitest";

// public-data.ts transitively initializes the supabase client at module load,
// so the env must exist before a dynamic import (a static import would hoist
// above these assignments and crash).
process.env.NEXT_PUBLIC_SUPABASE_URL ??= "http://localhost:54321";
process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ??= "test-anon-key";

const { FEDERAL_ENDOWMENT_FIELD_DOCS, publicFieldDefinitions, selectableFactKeys } =
  await import("./public-data");

describe("federal endowment field docs", () => {
  it("documents all six endowment facts under the finance category", () => {
    expect(FEDERAL_ENDOWMENT_FIELD_DOCS).toHaveLength(6);
    for (const field of FEDERAL_ENDOWMENT_FIELD_DOCS) {
      expect(field.key).toMatch(/^ipeds\.endowment_/);
      expect(field.category).toBe("finance");
      expect(field.source_layer).toBe("ipeds");
      expect(field.definition.length).toBeGreaterThan(0);
    }
  });

  it("appears in the public field dictionary", () => {
    const keys = new Set(publicFieldDefinitions().map((field) => field.key));
    for (const field of FEDERAL_ENDOWMENT_FIELD_DOCS) {
      expect(keys.has(field.key)).toBe(true);
    }
  });

  it("is excluded from the fields= selector key list", () => {
    const selectable = new Set(selectableFactKeys());
    expect(selectable.size).toBeGreaterThan(0);
    for (const field of FEDERAL_ENDOWMENT_FIELD_DOCS) {
      expect(selectable.has(field.key)).toBe(false);
    }
  });

  it("carries the sign and residual caveats on the two hazardous fields", () => {
    const byKey = new Map(FEDERAL_ENDOWMENT_FIELD_DOCS.map((field) => [field.key, field]));
    expect(byKey.get("ipeds.endowment_spending_distribution")?.caveat).toMatch(/sign/i);
    expect(byKey.get("ipeds.endowment_other_change")?.caveat).toMatch(/not a measure of borrowing/i);
  });
});
