-- Rename text in the scholarship view and in three comments.
--
-- Prepared for the rename cutover; apply from main after the old hosts
-- permanently redirect. Text only: no column, grant or logic change.
--
-- The view body is copied verbatim from
-- 20261118120000_scholarship_directory_other_info.sql (the latest definition;
-- no later migration redefines it) and matches the production pg_get_viewdef
-- of 2026-11-26 column for column. Only the attribution literal changes.
-- security_invoker is restated because create or replace view resets options
-- that are not listed.

begin;

create or replace view public.scholarship_directory
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
  'Scholarship program data from Quadfile (https://www.quadfile.org/scholarships), CC BY-SA 4.0. Terms as published by each school; see the source link on each record.'::text as attribution
from public.scholarship_directory_cache c;

comment on view public.scholarship_directory is
  'PRD 036 named scholarship programs: the latest non-unverified version per program, one row per participating school, with freshness_status computed at query time. Every row carries license and attribution; please display the attribution. Backed by scholarship_directory_cache.';

revoke all on public.scholarship_directory from public, anon, authenticated;
grant select on public.scholarship_directory to anon, authenticated;

comment on column public.api_usage_events.client_name is
  'Self-declared client marker from X-Quadfile-Client (or the older X-CollegeData-Client), qf_client or cd_client. Sanitized before insert; untrusted and advisory only.';

comment on table public.api_usage_downloads_daily is
  'PRD 033. Unique archive downloads per UTC day: one client key (IP + user agent, never stored) x one file x one day. access_method: browser, machine (scripts, AI agents acting for a person, unknown clients, and browser keys over the heavy-client threshold), bots_crawlers (declared bots and AI crawlers), excluded (our pipeline). from_site marks fetches with a Quadfile or collegedata.fyi referer. raw_downloads counts every 200/206 GET. Rows are replaced per (day, method_version).';

comment on table public.usage_public_daily is
  'PRD 033. Public whole-archive usage per closed UTC day. unique_downloads: one client x one archive file x one day, by access method and client kind (heavy_browser = browser-like clients over 30 files a day, counted as machine). site_downloads: browser downloads that followed a link on Quadfile. api_requests: third-party PostgREST and Edge Function requests. friendly_api_requests: calls to the Quadfile /api routes and MCP server. serving_requests: requests the site and friendly API made to serve pages. CC0.';

do $$
declare
  v_def text := pg_get_viewdef('public.scholarship_directory'::regclass);
  v_attr text;
  v_c1 text := col_description('public.api_usage_events'::regclass,
    (select attnum from pg_attribute
      where attrelid = 'public.api_usage_events'::regclass and attname = 'client_name'));
  v_c2 text := obj_description('public.api_usage_downloads_daily'::regclass, 'pg_class');
  v_c3 text := obj_description('public.usage_public_daily'::regclass, 'pg_class');
begin
  -- Check the stored definition (an empty cache would skip a row check) and one row.
  if v_def not like '%https://www.quadfile.org/scholarships%' or v_def like '%collegedata.fyi%' then
    raise exception 'scholarship_directory attribution not renamed';
  end if;
  select attribution into v_attr from public.scholarship_directory limit 1;
  if v_attr is not null and v_attr not like '%https://www.quadfile.org/scholarships%' then
    raise exception 'scholarship_directory row attribution not renamed: %', v_attr;
  end if;
  if v_c1 like '%collegedata.fyi%'
     or v_c1 not like '%X-Quadfile-Client (or the older X-CollegeData-Client)%' then
    raise exception 'client_name comment not renamed: %', v_c1;
  end if;
  -- The one collegedata.fyi kept on purpose: "a Quadfile or collegedata.fyi referer".
  if v_c2 not like '%a Quadfile or collegedata.fyi referer%'
     or replace(v_c2, 'a Quadfile or collegedata.fyi referer', '') like '%collegedata.fyi%' then
    raise exception 'api_usage_downloads_daily comment not renamed: %', v_c2;
  end if;
  if v_c3 like '%collegedata.fyi%'
     or v_c3 not like '%link on Quadfile%' or v_c3 not like '%the Quadfile /api routes%' then
    raise exception 'usage_public_daily comment not renamed: %', v_c3;
  end if;
end
$$;

commit;
