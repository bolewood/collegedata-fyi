export interface ManifestRow {
  document_id: string;
  school_id: string;
  school_name: string;
  sub_institutional: string | null;
  cds_year: string;
  source_url: string | null;
  source_format: string | null;
  participation_status: string;
  discovered_at: string | null;
  last_verified_at: string | null;
  removed_at: string | null;
  extraction_status: string;
  latest_canonical_artifact_id: string | null;
  source_storage_path: string | null;
  detected_year: string | null;
  canonical_year: string | null;
}

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

export interface ArtifactRow {
  id: string;
  document_id: string;
  kind: string;
  producer: string | null;
  producer_version: string | null;
  schema_version: string | null;
  storage_path: string | null;
  sha256: string | null;
  created_at: string;
  notes: {
    values?: Record<string, FieldValue>;
    stats?: { total_fields?: number; unmapped_count?: number };
    markdown?: string;
  } | null;
}

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
