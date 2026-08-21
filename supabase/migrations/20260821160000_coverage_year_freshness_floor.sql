-- Treat a successfully re-verified old CDS year as stale, not current.
--
-- archive-enqueue weekly-confirms the same one-file PDF seed
-- (unchanged_verified). derive_coverage_status then called that
-- cds_available_current even when the latest extracted year was
-- 2022-23. Public coverage should not look healthy when the file we
-- hold is older than the freshness floor used by the finder stuck-PDF
-- job (tools/finder/stuck_pdf_seeds.py default_min_fresh_year).

begin;

create or replace function public.cds_freshness_floor(p_as_of date default current_date)
returns text
language sql
immutable
set search_path = public
as $$
  -- Before September: prior complete cycle (Aug 2026 → 2024-25).
  -- From September: previous academic year (Sep 2026 → 2025-26).
  select case
    when extract(month from p_as_of) >= 9 then
      (extract(year from p_as_of)::int - 1)::text
      || '-'
      || right((extract(year from p_as_of)::int)::text, 2)
    else
      (extract(year from p_as_of)::int - 2)::text
      || '-'
      || right((extract(year from p_as_of)::int - 1)::text, 2)
  end;
$$;

comment on function public.cds_freshness_floor(date) is
  'Canonical CDS year that should already be on file. Matches tools/finder/stuck_pdf_seeds.default_min_fresh_year. Used by refresh_institution_cds_coverage to demote cds_available_current → cds_available_stale.';

revoke all on function public.cds_freshness_floor(date) from public;
grant execute on function public.cds_freshness_floor(date) to anon, authenticated, service_role;

create or replace function public.refresh_institution_cds_coverage()
returns table (rows_written int, duration_ms int)
language plpgsql
security invoker
set search_path = public
as $$
declare
  started timestamptz := clock_timestamp();
  written int;
begin
  truncate table public.institution_cds_coverage;

  with
    cds_extracted as (
      select distinct on (school_id)
        school_id,
        cds_year             as latest_extracted_year,
        id                   as latest_document_id,
        source_url           as latest_extracted_source_url
      from public.cds_documents
      where extraction_status = 'extracted'
      order by school_id, cds_year desc
    ),
    cds_found as (
      select distinct on (school_id)
        school_id,
        cds_year             as latest_found_year,
        extraction_status    as latest_found_extraction_status
      from public.cds_documents
      where source_url is not null
      order by school_id, cds_year desc
    ),
    queue_latest as (
      select distinct on (school_id)
        school_id,
        last_outcome,
        processed_at
      from public.archive_queue
      where status in ('done', 'failed_permanent')
        and last_outcome is not null
        and processed_at is not null
      order by school_id, processed_at desc
    ),
    crosswalk_aliases as (
      select
        ipeds_id,
        array_agg(distinct alias) filter (where source <> 'redirect') as aliases
      from public.institution_slug_crosswalk
      group by ipeds_id
    ),
    resolved_raw as (
      select
        d.ipeds_id,
        d.school_id,
        d.school_name,
        d.city,
        d.state,
        d.website_url,
        d.undergraduate_enrollment,
        d.scorecard_data_year,
        coalesce(ca.aliases, '{}'::text[])              as aliases,
        ce.latest_extracted_year,
        ce.latest_document_id,
        ce.latest_extracted_source_url,
        cf.latest_found_year,
        cf.latest_found_extraction_status,
        q.last_outcome,
        q.processed_at                                    as last_checked_at,
        o.public_note                                     as override_note,
        coalesce(
          o.status,
          public.derive_coverage_status(
            d.in_scope,
            ce.latest_extracted_year,
            cf.latest_found_year,
            cf.latest_found_extraction_status,
            q.last_outcome
          )
        )                                                 as derived_status
      from public.institution_directory d
      left join cds_extracted ce on ce.school_id = d.school_id
      left join cds_found cf on cf.school_id = d.school_id
      left join queue_latest q on q.school_id = d.school_id
      left join crosswalk_aliases ca on ca.ipeds_id = d.ipeds_id
      left join public.institution_cds_coverage_overrides o on o.ipeds_id = d.ipeds_id
    ),
    resolved as (
      select
        ipeds_id,
        school_id,
        school_name,
        city,
        state,
        website_url,
        undergraduate_enrollment,
        scorecard_data_year,
        aliases,
        latest_extracted_year,
        latest_document_id,
        latest_extracted_source_url,
        latest_found_year,
        latest_found_extraction_status,
        last_outcome,
        last_checked_at,
        override_note,
        case
          when derived_status = 'cds_available_current'
               and latest_extracted_year is not null
               and latest_extracted_year < public.cds_freshness_floor()
            then 'cds_available_stale'::public.coverage_status_t
          else derived_status
        end as coverage_status
      from resolved_raw
    )
  insert into public.institution_cds_coverage (
    ipeds_id,
    school_id,
    school_name,
    aliases,
    city,
    state,
    website_url,
    undergraduate_enrollment,
    scorecard_data_year,
    coverage_status,
    coverage_label,
    coverage_summary,
    latest_available_cds_year,
    latest_found_cds_year,
    latest_attempted_year,
    latest_document_id,
    latest_public_source_url,
    latest_field_count,
    last_checked_at,
    can_submit_source,
    search_text,
    updated_at
  )
  select
    ipeds_id,
    school_id,
    school_name,
    aliases,
    city,
    state,
    website_url,
    undergraduate_enrollment,
    scorecard_data_year,
    coverage_status,
    public.coverage_status_label(coverage_status),
    public.coverage_status_summary(
      school_name,
      coverage_status,
      latest_extracted_year,
      latest_found_year,
      last_outcome,
      override_note
    ),
    latest_extracted_year                                          as latest_available_cds_year,
    latest_found_year                                              as latest_found_cds_year,
    latest_found_year                                              as latest_attempted_year,
    latest_document_id,
    case
      when coverage_status = 'cds_available_current'
        then latest_extracted_source_url
      else null
    end                                                            as latest_public_source_url,
    null::integer                                                  as latest_field_count,
    last_checked_at,
    coverage_status in (
      'no_public_cds_found',
      'source_not_automatically_accessible',
      'not_checked'
    )                                                              as can_submit_source,
    lower(
      school_name
      || ' ' || coalesce(array_to_string(aliases, ' '), '')
      || ' ' || coalesce(city, '')
      || ' ' || coalesce(state, '')
    )                                                              as search_text,
    now()                                                          as updated_at
  from resolved;

  get diagnostics written = row_count;

  return query select
    written,
    extract(milliseconds from clock_timestamp() - started)::int;
end;
$$;

revoke all on function public.refresh_institution_cds_coverage() from public;
revoke all on function public.refresh_institution_cds_coverage() from anon, authenticated;
grant execute on function public.refresh_institution_cds_coverage() to service_role;

do $$
declare
  floor_aug text;
  floor_sep text;
begin
  select public.cds_freshness_floor(date '2026-08-21') into floor_aug;
  if floor_aug is distinct from '2024-25' then
    raise exception 'cds_freshness_floor Aug 2026 returned %, expected 2024-25', floor_aug;
  end if;
  select public.cds_freshness_floor(date '2026-09-01') into floor_sep;
  if floor_sep is distinct from '2025-26' then
    raise exception 'cds_freshness_floor Sep 2026 returned %, expected 2025-26', floor_sep;
  end if;
end;
$$;

commit;
