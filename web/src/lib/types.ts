import type { Database } from "./database.types";

// DB-derived types from generated schema
export type ManifestRow =
  Database["public"]["Views"]["cds_manifest"]["Row"];

export type ArtifactRow =
  Database["public"]["Tables"]["cds_artifacts"]["Row"];

// Artifact notes are typed as Json in the generated schema.
// This interface describes the actual runtime shape written by the
// extraction pipeline (Tier 2 and Tier 4 cleaners).
export interface FieldValue {
  value: string;
  value_decoded?: string;
  pdf_tag?: string;
  section?: string;
  question?: string;
  word_tag?: string;
  subsection?: string;
  value_type?: string;
}

export interface ArtifactNotes {
  values?: Record<string, FieldValue>;
  stats?: { total_fields?: number; unmapped_count?: number };
  markdown?: string;
}

// App-level aggregation types (not direct DB mirrors)
export interface SchoolSummary {
  school_id: string;
  school_name: string;
  doc_count: number;
  latest_year: string | null;
  formats: string[];
  has_extracted: boolean;
}

export interface CorpusStats {
  total_schools: number;
  total_documents: number;
  earliest_year: string | null;
  latest_year: string | null;
  extracted_count: number;
  extraction_pct: number;
}
