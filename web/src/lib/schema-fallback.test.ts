import { describe, expect, it } from "vitest";
import { schemaFallbackNote, schemaFallbackNoteFromArtifact } from "./schema-fallback";

describe("schemaFallbackNote", () => {
  it("uses the approved school-page copy", () => {
    expect(
      schemaFallbackNote({
        fallbackUsed: true,
        schemaVersion: "2025-26",
        documentYear: "2026-27",
      }),
    ).toBe(
      "Mapped to the 2025-26 template; the official 2026-27 template isn't published yet.",
    );
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
        { schema_fallback_used: true, schema_version: "2025-26" },
        "2026-27",
      ),
    ).toBe(
      "Mapped to the 2025-26 template; the official 2026-27 template isn't published yet.",
    );
  });
});
