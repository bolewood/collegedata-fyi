-- PRD 015 M4 — search_institutions() RPC.
--
-- Server-backed autocomplete for the homepage search box. Replaces the
-- hardcoded in-memory ILIKE that only knew about CDS-backed schools.
-- Returns rows from institution_cds_coverage so search results include
-- directory-only schools with honest coverage badges, instead of empty
-- silence for known schools we just haven't archived a CDS for.
--
-- Match strategy: substring ILIKE on the materialized search_text
-- column (school name + aliases + city + state, lowercased). On 2,924
-- in-scope rows a sequential scan completes in microseconds, so no
-- pg_trgm index is needed for v1. If we ever want fuzzy matching, swap
-- this to use pg_trgm + similarity().
--
-- Rank order:
--   0  exact name match           "harvard university"  →  Harvard
--   1  name prefix                "harv"                →  Harvard, Harvey Mudd
--   2  name substring             "art"                 →  Hartford, Art Inst
--   3  match anywhere in search   "cambridge"           →  MIT (city match)
-- Within a tier, ties broken by undergraduate_enrollment DESC NULLS LAST
-- and then school_name. The two-level sort surfaces the highest-interest
-- match first when many schools share a token (e.g. typing "state").
--
-- Authorization: anon and authenticated. The function is SECURITY
-- INVOKER, so the underlying RLS policy on institution_cds_coverage
-- (which already hides out_of_scope rows from anon/authenticated)
-- applies. The explicit `<> 'out_of_scope'` filter is redundant
-- defense-in-depth but kept for readability.
--
-- The search_text column is populated by refresh_institution_cds_coverage()
-- at refresh time (see migration 20260429144126_institution_cds_coverage.sql);
-- this function only reads it.

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
    select lower(trim(coalesce(p_query, ''))) as qstr
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
    and c.search_text like '%' || q.qstr || '%'
  order by
    case
      when lower(c.school_name) = q.qstr                       then 0
      when lower(c.school_name) like q.qstr || '%'             then 1
      when lower(c.school_name) like '%' || q.qstr || '%'      then 2
      else 3
    end,
    c.undergraduate_enrollment desc nulls last,
    c.school_name
  limit greatest(p_limit, 1);
$$;

comment on function public.search_institutions(text, int) is
  'Public autocomplete search over institution_cds_coverage. Returns up to p_limit rows ranked by name-exact > name-prefix > name-substring > other-substring, with enrollment as tie-breaker. SECURITY INVOKER so RLS on the coverage table applies — out_of_scope rows are hidden from anon/authenticated regardless of the explicit filter in this function.';

grant execute on function public.search_institutions(text, int) to anon, authenticated;

-- Self-test. Inserts a sentinel directory + coverage row, refreshes the
-- coverage table, exercises the RPC, asserts shape and ordering, then
-- cleans up. Aborts the migration if any assertion fails.
do $$
declare
  ipeds_a constant text := '9999101';
  ipeds_b constant text := '9999102';
  ipeds_c constant text := '9999103';
  found_count int;
  first_school text;
begin
  insert into public.institution_directory (
    ipeds_id, school_id, school_name, scorecard_data_year, in_scope, exclusion_reason, undergraduate_enrollment
  ) values
    (ipeds_a, '__test_search_alpha__', 'Alpha University',          '2024', true, null, 5000),
    (ipeds_b, '__test_search_beta__',  'Beta College',              '2024', true, null, 1000),
    (ipeds_c, '__test_search_gamma__', 'Gamma School of the Arts',  '2024', true, null, 500);

  perform public.refresh_institution_cds_coverage();

  -- Exact name match returns the right row.
  select count(*) into found_count
    from public.search_institutions('Alpha University', 5)
   where school_id = '__test_search_alpha__';
  if found_count <> 1 then
    raise exception 'M4 search self-test FAIL: exact match for "Alpha University" returned % rows', found_count;
  end if;

  -- Prefix match returns Beta first (only one Beta).
  select school_id into first_school
    from public.search_institutions('beta', 5)
   where school_id like '__test_search_%'
   order by 1 limit 1;
  if first_school is distinct from '__test_search_beta__' then
    raise exception 'M4 search self-test FAIL: prefix "beta" did not return beta first, got %', first_school;
  end if;

  -- Substring match catches name-internal tokens.
  select count(*) into found_count
    from public.search_institutions('arts', 5)
   where school_id = '__test_search_gamma__';
  if found_count <> 1 then
    raise exception 'M4 search self-test FAIL: substring "arts" did not return Gamma School of the Arts';
  end if;

  -- Empty query returns zero rows (length filter).
  select count(*) into found_count
    from public.search_institutions('   ', 5);
  if found_count <> 0 then
    raise exception 'M4 search self-test FAIL: blank query returned % rows, expected 0', found_count;
  end if;

  -- Cleanup. The fixture rows live in institution_directory only;
  -- deleting them and re-running refresh removes them from the
  -- coverage table without touching real data.
  delete from public.institution_directory where school_id like '__test_search_%';
  perform public.refresh_institution_cds_coverage();

  if exists (select 1 from public.search_institutions('Alpha University', 5)
              where school_id like '__test_search_%') then
    raise exception 'M4 search self-test FAIL: test fixtures leaked after cleanup';
  end if;
end$$;
