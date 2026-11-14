-- A school with no visible documents must not read "CDS available".
--
-- 20261114130000 stopped hidden documents from supplying the latest year, but
-- derive_coverage_status() still returns cds_available_current whenever the
-- last archive outcome was a "found" one (inserted, refreshed,
-- unchanged_verified, unchanged_repaired). For a school whose documents were
-- all hidden after that check, the outcome describes a file we no longer
-- publish. After 20261114130000, 62 schools read "CDS available" with no
-- year, among them Miami University-Hamilton and the Kent State regional
-- campuses, whose only files were the main campus's.
--
-- Change vs. 20261114130000: a visible_docs CTE, and a "found" outcome is
-- passed to derive_coverage_status() as 'no_pdfs_found' when the school has
-- no visible document. Schools with any visible document, including ones
-- whose year is unknown, are unaffected.

begin;

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
  -- Serialize overlapping refreshes. Does not block SELECT.
  perform pg_advisory_xact_lock(hashtext('public.refresh_institution_cds_coverage'));

  drop table if exists pg_temp.coverage_refresh_staging;
  create temp table coverage_refresh_staging (
    like public.institution_cds_coverage including defaults
  ) on commit drop;

  with
    cds_extracted as (
      select distinct on (school_id)
        school_id,
        cds_year             as latest_extracted_year,
        id                   as latest_document_id,
        source_url           as latest_extracted_source_url
      from public.cds_documents
      where extraction_status = 'extracted'
        and removed_at is null
        and cds_year ~ '^[0-9]{4}-[0-9]{2}$'
      order by school_id, cds_year desc
    ),
    cds_found as (
      select distinct on (school_id)
        school_id,
        cds_year             as latest_found_year,
        extraction_status    as latest_found_extraction_status
      from public.cds_documents
      where source_url is not null
        and removed_at is null
        and cds_year ~ '^[0-9]{4}-[0-9]{2}$'
      order by school_id, cds_year desc
    ),
    -- Schools with at least one document that is not hidden.
    visible_docs as (
      select distinct school_id
      from public.cds_documents
      where removed_at is null
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
            -- "Found or re-confirmed a source" is only true while a document
            -- from it is still visible. Once every document is hidden, the
            -- old outcome describes a file we no longer publish.
            case
              when vd.school_id is null
                   and q.last_outcome in ('inserted', 'refreshed',
                                          'unchanged_verified', 'unchanged_repaired')
                then 'no_pdfs_found'
              else q.last_outcome
            end
          )
        )                                                 as derived_status
      from public.institution_directory d
      left join cds_extracted ce on ce.school_id = d.school_id
      left join cds_found cf on cf.school_id = d.school_id
      left join queue_latest q on q.school_id = d.school_id
      left join visible_docs vd on vd.school_id = d.school_id
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
          when derived_status = 'cds_available_stale'
               and latest_extracted_year is not null
               and latest_extracted_year >= public.cds_freshness_floor()
            then 'cds_available_current'::public.coverage_status_t
          else derived_status
        end as coverage_status
      from resolved_raw
    )
  insert into coverage_refresh_staging (
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

  -- `where true` is load-bearing: the refresh-coverage Edge Function calls
  -- this via PostgREST, whose authenticator role preloads pg_safeupdate.
  -- A bare DELETE fails there with "DELETE requires a WHERE clause"
  -- (it passes from psql as postgres, which is how #239 shipped broken).
  delete from public.institution_cds_coverage where true;
  insert into public.institution_cds_coverage
  select * from coverage_refresh_staging;

  get diagnostics written = row_count;
  drop table if exists pg_temp.coverage_refresh_staging;

  return query select
    written,
    extract(milliseconds from clock_timestamp() - started)::int;
end;
$$;

revoke all on function public.refresh_institution_cds_coverage() from public;
revoke all on function public.refresh_institution_cds_coverage() from anon, authenticated;
grant execute on function public.refresh_institution_cds_coverage() to service_role;

commit;
