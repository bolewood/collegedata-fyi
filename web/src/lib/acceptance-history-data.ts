import { cache } from "react";
import type { MetadataRoute } from "next";
import { fetchExtract, fetchSchoolDocuments, fetchSchoolYearFacts } from "./queries";
import type { SchoolYearFacts } from "./school-summary";
import { gateC1Counts, ipedsAdmissions, type GateReason } from "./c1-hub-gate";
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
import {
  EARLY_DECISION_INDEXABLE,
  EARLY_DECISION_SCHOOLS,
  earlyDecisionPageDecision,
  earlyDecisionSitemapEntries,
  isEarlyDecisionSchool,
} from "./early-decision-pilot";
import type { ArtifactNotes, ManifestRow, SchoolFactUnifiedRow } from "./types";

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
      edApplicants: row.edApplicants,
      edAdmitted: row.edAdmitted,
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
 * The facts row a hub, meta description, or year page shows for one year:
 * the projected row, with its C1 counts replaced, kept, or withheld by the
 * gate (c1-hub-gate): pilot schools take the printed totals; elsewhere a
 * changed number must be corroborated by IPEDS. Administrative units show
 * none. Costs at most one cached artifact read.
 */
export async function gatedYearFacts(
  row: SchoolYearFacts | null,
  documents: Pick<ManifestRow, "document_id" | "extraction_status">[],
  context: { schoolId: string; ipedsId: string | null; federalFacts: SchoolFactUnifiedRow[] },
): Promise<(SchoolYearFacts & { c1Reason: GateReason }) | null> {
  if (!row) return null;
  const ipeds = ipedsAdmissions(context.federalFacts, context.ipedsId ?? row.ipeds_id);
  const doc = row.document_id ? documents.find((d) => d.document_id === row.document_id) : undefined;
  const resolver = doc && doc.extraction_status === "extracted" && row.document_id
    ? await printedCountsForDocument(row.document_id, row.canonical_year, row.applied, row.admitted, row.enrolledFirstYear)
    : null;
  const decision = gateC1Counts({
    pilot: isAcceptancePilotSchool(context.schoolId),
    yearStart: row.yearStart ?? Number(row.canonical_year.slice(0, 4)),
    projection: { applied: row.applied, admitted: row.admitted, enrolled: row.enrolledFirstYear },
    resolver,
    ipeds,
  });
  const counts = decision.counts;
  return {
    ...row,
    applied: counts?.applied ?? null,
    admitted: counts?.admitted ?? null,
    enrolledFirstYear: counts?.enrolled ?? null,
    // The rate is always recomputed from the gated counts, never a stored value.
    acceptanceRate: null,
    c1Reason: decision.reason,
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

/** True when /schools/{id}/early-decision renders. Never throws; the hub calls it. */
export const fetchEarlyDecisionPageServed = cache(async function fetchEarlyDecisionPageServed(
  schoolId: string,
): Promise<boolean> {
  if (!isEarlyDecisionSchool(schoolId)) return false;
  try {
    const { history } = await fetchAcceptanceHistory(schoolId);
    return earlyDecisionPageDecision(schoolId, history).kind !== "not-found";
  } catch (error) {
    console.warn(`fetchEarlyDecisionPageServed: ${String(error)}`);
    return false;
  }
});

export async function earlyDecisionSitemap(
  indexable: boolean = EARLY_DECISION_INDEXABLE,
): Promise<MetadataRoute.Sitemap> {
  if (!indexable) return [];
  const served = await Promise.all(
    EARLY_DECISION_SCHOOLS.map(async (id) => ((await fetchEarlyDecisionPageServed(id)) ? id : null)),
  );
  return earlyDecisionSitemapEntries(
    served.filter((id): id is string => id != null),
    indexable,
  );
}
