-- Atomic replacement helper for per-document browser projection refreshes.
--
-- The Python projector computes rows from selected extraction artifacts, then
-- hands both public projection surfaces to this RPC. Postgres executes the
-- delete + insert sequence in one transaction, so a mid-refresh failure cannot
-- leave a document partially removed from the browser.

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

COMMENT ON FUNCTION public.replace_browser_projection_for_document(uuid, jsonb, jsonb) IS
  'Atomically replaces cds_fields and school_browser_rows for one document. Intended for service-role projection workers.';

REVOKE ALL ON FUNCTION public.replace_browser_projection_for_document(uuid, jsonb, jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.replace_browser_projection_for_document(uuid, jsonb, jsonb) TO service_role;
