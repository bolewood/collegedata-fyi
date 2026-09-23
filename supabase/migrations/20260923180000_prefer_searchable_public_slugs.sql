-- Prefer the name people search as institution_directory.school_id (and
-- thus the primary crosswalk alias). Brand colors stay on the IPEDS-keyed
-- directory row; this only flips school_id and which alias is primary.
-- Legal-name slugs remain live aliases so documents merge and old URLs 308.
-- Do not retire those slugs: retired aliases are excluded from merge.

begin;

update public.institution_directory
set school_id = 'caltech', refreshed_at = now()
where ipeds_id = '110404'
  and school_id = 'california-institute-of-technology';

update public.institution_directory
set school_id = 'tulane-university', refreshed_at = now()
where ipeds_id = '160755'
  and school_id = 'tulane-university-of-louisiana';

update public.institution_directory
set school_id = 'virginia-tech', refreshed_at = now()
where ipeds_id = '233921'
  and school_id = 'virginia-polytechnic-institute-and-state-university';

update public.institution_cds_coverage
set school_id = 'caltech', updated_at = now()
where ipeds_id = '110404'
  and school_id = 'california-institute-of-technology';

update public.institution_cds_coverage
set school_id = 'tulane-university', updated_at = now()
where ipeds_id = '160755'
  and school_id = 'tulane-university-of-louisiana';

update public.institution_cds_coverage
set school_id = 'virginia-tech', updated_at = now()
where ipeds_id = '233921'
  and school_id = 'virginia-polytechnic-institute-and-state-university';

do $$
begin
  if not exists (
    select 1 from public.institution_directory
    where ipeds_id = '110404' and school_id = 'caltech'
  ) then
    raise exception 'Caltech directory school_id did not become caltech';
  end if;
  if not exists (
    select 1 from public.institution_directory
    where ipeds_id = '160755' and school_id = 'tulane-university'
  ) then
    raise exception 'Tulane directory school_id did not become tulane-university';
  end if;
  if not exists (
    select 1 from public.institution_directory
    where ipeds_id = '233921' and school_id = 'virginia-tech'
  ) then
    raise exception 'Virginia Tech directory school_id did not become virginia-tech';
  end if;
  if not exists (
    select 1 from public.institution_directory
    where ipeds_id = '233921'
      and school_id = 'virginia-tech'
      and brand_colors is not null
      and cardinality(brand_colors) > 0
  ) then
    raise exception 'Virginia Tech brand_colors missing after searchable slug flip';
  end if;
end$$;

update public.institution_slug_crosswalk
set school_id = 'caltech'
where ipeds_id = '110404';

update public.institution_slug_crosswalk
set school_id = 'tulane-university'
where ipeds_id = '160755';

update public.institution_slug_crosswalk
set school_id = 'virginia-tech'
where ipeds_id = '233921';

insert into public.institution_slug_crosswalk (
  ipeds_id, school_id, alias, source, is_primary, reviewed_at
)
values
  (
    '110404', 'caltech', 'caltech',
    'schools_yaml', true, now()
  ),
  (
    '110404', 'caltech', 'california-institute-of-technology',
    'scorecard', false, now()
  ),
  (
    '160755', 'tulane-university', 'tulane-university',
    'schools_yaml', true, now()
  ),
  (
    '160755', 'tulane-university', 'tulane-university-of-louisiana',
    'scorecard', false, now()
  ),
  (
    '233921', 'virginia-tech', 'virginia-tech',
    'schools_yaml', true, now()
  ),
  (
    '233921', 'virginia-tech',
    'virginia-polytechnic-institute-and-state-university',
    'scorecard', false, now()
  )
on conflict (ipeds_id, alias) do update
set school_id = excluded.school_id,
    source = excluded.source,
    is_primary = excluded.is_primary,
    reviewed_at = excluded.reviewed_at;

update public.institution_slug_crosswalk
set is_primary = (alias = school_id)
where ipeds_id in ('110404', '160755', '233921');

do $$
begin
  if exists (
    select ipeds_id
    from public.institution_slug_crosswalk
    where ipeds_id in ('110404', '160755', '233921')
    group by ipeds_id
    having count(*) filter (where is_primary) <> 1
  ) then
    raise exception 'Expected exactly one primary alias after searchable slug flip';
  end if;
  if exists (
    select 1
    from public.institution_directory d
    join public.institution_slug_crosswalk c
      on c.ipeds_id = d.ipeds_id and c.is_primary
    where d.ipeds_id in ('110404', '160755', '233921')
      and c.alias <> d.school_id
  ) then
    raise exception 'Primary alias does not match directory school_id';
  end if;
end$$;

commit;
