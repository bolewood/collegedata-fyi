-- PRD 015 M3 — Public-safe institution CDS coverage table.
--
-- This is the milestone that turns M1's directory rows + M2's resolver
-- attempts into a single materialized table the public API and search
-- can hit without computing status across four sources at read time.
--
-- The table answers one question per institution: "what do we know about
-- this school's CDS availability?" The answer is honest about the four
-- failure modes the PRD calls out — extracted, processing, found-but-
-- failed, attempted-but-no-source-found, attempted-and-blocked, never-
-- attempted, and human-verified-absent — instead of collapsing all of
-- them into "we have no data."
--
-- Atomic full-table replace via TRUNCATE+INSERT inside a transaction.
-- TRUNCATE acquires ACCESS EXCLUSIVE; concurrent readers in other
-- transactions wait for COMMIT and never see an empty table. ~6,300
-- rows means the lock window is sub-second.
--
-- Wrapped in BEGIN/COMMIT because Supabase CLI does not apply migrations
-- in a single implicit transaction. The wrapper makes the inline self-
-- test at the bottom load-bearing — if assertions fail, the entire
-- migration rolls back.
begin;

-- ─── coverage_status_t enum ─────────────────────────────────────────
-- Postgres ENUM (not text + CHECK) because two tables reference this
-- domain — institution_cds_coverage and institution_cds_coverage_overrides
-- — and a shared type guarantees they cannot drift. Adding a future
-- value is one ALTER TYPE ADD VALUE; renames are rare enough to live
-- with the explicit migration cost.
create type public.coverage_status_t as enum (
  'cds_available_current',
  'cds_available_stale',
  'cds_found_processing',
  'latest_found_extract_failed_with_prior_available',
  'extract_failed',
  'source_not_automatically_accessible',
  'no_public_cds_found',
  'verified_absent',
  'not_checked',
  'out_of_scope'
);

comment on type public.coverage_status_t is
  'Public coverage state per institution (PRD 015 M3). Precedence is computed by refresh_institution_cds_coverage(). out_of_scope is materialized but hidden by the public RLS policy. verified_absent is the only override-driven state today; the rest are derived from cds_documents + archive_queue + school_hosting_observations.';

-- ─── institution_cds_coverage_overrides ─────────────────────────────
-- Operator-curated layer for human-reviewed coverage state. Today's
-- only value-add is verified_absent — schools that have publicly stated
-- they do not publish a CDS — but the table is general enough to carry
-- forward any future override.

create table public.institution_cds_coverage_overrides (
  ipeds_id      text primary key,
  status        public.coverage_status_t not null,
  public_note   text,
  evidence_url  text,
  reviewed_by   text not null,
  reviewed_at   timestamptz not null default now()
);

comment on table public.institution_cds_coverage_overrides is
  'Operator-curated override layer for institution_cds_coverage. Each row pins a single ipeds_id to a specific coverage_status_t value, bypassing the automatic precedence in refresh_institution_cds_coverage(). Use sparingly — automated outcomes are the canonical signal. Today this carries verified_absent rows for schools that have publicly stated they do not publish a CDS.';

alter table public.institution_cds_coverage_overrides enable row level security;
-- No policies: service-role bypasses RLS, anon/authenticated cannot read.

-- ─── institution_cds_coverage ───────────────────────────────────────
-- One row per Title-IV institution from the directory. Out-of-scope
-- rows are materialized so an operator flipping in_scope on a single
-- directory row doesn't require a coverage refresh; the public RLS
-- policy filters them at read time.

