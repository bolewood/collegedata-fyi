import { cache } from "react";
import type { MetadataRoute } from "next";
import { fetchExtract, fetchSchoolDocuments, fetchSchoolYearFacts } from "./queries";
import {
  buildAcceptanceHistory,
  isHistoryCandidate,
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
