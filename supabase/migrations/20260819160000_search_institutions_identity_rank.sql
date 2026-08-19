-- Rank Jump-to-school by identity (school_id / alias) before name
-- substring, and prefer rows that actually have a CDS year. Fixes
-- "MIT" matching Smith and "Penn" losing to larger Pennsylvania names.
-- Does not consult the PRD 019 operator watchlist.

begin;

insert into public.institution_slug_crosswalk
  (ipeds_id, school_id, alias, source, is_primary)
values
  ('215062', 'upenn', 'penn', 'manual', false),
  ('110635', 'uc-berkeley', 'cal', 'manual', false),
  ('179867', 'washington-university-in-st-louis', 'washu', 'manual', false),
  ('162928', 'johns-hopkins', 'jhu', 'manual', false),
  ('139755', 'georgia-tech', 'gt', 'manual', false),
  ('231624', 'william-and-mary', 'wm', 'manual', false),
  ('231624', 'william-and-mary', 'w&m', 'manual', false),
  ('110404', 'california-institute-of-technology', 'caltech', 'manual', false)
on conflict (ipeds_id, alias) do nothing;

do $$
begin
  perform public.refresh_institution_cds_coverage();
end$$;

create or replace function public.search_institutions(
  p_query text,
  p_limit int default 10
)
returns table (
  school_id                  text,
  school_name                text,
  city                       text,
  state                      text,
  coverage_status            public.coverage_status_t,
  coverage_label             text,
  latest_available_cds_year  text
)
language sql
stable
security invoker
set search_path = public
as $$
  with q as (
    select
      lower(trim(coalesce(p_query, ''))) as qstr,
      regexp_replace(
        lower(trim(coalesce(p_query, ''))),
        '[^a-z0-9]',
        '',
        'g'
      ) as qcompact,
      regexp_replace(
        lower(trim(coalesce(p_query, ''))),
        '([\\.^$|?*+(){}\[\]-])',
        '\\\1',
        'g'
      ) as qescaped
  )
  select
    c.school_id,
    c.school_name,
    c.city,
    c.state,
    c.coverage_status,
    c.coverage_label,
    c.latest_available_cds_year
  from public.institution_cds_coverage c, q
  where c.coverage_status <> 'out_of_scope'
    and length(q.qstr) > 0
    and length(q.qcompact) > 0
    and (
      regexp_replace(c.school_id, '[^a-z0-9]', '', 'g') like q.qcompact || '%'
      or exists (
        select 1
        from unnest(coalesce(c.aliases, '{}'::text[])) as alias
        where regexp_replace(lower(alias), '[^a-z0-9]', '', 'g')
          like q.qcompact || '%'
      )
      or (
        length(q.qescaped) > 0
        and lower(c.school_name) ~ ('\y' || q.qescaped)
      )
      or (
        length(q.qstr) > 4
        and c.search_text like '%' || q.qstr || '%'
      )
    )
  order by
    case
      when regexp_replace(c.school_id, '[^a-z0-9]', '', 'g') = q.qcompact
        then 0
      when exists (
        select 1
        from unnest(coalesce(c.aliases, '{}'::text[])) as alias
        where regexp_replace(lower(alias), '[^a-z0-9]', '', 'g') = q.qcompact
      ) then 0
      when regexp_replace(c.school_id, '[^a-z0-9]', '', 'g') like q.qcompact || '%'
        then 1
      when exists (
        select 1
        from unnest(coalesce(c.aliases, '{}'::text[])) as alias
        where regexp_replace(lower(alias), '[^a-z0-9]', '', 'g') like q.qcompact || '%'
      ) then 1
      when length(q.qescaped) > 0
        and lower(c.school_name) ~ ('\y' || q.qescaped)
        then 2
      when lower(c.school_name) like '%' || q.qstr || '%'
        then 3
      else 4
    end,
    case when c.latest_available_cds_year is not null then 0 else 1 end,
    c.undergraduate_enrollment desc nulls last,
    c.school_name
  limit greatest(p_limit, 1);
$$;

comment on function public.search_institutions(text, int) is
  'Public autocomplete over institution_cds_coverage. Rank: exact school_id/alias, id/alias prefix, name token-prefix, name substring, other search_text. CDS year then enrollment as tie-breaks. Short queries do not match mid-word. SECURITY INVOKER so RLS hides out_of_scope rows.';

grant execute on function public.search_institutions(text, int) to anon, authenticated;

do $$
declare
  first_school text;
  found_count int;
begin
  insert into public.institution_directory (
    ipeds_id, school_id, school_name, scorecard_data_year, in_scope,
    exclusion_reason, undergraduate_enrollment
  ) values
    ('9999201', 'z9qk', 'Z9qk Institute of Technology', '2024', true, null, 1000),
    ('9999202', '__test_z9qk_mid__', 'Foz9qkton College', '2024', true, null, 90000),
    ('9999203', 'z9qk-state', 'Z9qk State University', '2024', true, null, 80000),
    ('9999204', '__test_z9qn_u__', 'University of Z9qnsylvania', '2024', true, null, 12000),
    ('9999205', 'z9qn-state', 'Z9qn State University', '2024', true, null, 85000);

  insert into public.institution_slug_crosswalk
    (ipeds_id, school_id, alias, source, is_primary)
  values
    ('9999201', 'z9qk', 'z9qk', 'manual', true),
    ('9999202', '__test_z9qk_mid__', '__test_z9qk_mid__', 'manual', true),
    ('9999203', 'z9qk-state', 'z9qk-state', 'manual', true),
    ('9999204', '__test_z9qn_u__', '__test_z9qn_u__', 'manual', true),
    ('9999204', '__test_z9qn_u__', 'z9qn', 'manual', false),
    ('9999205', 'z9qn-state', 'z9qn-state', 'manual', true);

  perform public.refresh_institution_cds_coverage();

  select school_id into first_school
    from public.search_institutions('z9qk', 7)
   limit 1;
  if first_school is distinct from 'z9qk' then
    raise exception 'search identity rank FAIL: z9qk first was %, expected z9qk', first_school;
  end if;

  select count(*) into found_count
    from public.search_institutions('z9qk', 20)
   where school_id = '__test_z9qk_mid__';
  if found_count <> 0 then
    raise exception 'search identity rank FAIL: mid-word Foz9qkton should not match z9qk';
  end if;

  select school_id into first_school
    from public.search_institutions('z9qn', 7)
   limit 1;
  if first_school is distinct from '__test_z9qn_u__' then
    raise exception 'search identity rank FAIL: z9qn first was %, expected __test_z9qn_u__', first_school;
  end if;

  delete from public.institution_slug_crosswalk
   where ipeds_id in ('9999201', '9999202', '9999203', '9999204', '9999205');
  delete from public.institution_directory
   where ipeds_id in ('9999201', '9999202', '9999203', '9999204', '9999205');
  perform public.refresh_institution_cds_coverage();
end$$;

commit;
