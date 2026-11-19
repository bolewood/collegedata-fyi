import { describe, expect, it } from "vitest";
import { schemaFallbackNote, schemaFallbackNoteFromArtifact } from "./schema-fallback";

describe("schemaFallbackNote", () => {
  it("uses the approved school-page copy", () => {
    expect(
      schemaFallbackNote({
        fallbackUsed: true,
        schemaVersion: "2026-27",
        documentYear: "2027-28",
      }),
    ).toBe(
      "Mapped to the 2026-27 template; the official 2027-28 template isn't published yet.",
    );
  });

  it("stays silent for a document older than the template it was mapped to", () => {
    // The 2021-22 template was published long ago; there is just no schema for it.
    expect(
      schemaFallbackNote({ fallbackUsed: true, schemaVersion: "2025-26", documentYear: "2021-22" }),
    ).toBeNull();
  });

  it("stays silent when the school filed on the previous year's form", () => {
    expect(
      schemaFallbackNote({
        fallbackUsed: true,
        fallbackReason: "form_is_2025-26",
        schemaVersion: "2025-26",
        documentYear: "2026-27",
      }),
    ).toBeNull();
    expect(
      schemaFallbackNoteFromArtifact(
        { schema_fallback_used: true, schema_fallback_reason: "form_is_2025-26", schema_version: "2025-26" },
        "2026-27",
      ),
    ).toBeNull();
  });

  it("stays silent when the year-matched template was used", () => {
    expect(
      schemaFallbackNote({
        fallbackUsed: false,
        schemaVersion: "2025-26",
        documentYear: "2025-26",
      }),
    ).toBeNull();
  });

  it("stays silent when fallback is marked but years match", () => {
    expect(
      schemaFallbackNote({
        fallbackUsed: true,
        schemaVersion: "2025-26",
        documentYear: "2025-26",
      }),
    ).toBeNull();
  });

  it("stays silent without a canonical document year", () => {
    expect(
      schemaFallbackNote({
        fallbackUsed: true,
        schemaVersion: "2025-26",
        documentYear: "unknown",
      }),
    ).toBeNull();
  });

  it("reads artifact notes", () => {
    expect(
      schemaFallbackNoteFromArtifact(
        { schema_fallback_used: true, schema_fallback_reason: "no_schema_for_2027-28", schema_version: "2026-27" },
        "2027-28",
      ),
    ).toBe(
      "Mapped to the 2026-27 template; the official 2027-28 template isn't published yet.",
    );
  });
});
