-- Extend archive_queue.last_outcome to carry the full ProbeOutcome
-- enum (success + failure categories), not just the 5 ArchiveAction
-- success values from PR 1's migration. Reflects the typed
-- ProbeOutcome introduced in supabase/functions/_shared/probe_outcome.ts.
--
-- Why now: PR 1's cooldown only acted on unchanged_verified, which is
-- a single failure mode. The 448-school force-resolve batch on
-- 2026-04-18 surfaced 11 distinct outcome categories — auth_walled
-- variants, dead_url, no_pdfs_found, etc. — each warranting a
-- different cooldown / re-check policy. This migration unblocks the
-- per-outcome policy logic by making the column able to carry the
-- structured category, and backfills historical rows by parsing
-- last_error so existing archive_queue history isn't lost.

-- Drop and re-add the CHECK constraint with the expanded value set.
-- All values mirror supabase/functions/_shared/probe_outcome.ts.
alter table public.archive_queue
  drop constraint if exists archive_queue_last_outcome_valid;

alter table public.archive_queue
  add constraint archive_queue_last_outcome_valid
  check (
    last_outcome is null
    or last_outcome in (
      -- ArchiveAction values (success outcomes from archiveOneSchool)
      'inserted',
      'refreshed',
      'unchanged_verified',
      'unchanged_repaired',
      'marked_removed',
      -- Failure outcomes (from PermanentError.category / TransientError.category)
      'dead_url',
      'auth_walled_microsoft',
      'auth_walled_okta',
      'auth_walled_google',
      'no_pdfs_found',
      'wrong_content_type',
      'file_too_large',
      'blocked_url',
      'transient',
      'permanent_other'
    )
  );

-- Backfill last_outcome for historical rows where the column is NULL
-- but last_error contains enough signal to categorise. Patterns mirror
-- categoriseLegacyError() in probe_outcome.ts. Order matters — more
-- specific patterns checked first so an "all candidates failed
-- permanently: ... login.microsoftonline.com ..." aggregated error
-- is correctly tagged as auth_walled_microsoft and not the catch-all.
--
-- Failed rows that don't match any pattern stay NULL (better to leave
-- a known unknown than to over-classify); they'll be re-classified
-- naturally on their next run when the typed throw site fires.

update public.archive_queue
set last_outcome = 'auth_walled_microsoft'
where last_outcome is null
  and status = 'failed_permanent'
  and (last_error ilike '%login.microsoftonline.com%' or last_error ilike '%/saml%');

update public.archive_queue
set last_outcome = 'auth_walled_okta'
where last_outcome is null
  and status = 'failed_permanent'
  and last_error ilike '%.okta.com%';

update public.archive_queue
set last_outcome = 'auth_walled_google'
where last_outcome is null
  and status = 'failed_permanent'
  and last_error ilike '%accounts.google.com%';

update public.archive_queue
set last_outcome = 'dead_url'
where last_outcome is null
  and status = 'failed_permanent'
  and (last_error ilike '%http 404%' or last_error ilike '%http 410%' or last_error ilike '%upstream_gone%');

update public.archive_queue
set last_outcome = 'no_pdfs_found'
where last_outcome is null
  and status = 'failed_permanent'
  and (last_error ilike '%no cds found%' or last_error ilike '%no_cds_found%' or last_error ilike '%no anchors%');

update public.archive_queue
set last_outcome = 'wrong_content_type'
where last_outcome is null
  and status = 'failed_permanent'
  and (last_error ilike '%unsupported%' or last_error ilike '%magic%' or last_error ilike '%content type%');

update public.archive_queue
set last_outcome = 'blocked_url'
where last_outcome is null
  and status = 'failed_permanent'
  and (last_error ilike '%blocked%' or last_error ilike '%unsafe url%');

update public.archive_queue
set last_outcome = 'file_too_large'
where last_outcome is null
  and status = 'failed_permanent'
  and last_error ilike '%exceeds%bytes%';

update public.archive_queue
set last_outcome = 'transient'
where last_outcome is null
  and status = 'failed_permanent'
  and (last_error ilike '%http 5%' or last_error ilike '%timeout%' or last_error ilike '%transient%');

-- Whatever's left in failed_permanent without a category is
-- structurally permanent_other. This is the safety net so the column
-- is dense enough to be useful for analytics.
update public.archive_queue
set last_outcome = 'permanent_other'
where last_outcome is null
  and status = 'failed_permanent';

-- Add the partial index for cooldown lookups on the new failure
-- categories. The PR 1 index only covered (status=done,
-- last_outcome=unchanged_verified). New categories warrant their own
-- partial indexes if cooldown queries become common per-category;
-- for now a single broader partial index covers all
-- failed_permanent + last_outcome reads (which is the most common
-- ad-hoc analytics query: "show me schools by failure mode").
create index if not exists archive_queue_failure_outcome_idx
  on public.archive_queue (school_id, processed_at desc, last_outcome)
  where status = 'failed_permanent' and last_outcome is not null;
