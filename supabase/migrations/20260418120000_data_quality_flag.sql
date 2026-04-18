-- Add data_quality_flag to cds_documents for flagging publisher-side issues
-- that are not extraction bugs (blank templates, wrong files, etc.)
--
-- Values: null (no issue), 'blank_template', 'wrong_file', 'low_coverage'

ALTER TABLE public.cds_documents
  ADD COLUMN data_quality_flag text;

COMMENT ON COLUMN public.cds_documents.data_quality_flag IS
  'Publisher-side data quality issue. null = OK, ''blank_template'' = school '
  'published an unfilled CDS template, ''wrong_file'' = archive grabbed the '
  'wrong document (e.g. CDS Definitions glossary), ''low_coverage'' = fewer '
  'than 5 fields extracted (likely a publisher issue, not an extraction bug). '
  'Set by tools/data_quality/audit_manifest.py.';

-- Recreate cds_manifest view to include data_quality_flag.
-- Must DROP + CREATE (not CREATE OR REPLACE) because adding a column
-- in the middle changes the column order, which Postgres disallows.
DROP VIEW IF EXISTS public.cds_manifest;

CREATE VIEW public.cds_manifest AS
  SELECT
    d.id                   AS document_id,
    d.school_id,
    d.school_name,
    d.sub_institutional,
    d.cds_year,
    d.source_url,
    d.source_format,
    d.participation_status,
    d.discovered_at,
    d.last_verified_at,
    d.removed_at,
    d.extraction_status,
    (
      SELECT a.id
      FROM public.cds_artifacts a
      WHERE a.document_id = d.id AND a.kind = 'canonical'
      ORDER BY a.created_at DESC
      LIMIT 1
    ) AS latest_canonical_artifact_id,
    (
      SELECT a.storage_path
      FROM public.cds_artifacts a
      WHERE a.document_id = d.id AND a.kind = 'source'
      ORDER BY a.created_at DESC
      LIMIT 1
    ) AS source_storage_path,
    d.detected_year,
    COALESCE(d.detected_year, d.cds_year) AS canonical_year,
    d.data_quality_flag
  FROM public.cds_documents d;

-- Restore RLS grants (DROP VIEW removes them)
GRANT SELECT ON public.cds_manifest TO anon, authenticated;

COMMENT ON VIEW public.cds_manifest IS
  'Convenience view joining cds_documents to their most recent canonical '
  'artifact and archived source file. Query this view when you want '
  '"latest structured data per school" as a single join-free GET. '
  'Prefer canonical_year over cds_year. data_quality_flag surfaces '
  'publisher-side issues (blank templates, wrong files).';
