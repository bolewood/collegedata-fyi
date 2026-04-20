-- Consumer-facing joined view: one row per CDS document with the
-- Scorecard outcome fields appended. LEFT JOIN so CDS rows without a
-- Scorecard match (rare for CDS-participating institutions, but
-- possible for newly added or non-Title-IV schools) still appear
-- with NULL scorecard columns.
--
-- The column selection here is deliberately narrower than
-- scorecard_summary.* — it covers the 20-ish fields that answer
-- "should I apply here, and what happens if I do?" in a single API
-- call. Consumers who need the full 43-column Scorecard subset can
-- GET /rest/v1/scorecard_summary directly and join on ipeds_id.

-- security_invoker = true makes the view honor the querying user's RLS
-- policies on the base tables instead of running as the view owner.
-- Without it (Postgres 15+ default is security_invoker = false), a future
-- tightening of scorecard_summary's "USING (true)" policy would not apply
-- to queries routed through this view. Defense in depth — the base-table
-- policies are the intended authority.
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
    sc.grad_rate_non_pell,
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
  'For the full 43-column Scorecard subset query scorecard_summary '
  'directly and join on ipeds_id.';

GRANT SELECT ON public.cds_scorecard TO anon, authenticated;
