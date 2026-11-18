-- PRD 036: other_info, display-only sourced facts with no typed field.
--
-- versions[].other_info in the YAML is null or up to 6 {text, source_ref}
-- entries. The public view gains an other_info jsonb column: '[]' when absent,
-- else [{text, source_ref, source_url}], so a consumer needs no join. The quoted
-- excerpt stays out of the public payload (same rule as evidence).
--
-- scholarship_directory reads scholarship_directory_cache, a materialized view,
-- and a materialized view cannot gain a column in place. So this drops the
-- view, then the cache, and recreates both with the new column placed after
-- evidence, plus the indexes, comments and grants the first migration set. The
-- cache is populated when it is created, so no refresh is needed to serve rows.
-- refresh_scholarship_directory_cache() is plpgsql and binds the name at call
-- time, so it is untouched. Nothing else depends on either object.
--
-- Deploy order: this migration must be applied (supabase db push from main)
-- before the web build that selects other_info ships, or PostgREST rejects the
-- unknown column, every scholarship card is hidden, and school pages rendered in
-- that gap stay cached for up to 7 days. The web change therefore ships in a later PR.

-- One explicit transaction: the public API never sees the view missing, and a
-- dependent object that exists only in production makes the plain drop fail and
-- roll everything back.
begin;

drop view public.scholarship_directory;
drop materialized view public.scholarship_directory_cache;

create materialized view public.scholarship_directory_cache as
with heads as (
  select distinct on (v.program_id) v.*
  from public.scholarship_program_versions v
  where v.is_published
    and v.verification_status <> 'unverified'
  order by
    v.program_id,
    coalesce(
      v.entry_year,
      public.scholarship_cycle_year(v.cycle_through_date),
      public.scholarship_cycle_year(v.source_retrieved_at)
    ) desc nulls last,
    (v.entry_year is null),
    v.version_id
)
select
  p.program_id,
  s.school ->> 'school_id' as school_id,
  s.school ->> 'ipeds_id' as ipeds_id,
  (
    select coalesce(array_agg(x ->> 'school_id' order by ord), '{}')
    from jsonb_array_elements(p.participating_schools) with ordinality as e(x, ord)
  ) as participating_school_ids,
  p.official_name,
  p.aliases,
  p.program_family,
  p.awarding_authority,
  p.status as program_status,
  p.applicable_campuses,
  p.related_programs,

  h.version_id,
  h.entry_year,
  h.entry_year_label,
  h.entry_terms,
  h.source_cohort_text,
  h.verification_status,
  h.last_reviewed_at,
  h.reviewed_by,
  h.owner_spot_checked,
  h.program_status_for_entry,

  h.coverages,
  h.selection_modes,
  h.residencies,
  h.national_merit_statuses,
  h.statuses_required,
  h.need_roles,
  h.separate_application,
  h.deadline_months,
  h.key_deadline,
  h.cycle_through_date,
  h.source_retrieved_at,

  h.offers,
  nullif(h.record -> 'application', 'null'::jsonb) as application,
  nullif(h.record -> 'renewal_rules', 'null'::jsonb) as renewal_rules,
  nullif(h.record -> 'stacking_rules', 'null'::jsonb) as stacking_rules,
  coalesce(nullif(h.record -> 'award_counts', 'null'::jsonb), '[]'::jsonb) as award_counts,
  coalesce(src.sources, '[]'::jsonb) as sources,
  coalesce(ev.evidence, '[]'::jsonb) as evidence,
  coalesce(oi.other_info, '[]'::jsonb) as other_info,

  lc.checked_at as last_check_at,
  lc.result as last_check_result,
  lc.needs_review
from heads h
join public.scholarship_programs p
  on p.program_id = h.program_id
