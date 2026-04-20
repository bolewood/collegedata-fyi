import { cache } from "react";
import { supabase } from "./supabase";
import type {
  ManifestRow,
  ArtifactRow,
  ArtifactNotes,
  FieldValue,
  SchoolSummary,
  CorpusStats,
} from "./types";

// Documents with these participation_status values are excluded from every
// public-facing manifest query. 'withdrawn' = takedown per ADR 0008.
// 'verified_absent' = school is publicly known not to publish CDS.
// Consumers who need the full manifest (audit, transparency log reconciliation)
// can query cds_documents directly via PostgREST.
const PUBLIC_EXCLUDED_STATUSES = ["withdrawn", "verified_absent"];

export async function fetchManifest(): Promise<ManifestRow[]> {
  const PAGE_SIZE = 1000;
  const allRows: ManifestRow[] = [];
  let from = 0;

  while (true) {
    const { data, error } = await supabase
      .from("cds_manifest")
      .select("*")
      .not("participation_status", "in", `(${PUBLIC_EXCLUDED_STATUSES.join(",")})`)
      .order("school_name")
      .range(from, from + PAGE_SIZE - 1);

    if (error) throw new Error(`Failed to fetch manifest: ${error.message}`);
    if (!data || data.length === 0) break;

    allRows.push(...data);
    if (data.length < PAGE_SIZE) break;
    from += PAGE_SIZE;
  }

  return allRows;
}

export function aggregateSchools(rows: ManifestRow[]): SchoolSummary[] {
  const map = new Map<string, SchoolSummary>();

  for (const row of rows) {
    const sid = row.school_id ?? "";
    const sname = row.school_name ?? sid;
    const existing = map.get(sid);
    if (!existing) {
      map.set(sid, {
        school_id: sid,
        school_name: sname,
        doc_count: 1,
        latest_year: row.canonical_year,
        formats: row.source_format ? [row.source_format] : [],
        has_extracted: row.extraction_status === "extracted",
      });
    } else {
      existing.doc_count += 1;
      if (
        row.canonical_year &&
        (!existing.latest_year || row.canonical_year > existing.latest_year)
      ) {
        existing.latest_year = row.canonical_year;
      }
      if (row.source_format && !existing.formats.includes(row.source_format)) {
        existing.formats.push(row.source_format);
      }
      if (row.extraction_status === "extracted") {
        existing.has_extracted = true;
      }
    }
  }

  return Array.from(map.values()).sort((a, b) =>
    a.school_name.localeCompare(b.school_name)
  );
}

export function computeStats(rows: ManifestRow[]): CorpusStats {
  const schoolIds = new Set(rows.map((r) => r.school_id).filter(Boolean));
  const years = rows
    .map((r) => r.canonical_year)
    .filter((y): y is string => y != null && y !== "unknown" && /^\d{4}/.test(y))
    .sort();
  const extracted = rows.filter(
    (r) => r.extraction_status === "extracted"
  ).length;

  return {
    total_schools: schoolIds.size,
    total_documents: rows.length,
    earliest_year: years[0] ?? null,
    latest_year: years[years.length - 1] ?? null,
    extracted_count: extracted,
    extraction_pct:
      rows.length > 0 ? Math.round((extracted / rows.length) * 100) : 0,
  };
}

export const fetchSchoolDocuments = cache(async function fetchSchoolDocuments(
  schoolId: string
): Promise<ManifestRow[]> {
  const { data, error } = await supabase
    .from("cds_manifest")
    .select("*")
    .eq("school_id", schoolId)
    .not("participation_status", "in", `(${PUBLIC_EXCLUDED_STATUSES.join(",")})`)
    .order("canonical_year", { ascending: false });

  if (error)
    throw new Error(`Failed to fetch school documents: ${error.message}`);
  return data ?? [];
});

export const fetchDocumentsBySchoolAndYear = cache(async function fetchDocumentsBySchoolAndYear(
  schoolId: string,
  year: string
): Promise<ManifestRow[]> {
  const { data, error } = await supabase
    .from("cds_manifest")
    .select("*")
    .eq("school_id", schoolId)
    .eq("canonical_year", year)
    .not("participation_status", "in", `(${PUBLIC_EXCLUDED_STATUSES.join(",")})`)
    .order("sub_institutional", { ascending: true, nullsFirst: true });

  if (error) {
    throw new Error(`Failed to fetch documents: ${error.message}`);
  }
  return data ?? [];
});

export async function fetchCanonicalArtifact(
  documentId: string
): Promise<ArtifactRow | null> {
  const { data, error } = await supabase
    .from("cds_artifacts")
    .select("*")
    .eq("document_id", documentId)
    .eq("kind", "canonical")
    .order("created_at", { ascending: false })
    .limit(1)
    .single();

  if (error && error.code !== "PGRST116") {
    throw new Error(`Failed to fetch artifact: ${error.message}`);
  }
  return data ?? null;
}

/**
 * Fetch the canonical (deterministic) artifact and, if present, the
 * tier4_llm_fallback artifact, and return merged values per PRD 006 Mode B
 * (fill_gaps): the deterministic cleaner always wins; the fallback only
 * populates question numbers the cleaner left blank.
 *
 * Callers that need the raw canonical (markdown, stats) still get it back
 * via `canonical`. The `mergedValues` field is the shape to render to users.
 */
export async function fetchExtract(documentId: string): Promise<{
  canonical: ArtifactRow | null;
  fallback: ArtifactRow | null;
  mergedValues: Record<string, FieldValue>;
}> {
  const [canonicalRes, fallbackRes] = await Promise.all([
    supabase
      .from("cds_artifacts")
      .select("*")
      .eq("document_id", documentId)
      .eq("kind", "canonical")
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle(),
    supabase
      .from("cds_artifacts")
      .select("*")
      .eq("document_id", documentId)
      .eq("producer", "tier4_llm_fallback")
      .order("created_at", { ascending: false })
      .limit(1)
      .maybeSingle(),
  ]);

  if (canonicalRes.error) {
    throw new Error(`Failed to fetch canonical artifact: ${canonicalRes.error.message}`);
  }
  if (fallbackRes.error) {
    throw new Error(`Failed to fetch fallback artifact: ${fallbackRes.error.message}`);
  }

  const canonicalValues =
    ((canonicalRes.data?.notes as ArtifactNotes | null)?.values ?? {}) as Record<string, FieldValue>;
  const fallbackValues =
    ((fallbackRes.data?.notes as ArtifactNotes | null)?.values ?? {}) as Record<string, FieldValue>;

  // Mode B merge: fallback is the base, canonical overlays on top so the
  // deterministic cleaner's values always win on collision.
  const mergedValues: Record<string, FieldValue> = {
    ...fallbackValues,
    ...canonicalValues,
  };

  return {
    canonical: canonicalRes.data ?? null,
    fallback: fallbackRes.data ?? null,
    mergedValues,
  };
}
