-- PRD 021 follow-up.
--
-- Historical IPEDS now contains every official NCES release from 2004-05
-- through 2024-25. Keep raw long-form analysis queries index-backed, and put
-- the expensive "latest public fact per school + field" window behind a
-- materialized cache while preserving the public ipeds_current_facts view name.

create index if not exists ipeds_facts_field_year_ipeds_idx
  on public.ipeds_facts (field_key, data_year, ipeds_id)
  where public_visible = true;

drop materialized view if exists public.ipeds_current_facts_cache;

create materialized view public.ipeds_current_facts_cache as
with ranked as (
  select
    f.*,
    row_number() over (
      partition by f.unitid, f.field_key
      order by
        f.data_year desc,
        case f.release_type
          when 'final' then 3
          when 'provisional' then 2
          when 'preliminary' then 1
          else 0
        end desc,
        f.created_at desc
    ) as rn
  from public.ipeds_facts f
  where f.public_visible = true
)
select *
from ranked
where rn = 1;

comment on materialized view public.ipeds_current_facts_cache is
  'Materialized latest public IPEDS fact per UNITID + field_key. Refreshed by refresh_ipeds_current_facts_cache() after IPEDS loads.';

create unique index ipeds_current_facts_cache_ipeds_field_uidx
  on public.ipeds_current_facts_cache (ipeds_id, field_key);

create index ipeds_current_facts_cache_school_field_idx
  on public.ipeds_current_facts_cache (school_id, field_key)
  where school_id is not null;

grant select on public.ipeds_current_facts_cache to anon, authenticated;

drop view if exists public.school_facts_unified;
drop view if exists public.ipeds_current_facts;

create view public.ipeds_current_facts
with (security_invoker = true) as
select *
from public.ipeds_current_facts_cache;

comment on view public.ipeds_current_facts is
  'Latest public IPEDS fact per UNITID + field_key. Backed by ipeds_current_facts_cache for public serving performance.';

grant select on public.ipeds_current_facts to anon, authenticated;

create or replace view public.school_facts_unified
with (security_invoker = true) as
select
  d.ipeds_id,
  d.school_id,
  d.school_name,
  d.city,
  d.state,
  d.in_scope,
  f.collection_year,
  f.data_year,
  f.field_key,
  f.field_label,
  coalesce(
    f.value_label,
    f.value_text,
    case
      when f.unit = 'percent' and f.value_numeric is not null
        then trim(trailing '.' from trim(trailing '0' from trim(to_char(f.value_numeric, 'FM999999990.099')))) || '%'
      when f.value_numeric is not null
        then trim(trailing '.' from trim(trailing '0' from trim(to_char(f.value_numeric, 'FM999999999999990.999999'))))
      else null
    end
  ) as display_value,
  f.value_numeric,
  f.value_text,
  f.value_label,
  f.unit,
  f.cohort,
  f.population,
  'ipeds'::text as source_layer,
  f.source_table,
  f.source_variable,
  f.source_title,
  f.release_type,
  f.imputation_flag,
  f.imputation_label,
  f.quality_flag,
  f.definition_alignment,
  f.definition_note,
  f.display_group,
  f.created_at
from public.ipeds_current_facts f
join public.institution_directory d
  on d.ipeds_id = f.ipeds_id
where d.in_scope = true;

comment on view public.school_facts_unified is
  'Public PRD 021 serving view. Exposes source-labeled federal baseline facts for in-scope institutions without hiding provenance or definition alignment.';

grant select on public.school_facts_unified to anon, authenticated;

create or replace function public.refresh_ipeds_current_facts_cache()
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  refreshed_count integer;
begin
  refresh materialized view concurrently public.ipeds_current_facts_cache;
  select count(*) into refreshed_count from public.ipeds_current_facts_cache;
  return refreshed_count;
end;
$$;

comment on function public.refresh_ipeds_current_facts_cache() is
  'Refreshes the materialized latest-IPEDS-facts serving cache after release loads.';

revoke all on function public.refresh_ipeds_current_facts_cache() from public;
grant execute on function public.refresh_ipeds_current_facts_cache() to service_role;

create or replace function public.refresh_ipeds_browser_source_modes()
returns integer
language plpgsql
security invoker
set search_path = public
as $$
declare
  updated_count integer;
begin
  update public.school_browser_rows as sbr
  set
    federal_baseline_available = exists (
      select 1
      from public.ipeds_current_facts f
      where f.ipeds_id = sbr.ipeds_id
      limit 1
    ),
    federal_source_mode = case
      when exists (
        select 1
        from public.ipeds_current_facts f
        where f.ipeds_id = sbr.ipeds_id
        limit 1
      )
        then 'cds_plus_ipeds_baseline'
      else 'cds_only'
    end
  where sbr.document_id is not null;

  get diagnostics updated_count = row_count;
  return updated_count;
end;
$$;

comment on function public.refresh_ipeds_browser_source_modes() is
  'Refreshes public browser rows so CDS schools advertise whether source-labeled IPEDS baseline facts are available.';

revoke all on function public.refresh_ipeds_browser_source_modes() from public;
grant execute on function public.refresh_ipeds_browser_source_modes() to service_role;
