-- Launch coverage data-quality cleanup.
--
-- Addresses the PRD 015 audit findings that directly affect public
-- coverage/search trust before launch:
--   1. Correct stale Bucknell/Drexel IPEDS IDs that prevented their
--      CDS-backed rows from joining to Scorecard directory rows.
--   2. Canonicalize non-conflicting cds_documents rows whose IPEDS ID
--      points at a primary schools.yaml slug but whose school_id is a
--      Scorecard-style alias.
--   3. Preserve remaining alias routes in institution_slug_crosswalk as
--      redirects so consumers can resolve old/Scorecard-style slugs.
--   4. Mark stale system-office CDS rows as verified_absent and remove
--      their archive queue work.

begin;

-- Bucknell and Drexel had stale IPEDS IDs in schools.yaml, so production
-- rows inserted before this migration can carry the wrong ID. The NCES
-- institution profiles identify Bucknell as 211291 and Drexel as 212054.
update public.cds_documents
set ipeds_id = case school_id
  when 'bucknell' then '211291'
  when 'drexel' then '212054'
  else ipeds_id
end
where school_id in ('bucknell', 'drexel');

-- If institution_directory was loaded while schools.yaml had the stale
-- IDs, Scorecard rows for these institutions got auto-slugs instead of
-- preserving the public canonical slugs. Repair that serving substrate.
update public.institution_directory
set school_id = 'bucknell',
    directory_source = 'scorecard',
    refreshed_at = now()
where ipeds_id = '211291'
  and school_id <> 'bucknell'
  and not exists (
    select 1
    from public.institution_directory existing
    where existing.school_id = 'bucknell'
      and existing.ipeds_id <> '211291'
  );

update public.institution_directory
set school_id = 'drexel',
    directory_source = 'scorecard',
    refreshed_at = now()
where ipeds_id = '212054'
  and school_id <> 'drexel'
  and not exists (
    select 1
    from public.institution_directory existing
    where existing.school_id = 'drexel'
      and existing.ipeds_id <> '212054'
  );

-- Keep the crosswalk coherent after the directory slug repair. The
-- Scorecard-style slugs remain aliases; the short schools.yaml slugs
-- become primary.
insert into public.institution_slug_crosswalk
  (ipeds_id, school_id, alias, source, is_primary, reviewed_at)
values
  ('211291', 'bucknell', 'bucknell', 'schools_yaml', true, now()),
  ('211291', 'bucknell', 'bucknell-university', 'scorecard', false, now()),
  ('212054', 'drexel', 'drexel', 'schools_yaml', true, now()),
  ('212054', 'drexel', 'drexel-university', 'scorecard', false, now())
on conflict (ipeds_id, alias) do update
set school_id = excluded.school_id,
    source = excluded.source,
    is_primary = excluded.is_primary,
    reviewed_at = excluded.reviewed_at;

-- Ensure no stale primary aliases remain for the repaired institutions.
update public.institution_slug_crosswalk
set school_id = case ipeds_id
      when '211291' then 'bucknell'
      when '212054' then 'drexel'
      else school_id
    end,
    is_primary = (alias = case ipeds_id
      when '211291' then 'bucknell'
      when '212054' then 'drexel'
      else alias
    end),
    source = case
      when ipeds_id = '211291' and alias = 'bucknell' then 'schools_yaml'
      when ipeds_id = '212054' and alias = 'drexel' then 'schools_yaml'
      else source
    end
where ipeds_id in ('211291', '212054');

-- General slug-fragmentation repair: if a document carries an IPEDS ID
-- whose primary crosswalk row is a schools.yaml canonical slug, move it
-- to that canonical slug when doing so cannot violate the existing
-- (school_id, sub_institutional, cds_year) uniqueness contract.
with primary_slug as (
  select ipeds_id, school_id as canonical_school_id
  from public.institution_slug_crosswalk
  where is_primary = true
    and source = 'schools_yaml'
),
candidates as (
  select d.id, d.school_id as old_school_id, p.canonical_school_id
  from public.cds_documents d
  join primary_slug p on p.ipeds_id = d.ipeds_id
  where d.school_id <> p.canonical_school_id
),
to_update as (
  select c.id, c.old_school_id, c.canonical_school_id
  from (
    select
      c.*,
      count(*) over (
        partition by c.canonical_school_id, d.sub_institutional, d.cds_year
      ) as candidate_count
    from candidates c
    join public.cds_documents d on d.id = c.id
  ) c
  join public.cds_documents d on d.id = c.id
  where c.candidate_count = 1
    and not exists (
      select 1
      from public.cds_documents existing
      where existing.school_id = c.canonical_school_id
        and existing.sub_institutional is not distinct from d.sub_institutional
        and existing.cds_year = d.cds_year
    )
),
redirects as (
  insert into public.institution_slug_crosswalk
    (ipeds_id, school_id, alias, source, is_primary, reviewed_at)
  select distinct d.ipeds_id, p.canonical_school_id, d.school_id, 'redirect', false, now()
  from public.cds_documents d
  join primary_slug p on p.ipeds_id = d.ipeds_id
  where d.school_id <> p.canonical_school_id
  on conflict (ipeds_id, alias) do update
  set school_id = excluded.school_id,
      source = 'redirect',
      is_primary = false,
      reviewed_at = excluded.reviewed_at
  returning 1
)
update public.cds_documents d
set school_id = u.canonical_school_id
from to_update u
where d.id = u.id;

-- System offices are administrative entities, not CDS publishers. Keep
-- row history but remove them from public extraction/search surfaces.
update public.cds_documents
set participation_status = 'verified_absent',
    extraction_status = 'not_applicable'
where school_id in (
  'university-of-maine-system-central-office',
  'university-of-houston-system-administration',
  'university-of-hawaii-system-office',
  'the-university-of-texas-system-office'
);

delete from public.archive_queue
where school_id in (
  'university-of-maine-system-central-office',
  'university-of-houston-system-administration',
  'university-of-hawaii-system-office',
  'the-university-of-texas-system-office'
);

-- Refresh the serving table immediately when this migration is applied.
select * from public.refresh_institution_cds_coverage();

commit;