cross join lateral jsonb_array_elements(
  case
    when jsonb_array_length(p.participating_schools) > 0 then p.participating_schools
    else jsonb_build_array(jsonb_build_object('school_id', p.school_id, 'ipeds_id', p.ipeds_id))
  end
) as s(school)
left join lateral (
  select jsonb_agg(
    jsonb_build_object(
      'source_id', so.source_id,
      'url', so.url,
      'authority', so.authority,
      'retrieved_at', so.retrieved_at,
      'archive_url', so.archive_url
    )
    order by so.source_id
  ) as sources
  from public.scholarship_sources so
  where so.program_id = h.program_id
    and so.version_id = h.version_id
) src on true
left join lateral (
  -- Locators only: field_path, source_ref, locator, value_status. Never the excerpt.
  select jsonb_agg(
    jsonb_build_object(
      'field_path', e.item -> 'field_path',
      'source_ref', e.item -> 'source_ref',
      'locator', e.item -> 'locator',
      'value_status', e.item -> 'value_status'
    )
    order by e.ord
  ) as evidence
  from jsonb_array_elements(coalesce(nullif(h.record -> 'field_evidence', 'null'::jsonb), '[]'::jsonb))
    with ordinality as e(item, ord)
) ev on true
left join lateral (
  -- Display-only facts with no typed home. Text, which source, and that
  -- source's URL, so a consumer needs no join. Never the quoted excerpt.
  select jsonb_agg(
    jsonb_build_object(
      'text', o.item ->> 'text',
      'source_ref', o.item ->> 'source_ref',
      'source_url', so.url
    )
    order by o.ord
  ) as other_info
  from jsonb_array_elements(coalesce(nullif(h.record -> 'other_info', 'null'::jsonb), '[]'::jsonb))
    with ordinality as o(item, ord)
  left join public.scholarship_sources so
    on so.program_id = h.program_id
   and so.version_id = h.version_id
   and so.source_id = o.item ->> 'source_ref'
) oi on true
left join lateral (
  select c.checked_at, c.result, c.needs_review
  from public.scholarship_version_checks c
  where c.program_id = h.program_id
    and c.version_id = h.version_id
  order by c.checked_at desc, c.id desc
  limit 1
) lc on true;

comment on materialized view public.scholarship_directory_cache is
  'PRD 036 materialized public rows: latest non-unverified chain-head version per program, one row per participating school. Refreshed by refresh_scholarship_directory_cache().';

-- REFRESH ... CONCURRENTLY needs a unique index.
create unique index scholarship_directory_cache_program_school_uidx
  on public.scholarship_directory_cache (program_id, school_id);

create index scholarship_directory_cache_school_idx
  on public.scholarship_directory_cache (school_id);
create index scholarship_directory_cache_coverages_idx
  on public.scholarship_directory_cache using gin (coverages);
create index scholarship_directory_cache_nm_idx
  on public.scholarship_directory_cache using gin (national_merit_statuses);


create view public.scholarship_directory
with (security_invoker = true) as
select
  c.program_id,
  c.school_id,
  c.ipeds_id,
  c.participating_school_ids,
  c.official_name,
  c.aliases,
  c.program_family,
  c.awarding_authority,
  c.program_status,
  c.applicable_campuses,
  c.related_programs,

  c.version_id,
  c.entry_year,
  c.entry_year_label,
  c.entry_terms,
  c.source_cohort_text,
  c.verification_status,
  public.scholarship_freshness_status(
    c.entry_year,
    c.verification_status,
    c.cycle_through_date,
    c.last_reviewed_at,
    c.last_check_result,
    c.needs_review
  ) as freshness_status,
  public.scholarship_cycle_basis(c.entry_year, c.cycle_through_date) as cycle_basis,
  c.cycle_through_date,
  public.scholarship_current_entry_year() as current_entry_year,
  c.last_reviewed_at,
  c.reviewed_by,
  c.owner_spot_checked,
  c.program_status_for_entry,

  c.coverages,
  c.selection_modes,
  c.residencies,
  c.national_merit_statuses,
  c.statuses_required,
  c.need_roles,
  c.separate_application,
  c.deadline_months,
  c.key_deadline,
  c.source_retrieved_at,

  c.offers,
  c.application,
  c.renewal_rules,
  c.stacking_rules,
  c.award_counts,
  c.sources,
  c.evidence,
  c.other_info,

  c.last_check_at,
  c.last_check_result,
  c.needs_review,

  'CC-BY-SA-4.0'::text as license,
  'Scholarship program data from collegedata.fyi (https://collegedata.fyi/scholarships), CC BY-SA 4.0. Terms as published by each school; see the source link on each record.'::text as attribution
from public.scholarship_directory_cache c;

comment on view public.scholarship_directory is
  'PRD 036 named scholarship programs: the latest non-unverified version per program, one row per participating school, with freshness_status computed at query time. Every row carries license and attribution; please display the attribution. Backed by scholarship_directory_cache.';

-- Explicit grants rather than inherited defaults: read-only for the public roles.
revoke all on public.scholarship_directory_cache from public, anon, authenticated;
grant select on public.scholarship_directory_cache to anon, authenticated;
revoke all on public.scholarship_directory from public, anon, authenticated;
grant select on public.scholarship_directory to anon, authenticated;

commit;
