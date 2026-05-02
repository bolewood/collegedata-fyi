-- PRD 016B: backfill admission strategy columns from the current cds_fields projection.
--
-- This is a production data backfill for rows that existed before the new
-- school_browser_rows columns were added. It does not rewrite extraction
-- artifacts; future extraction drains and full projection rebuilds keep using
-- project_browser_data.py as the source of truth.

WITH field_pivot AS (
  SELECT
    document_id,
    bool_or(value_bool) FILTER (
      WHERE field_id = 'C.2101' AND value_status = 'reported'
    ) AS ed_offered,
    (max(value_num) FILTER (
      WHERE value_status = 'reported'
        AND (
          (schema_version = '2024-25' AND field_id = 'C.2106')
          OR (schema_version <> '2024-25' AND field_id = 'C.2110')
        )
    ))::integer AS ed_applicants,
    (max(value_num) FILTER (
      WHERE value_status = 'reported'
        AND (
          (schema_version = '2024-25' AND field_id = 'C.2107')
          OR (schema_version <> '2024-25' AND field_id = 'C.2111')
        )
    ))::integer AS ed_admitted,
    bool_or(
      value_status = 'reported'
      AND coalesce(value_text, value_num::text, value_bool::text) IS NOT NULL
    ) FILTER (
      WHERE
        (schema_version = '2024-25' AND field_id IN ('C.2104', 'C.2105'))
        OR (schema_version <> '2024-25' AND field_id IN ('C.2106', 'C.2107', 'C.2108', 'C.2109'))
    ) AS ed_has_second_deadline,
    bool_or(value_bool) FILTER (
      WHERE field_id = 'C.2201' AND value_status = 'reported'
    ) AS ea_offered,
    bool_or(value_bool) FILTER (
      WHERE field_id = 'C.2206' AND value_status = 'reported'
    ) AS ea_restrictive,
    bool_or(value_bool) FILTER (
      WHERE field_id = 'C.201' AND value_status = 'reported'
    ) AS wait_list_policy,
    (max(value_num) FILTER (
      WHERE field_id = 'C.202' AND value_status = 'reported'
    ))::integer AS wait_list_offered,
    (max(value_num) FILTER (
      WHERE field_id = 'C.203' AND value_status = 'reported'
    ))::integer AS wait_list_accepted,
    (max(value_num) FILTER (
      WHERE field_id = 'C.204' AND value_status = 'reported'
    ))::integer AS wait_list_admitted,
    max(value_text) FILTER (
      WHERE field_id = 'C.711' AND value_status = 'reported'
    ) AS c711_first_gen_factor,
    max(value_text) FILTER (
      WHERE field_id = 'C.712' AND value_status = 'reported'
    ) AS c712_legacy_factor,
    max(value_text) FILTER (
      WHERE field_id = 'C.713' AND value_status = 'reported'
    ) AS c713_geography_factor,
    max(value_text) FILTER (
      WHERE field_id = 'C.714' AND value_status = 'reported'
    ) AS c714_state_residency_factor,
    max(value_text) FILTER (
      WHERE field_id = 'C.718' AND value_status = 'reported'
    ) AS c718_demonstrated_interest_factor,
    (max(value_num) FILTER (
      WHERE field_id = 'C.1302' AND value_status = 'reported'
    ))::integer AS app_fee_amount,
    bool_or(value_bool) FILTER (
      WHERE field_id = 'C.1305' AND value_status = 'reported'
    ) AS app_fee_waiver_offered
  FROM public.cds_fields
  WHERE year_start >= 2024
    AND field_id IN (
      'C.2101', 'C.2104', 'C.2105', 'C.2106', 'C.2107', 'C.2108', 'C.2109', 'C.2110', 'C.2111',
      'C.2201', 'C.2206',
      'C.201', 'C.202', 'C.203', 'C.204',
      'C.711', 'C.712', 'C.713', 'C.714', 'C.718',
      'C.1302', 'C.1305'
    )
  GROUP BY document_id
)
UPDATE public.school_browser_rows AS sbr
SET
  ed_offered = fp.ed_offered,
  ed_applicants = fp.ed_applicants,
  ed_admitted = fp.ed_admitted,
  ed_has_second_deadline = coalesce(fp.ed_has_second_deadline, false),
  ea_offered = fp.ea_offered,
  ea_restrictive = fp.ea_restrictive,
  wait_list_policy = fp.wait_list_policy,
  wait_list_offered = fp.wait_list_offered,
  wait_list_accepted = fp.wait_list_accepted,
  wait_list_admitted = fp.wait_list_admitted,
  c711_first_gen_factor = fp.c711_first_gen_factor,
  c712_legacy_factor = fp.c712_legacy_factor,
  c713_geography_factor = fp.c713_geography_factor,
  c714_state_residency_factor = fp.c714_state_residency_factor,
  c718_demonstrated_interest_factor = fp.c718_demonstrated_interest_factor,
  app_fee_amount = fp.app_fee_amount,
  app_fee_waiver_offered = fp.app_fee_waiver_offered
FROM field_pivot AS fp
WHERE sbr.document_id = fp.document_id
  AND sbr.year_start >= 2024;

UPDATE public.school_browser_rows
SET admission_strategy_card_quality =
  CASE
    WHEN (
      ed_applicants IS NOT NULL
      AND ed_admitted IS NOT NULL
      AND ed_admitted > ed_applicants
    )
    OR (
      admitted IS NOT NULL
      AND admitted > 0
      AND ed_admitted IS NOT NULL
      AND ed_admitted > admitted
    ) THEN 'ed_math_inconsistent'
    WHEN (
      wait_list_offered IS NOT NULL
      AND wait_list_accepted IS NOT NULL
      AND wait_list_accepted > wait_list_offered
    )
    OR (
      wait_list_accepted IS NOT NULL
      AND wait_list_admitted IS NOT NULL
      AND wait_list_admitted > wait_list_accepted
    ) THEN 'wait_list_math_inconsistent'
    WHEN NOT (
      (ed_offered IS TRUE AND ed_applicants IS NOT NULL AND ed_applicants > 0 AND ed_admitted IS NOT NULL)
      OR yield_rate IS NOT NULL
      OR (wait_list_policy IS TRUE AND wait_list_offered IS NOT NULL AND wait_list_accepted IS NOT NULL AND wait_list_admitted IS NOT NULL)
      OR c711_first_gen_factor IN ('Important', 'Very Important')
      OR c712_legacy_factor IN ('Important', 'Very Important')
      OR c713_geography_factor IN ('Important', 'Very Important')
      OR c714_state_residency_factor IN ('Important', 'Very Important')
      OR c718_demonstrated_interest_factor IN ('Important', 'Very Important')
      OR app_fee_amount IS NOT NULL
      OR app_fee_waiver_offered IS NOT NULL
    ) THEN 'insufficient_data'
    ELSE 'ok'
  END
WHERE year_start >= 2024;
