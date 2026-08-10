-- Repair the Tufts University / UMass Dartmouth identity split.
--
-- tools/finder/schools.yaml incorrectly assigned Tufts the UMass Dartmouth
-- UNITID (167987). The directory loader trusted that claim as canonical, so
-- the public `tufts` slug, coverage, federal facts, projections, and recipes
-- mixed two institutions. The corrected Tufts UNITID is 168148.

begin;

-- Keep public reads available while stopping all writers that can race this
-- identity repair.
lock table
  public.institution_directory,
  public.institution_slug_crosswalk,
  public.institution_cds_coverage_overrides,
  public.cds_documents,
  public.archive_queue,
  public.school_hosting_observations,
  public.cds_fields,
  public.school_browser_rows,
  public.cds_field_change_events,
  public.scorecard_summary
in share row exclusive mode;

do $preflight$
declare
  directory_count integer;
begin
  select count(*)
    into directory_count
    from public.institution_directory
   where ipeds_id in ('167987', '168148');

  -- A clean db reset applies migrations before directory data is loaded.
  if directory_count = 0 then
    if exists (
      select 1
        from public.institution_slug_crosswalk
       where ipeds_id in ('167987', '168148')
    ) or exists (
      select 1
        from public.cds_documents
       where school_id in (
         'tufts',
         'tufts-university',
         'university-of-massachusetts-dartmouth'
       )
          or lower(coalesce(source_url, '')) like '%tufts.edu/%'
    ) or exists (
      select 1
        from public.archive_queue
       where school_id in ('tufts', 'tufts-university')
    ) or exists (
      select 1
        from public.school_hosting_observations
       where school_id in ('tufts', 'tufts-university')
    ) then
      raise exception
        'Tufts identity repair aborted: directory rows are absent but dependent identity rows exist';
    end if;

    raise notice
      'Tufts identity repair: clean database has no directory data; data repair is a no-op';
    return;
  end if;

  if directory_count <> 2 then
    raise exception
      'Tufts identity repair aborted: expected both UNITIDs 167987 and 168148, found % rows',
      directory_count;
  end if;

  if not exists (
    select 1
      from public.institution_directory
     where ipeds_id = '167987'
       and school_name = 'University of Massachusetts-Dartmouth'
       and lower(coalesce(website_url, '')) like '%umassd.edu%'
  ) then
    raise exception
      'Tufts identity repair aborted: UNITID 167987 is not the expected UMass Dartmouth row';
  end if;

  if not exists (
    select 1
      from public.institution_directory
     where ipeds_id = '168148'
       and school_name = 'Tufts University'
       and lower(coalesce(website_url, '')) like '%tufts.edu%'
  ) then
    raise exception
      'Tufts identity repair aborted: UNITID 168148 is not the expected Tufts row';
  end if;

  if exists (
    select 1
      from public.institution_directory
     where school_id = 'tufts'
       and ipeds_id not in ('167987', '168148')
  ) then
    raise exception
      'Tufts identity repair aborted: slug tufts is occupied by an unexpected UNITID';
  end if;

  if exists (
    select 1
      from public.institution_directory
     where school_id = 'tufts-university'
       and ipeds_id <> '168148'
  ) then
    raise exception
      'Tufts identity repair aborted: slug tufts-university is occupied by an unexpected UNITID';
  end if;

  if exists (
    select 1
      from public.institution_directory
     where school_id = 'university-of-massachusetts-dartmouth'
       and ipeds_id <> '167987'
  ) then
    raise exception
      'Tufts identity repair aborted: the target UMass Dartmouth slug is occupied';
  end if;

  if not exists (
    select 1
      from public.scorecard_summary
     where ipeds_id = '167987'
       and school_name = 'University of Massachusetts-Dartmouth'
  ) or not exists (
    select 1
      from public.scorecard_summary
     where ipeds_id = '168148'
       and school_name = 'Tufts University'
  ) then
    raise exception
      'Tufts identity repair aborted: expected Scorecard rows are missing or misidentified';
  end if;

  if not exists (
    select 1
      from public.cds_documents
     where school_id = 'tufts'
       and school_name = 'Tufts University'
       and lower(coalesce(source_url, '')) like '%tufts.edu/%'
  ) then
    raise exception
      'Tufts identity repair aborted: no canonical Tufts documents were found';
  end if;

  if exists (
    select 1
      from public.cds_documents
     where school_id = 'tufts'
       and (
         school_name is distinct from 'Tufts University'
         or lower(coalesce(source_url, '')) not like '%tufts.edu/%'
         or (
           ipeds_id is distinct from '167987'
           and ipeds_id is distinct from '168148'
         )
       )
  ) then
    raise exception
      'Tufts identity repair aborted: school_id=tufts contains an unexpected document';
  end if;

  if exists (
    select 1
      from public.cds_documents
     where school_id = 'tufts-university'
  ) then
    raise exception
      'Tufts identity repair aborted: tufts-university has document rows requiring review';
  end if;

  if exists (
    select 1
      from public.archive_queue
     where school_id = 'tufts-university'
       and (
         status not in ('done', 'failed_permanent')
         or school_name is distinct from 'Tufts University'
         or lower(coalesce(cds_url_hint, '')) not like '%tufts.edu%'
       )
  ) then
    raise exception
      'Tufts identity repair aborted: tufts-university has an active or non-Tufts queue row';
  end if;

  if exists (
    select 1
      from public.archive_queue retired
      join public.archive_queue canonical
        on canonical.enqueued_run_id = retired.enqueued_run_id
       and canonical.school_id = 'tufts'
     where retired.school_id = 'tufts-university'
  ) then
    raise exception
      'Tufts identity repair aborted: retired queue row collides with a canonical run';
  end if;

  if exists (
    select 1
      from public.school_hosting_observations
     where school_id = 'tufts-university'
       and lower(coalesce(origin_domain, '')) <> 'tufts.edu'
       and lower(coalesce(final_url_host, '')) not like '%tufts.edu'
       and lower(coalesce(seed_url, '')) not like '%tufts.edu/%'
  ) then
    raise exception
      'Tufts identity repair aborted: retired hosting row lacks Tufts provenance';
  end if;

  if exists (
    select 1
      from public.institution_cds_coverage_overrides
     where ipeds_id in ('167987', '168148')
  ) then
    raise exception
      'Tufts identity repair aborted: an affected UNITID has a coverage override';
  end if;
