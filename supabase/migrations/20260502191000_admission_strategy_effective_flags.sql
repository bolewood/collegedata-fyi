-- PRD 016B: align backfilled rows with effective ED/wait-list flag semantics.
--
-- Valid ED counts imply ED is offered, and valid wait-list counts imply a
-- wait-list policy, even when the source checkbox field was missing or failed
-- to parse. App-fee-only rows should not qualify the card to render.

UPDATE public.school_browser_rows
SET
  ed_offered = TRUE
WHERE year_start >= 2024
  AND ed_applicants IS NOT NULL
  AND ed_applicants > 0
  AND ed_admitted IS NOT NULL
  AND ed_admitted >= 0
  AND ed_admitted <= ed_applicants
  AND (admitted IS NULL OR admitted <= 0 OR ed_admitted <= admitted);

UPDATE public.school_browser_rows
SET
  wait_list_policy = TRUE
WHERE year_start >= 2024
  AND wait_list_offered IS NOT NULL
  AND wait_list_offered >= 0
  AND wait_list_accepted IS NOT NULL
  AND wait_list_accepted >= 0
  AND wait_list_admitted IS NOT NULL
  AND wait_list_admitted >= 0
  AND wait_list_accepted <= wait_list_offered
  AND wait_list_admitted <= wait_list_accepted;

UPDATE public.school_browser_rows
SET admission_strategy_card_quality =
  CASE
    WHEN (
      ed_applicants IS NOT NULL
      AND ed_admitted IS NOT NULL
      AND (
        ed_applicants < 0
        OR ed_admitted < 0
        OR ed_admitted > ed_applicants
      )
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
      AND (
        wait_list_offered < 0
        OR wait_list_accepted < 0
        OR wait_list_accepted > wait_list_offered
      )
    )
    OR (
      wait_list_accepted IS NOT NULL
      AND wait_list_admitted IS NOT NULL
      AND (
        wait_list_admitted < 0
        OR wait_list_admitted > wait_list_accepted
      )
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
      OR ea_offered IS TRUE
    ) THEN 'insufficient_data'
    ELSE 'ok'
  END
WHERE year_start >= 2024;
