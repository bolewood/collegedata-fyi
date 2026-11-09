-- Split the CDS H14 "academics" criterion into its non-need and need-based
-- checkboxes.
--
-- school_merit_profile.institutional_aid_academics ORs H.1401 (academics is a
-- criterion for institutional NON-need aid) with H.1411 (academics is a
-- criterion for institutional NEED-based aid). The school page labeled it
-- "Academic merit aid checked", which is wrong for a school that only checked
-- the need-based box (2 of 518 schools at the time of writing).
--
-- Adds merit_criteria_academics (H.1401) and need_criteria_academics (H.1411).
-- institutional_aid_academics keeps its old meaning for API compatibility and
-- is marked deprecated. The materialized cache is rebuilt with the same
-- definition as 20260627133000_materialize_public_serving_paths.sql apart from
-- the two new columns; nothing else depends on the view.

drop view if exists public.school_merit_profile;
drop materialized view if exists public.school_merit_profile_cache;

create materialized view public.school_merit_profile_cache as
with latest_primary as (
  select distinct on (sbr.school_id)
    sbr.*
  from public.school_browser_rows sbr
  where sbr.year_start >= 2024
    and sbr.sub_institutional is null
  order by
    sbr.school_id,
    sbr.year_start desc,
    sbr.document_id
),
section_h as (
  select
    f.document_id,

    max(f.value_num) filter (where f.field_id = 'H.201' and f.value_status = 'reported') as first_year_ft_students,
    max(f.value_num) filter (where f.field_id = 'H.214' and f.value_status = 'reported') as all_ft_undergrads,

    max(f.value_num) filter (where f.field_id = 'H.109' and f.value_status = 'reported') as need_grants_total,
    max(f.value_num) filter (where f.field_id = 'H.121' and f.value_status = 'reported') as non_need_grants_total,

    max(f.value_num) filter (where f.field_id = 'H.204' and f.value_status = 'reported') as aid_recipients_first_year_ft,
    max(f.value_num) filter (where f.field_id = 'H.217' and f.value_status = 'reported') as aid_recipients_all_ft,
    max(f.value_num) filter (where f.field_id = 'H.210' and f.value_status = 'reported') as avg_aid_package_first_year_ft,
    max(f.value_num) filter (where f.field_id = 'H.223' and f.value_status = 'reported') as avg_aid_package_all_ft,
    max(f.value_num) filter (where f.field_id = 'H.211' and f.value_status = 'reported') as avg_need_grant_first_year_ft,
    max(f.value_num) filter (where f.field_id = 'H.224' and f.value_status = 'reported') as avg_need_grant_all_ft,
    max(f.value_num) filter (where f.field_id = 'H.212' and f.value_status = 'reported') as avg_need_self_help_first_year_ft,
    max(f.value_num) filter (where f.field_id = 'H.225' and f.value_status = 'reported') as avg_need_self_help_all_ft,

    max(f.value_num) filter (where f.field_id = 'H.2A01' and f.value_status = 'reported') as non_need_aid_recipients_first_year_ft,
    max(f.value_num) filter (where f.field_id = 'H.2A02' and f.value_status = 'reported') as avg_non_need_grant_first_year_ft,
    max(f.value_num) filter (where f.field_id = 'H.2A05' and f.value_status = 'reported') as non_need_aid_recipients_all_ft,
    max(f.value_num) filter (where f.field_id = 'H.2A06' and f.value_status = 'reported') as avg_non_need_grant_all_ft,

    bool_or(
      coalesce(f.value_bool, false)
      or lower(coalesce(f.value_text, '')) in ('x', 'yes', 'true', 'checked')
      or coalesce(f.value_num, 0) <> 0
    ) filter (where f.field_id = 'H.601' and f.value_status = 'reported') as institutional_need_aid_nonresident,
    bool_or(
      coalesce(f.value_bool, false)
      or lower(coalesce(f.value_text, '')) in ('x', 'yes', 'true', 'checked')
      or coalesce(f.value_num, 0) <> 0
    ) filter (where f.field_id = 'H.602' and f.value_status = 'reported') as institutional_non_need_aid_nonresident,
    max(f.value_num) filter (where f.field_id = 'H.605' and f.value_status = 'reported') as avg_international_aid,
    bool_or(
      coalesce(f.value_bool, false)
      or lower(coalesce(f.value_text, '')) in ('x', 'yes', 'true', 'checked')
      or coalesce(f.value_num, 0) <> 0
    ) filter (where f.field_id in ('H.1401', 'H.1411') and f.value_status = 'reported') as institutional_aid_academics,
    bool_or(
      coalesce(f.value_bool, false)
      or lower(coalesce(f.value_text, '')) in ('x', 'yes', 'true', 'checked')
      or coalesce(f.value_num, 0) <> 0
    ) filter (where f.field_id in ('H.1401') and f.value_status = 'reported') as merit_criteria_academics,
    bool_or(
      coalesce(f.value_bool, false)
      or lower(coalesce(f.value_text, '')) in ('x', 'yes', 'true', 'checked')
      or coalesce(f.value_num, 0) <> 0
    ) filter (where f.field_id in ('H.1411') and f.value_status = 'reported') as need_criteria_academics,

    count(distinct f.field_id) filter (
      where f.field_id in ('H.204', 'H.210', 'H.211', 'H.2A01', 'H.2A02')
        and f.value_status = 'reported'
        and (f.value_num is not null or f.value_bool is not null or nullif(f.value_text, '') is not null)
    )::integer as cds_merit_core_count,
    count(distinct f.field_id) filter (
      where f.field_id in (
        'H.201', 'H.214', 'H.109', 'H.121', 'H.204', 'H.217',
        'H.210', 'H.223', 'H.211', 'H.224', 'H.212', 'H.225',
        'H.2A01', 'H.2A02', 'H.2A05', 'H.2A06',
        'H.601', 'H.602', 'H.605', 'H.1401', 'H.1411'
      )
        and f.value_status = 'reported'
        and (f.value_num is not null or f.value_bool is not null or nullif(f.value_text, '') is not null)
    )::integer as cds_merit_field_count
  from public.cds_fields f
  inner join latest_primary lp
    on lp.document_id = f.document_id
  where f.field_id in (
    'H.201', 'H.214', 'H.109', 'H.121', 'H.204', 'H.217',
    'H.210', 'H.223', 'H.211', 'H.224', 'H.212', 'H.225',
    'H.2A01', 'H.2A02', 'H.2A05', 'H.2A06',
    'H.601', 'H.602', 'H.605', 'H.1401', 'H.1411'
  )
  group by f.document_id
)
select
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
  case
    when h.first_year_ft_students > 0 and h.non_need_aid_recipients_first_year_ft is not null
      then h.non_need_aid_recipients_first_year_ft / h.first_year_ft_students
    else null
  end as non_need_aid_share_first_year_ft,
  case
    when h.all_ft_undergrads > 0 and h.non_need_aid_recipients_all_ft is not null
      then h.non_need_aid_recipients_all_ft / h.all_ft_undergrads
    else null
  end as non_need_aid_share_all_ft,
  h.institutional_need_aid_nonresident,
  h.institutional_non_need_aid_nonresident,
  h.avg_international_aid,
  h.institutional_aid_academics,
  h.merit_criteria_academics,
  h.need_criteria_academics,
  coalesce(h.cds_merit_core_count, 0) as cds_merit_core_count,
  coalesce(h.cds_merit_field_count, 0) as cds_merit_field_count,
  case
    when coalesce(h.cds_merit_core_count, 0) >= 4 and h.avg_non_need_grant_first_year_ft is not null then 'strong'
    when coalesce(h.cds_merit_core_count, 0) >= 3 then 'partial'
    when coalesce(h.cds_merit_field_count, 0) > 0 then 'limited'
    else 'missing'
  end as merit_profile_quality,

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
from latest_primary lp
left join section_h h
  on h.document_id = lp.document_id