end;
$preflight$;

-- Move 167987 first to free UNIQUE(institution_directory.school_id).
update public.institution_directory
   set school_id = 'university-of-massachusetts-dartmouth',
       refreshed_at = now()
 where ipeds_id = '167987'
   and school_id is distinct from 'university-of-massachusetts-dartmouth';

update public.institution_directory
   set school_id = 'tufts',
       refreshed_at = now()
 where ipeds_id = '168148'
   and school_id is distinct from 'tufts';

-- Rebuild both affected crosswalks. Retired slugs are redirects, so coverage
-- search does not advertise them as current aliases.
delete from public.institution_slug_crosswalk
 where ipeds_id = '167987'
   and alias = 'tufts';

update public.institution_slug_crosswalk
   set school_id = 'university-of-massachusetts-dartmouth',
       is_primary = false,
       reviewed_at = now()
 where ipeds_id = '167987';

insert into public.institution_slug_crosswalk (
  ipeds_id, school_id, alias, source, is_primary, reviewed_at
)
select
  '167987',
  'university-of-massachusetts-dartmouth',
  'university-of-massachusetts-dartmouth',
  'scorecard',
  true,
  now()
where exists (
  select 1 from public.institution_directory where ipeds_id = '167987'
)
on conflict (ipeds_id, alias) do update
set school_id = excluded.school_id,
    source = excluded.source,
    is_primary = excluded.is_primary,
    reviewed_at = excluded.reviewed_at;

update public.institution_slug_crosswalk
   set school_id = 'tufts',
       is_primary = false,
       reviewed_at = now()
 where ipeds_id = '168148';

