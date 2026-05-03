-- PRD 018: public merit-aid profile.
--
-- One latest primary CDS row per school, joined to the curated College
-- Scorecard subset. This view intentionally keeps the CDS H-section facts
-- separate from federal net-price/outcomes context: H2A answers "what the
-- school reported awarding to no-need students," not "what this student will
-- pay."

CREATE VIEW public.school_merit_profile
WITH (security_invoker = true) AS
WITH latest_primary AS (
  SELECT DISTINCT ON (sbr.school_id)
    sbr.*
  FROM public.school_browser_rows sbr
  WHERE sbr.year_start >= 2024
    AND sbr.sub_institutional IS NULL
  ORDER BY
    sbr.school_id,
    sbr.year_start DESC,
    sbr.document_id
),
section_h AS (
  SELECT
    f.document_id,

    MAX(f.value_num) FILTER (WHERE f.field_id = 'H.201' AND f.value_status = 'reported') AS first_year_ft_students,
    MAX(f.value_num) FILTER (WHERE f.field_id = 'H.214' AND f.value_status = 'reported') AS all_ft_undergrads,

    MAX(f.value_num) FILTER (WHERE f.field_id = 'H.109' AND f.value_status = 'reported') AS need_grants_total,
    MAX(f.value_num) FILTER (WHERE f.field_id = 'H.121' AND f.value_status = 'reported') AS non_need_grants_total,

    MAX(f.value_num) FILTER (WHERE f.field_id = 'H.204' AND f.value_status = 'reported') AS aid_recipients_first_year_ft,
    MAX(f.value_num) FILTER (WHERE f.field_id = 'H.217' AND f.value_status = 'reported') AS aid_recipients_all_ft,
    MAX(f.value_num) FILTER (WHERE f.field_id = 'H.210' AND f.value_status = 'reported') AS avg_aid_package_first_year_ft,
    MAX(f.value_num) FILTER (WHERE f.field_id = 'H.223' AND f.value_status = 'reported') AS avg_aid_package_all_ft,
    MAX(f.value_num) FILTER (WHERE f.field_id = 'H.211' AND f.value_status = 'reported') AS avg_need_grant_first_year_ft,
    MAX(f.value_num) FILTER (WHERE f.field_id = 'H.224' AND f.value_status = 'reported') AS avg_need_grant_all_ft,
    MAX(f.value_num) FILTER (WHERE f.field_id = 'H.212' AND f.value_status = 'reported') AS avg_need_self_help_first_year_ft,
    MAX(f.value_num) FILTER (WHERE f.field_id = 'H.225' AND f.value_status = 'reported') AS avg_need_self_help_all_ft,

    MAX(f.value_num) FILTER (WHERE f.field_id = 'H.2A01' AND f.value_status = 'reported') AS non_need_aid_recipients_first_year_ft,
    MAX(f.value_num) FILTER (WHERE f.field_id = 'H.2A02' AND f.value_status = 'reported') AS avg_non_need_grant_first_year_ft,
    MAX(f.value_num) FILTER (WHERE f.field_id = 'H.2A05' AND f.value_status = 'reported') AS non_need_aid_recipients_all_ft,
    MAX(f.value_num) FILTER (WHERE f.field_id = 'H.2A06' AND f.value_status = 'reported') AS avg_non_need_grant_all_ft,

    -- H.6 and H.14 are checkbox-like fields. The numeric truthy branch catches
    -- legacy "1" checkbox marks only; counts/dollar values are not expected
    -- for these field IDs and should be audited upstream if they appear.
    BOOL_OR(
      COALESCE(f.value_bool, false)
      OR LOWER(COALESCE(f.value_text, '')) IN ('x', 'yes', 'true', 'checked')
      OR COALESCE(f.value_num, 0) <> 0
    ) FILTER (WHERE f.field_id = 'H.601' AND f.value_status = 'reported') AS institutional_need_aid_nonresident,
    BOOL_OR(
      COALESCE(f.value_bool, false)
      OR LOWER(COALESCE(f.value_text, '')) IN ('x', 'yes', 'true', 'checked')
      OR COALESCE(f.value_num, 0) <> 0
    ) FILTER (WHERE f.field_id = 'H.602' AND f.value_status = 'reported') AS institutional_non_need_aid_nonresident,
    MAX(f.value_num) FILTER (WHERE f.field_id = 'H.605' AND f.value_status = 'reported') AS avg_international_aid,
    BOOL_OR(
      COALESCE(f.value_bool, false)
      OR LOWER(COALESCE(f.value_text, '')) IN ('x', 'yes', 'true', 'checked')
      OR COALESCE(f.value_num, 0) <> 0
    ) FILTER (WHERE f.field_id IN ('H.1401', 'H.1411') AND f.value_status = 'reported') AS institutional_aid_academics,

    COUNT(DISTINCT f.field_id) FILTER (
      WHERE f.field_id IN ('H.204', 'H.210', 'H.211', 'H.2A01', 'H.2A02')
        AND f.value_status = 'reported'
        AND (f.value_num IS NOT NULL OR f.value_bool IS NOT NULL OR NULLIF(f.value_text, '') IS NOT NULL)
    )::integer AS cds_merit_core_count,
    COUNT(DISTINCT f.field_id) FILTER (
      WHERE f.field_id IN (
        'H.201', 'H.214', 'H.109', 'H.121', 'H.204', 'H.217',
        'H.210', 'H.223', 'H.211', 'H.224', 'H.212', 'H.225',
        'H.2A01', 'H.2A02', 'H.2A05', 'H.2A06',
        'H.601', 'H.602', 'H.605', 'H.1401', 'H.1411'
      )
        AND f.value_status = 'reported'
        AND (f.value_num IS NOT NULL OR f.value_bool IS NOT NULL OR NULLIF(f.value_text, '') IS NOT NULL)
    )::integer AS cds_merit_field_count
  FROM public.cds_fields f
  INNER JOIN latest_primary lp
    ON lp.document_id = f.document_id
  WHERE f.field_id IN (
    'H.201', 'H.214', 'H.109', 'H.121', 'H.204', 'H.217',
    'H.210', 'H.223', 'H.211', 'H.224', 'H.212', 'H.225',
    'H.2A01', 'H.2A02', 'H.2A05', 'H.2A06',
    'H.601', 'H.602', 'H.605', 'H.1401', 'H.1411'
  )
  GROUP BY f.document_id
)
SELECT
  lp.document_id,
  lp.school_id,
  lp.school_name,
  lp.sub_institutional,
  lp.ipeds_id,
  lp.canonical_year,
  lp.year_start,
  lp.schema_version,
  lp.source_format,
  lp.producer,
  lp.producer_version,
  lp.data_quality_flag,
  lp.archive_url,

  h.first_year_ft_students,
  h.all_ft_undergrads,
  h.need_grants_total,
  h.non_need_grants_total,
  h.aid_recipients_first_year_ft,
  h.aid_recipients_all_ft,
  h.avg_aid_package_first_year_ft,
  h.avg_aid_package_all_ft,
  h.avg_need_grant_first_year_ft,
  h.avg_need_grant_all_ft,
  h.avg_need_self_help_first_year_ft,
  h.avg_need_self_help_all_ft,
  h.non_need_aid_recipients_first_year_ft,
  h.avg_non_need_grant_first_year_ft,
  h.non_need_aid_recipients_all_ft,
  h.avg_non_need_grant_all_ft,
  CASE
    WHEN h.first_year_ft_students > 0 AND h.non_need_aid_recipients_first_year_ft IS NOT NULL
      THEN h.non_need_aid_recipients_first_year_ft / h.first_year_ft_students
    ELSE NULL
  END AS non_need_aid_share_first_year_ft,
  CASE
    WHEN h.all_ft_undergrads > 0 AND h.non_need_aid_recipients_all_ft IS NOT NULL
      THEN h.non_need_aid_recipients_all_ft / h.all_ft_undergrads
    ELSE NULL
  END AS non_need_aid_share_all_ft,
  h.institutional_need_aid_nonresident,
  h.institutional_non_need_aid_nonresident,
  h.avg_international_aid,
  h.institutional_aid_academics,
  COALESCE(h.cds_merit_core_count, 0) AS cds_merit_core_count,
  COALESCE(h.cds_merit_field_count, 0) AS cds_merit_field_count,
  CASE
    WHEN COALESCE(h.cds_merit_core_count, 0) >= 4 AND h.avg_non_need_grant_first_year_ft IS NOT NULL THEN 'strong'
    WHEN COALESCE(h.cds_merit_core_count, 0) >= 3 THEN 'partial'
    WHEN COALESCE(h.cds_merit_field_count, 0) > 0 THEN 'limited'
    ELSE 'missing'
  END AS merit_profile_quality,

  sc.scorecard_data_year,
  sc.earnings_6yr_median,
  sc.earnings_8yr_median,
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
  sc.pell_grant_rate,
  sc.federal_loan_rate,
  sc.retention_rate_ft
FROM latest_primary lp
LEFT JOIN section_h h
  ON h.document_id = lp.document_id
LEFT JOIN public.scorecard_summary sc
  ON sc.ipeds_id = lp.ipeds_id;

COMMENT ON VIEW public.school_merit_profile IS
  'Latest primary 2024-25+ CDS Section H merit/need-aid facts per school, left-joined to selected College Scorecard affordability and outcomes fields. H2A non-need award data is source-reported institutional scholarship/grant data, not a personalized estimate.';

GRANT SELECT ON public.school_merit_profile TO anon, authenticated;
