-- PRD 010: queryable school browser backend.
--
-- Adds the materialized field-query substrate, curated browser-serving
-- table, and a reusable selected-extraction-result helper view. The helper
-- intentionally supports the Tier 4 LLM fallback overlay, which is stored
-- as kind='cleaned' rather than kind='canonical'.

-- ─── Field metadata ────────────────────────────────────────────────────────
CREATE TABLE public.cds_field_definitions (
  schema_version    text NOT NULL,
  field_id          text NOT NULL,
  field_label       text NOT NULL,
  section           text,
  subsection        text,
  value_kind_hint   text,
  PRIMARY KEY (schema_version, field_id)
);

COMMENT ON TABLE public.cds_field_definitions IS
  'Schema-local CDS field labels and type hints populated from committed schema artifacts. Public read; service-role writes.';

CREATE TABLE public.cds_metric_aliases (
  canonical_metric  text NOT NULL,
  schema_version    text NOT NULL,
  field_id          text NOT NULL,
  value_kind        text NOT NULL,
  mvp_certified     boolean NOT NULL DEFAULT false,
  notes             text,
  PRIMARY KEY (canonical_metric, schema_version, field_id),
  FOREIGN KEY (schema_version, field_id)
    REFERENCES public.cds_field_definitions (schema_version, field_id)
    ON DELETE CASCADE,
  CONSTRAINT cds_metric_aliases_kind_valid
    CHECK (value_kind IN (
      'number',
      'percent',
      'currency',
      'text',
      'yesno',
      'checkbox',
      'unknown',
      'not_applicable'
    ))
);

COMMENT ON TABLE public.cds_metric_aliases IS
  'Stable direct-field aliases for vetted CDS metrics. Derived metrics such as acceptance_rate and yield_rate do not belong here.';

-- ─── Selected extraction result helper ─────────────────────────────────────
CREATE VIEW public.cds_selected_extraction_result
WITH (security_invoker = true) AS
WITH ranked_base AS (
  SELECT
    a.*,
    CASE a.producer
      WHEN 'tier1_xlsx' THEN 1
      WHEN 'tier2_acroform' THEN 2
      WHEN 'tier6_html' THEN 3
      WHEN 'tier4_docling' THEN 4
      ELSE 99
    END AS producer_rank,
    row_number() OVER (
      PARTITION BY a.document_id
      ORDER BY
        CASE a.producer
          WHEN 'tier1_xlsx' THEN 1
          WHEN 'tier2_acroform' THEN 2
          WHEN 'tier6_html' THEN 3
          WHEN 'tier4_docling' THEN 4
          ELSE 99
        END,
        a.created_at DESC,
        a.id DESC
    ) AS rn
  FROM public.cds_artifacts a
  WHERE a.kind = 'canonical'
    AND a.producer IN ('tier1_xlsx', 'tier2_acroform', 'tier6_html', 'tier4_docling')
),
latest_fallback AS (
  SELECT DISTINCT ON (a.document_id)
    a.*
  FROM public.cds_artifacts a
  WHERE a.kind = 'cleaned'
    AND a.producer = 'tier4_llm_fallback'
  ORDER BY a.document_id, a.created_at DESC, a.id DESC
)
SELECT
  b.document_id,
  b.id AS base_artifact_id,
  b.producer AS base_producer,
  b.producer_version AS base_producer_version,
  b.schema_version AS base_schema_version,
  b.created_at AS base_created_at,
  CASE WHEN b.producer = 'tier4_docling' THEN f.id ELSE NULL END AS fallback_artifact_id,
  CASE WHEN b.producer = 'tier4_docling' THEN f.producer ELSE NULL END AS fallback_producer,
  CASE WHEN b.producer = 'tier4_docling' THEN f.producer_version ELSE NULL END AS fallback_producer_version,
  CASE WHEN b.producer = 'tier4_docling' THEN f.created_at ELSE NULL END AS fallback_created_at,
  CASE
    WHEN b.producer = 'tier4_docling' AND f.id IS NOT NULL
      THEN COALESCE(f.notes -> 'values', '{}'::jsonb) || COALESCE(b.notes -> 'values', '{}'::jsonb)
    ELSE COALESCE(b.notes -> 'values', '{}'::jsonb)
  END AS selected_values
FROM ranked_base b
LEFT JOIN latest_fallback f
  ON f.document_id = b.document_id
WHERE b.rn = 1;

COMMENT ON VIEW public.cds_selected_extraction_result IS
  'One selected extraction result per document. Chooses canonical producer precedence tier1_xlsx > tier2_acroform > tier6_html > tier4_docling, then overlays tier4_llm_fallback cleaned values only for Tier 4 base results. JSONB merge order makes deterministic base values win conflicts.';

