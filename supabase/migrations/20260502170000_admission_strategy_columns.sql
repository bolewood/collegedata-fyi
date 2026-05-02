-- PRD 016B: admission strategy card columns.

ALTER TABLE public.school_browser_rows
  ADD COLUMN IF NOT EXISTS ed_offered boolean,
  ADD COLUMN IF NOT EXISTS ed_applicants integer,
  ADD COLUMN IF NOT EXISTS ed_admitted integer,
  ADD COLUMN IF NOT EXISTS ed_has_second_deadline boolean,
  ADD COLUMN IF NOT EXISTS ea_offered boolean,
  ADD COLUMN IF NOT EXISTS ea_restrictive boolean,
  ADD COLUMN IF NOT EXISTS wait_list_policy boolean,
  ADD COLUMN IF NOT EXISTS wait_list_offered integer,
  ADD COLUMN IF NOT EXISTS wait_list_accepted integer,
  ADD COLUMN IF NOT EXISTS wait_list_admitted integer,
  ADD COLUMN IF NOT EXISTS c711_first_gen_factor text,
  ADD COLUMN IF NOT EXISTS c712_legacy_factor text,
  ADD COLUMN IF NOT EXISTS c713_geography_factor text,
  ADD COLUMN IF NOT EXISTS c714_state_residency_factor text,
  ADD COLUMN IF NOT EXISTS c718_demonstrated_interest_factor text,
  ADD COLUMN IF NOT EXISTS app_fee_amount integer,
  ADD COLUMN IF NOT EXISTS app_fee_waiver_offered boolean,
  ADD COLUMN IF NOT EXISTS admission_strategy_card_quality text;

ALTER TABLE public.school_browser_rows
  ADD CONSTRAINT school_browser_rows_ed_applicants_nonnegative
    CHECK (ed_applicants IS NULL OR ed_applicants >= 0),
  ADD CONSTRAINT school_browser_rows_ed_admitted_nonnegative
    CHECK (ed_admitted IS NULL OR ed_admitted >= 0),
  ADD CONSTRAINT school_browser_rows_wait_list_offered_nonnegative
    CHECK (wait_list_offered IS NULL OR wait_list_offered >= 0),
  ADD CONSTRAINT school_browser_rows_wait_list_accepted_nonnegative
    CHECK (wait_list_accepted IS NULL OR wait_list_accepted >= 0),
  ADD CONSTRAINT school_browser_rows_wait_list_admitted_nonnegative
    CHECK (wait_list_admitted IS NULL OR wait_list_admitted >= 0),
  ADD CONSTRAINT school_browser_rows_app_fee_amount_nonnegative
    CHECK (app_fee_amount IS NULL OR app_fee_amount >= 0),
  ADD CONSTRAINT school_browser_rows_admission_strategy_quality_valid
    CHECK (
      admission_strategy_card_quality IS NULL OR
      admission_strategy_card_quality IN (
        'ok',
        'ed_math_inconsistent',
        'wait_list_math_inconsistent',
        'insufficient_data'
      )
    );

COMMENT ON COLUMN public.school_browser_rows.ed_offered IS
  'PRD 016B C.21 Early Decision offered flag.';
COMMENT ON COLUMN public.school_browser_rows.ed_applicants IS
  'PRD 016B C.21 Early Decision applicants.';
COMMENT ON COLUMN public.school_browser_rows.ed_admitted IS
  'PRD 016B C.21 Early Decision admitted applicants.';
COMMENT ON COLUMN public.school_browser_rows.ed_has_second_deadline IS
  'PRD 016B derived signal for an additional binding ED round.';
COMMENT ON COLUMN public.school_browser_rows.ea_offered IS
  'PRD 016B C.22 Early Action offered flag. CDS does not publish EA applicant/admit counts.';
COMMENT ON COLUMN public.school_browser_rows.ea_restrictive IS
  'PRD 016B C.22 restrictive Early Action flag.';
COMMENT ON COLUMN public.school_browser_rows.admission_strategy_card_quality IS
  'PRD 016B card-level quality state; suppress affected card blocks without invalidating the document.';

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
      act_composite_p75,
      ed_offered,
      ed_applicants,
      ed_admitted,
      ed_has_second_deadline,
      ea_offered,
      ea_restrictive,
      wait_list_policy,
      wait_list_offered,
      wait_list_accepted,
      wait_list_admitted,
      c711_first_gen_factor,
      c712_legacy_factor,
      c713_geography_factor,
      c714_state_residency_factor,
      c718_demonstrated_interest_factor,
      app_fee_amount,
      app_fee_waiver_offered,
      admission_strategy_card_quality
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
      act_composite_p75,
      ed_offered,
      ed_applicants,
      ed_admitted,
      ed_has_second_deadline,
      ea_offered,
      ea_restrictive,
      wait_list_policy,
      wait_list_offered,
      wait_list_accepted,
      wait_list_admitted,
      c711_first_gen_factor,
      c712_legacy_factor,
      c713_geography_factor,
      c714_state_residency_factor,
      c718_demonstrated_interest_factor,
      app_fee_amount,
      app_fee_waiver_offered,
      admission_strategy_card_quality
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
      act_composite_p75 integer,
      ed_offered boolean,
      ed_applicants integer,
      ed_admitted integer,
      ed_has_second_deadline boolean,
      ea_offered boolean,
      ea_restrictive boolean,
      wait_list_policy boolean,
      wait_list_offered integer,
      wait_list_accepted integer,
      wait_list_admitted integer,
      c711_first_gen_factor text,
      c712_legacy_factor text,
      c713_geography_factor text,
      c714_state_residency_factor text,
      c718_demonstrated_interest_factor text,
      app_fee_amount integer,
      app_fee_waiver_offered boolean,
      admission_strategy_card_quality text
    );
  END IF;
END;
$$;
