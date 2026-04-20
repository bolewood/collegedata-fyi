-- Curated subset of federal College Scorecard data. One row per IPEDS
-- UNITID. Covers every Scorecard field that complements CDS without
-- duplicating it: post-enrollment earnings, federal debt, net-price by
-- income bracket, completion, repayment, and institutional context.
--
-- Filled by tools/scorecard/refresh_summary.py from the Most-Recent
-- Institution-Level CSV released annually by the U.S. Department of
-- Education (https://collegescorecard.ed.gov/data/). Refresh cadence is
-- one bulk upsert per year after each Scorecard release. Per-row data
-- year is preserved in scorecard_data_year so consumers can filter by
-- vintage.
--
-- See docs/research/scorecard-summary-table-v2-plan.md for the field
-- mapping, implementation phases, and the decision log on which
-- Scorecard fields we deliberately exclude.

CREATE TABLE public.scorecard_summary (
  -- ── Identity ─────────────────────────────────────────────────────
  ipeds_id                        text PRIMARY KEY,
  school_name                     text NOT NULL,
  scorecard_data_year             text NOT NULL,
  refreshed_at                    timestamptz NOT NULL DEFAULT now(),

  -- ── Earnings (Treasury/IRS) ─────────────────────────────────────
  -- Post-enrollment earnings, working-not-enrolled (WNE) cohort, at
  -- three time horizons.
  earnings_6yr_median             int,
  earnings_8yr_median             int,
  earnings_10yr_median            int,
  earnings_10yr_p25               int,
  earnings_10yr_p75               int,

  -- ── Debt (NSLDS) ────────────────────────────────────────────────
  median_debt_completers          int,
  median_debt_noncompleters       int,
  median_debt_monthly_payment     numeric(8, 2),
  cumulative_debt_p90             int,
  median_debt_pell                int,
  median_debt_non_pell            int,

  -- ── Net price (IPEDS) ───────────────────────────────────────────
  -- Average net price (sticker minus grants) overall and by family
  -- income bracket. Scorecard publishes these separately by
  -- institutional control (public vs. private nonprofit); the refresh
  -- script picks the right column per row.
  avg_net_price                   int,
  net_price_0_30k                 int,
  net_price_30k_48k               int,
  net_price_48k_75k               int,
  net_price_75k_110k              int,
  net_price_110k_plus             int,

  -- ── Completion (IPEDS + NSLDS) ──────────────────────────────────
  graduation_rate_4yr             numeric(5, 4),
  graduation_rate_6yr             numeric(5, 4),
  graduation_rate_8yr             numeric(5, 4),
  grad_rate_pell                  numeric(5, 4),
  grad_rate_non_pell              numeric(5, 4),
  transfer_out_rate               numeric(5, 4),

  -- ── Repayment (NSLDS + FSA) ─────────────────────────────────────
  repayment_rate_3yr              numeric(5, 4),
  default_rate_3yr                numeric(5, 4),

  -- ── Student profile (IPEDS + NSLDS) ─────────────────────────────
  enrollment                      int,
  pell_grant_rate                 numeric(5, 4),
  federal_loan_rate               numeric(5, 4),
  first_generation_share          numeric(5, 4),
  median_family_income            int,
  female_share                    numeric(5, 4),
  retention_rate_ft               numeric(5, 4),

  -- ── Institutional context (IPEDS + OPE) ─────────────────────────
  carnegie_basic                  int,
  locale                          int,
  historically_black              boolean,
  predominantly_black             boolean,
  hispanic_serving                boolean,
  endowment_end                   bigint,
  instructional_expenditure_fte   int,
  faculty_salary_avg              int
);

COMMENT ON TABLE public.scorecard_summary IS
  'Curated subset of College Scorecard fields that complement CDS data. '
  'One row per IPEDS UNITID. Refreshed annually after the Scorecard '
  'bulk release by tools/scorecard/refresh_summary.py. Join to '
  'cds_manifest via ipeds_id, or query the cds_scorecard view which '
  'pre-joins the two.';

COMMENT ON COLUMN public.scorecard_summary.scorecard_data_year IS
  'Scorecard data vintage (e.g., "2022-23"). Preserved per row so '
  'consumers can filter by vintage and so mixed-vintage refreshes are '
  'tracked accurately.';

-- Anon read-only access. Service role writes via refresh_summary.py.
-- Same policy pattern as cds_documents / cds_artifacts.
ALTER TABLE public.scorecard_summary ENABLE ROW LEVEL SECURITY;

CREATE POLICY scorecard_summary_public_read ON public.scorecard_summary
  FOR SELECT TO anon, authenticated USING (true);

GRANT SELECT ON public.scorecard_summary TO anon, authenticated;
