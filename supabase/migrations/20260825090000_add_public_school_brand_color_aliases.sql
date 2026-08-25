-- Map three public CDS slugs to reviewed Scorecard identities so list-page
-- brand colors can resolve through institution_slug_crosswalk. The Houston
-- system-administration slug remains deliberately unresolved pending review
-- of its archived CDS document.

begin;

do $$
begin
  if not exists (
    select 1 from public.institution_directory
    where ipeds_id = '228723' and school_id = 'texas-am'
  ) then
    raise exception 'Expected Texas A&M directory identity is missing';
  end if;
  if not exists (
    select 1 from public.institution_directory
    where ipeds_id = '160755' and school_id = 'tulane-university-of-louisiana'
  ) then
    raise exception 'Expected Tulane directory identity is missing';
  end if;
  if not exists (
    select 1 from public.institution_directory
    where ipeds_id = '233921'
      and school_id = 'virginia-polytechnic-institute-and-state-university'
  ) then
    raise exception 'Expected Virginia Tech directory identity is missing';
  end if;
end$$;

insert into public.institution_slug_crosswalk (
  ipeds_id, school_id, alias, source, is_primary, reviewed_at
)
values
  (
    '228723', 'texas-am',
    'texas-a-and-m-university-college-station', 'manual', false, now()
  ),
  (
    '160755', 'tulane-university-of-louisiana',
    'tulane-university', 'manual', false, now()
  ),
  (
    '233921', 'virginia-polytechnic-institute-and-state-university',
    'virginia-tech', 'manual', false, now()
  )
on conflict (ipeds_id, alias) do update
set school_id = excluded.school_id,
    source = excluded.source,
    is_primary = excluded.is_primary,
    reviewed_at = excluded.reviewed_at;

do $$
declare
  bad_alias_count integer;
begin
  select count(*) into bad_alias_count
  from (
    values
      ('texas-a-and-m-university-college-station', 'texas-am'),
      ('tulane-university', 'tulane-university-of-louisiana'),
      ('virginia-tech', 'virginia-polytechnic-institute-and-state-university')
  ) as expected(alias, school_id)
  where (
      select count(distinct crosswalk.school_id)
      from public.institution_slug_crosswalk as crosswalk
      where crosswalk.alias = expected.alias
    ) <> 1
    or not exists (
      select 1
      from public.institution_slug_crosswalk as crosswalk
      where crosswalk.alias = expected.alias
        and crosswalk.school_id = expected.school_id
    );

  if bad_alias_count <> 0 then
    raise exception 'Brand-color alias verification failed for % rows', bad_alias_count;
  end if;
end$$;

do $$
begin
  perform public.refresh_institution_cds_coverage();
end$$;

commit;
