import { cache } from "react";
import type { MetadataRoute } from "next";
import { fetchExtract, fetchSchoolDocuments, fetchSchoolYearFacts } from "./queries";
import type { SchoolYearFacts } from "./school-summary";
import {
  buildAcceptanceHistory,
  isHistoryCandidate,
  readAcceptanceYear,
  type AcceptanceHistory,
  type BrowserCounts,
  type HistoryExtract,
} from "./acceptance-history";
import {
  ACCEPTANCE_PILOT_INDEXABLE,
  ACCEPTANCE_PILOT_SCHOOLS,
  acceptancePageDecision,
  acceptanceSitemapEntries,
  isAcceptancePilotSchool,
} from "./acceptance-pilot";
import type { ArtifactNotes, ManifestRow } from "./types";

const fetchHistoryExtract = cache(async function fetchHistoryExtract(
  documentId: string,
): Promise<HistoryExtract | null> {
  const { canonical, mergedValues } = await fetchExtract(documentId);
  if (!canonical) return null;
  const notes = canonical.notes as ArtifactNotes | null;
  return {
    values: mergedValues,
    schemaVersion: notes?.schema_version ?? null,
    producer: canonical.producer ?? null,
    markdown: notes?.markdown ?? null,
  };
});

export type SchoolAcceptanceHistory = {
  /** Hub display name: the newest report's name. */
  schoolName: string | null;
  documents: ManifestRow[];
  history: AcceptanceHistory;
};

/** Alias-aware (via fetchSchoolDocuments); one extract read per candidate year, in parallel. */
export const fetchAcceptanceHistory = cache(async function fetchAcceptanceHistory(
  schoolId: string,
): Promise<SchoolAcceptanceHistory> {
  const [documents, facts] = await Promise.all([
    fetchSchoolDocuments(schoolId),
    fetchSchoolYearFacts(schoolId),
  ]);
  const candidates = documents.filter(isHistoryCandidate);
  const extracts = await Promise.all(
    candidates.map((doc) => fetchHistoryExtract(doc.document_id as string)),
  );
  const browserByDocument = new Map<string, BrowserCounts>();
  for (const row of facts) {
    if (!row.document_id) continue;
    browserByDocument.set(row.document_id, {
      applied: row.applied,
      admitted: row.admitted,
      enrolled: row.enrolledFirstYear,
    });
  }
  return {
    schoolName: documents[0]?.school_name ?? null,
    documents,
    history: buildAcceptanceHistory(
      candidates.map((doc, i) => ({ doc, extract: extracts[i] })),
      browserByDocument,
    ),
  };
});

/**
 * One fact, one number: the school's printed C1 counts for one document,
 * read the same way the acceptance-rate page reads them (readAcceptanceYear
 * with the projected row as fallback). Cached per document, so a hub or
 * year page costs at most one extra artifact read. Null when the extract
 * has no usable reading; callers then keep the projected row.
 */
const printedCountsForDocument = cache(async function printedCountsForDocument(
  documentId: string,
  canonicalYear: string,
  applied: number | null,
  admitted: number | null,
  enrolled: number | null,
): Promise<BrowserCounts | null> {
  try {
    const extract = await fetchHistoryExtract(documentId);
    const reading = readAcceptanceYear(
      {
        document_id: documentId,
        canonical_year: canonicalYear,
        extraction_status: "extracted",
        data_quality_flag: null,
        sub_institutional: null,
        source_storage_path: null,
        source_format: null,
      },
      extract,
      { applied, admitted, enrolled },
    );
    if (!reading.ok || reading.row.source === "projection") return null;
    return { applied: reading.row.applied, admitted: reading.row.admitted, enrolled: reading.row.enrolled };
  } catch (error) {
    console.warn(`printedCountsForDocument: ${String(error)}`);
    return null;
  }
});

/**
 * The projected facts row with its C1 counts replaced by the school's
 * printed totals when those differ. Used by the hub summary and meta, the
 * year page summary, and (through readAcceptanceYear) the acceptance-rate
 * page, so all of them show the same applied, admitted, and rate.
 */
export async function withPrintedTotals(
  row: SchoolYearFacts | null,
  documents: Pick<ManifestRow, "document_id" | "extraction_status">[],
): Promise<SchoolYearFacts | null> {
  if (!row?.document_id) return row;
  const doc = documents.find((d) => d.document_id === row.document_id);
  if (!doc || doc.extraction_status !== "extracted") return row;
  const printed = await printedCountsForDocument(
    row.document_id,
    row.canonical_year,
    row.applied,
    row.admitted,
    row.enrolledFirstYear,
  );
  if (!printed) return row;
  if (printed.applied === row.applied && printed.admitted === row.admitted && printed.enrolled === row.enrolledFirstYear) {
    return row;
  }
  return {
    ...row,
    applied: printed.applied,
    admitted: printed.admitted,
    enrolledFirstYear: printed.enrolled,
    acceptanceRate: null,
  };
}

/** True when /schools/{id}/acceptance-rate renders. Never throws; the hub calls it. */
export const fetchAcceptancePageServed = cache(async function fetchAcceptancePageServed(
  schoolId: string,
): Promise<boolean> {
  if (!isAcceptancePilotSchool(schoolId)) return false;
  try {
    const { history } = await fetchAcceptanceHistory(schoolId);
    return acceptancePageDecision(schoolId, history).kind !== "not-found";
  } catch (error) {
    console.warn(`fetchAcceptancePageServed: ${String(error)}`);
    return false;
  }
});

export async function acceptanceRateSitemap(
  indexable: boolean = ACCEPTANCE_PILOT_INDEXABLE,
): Promise<MetadataRoute.Sitemap> {
  if (!indexable) return [];
  const served = await Promise.all(
    ACCEPTANCE_PILOT_SCHOOLS.map(async (id) => ((await fetchAcceptancePageServed(id)) ? id : null)),
  );
  return acceptanceSitemapEntries(
    served.filter((id): id is string => id != null),
    indexable,
  );
}
