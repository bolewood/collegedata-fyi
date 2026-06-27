-- Public serving performance pass.
--
-- The slow-query export showed three avoidable read-time costs:
--   1. school_merit_profile recalculated latest Section H aggregates on every
--      school lookup.
--   2. site-wide stats repeatedly counted/ordered large public tables.
--   3. common cds_artifacts/cds_manifest access patterns missed covering
--      indexes.
--
-- Keep public API names stable while moving the expensive work behind
-- materialized caches that can be refreshed by service-role jobs.

create index if not exists cds_artifacts_document_kind_created_idx
  on public.cds_artifacts (document_id, kind, created_at desc);

create index if not exists cds_documents_public_manifest_school_name_idx
  on public.cds_documents (removed_at, school_name);

create index if not exists cds_fields_2024_updated_idx
  on public.cds_fields (updated_at desc)
  where year_start >= 2024;

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

drop materialized view if exists public.site_stats_cache;

create materialized view public.site_stats_cache as
with manifest as (
  select *
  from public.cds_manifest
  where participation_status not in ('withdrawn', 'verified_absent')
    and removed_at is null
),
manifest_stats as (
  select
    count(distinct school_id)::integer as total_schools,
    count(*)::integer as total_documents,
    min(canonical_year) filter (where canonical_year ~ '^[0-9]{4}') as earliest_year,
    max(canonical_year) filter (where canonical_year ~ '^[0-9]{4}') as latest_year,
    count(*) filter (where extraction_status = 'extracted')::integer as extracted_count
  from manifest
),
queryable_stats as (
  select
    count(*)::integer as queryable_field_count,
    max(updated_at) as queryable_field_updated_at
  from public.cds_fields
  where year_start >= 2024
),
browser_stats as (
  select
    count(*)::integer as browser_row_count,
    count(*) filter (where sub_institutional is null)::integer as browser_primary_row_count,
    count(distinct school_id) filter (where sub_institutional is null)::integer as browser_school_count,
    max(updated_at) as browser_updated_at
  from public.school_browser_rows
  where year_start >= 2024
),
scorecard_latest as (
  select
    scorecard_data_year,
    refreshed_at
  from public.scorecard_summary
  order by scorecard_data_year desc nulls last
  limit 1
),
scorecard_stats as (
  select count(*)::integer as scorecard_institution_count
  from public.scorecard_summary
),
schema_stats as (
  select count(*)::integer as schema_field_count
  from public.cds_field_definitions
)
select
  1::integer as id,
  manifest_stats.total_schools,
  manifest_stats.total_documents,
  manifest_stats.earliest_year,
  manifest_stats.latest_year,
  manifest_stats.extracted_count,
  case
    when manifest_stats.total_documents > 0
      then round((manifest_stats.extracted_count::numeric / manifest_stats.total_documents) * 100)::integer
    else 0
  end as extraction_pct,
  schema_stats.schema_field_count,
  queryable_stats.queryable_field_count,
  queryable_stats.queryable_field_updated_at,
  browser_stats.browser_row_count,
  browser_stats.browser_primary_row_count,
  browser_stats.browser_school_count,
  browser_stats.browser_updated_at,
  scorecard_stats.scorecard_institution_count,
  scorecard_latest.scorecard_data_year,
  scorecard_latest.refreshed_at as scorecard_refreshed_at,
  now() as refreshed_at
from manifest_stats
cross join schema_stats
cross join queryable_stats
cross join browser_stats
cross join scorecard_stats
left join scorecard_latest on true;

comment on materialized view public.site_stats_cache is
  'One-row public serving cache for homepage/API/browse stats. Refreshed by refresh_site_stats_cache().';

create unique index site_stats_cache_id_uidx
  on public.site_stats_cache (id);

grant select on public.site_stats_cache to anon, authenticated;

create or replace function public.refresh_site_stats_cache()
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  refreshed_count integer;
begin
  refresh materialized view concurrently public.site_stats_cache;
  select count(*) into refreshed_count from public.site_stats_cache;
  return refreshed_count;
end;
$$;

comment on function public.refresh_site_stats_cache() is
  'Refreshes the materialized homepage/API/browse stats serving cache.';

revoke all on function public.refresh_site_stats_cache() from public;
grant execute on function public.refresh_site_stats_cache() to service_role;

create or replace function public.refresh_public_serving_caches()
returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
  merit_count integer;
  stats_count integer;
begin
  merit_count := public.refresh_school_merit_profile_cache();
  stats_count := public.refresh_site_stats_cache();
  return jsonb_build_object(
    'school_merit_profile_cache', merit_count,
    'site_stats_cache', stats_count
  );
end;
$$;

comment on function public.refresh_public_serving_caches() is
  'Refreshes all materialized public serving caches affected by CDS browser projection updates.';

revoke all on function public.refresh_public_serving_caches() from public;
grant execute on function public.refresh_public_serving_caches() to service_role;

create extension if not exists pg_cron with schema extensions;

do $$
begin
  if exists (select 1 from cron.job where jobname = 'refresh-public-serving-caches-hourly') then
    perform cron.unschedule('refresh-public-serving-caches-hourly');
  end if;

  perform cron.schedule(
    'refresh-public-serving-caches-hourly',
    '23 * * * *',
    'select public.refresh_public_serving_caches();'
  );
exception
  when undefined_table or undefined_function or insufficient_privilege then
    raise notice 'refresh-public-serving-caches-hourly cron not scheduled in this environment; call public.refresh_public_serving_caches() after data loads.';
end;
$$;
