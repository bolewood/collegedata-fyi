-- PRD 036 M2: named scholarship directory storage and public serving path.
--
-- Records are authored as YAML under data/scholarships/ and loaded by
-- tools/scholarships/load.py from main. This migration adds:
--   scholarship_programs          program-level facts
--   scholarship_program_versions  one row per entering-class version, typed
--                                 filter columns plus the full record jsonb
--   scholarship_sources           official sources per version
--   scholarship_version_checks    monitor results (written by M4, never by YAML)
--   scholarship_directory_cache   materialized public rows (one per program per
--                                 participating school)
--   scholarship_directory         thin security_invoker view; computes
--                                 freshness_status at query time
--   refresh_scholarship_directory_cache()
--
-- Same shape as school_merit_profile in 20260627133000_materialize_public_serving_paths.sql.
--
-- Access model: the four base tables are service-role only (RLS enabled, no
-- policies, anon/authenticated privileges revoked). Anon and authenticated may
-- SELECT the view and the cache it reads. The cache grant is required: a
-- security_invoker view checks the caller's privileges on what it reads, and
-- the merit-profile pattern grants the cache for the same reason.
--
-- Keys: version_id is unique only within a program (the validator checks it per
-- file), so versions are keyed on (program_id, version_id).

create table public.scholarship_programs (
  program_id text primary key,
  school_id text not null,
  ipeds_id text not null,
  -- [{school_id, ipeds_id}], lead school first; a one-school program lists itself.
  participating_schools jsonb not null,
  applicable_campuses text[] not null default '{}',
  official_name text not null,
  aliases text[] not null default '{}',
  program_family text not null
    check (program_family in ('stamps', 'national_merit', 'presidential', 'honors', 'other')),
  awarding_authority text not null
    check (awarding_authority in ('institution', 'affiliated_foundation', 'cofunded', 'unknown')),
  related_programs jsonb not null default '[]'::jsonb,
  status text not null
    check (status in ('active', 'paused', 'closed_to_new_entrants', 'merged', 'discontinued', 'unknown')),
  file_path text,
  loaded_at timestamptz not null default now()
);

create index scholarship_programs_school_idx on public.scholarship_programs (school_id);

create table public.scholarship_program_versions (
  program_id text not null references public.scholarship_programs (program_id) on delete cascade,
  version_id text not null,
  primary key (program_id, version_id),
  supersedes text,
  -- True when no other version supersedes this one. The directory serves the
  -- head of each chain; the loader computes the flag.
  is_chain_head boolean not null,
  entry_year integer,
  entry_year_label text,
  entry_terms text[] not null default '{}',
  source_cohort_text text,
  verification_status text not null
    check (verification_status in ('verified', 'conflicting', 'historical_only', 'unverified')),
  last_reviewed_at date,
  reviewed_by text,
  owner_spot_checked boolean,
  program_status_for_entry text,
  -- Typed filter columns for /scholarships (PRD M3). Version-level arrays, so
  -- PostgREST cs / ov filters work: ?coverages=cs.{full_tuition}
  coverages text[] not null default '{}',
  selection_modes text[] not null default '{}',
  residencies text[] not null default '{}',
  national_merit_statuses text[] not null default '{}',
  need_roles text[] not null default '{}',
  separate_application text,
  deadline_months integer[] not null default '{}',
  key_deadline date,
  latest_milestone_date date,
  source_retrieved_at date,
  -- The record's offers with the derived normalized_coverage added to each.
  offers jsonb not null default '[]'::jsonb,
  -- The full version exactly as authored in YAML.
  record jsonb not null,
  loaded_at timestamptz not null default now()
);

create index scholarship_program_versions_year_idx
  on public.scholarship_program_versions (entry_year);

create table public.scholarship_sources (
  program_id text not null,
  version_id text not null,
  source_id text not null,
  primary key (program_id, version_id, source_id),
  foreign key (program_id, version_id)
    references public.scholarship_program_versions (program_id, version_id) on delete cascade,
  url text not null,
  authority text not null
    check (authority in (
      'official_program', 'official_aid_policy', 'official_admissions',
      'official_news', 'archived_official', 'foundation_official'
    )),
  retrieved_at date not null,
  content_sha256 text,
  archive_url text
);