left join public.scorecard_summary sc
  on sc.ipeds_id = lp.ipeds_id;

comment on materialized view public.school_merit_profile_cache is
  'Materialized latest primary 2024-25+ CDS Section H merit/need-aid facts per school, with selected College Scorecard affordability and outcomes fields.';

create unique index school_merit_profile_cache_school_uidx
  on public.school_merit_profile_cache (school_id);

create unique index school_merit_profile_cache_document_uidx
  on public.school_merit_profile_cache (document_id);

grant select on public.school_merit_profile_cache to anon, authenticated;

drop view if exists public.school_merit_profile;

create view public.school_merit_profile
with (security_invoker = true) as
select *
from public.school_merit_profile_cache;

comment on view public.school_merit_profile is
  'Latest primary 2024-25+ CDS Section H merit/need-aid facts per school. Backed by school_merit_profile_cache for public serving performance.';

grant select on public.school_merit_profile to anon, authenticated;

create or replace function public.refresh_school_merit_profile_cache()
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  refreshed_count integer;
begin
  refresh materialized view concurrently public.school_merit_profile_cache;
  select count(*) into refreshed_count from public.school_merit_profile_cache;
  return refreshed_count;
end;
$$;

comment on function public.refresh_school_merit_profile_cache() is
  'Refreshes the materialized school_merit_profile serving cache after browser projection updates.';

revoke all on function public.refresh_school_merit_profile_cache() from public;
grant execute on function public.refresh_school_merit_profile_cache() to service_role;

comment on column public.school_merit_profile_cache.merit_criteria_academics is
  'CDS H.1401: academics is a criterion for institutional non-need (merit) scholarships/grants.';
comment on column public.school_merit_profile_cache.need_criteria_academics is
  'CDS H.1411: academics is a criterion for institutional need-based scholarships/grants.';
comment on column public.school_merit_profile_cache.institutional_aid_academics is
  'Deprecated: H.1401 OR H.1411 (non-need or need-based). Use merit_criteria_academics / need_criteria_academics.';
