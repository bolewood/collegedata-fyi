-- Archive pipeline foundations
--
-- This migration lands three things that the archive-enqueue / archive-process
-- edge functions need before they can do anything useful:
--
--   1. Fix the silent NULL-uniqueness bug on cds_documents. The original
--      constraint UNIQUE (school_id, sub_institutional, cds_year) does not
--      actually prevent duplicate rows for the common case where a school has
--      no sub-institutional variant, because Postgres treats NULL as distinct
--      by default. Every "one CDS per school per year" row can be inserted
--      any number of times and ON CONFLICT will never fire. We switch the
--      constraint to NULLS NOT DISTINCT (Postgres 15+, Supabase runs 17).
--
--   2. Create archive_queue, a tiny work-queue table the archive-process
--      edge function drains one row per invocation. This avoids the 256 MB
--      memory + 400s wall clock caps on Supabase Edge Functions by
--      distributing ~840 schools across ~840 separate invocations. Status
--      lifecycle: ready -> processing -> (done | failed_permanent) with a
--      10-minute visibility timeout so a crashed processor can't wedge a row.
--
--   3. Create the claim_archive_queue_row() RPC used by archive-process to
--      atomically claim one row under FOR UPDATE SKIP LOCKED, handling
--      visibility timeout in the same query so the caller stays simple.
--
-- The migration includes an inline self-test for the NULLS NOT DISTINCT fix
-- at the bottom. If the constraint swap doesn't actually enforce uniqueness,
-- the migration aborts and rolls back.
--
-- Wrapped in an explicit BEGIN/COMMIT because Supabase CLI does NOT apply
-- migrations in a single implicit transaction — each statement is
-- auto-committed by default. The explicit block is required for LOCK TABLE
-- to span statements and for the whole migration to roll back atomically
-- if the self-test at the bottom fails.
begin;

-- ─── cds_documents unique constraint fix ────────────────────────────────────

-- Take the table lock BEFORE checking for duplicates. Without this lock, a
-- concurrent writer could insert a duplicate (school_id, NULL, cds_year) row
-- between the guard check and the ALTER TABLE, causing the new constraint to
-- fail after we thought we were safe. ACCESS EXCLUSIVE is what ALTER TABLE
-- would take anyway, so acquiring it early just widens the coverage window.
lock table public.cds_documents in access exclusive mode;

-- Guard: if any dup (school_id, sub_institutional, cds_year) groups already
-- exist with NULL sub_institutional, the new constraint will fail to create.
-- Abort early with a clear error so the operator can clean up manually.
do $$
declare
  dup_count int;
begin
  select count(*) into dup_count
    from (
      select school_id, cds_year, count(*) as n
        from public.cds_documents
       where sub_institutional is null
       group by school_id, cds_year
      having count(*) > 1
    ) dups;

  if dup_count > 0 then
    raise exception
      'archive_pipeline migration aborted: % (school_id, cds_year) groups have duplicate rows with NULL sub_institutional. Clean these up before applying this migration so the NULLS NOT DISTINCT constraint can be created.',
      dup_count;
  end if;
end$$;

alter table public.cds_documents
  drop constraint cds_documents_unique_school_year;

alter table public.cds_documents
  add constraint cds_documents_unique_school_year
  unique nulls not distinct (school_id, sub_institutional, cds_year);

comment on constraint cds_documents_unique_school_year on public.cds_documents is
  'One row per (school, sub-institutional variant, CDS year). NULLS NOT DISTINCT because the common case is sub_institutional IS NULL and we need ON CONFLICT to fire for it. Without NULLS NOT DISTINCT, Postgres would treat every NULL as a distinct value and the archiver would silently insert duplicates.';

-- ─── cds_artifacts lookup index ─────────────────────────────────────────────
-- Non-unique, partial. Lets the archiver cheaply answer "have we already
-- archived these exact bytes under any document?" without a full table scan,
-- which is useful for debugging and for the "Storage object missing, re-upload"
-- repair path in archive-process.

create index if not exists cds_artifacts_source_sha_idx
  on public.cds_artifacts (sha256)
  where kind = 'source';

-- ─── archive_queue ──────────────────────────────────────────────────────────

create table public.archive_queue (
  id                uuid primary key default gen_random_uuid(),

  -- Identifies the batch. archive-enqueue sets one run_id per invocation
  -- and writes one row per active school. The (run_id, school_id) unique
  -- constraint makes re-enqueueing the same batch a no-op.
  enqueued_run_id   uuid not null,

  -- Denormalized from schools.yaml so archive-process never needs to
  -- re-fetch schools.yaml on each tick.
  school_id         text not null,
  school_name       text not null,
  cds_url_hint      text not null,

  -- Lifecycle
  status            text not null default 'ready',
  attempts          int  not null default 0,
  last_error        text,

  -- Bookkeeping
  enqueued_at       timestamptz not null default now(),
  claimed_at        timestamptz,
  processed_at      timestamptz,

  constraint archive_queue_status_valid
    check (status in ('ready', 'processing', 'done', 'failed_permanent')),

  constraint archive_queue_unique_school_per_run
    unique (enqueued_run_id, school_id)
);

comment on table public.archive_queue is
  'Work queue drained by supabase/functions/archive-process. One row per (monthly batch, school). archive-enqueue seeds rows with status=ready; archive-process claims one per invocation via claim_archive_queue_row(), runs the shared archive-one-school pipeline, and marks the row terminal (done or failed_permanent) in a finally block so a crashed processor cannot wedge the queue.';