insert into public.institution_slug_crosswalk (
  ipeds_id, school_id, alias, source, is_primary, reviewed_at
)
select '168148', 'tufts', 'tufts', 'schools_yaml', true, now()
where exists (
  select 1 from public.institution_directory where ipeds_id = '168148'
)
on conflict (ipeds_id, alias) do update
set school_id = excluded.school_id,
    source = excluded.source,
    is_primary = excluded.is_primary,
    reviewed_at = excluded.reviewed_at;

insert into public.institution_slug_crosswalk (
  ipeds_id, school_id, alias, source, is_primary, reviewed_at
)
select '168148', 'tufts', 'tufts-university', 'redirect', false, now()
where exists (
  select 1 from public.institution_directory where ipeds_id = '168148'
)
on conflict (ipeds_id, alias) do update
set school_id = excluded.school_id,
    source = excluded.source,
    is_primary = excluded.is_primary,
    reviewed_at = excluded.reviewed_at;

-- The archive slug and source URLs were always Tufts; correct their federal
-- identity and fold the one retired-slug discovery history row into it.
update public.cds_documents
   set ipeds_id = '168148',
       school_name = 'Tufts University'
 where school_id = 'tufts'
   and school_name = 'Tufts University'
   and lower(coalesce(source_url, '')) like '%tufts.edu/%';

update public.archive_queue
   set school_id = 'tufts',
       school_name = 'Tufts University'
 where school_id = 'tufts-university';

update public.school_hosting_observations
   set school_id = 'tufts'
 where school_id = 'tufts-university';

-- Synchronize queryable projections and replace the five stored Scorecard
-- metrics with the 168148 row.
update public.cds_fields as field_row
   set school_id = document.school_id,
       school_name = document.school_name,
       ipeds_id = document.ipeds_id,
       updated_at = now()
  from public.cds_documents as document
 where field_row.document_id = document.id
   and document.school_id = 'tufts'
   and document.school_name = 'Tufts University'
   and document.ipeds_id = '168148';

update public.school_browser_rows as browser_row
   set school_id = document.school_id,
       school_name = document.school_name,
       ipeds_id = document.ipeds_id,
       undergrad_enrollment_scorecard = scorecard.enrollment,
       scorecard_data_year = scorecard.scorecard_data_year,
       retention_rate = scorecard.retention_rate_ft,
       avg_net_price = scorecard.avg_net_price,
       pell_rate = scorecard.pell_grant_rate,
       updated_at = now()
  from public.cds_documents as document
  join public.scorecard_summary as scorecard
    on scorecard.ipeds_id = document.ipeds_id
 where browser_row.document_id = document.id
   and document.school_id = 'tufts'
   and document.school_name = 'Tufts University'
   and document.ipeds_id = '168148';

update public.cds_field_change_events as event_row
   set school_id = 'tufts',
       school_name = 'Tufts University',
       ipeds_id = '168148',
       updated_at = now()
 where event_row.from_document_id in (
         select id from public.cds_documents
          where school_id = 'tufts' and ipeds_id = '168148'
       )
    or event_row.to_document_id in (
         select id from public.cds_documents
          where school_id = 'tufts' and ipeds_id = '168148'
       );

select * from public.refresh_institution_cds_coverage();
select public.refresh_ipeds_browser_source_modes();
-- Keep cache refreshes in the repair transaction so a failed postcondition
-- rolls back both source rows and projections. PostgreSQL permits REFRESH
-- MATERIALIZED VIEW CONCURRENTLY here (unlike CREATE INDEX CONCURRENTLY);
-- ExecRefreshMatView deliberately holds its lock until transaction end.
select public.refresh_public_serving_caches();

do $assertions$
declare
  directory_count integer;
  result_count integer;
