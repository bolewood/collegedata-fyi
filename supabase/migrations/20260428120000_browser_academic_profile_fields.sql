-- PRD 012: first browser academic-profile backend expansion.
--
-- Adds SAT/ACT submission-rate and percentile columns that cleared the
-- post-Tier-4-v0.3 measurement gate. GPA and class-rank fields intentionally
-- remain in the long-form cds_fields substrate until their interpretation is
-- safer for cross-school browser filtering.

ALTER TABLE public.school_browser_rows
  ADD COLUMN sat_submit_rate numeric(5, 4),
  ADD COLUMN act_submit_rate numeric(5, 4),
  ADD COLUMN sat_composite_p25 integer,
  ADD COLUMN sat_composite_p50 integer,
  ADD COLUMN sat_composite_p75 integer,
  ADD COLUMN sat_ebrw_p25 integer,
  ADD COLUMN sat_ebrw_p50 integer,
  ADD COLUMN sat_ebrw_p75 integer,
  ADD COLUMN sat_math_p25 integer,
  ADD COLUMN sat_math_p50 integer,
  ADD COLUMN sat_math_p75 integer,
  ADD COLUMN act_composite_p25 integer,
  ADD COLUMN act_composite_p50 integer,
  ADD COLUMN act_composite_p75 integer;

ALTER TABLE public.school_browser_rows
  ADD CONSTRAINT school_browser_rows_sat_submit_rate_fractional
    CHECK (sat_submit_rate IS NULL OR (sat_submit_rate >= 0 AND sat_submit_rate <= 1)),
  ADD CONSTRAINT school_browser_rows_act_submit_rate_fractional
    CHECK (act_submit_rate IS NULL OR (act_submit_rate >= 0 AND act_submit_rate <= 1)),
  ADD CONSTRAINT school_browser_rows_sat_composite_p25_range
    CHECK (sat_composite_p25 IS NULL OR (sat_composite_p25 >= 400 AND sat_composite_p25 <= 1600)),
  ADD CONSTRAINT school_browser_rows_sat_composite_p50_range
    CHECK (sat_composite_p50 IS NULL OR (sat_composite_p50 >= 400 AND sat_composite_p50 <= 1600)),
  ADD CONSTRAINT school_browser_rows_sat_composite_p75_range
    CHECK (sat_composite_p75 IS NULL OR (sat_composite_p75 >= 400 AND sat_composite_p75 <= 1600)),
  ADD CONSTRAINT school_browser_rows_sat_ebrw_p25_range
    CHECK (sat_ebrw_p25 IS NULL OR (sat_ebrw_p25 >= 200 AND sat_ebrw_p25 <= 800)),
  ADD CONSTRAINT school_browser_rows_sat_ebrw_p50_range
    CHECK (sat_ebrw_p50 IS NULL OR (sat_ebrw_p50 >= 200 AND sat_ebrw_p50 <= 800)),
  ADD CONSTRAINT school_browser_rows_sat_ebrw_p75_range
    CHECK (sat_ebrw_p75 IS NULL OR (sat_ebrw_p75 >= 200 AND sat_ebrw_p75 <= 800)),
  ADD CONSTRAINT school_browser_rows_sat_math_p25_range
    CHECK (sat_math_p25 IS NULL OR (sat_math_p25 >= 200 AND sat_math_p25 <= 800)),
  ADD CONSTRAINT school_browser_rows_sat_math_p50_range
    CHECK (sat_math_p50 IS NULL OR (sat_math_p50 >= 200 AND sat_math_p50 <= 800)),
  ADD CONSTRAINT school_browser_rows_sat_math_p75_range
    CHECK (sat_math_p75 IS NULL OR (sat_math_p75 >= 200 AND sat_math_p75 <= 800)),
  ADD CONSTRAINT school_browser_rows_act_composite_p25_range
    CHECK (act_composite_p25 IS NULL OR (act_composite_p25 >= 1 AND act_composite_p25 <= 36)),
  ADD CONSTRAINT school_browser_rows_act_composite_p50_range
    CHECK (act_composite_p50 IS NULL OR (act_composite_p50 >= 1 AND act_composite_p50 <= 36)),
  ADD CONSTRAINT school_browser_rows_act_composite_p75_range
    CHECK (act_composite_p75 IS NULL OR (act_composite_p75 >= 1 AND act_composite_p75 <= 36));

COMMENT ON COLUMN public.school_browser_rows.sat_submit_rate IS
  'Fraction of first-time first-year students submitting SAT scores, from CDS C.901. Stored 0..1.';
COMMENT ON COLUMN public.school_browser_rows.act_submit_rate IS
  'Fraction of first-time first-year students submitting ACT scores, from CDS C.902. Stored 0..1.';
COMMENT ON COLUMN public.school_browser_rows.sat_composite_p25 IS
  'Reported SAT Composite 25th percentile for score submitters, from CDS C.905.';
COMMENT ON COLUMN public.school_browser_rows.sat_composite_p50 IS
  'Reported SAT Composite 50th percentile for score submitters, from CDS C.906.';
COMMENT ON COLUMN public.school_browser_rows.sat_composite_p75 IS
  'Reported SAT Composite 75th percentile for score submitters, from CDS C.907.';
COMMENT ON COLUMN public.school_browser_rows.act_composite_p25 IS
  'Reported ACT Composite 25th percentile for score submitters, from CDS C.914.';
COMMENT ON COLUMN public.school_browser_rows.act_composite_p50 IS
  'Reported ACT Composite 50th percentile for score submitters, from CDS C.915.';
COMMENT ON COLUMN public.school_browser_rows.act_composite_p75 IS
  'Reported ACT Composite 75th percentile for score submitters, from CDS C.916.';