-- Written by the change monitor (M4), never by the loader or the YAML files:
-- verified versions are immutable, so check state lives here. The public view
-- reads the latest row per version. Deleting a version deletes its checks.
create table public.scholarship_version_checks (
  id bigint generated always as identity primary key,
  program_id text not null,
  version_id text not null,
  foreign key (program_id, version_id)
    references public.scholarship_program_versions (program_id, version_id) on delete cascade,
  checked_at timestamptz not null default now(),
  result text not null
    check (result in ('unchanged', 'changed', 'stale_signal', 'unreachable', 'conflicting')),
  needs_review boolean not null default false,
  detail jsonb not null default '{}'::jsonb
);

create index scholarship_version_checks_latest_idx
  on public.scholarship_version_checks (program_id, version_id, checked_at desc, id desc);

alter table public.scholarship_programs enable row level security;
alter table public.scholarship_program_versions enable row level security;
alter table public.scholarship_sources enable row level security;
alter table public.scholarship_version_checks enable row level security;

-- Supabase grants new public tables to anon and authenticated by default; the
-- base tables are not public API.
revoke all on public.scholarship_programs from public, anon, authenticated;
revoke all on public.scholarship_program_versions from public, anon, authenticated;
revoke all on public.scholarship_sources from public, anon, authenticated;
revoke all on public.scholarship_version_checks from public, anon, authenticated;
grant all on public.scholarship_programs to service_role;
grant all on public.scholarship_program_versions to service_role;
grant all on public.scholarship_sources to service_role;
grant all on public.scholarship_version_checks to service_role;

comment on table public.scholarship_programs is
  'PRD 036 named scholarship programs, loaded from data/scholarships/ by tools/scholarships/load.py. Service role only; read through scholarship_directory.';
comment on table public.scholarship_program_versions is
  'PRD 036 one row per entering-class version of a program. Keyed on (program_id, version_id). Service role only.';
comment on table public.scholarship_sources is
  'PRD 036 official sources per program version. Service role only.';
comment on table public.scholarship_version_checks is
  'PRD 036 monitor results per program version, written by the M4 monitor. The latest row per version feeds freshness_status. Service role only.';