begin
  select count(*)
    into directory_count
    from public.institution_directory
   where ipeds_id in ('167987', '168148');

  if directory_count = 0 then
    return;
  end if;

  if not exists (
    select 1 from public.institution_directory
     where ipeds_id = '167987'
       and school_id = 'university-of-massachusetts-dartmouth'
       and school_name = 'University of Massachusetts-Dartmouth'
  ) or not exists (
    select 1 from public.institution_directory
     where ipeds_id = '168148'
       and school_id = 'tufts'
       and school_name = 'Tufts University'
  ) then
    raise exception
      'Tufts identity repair assertion failed: directory identities are not canonical';
  end if;

  if (
    select count(*) from public.institution_slug_crosswalk
     where ipeds_id = '167987' and is_primary = true
  ) <> 1 or not exists (
    select 1 from public.institution_slug_crosswalk
     where ipeds_id = '167987'
       and school_id = 'university-of-massachusetts-dartmouth'
       and alias = 'university-of-massachusetts-dartmouth'
       and source = 'scorecard'
       and is_primary = true
  ) then
    raise exception
      'Tufts identity repair assertion failed: UMass Dartmouth crosswalk is invalid';
  end if;

  if (
    select count(*) from public.institution_slug_crosswalk
     where ipeds_id = '168148' and is_primary = true
  ) <> 1 or not exists (
    select 1 from public.institution_slug_crosswalk
     where ipeds_id = '168148'
       and school_id = 'tufts'
       and alias = 'tufts'
       and source = 'schools_yaml'
       and is_primary = true
  ) then
    raise exception
      'Tufts identity repair assertion failed: Tufts crosswalk is invalid';
  end if;

  if exists (
    select 1 from public.institution_slug_crosswalk
     where ipeds_id = '167987' and alias = 'tufts'
  ) or not exists (
    select 1 from public.institution_slug_crosswalk
     where ipeds_id = '168148'
       and school_id = 'tufts'
       and alias = 'tufts-university'
       and source = 'redirect'
       and is_primary = false
  ) then
    raise exception
      'Tufts identity repair assertion failed: stale/redirect aliases are invalid';
  end if;

  if exists (
    select 1 from public.institution_slug_crosswalk
     where ipeds_id = '167987'
       and school_id <> 'university-of-massachusetts-dartmouth'
  ) or exists (
    select 1 from public.institution_slug_crosswalk
     where ipeds_id = '168148' and school_id <> 'tufts'
  ) then
    raise exception
      'Tufts identity repair assertion failed: crosswalk disagrees with directory';
  end if;

  if (
    select count(*) from public.institution_slug_crosswalk
     where alias = 'tufts'
  ) <> 1 or (
    select count(*) from public.institution_slug_crosswalk
     where alias = 'tufts-university'
  ) <> 1 then
    raise exception
      'Tufts identity repair assertion failed: route aliases are ambiguous';
  end if;

  if exists (
    select 1 from public.cds_documents
     where lower(coalesce(source_url, '')) like '%tufts.edu/%'
       and (
         school_id is distinct from 'tufts'
         or school_name is distinct from 'Tufts University'
         or ipeds_id is distinct from '168148'
       )
  ) then
    raise exception
      'Tufts identity repair assertion failed: a Tufts document remains misidentified';
  end if;

  if exists (
    select 1 from public.archive_queue where school_id = 'tufts-university'
  ) or exists (
    select 1 from public.school_hosting_observations
     where school_id = 'tufts-university'
  ) then
    raise exception
      'Tufts identity repair assertion failed: retired discovery rows remain';
  end if;

  if exists (
    select 1
      from public.cds_fields as field_row
      join public.cds_documents as document
        on document.id = field_row.document_id
     where document.school_id = 'tufts'
       and document.ipeds_id = '168148'
       and (
         field_row.school_id is distinct from document.school_id
         or field_row.school_name is distinct from document.school_name
         or field_row.ipeds_id is distinct from document.ipeds_id
       )
  ) then
    raise exception
      'Tufts identity repair assertion failed: cds_fields identity is stale';
  end if;

  if exists (
    select 1
      from public.school_browser_rows as browser_row
      join public.cds_documents as document
        on document.id = browser_row.document_id
      join public.scorecard_summary as scorecard
        on scorecard.ipeds_id = document.ipeds_id
     where document.school_id = 'tufts'
       and document.ipeds_id = '168148'
       and (
         browser_row.school_id is distinct from document.school_id
         or browser_row.school_name is distinct from document.school_name
         or browser_row.ipeds_id is distinct from document.ipeds_id
         or browser_row.undergrad_enrollment_scorecard is distinct from scorecard.enrollment
         or browser_row.scorecard_data_year is distinct from scorecard.scorecard_data_year
         or browser_row.retention_rate is distinct from scorecard.retention_rate_ft
         or browser_row.avg_net_price is distinct from scorecard.avg_net_price
         or browser_row.pell_rate is distinct from scorecard.pell_grant_rate
         or browser_row.federal_baseline_available is distinct from true
         or browser_row.federal_source_mode is distinct from 'cds_plus_ipeds_baseline'
       )
  ) then
    raise exception
      'Tufts identity repair assertion failed: browser/Scorecard projection is stale';
  end if;

  if exists (
    select 1 from public.cds_field_change_events
     where (
       from_document_id in (
         select id from public.cds_documents
          where school_id = 'tufts' and ipeds_id = '168148'
       )
       or to_document_id in (
         select id from public.cds_documents
          where school_id = 'tufts' and ipeds_id = '168148'
       )
     )
       and (
         school_id is distinct from 'tufts'
         or school_name is distinct from 'Tufts University'
         or ipeds_id is distinct from '168148'
       )
  ) then
    raise exception
      'Tufts identity repair assertion failed: change-event identity is stale';
  end if;

  if not exists (
    select 1 from public.school_merit_profile
     where school_id = 'tufts'
       and school_name = 'Tufts University'
       and ipeds_id = '168148'
       and scorecard_data_year = (
         select scorecard_data_year from public.scorecard_summary
          where ipeds_id = '168148'
       )
       and avg_net_price = (
         select avg_net_price from public.scorecard_summary
          where ipeds_id = '168148'
       )
  ) then
    raise exception
      'Tufts identity repair assertion failed: merit-profile cache is stale';
  end if;

  if not exists (
    select 1 from public.institution_cds_coverage
     where ipeds_id = '168148'
       and school_id = 'tufts'
       and school_name = 'Tufts University'
       and coverage_status = 'cds_available_current'
       and latest_available_cds_year is not null
       and latest_document_id in (
         select id from public.cds_documents
          where school_id = 'tufts' and ipeds_id = '168148'
       )
       and 'tufts' = any(aliases)
       and not ('tufts-university' = any(aliases))
  ) then
    raise exception
      'Tufts identity repair assertion failed: Tufts coverage is not canonical/current';
  end if;

  if not exists (
    select 1 from public.institution_cds_coverage
     where ipeds_id = '167987'
       and school_id = 'university-of-massachusetts-dartmouth'
       and school_name = 'University of Massachusetts-Dartmouth'
       and coverage_status = 'not_checked'
       and latest_document_id is null
       and latest_available_cds_year is null
  ) then
    raise exception
      'Tufts identity repair assertion failed: UMass Dartmouth inherited coverage';
  end if;

  select count(*)
    into result_count
    from public.search_institutions('Tufts University', 10)
   where school_id = 'tufts'
     and school_name = 'Tufts University'
     and coverage_status = 'cds_available_current';

  if result_count <> 1 then
    raise exception
      'Tufts identity repair assertion failed: Tufts search returned % canonical rows',
      result_count;
  end if;

  select count(*)
    into result_count
    from public.search_institutions('University of Massachusetts-Dartmouth', 10)
   where school_id = 'university-of-massachusetts-dartmouth'
     and school_name = 'University of Massachusetts-Dartmouth'
     and coverage_status = 'not_checked';

  if result_count <> 1 then
    raise exception
      'Tufts identity repair assertion failed: UMass search returned % canonical rows',
      result_count;
  end if;

  if not exists (
    select 1 from public.school_facts_unified
     where ipeds_id = '168148'
       and school_id = 'tufts'
       and school_name = 'Tufts University'
       and field_key = 'institution_name'
       and lower(coalesce(display_value, '')) like 'tufts university%'
  ) or exists (
    select 1 from public.school_facts_unified
     where school_id = 'tufts'
       and field_key = 'institution_name'
       and lower(coalesce(display_value, '')) like '%massachusetts%dartmouth%'
  ) then
    raise exception
      'Tufts identity repair assertion failed: federal baseline remains inverted';
  end if;
end;
$assertions$;

commit;
