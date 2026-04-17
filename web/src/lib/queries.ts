import { cache } from "react";
import { supabase } from "./supabase";
import type { ManifestRow, ArtifactRow, SchoolSummary, CorpusStats } from "./types";

const MANIFEST_COLUMNS =
  "document_id, school_id, school_name, sub_institutional, cds_year, source_format, extraction_status, canonical_year, source_storage_path";

export async function fetchManifest(): Promise<ManifestRow[]> {
  const PAGE_SIZE = 1000;
  const allRows: ManifestRow[] = [];
  let from = 0;

  while (true) {
    const { data, error } = await supabase
      .from("cds_manifest")
      .select(MANIFEST_COLUMNS)
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
    const existing = map.get(row.school_id);
    if (!existing) {
      map.set(row.school_id, {
        school_id: row.school_id,
        school_name: row.school_name,
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
  const schoolIds = new Set(rows.map((r) => r.school_id));
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
