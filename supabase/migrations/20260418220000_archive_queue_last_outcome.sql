-- Add last_outcome to archive_queue so archive-enqueue can apply a
-- per-school cooldown to schools whose previous run came back
-- unchanged_verified. Empirical motivation: a force-resolve batch of
-- 448 active-but-missing schools (2026-04-18) showed 52% returning
-- unchanged_verified, meaning the resolver re-fetched a single direct
-- PDF, hashed it, and confirmed no change. Each unchanged_verified
-- run is ~3-30 seconds of network + storage + DB time that produces no
-- new data. With monthly cron cadence, a school that returns
-- unchanged_verified every cycle costs ~12 wasted runs/year.
--
-- Cooldown lives at enqueue time (this column drives that filter) so
-- the queue stays a faithful record of "what we considered" — schools
-- in cooldown don't even appear as ready rows for the current run.
-- Operator overrides via force_school remain available because
-- force_school bypasses the queue entirely.
--
-- failed_permanent and other statuses are unaffected by this column.
-- A future PR (the typed ProbeOutcome enum) will replace this single
-- text field with structured outcome categories that distinguish
-- auth_walled_microsoft, dead_url, etc., so different cooldown
-- policies can apply per outcome class. Until then, last_outcome
-- mirrors the ArchiveAction values produced by archiveOneSchool.

alter table public.archive_queue
  add column last_outcome text;

comment on column public.archive_queue.last_outcome is
  'The ArchiveAction returned by archiveOneSchool (inserted, refreshed, unchanged_verified, unchanged_repaired, marked_removed) when status=done. NULL for status=ready/processing or when the row failed before producing an outcome. Used by archive-enqueue cooldown logic to skip recent unchanged_verified schools.';

-- Constraint matches the ArchiveAction enum in supabase/functions/_shared/archive.ts.
-- Keep these in sync — the Deno code is the source of truth, this constraint is
-- defense-in-depth so a buggy worker can't write a typo here.
alter table public.archive_queue
  add constraint archive_queue_last_outcome_valid
  check (
    last_outcome is null
    or last_outcome in (
      'inserted',
      'refreshed',
      'unchanged_verified',
      'unchanged_repaired',
      'marked_removed'
    )
  );

-- Index on (school_id, last_outcome, processed_at desc) supports the
-- archive-enqueue cooldown query: "for each candidate school, find the
-- most recent done row with last_outcome=unchanged_verified, check if
-- processed_at is within the cooldown window". Partial index keeps it
-- small — only rows that participate in the cooldown predicate.
create index archive_queue_cooldown_idx
  on public.archive_queue (school_id, processed_at desc)
  where status = 'done' and last_outcome = 'unchanged_verified';