create table public.institution_cds_coverage (
  ipeds_id                   text primary key,
  school_id                  text not null unique,
  school_name                text not null,
  aliases                    text[] not null default '{}',
  city                       text,
  state                      text,
  website_url                text,
  undergraduate_enrollment   integer,
  scorecard_data_year        text,

  coverage_status            public.coverage_status_t not null,
  coverage_label             text not null,
  coverage_summary           text not null,

  latest_available_cds_year  text,
  latest_found_cds_year      text,
  latest_attempted_year      text,
  latest_document_id         uuid,
  latest_public_source_url   text,
  latest_field_count         integer,
  last_checked_at            timestamptz,

  can_submit_source          boolean not null,

  search_text                text generated always as (
    lower(
      school_name
      || ' ' || coalesce(array_to_string(aliases, ' '), '')
      || ' ' || coalesce(city, '')
      || ' ' || coalesce(state, '')
    )
  ) stored,

  updated_at                 timestamptz not null default now()
);

comment on table public.institution_cds_coverage is
  'Materialized public-safe coverage state, one row per institution_directory ipeds_id. Refreshed atomically by refresh_institution_cds_coverage(); pg_cron hits the refresh-coverage edge function every 15 minutes. Public RLS allows reads of all rows except coverage_status = out_of_scope. Search and the school detail page should query this table, not the underlying cds_documents/archive_queue join.';

comment on column public.institution_cds_coverage.coverage_label is
  'Short public copy for the coverage badge (PRD line 442). Generated from a fixed copy map in coverage_status_label(); never free-form.';

comment on column public.institution_cds_coverage.coverage_summary is
  'One-paragraph public copy for the school page coverage panel (PRD line 469-485). Generated from a fixed copy map in coverage_status_summary(); never includes raw resolver notes, hosting observations, or operator commentary.';

comment on column public.institution_cds_coverage.can_submit_source is
  'True when the public should see a "send us the link" CTA — i.e., status is no_public_cds_found, source_not_automatically_accessible, or not_checked. False when the school has a usable extraction or has been verified_absent.';

comment on column public.institution_cds_coverage.latest_public_source_url is
  'Set only when status is cds_available_current and we have a published source URL we are already exposing elsewhere. Null for every other status — the column never leaks resolver-only or hosting-observation URLs.';

-- ─── Indexes ────────────────────────────────────────────────────────

create index institution_cds_coverage_status_idx
  on public.institution_cds_coverage (coverage_status);

create index institution_cds_coverage_state_idx
  on public.institution_cds_coverage (state)
  where coverage_status <> 'out_of_scope';

create index institution_cds_coverage_enrollment_idx
  on public.institution_cds_coverage (undergraduate_enrollment desc nulls last)
  where coverage_status <> 'out_of_scope';

create index institution_cds_coverage_search_idx
  on public.institution_cds_coverage
  using gin (to_tsvector('simple', search_text))
  where coverage_status <> 'out_of_scope';

-- ─── RLS ────────────────────────────────────────────────────────────

alter table public.institution_cds_coverage enable row level security;

create policy institution_cds_coverage_public_read
  on public.institution_cds_coverage
  for select
  to anon, authenticated
  using (coverage_status <> 'out_of_scope');

grant select on public.institution_cds_coverage to anon, authenticated;

-- ─── Helper: derive_coverage_status ─────────────────────────────────
-- Encodes the 9-rule precedence from PRD lines 326-346 in one place.
-- Called by refresh_institution_cds_coverage() once per directory row;
-- the result is reused for the label, summary, can_submit, and source
-- URL exposure decision. Keeps the precedence visible in one CASE
-- instead of duplicated across the INSERT and three derived columns.