comment on column public.archive_queue.enqueued_run_id is
  'Batch identifier. archive-enqueue picks one uuid per invocation and writes one row per active school. The (enqueued_run_id, school_id) unique constraint makes re-enqueueing the same batch a no-op so the outer cron is safe to double-fire.';

comment on column public.archive_queue.status is
  'ready = waiting to be claimed; processing = claimed by a processor (claimed_at is when); done = archive succeeded and row is terminal; failed_permanent = repeated failures or non-retryable error, row is terminal for manual inspection.';

comment on column public.archive_queue.attempts is
  'How many times archive-process has tried this row. Incremented on every finally-block write whether success or failure. After MAX_ATTEMPTS (enforced in the edge function, not the schema) the processor flips status to failed_permanent.';

comment on column public.archive_queue.claimed_at is
  'When the row transitioned ready -> processing. Used as the visibility timeout anchor: rows with status=processing and claimed_at older than 10 minutes are considered abandoned and re-claimable.';

-- Partial index covering the only shape claim_archive_queue_row() scans:
-- either ready rows or stale processing rows. Keeps the claim query fast
-- even when the queue has hundreds of thousands of terminal rows in history.
create index archive_queue_claimable_idx
  on public.archive_queue (enqueued_at)
  where status = 'ready' or status = 'processing';

-- Row-level security: service role only. This table is entirely internal
-- machinery; there is no public read story for it. RLS is enabled with no
-- policies so only the service_role key (which bypasses RLS) can touch it.
alter table public.archive_queue enable row level security;

-- ─── claim_archive_queue_row() RPC ──────────────────────────────────────────
-- Atomically claims one row from archive_queue for processing. Encapsulates
-- the FOR UPDATE SKIP LOCKED semantics + visibility timeout so the caller
-- (archive-process) stays a simple loop.
--
-- Returns the claimed row, or NULL if the queue has no eligible rows.
-- NULL is the "queue drained" signal — the edge function returns early
-- without logging a failure, and the next cron tick picks up whenever
-- the next batch lands.

create or replace function public.claim_archive_queue_row()
returns public.archive_queue
language plpgsql
security definer
set search_path = public
as $$
declare
  claimed public.archive_queue;
begin
  update public.archive_queue q
     set status = 'processing',
         claimed_at = now(),
         -- attempts is incremented HERE, not in the worker's finally block.
         -- A worker that OOMs, wall-clocks, or otherwise never reaches its
         -- finally would otherwise leave attempts at its old value, and
         -- the visibility timeout would let the same row be reclaimed
         -- forever on poison input. Incrementing in the claim means the
         -- retry cap (MAX_ATTEMPTS in archive-process) works even when
         -- the worker dies before it can update anything itself.
         attempts = q.attempts + 1
   where q.id = (
     select id
       from public.archive_queue
      where status = 'ready'
         or (status = 'processing' and claimed_at < now() - interval '10 minutes')
      order by enqueued_at asc
        for update skip locked
       limit 1
   )
  returning q.* into claimed;

  return claimed;  -- NULL if no row matched (queue drained)
end;
$$;

comment on function public.claim_archive_queue_row() is
  'Atomic queue claim for archive-process. Returns one row with status flipped to processing, claimed_at set to now(), and attempts incremented. Returns NULL if no ready rows exist. Handles visibility timeout inline: rows stuck in processing for more than 10 minutes are considered abandoned and become re-claimable. Uses FOR UPDATE SKIP LOCKED so concurrent processors never see the same row. attempts is incremented here rather than in the worker to make the retry cap crash-safe (a worker that dies before its finally block still consumes an attempt).';

-- Only the service role should call this. Lock down execute.
revoke all on function public.claim_archive_queue_row() from public;
revoke all on function public.claim_archive_queue_row() from anon, authenticated;
grant execute on function public.claim_archive_queue_row() to service_role;

-- ─── Self-test: NULLS NOT DISTINCT actually enforces uniqueness ─────────────
-- This verifies the whole point of the constraint swap. If Postgres is
-- somehow not enforcing uniqueness over NULL sub_institutional, the
-- migration aborts and rolls back. Running the migration and seeing it
-- commit IS the passing test for PR 1.

do $$
declare
  test_school constant text := '__archive_pipeline_migration_self_test__';
  test_year  constant text := '2099-00';
  collision_fired boolean := false;
begin
  -- Insert one row.
  insert into public.cds_documents (school_id, school_name, cds_year)
    values (test_school, 'Migration Self Test', test_year);

  -- Try to insert a duplicate with the same NULL sub_institutional.
  -- Before this migration this would have silently succeeded. After,
  -- it must raise unique_violation.
  begin
    insert into public.cds_documents (school_id, school_name, cds_year)
      values (test_school, 'Migration Self Test', test_year);
  exception when unique_violation then
    collision_fired := true;
  end;

  -- Clean up regardless of outcome.
  delete from public.cds_documents where school_id = test_school;

  if not collision_fired then
    raise exception
      'archive_pipeline migration self-test FAILED: the NULLS NOT DISTINCT constraint did not fire on a duplicate insert. The archiver would still be able to create duplicate cds_documents rows for schools without sub-institutional variants. Aborting and rolling back.';
  end if;
end$$;

commit;
