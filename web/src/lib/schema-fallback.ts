import { isCanonicalCdsYear } from "./format";
import type { ArtifactNotes } from "./types";

export type SchemaFallbackFacts = {
  fallbackUsed?: boolean | null;
  fallbackReason?: string | null;
  schemaVersion?: string | null;
  documentYear?: string | null;
};

/**
 * Public copy when extraction mapped a year onto an older published template
 * because that year's template is not out yet.
 *
 * The sentence is only true for a document newer than the template it was
 * mapped to, so nothing is shown for the other two fallbacks: a document older
 * than every schema (a 2021-22 file mapped to 2025-26), and a file the school
 * built on the previous year's form (reason `form_is_<year>`), whose own
 * year's template is published.
 */
export function schemaFallbackNote(facts: SchemaFallbackFacts): string | null {
  if (!facts.fallbackUsed) return null;
  if (facts.fallbackReason?.startsWith("form_is_")) return null;
  const schemaVersion = facts.schemaVersion?.trim() ?? "";
  const documentYear = facts.documentYear?.trim() ?? "";
  if (!isCanonicalCdsYear(schemaVersion) || !isCanonicalCdsYear(documentYear)) {
    return null;
  }
  // "YYYY-YY" years sort as text.
  if (documentYear <= schemaVersion) return null;
  return `Mapped to the ${schemaVersion} template; the official ${documentYear} template isn't published yet.`;
}

export function schemaFallbackNoteFromArtifact(
  notes: ArtifactNotes | null | undefined,
  documentYear: string | null | undefined,
): string | null {
  return schemaFallbackNote({
    fallbackUsed: notes?.schema_fallback_used,
    fallbackReason: notes?.schema_fallback_reason,
    schemaVersion: notes?.schema_version,
    documentYear,
  });
}