-- Freshness rule. The view calls these at query time, so a version ages out
-- without a cache refresh.
--
-- Entry cycle: a class entering in fall Y is the current cycle from 1 July of
-- Y-1 (the validator's application window opens then). So the current entry
-- year at time t is year(t) + 1 when month(t) >= 7, else year(t), in UTC.
-- On 2026-11-14 that is 2027.
--
-- freshness_status, first match wins:
--   conflicting               verification_status = 'conflicting', or the latest
--                             check result is 'conflicting'
--   past_cycle                verification_status = 'historical_only'; or
--                             entry_year < current entry year; or entry_year is
--                             null and its latest dated milestone is before today
--   current_cycle_unconfirmed entry_year is null (cycle not stated); or the latest
--                             check set needs_review; or the status is anything
--                             other than 'verified'
--   current_cycle_verified    verified, entry_year >= current entry year, and no
--                             open needs_review on the latest check
-- A version for a later entry year than the current one counts as current cycle.
create function public.scholarship_current_entry_year(p_at timestamptz default now())
returns integer
language sql
stable
as $$
  select (extract(year from p_at at time zone 'UTC'))::integer
    + case when extract(month from p_at at time zone 'UTC') >= 7 then 1 else 0 end;
$$;

create function public.scholarship_freshness_status(
  p_entry_year integer,
  p_verification_status text,
  p_latest_milestone_date date,
  p_check_result text,
  p_check_needs_review boolean,
  p_at timestamptz default now()
)
returns text
language sql
stable
as $$
  select case
    when p_verification_status = 'conflicting' or p_check_result = 'conflicting'
      then 'conflicting'
    when p_verification_status = 'historical_only'
      or (p_entry_year is not null and p_entry_year < public.scholarship_current_entry_year(p_at))
      or (p_entry_year is null
          and p_latest_milestone_date is not null
          and p_latest_milestone_date < (p_at at time zone 'UTC')::date)
      then 'past_cycle'
    when p_entry_year is null
      or coalesce(p_check_needs_review, false)
      or p_verification_status is distinct from 'verified'
      then 'current_cycle_unconfirmed'
    else 'current_cycle_verified'
  end;
$$;

comment on function public.scholarship_freshness_status(integer, text, date, text, boolean, timestamptz) is
  'PRD 036 freshness_status: conflicting, then past_cycle, then current_cycle_unconfirmed, else current_cycle_verified. Entry cycle turns over on 1 July (UTC) of the year before entry.';

-- One row per program per participating school (a joint program appears once
-- for each school). Per program the cache holds the latest entry year whose
-- chain head is not unverified, so an unverified draft never reaches the
-- public. Time-dependent status is not computed here: a materialized view
-- freezes now() at refresh time, and the loader refreshes only when YAML
-- changes. The inputs are stored instead and the view derives freshness_status.
-- The monitor must call refresh_scholarship_directory_cache() after writing checks.
create materialized view public.scholarship_directory_cache as
with heads as (
  select distinct on (v.program_id) v.*
  from public.scholarship_program_versions v
  where v.is_chain_head
    and v.verification_status <> 'unverified'
  order by v.program_id, v.entry_year desc nulls last, v.version_id
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
  h.need_roles,
  h.separate_application,
  h.deadline_months,
  h.key_deadline,
  h.latest_milestone_date,
  h.source_retrieved_at,

  h.offers,
  nullif(h.record -> 'application', 'null'::jsonb) as application,
  nullif(h.record -> 'renewal_rules', 'null'::jsonb) as renewal_rules,
  nullif(h.record -> 'stacking_rules', 'null'::jsonb) as stacking_rules,
  coalesce(nullif(h.record -> 'award_counts', 'null'::jsonb), '[]'::jsonb) as award_counts,
  coalesce(src.sources, '[]'::jsonb) as sources,

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

revoke all on public.scholarship_directory_cache from public, anon, authenticated;
grant select on public.scholarship_directory_cache to anon, authenticated;

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
    c.latest_milestone_date,
    c.last_check_result,
    c.needs_review
  ) as freshness_status,
  public.scholarship_current_entry_year() as current_entry_year,
  c.last_reviewed_at,
  c.reviewed_by,
  c.owner_spot_checked,
  c.program_status_for_entry,

  c.coverages,
  c.selection_modes,
  c.residencies,
  c.national_merit_statuses,
  c.need_roles,
  c.separate_application,
  c.deadline_months,
  c.key_deadline,
  c.latest_milestone_date,
  c.source_retrieved_at,

  c.offers,
  c.application,
  c.renewal_rules,
  c.stacking_rules,
  c.award_counts,
  c.sources,

  c.last_check_at,
  c.needs_review,

  'CC-BY-SA-4.0'::text as license,
  'Scholarship program data from collegedata.fyi (https://collegedata.fyi/scholarships), CC BY-SA 4.0. Terms as published by each school; see the source link on each record.'::text as attribution
from public.scholarship_directory_cache c;

comment on view public.scholarship_directory is
  'PRD 036 named scholarship programs: the latest non-unverified version per program, one row per participating school, with freshness_status computed at query time. Every row carries license and attribution; please display the attribution. Backed by scholarship_directory_cache.';

grant select on public.scholarship_directory to anon, authenticated;

create function public.refresh_scholarship_directory_cache()
returns integer
language plpgsql
security definer
set search_path = public
as $$
declare
  refreshed_count integer;
begin
  refresh materialized view concurrently public.scholarship_directory_cache;
  select count(*) into refreshed_count from public.scholarship_directory_cache;
  return refreshed_count;
end;
$$;

comment on function public.refresh_scholarship_directory_cache() is
  'Refreshes the materialized scholarship_directory serving cache after the loader or the change monitor writes.';

-- Supabase also grants EXECUTE on new public functions to anon and authenticated.
revoke all on function public.refresh_scholarship_directory_cache() from public, anon, authenticated;
grant execute on function public.refresh_scholarship_directory_cache() to service_role;