create or replace function public.derive_coverage_status(
  p_in_scope boolean,
  p_latest_extracted_year text,
  p_latest_found_year text,
  p_latest_found_extraction_status text,
  p_last_outcome text
)
returns public.coverage_status_t
language sql
immutable
set search_path = public
as $$
  select case
    when p_in_scope = false then 'out_of_scope'::public.coverage_status_t
    -- Newest found year IS the newest extracted year → fully current.
    when p_latest_extracted_year is not null
         and (p_latest_found_year is null
              or p_latest_extracted_year >= p_latest_found_year)
      then 'cds_available_current'::public.coverage_status_t
    -- Newer source found, extraction in flight, no older fallback.
    when p_latest_found_extraction_status in ('discovered', 'extraction_pending')
         and p_latest_extracted_year is null
      then 'cds_found_processing'::public.coverage_status_t
    -- Newer source found, extraction failed, older usable extraction exists.
    when p_latest_found_extraction_status = 'failed'
         and p_latest_extracted_year is not null
         and p_latest_found_year > p_latest_extracted_year
      then 'latest_found_extract_failed_with_prior_available'::public.coverage_status_t
    -- Source found, extraction failed, no older fallback.
    when p_latest_found_extraction_status = 'failed'
         and p_latest_extracted_year is null
      then 'extract_failed'::public.coverage_status_t
    -- Latest discovery hit an auth wall.
    when p_last_outcome in ('auth_walled_microsoft', 'auth_walled_okta', 'auth_walled_google')
         and p_latest_extracted_year is not null
      then 'cds_available_stale'::public.coverage_status_t
    when p_last_outcome in ('auth_walled_microsoft', 'auth_walled_okta', 'auth_walled_google')
      then 'source_not_automatically_accessible'::public.coverage_status_t
    -- Latest discovery probed and found nothing.
    when p_last_outcome in ('no_pdfs_found', 'dead_url', 'wrong_content_type',
                            'transient', 'permanent_other', 'blocked_url',
                            'file_too_large')
         and p_latest_extracted_year is not null
      then 'cds_available_stale'::public.coverage_status_t
    when p_last_outcome in ('no_pdfs_found', 'dead_url', 'wrong_content_type',
                            'transient', 'permanent_other', 'blocked_url',
                            'file_too_large')
      then 'no_public_cds_found'::public.coverage_status_t
    -- Resolver has never attempted this school.
    else 'not_checked'::public.coverage_status_t
  end;
$$;

-- ─── Helper: coverage_status_label ──────────────────────────────────
-- Fixed copy map for the public coverage badge (PRD line 442). Never
-- produces free-form text.

create or replace function public.coverage_status_label(p_status public.coverage_status_t)
returns text
language sql
immutable
as $$
  select case p_status
    when 'cds_available_current' then 'CDS available'
    when 'cds_available_stale' then 'Older CDS available'
    when 'cds_found_processing' then 'CDS found; processing'
    when 'latest_found_extract_failed_with_prior_available' then 'Latest CDS needs review; older CDS available'
    when 'extract_failed' then 'CDS found; extraction needs review'
    when 'source_not_automatically_accessible' then 'Source could not be accessed automatically'
    when 'no_public_cds_found' then 'No public CDS found'
    when 'verified_absent' then 'CDS not published or not applicable'
    when 'not_checked' then 'Not checked yet'
    when 'out_of_scope' then 'Out of scope'
  end;
$$;

-- ─── Helper: coverage_status_summary ────────────────────────────────
-- Fixed copy map for the school-page coverage paragraph (PRD line
-- 469-485). The cds_available_stale case has two variants depending on
-- whether the latest discovery hit an auth wall — baked in here per
-- M3 review decision (rather than exposing a separate subreason
-- column). The override path uses the operator-supplied public_note
-- when present; otherwise falls back to a default verified_absent line.