-- ─── Long-form field projection ────────────────────────────────────────────
CREATE TABLE public.cds_fields (
  document_id        uuid NOT NULL REFERENCES public.cds_documents(id) ON DELETE CASCADE,
  school_id          text NOT NULL,
  school_name        text NOT NULL,
  sub_institutional  text,
  ipeds_id           text,
  canonical_year     text NOT NULL,
  year_start         integer NOT NULL,
  schema_version     text NOT NULL,
  field_id           text NOT NULL,
  canonical_metric   text,

  value_text         text,
  value_num          numeric,
  value_bool         boolean,
  value_kind         text NOT NULL,
  value_status       text NOT NULL,

  source_format      text,
  producer           text NOT NULL,
  producer_version   text,
  data_quality_flag  text,

  archive_url        text NOT NULL,
  updated_at         timestamptz NOT NULL DEFAULT now(),

  PRIMARY KEY (document_id, schema_version, field_id),
  CONSTRAINT cds_fields_value_kind_valid
    CHECK (value_kind IN (
      'number',
      'percent',
      'currency',
      'text',
      'yesno',
      'checkbox',
      'unknown',
      'not_applicable'
    )),
  CONSTRAINT cds_fields_value_status_valid
    CHECK (value_status IN (
      'reported',
      'missing',
      'not_applicable',
      'parse_error'
    )),
  CONSTRAINT cds_fields_percent_fractional
    CHECK (value_kind <> 'percent' OR value_num IS NULL OR (value_num >= 0 AND value_num <= 1))
);

CREATE INDEX idx_cds_fields_school_year
  ON public.cds_fields (school_id, sub_institutional, year_start DESC);
CREATE INDEX idx_cds_fields_metric_num
  ON public.cds_fields (canonical_metric, value_num);
CREATE INDEX idx_cds_fields_field_num
  ON public.cds_fields (schema_version, field_id, value_num);
CREATE INDEX idx_cds_fields_status
  ON public.cds_fields (value_status, source_format, data_quality_flag);
CREATE INDEX idx_cds_fields_year
  ON public.cds_fields (year_start);

COMMENT ON TABLE public.cds_fields IS
  'Materialized long-form CDS field projection for 2024-25+ selected extraction results. This is query-friendly derived data; cds_artifacts.notes.values remains authoritative.';

-- ─── Curated browser-serving rows ──────────────────────────────────────────
CREATE TABLE public.school_browser_rows (
  document_id                      uuid PRIMARY KEY REFERENCES public.cds_documents(id) ON DELETE CASCADE,
  school_id                        text NOT NULL,
  school_name                      text NOT NULL,
  sub_institutional                text,
  ipeds_id                         text,

  canonical_year                   text NOT NULL,
  year_start                       integer NOT NULL,
  schema_version                   text NOT NULL,

  source_format                    text,
  producer                         text NOT NULL,
  producer_version                 text,
  data_quality_flag                text,
  archive_url                      text NOT NULL,

  applied                          integer,
  admitted                         integer,
  enrolled_first_year              integer,
  acceptance_rate                  numeric(7, 6),
  yield_rate                       numeric(7, 6),

  undergrad_enrollment_scorecard   integer,
  scorecard_data_year              text,
  retention_rate                   numeric(7, 6),
  avg_net_price                    integer,
  pell_rate                        numeric(7, 6),

  updated_at                       timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT school_browser_rows_acceptance_fractional
    CHECK (acceptance_rate IS NULL OR (acceptance_rate >= 0 AND acceptance_rate <= 1)),
  CONSTRAINT school_browser_rows_yield_fractional
    CHECK (yield_rate IS NULL OR (yield_rate >= 0 AND yield_rate <= 1)),
  CONSTRAINT school_browser_rows_retention_fractional
    CHECK (retention_rate IS NULL OR (retention_rate >= 0 AND retention_rate <= 1)),
  CONSTRAINT school_browser_rows_pell_fractional
    CHECK (pell_rate IS NULL OR (pell_rate >= 0 AND pell_rate <= 1))
);

CREATE INDEX idx_browser_rows_school_year
  ON public.school_browser_rows (school_id, sub_institutional, year_start DESC);
CREATE INDEX idx_browser_rows_year
  ON public.school_browser_rows (year_start DESC);
CREATE INDEX idx_browser_rows_acceptance
  ON public.school_browser_rows (acceptance_rate);
CREATE INDEX idx_browser_rows_enrollment
  ON public.school_browser_rows (undergrad_enrollment_scorecard);
CREATE INDEX idx_browser_rows_price
  ON public.school_browser_rows (avg_net_price);
CREATE INDEX idx_browser_rows_quality
  ON public.school_browser_rows (source_format, data_quality_flag);

COMMENT ON TABLE public.school_browser_rows IS
  'Curated one-row-per-school-year serving table for the browser and exports. Stores all qualifying 2024-25+ rows; latest-per-school is query behavior, not storage behavior.';

-- ─── RLS/public read ───────────────────────────────────────────────────────
ALTER TABLE public.cds_field_definitions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cds_metric_aliases ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.cds_fields ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.school_browser_rows ENABLE ROW LEVEL SECURITY;

CREATE POLICY cds_field_definitions_public_read
  ON public.cds_field_definitions
  FOR SELECT TO anon, authenticated USING (true);

CREATE POLICY cds_metric_aliases_public_read
  ON public.cds_metric_aliases
  FOR SELECT TO anon, authenticated USING (true);

CREATE POLICY cds_fields_public_read
  ON public.cds_fields
  FOR SELECT TO anon, authenticated USING (true);

CREATE POLICY school_browser_rows_public_read
  ON public.school_browser_rows
  FOR SELECT TO anon, authenticated USING (true);

GRANT SELECT ON public.cds_field_definitions TO anon, authenticated;
GRANT SELECT ON public.cds_metric_aliases TO anon, authenticated;
GRANT SELECT ON public.cds_fields TO anon, authenticated;
GRANT SELECT ON public.school_browser_rows TO anon, authenticated;
GRANT SELECT ON public.cds_selected_extraction_result TO anon, authenticated;
