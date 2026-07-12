import { fetchDocumentsBySchoolAndYear, fetchExtract } from "./queries";
import { storageUrl } from "./format";
import type { ArtifactNotes } from "./types";
import type { SpreadsheetInput } from "./spreadsheet";

// Assembles the SpreadsheetInput for the cds.xlsx / cds.csv routes from the
// same queries the school-year page renders with (fetchExtract merges the
// canonical cleaner artifact with the LLM gap-fill fallback, cleaner wins).
// Returns null when the school/year has no public documents or none of them
// carry structured values yet — the routes turn that into a 404.
export async function fetchSpreadsheetInput(
  schoolId: string,
  year: string,
): Promise<SpreadsheetInput | null> {
  const docs = await fetchDocumentsBySchoolAndYear(schoolId, year);
  if (docs.length === 0) return null;

  const documents = await Promise.all(
    docs
      .filter((doc) => doc.extraction_status === "extracted" && doc.document_id)
      .map(async (doc) => {
        const { canonical, mergedValues } = await fetchExtract(doc.document_id!);
        const notes = canonical?.notes as ArtifactNotes | null;
        return {
          variant: doc.sub_institutional,
          schemaVersion: notes?.schema_version ?? doc.cds_year ?? null,
          sourceUrl: storageUrl(doc.source_storage_path),
          values: mergedValues,
        };
      }),
  );

  const withValues = documents.filter(
    (doc) => Object.keys(doc.values).length > 0,
  );
  if (withValues.length === 0) return null;

  return {
    schoolId,
    schoolName: docs[0].school_name ?? schoolId,
    year,
    generatedAt: new Date().toISOString().slice(0, 10),
    documents: withValues,
  };
}

export function notFoundResponse(schoolId: string, year: string): Response {
  return Response.json(
    {
      error: "no_extracted_document",
      school_id: schoolId,
      year,
      message:
        "No extracted CDS document with structured field values was found for this school and year.",
    },
    { status: 404 },
  );
}

export const SPREADSHEET_CACHE_CONTROL =
  "public, s-maxage=3600, stale-while-revalidate=86400";
