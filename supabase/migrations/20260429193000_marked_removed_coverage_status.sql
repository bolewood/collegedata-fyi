-- PRD 015 M3 hotfix - `marked_removed` is a real terminal probe.
--
-- Directory-enqueue can produce archive_queue rows whose successful
-- archive action is `marked_removed` when the resolver reaches a stale
-- source URL and confirms the upstream file is gone. That is not the
-- same as "never checked"; public coverage should reflect a completed
-- scan. Treat it with the same precedence as no_pdfs_found/dead_url:
-- known usable archive remains stale, known failed/pending source keeps
-- its source state, and no source on file becomes no_public_cds_found.

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

    -- Latest discovery FOUND a source (or re-confirmed one).
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

    -- Latest discovery FOUND NOTHING / SOURCE GONE.
    -- Three-way: usable extraction -> stale; known source but extraction
    -- failed/pending keeps that state; pure no-source -> no_public_cds_found.
    when p_last_outcome in ('marked_removed', 'no_pdfs_found', 'dead_url',
                            'wrong_content_type', 'transient',
                            'permanent_other', 'blocked_url',
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

    -- Latest discovery BLOCKED by auth wall.
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

    -- No queue history (legacy data, manual uploads, etc.).
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

do $$
declare
  s public.coverage_status_t;
begin
  -- Directory-only, terminal marked_removed means we checked and found no
  -- public source; it must not remain not_checked.
  select public.derive_coverage_status(true, null, null, null, 'marked_removed')
    into s;
  if s is distinct from 'no_public_cds_found' then
    raise exception 'marked_removed coverage hotfix FAIL: no-doc shape returned %, expected no_public_cds_found', s;
  end if;

  -- Existing usable archive stays stale when the latest probe says the
  -- upstream source is gone.
  select public.derive_coverage_status(true, '2023-24', null, null, 'marked_removed')
    into s;
  if s is distinct from 'cds_available_stale' then
    raise exception 'marked_removed coverage hotfix FAIL: existing archive shape returned %, expected cds_available_stale', s;
  end if;

  -- Known source states should not be hidden by a later marked_removed
  -- queue terminal.
  select public.derive_coverage_status(true, null, '2024-25', 'failed', 'marked_removed')
    into s;
  if s is distinct from 'extract_failed' then
    raise exception 'marked_removed coverage hotfix FAIL: failed source shape returned %, expected extract_failed', s;
  end if;
end $$;
