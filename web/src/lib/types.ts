import type { Database } from "./database.types";

// DB-derived types from generated schema
export type ManifestRow =
  Database["public"]["Views"]["cds_manifest"]["Row"];

export type ArtifactRow =
  Database["public"]["Tables"]["cds_artifacts"]["Row"];

export type ScorecardSummary =
  Database["public"]["Tables"]["scorecard_summary"]["Row"];

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
  // Added by the tier4_llm_fallback producer (PRD 006).
  source?: string;
  evidence_text?: string;
  evidence_section?: string;
  verification?: string;
  confidence?: number;
}

export interface ArtifactNotes {
  values?: Record<string, FieldValue>;
  stats?: {
    total_fields?: number;
    unmapped_count?: number;
    fields_accepted?: number;
    fields_rejected?: number;
    cache_hits?: number;
    cache_misses?: number;
    total_cost_usd?: number;
  };
  markdown?: string;
  // tier4_llm_fallback-only fields
  mode?: "fill_gaps" | "shadow";
  producer?: string;
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

export interface SiteStats extends CorpusStats {
  schema_field_count: number | null;
  queryable_field_count: number | null;
  queryable_field_updated_at: string | null;
  browser_row_count: number | null;
  browser_primary_row_count: number | null;
  browser_school_count: number | null;
  browser_updated_at: string | null;
  scorecard_institution_count: number | null;
  scorecard_data_year: string | null;
  scorecard_refreshed_at: string | null;
}