create or replace function public.coverage_status_summary(
  p_school_name text,
  p_status public.coverage_status_t,
  p_latest_extracted_year text,
  p_latest_found_year text,
  p_last_outcome text,
  p_override_note text
)
returns text
language sql
immutable
as $$
  select case p_status
    when 'cds_available_current' then
      'We have a CDS for ' || p_school_name
      || coalesce(' from ' || p_latest_extracted_year, '') || '.'
    when 'cds_available_stale' then
      case
        when p_last_outcome in ('auth_walled_microsoft', 'auth_walled_okta', 'auth_walled_google') then
          'We have an older CDS for ' || p_school_name
          || coalesce(' from ' || p_latest_extracted_year, '')
          || '. We found a possible newer source but it could not be accessed automatically.'
        else
          'We have an older CDS for ' || p_school_name
          || coalesce(' from ' || p_latest_extracted_year, '')
          || '; we could not find a newer one in our latest scan.'
      end
    when 'cds_found_processing' then
      'We found a CDS for ' || p_school_name
      || ' but our extraction has not yet completed.'
    when 'latest_found_extract_failed_with_prior_available' then
      'We have an older CDS for ' || p_school_name
      || coalesce(' from ' || p_latest_extracted_year, '')
      || '; the newer one we found could not be extracted automatically.'
    when 'extract_failed' then
      'We found a possible CDS for ' || p_school_name
      || ' but our extraction failed and we have no older copy.'
    when 'source_not_automatically_accessible' then
      'We found a possible CDS source for ' || p_school_name
      || ' but it could not be accessed automatically.'
    when 'no_public_cds_found' then
      'We could not find a public Common Data Set for ' || p_school_name
      || ' in our latest scan.'
    when 'verified_absent' then
      coalesce(p_override_note,
        'We have no CDS for ' || p_school_name
        || '; this school has not made one publicly available.')
    when 'not_checked' then
      p_school_name || ' is in our institution directory, but we have not '
      || 'completed a public CDS scan for it yet.'
    when 'out_of_scope' then
      ''
  end;
$$;

-- ─── refresh_institution_cds_coverage ───────────────────────────────
-- Atomic full-table replace inside a single transaction. CTEs compute
-- the latest extraction state and latest archive_queue terminal per
-- school; the resolved CTE attaches them to each directory row plus
-- the override (if any) and computes coverage_status once via the
-- helper. The INSERT then references coverage_status for the label,
-- summary, can_submit_source, and the source-URL exposure gate.

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
  -- TRUNCATE acquires ACCESS EXCLUSIVE on its own; explicit LOCK is
  -- redundant. Concurrent readers in other transactions wait until
  -- the new rows are committed and never observe an empty table.
  truncate table public.institution_cds_coverage;

  with
    -- Latest extraction state per school. Picks the row with the
    -- newest cds_year that is fully extracted (gives latest_available)
    -- and separately the row with the newest cds_year regardless of
    -- extraction state (gives latest_found). cds_year strings are
    -- lexicographically comparable in the canonical "YYYY-YY" form.
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
    -- Latest terminal archive_queue row per school. Drives
    -- last_checked_at and the failure-mode discrimination in the
    -- status helper. Only terminal rows (done/failed_permanent) carry
    -- a meaningful last_outcome.
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
    -- Aliases per institution from the slug crosswalk. Excludes
    -- 'redirect' source so retired slugs don't show up in search
    -- results — they should produce 301s, not appear in the alias
    -- list.
    crosswalk_aliases as (
      select
        ipeds_id,
        array_agg(distinct alias) filter (where source <> 'redirect') as aliases
      from public.institution_slug_crosswalk
      group by ipeds_id
    ),
    -- Resolved row: directory + extracted + found + queue + override.
    -- coverage_status is computed once here and consumed by the
    -- INSERT below for label, summary, source-URL exposure, and the
    -- can_submit_source flag.
    resolved as (
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
        )                                                 as coverage_status
      from public.institution_directory d
      left join cds_extracted ce on ce.school_id = d.school_id
      left join cds_found cf on cf.school_id = d.school_id
      left join queue_latest q on q.school_id = d.school_id
      left join crosswalk_aliases ca on ca.ipeds_id = d.ipeds_id
      left join public.institution_cds_coverage_overrides o on o.ipeds_id = d.ipeds_id
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
    -- Only expose source URL when status is cds_available_current.
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

-- ─── Self-test ──────────────────────────────────────────────────────
-- Inserts test fixtures into the four input tables, runs the refresh
-- function, asserts each scenario produces the expected coverage_status,
-- then cleans up. Aborts (and rolls back the whole migration) on any
-- mismatch. Same pattern as the archive_pipeline migration self-test.
--
-- Sentinel ipeds_id prefix '99990xx' so test rows can never collide
-- with real Scorecard UNITIDs (max real UNITID is in the 500K range).

