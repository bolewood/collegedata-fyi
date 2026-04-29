-- Cross-year canonical field equivalence support (PRD 014 M2.5).
--
-- cds_fields.field_id remains the source schema field id. The new
-- canonical_field_id/equivalence_kind columns record how that source field
-- maps into the 2025-26 reference frame, if it does.

ALTER TABLE public.cds_fields
  ADD COLUMN IF NOT EXISTS canonical_field_id text,
  ADD COLUMN IF NOT EXISTS equivalence_kind text NOT NULL DEFAULT 'direct';

ALTER TABLE public.cds_fields
  DROP CONSTRAINT IF EXISTS cds_fields_equivalence_kind_valid,
  ADD CONSTRAINT cds_fields_equivalence_kind_valid
    CHECK (equivalence_kind IN ('direct', 'derived', 'preserved-only', 'unmapped'));

UPDATE public.cds_fields
SET canonical_field_id = field_id
WHERE canonical_field_id IS NULL
  AND equivalence_kind = 'direct';

CREATE TABLE IF NOT EXISTS public.cds_canonical_field_equivalence (
  schema_version       text NOT NULL,
  field_id             text NOT NULL,
  canonical_field_id   text,
  equivalence_kind     text NOT NULL,
  derivation_formula   text,
  updated_at           timestamptz NOT NULL DEFAULT now(),

  PRIMARY KEY (schema_version, field_id),
  CONSTRAINT cds_canonical_field_equivalence_kind_valid
    CHECK (equivalence_kind IN ('direct', 'derived', 'preserved-only', 'unmapped')),
  CONSTRAINT cds_canonical_field_equivalence_derived_formula
    CHECK (
      (equivalence_kind = 'derived' AND derivation_formula IS NOT NULL)
      OR (equivalence_kind <> 'derived')
    )
);

COMMENT ON TABLE public.cds_canonical_field_equivalence IS
  'Maps source schema field ids to the 2025-26 canonical reference frame. Direct rows map one source field to one canonical field; derived rows document projection formulas.';

ALTER TABLE public.cds_canonical_field_equivalence ENABLE ROW LEVEL SECURITY;

CREATE POLICY cds_canonical_field_equivalence_public_read
  ON public.cds_canonical_field_equivalence
  FOR SELECT
  TO anon, authenticated
  USING (true);

GRANT SELECT ON public.cds_canonical_field_equivalence TO anon, authenticated;
GRANT ALL ON public.cds_canonical_field_equivalence TO service_role;

CREATE INDEX IF NOT EXISTS idx_cds_fields_canonical_field_num
  ON public.cds_fields (canonical_field_id, value_num);

