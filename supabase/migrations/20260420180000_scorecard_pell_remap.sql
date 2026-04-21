-- Adapt scorecard_summary + cds_scorecard to the March 2026 Scorecard
-- data dictionary. Three columns from the original v2 plan were sourced
-- from Scorecard fields that have since been renamed or removed:
--
--   median_debt_pell        ← was GRAD_DEBT_MDN_PELL, now PELL_DEBT_MDN
--                              (column kept; refresh_summary.py remaps source)
--   median_debt_non_pell    ← was GRAD_DEBT_MDN_NOPELL, no replacement
--                              (Scorecard no longer publishes a single
--                              non-Pell median; column dropped)
--   grad_rate_non_pell      ← was C150_4_NONPELL, no direct replacement
--                              (split into C150_4_LOANNOPELL +
--                              C150_4_NOLOANNOPELL; computing a synthetic
--                              weighted average isn't worth the brittleness;
--                              column dropped)
--
-- Anyone who needs non-Pell debt or completion can query Scorecard
-- directly via the join recipe in docs/research/scorecard-join-recipe.md.
--
-- Table is empty at migration time (initial refresh hasn't run yet),
-- so DROP COLUMN is a no-op for data and there's no backfill to worry about.

-- cds_scorecard view depends on the columns being dropped, so the view
-- must come down first. cds_manifest (the other dependency) is
-- unchanged here.
DROP VIEW IF EXISTS public.cds_scorecard;

ALTER TABLE public.scorecard_summary DROP COLUMN IF EXISTS median_debt_non_pell;
ALTER TABLE public.scorecard_summary DROP COLUMN IF EXISTS grad_rate_non_pell;

CREATE VIEW public.cds_scorecard
WITH (security_invoker = true) AS
  SELECT
    -- CDS side
    m.document_id,
    m.school_id,
    m.school_name,
    m.ipeds_id,
    m.canonical_year                    AS cds_year,
    m.source_format,
    m.extraction_status,
    m.data_quality_flag,
    m.latest_canonical_artifact_id,
    m.source_storage_path,

    -- Scorecard side (selected outcome fields only)
    sc.scorecard_data_year,
    sc.earnings_10yr_median,
    sc.earnings_10yr_p25,
    sc.earnings_10yr_p75,
    sc.median_debt_completers,
    sc.median_debt_monthly_payment,
    sc.avg_net_price,
    sc.net_price_0_30k,
    sc.net_price_30k_48k,
    sc.net_price_48k_75k,
    sc.net_price_75k_110k,
    sc.net_price_110k_plus,
    sc.graduation_rate_6yr,
    sc.grad_rate_pell,
    sc.repayment_rate_3yr,
    sc.default_rate_3yr,
    sc.pell_grant_rate,
    sc.federal_loan_rate,
    sc.first_generation_share,
    sc.median_family_income,
    sc.retention_rate_ft,
    sc.endowment_end,
    sc.instructional_expenditure_fte
  FROM public.cds_manifest m
  LEFT JOIN public.scorecard_summary sc
    ON sc.ipeds_id = m.ipeds_id;

COMMENT ON VIEW public.cds_scorecard IS
  'CDS manifest left-joined with the curated College Scorecard subset. '
  'One row per CDS document. NULL scorecard columns mean the school '
  'has no Scorecard match (rare for CDS-participating institutions). '
  'For the full Scorecard subset query scorecard_summary directly and '
  'join on ipeds_id.';

GRANT SELECT ON public.cds_scorecard TO anon, authenticated;
