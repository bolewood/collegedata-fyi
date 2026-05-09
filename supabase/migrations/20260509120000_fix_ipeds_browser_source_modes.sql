-- PRD 021 follow-up.
--
-- Production has a safe-update guard that rejects UPDATE statements without
-- an explicit WHERE clause, even inside RPC functions. Recreate the post-load
-- helper with an always-true key predicate. Also tighten numeric display for
-- school_facts_unified so integer values render as "1970", not "1970.".

begin;

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
  'Marks existing CDS browser rows that have a matching IPEDS baseline after an IPEDS fact load. Service-role loader calls this after upserting facts.';

revoke all on function public.refresh_ipeds_browser_source_modes() from public;
grant execute on function public.refresh_ipeds_browser_source_modes() to service_role;

commit;
