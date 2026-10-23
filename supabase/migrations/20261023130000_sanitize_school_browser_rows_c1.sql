-- Suppress impossible derived C1 rates (0% acceptance_rate, 0% yield_rate,
-- or rates derived from inverted/zero C1 cohort counts) in school_browser_rows.

UPDATE public.school_browser_rows
SET
  acceptance_rate = NULL
WHERE
  acceptance_rate <= 0
  OR admitted IS NULL
  OR admitted <= 0
  OR applied IS NULL
  OR applied <= 0
  OR admitted > applied
  OR (enrolled_first_year IS NOT NULL AND enrolled_first_year > admitted);

UPDATE public.school_browser_rows
SET
  yield_rate = NULL
WHERE
  yield_rate <= 0
  OR admitted IS NULL
  OR admitted <= 0
  OR enrolled_first_year IS NULL
  OR enrolled_first_year <= 0
  OR enrolled_first_year > admitted
  OR (applied IS NOT NULL AND admitted > applied);

ALTER TABLE public.school_browser_rows
  DROP CONSTRAINT IF EXISTS school_browser_rows_acceptance_fractional,
  ADD CONSTRAINT school_browser_rows_acceptance_fractional
    CHECK (acceptance_rate IS NULL OR (acceptance_rate > 0 AND acceptance_rate <= 1)),
  DROP CONSTRAINT IF EXISTS school_browser_rows_yield_fractional,
  ADD CONSTRAINT school_browser_rows_yield_fractional
    CHECK (yield_rate IS NULL OR (yield_rate > 0 AND yield_rate <= 1));
