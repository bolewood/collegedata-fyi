import type { Database } from "./database.types";

// DB-derived types from generated schema
export type ManifestRow =
  Database["public"]["Views"]["cds_manifest"]["Row"];

export type ArtifactRow =
  Database["public"]["Tables"]["cds_artifacts"]["Row"];

export type ScorecardSummary =
  Database["public"]["Tables"]["scorecard_summary"]["Row"];

export type MeritProfileQuality = "strong" | "partial" | "limited" | "missing";

export type ChangeEventSeverity = "watch" | "notable" | "major";

export type ChangeEventType =
  | "material_delta"
  | "newly_missing"
  | "newly_reported"
  | "reappeared"
  | "format_changed"
  | "producer_changed"
  | "quality_regression"
  | "quality_recovered"
  | "card_quality_changed";

export type ChangeEventVerificationStatus =
  | "not_required"
  | "candidate"
  | "confirmed"
  | "extractor_noise"
  | "ambiguous"
  | "not_reportable";

export interface ChangeEventRow {
  id: string;
  schoolId: string;
  schoolName: string;
  fieldKey: string;
  fieldLabel: string;
  fieldFamily: string;
  fromYear: string;
  toYear: string;
  toYearStart: number | null;
  eventType: ChangeEventType;
  severity: ChangeEventSeverity;
  fromValue: string | null;
  toValue: string | null;
  absoluteDelta: number | null;
  relativeDelta: number | null;
  summary: string;
  fromArchiveUrl: string | null;
  toArchiveUrl: string | null;
  verificationStatus: ChangeEventVerificationStatus;
}

export interface MeritProfileRow {
  documentId: string;
  schoolId: string;
  schoolName: string;
  subInstitutional: string | null;
  ipedsId: string | null;
  cdsYear: string;
  yearStart: number | null;
  schemaVersion: string | null;
  sourceFormat: string | null;
  producer: string | null;
  producerVersion: string | null;
  dataQualityFlag: string | null;
  archiveUrl: string | null;
  firstYearFtStudents: number | null;
  allFtUndergrads: number | null;
  needGrantsTotal: number | null;
  nonNeedGrantsTotal: number | null;
  aidRecipientsFirstYearFt: number | null;
  aidRecipientsAllFt: number | null;
  avgAidPackageFirstYearFt: number | null;
  avgAidPackageAllFt: number | null;
  avgNeedGrantFirstYearFt: number | null;
  avgNeedGrantAllFt: number | null;
  avgNeedSelfHelpFirstYearFt: number | null;
  avgNeedSelfHelpAllFt: number | null;
  nonNeedAidRecipientsFirstYearFt: number | null;
  avgNonNeedGrantFirstYearFt: number | null;
  nonNeedAidRecipientsAllFt: number | null;
  avgNonNeedGrantAllFt: number | null;
  nonNeedAidShareFirstYearFt: number | null;
  nonNeedAidShareAllFt: number | null;
  institutionalNeedAidNonresident: boolean | null;
  institutionalNonNeedAidNonresident: boolean | null;
  avgInternationalAid: number | null;
  institutionalAidAcademics: boolean | null;
  cdsMeritCoreCount: number;
  cdsMeritFieldCount: number;
  meritProfileQuality: MeritProfileQuality;
  scorecardDataYear: string | null;
  earnings6yrMedian: number | null;
  earnings8yrMedian: number | null;
  earnings10yrMedian: number | null;
  earnings10yrP25: number | null;
  earnings10yrP75: number | null;
  medianDebtCompleters: number | null;
  medianDebtMonthlyPayment: number | null;
  avgNetPrice: number | null;
  netPrice0_30k: number | null;
  netPrice30k_48k: number | null;
  netPrice48k_75k: number | null;
  netPrice75k_110k: number | null;
  netPrice110kPlus: number | null;
  graduationRate6yr: number | null;
  pellGrantRate: number | null;
  federalLoanRate: number | null;
  retentionRateFt: number | null;
}

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
  producer?: string;
  producer_version?: string;
  base_artifact_id?: string;
  base_producer?: string;
  base_producer_version?: string;
  cleaner_version?: string;
  markdown_sha256?: string;
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

// PRD 015 M3 — coverage_status_t enum from
// supabase/migrations/20260429144126_institution_cds_coverage.sql.
// Out_of_scope is hidden by RLS for anon/authenticated, so it should
// never appear in any payload reaching the frontend, but it's listed
// here so the union type stays exhaustive against the DB enum.
export type CoverageStatus =
  | "cds_available_current"
  | "cds_available_stale"
  | "cds_found_processing"
  | "latest_found_extract_failed_with_prior_available"
  | "extract_failed"
  | "source_not_automatically_accessible"
  | "no_public_cds_found"
  | "verified_absent"
  | "not_checked"
  | "out_of_scope";

// search_institutions() RPC return shape (PRD 015 M4).
export interface InstitutionSearchResult {
  school_id: string;
  school_name: string;
  city: string | null;
  state: string | null;
  coverage_status: CoverageStatus;
  coverage_label: string;
  latest_available_cds_year: string | null;
}

// fetchInstitutionCoverage() return shape — a single row from
// institution_cds_coverage for the school detail page directory-only
// stub (PRD 015 M4 stub for M5).
export interface InstitutionCoverage {
  ipeds_id: string;
  school_id: string;
  school_name: string;
  city: string | null;
  state: string | null;
  website_url: string | null;
  undergraduate_enrollment: number | null;
  coverage_status: CoverageStatus;
  coverage_label: string;
  coverage_summary: string;
  latest_available_cds_year: string | null;
  last_checked_at: string | null;
  can_submit_source: boolean;
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
