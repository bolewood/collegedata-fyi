import { isCanonicalCdsYear } from "./format";
import type { ArtifactNotes } from "./types";

export type SchemaFallbackFacts = {
  fallbackUsed?: boolean | null;
  schemaVersion?: string | null;
  documentYear?: string | null;
};

/** Public copy when extraction mapped a year onto an older published template. */
export function schemaFallbackNote(facts: SchemaFallbackFacts): string | null {
  if (!facts.fallbackUsed) return null;
  const schemaVersion = facts.schemaVersion?.trim() ?? "";
  const documentYear = facts.documentYear?.trim() ?? "";
  if (!isCanonicalCdsYear(schemaVersion) || !isCanonicalCdsYear(documentYear)) {
    return null;
  }
  if (schemaVersion === documentYear) return null;
  return `Mapped to the ${schemaVersion} template; the official ${documentYear} template isn't published yet.`;
}

export function schemaFallbackNoteFromArtifact(
  notes: ArtifactNotes | null | undefined,
  documentYear: string | null | undefined,
): string | null {
  return schemaFallbackNote({
    fallbackUsed: notes?.schema_fallback_used,
    schemaVersion: notes?.schema_version,
    documentYear,
  });
}