do $$
declare
  ipeds_current     constant text := '9999001';
  ipeds_failed      constant text := '9999002';
  ipeds_stale       constant text := '9999003';
  ipeds_processing  constant text := '9999004';
  ipeds_unchecked   constant text := '9999005';
  ipeds_no_cds      constant text := '9999006';
  ipeds_override    constant text := '9999007';

  doc_current_id   uuid := gen_random_uuid();
  doc_old_id       uuid := gen_random_uuid();
  doc_old_stale_id uuid := gen_random_uuid();

  s text;
begin
  insert into public.institution_directory (
    ipeds_id, school_id, school_name, scorecard_data_year, in_scope, exclusion_reason
  )
  values
    (ipeds_current,    '__test_current__',    'Test Current Univ',    '2024', true, null),
    (ipeds_failed,     '__test_failed__',     'Test Failed Univ',     '2024', true, null),
    (ipeds_stale,      '__test_stale__',      'Test Stale Univ',      '2024', true, null),
    (ipeds_processing, '__test_processing__', 'Test Processing Univ', '2024', true, null),
    (ipeds_unchecked,  '__test_unchecked__',  'Test Unchecked Univ',  '2024', true, null),
    (ipeds_no_cds,     '__test_no_cds__',     'Test NoCDS Univ',      '2024', true, null),
    (ipeds_override,   '__test_override__',   'Test Override Univ',   '2024', true, null);

  -- Scenario 1: extracted == found, current state.
  insert into public.cds_documents (id, school_id, school_name, cds_year, source_url, participation_status, extraction_status)
  values (doc_current_id, '__test_current__', 'Test Current Univ', '2024-25',
          'https://test.example/cds.pdf', 'published', 'extracted');

  -- Scenario 2: older extracted (2023-24), newer failed (2024-25).
  insert into public.cds_documents (id, school_id, school_name, cds_year, source_url, participation_status, extraction_status)
  values
    (doc_old_id, '__test_failed__', 'Test Failed Univ', '2023-24',
     'https://test.example/old.pdf', 'published', 'extracted'),
    (gen_random_uuid(), '__test_failed__', 'Test Failed Univ', '2024-25',
     'https://test.example/new.pdf', 'published', 'failed');

  -- Scenario 3: older extracted, no newer source — but archive_queue
  -- terminal says we tried recently with no_pdfs_found.
  insert into public.cds_documents (id, school_id, school_name, cds_year, source_url, participation_status, extraction_status)
  values (doc_old_stale_id, '__test_stale__', 'Test Stale Univ', '2022-23',
          'https://test.example/older.pdf', 'published', 'extracted');
  insert into public.archive_queue (
    enqueued_run_id, school_id, school_name, cds_url_hint, status, last_outcome, processed_at
  ) values (
    gen_random_uuid(), '__test_stale__', 'Test Stale Univ',
    'https://test.example/', 'done', 'no_pdfs_found', now()
  );

  -- Scenario 4: newer source discovered but extraction pending.
  insert into public.cds_documents (id, school_id, school_name, cds_year, source_url, participation_status, extraction_status)
  values (gen_random_uuid(), '__test_processing__', 'Test Processing Univ', '2024-25',
          'https://test.example/process.pdf', 'published', 'extraction_pending');

  -- Scenario 5: directory only, no archive_queue, no cds_documents.

  -- Scenario 6 (M2 case): archive_queue terminal, no cds_documents.
  insert into public.archive_queue (
    enqueued_run_id, school_id, school_name, cds_url_hint, status, last_outcome, processed_at, source
  ) values (
    gen_random_uuid(), '__test_no_cds__', 'Test NoCDS Univ',
    'https://test.example/', 'failed_permanent', 'no_pdfs_found', now(), 'institution_directory'
  );

  -- Scenario 7: override beats automatic precedence.
  insert into public.institution_cds_coverage_overrides (ipeds_id, status, public_note, reviewed_by)
  values (ipeds_override, 'verified_absent',
          'Confirmed via IR contact 2025-08-01: school does not publish CDS.',
          'self_test');

  perform public.refresh_institution_cds_coverage();

  select coverage_status::text into s
    from public.institution_cds_coverage where ipeds_id = ipeds_current;
  if s is distinct from 'cds_available_current' then
    raise exception 'M3 self-test FAIL scenario 1: expected cds_available_current, got %', s;
  end if;

  select coverage_status::text into s
    from public.institution_cds_coverage where ipeds_id = ipeds_failed;
  if s is distinct from 'latest_found_extract_failed_with_prior_available' then
    raise exception 'M3 self-test FAIL scenario 2: expected latest_found_extract_failed_with_prior_available, got %', s;
  end if;

  select coverage_status::text into s
    from public.institution_cds_coverage where ipeds_id = ipeds_stale;
  if s is distinct from 'cds_available_stale' then
    raise exception 'M3 self-test FAIL scenario 3: expected cds_available_stale, got %', s;
  end if;

  select coverage_status::text into s
    from public.institution_cds_coverage where ipeds_id = ipeds_processing;
  if s is distinct from 'cds_found_processing' then
    raise exception 'M3 self-test FAIL scenario 4: expected cds_found_processing, got %', s;
  end if;

  select coverage_status::text into s
    from public.institution_cds_coverage where ipeds_id = ipeds_unchecked;
  if s is distinct from 'not_checked' then
    raise exception 'M3 self-test FAIL scenario 5: expected not_checked, got %', s;
  end if;

  select coverage_status::text into s
    from public.institution_cds_coverage where ipeds_id = ipeds_no_cds;
  if s is distinct from 'no_public_cds_found' then
    raise exception 'M3 self-test FAIL scenario 6: expected no_public_cds_found, got %', s;
  end if;

  select coverage_status::text into s
    from public.institution_cds_coverage where ipeds_id = ipeds_override;
  if s is distinct from 'verified_absent' then
    raise exception 'M3 self-test FAIL scenario 7: expected verified_absent, got %', s;
  end if;

  -- Sanity: can_submit_source maps correctly.
  if not exists (
    select 1 from public.institution_cds_coverage
    where ipeds_id = ipeds_no_cds and can_submit_source = true
  ) then
    raise exception 'M3 self-test FAIL: can_submit_source should be true for no_public_cds_found';
  end if;
  if exists (
    select 1 from public.institution_cds_coverage
    where ipeds_id = ipeds_current and can_submit_source = true
  ) then
    raise exception 'M3 self-test FAIL: can_submit_source should be false for cds_available_current';
  end if;

  -- Sanity: latest_public_source_url exposed only on cds_available_current.
  if not exists (
    select 1 from public.institution_cds_coverage
    where ipeds_id = ipeds_current and latest_public_source_url is not null
  ) then
    raise exception 'M3 self-test FAIL: latest_public_source_url missing on cds_available_current row';
  end if;
  if exists (
    select 1 from public.institution_cds_coverage
    where ipeds_id in (ipeds_failed, ipeds_stale, ipeds_processing, ipeds_no_cds)
      and latest_public_source_url is not null
  ) then
    raise exception 'M3 self-test FAIL: latest_public_source_url leaked on a non-current row';
  end if;

  -- Cleanup: delete fixtures from input tables, then re-run refresh
  -- so the materialized table reflects production state without
  -- sentinels.
  delete from public.archive_queue                       where school_id like '__test_%';
  delete from public.cds_documents                       where school_id like '__test_%';
  delete from public.institution_cds_coverage_overrides  where ipeds_id like '99990%';
  delete from public.institution_directory               where school_id like '__test_%';

  perform public.refresh_institution_cds_coverage();

  if exists (
    select 1 from public.institution_cds_coverage where ipeds_id like '99990%'
  ) then
    raise exception 'M3 self-test FAIL: test fixture rows leaked into institution_cds_coverage after cleanup';
  end if;
end$$;

commit;
