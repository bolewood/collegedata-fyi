-- PRD 015 M3 hotfix — derive_coverage_status precedence bug.
--
-- Symptom: 4 schools (Adams State, Albany State, Williams College — 28
-- archived years — and Saint Louis University) showed as
-- `no_public_cds_found` despite having `cds_documents` rows with
-- non-null source_url. They should have been `extract_failed`.
--
-- Root cause: the "latest discovery found nothing" branch only checked
-- `latest_extracted_year` before deciding between `cds_available_stale`
-- and `no_public_cds_found`. It never consulted `latest_found_year`.
-- Williams's history is the load-bearing case: 28 archived CDS PDFs
-- across 1998-99 → 2025-26, all with `extraction_status='failed'`
-- (Tier 4 cleaner couldn't parse them). The latest archive_queue
-- terminal is `transient` because the resolver couldn't fresh-fetch
-- on the most recent attempt. Status was computed as:
--
--   last_outcome='transient' → "found nothing" branch
--   latest_extracted_year=NULL (no extracted docs) → no_public_cds_found
--
-- That's wrong. We DO know Williams's CDS sources publicly — we have
-- 28 archived years. The right status is `extract_failed`: source
-- found, extraction needs review.
--
-- Fix: in the "found nothing" and "auth-walled" branches, fall through
-- to the cds_found CTE before declaring no source. If `latest_found_year`
-- is non-null, the school has a known source — even if the latest probe
-- couldn't reach it. Status takes the doc-state path:
--   - extraction failed → extract_failed
--   - extraction in flight → cds_found_processing
--
-- The "we have a usable extraction" path (cds_available_stale) keeps
-- precedence over the "we have a doc but extraction failed" path
-- because a stale-but-readable doc beats a found-but-broken doc.
--
-- After this CREATE OR REPLACE applies, refresh_institution_cds_coverage()
-- will be invoked at the bottom so the materialized table reflects the
-- corrected statuses immediately, without waiting for the 15-minute cron.

begin;

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
  -- The freshness signal is archive_queue.last_outcome. But when the
  -- queue says "found nothing" or "blocked," we still want to surface
  -- known doc state (extract_failed, cds_found_processing) over a
  -- generic no_public_cds_found / source_not_automatically_accessible
  -- claim — those should only fire when we genuinely have no source
  -- on file at all.
  select case
    when p_in_scope = false then 'out_of_scope'::public.coverage_status_t

    -- ── Latest discovery FOUND a source (or re-confirmed one) ──
    when p_last_outcome in ('inserted', 'refreshed', 'unchanged_verified', 'unchanged_repaired') then
      case
        when p_latest_extracted_year is not null
             and (p_latest_found_year is null
                  or p_latest_extracted_year >= p_latest_found_year)
          then 'cds_available_current'::public.coverage_status_t
        when p_latest_found_extraction_status = 'failed'
             and p_latest_extracted_year is not null
             and p_latest_found_year > p_latest_extracted_year
          then 'latest_found_extract_failed_with_prior_available'::public.coverage_status_t
        when p_latest_found_extraction_status = 'failed'
          then 'extract_failed'::public.coverage_status_t
        when p_latest_found_extraction_status in ('discovered', 'extraction_pending')
          then 'cds_found_processing'::public.coverage_status_t
        else 'cds_available_current'::public.coverage_status_t
      end

    -- ── Latest discovery FOUND NOTHING ──
    -- Three-way: usable extraction → stale; known source but extraction
    -- failed → extract_failed (the bug fix); pure no-source → no_public_cds_found.
    when p_last_outcome in ('no_pdfs_found', 'dead_url', 'wrong_content_type',
                            'transient', 'permanent_other', 'blocked_url',
                            'file_too_large') then
      case
        when p_latest_extracted_year is not null
          then 'cds_available_stale'::public.coverage_status_t
        when p_latest_found_year is not null
             and p_latest_found_extraction_status = 'failed'
          then 'extract_failed'::public.coverage_status_t
        when p_latest_found_year is not null
             and p_latest_found_extraction_status in ('discovered', 'extraction_pending')
          then 'cds_found_processing'::public.coverage_status_t
        else 'no_public_cds_found'::public.coverage_status_t
      end

    -- ── Latest discovery BLOCKED by auth wall ──
    -- Same three-way structure. A school we previously archived that
    -- now sits behind SSO is "extract_failed" (source known, can't
    -- refresh) over "source_not_automatically_accessible" (we never
    -- got the source).
    when p_last_outcome in ('auth_walled_microsoft', 'auth_walled_okta', 'auth_walled_google') then
      case
        when p_latest_extracted_year is not null
          then 'cds_available_stale'::public.coverage_status_t
        when p_latest_found_year is not null
             and p_latest_found_extraction_status = 'failed'
          then 'extract_failed'::public.coverage_status_t
        when p_latest_found_year is not null
             and p_latest_found_extraction_status in ('discovered', 'extraction_pending')
          then 'cds_found_processing'::public.coverage_status_t
        else 'source_not_automatically_accessible'::public.coverage_status_t
      end

    -- ── No queue history (legacy data, manual uploads, etc.) ──
    when p_latest_extracted_year is not null
         and (p_latest_found_year is null
              or p_latest_extracted_year >= p_latest_found_year)
      then 'cds_available_current'::public.coverage_status_t
    when p_latest_found_extraction_status in ('discovered', 'extraction_pending')
         and p_latest_extracted_year is null
      then 'cds_found_processing'::public.coverage_status_t
    when p_latest_found_extraction_status = 'failed'
         and p_latest_extracted_year is not null
         and p_latest_found_year > p_latest_extracted_year
      then 'latest_found_extract_failed_with_prior_available'::public.coverage_status_t
    when p_latest_found_extraction_status = 'failed'
      then 'extract_failed'::public.coverage_status_t

    else 'not_checked'::public.coverage_status_t
  end;
$$;

-- ── Self-test: regression coverage for the Williams scenario plus the
-- two new branches the fix introduces. ────────────────────────────────
do $$
declare
  ipeds_a constant text := '9999201'; -- Williams shape: failed extraction + transient queue
  ipeds_b constant text := '9999202'; -- pending extraction + no_pdfs_found queue
  ipeds_c constant text := '9999203'; -- failed extraction + auth_walled queue
  ipeds_d constant text := '9999204'; -- nothing in cds_documents + no_pdfs_found queue
                                       -- (control: confirms no_public_cds_found still fires)
  s text;
begin
  insert into public.institution_directory (
    ipeds_id, school_id, school_name, scorecard_data_year, in_scope, exclusion_reason
  ) values
    (ipeds_a, '__test_williams__',     'Test Williams Univ',    '2024', true, null),
    (ipeds_b, '__test_processing__',   'Test Processing Univ',  '2024', true, null),
    (ipeds_c, '__test_authwalled__',   'Test AuthWalled Univ',  '2024', true, null),
    (ipeds_d, '__test_nodocs__',       'Test NoDocs Univ',      '2024', true, null);

  -- Williams shape: known source URLs, extraction failed, latest probe transient.
  insert into public.cds_documents (id, school_id, school_name, cds_year, source_url, participation_status, extraction_status)
  values (gen_random_uuid(), '__test_williams__', 'Test Williams Univ', '2024-25',
          'https://example.edu/cds.pdf', 'published', 'failed');
  insert into public.archive_queue (
    enqueued_run_id, school_id, school_name, cds_url_hint, status, last_outcome, processed_at
  ) values (
    gen_random_uuid(), '__test_williams__', 'Test Williams Univ',
    'https://example.edu/', 'failed_permanent', 'transient', now()
  );

  -- Source found, extraction in flight, latest probe no_pdfs_found.
  insert into public.cds_documents (id, school_id, school_name, cds_year, source_url, participation_status, extraction_status)
  values (gen_random_uuid(), '__test_processing__', 'Test Processing Univ', '2024-25',
          'https://example.edu/cds2.pdf', 'published', 'extraction_pending');
  insert into public.archive_queue (
    enqueued_run_id, school_id, school_name, cds_url_hint, status, last_outcome, processed_at
  ) values (
    gen_random_uuid(), '__test_processing__', 'Test Processing Univ',
    'https://example.edu/', 'failed_permanent', 'no_pdfs_found', now()
  );

  -- Source found, extraction failed, latest probe auth_walled.
  insert into public.cds_documents (id, school_id, school_name, cds_year, source_url, participation_status, extraction_status)
  values (gen_random_uuid(), '__test_authwalled__', 'Test AuthWalled Univ', '2024-25',
          'https://example.edu/cds3.pdf', 'published', 'failed');
  insert into public.archive_queue (
    enqueued_run_id, school_id, school_name, cds_url_hint, status, last_outcome, processed_at
  ) values (
    gen_random_uuid(), '__test_authwalled__', 'Test AuthWalled Univ',
    'https://example.edu/', 'failed_permanent', 'auth_walled_microsoft', now()
  );

  -- Control: no cds_documents row, queue terminal no_pdfs_found.
  -- Confirms the fix doesn't accidentally swallow the "we tried, found
  -- nothing, have nothing" case.
  insert into public.archive_queue (
    enqueued_run_id, school_id, school_name, cds_url_hint, status, last_outcome, processed_at
  ) values (
    gen_random_uuid(), '__test_nodocs__', 'Test NoDocs Univ',
    'https://example.edu/', 'failed_permanent', 'no_pdfs_found', now()
  );

  perform public.refresh_institution_cds_coverage();

  select coverage_status::text into s
    from public.institution_cds_coverage where ipeds_id = ipeds_a;
  if s is distinct from 'extract_failed' then
    raise exception 'derive_coverage_status hotfix FAIL: Williams shape (failed-extract + transient queue) returned %, expected extract_failed', s;
  end if;

  select coverage_status::text into s
    from public.institution_cds_coverage where ipeds_id = ipeds_b;
  if s is distinct from 'cds_found_processing' then
    raise exception 'derive_coverage_status hotfix FAIL: pending-extract + no_pdfs_found queue returned %, expected cds_found_processing', s;
  end if;

  select coverage_status::text into s
    from public.institution_cds_coverage where ipeds_id = ipeds_c;
  if s is distinct from 'extract_failed' then
    raise exception 'derive_coverage_status hotfix FAIL: failed-extract + auth_walled queue returned %, expected extract_failed', s;
  end if;

  select coverage_status::text into s
    from public.institution_cds_coverage where ipeds_id = ipeds_d;
  if s is distinct from 'no_public_cds_found' then
    raise exception 'derive_coverage_status hotfix FAIL: control case (no docs + no_pdfs_found) returned %, expected no_public_cds_found — fix may have over-corrected', s;
  end if;

  -- Cleanup
  delete from public.archive_queue where school_id like '__test_%';
  delete from public.cds_documents where school_id like '__test_%';
  delete from public.institution_directory where school_id like '__test_%';

  perform public.refresh_institution_cds_coverage();

  if exists (select 1 from public.institution_cds_coverage where ipeds_id like '99992%') then
    raise exception 'derive_coverage_status hotfix FAIL: test fixtures leaked after cleanup';
  end if;
end$$;

commit;