CREATE OR REPLACE FUNCTION public.replace_browser_projection_for_document(
  p_document_id uuid,
  p_field_rows jsonb DEFAULT '[]'::jsonb,
  p_browser_row jsonb DEFAULT NULL
)
RETURNS void
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = public
AS $$
BEGIN
  IF p_field_rows IS NULL THEN
    p_field_rows := '[]'::jsonb;
  END IF;

  IF jsonb_typeof(p_field_rows) <> 'array' THEN
    RAISE EXCEPTION 'p_field_rows must be a JSON array';
  END IF;

  IF p_browser_row IS NOT NULL AND jsonb_typeof(p_browser_row) <> 'object' THEN
    RAISE EXCEPTION 'p_browser_row must be a JSON object or null';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM jsonb_array_elements(p_field_rows) AS field_row(value)
    WHERE field_row.value ->> 'document_id' IS DISTINCT FROM p_document_id::text
  ) THEN
    RAISE EXCEPTION 'all field rows must match p_document_id';
  END IF;

  IF p_browser_row IS NOT NULL
     AND p_browser_row ->> 'document_id' IS DISTINCT FROM p_document_id::text THEN
    RAISE EXCEPTION 'browser row must match p_document_id';
  END IF;

  DELETE FROM public.cds_fields
  WHERE document_id = p_document_id;

  DELETE FROM public.school_browser_rows
  WHERE document_id = p_document_id;

  INSERT INTO public.cds_fields (
    document_id,
    school_id,
    school_name,
    sub_institutional,
    ipeds_id,
    canonical_year,
    year_start,
    schema_version,
    field_id,
    canonical_field_id,
    equivalence_kind,
    canonical_metric,
    value_text,
    value_num,
    value_bool,
    value_kind,
    value_status,
    source_format,
    producer,
    producer_version,
    data_quality_flag,
    archive_url
  )
  SELECT
    document_id,
    school_id,
    school_name,
    sub_institutional,
    ipeds_id,
    canonical_year,
    year_start,
    schema_version,
    field_id,
    canonical_field_id,
    equivalence_kind,
    canonical_metric,
    value_text,
    value_num,
    value_bool,
    value_kind,
    value_status,
    source_format,
    producer,
    producer_version,
    data_quality_flag,
    archive_url
  FROM jsonb_to_recordset(p_field_rows) AS r(
    document_id uuid,
    school_id text,
    school_name text,
    sub_institutional text,
    ipeds_id text,
    canonical_year text,
    year_start integer,
    schema_version text,
    field_id text,
    canonical_field_id text,
    equivalence_kind text,
    canonical_metric text,
    value_text text,
    value_num numeric,
    value_bool boolean,
    value_kind text,
    value_status text,
    source_format text,
    producer text,
    producer_version text,
    data_quality_flag text,
    archive_url text
  );

  IF p_browser_row IS NOT NULL THEN
    INSERT INTO public.school_browser_rows (
      document_id,
      school_id,
      school_name,
      sub_institutional,
      ipeds_id,
      canonical_year,
      year_start,
      schema_version,
      source_format,
      producer,
      producer_version,
      data_quality_flag,
      archive_url,
      applied,
      admitted,
      enrolled_first_year,
      acceptance_rate,
      yield_rate,
      undergrad_enrollment_scorecard,
      scorecard_data_year,
      retention_rate,
      avg_net_price,
      pell_rate,
      sat_submit_rate,
      act_submit_rate,
      sat_composite_p25,
      sat_composite_p50,
      sat_composite_p75,
      sat_ebrw_p25,
      sat_ebrw_p50,
      sat_ebrw_p75,
      sat_math_p25,
      sat_math_p50,
      sat_math_p75,
      act_composite_p25,
      act_composite_p50,
      act_composite_p75
    )
    SELECT
      document_id,
      school_id,
      school_name,
      sub_institutional,
      ipeds_id,
      canonical_year,
      year_start,
      schema_version,
      source_format,
      producer,
      producer_version,
      data_quality_flag,
      archive_url,
      applied,
      admitted,
      enrolled_first_year,
      acceptance_rate,
      yield_rate,
      undergrad_enrollment_scorecard,
      scorecard_data_year,
      retention_rate,
      avg_net_price,
      pell_rate,
      sat_submit_rate,
      act_submit_rate,
      sat_composite_p25,
      sat_composite_p50,
      sat_composite_p75,
      sat_ebrw_p25,
      sat_ebrw_p50,
      sat_ebrw_p75,
      sat_math_p25,
      sat_math_p50,
      sat_math_p75,
      act_composite_p25,
      act_composite_p50,
      act_composite_p75
    FROM jsonb_to_record(p_browser_row) AS r(
      document_id uuid,
      school_id text,
      school_name text,
      sub_institutional text,
      ipeds_id text,
      canonical_year text,
      year_start integer,
      schema_version text,
      source_format text,
      producer text,
      producer_version text,
      data_quality_flag text,
      archive_url text,
      applied integer,
      admitted integer,
      enrolled_first_year integer,
      acceptance_rate numeric,
      yield_rate numeric,
      undergrad_enrollment_scorecard integer,
      scorecard_data_year text,
      retention_rate numeric,
      avg_net_price integer,
      pell_rate numeric,
      sat_submit_rate numeric,
      act_submit_rate numeric,
      sat_composite_p25 integer,
      sat_composite_p50 integer,
      sat_composite_p75 integer,
      sat_ebrw_p25 integer,
      sat_ebrw_p50 integer,
      sat_ebrw_p75 integer,
      sat_math_p25 integer,
      sat_math_p50 integer,
      sat_math_p75 integer,
      act_composite_p25 integer,
      act_composite_p50 integer,
      act_composite_p75 integer
    );
  END IF;
END;
$$;
